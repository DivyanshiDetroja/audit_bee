"""
Document processing pipeline (DESIGN.md §6.1, 6.2, 6.3, 6.9).

Called as a FastAPI BackgroundTask immediately after upload.  Opens its own
DB session (the request session is already closed by then).

Flow:
  extract text  →  call Claude  →  parse result  →  normalize filename
  →  write classified / needs_review + processed_at

Every step is wrapped so any failure lands the document in needs_review
rather than crashing the background thread (§6.9).
"""

import io
import json
import logging
import re
import uuid
from datetime import datetime, timezone

import pdfplumber

from app import storage
from app.checklist import create_context_entry, match_and_update_checklist
from app.claude_client import get_client
from app.database import SessionLocal
from app.models import Client, Document, DocumentStatus
from app.probes import run_context_probe

log = logging.getLogger(__name__)

# ── Classifier prompt (verbatim from DESIGN.md §6.2) ──────────────────────────
_CLASSIFY_PROMPT = """\
You are a tax document classifier for a CPA firm. Given the text of one \
document, identify it and extract key fields. Respond with ONLY valid JSON, \
no prose, no markdown fences.

{{
  "doc_type": "one of: W-2, 1099-NEC, 1099-INT, 1099-DIV, 1098, K-1, \
prior_year_return, bank_statement, engagement_letter, other",
  "tax_year": "YYYY or null",
  "summary": "one sentence, plain language",
  "fields": {{ "issuer": "...", "recipient": "...", "key_amounts": {{...}} }},
  "confidence": 0.0
}}

If the document is unclear, set doc_type to "other" and confidence below 0.5.

Document text:
{document_text}"""

_MAX_TEXT_CHARS = 15_000  # ~4 000 tokens; enough for any single tax document


# ── Text extraction ────────────────────────────────────────────────────────────

def _extract_text(doc: Document) -> str:
    try:
        data = storage.load_file(doc.storage_key)
    except Exception as exc:
        log.warning("pipeline: could not load file %s: %s", doc.storage_key, exc)
        return "[File could not be loaded]"

    if doc.mime_type == "application/pdf":
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages[:20]]
            text = "\n\n".join(t for t in pages if t.strip())
            return text or "[No extractable text in this PDF]"
        except Exception as exc:
            log.warning("pipeline: pdfplumber failed for %s: %s", doc.id, exc)
            return "[PDF text extraction failed]"

    # Image documents — pdfplumber can't handle these.
    # Claude's text-only API can't classify them directly, so they'll land in
    # needs_review.  Vision support is a Phase 4+ enhancement.
    return (
        f"[Image document — MIME type: {doc.mime_type}, "
        f"filename: {doc.original_filename}. "
        "Text extraction is not available for image files.]"
    )


# ── Claude classify call ───────────────────────────────────────────────────────

def _call_claude(text: str) -> dict:
    """Call the Claude classifier.  Raises on any error (caller handles it)."""
    client = get_client()
    prompt = _CLASSIFY_PROMPT.format(document_text=text[:_MAX_TEXT_CHARS])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Defensive strip: Claude occasionally wraps JSON in markdown fences despite
    # the instruction not to.
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?\s*```\s*$", "", raw)

    data = json.loads(raw)  # raises JSONDecodeError on bad output → needs_review

    if "doc_type" not in data:
        raise ValueError("Claude response missing required 'doc_type' field")

    return data


# ── Filename normalisation (DESIGN.md §6.3) ───────────────────────────────────

def _normalize_filename(client_name: str, doc_type: str | None, tax_year: int | None) -> str:
    """
    Pattern: {ClientLastName}_{DocType}_{TaxYear}.pdf
    Original filename is always preserved on the Document row — this is only the
    display / filing name.
    """
    words = client_name.strip().split()
    last_name = re.sub(r"[^\w]", "", words[-1]) if words else "Unknown"
    dt = re.sub(r"[^\w-]", "", doc_type or "unknown")
    year = str(tax_year) if tax_year else "unknownyear"
    return f"{last_name}_{dt}_{year}.pdf"


# ── Pipeline entry point ───────────────────────────────────────────────────────

def process_document(document_id: uuid.UUID) -> None:
    """
    Background task.  Opens its own DB session — the upload handler's session
    is already closed before this runs.
    """
    db = SessionLocal()
    try:
        _run(document_id, db)
    except Exception as exc:
        # Outer safety net — individual steps already handle their own errors,
        # but this prevents the background thread from dying silently.
        log.exception("pipeline: unexpected error for document %s: %s", document_id, exc)
    finally:
        db.close()


def _run(document_id: uuid.UUID, db) -> None:
    doc: Document | None = db.query(Document).filter_by(id=document_id).first()
    if not doc:
        log.warning("pipeline: document %s not found", document_id)
        return

    client_row: Client | None = db.query(Client).filter_by(id=doc.client_id).first()
    if not client_row:
        log.warning("pipeline: client for document %s not found", document_id)
        _set_needs_review(doc, db)
        return

    # 1. Extract text
    text = _extract_text(doc)

    # 2. Call Claude (§6.9: any failure → needs_review, never raise)
    try:
        result = _call_claude(text)
    except Exception as exc:
        log.warning("pipeline: Claude call failed for %s: %s", document_id, exc)
        _set_needs_review(doc, db)
        return

    # 3. Populate document fields from Claude's response
    doc.doc_type = result.get("doc_type")

    raw_year = result.get("tax_year")
    if raw_year and str(raw_year).isdigit() and len(str(raw_year)) == 4:
        doc.tax_year = int(str(raw_year))

    doc.extracted_summary = result.get("summary")
    doc.extracted_fields = result.get("fields") or {}

    confidence = float(result.get("confidence", 0.0))

    if doc.doc_type == "other" or confidence < 0.5:
        doc.status = DocumentStatus.needs_review
    else:
        doc.status = DocumentStatus.classified

    # 4. Normalised filename (§6.3) — original_filename is always retained
    doc.normalized_filename = _normalize_filename(
        client_row.name, doc.doc_type, doc.tax_year
    )

    # 5. Checklist + context (§6.4): only for high-confidence classifications
    if doc.status == DocumentStatus.classified:
        match_and_update_checklist(doc, db)
        create_context_entry(doc, result, db)
        # 6. Context probe (§6.5) — silently skipped on any failure
        run_context_probe(client_row, db)

    doc.processed_at = datetime.now(timezone.utc)
    db.commit()

    log.info(
        "pipeline: document %s → status=%s doc_type=%s normalized=%s",
        document_id, doc.status.value, doc.doc_type, doc.normalized_filename,
    )


def _set_needs_review(doc: Document, db) -> None:
    doc.status = DocumentStatus.needs_review
    doc.processed_at = datetime.now(timezone.utc)
    db.commit()

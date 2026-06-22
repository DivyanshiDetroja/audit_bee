"""
Checklist engine (DESIGN.md §6.4).

Defines the per-client-type required-document lists and provides two service
functions:
  - seed_checklist(client, db)  — idempotent; creates RequiredDocument rows
  - match_and_update_checklist(doc, db)  — flips a pending item to received
    when a document is classified; called from pipeline._run().
"""

from app.models import (
    Client,
    ClientType,
    ContextEntry,
    ContextSource,
    Document,
    DocumentStatus,
    RequiredDocument,
    RequiredDocStatus,
)
from sqlalchemy.orm import Session


INDIVIDUAL_CHECKLIST = [
    {"doc_type": "W-2",               "label": "W-2 Wage and Tax Statement",         "required": True},
    {"doc_type": "1099-INT",           "label": "1099-INT Interest Income",            "required": True},
    {"doc_type": "1099-DIV",           "label": "1099-DIV Dividends and Distributions","required": False},
    {"doc_type": "1098",               "label": "1098 Mortgage Interest Statement",    "required": False},
    {"doc_type": "prior_year_return",  "label": "Prior Year Tax Return",               "required": True},
]

BUSINESS_CHECKLIST = [
    {"doc_type": "profit_and_loss",   "label": "Profit & Loss Statement",             "required": True},
    {"doc_type": "balance_sheet",     "label": "Balance Sheet",                       "required": True},
    {"doc_type": "1099-NEC",          "label": "1099-NEC Non-Employee Compensation",  "required": True},
    {"doc_type": "bank_statement",    "label": "Business Bank Statements",            "required": True},
    {"doc_type": "prior_year_return", "label": "Prior Year Business Tax Return",      "required": True},
]


def seed_checklist(client: Client, db: Session) -> list[RequiredDocument]:
    """Create RequiredDocument rows for *client* based on its type.

    Idempotent: if any rows already exist for this client, returns empty list
    and does nothing.  Caller is responsible for db.commit().
    """
    existing = db.query(RequiredDocument).filter_by(client_id=client.id).first()
    if existing:
        return []

    template = (
        INDIVIDUAL_CHECKLIST
        if client.type == ClientType.individual
        else BUSINESS_CHECKLIST
    )

    items = [
        RequiredDocument(
            client_id=client.id,
            doc_type=item["doc_type"],
            label=item["label"],
            required=item["required"],
            status=RequiredDocStatus.pending,
        )
        for item in template
    ]
    db.add_all(items)
    return items


def match_and_update_checklist(doc: Document, db: Session) -> RequiredDocument | None:
    """Flip the pending checklist item whose doc_type matches *doc* to received.

    Only acts when doc.status is classified and doc.doc_type is set.
    Returns the updated RequiredDocument, or None if no match.
    Caller is responsible for db.commit().
    """
    if doc.status != DocumentStatus.classified or not doc.doc_type:
        return None

    item = (
        db.query(RequiredDocument)
        .filter_by(
            client_id=doc.client_id,
            doc_type=doc.doc_type,
            status=RequiredDocStatus.pending,
        )
        .first()
    )

    if item:
        item.status = RequiredDocStatus.received
        item.satisfied_by_document_id = doc.id

    return item


def build_context_content(doc: Document, result: dict) -> str:
    """Build a human-readable ContextEntry content string from a classified doc."""
    parts: list[str] = []

    doc_type = result.get("doc_type", "unknown document")
    parts.append(f"Received and classified: {doc_type}.")

    if summary := result.get("summary"):
        parts.append(summary)

    fields = result.get("fields") or {}
    details: list[str] = []

    if issuer := fields.get("issuer"):
        details.append(f"Issuer: {issuer}")
    if recipient := fields.get("recipient"):
        details.append(f"Recipient: {recipient}")
    if isinstance(fields.get("key_amounts"), dict):
        for k, v in list(fields["key_amounts"].items())[:3]:
            details.append(f"{k}: {v}")

    if details:
        parts.append(" | ".join(details))

    return " ".join(parts)


def create_context_entry(doc: Document, result: dict, db: Session) -> ContextEntry:
    """Create and add (but not commit) a ContextEntry for a classified document."""
    content = build_context_content(doc, result)
    entry = ContextEntry(
        client_id=doc.client_id,
        content=content,
        source=ContextSource.document,
        created_by=doc.uploaded_by,
    )
    db.add(entry)
    return entry

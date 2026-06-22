"""
Context-probe service (DESIGN.md §6.5).

Runs a second Claude call after document classification to decide whether the
client's context has a genuine ambiguity that needs the CPA's input.  Called
from the pipeline background task, so:
  - Receives the existing DB session; does NOT open its own.
  - Must never raise — any failure is logged and silently skipped.
"""

import json
import logging
import re

from sqlalchemy.orm import Session

from app.claude_client import get_client
from app.models import Client, ContextEntry, ContextProbe, ProbeStatus

log = logging.getLogger(__name__)

# Prompt verbatim from DESIGN.md §6.5 — braces around JSON keys doubled for .format()
_PROBE_PROMPT = """\
You are assisting a CPA. Given a client's current document context, decide \
whether anything is ambiguous enough to need the CPA's input before the \
return can proceed. Respond ONLY as JSON, no prose, no markdown fences.

{{"needs_input": true, "question": "one specific question or null"}}
{{"needs_input": false, "question": null}}

Only flag genuine ambiguities. Do not nitpick.

Context:
{client_context}"""


def _build_context_string(client_id, db: Session) -> str:
    entries = (
        db.query(ContextEntry)
        .filter_by(client_id=client_id)
        .order_by(ContextEntry.created_at.asc())
        .all()
    )
    return "\n\n".join(e.content for e in entries)


def _call_probe(context: str) -> dict:
    """Call Claude with the probe prompt.  Raises on any error (caller handles)."""
    client = get_client()
    prompt = _PROBE_PROMPT.format(client_context=context)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?\s*```\s*$", "", raw)

    data = json.loads(raw)

    if "needs_input" not in data:
        raise ValueError("probe response missing 'needs_input'")

    return data


def run_context_probe(client: Client, db: Session) -> ContextProbe | None:
    """
    Try to create a ContextProbe for *client* based on its current context trail.

    Returns the new (uncommitted) ContextProbe if Claude flagged an ambiguity,
    otherwise None.  Never raises.  Caller commits.
    """
    # Flush so the ContextEntry created moments earlier is visible to this query
    # (session has autoflush=False).
    db.flush()
    context = _build_context_string(client.id, db)
    if not context:
        return None

    try:
        result = _call_probe(context)
    except Exception as exc:
        log.warning("probe: Claude call failed for client %s: %s", client.id, exc)
        return None

    if not result.get("needs_input"):
        return None

    question = result.get("question")
    if not question:
        return None

    probe = ContextProbe(
        client_id=client.id,
        question=question,
        status=ProbeStatus.open,
    )
    db.add(probe)
    log.info("probe: created open probe for client %s: %s", client.id, question[:80])
    return probe

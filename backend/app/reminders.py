"""
AI-drafted reminder service (DESIGN.md §6.6).

The reminder is always drafted by Claude; the CPA reviews, optionally edits,
and explicitly sends.  Nothing is auto-sent.
"""

import json
import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.claude_client import get_client
from app.models import (
    Client,
    Reminder,
    ReminderChannel,
    ReminderStatus,
    RequiredDocument,
    RequiredDocStatus,
)

log = logging.getLogger(__name__)

# Prompt verbatim from DESIGN.md §6.6
_REMINDER_PROMPT = """\
Draft a short, warm, professional email from a CPA to a tax client \
reminding them of outstanding documents. Plain text, no placeholders left \
unfilled. Client: {client_name}. Still needed: {pending_items}.
Return JSON: {{ "subject": "...", "body": "..." }}"""


def _call_reminder(client_name: str, pending_items: str) -> dict:
    """Call Claude with the reminder prompt.  Raises on any error."""
    claude = get_client()
    prompt = _REMINDER_PROMPT.format(
        client_name=client_name,
        pending_items=pending_items,
    )

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?\s*```\s*$", "", raw)

    data = json.loads(raw)

    if "subject" not in data or "body" not in data:
        raise ValueError("reminder response missing 'subject' or 'body'")

    return data


def draft_reminder(client: Client, created_by_id: uuid.UUID, db: Session) -> Reminder:
    """
    Build the pending list, call Claude, create and return a draft Reminder.

    Raises ValueError("no_pending") if nothing is outstanding — caller turns
    this into a 422.  Raises any other exception on Claude failure — caller
    turns this into a 503.  Caller is responsible for db.commit().
    """
    pending = (
        db.query(RequiredDocument)
        .filter_by(client_id=client.id, status=RequiredDocStatus.pending)
        .all()
    )
    if not pending:
        raise ValueError("no_pending")

    pending_labels = ", ".join(item.label for item in pending)
    result = _call_reminder(client.name, pending_labels)

    reminder = Reminder(
        client_id=client.id,
        channel=ReminderChannel.email_sim,
        draft_subject=result.get("subject"),
        draft_body=result.get("body"),
        status=ReminderStatus.draft,
        created_by=created_by_id,
    )
    db.add(reminder)
    return reminder

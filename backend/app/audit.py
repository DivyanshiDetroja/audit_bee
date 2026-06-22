"""
Append-only audit logger.  Every document access, download, upload, and
user-management action must call log_event.  The log row is added to the
caller's open transaction — it commits (and becomes permanent) when the
endpoint's normal response path commits.

NOTE: for a production system, the audit write should use a separate
connection so it survives a rollback of the main operation.  Acceptable
for the demo.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_event(
    db: Session,
    *,
    user_id: uuid.UUID | None = None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip=ip,
            detail=detail,
        )
    )

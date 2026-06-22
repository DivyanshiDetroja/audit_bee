"""
Integrations router (DESIGN.md §6.8).

These integrations are DEMO SIMULATIONS.  No real OAuth handshakes are built.
Gmail / DocuSign / Calendly / QuickBooks appear as "Connected" surfaces to
tell the channel-agnostic story; toggling is cosmetic and is disclosed as such
in the demo script.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.integrations.schemas import IntegrationOut
from app.models import Integration, IntegrationStatus, User, UserRole

router = APIRouter(tags=["integrations"])


@router.get("/integrations", response_model=list[IntegrationOut])
def list_integrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Integration]:
    """Return all integrations for the current user's firm."""
    return (
        db.query(Integration)
        .filter_by(firm_id=current_user.firm_id)
        .order_by(Integration.name)
        .all()
    )


@router.post("/integrations/{integration_id}/toggle", response_model=IntegrationOut)
def toggle_integration(
    integration_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> Integration:
    """
    Toggle an integration between connected and disconnected.

    DEMO SIMULATION — cosmetic only; no real OAuth credentials are stored or
    revoked.  Returns 404 if the integration is not in the current user's firm
    (closes IDOR per DESIGN.md §5.2).
    """
    integration = (
        db.query(Integration)
        .filter_by(id=integration_id, firm_id=current_user.firm_id)
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404)

    if integration.status == IntegrationStatus.connected:
        integration.status = IntegrationStatus.disconnected
        integration.connected_at = None
    else:
        integration.status = IntegrationStatus.connected
        integration.connected_at = datetime.now(timezone.utc)

    ip = request.client.host if request.client else None
    log_event(
        db,
        user_id=current_user.id,
        action="integration_toggled",
        resource_type="integration",
        resource_id=str(integration.id),
        ip=ip,
        detail={
            "name": integration.name,
            "new_status": integration.status.value,
        },
    )
    db.commit()
    db.refresh(integration)
    return integration

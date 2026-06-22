"""
Authorization dependencies for every data endpoint.

The hard rule (DESIGN.md §5.2 + §6.7):
  - Unauthorized access to a resource returns 404, not 403.
  - Object-level checks run on every endpoint that reads or mutates client data.
  - admin  → all resources within user.firm_id
  - cpa    → only clients where client.assigned_cpa_id == user.id
  - client → only resources where resource.client_id == user.client_id
"""

import uuid

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.service import decode_token
from app.database import get_db
from app.models import Client, User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Authentication ─────────────────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Malformed token")

    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


# ── Role gate (coarse) ─────────────────────────────────────────────────────────

def require_role(*roles: UserRole):
    """Returns a dependency that asserts the authenticated user has one of the
    given roles. Use as: Depends(require_role(UserRole.admin, UserRole.cpa))"""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return dependency


# ── Object-level gate (fine, mandatory) ───────────────────────────────────────

def authorize_client_access(
    client_id: uuid.UUID,
    user: User,
    db: Session,
) -> Client:
    """
    Exact implementation from DESIGN.md Section 6.7.

    Never returns 403 — unauthorized access to a resource is 404 so that
    existence is not confirmed to the caller (closes IDOR).
    """
    client = db.query(Client).filter_by(id=client_id).first()

    if client is None or client.firm_id != user.firm_id:
        raise HTTPException(status_code=404)

    if user.role == UserRole.client and user.client_id != client.id:
        raise HTTPException(status_code=404)

    if user.role == UserRole.cpa and client.assigned_cpa_id != user.id:
        raise HTTPException(status_code=404)

    # admin within firm passes — falls through
    return client


def get_authorized_client(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Client:
    """FastAPI path-parameter dependency. Wire this into any endpoint that takes
    {client_id} in the path to get automatic object-level authorization."""
    return authorize_client_access(client_id, current_user, db)

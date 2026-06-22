import uuid
from collections import defaultdict
from threading import Lock
from time import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import authorize_client_access, get_current_user, require_role
from app.auth.schemas import (
    AssignCPARequest,
    AuditLogOut,
    ClientOut,
    InviteClientRequest,
    InviteRequest,
    InviteResponse,
    LoginRequest,
    MeResponse,
    RedeemRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.auth.service import (
    create_access_token,
    create_invite_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.audit import log_event
from app.database import get_db
from sqlalchemy import func
from app.models import AuditLog, Client, RequiredDocument, RequiredDocStatus, User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])

# ── In-process rate limiter for the login endpoint ────────────────────────────
# Per-IP sliding window: 5 attempts per 60 s.
# NOTE: single-process only — acceptable for the demo; use Redis in production.
_login_attempts: dict[str, list[float]] = defaultdict(list)
_lock = Lock()
_RATE_WINDOW = 60
_RATE_MAX = 5


def _check_login_rate(ip: str) -> None:
    now = time()
    with _lock:
        times = _login_attempts[ip]
        times[:] = [t for t in times if now - t < _RATE_WINDOW]
        if len(times) >= _RATE_MAX:
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Please try again later.",
            )
        times.append(now)


# ── Login ──────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    _check_login_rate(ip)

    user = db.query(User).filter_by(email=body.email, is_active=True).first()

    # Generic message — never reveal which field was wrong (DESIGN.md §5.6)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(
        str(user.id),
        user.role.value,
        str(user.firm_id),
        str(user.client_id) if user.client_id else None,
    )
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ── Refresh ────────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Wrong token type")

    user = db.query(User).filter_by(id=payload.get("sub"), is_active=True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(
        str(user.id),
        user.role.value,
        str(user.firm_id),
        str(user.client_id) if user.client_id else None,
    )
    new_refresh = create_refresh_token(str(user.id))

    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


# ── Firm users list (admin) ────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserOut])
def list_users(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[User]:
    return (
        db.query(User)
        .filter_by(firm_id=current_user.firm_id)
        .order_by(User.role, User.name)
        .all()
    )


# ── Audit log (admin) ─────────────────────────────────────────────────────────

@router.get("/audit-log", response_model=list[AuditLogOut])
def get_audit_log(
    limit: int = 200,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    firm_user_ids = [
        u.id
        for u in db.query(User.id).filter_by(firm_id=current_user.firm_id).all()
    ]
    return (
        db.query(AuditLog)
        .filter(AuditLog.user_id.in_(firm_user_ids))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


# ── Client list (cpa / admin) ─────────────────────────────────────────────────

def _attach_pending_counts(clients: list[Client], db: Session) -> list[Client]:
    if not clients:
        return clients
    ids = [c.id for c in clients]
    counts = dict(
        db.query(RequiredDocument.client_id, func.count())
        .filter(
            RequiredDocument.client_id.in_(ids),
            RequiredDocument.status == RequiredDocStatus.pending,
        )
        .group_by(RequiredDocument.client_id)
        .all()
    )
    for c in clients:
        c.pending_count = counts.get(c.id, 0)
    return clients


@router.get("/clients-list", response_model=list[ClientOut])
def list_clients(
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cpa)),
    db: Session = Depends(get_db),
) -> list[Client]:
    q = db.query(Client).filter_by(firm_id=current_user.firm_id)
    if current_user.role == UserRole.cpa:
        q = q.filter_by(assigned_cpa_id=current_user.id)
    clients = q.order_by(Client.name).all()
    return _attach_pending_counts(clients, db)


@router.get("/clients-list/{client_id}", response_model=ClientOut)
def get_client(
    client_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cpa)),
    db: Session = Depends(get_db),
) -> Client:
    from app.auth.dependencies import authorize_client_access
    client = authorize_client_access(client_id, current_user, db)
    return _attach_pending_counts([client], db)[0]


@router.patch("/clients-list/{client_id}/assign", response_model=ClientOut)
def assign_cpa(
    client_id: uuid.UUID,
    body: AssignCPARequest,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
) -> Client:
    client = db.query(Client).filter_by(id=client_id, firm_id=current_user.firm_id).first()
    if not client:
        raise HTTPException(status_code=404)
    if body.assigned_cpa_id is not None:
        cpa = db.query(User).filter_by(
            id=body.assigned_cpa_id, firm_id=current_user.firm_id, role=UserRole.cpa
        ).first()
        if not cpa:
            raise HTTPException(status_code=422, detail="CPA not found in this firm")
    client.assigned_cpa_id = body.assigned_cpa_id
    db.commit()
    db.refresh(client)
    return client


@router.post("/clients-list/{client_id}/invite", response_model=InviteResponse)
def invite_client_user(
    client_id: uuid.UUID,
    body: InviteClientRequest,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cpa)),
    db: Session = Depends(get_db),
) -> InviteResponse:
    from app.auth.dependencies import authorize_client_access
    client = authorize_client_access(client_id, current_user, db)

    if db.query(User).filter_by(client_id=client.id).first():
        raise HTTPException(status_code=409, detail="Client already has an account")

    client.email = body.email
    jti = str(uuid.uuid4())
    client.invite_token_jti = jti
    db.commit()

    token = create_invite_token(str(client.id), str(client.firm_id), body.email, jti)
    return InviteResponse(invite_token=token)


# ── Current user ───────────────────────────────────────────────────────────────

@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role.value,
        firm_id=str(current_user.firm_id),
        client_id=str(current_user.client_id) if current_user.client_id else None,
    )


# ── Invite (admin or cpa issues a single-use token for a client) ───────────────

@router.post("/invite", response_model=InviteResponse)
def issue_invite(
    body: InviteRequest,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cpa)),
    db: Session = Depends(get_db),
):
    # CPA can only invite clients they are assigned to; admin sees all.
    # authorize_client_access enforces this per §6.7.
    client = authorize_client_access(body.client_id, current_user, db)

    # Reject if this client already has an account
    existing = db.query(User).filter_by(client_id=client.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Client already has an account")

    # Optionally update the client email
    if body.email:
        client.email = body.email

    if not client.email:
        raise HTTPException(
            status_code=422, detail="Client has no email address. Provide one in this request."
        )

    # Generate a single-use JTI and store it on the client record
    jti = str(uuid.uuid4())
    client.invite_token_jti = jti
    db.commit()

    token = create_invite_token(
        str(client.id), str(client.firm_id), client.email, jti
    )

    # In production this token would be emailed to the client; for the demo it
    # is returned to the CPA who can share it via any channel.
    return InviteResponse(invite_token=token)


# ── Redeem (client sets password and creates their account) ───────────────────

@router.post("/redeem", response_model=TokenResponse)
def redeem_invite(body: RedeemRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.invite_token)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")

    if payload.get("purpose") != "invite":
        raise HTTPException(status_code=400, detail="Wrong token type")

    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    client_id = payload.get("client_id")
    jti = payload.get("jti")
    email = payload.get("email")
    firm_id = payload.get("firm_id")

    client = db.query(Client).filter_by(id=client_id).first()
    if not client:
        raise HTTPException(status_code=404)

    # Single-use check: JTI must match what's stored on the client record
    if not client.invite_token_jti or client.invite_token_jti != jti:
        raise HTTPException(status_code=400, detail="Invite token has already been used or revoked")

    # Belt-and-suspenders: check no user exists for this client yet
    if db.query(User).filter_by(client_id=client.id).first():
        raise HTTPException(status_code=409, detail="Account already exists for this client")

    new_user = User(
        firm_id=uuid.UUID(firm_id),
        email=email,
        password_hash=hash_password(body.password),
        role=UserRole.client,
        name=body.name,
        client_id=client.id,
        is_active=True,
    )
    db.add(new_user)

    # Invalidate the token so it cannot be redeemed a second time
    client.invite_token_jti = None

    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(
        str(new_user.id),
        new_user.role.value,
        str(new_user.firm_id),
        str(new_user.client_id),
    )
    refresh_token = create_refresh_token(str(new_user.id))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)

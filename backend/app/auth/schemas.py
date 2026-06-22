import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class InviteRequest(BaseModel):
    client_id: uuid.UUID
    # Optionally set/override the client's email when issuing the invite.
    # If omitted, the email already on the Client record is used.
    email: str | None = None


class InviteResponse(BaseModel):
    invite_token: str
    expires_in_days: int = 7


class RedeemRequest(BaseModel):
    invite_token: str
    password: str
    name: str


class MeResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    firm_id: str
    client_id: str | None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    name: str
    role: str
    firm_id: uuid.UUID
    client_id: uuid.UUID | None
    is_active: bool
    created_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    resource_type: str
    resource_id: str
    ip: str | None
    detail: dict
    created_at: datetime


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    firm_id: uuid.UUID
    name: str
    type: str
    assigned_cpa_id: uuid.UUID | None
    created_at: datetime
    pending_count: int = 0


class AssignCPARequest(BaseModel):
    assigned_cpa_id: uuid.UUID | None


class InviteClientRequest(BaseModel):
    email: str

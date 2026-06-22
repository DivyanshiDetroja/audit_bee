from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from jose import JWTError, jwt

from app.config import settings

_ph = PasswordHasher()  # argon2id by default in argon2-cffi

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30
INVITE_TOKEN_EXPIRE_DAYS = 7


# ── Password hashing ───────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, VerificationError):
        return False


# ── JWT helpers ────────────────────────────────────────────────────────────────

def _encode(payload: dict, expires_delta: timedelta) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(data, settings.jwt_secret, algorithm=ALGORITHM)


def create_access_token(
    user_id: str,
    role: str,
    firm_id: str,
    client_id: str | None,
) -> str:
    return _encode(
        {
            "sub": user_id,
            "role": role,
            "firm_id": firm_id,
            "client_id": client_id,
            "type": "access",
        },
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> str:
    return _encode(
        {"sub": user_id, "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_invite_token(
    client_id: str,
    firm_id: str,
    email: str,
    jti: str,
) -> str:
    return _encode(
        {
            "purpose": "invite",
            "client_id": client_id,
            "firm_id": firm_id,
            "email": email,
            "jti": jti,
        },
        timedelta(days=INVITE_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError(str(exc)) from exc

"""JWT token creation and verification utilities."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from backend.app.core.config import get_settings

settings = get_settings()

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra: dict | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    secret = (
        settings.jwt_secret_key
        if token_type == ACCESS_TOKEN_TYPE
        else settings.jwt_refresh_secret_key
    )
    return jwt.encode(payload, secret, algorithm="HS256")


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        extra={"role": role},
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_access_token(token: str) -> dict:
    """Decode and validate access token. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise JWTError("wrong token type")
    return payload


def decode_refresh_token(token: str) -> dict:
    """Decode and validate refresh token. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.jwt_refresh_secret_key, algorithms=["HS256"])
    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise JWTError("wrong token type")
    return payload

"""Password hashing and JWT access tokens."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

ACCESS_TOKEN_TYPE = "access"

_ph = PasswordHasher()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _ph.verify(password_hash, plain)
    except VerifyMismatchError:
        return False


def create_access_token(*, user_id: uuid.UUID, now: datetime | None = None) -> tuple[str, int]:
    settings = get_settings()
    issued_at = now or datetime.now(timezone.utc)
    expires_in = settings.access_token_expire_seconds
    expire = issued_at + timedelta(seconds=expires_in)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "typ": ACCESS_TOKEN_TYPE,
        "iat": int(issued_at.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_in


def decode_access_token(token: str) -> uuid.UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise ValueError("invalid token") from exc
    if payload.get("typ") != ACCESS_TOKEN_TYPE:
        raise ValueError("invalid token type")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("missing subject")
    return uuid.UUID(str(sub))

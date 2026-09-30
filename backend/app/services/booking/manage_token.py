from __future__ import annotations

import hashlib
import hmac
import secrets

_MANAGE_TOKEN_BYTES = 32


def generate_manage_token() -> str:
    """Return a URL-safe manage token with at least 128 bits of entropy."""
    return secrets.token_urlsafe(_MANAGE_TOKEN_BYTES)


def hash_manage_token(raw_token: str, *, pepper: str) -> str:
    """Derive a stored HMAC-SHA256 hex digest for the raw manage token."""
    return hmac.new(
        pepper.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_manage_token(
    raw_token: str,
    stored_hash: str | None,
    *,
    pepper: str,
) -> bool:
    """Constant-time compare of raw token against stored hash; False if hash missing."""
    if not raw_token or stored_hash is None:
        return False
    expected = hash_manage_token(raw_token, pepper=pepper)
    return hmac.compare_digest(expected, stored_hash)

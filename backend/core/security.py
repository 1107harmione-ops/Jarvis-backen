"""
JARVIS V3 — Security Module
JWT auth, password hashing, encryption, and input validation.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from backend.core.config import get_settings

# ── Password Hashing ────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Tokens ──────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str  # user id or identifier
    exp: datetime
    iat: datetime
    role: str = "user"
    scp: list[str] = []  # scopes/permissions


def create_access_token(
    subject: str,
    role: str = "user",
    scopes: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))

    payload = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "role": role,
        "scp": scopes or [],
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token with longer expiry."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.refresh_token_expire_days))

    payload = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def verify_token(token: str) -> Optional[TokenPayload]:
    """Verify a JWT token and return its payload, or None if invalid."""
    try:
        payload = decode_token(token)
        return TokenPayload(
            sub=payload.get("sub", ""),
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            role=payload.get("role", "user"),
            scp=payload.get("scp", []),
        )
    except (JWTError, KeyError, ValueError):
        return None


# ── API Key Generation ─────────────────────────────────────────

def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key pair.
    Returns (raw_key, key_hash) — store the hash, return the raw key once.
    """
    raw_key = f"jv_{secrets.token_urlsafe(32)}"
    key_hash = hash_password(raw_key)
    return raw_key, key_hash


# ── HMAC Signatures ────────────────────────────────────────────

def sign_payload(payload: str, secret: str | None = None) -> str:
    """Create an HMAC-SHA256 signature for a payload."""
    key = (secret or get_settings().secret_key).encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def verify_signature(payload: str, signature: str, secret: str | None = None) -> bool:
    """Verify an HMAC-SHA256 signature in constant time."""
    key = (secret or get_settings().secret_key).encode()
    expected = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Input Validation Utilities ─────────────────────────────────

def sanitize_input(text: str, max_length: int = 4096) -> str:
    """Sanitize user input: strip control chars, limit length."""
    import re
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return cleaned[:max_length]


def validate_device_id(device_id: str) -> bool:
    """Validate a device ID format (alphanumeric + hyphens, 8-64 chars)."""
    import re
    return bool(re.match(r"^[a-zA-Z0-9\-_]{8,64}$", device_id))


def validate_filename(filename: str) -> bool:
    """Validate filename: no path traversal, no special chars."""
    import re
    return bool(re.match(r"^[a-zA-Z0-9_\-\.]{1,255}$", filename)) and not filename.startswith(".")


# ── Rate Limit Key Helpers ─────────────────────────────────────

def rate_limit_key_ip(client_ip: str) -> str:
    """Generate a rate limit key for an IP."""
    return f"rl:ip:{client_ip}"


def rate_limit_key_user(user_id: str) -> str:
    """Generate a rate limit key for a user."""
    return f"rl:usr:{user_id}"

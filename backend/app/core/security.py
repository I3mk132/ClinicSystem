"""
Password hashing, JWT helpers, one-time verification codes, and API keys.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, extra_claims: Optional[dict[str, Any]] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# One-time verification codes (account verification / password reset)
# ---------------------------------------------------------------------------
def generate_otp_code(length: int = 6) -> str:
    """A numeric code (e.g. '482913') suitable for email/SMS - easy to type on a phone."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def hash_code(code: str) -> str:
    # Reuses the same bcrypt context as passwords - it's just a short-lived secret string.
    return pwd_context.hash(code)


def verify_code(plain_code: str, hashed_code: str) -> bool:
    return pwd_context.verify(plain_code, hashed_code)


# ---------------------------------------------------------------------------
# API keys (server-to-server / bot integrations - see routers/public.py)
# ---------------------------------------------------------------------------
API_KEY_PREFIX = "ck_"  # "clinic key" - shown to admins so keys are visually recognizable


def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, hashed_key, key_prefix). Only `raw_key` is ever shown to the user."""
    raw_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    hashed = hashlib.sha256(raw_key.encode()).hexdigest()
    prefix = raw_key[:10]
    return raw_key, hashed, prefix


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


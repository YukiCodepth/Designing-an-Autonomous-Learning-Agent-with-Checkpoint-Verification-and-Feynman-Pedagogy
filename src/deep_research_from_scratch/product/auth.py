"""Authentication helpers for the product API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from deep_research_from_scratch.product.config import settings


# Use a pure-Python scheme to avoid runtime backend issues from bcrypt/passlib
# version mismatches inside the self-hosted Docker stack.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a hash."""
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str) -> str:
    """Create a signed JWT access token for a user id."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Decode a JWT token into a user id."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None
    return payload.get("sub")


def create_invite_token(*, workspace_id: str, email: str, role: str) -> str:
    """Create a signed invitation token."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.invite_expire_hours)
    payload: dict[str, Any] = {
        "workspace_id": workspace_id,
        "email": email,
        "role": role,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.invite_secret, algorithm=settings.jwt_algorithm)


def decode_invite_token(token: str) -> dict[str, Any] | None:
    """Decode an invite token into its payload."""
    try:
        return jwt.decode(
            token,
            settings.invite_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None

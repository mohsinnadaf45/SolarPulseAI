"""
app/core/security.py

Password hashing, JWT token creation and validation.
Uses passlib for hashing and python-jose for JWT.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from jose import JWTError, jwt
except ImportError:
    import jwt  # type: ignore
    from jwt.exceptions import PyJWTError as JWTError  # type: ignore
import bcrypt

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash of the given plain-text password."""
    pwd_bytes = plain_password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


get_password_hash = hash_password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches hashed_password."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: Optional[dict] = None,
) -> str:
    """Internal helper — build and sign a JWT."""
    now = datetime.now(tz=timezone.utc)
    payload: dict = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str) -> str:
    """Create a short-lived access token for the given subject (user id/email)."""
    return _create_token(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str) -> str:
    """Create a long-lived refresh token for the given subject."""
    return _create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT.

    Raises:
        JWTError: if the token is invalid or expired.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def decode_access_token(token: str) -> str:
    """
    Decode an access token and return the subject claim.

    Raises:
        ValueError: if the token type is not 'access' or token is invalid.
    """
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    if payload.get("type") != "access":
        raise ValueError("Token type is not 'access'")

    subject: Optional[str] = payload.get("sub")
    if subject is None:
        raise ValueError("Token missing 'sub' claim")

    return subject


def decode_refresh_token(token: str) -> str:
    """
    Decode a refresh token and return the subject claim.

    Raises:
        ValueError: if the token type is not 'refresh' or token is invalid.
    """
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise ValueError("Invalid or expired refresh token") from exc

    if payload.get("type") != "refresh":
        raise ValueError("Token type is not 'refresh'")

    subject: Optional[str] = payload.get("sub")
    if subject is None:
        raise ValueError("Token missing 'sub' claim")

    return subject

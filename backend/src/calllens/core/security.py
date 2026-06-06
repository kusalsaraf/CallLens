"""Password hashing and JWT token helpers."""

import uuid as _uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from calllens.core.config import get_settings
from calllens.core.exceptions import AuthenticationError

_ALGORITHM = "HS256"

_password_hash = PasswordHash([Argon2Hasher()])


def hash_password(plain: str) -> str:
    """Return the Argon2 hash of a plain-text password.

    Args:
        plain: The raw password string to hash.

    Returns:
        An Argon2id hash string suitable for storage.
    """
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a stored Argon2 hash.

    Args:
        plain: The raw password string from the user.
        hashed: The stored Argon2 hash to compare against.

    Returns:
        ``True`` if the password matches, ``False`` otherwise.
    """
    try:
        return _password_hash.verify(plain, hashed)
    except Exception:
        return False


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def _base_payload(subject: str, token_type: str, expiry_seconds: int) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "sub": subject,
        "type": token_type,
        "jti": str(_uuid.uuid4()),  # unique per-token ID; enables future revocation
        "iat": now,
        "exp": now + timedelta(seconds=expiry_seconds),
    }


def create_access_token(user_id: str) -> tuple[str, int]:
    """Create a short-lived JWT access token.

    Args:
        user_id: The user's UUID as a string, used as the ``sub`` claim.

    Returns:
        A tuple of ``(encoded_token, expires_in_seconds)``.
    """
    expiry = get_settings().jwt_access_expiry_seconds
    token = _encode(_base_payload(user_id, "access", expiry))
    return token, expiry


def create_refresh_token(user_id: str) -> tuple[str, int]:
    """Create a long-lived JWT refresh token.

    Args:
        user_id: The user's UUID as a string, used as the ``sub`` claim.

    Returns:
        A tuple of ``(encoded_token, expires_in_seconds)``.
    """
    expiry = get_settings().jwt_refresh_expiry_seconds
    token = _encode(_base_payload(user_id, "refresh", expiry))
    return token, expiry


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Decode and validate a JWT, enforcing the expected token type.

    Args:
        token: The encoded JWT string.
        expected_type: Either ``"access"`` or ``"refresh"``.

    Returns:
        The decoded payload dict.

    Raises:
        AuthenticationError: If the token is invalid, expired, or the wrong type.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise AuthenticationError("Invalid token type")

    return payload

"""Authentication business logic with single-user lock."""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.exceptions import AuthenticationError, ConflictError
from calllens.core.security import hash_password, verify_password
from calllens.db.models.user import User

logger = logging.getLogger(__name__)

# Pre-computed hash used when the looked-up email doesn't exist, so that
# verify_password always runs and eliminates timing-based email enumeration.
_DUMMY_HASH: str = hash_password("__calllens_dummy__")


async def _user_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(User))
    count: int = result.scalar_one()
    return count


async def create_user(db: AsyncSession, email: str, password: str, name: str) -> User:
    """Create the first (and only) application user.

    Args:
        db: The database session.
        email: The user's email address.
        password: Plain-text password (will be hashed before storage).
        name: Display name.

    Returns:
        The newly created ``User`` ORM instance.

    Raises:
        ConflictError: If a user already exists — signup is permanently locked.
    """
    if await _user_count(db) > 0:
        raise ConflictError("Signup is closed — this installation already has an owner.")

    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password(password),
        name=name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("User created", extra={"user_id": str(user.id)})
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Verify credentials and return the active user.

    Always runs Argon2 verification regardless of whether the email exists,
    to prevent timing-based email enumeration.

    Args:
        db: The database session.
        email: Submitted email address.
        password: Submitted plain-text password.

    Returns:
        The authenticated ``User`` ORM instance.

    Raises:
        AuthenticationError: On any credential failure (generic message only).
    """
    result = await db.execute(select(User).where(User.email == email))
    user: User | None = result.scalar_one_or_none()

    check_hash = user.hashed_password if user is not None else _DUMMY_HASH
    password_ok = verify_password(password, check_hash)

    if user is None or not password_ok or not user.is_active:
        raise AuthenticationError("Invalid email or password")

    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Fetch a user by primary key.

    Args:
        db: The database session.
        user_id: The UUID primary key to look up.

    Returns:
        The ``User`` if found, otherwise ``None``.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

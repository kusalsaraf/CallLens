"""Reusable FastAPI dependencies shared across routers."""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.exceptions import AuthenticationError
from calllens.core.security import decode_token
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.services.auth_service import get_user_by_id

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate a Bearer access token, then load the active user.

    Args:
        credentials: HTTP Bearer credentials extracted from the Authorization header.
        db: Injected database session.

    Returns:
        The active ``User`` associated with the token.

    Raises:
        AuthenticationError: If the header is missing, the token is invalid,
            or the user does not exist / is inactive.
    """
    if credentials is None:
        raise AuthenticationError()

    payload = decode_token(credentials.credentials, "access")

    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (ValueError, KeyError) as exc:
        raise AuthenticationError("Malformed token subject") from exc

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError()

    return user

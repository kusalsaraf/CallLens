"""Authentication endpoints: signup, login, refresh, logout, me."""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.config import get_settings
from calllens.core.deps import get_current_user
from calllens.core.exceptions import AuthenticationError
from calllens.core.security import create_access_token, create_refresh_token, decode_token
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserOut
from calllens.services.auth_service import authenticate_user, create_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE_NAME = "refresh_token"
_COOKIE_PATH = "/api/v1/auth"


def _attach_refresh_cookie(response: Response, token: str, max_age: int) -> None:
    settings = get_settings()
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
        max_age=max_age,
        path=_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path=_COOKIE_PATH)


def _build_token_response(user_id: str, response: Response) -> TokenResponse:
    access_token, expires_in = create_access_token(user_id)
    refresh_token, refresh_max_age = create_refresh_token(user_id)
    _attach_refresh_cookie(response, refresh_token, refresh_max_age)
    return TokenResponse(access_token=access_token, token_type="bearer", expires_in=expires_in)


@router.post("/signup", response_model=TokenResponse)
async def signup(
    body: SignupRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Create the first (and only) user and immediately issue tokens.

    Locked with HTTP 409 once a user already exists.

    Args:
        body: Signup fields — email, password, name.
        response: FastAPI response object used to set the refresh cookie.
        db: Injected database session.

    Returns:
        Access token and expiry; refresh token set as httpOnly cookie.
    """
    user = await create_user(db, email=str(body.email), password=body.password, name=body.name)
    return _build_token_response(str(user.id), response)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Verify credentials and issue tokens.

    Returns a generic 401 on any failure — never indicates whether the email
    or password was wrong specifically.

    Args:
        body: Login fields — email and password.
        response: FastAPI response object used to set the refresh cookie.
        db: Injected database session.

    Returns:
        Access token and expiry; refresh token set as httpOnly cookie.
    """
    user = await authenticate_user(db, email=str(body.email), password=body.password)
    logger.info("User authenticated", extra={"user_id": str(user.id)})
    return _build_token_response(str(user.id), response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> TokenResponse:
    """Validate the refresh cookie and rotate both tokens.

    Args:
        response: FastAPI response object used to set the new refresh cookie.
        refresh_token: The current refresh token read from the httpOnly cookie.

    Returns:
        A new access token; a rotated refresh token is set as a new httpOnly cookie.

    Raises:
        AuthenticationError: If the cookie is absent or the token is invalid.
    """
    if refresh_token is None:
        raise AuthenticationError("Refresh token cookie missing")

    payload = decode_token(refresh_token, "refresh")
    user_id = str(payload["sub"])
    return _build_token_response(user_id, response)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear the refresh token cookie.

    Args:
        response: FastAPI response object used to clear the cookie.

    Returns:
        A confirmation message.
    """
    _clear_refresh_cookie(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    """Return the profile of the currently authenticated user.

    Args:
        current_user: The active user extracted from the Bearer token.

    Returns:
        Public user fields.
    """
    return UserOut.model_validate(current_user)

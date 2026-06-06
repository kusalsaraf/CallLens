"""Pydantic schemas for authentication endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    """Request body for POST /auth/signup."""

    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Public representation of the authenticated user."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """Successful authentication response body."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int

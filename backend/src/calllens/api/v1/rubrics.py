"""Rubric CRUD API endpoints."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.deps import get_current_user
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.schemas.rubric import (
    RubricCreateIn,
    RubricDetailOut,
    RubricListOut,
    RubricOut,
    RubricUpdateIn,
)
from calllens.services import rubric_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rubrics", tags=["rubrics"])


@router.get("", response_model=RubricListOut)
async def list_rubrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> RubricListOut:
    """List all rubrics.

    Args:
        db: Database session.
        _user: Authenticated user (auth guard).

    Returns:
        List of rubrics with their active/default flags.
    """
    rubrics = await rubric_service.list_rubrics(db)
    return RubricListOut(items=[RubricOut.model_validate(r) for r in rubrics])


@router.get("/{rubric_id}", response_model=RubricDetailOut)
async def get_rubric(
    rubric_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> RubricDetailOut:
    """Get a rubric with its dimensions.

    Args:
        rubric_id: UUID of the rubric.
        db: Database session.
        _user: Authenticated user (auth guard).

    Returns:
        Rubric detail with dimensions.

    Raises:
        HTTPException 404: If the rubric is not found.
    """
    rubric = await rubric_service.get_rubric(db, rubric_id)
    if rubric is None:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return RubricDetailOut.model_validate(rubric)


@router.post("", response_model=RubricDetailOut, status_code=201)
async def create_rubric(
    data: RubricCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RubricDetailOut:
    """Create a new rubric (inactive by default).

    Args:
        data: Rubric creation payload with dimensions.
        db: Database session.
        user: Authenticated user.

    Returns:
        The newly created rubric with dimensions.
    """
    rubric = await rubric_service.create_rubric(db, data, actor=f"user:{user.id}")
    return RubricDetailOut.model_validate(rubric)


@router.put("/{rubric_id}", response_model=RubricDetailOut)
async def update_rubric(
    rubric_id: uuid.UUID,
    data: RubricUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RubricDetailOut:
    """Update a rubric's name/description and optionally replace dimensions.

    Args:
        rubric_id: UUID of the rubric to update.
        data: Update payload.
        db: Database session.
        user: Authenticated user.

    Returns:
        Updated rubric with dimensions.

    Raises:
        HTTPException 404: If the rubric is not found.
    """
    rubric = await rubric_service.update_rubric(db, rubric_id, data, actor=f"user:{user.id}")
    if rubric is None:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return RubricDetailOut.model_validate(rubric)


@router.post("/{rubric_id}/activate", response_model=RubricDetailOut)
async def activate_rubric(
    rubric_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RubricDetailOut:
    """Set this rubric active, deactivating all others.

    Args:
        rubric_id: UUID of the rubric to activate.
        db: Database session.
        user: Authenticated user.

    Returns:
        The activated rubric.

    Raises:
        HTTPException 404: If the rubric is not found.
    """
    rubric = await rubric_service.activate_rubric(db, rubric_id, actor=f"user:{user.id}")
    if rubric is None:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return RubricDetailOut.model_validate(rubric)


@router.post("/{rubric_id}/clone", response_model=RubricDetailOut, status_code=201)
async def clone_rubric(
    rubric_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RubricDetailOut:
    """Clone a rubric + dimensions as a new inactive draft.

    Args:
        rubric_id: UUID of the source rubric.
        db: Database session.
        user: Authenticated user.

    Returns:
        The cloned rubric.

    Raises:
        HTTPException 404: If the source rubric is not found.
    """
    rubric = await rubric_service.clone_rubric(db, rubric_id, actor=f"user:{user.id}")
    if rubric is None:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return RubricDetailOut.model_validate(rubric)


@router.delete("/{rubric_id}", status_code=204)
async def delete_rubric(
    rubric_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a rubric (blocked if active or referenced by calls).

    Args:
        rubric_id: UUID of the rubric to delete.
        db: Database session.
        user: Authenticated user.

    Raises:
        HTTPException 404: If the rubric is not found.
        HTTPException 409: If the rubric cannot be deleted (active or referenced).
    """
    ok, reason = await rubric_service.delete_rubric(db, rubric_id, actor=f"user:{user.id}")
    if not ok:
        if reason == "Rubric not found":
            raise HTTPException(status_code=404, detail=reason)
        raise HTTPException(status_code=409, detail=reason)

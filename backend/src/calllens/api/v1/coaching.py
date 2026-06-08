"""Coaching notes API — create, list, and delete manual coaching notes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.deps import get_current_user
from calllens.core.exceptions import NotFoundError, ValidationError
from calllens.db.models.agent import Agent
from calllens.db.models.audit import AuditLog
from calllens.db.models.coaching import CoachingNote
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.schemas.analysis import CoachingListOut, CoachingNoteCreate, CoachingNoteOut

router = APIRouter(prefix="/coaching-notes", tags=["coaching"])


@router.post("/", response_model=CoachingNoteOut, status_code=201)
async def create_coaching_note(
    body: CoachingNoteCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CoachingNoteOut:
    """Create a manual coaching note for an agent.

    Args:
        body: Note payload with agent_id, optional call_id, and note text.
        db: Database session.
        current_user: Authenticated user (becomes audit actor).

    Returns:
        The created CoachingNoteOut.

    Raises:
        NotFoundError: If the agent does not exist.
    """
    agent = (await db.execute(select(Agent).where(Agent.id == body.agent_id))).scalar_one_or_none()
    if agent is None:
        raise NotFoundError(f"Agent {body.agent_id} not found")

    note = CoachingNote(
        agent_id=body.agent_id,
        call_id=body.call_id,
        source="manual",
        note=body.note,
    )
    db.add(note)
    await db.flush()

    db.add(
        AuditLog(
            actor=f"user:{current_user.id}",
            action="coaching_note_create",
            entity="coaching_note",
            entity_id=note.id,
            payload={"agent_id": str(body.agent_id)},
        )
    )
    await db.commit()
    await db.refresh(note)
    return CoachingNoteOut.model_validate(note)


@router.get("/", response_model=CoachingListOut)
async def list_coaching_notes(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    agent_id: uuid.UUID | None = None,
    call_id: uuid.UUID | None = None,
) -> CoachingListOut:
    """Return coaching notes with optional agent_id and call_id filters.

    Args:
        db: Database session.
        current_user: Authenticated user.
        agent_id: Optional filter by agent UUID.
        call_id: Optional filter by call UUID.

    Returns:
        CoachingListOut with matching notes ordered newest-first.
    """
    stmt = select(CoachingNote).order_by(CoachingNote.created_at.desc())
    if agent_id is not None:
        stmt = stmt.where(CoachingNote.agent_id == agent_id)
    if call_id is not None:
        stmt = stmt.where(CoachingNote.call_id == call_id)

    notes = (await db.execute(stmt)).scalars().all()
    return CoachingListOut(
        items=[CoachingNoteOut.model_validate(n) for n in notes],
        agent_id=agent_id,
    )


@router.delete("/{note_id}", status_code=204)
async def delete_coaching_note(
    note_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a manual coaching note.

    Args:
        note_id: UUID of the coaching note.
        db: Database session.
        current_user: Authenticated user.

    Raises:
        NotFoundError: If the note does not exist.
        ValidationError: If the note is auto-generated and may not be deleted.
    """
    note = (
        await db.execute(select(CoachingNote).where(CoachingNote.id == note_id))
    ).scalar_one_or_none()
    if note is None:
        raise NotFoundError(f"Coaching note {note_id} not found")
    if note.source == "auto":
        raise ValidationError("Cannot delete auto-generated coaching notes")

    db.add(
        AuditLog(
            actor=f"user:{current_user.id}",
            action="coaching_note_delete",
            entity="coaching_note",
            entity_id=note_id,
            payload={"agent_id": str(note.agent_id)},
        )
    )
    await db.delete(note)
    await db.commit()

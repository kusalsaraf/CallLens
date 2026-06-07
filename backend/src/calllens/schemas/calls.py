"""Pydantic schemas for the calls API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CallOut(BaseModel):
    """Public representation of a Call row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    original_filename: str
    duration_seconds: float | None
    agent_id: uuid.UUID | None
    status_detail: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_call(cls, call: object) -> "CallOut":
        """Build from a Call ORM instance, serializing the status enum.

        Args:
            call: A Call ORM model instance.

        Returns:
            Serialised CallOut.
        """
        from calllens.db.models.call import Call as CallModel

        assert isinstance(call, CallModel)
        return cls(
            id=call.id,
            status=call.status.value,
            original_filename=call.original_filename,
            duration_seconds=call.duration_seconds,
            agent_id=call.agent_id,
            status_detail=call.status_detail,
            created_at=call.created_at,
            updated_at=call.updated_at,
        )


class SegmentOut(BaseModel):
    """A single transcript segment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    start_ms: int
    end_ms: int
    text: str
    speaker: str


class TranscriptOut(BaseModel):
    """A full transcript with ordered segments."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_id: uuid.UUID
    language: str | None
    segments: list[SegmentOut]
    created_at: datetime


class CallListOut(BaseModel):
    """Paginated list of calls."""

    items: list[CallOut]
    total: int
    page: int
    page_size: int

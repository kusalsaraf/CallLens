"""Pydantic schemas for the calls API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


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


class EvidenceOut(BaseModel):
    """A single evidence reference returned in a score response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    segment_id: uuid.UUID | None
    quote: str


class DimensionInfo(BaseModel):
    """Brief rubric dimension info embedded in a score response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    weight: float


class CallScoreOut(BaseModel):
    """A scored dimension result with evidence."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dimension: DimensionInfo
    score: int
    confidence: float
    rationale: str
    is_supported: bool
    scored_at: datetime
    evidence: list[EvidenceOut]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def band(self) -> str:
        """Score band classification: excellent ≥90, good ≥70, fair ≥50, poor <50."""
        if self.score >= 90:
            return "excellent"
        if self.score >= 70:
            return "good"
        if self.score >= 50:
            return "fair"
        return "poor"


class ScoresListOut(BaseModel):
    """List of all scored dimensions for a call."""

    call_id: uuid.UUID
    scores: list[CallScoreOut]

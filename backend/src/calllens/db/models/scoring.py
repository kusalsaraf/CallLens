"""CallScore and ScoreEvidence ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calllens.db.base import Base

if TYPE_CHECKING:
    from calllens.db.models.call import Call
    from calllens.db.models.rubric import RubricDimension
    from calllens.db.models.segment import TranscriptSegment


class CallScore(Base):
    """A scored dimension result for a single call."""

    __tablename__ = "call_scores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rubric_dimensions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    is_supported: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    call: Mapped[Call] = relationship("Call", back_populates="scores")
    dimension: Mapped[RubricDimension] = relationship("RubricDimension", back_populates="scores")
    evidence: Mapped[list[ScoreEvidence]] = relationship(
        "ScoreEvidence", back_populates="call_score", cascade="all, delete-orphan"
    )


class ScoreEvidence(Base):
    """A verbatim excerpt from a transcript segment supporting a CallScore."""

    __tablename__ = "score_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_score_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("call_scores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quote: Mapped[str] = mapped_column(Text, nullable=False)

    call_score: Mapped[CallScore] = relationship("CallScore", back_populates="evidence")
    segment: Mapped[TranscriptSegment | None] = relationship("TranscriptSegment")

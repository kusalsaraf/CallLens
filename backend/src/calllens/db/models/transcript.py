"""Transcript ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calllens.db.base import Base

if TYPE_CHECKING:
    from calllens.db.models.call import Call
    from calllens.db.models.segment import TranscriptSegment


class Transcript(Base):
    """Full transcript associated with a call."""

    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), unique=True
    )
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    redaction_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entities_redacted: Mapped[dict[str, int] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call: Mapped[Call] = relationship("Call", back_populates="transcript")
    segments: Mapped[list[TranscriptSegment]] = relationship(
        "TranscriptSegment",
        back_populates="transcript",
        order_by="TranscriptSegment.sequence",
    )

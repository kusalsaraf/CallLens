"""TranscriptSegment ORM model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calllens.core.config import get_settings
from calllens.db.base import Base

if TYPE_CHECKING:
    from calllens.db.models.transcript import Transcript


class TranscriptSegment(Base):
    """A single timed text segment in a transcript, with speaker attribution."""

    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    redacted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaker: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[Any | None] = mapped_column(
        Vector(get_settings().embedding_dim), nullable=True
    )

    transcript: Mapped[Transcript] = relationship("Transcript", back_populates="segments")

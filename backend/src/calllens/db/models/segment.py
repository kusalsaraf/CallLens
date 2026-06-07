"""TranscriptSegment ORM model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    speaker: Mapped[str] = mapped_column(String(64))
    # Nullable — populated in a later phase via pgvector
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)

    transcript: Mapped[Transcript] = relationship("Transcript", back_populates="segments")

"""Call ORM model."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calllens.db.base import Base

if TYPE_CHECKING:
    from calllens.db.models.agent import Agent
    from calllens.db.models.scoring import CallScore
    from calllens.db.models.transcript import Transcript


class CallStatus(enum.Enum):
    """Lifecycle states of a call recording."""

    uploaded = "uploaded"
    transcribing = "transcribing"
    diarizing = "diarizing"
    transcribed = "transcribed"
    scoring = "scoring"
    scored = "scored"
    failed = "failed"


_TERMINAL_STATUSES: frozenset[CallStatus] = frozenset(
    {CallStatus.transcribed, CallStatus.scored, CallStatus.failed}
)


def is_terminal(status: CallStatus) -> bool:
    """Return True if the status requires no further processing.

    Args:
        status: A CallStatus value.

    Returns:
        True if the status is transcribed or failed.
    """
    return status in _TERMINAL_STATUSES


class Call(Base):
    """A call recording with its processing lifecycle."""

    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[CallStatus] = mapped_column(
        Enum(CallStatus, name="callstatus"), default=CallStatus.uploaded
    )
    storage_key: Mapped[str] = mapped_column(String(512))
    original_filename: Mapped[str] = mapped_column(String(512))
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    agent: Mapped[Agent | None] = relationship("Agent", back_populates="calls")
    transcript: Mapped[Transcript | None] = relationship(
        "Transcript", back_populates="call", uselist=False
    )
    scores: Mapped[list[CallScore]] = relationship(
        "CallScore", back_populates="call", cascade="all, delete-orphan"
    )

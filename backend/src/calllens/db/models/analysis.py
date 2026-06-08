"""CallAnalysis ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from calllens.db.base import Base


class CallAnalysis(Base):
    """Aggregated analysis produced by the scoring supervisor for one call."""

    __tablename__ = "call_analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_moments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    action_items: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    sentiment_overall: Mapped[str | None] = mapped_column(Text, nullable=True)
    talk_listen_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    interruptions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_monologue_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compliance_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    escalate_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

"""CallAgentRun ORM model — per-node trace for one scoring pass."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from calllens.db.base import Base


class CallAgentRun(Base):
    """Records the execution of one LangGraph node during call scoring."""

    __tablename__ = "call_agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # dimension key, "supervisor", or "preprocess"
    role: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "specialist", "supervisor", "preprocess"
    provider: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # "stub", "langchain", "deterministic"
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_kept: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_dropped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

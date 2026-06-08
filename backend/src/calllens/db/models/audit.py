"""AuditLog ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from calllens.db.base import Base


class AuditLog(Base):
    """Immutable record of a system or user action on a domain entity."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)  # "system" or "user:<uuid>"
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # "score", "reprocess", "coaching_note_create", "coaching_note_delete"
    entity: Mapped[str] = mapped_column(String(64), nullable=False)  # "call", "coaching_note"
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

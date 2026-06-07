"""Rubric and RubricDimension ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calllens.db.base import Base

if TYPE_CHECKING:
    from calllens.db.models.scoring import CallScore


class Rubric(Base):
    """A scoring rubric composed of weighted evaluation dimensions."""

    __tablename__ = "rubrics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dimensions: Mapped[list[RubricDimension]] = relationship(
        "RubricDimension", back_populates="rubric", cascade="all, delete-orphan"
    )


class RubricDimension(Base):
    """A single weighted evaluation axis within a rubric."""

    __tablename__ = "rubric_dimensions"
    __table_args__ = (UniqueConstraint("rubric_id", "key", name="uq_rubric_dimensions_rubric_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rubric_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rubric: Mapped[Rubric] = relationship("Rubric", back_populates="dimensions")
    scores: Mapped[list[CallScore]] = relationship("CallScore", back_populates="dimension")

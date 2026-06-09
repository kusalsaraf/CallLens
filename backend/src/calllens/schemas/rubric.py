"""Pydantic schemas for rubric CRUD API — dimension kind validation included."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DimensionKind(enum.StrEnum):
    """Allowed dimension kinds for rubric dimensions."""

    sentiment_empathy = "sentiment_empathy"
    script_adherence = "script_adherence"
    compliance = "compliance"
    objection_handling = "objection_handling"
    talk_listen = "talk_listen"
    outcome = "outcome"
    custom = "custom"


# Kinds that require per-kind config fields
_CONFIG_REQUIRED: dict[DimensionKind, tuple[str, str]] = {
    DimensionKind.compliance: (
        "required_phrases",
        "compliance dimensions require a non-empty 'required_phrases' list in config",
    ),
    DimensionKind.script_adherence: (
        "checklist",
        "script_adherence dimensions require a non-empty 'checklist' list in config",
    ),
    DimensionKind.custom: (
        "guidance",
        "custom dimensions require a 'guidance' string in config describing the scoring criteria",
    ),
}


class DimensionIn(BaseModel):
    """Input schema for a single rubric dimension (create/update)."""

    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    weight: float = Field(gt=0)
    kind: DimensionKind
    config: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_config_for_kind(self) -> DimensionIn:
        """Enforce per-kind config requirements."""
        rule = _CONFIG_REQUIRED.get(self.kind)
        if rule is None:
            return self

        field_name, err_msg = rule
        cfg = self.config or {}
        value = cfg.get(field_name)

        if self.kind == DimensionKind.custom:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(err_msg)
        else:
            if not isinstance(value, list) or len(value) == 0:
                raise ValueError(err_msg)

        return self


class RubricCreateIn(BaseModel):
    """Input schema for creating a new rubric with its dimensions."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    dimensions: list[DimensionIn] = Field(min_length=1)


class RubricUpdateIn(BaseModel):
    """Input schema for updating a rubric's name/description and dimensions."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    dimensions: list[DimensionIn] | None = None


class DimensionOut(BaseModel):
    """Output schema for a rubric dimension."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    weight: float
    kind: str
    config: dict[str, Any] | None
    created_at: datetime


class RubricOut(BaseModel):
    """Output schema for a rubric (without dimensions)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    is_default: bool
    created_at: datetime


class RubricDetailOut(RubricOut):
    """Output schema for a rubric with its dimensions."""

    dimensions: list[DimensionOut]


class RubricListOut(BaseModel):
    """List of rubrics."""

    items: list[RubricOut]

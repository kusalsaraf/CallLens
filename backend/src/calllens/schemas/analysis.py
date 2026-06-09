"""Pydantic schemas for analysis, agent, and coaching responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KeyMomentOut(BaseModel):
    """A notable moment in the call, linked to a transcript segment."""

    segment_id: uuid.UUID
    label: str


class CallTopicBrief(BaseModel):
    """A topic attached to a call — minimal shape for the analysis response."""

    topic_id: uuid.UUID
    name: str
    slug: str
    relevance: float


class CallAnalysisOut(BaseModel):
    """Aggregated call analysis returned by GET /calls/{id}/analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_id: uuid.UUID
    overall_score: int
    summary: str
    key_moments: list[KeyMomentOut]
    action_items: list[str]
    sentiment_overall: str | None
    talk_listen_ratio: float
    interruptions: int
    longest_monologue_ms: int
    total_turns: int
    compliance_passed: bool
    escalate_for_review: bool
    escalation_reason: str | None
    topics: list[CallTopicBrief] = []
    created_at: datetime


class AgentRunOut(BaseModel):
    """One LangGraph node execution trace entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    node: str
    role: str
    provider: str
    score: int | None
    confidence: float | None
    evidence_kept: int
    evidence_dropped: int
    duration_ms: int
    detail: dict[str, Any] | None
    created_at: datetime


class TraceOut(BaseModel):
    """Full agent run trace for one call."""

    call_id: uuid.UUID
    runs: list[AgentRunOut]


class AgentStatsOut(BaseModel):
    """An agent with aggregated scoring statistics."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    team_id: uuid.UUID
    created_at: datetime
    calls_scored: int
    avg_overall_score: int


class AgentListOut(BaseModel):
    """Paginated list of agents with stats."""

    items: list[AgentStatsOut]


class CoachingNoteOut(BaseModel):
    """A coaching note returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    call_id: uuid.UUID | None
    source: str
    note: str
    created_at: datetime


class CoachingNoteCreate(BaseModel):
    """Request body for POST /coaching-notes."""

    agent_id: uuid.UUID
    call_id: uuid.UUID | None = None
    note: str = Field(min_length=1)


class CoachingListOut(BaseModel):
    """List of coaching notes, optionally filtered by agent."""

    items: list[CoachingNoteOut]
    agent_id: uuid.UUID | None = None

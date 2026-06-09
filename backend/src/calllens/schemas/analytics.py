"""Pydantic response schemas for the manager analytics API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

from calllens.core.scoring import AT_RISK_THRESHOLD, QUALITY_THRESHOLD
from calllens.core.scoring import band as band_from_score

# Re-export so callers can import a single name without knowing the internal module.
__all__ = [
    "QUALITY_THRESHOLD",
    "AT_RISK_THRESHOLD",
    "band_from_score",
]


# ── Shared filter dependency ──────────────────────────────────────────────────
class AnalyticsFilters:
    """Common optional query-param filters honoured by all analytics endpoints."""

    def __init__(
        self,
        date_from: Annotated[datetime | None, Query()] = None,
        date_to: Annotated[datetime | None, Query()] = None,
        team_id: Annotated[uuid.UUID | None, Query()] = None,
        agent_id: Annotated[uuid.UUID | None, Query()] = None,
        topic_id: Annotated[uuid.UUID | None, Query()] = None,
    ) -> None:
        """Initialise the filter set from query params.

        Args:
            date_from: Include calls uploaded on or after this timestamp.
            date_to: Include calls uploaded on or before this timestamp.
            team_id: Restrict to agents belonging to this team.
            agent_id: Restrict to a single agent.
            topic_id: Restrict to calls tagged with this topic.
        """
        self.date_from = date_from
        self.date_to = date_to
        self.team_id = team_id
        self.agent_id = agent_id
        self.topic_id = topic_id


# ── Overview ──────────────────────────────────────────────────────────────────
class OverviewOut(BaseModel):
    """Summary stats for the manager dashboard header."""

    calls_total: int
    calls_scored: int
    avg_overall_score: float | None
    compliance_pass_rate: float | None
    flagged_count: int


# ── Quality trends ────────────────────────────────────────────────────────────
class QualityBucketOut(BaseModel):
    """One time-bucket in the quality trend series."""

    date: str
    avg_overall_score: float
    calls_scored: int


class QualityTrendsOut(BaseModel):
    """Ordered quality-trend series bucketed by day or week."""

    bucket: str
    items: list[QualityBucketOut]


# ── Score distribution ────────────────────────────────────────────────────────
class ScoreBucketOut(BaseModel):
    """Count of scored calls within a 10-point score range."""

    bucket: int
    label: str
    count: int


class BandDistributionOut(BaseModel):
    """Count of scored calls per quality band."""

    quality: int
    at_risk: int
    fail: int


class ScoreDistributionOut(BaseModel):
    """Histogram of overall scores by 10-point bucket and band."""

    buckets: list[ScoreBucketOut]
    bands: BandDistributionOut


# ── Compliance ────────────────────────────────────────────────────────────────
class ComplianceTrendPointOut(BaseModel):
    """Compliance pass rate for one weekly bucket."""

    date: str
    pass_rate: float
    calls: int


class ComplianceOut(BaseModel):
    """Overall compliance pass rate plus weekly trend."""

    pass_rate: float | None
    trend: list[ComplianceTrendPointOut]


# ── Flagged calls ─────────────────────────────────────────────────────────────
class FlaggedCallOut(BaseModel):
    """A call flagged for review — at-risk score or explicit escalation."""

    call_id: uuid.UUID
    agent_name: str | None
    overall_score: int
    band: str
    escalate_for_review: bool
    escalation_reason: str | None
    uploaded_at: datetime


class FlaggedListOut(BaseModel):
    """Paginated list of flagged calls."""

    items: list[FlaggedCallOut]
    total: int
    limit: int
    offset: int


# ── Leaderboard ───────────────────────────────────────────────────────────────
class LeaderboardEntryOut(BaseModel):
    """One agent row in the leaderboard."""

    agent_id: uuid.UUID
    name: str
    team: str
    calls_scored: int
    avg_overall_score: float
    compliance_pass_rate: float
    is_at_risk: bool


class LeaderboardOut(BaseModel):
    """Agents ranked by avg overall score, best first."""

    items: list[LeaderboardEntryOut]


# ── Agent performance ─────────────────────────────────────────────────────────
class TrendPointOut(BaseModel):
    """One weekly data point in an agent's score trend."""

    date: str
    avg_overall_score: float


class DimensionBreakdownOut(BaseModel):
    """Average score per rubric dimension for an agent."""

    dimension_key: str
    dimension_name: str
    avg_score: float


class VsTeamOut(BaseModel):
    """Agent score versus their team average."""

    agent_avg: float
    team_avg: float


class AgentPerformanceOut(BaseModel):
    """Detailed scoring performance report for one agent."""

    calls_scored: int
    avg_overall_score: float
    trend: list[TrendPointOut]
    dimension_breakdown: list[DimensionBreakdownOut]
    vs_team: VsTeamOut


# ── Team list ─────────────────────────────────────────────────────────────────
class TeamOut(BaseModel):
    """Brief team representation for the filter selector."""

    id: uuid.UUID
    name: str


class TeamListOut(BaseModel):
    """All teams in the workspace."""

    items: list[TeamOut]


# ── Team analytics ────────────────────────────────────────────────────────────
class TopicAnalyticsEntryOut(BaseModel):
    """Per-topic analytics row."""

    topic_id: uuid.UUID
    name: str
    slug: str
    call_count: int
    avg_overall_score: float | None
    band: str | None
    flagged_rate: float | None


class TopicAnalyticsOut(BaseModel):
    """Topic-level analytics ordered by call_count desc."""

    items: list[TopicAnalyticsEntryOut]


# ── Topic CRUD ────────────────────────────────────────────────────────────────
class TopicOut(BaseModel):
    """A topic in the taxonomy."""

    id: uuid.UUID
    name: str
    slug: str
    keywords: list[str]


class TopicListOut(BaseModel):
    """List of all topics."""

    items: list[TopicOut]


class TopicDetailOut(BaseModel):
    """A topic with its stats."""

    id: uuid.UUID
    name: str
    slug: str
    keywords: list[str]
    call_count: int
    avg_overall_score: float | None
    band: str | None


class CallTopicOut(BaseModel):
    """A topic attached to a call."""

    topic_id: uuid.UUID
    name: str
    slug: str
    relevance: float


class TeamScoreBandOut(BaseModel):
    """Count of scored calls per quality band within a team."""

    quality: int
    at_risk: int
    fail: int


class TeamAgentComparisonOut(BaseModel):
    """One agent row in the team's agent-comparison table."""

    agent_id: uuid.UUID
    name: str
    calls_scored: int
    avg_overall_score: float


class TeamAnalyticsOut(BaseModel):
    """Aggregated analytics for one team."""

    calls_scored: int
    avg_overall_score: float | None
    compliance_pass_rate: float | None
    score_distribution: TeamScoreBandOut
    agent_comparison: list[TeamAgentComparisonOut]

"""Teams API — team-level analytics endpoint."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.deps import get_current_user
from calllens.core.exceptions import NotFoundError
from calllens.core.scoring import AT_RISK_THRESHOLD, QUALITY_THRESHOLD
from calllens.db.models.agent import Agent
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.team import Team
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.schemas.analytics import (
    TeamAgentComparisonOut,
    TeamAnalyticsOut,
    TeamListOut,
    TeamOut,
    TeamScoreBandOut,
)

router = APIRouter(prefix="/teams", tags=["teams"])

_SCORED = Call.status == CallStatus.scored


@router.get("/", response_model=TeamListOut)
async def list_teams(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TeamListOut:
    """Return all teams ordered by name.

    Args:
        db: Database session.
        current_user: Authenticated user.

    Returns:
        TeamListOut with id and name of every team.
    """
    rows = (await db.execute(select(Team).order_by(Team.name))).scalars().all()
    return TeamListOut(items=[TeamOut(id=t.id, name=t.name) for t in rows])


@router.get("/{team_id}/analytics", response_model=TeamAnalyticsOut)
async def get_team_analytics(
    team_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TeamAnalyticsOut:
    """Return aggregated scoring analytics for one team.

    Args:
        team_id: UUID of the team.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        TeamAnalyticsOut with distribution and per-agent comparison.

    Raises:
        NotFoundError: If the team does not exist.
    """
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if team is None:
        raise NotFoundError(f"Team {team_id} not found")

    stats_stmt = (
        select(
            func.count(CallAnalysis.id).label("calls_scored"),
            func.avg(CallAnalysis.overall_score).label("avg_score"),
            func.count(CallAnalysis.id)
            .filter(CallAnalysis.compliance_passed == True)  # noqa: E712
            .label("compliance_passed_count"),
            func.count(CallAnalysis.id)
            .filter(CallAnalysis.overall_score >= QUALITY_THRESHOLD)
            .label("quality"),
            func.count(CallAnalysis.id)
            .filter(
                (CallAnalysis.overall_score >= AT_RISK_THRESHOLD)
                & (CallAnalysis.overall_score < QUALITY_THRESHOLD)
            )
            .label("at_risk"),
            func.count(CallAnalysis.id)
            .filter(CallAnalysis.overall_score < AT_RISK_THRESHOLD)
            .label("fail"),
        )
        .select_from(Call)
        .join(CallAnalysis, CallAnalysis.call_id == Call.id)
        .join(Agent, Agent.id == Call.agent_id)
        .where(_SCORED)
        .where(Agent.team_id == team_id)
    )
    stats = (await db.execute(stats_stmt)).one()
    calls_scored: int = stats.calls_scored or 0
    avg_score: float | None = (
        round(float(stats.avg_score), 1) if stats.avg_score is not None else None
    )
    pass_rate: float | None = (
        round(stats.compliance_passed_count / calls_scored, 4) if calls_scored > 0 else None
    )

    agent_avg_expr = func.avg(CallAnalysis.overall_score)
    agent_stmt = (
        select(
            Agent.id,
            Agent.name,
            func.count(CallAnalysis.id).label("calls_scored"),
            agent_avg_expr.label("avg_score"),
        )
        .select_from(Agent)
        .join(Call, Call.agent_id == Agent.id)
        .join(CallAnalysis, CallAnalysis.call_id == Call.id)
        .where(_SCORED)
        .where(Agent.team_id == team_id)
        .group_by(Agent.id, Agent.name)
        .order_by(agent_avg_expr.desc())
    )
    agent_rows = (await db.execute(agent_stmt)).all()

    return TeamAnalyticsOut(
        calls_scored=calls_scored,
        avg_overall_score=avg_score,
        compliance_pass_rate=pass_rate,
        score_distribution=TeamScoreBandOut(
            quality=stats.quality,
            at_risk=stats.at_risk,
            fail=stats.fail,
        ),
        agent_comparison=[
            TeamAgentComparisonOut(
                agent_id=row.id,
                name=row.name,
                calls_scored=row.calls_scored,
                avg_overall_score=round(float(row.avg_score), 1),
            )
            for row in agent_rows
        ],
    )

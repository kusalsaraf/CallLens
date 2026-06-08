"""Agents API — list agents with scoring stats and their coaching notes."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.deps import get_current_user
from calllens.core.exceptions import NotFoundError
from calllens.db.models.agent import Agent
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.coaching import CoachingNote
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.schemas.analysis import AgentListOut, AgentStatsOut, CoachingListOut, CoachingNoteOut

router = APIRouter(prefix="/agents", tags=["agents"])


def _build_agent_stats_stmt(agent_id: uuid.UUID | None = None) -> Any:  # noqa: ANN401
    """Build the SELECT that joins Agent → Call → CallAnalysis for stats.

    Args:
        agent_id: If provided, filters to a single agent.

    Returns:
        A SQLAlchemy select statement.
    """
    stmt = (
        select(
            Agent,
            func.count(Call.id).filter(Call.status == CallStatus.scored).label("calls_scored"),
            func.coalesce(func.avg(CallAnalysis.overall_score), 0).label("avg_overall_score"),
        )
        .outerjoin(Call, Call.agent_id == Agent.id)
        .outerjoin(CallAnalysis, CallAnalysis.call_id == Call.id)
        .group_by(Agent.id)
        .order_by(Agent.name)
    )
    if agent_id is not None:
        stmt = stmt.where(Agent.id == agent_id)
    return stmt


@router.get("/", response_model=AgentListOut)
async def list_agents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentListOut:
    """Return all agents with aggregated scoring statistics.

    Args:
        db: Database session.
        current_user: Authenticated user.

    Returns:
        AgentListOut with calls_scored and avg_overall_score per agent.
    """
    rows = (await db.execute(_build_agent_stats_stmt())).all()
    return AgentListOut(
        items=[
            AgentStatsOut(
                id=row.Agent.id,
                name=row.Agent.name,
                team_id=row.Agent.team_id,
                created_at=row.Agent.created_at,
                calls_scored=row.calls_scored or 0,
                avg_overall_score=round(float(row.avg_overall_score or 0)),
            )
            for row in rows
        ]
    )


@router.get("/{agent_id}", response_model=AgentStatsOut)
async def get_agent(
    agent_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentStatsOut:
    """Return a single agent with aggregated scoring statistics.

    Args:
        agent_id: UUID of the agent.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        AgentStatsOut for the requested agent.

    Raises:
        NotFoundError: If the agent does not exist.
    """
    row = (await db.execute(_build_agent_stats_stmt(agent_id=agent_id))).one_or_none()
    if row is None:
        raise NotFoundError(f"Agent {agent_id} not found")
    return AgentStatsOut(
        id=row.Agent.id,
        name=row.Agent.name,
        team_id=row.Agent.team_id,
        created_at=row.Agent.created_at,
        calls_scored=row.calls_scored or 0,
        avg_overall_score=round(float(row.avg_overall_score or 0)),
    )


@router.get("/{agent_id}/coaching", response_model=CoachingListOut)
async def get_agent_coaching(
    agent_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CoachingListOut:
    """Return all coaching notes for an agent, newest first.

    Args:
        agent_id: UUID of the agent.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        CoachingListOut filtered to the given agent.

    Raises:
        NotFoundError: If the agent does not exist.
    """
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if agent is None:
        raise NotFoundError(f"Agent {agent_id} not found")

    notes = (
        (
            await db.execute(
                select(CoachingNote)
                .where(CoachingNote.agent_id == agent_id)
                .order_by(CoachingNote.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    return CoachingListOut(
        items=[CoachingNoteOut.model_validate(n) for n in notes],
        agent_id=agent_id,
    )

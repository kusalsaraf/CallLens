"""Idempotent seeding of required default rows."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.db.models.agent import Agent
from calllens.db.models.team import Team

logger = logging.getLogger(__name__)

_DEFAULT_TEAM_NAME = "Default Team"
_DEFAULT_AGENT_NAME = "Default Agent"


async def seed_defaults(db: AsyncSession) -> None:
    """Create the default Team and Agent if they do not exist.

    Args:
        db: An open async database session.
    """
    team_result = await db.execute(select(Team).where(Team.name == _DEFAULT_TEAM_NAME))
    team = team_result.scalar_one_or_none()

    if team is None:
        team = Team(name=_DEFAULT_TEAM_NAME)
        db.add(team)
        await db.flush()
        logger.info("Created default team", extra={"team_id": str(team.id)})

    agent_result = await db.execute(
        select(Agent).where(Agent.name == _DEFAULT_AGENT_NAME, Agent.team_id == team.id)
    )
    agent = agent_result.scalar_one_or_none()

    if agent is None:
        agent = Agent(name=_DEFAULT_AGENT_NAME, team_id=team.id)
        db.add(agent)
        logger.info("Created default agent", extra={"agent_id": str(agent.id)})

    await db.commit()


async def get_default_agent(db: AsyncSession) -> Agent:
    """Return the default agent, raising ValueError if seeding was skipped.

    Args:
        db: An open async database session.

    Returns:
        The default Agent row.

    Raises:
        ValueError: If no agent exists (should not happen after seeding).
    """
    result = await db.execute(select(Agent).where(Agent.name == _DEFAULT_AGENT_NAME).limit(1))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise ValueError("No default agent found — run seed_defaults first")
    return agent

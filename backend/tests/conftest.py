"""Shared pytest fixtures for the test suite."""

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import calllens.db.models  # noqa: F401 — registers ORM models on Base.metadata
from calllens.db.base import Base
from calllens.db.models.agent import Agent
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.team import Team
from calllens.db.session import get_db
from calllens.main import app
from calllens.services.seed import seed_defaults

_JUNE_1 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_JUNE_8 = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)


@dataclass
class AnalyticsDataset:
    """IDs from the deterministic analytics fixture."""

    team_alpha_id: uuid.UUID
    team_beta_id: uuid.UUID
    agent_a1_id: uuid.UUID
    agent_a2_id: uuid.UUID
    agent_b1_id: uuid.UUID


_TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://calllens:calllens@localhost:5432/calllens",
)

_SIGNUP_PAYLOAD = {
    "email": "owner@example.com",
    "password": "superSecret1",
    "name": "Test Owner",
}


@pytest_asyncio.fixture
async def db_engine():
    """Create all tables before the test and drop them afterwards."""
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine) -> AsyncSession:
    """Open session on the test engine for direct DB setup in API tests."""
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    """HTTP test client with the DB session overridden to the test engine."""
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    # Seed default team/agent into the test DB so uploads can reference an agent
    async with factory() as session:
        await seed_defaults(session)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


async def signup_and_get_token(client: AsyncClient) -> str:
    """Sign up the owner and return the access token.

    Args:
        client: The test HTTP client.

    Returns:
        Bearer access token string.
    """
    resp = await client.post("/api/v1/auth/signup", json=_SIGNUP_PAYLOAD)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient) -> str:
    """Signed-up user access token."""
    return await signup_and_get_token(client)


@pytest_asyncio.fixture
def wav_fixture() -> bytes:
    """Return the bytes of the silence.wav test fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "silence.wav"
    return fixture_path.read_bytes()


@pytest_asyncio.fixture
async def analytics_dataset(db: AsyncSession) -> AnalyticsDataset:
    """Insert two teams, three agents, six scored calls, two unscored calls.

    Score layout:
      A1 @ june_1  score=80  compliance=True  escalate=False  NOT flagged
      A1 @ june_8  score=90  compliance=True  escalate=False  NOT flagged
      A2 @ june_1  score=55  compliance=True  escalate=False  FLAGGED (55<60)
      A2 @ june_8  score=40  compliance=False escalate=True   FLAGGED
      B1 @ june_1  score=75  compliance=True  escalate=False  NOT flagged
      B1 @ june_8  score=30  compliance=False escalate=True   FLAGGED
    Unscored: u1 (A1, uploaded), u2 (A2, transcribed)
    """
    team_alpha = Team(name="Alpha Team")
    team_beta = Team(name="Beta Team")
    db.add_all([team_alpha, team_beta])
    await db.flush()

    agent_a1 = Agent(name="Agent A1", team_id=team_alpha.id)
    agent_a2 = Agent(name="Agent A2", team_id=team_alpha.id)
    agent_b1 = Agent(name="Agent B1", team_id=team_beta.id)
    db.add_all([agent_a1, agent_a2, agent_b1])
    await db.flush()

    def _call(agent_id: uuid.UUID, ts: datetime) -> Call:
        return Call(
            status=CallStatus.scored,
            storage_key="test/dummy.wav",
            original_filename="dummy.wav",
            agent_id=agent_id,
            created_at=ts,
        )

    c1 = _call(agent_a1.id, _JUNE_1)
    c2 = _call(agent_a1.id, _JUNE_8)
    c3 = _call(agent_a2.id, _JUNE_1)
    c4 = _call(agent_a2.id, _JUNE_8)
    c5 = _call(agent_b1.id, _JUNE_1)
    c6 = _call(agent_b1.id, _JUNE_8)
    u1 = Call(
        status=CallStatus.uploaded,
        storage_key="test/u1.wav",
        original_filename="u1.wav",
        agent_id=agent_a1.id,
    )
    u2 = Call(
        status=CallStatus.transcribed,
        storage_key="test/u2.wav",
        original_filename="u2.wav",
        agent_id=agent_a2.id,
    )
    db.add_all([c1, c2, c3, c4, c5, c6, u1, u2])
    await db.flush()

    def _analysis(
        call_id: uuid.UUID,
        score: int,
        compliance: bool,
        escalate: bool,
        reason: str | None = None,
    ) -> CallAnalysis:
        return CallAnalysis(
            call_id=call_id,
            overall_score=score,
            summary="test",
            key_moments=[],
            action_items=[],
            compliance_passed=compliance,
            escalate_for_review=escalate,
            escalation_reason=reason,
        )

    db.add_all(
        [
            _analysis(c1.id, 80, True, False),
            _analysis(c2.id, 90, True, False),
            _analysis(c3.id, 55, True, False),
            _analysis(c4.id, 40, False, True, "Low overall"),
            _analysis(c5.id, 75, True, False),
            _analysis(c6.id, 30, False, True, "Low overall"),
        ]
    )
    await db.commit()

    return AnalyticsDataset(
        team_alpha_id=team_alpha.id,
        team_beta_id=team_beta.id,
        agent_a1_id=agent_a1.id,
        agent_a2_id=agent_a2.id,
        agent_b1_id=agent_b1.id,
    )

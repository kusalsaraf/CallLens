"""Shared pytest fixtures for the test suite."""

import os
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import calllens.db.models  # noqa: F401 — registers ORM models on Base.metadata
from calllens.db.base import Base
from calllens.db.session import get_db
from calllens.main import app
from calllens.services.seed import seed_defaults

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

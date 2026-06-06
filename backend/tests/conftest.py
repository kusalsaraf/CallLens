"""Shared pytest fixtures for the test suite."""

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import calllens.db.models  # noqa: F401 — registers ORM models on Base.metadata
from calllens.db.base import Base
from calllens.db.session import get_db
from calllens.main import app

_TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://calllens:calllens@localhost:5432/calllens",
)


@pytest_asyncio.fixture
async def db_engine():
    """Create tables before the test and drop them after."""
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    """HTTP test client with the DB session overridden to the test engine."""
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Convenience helpers used across test modules
# ---------------------------------------------------------------------------

_SIGNUP_PAYLOAD = {
    "email": "owner@example.com",
    "password": "superSecret1",
    "name": "Test Owner",
}


async def signup_and_get_token(client: AsyncClient) -> str:
    """Sign up the owner and return the access token."""
    resp = await client.post("/api/v1/auth/signup", json=_SIGNUP_PAYLOAD)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])

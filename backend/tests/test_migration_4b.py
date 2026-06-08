"""Smoke-test that the Phase 4B migration tables exist after create_all."""

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import calllens.db.models  # noqa: F401
from calllens.db.base import Base

_TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://calllens:calllens@localhost:5432/calllens",
)


@pytest_asyncio.fixture
async def fresh_engine():
    """Create all tables, yield the engine, then drop all."""
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_phase4b_tables_exist(fresh_engine) -> None:  # type: ignore[no-untyped-def]
    async with fresh_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
        tables = {row[0] for row in result}

    assert "call_analyses" in tables
    assert "coaching_notes" in tables
    assert "audit_logs" in tables
    assert "call_agent_runs" in tables

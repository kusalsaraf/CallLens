"""Service-layer tests for the Phase 4B scoring service rewrite."""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import calllens.db.models  # noqa: F401 — registers all models
from calllens.db.base import Base
from calllens.db.models.agent import Agent
from calllens.db.models.agent_run import CallAgentRun
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.audit import AuditLog
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.coaching import CoachingNote
from calllens.db.models.rubric import RubricDimension
from calllens.db.models.scoring import CallScore
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.seed.rubric import seed_default_rubric
from calllens.services.scoring_service import score_call
from calllens.services.seed import seed_defaults

_TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://calllens:calllens@localhost:5432/calllens",
)


@pytest_asyncio.fixture
async def engine():
    """Fresh database schema for each test."""
    eng = create_async_engine(_TEST_DB_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine):
    """Open session bound to the test engine."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_call(db: AsyncSession) -> Call:
    """Create a Call with Transcript, Segments, and default Rubric."""
    await seed_defaults(db)
    await seed_default_rubric(db)

    agent = (await db.execute(select(Agent).limit(1))).scalar_one()

    call = Call(
        id=uuid.uuid4(),
        status=CallStatus.transcribed,
        storage_key="test.wav",
        original_filename="test.wav",
        agent_id=agent.id,
    )
    db.add(call)
    await db.flush()

    transcript = Transcript(id=uuid.uuid4(), call_id=call.id, language="en")
    db.add(transcript)
    await db.flush()

    for i in range(4):
        speaker = "agent" if i % 2 == 0 else "customer"
        db.add(
            TranscriptSegment(
                id=uuid.uuid4(),
                transcript_id=transcript.id,
                sequence=i,
                start_ms=i * 5000,
                end_ms=(i + 1) * 5000,
                text=f"This is segment {i} spoken by {speaker}.",
                speaker=speaker,
            )
        )
    await db.commit()
    await db.refresh(call)
    return call


async def test_score_call_persists_all_rows(db: AsyncSession, seeded_call: Call) -> None:
    await score_call(seeded_call.id, db=db)

    scores = (
        (await db.execute(select(CallScore).where(CallScore.call_id == seeded_call.id)))
        .scalars()
        .all()
    )
    assert len(scores) > 0, "Expected at least one CallScore row"

    analysis = (
        await db.execute(select(CallAnalysis).where(CallAnalysis.call_id == seeded_call.id))
    ).scalar_one_or_none()
    assert analysis is not None
    assert 0 <= analysis.overall_score <= 100

    runs = (
        (await db.execute(select(CallAgentRun).where(CallAgentRun.call_id == seeded_call.id)))
        .scalars()
        .all()
    )
    assert len(runs) >= 2, "Expected at least preprocess + supervisor nodes"

    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.entity == "call",
                AuditLog.entity_id == seeded_call.id,
                AuditLog.action == "score",
            )
        )
    ).scalar_one_or_none()
    assert audit is not None

    await db.refresh(seeded_call)
    assert seeded_call.status == CallStatus.scored


async def test_reprocess_is_idempotent(db: AsyncSession, seeded_call: Call) -> None:
    await score_call(seeded_call.id, db=db)
    await score_call(seeded_call.id, db=db)

    analysis_rows = (
        (await db.execute(select(CallAnalysis).where(CallAnalysis.call_id == seeded_call.id)))
        .scalars()
        .all()
    )

    assert len(analysis_rows) == 1, "Must have exactly one CallAnalysis after two passes"

    score_rows = (
        (await db.execute(select(CallScore).where(CallScore.call_id == seeded_call.id)))
        .scalars()
        .all()
    )

    dim_count = (await db.execute(select(RubricDimension))).scalars().all()
    active_count = sum(1 for d in dim_count if d.kind in ("score", "ratio"))
    assert len(score_rows) == active_count, f"Expected {active_count} scores, got {len(score_rows)}"


async def test_reprocess_preserves_manual_coaching_notes(
    db: AsyncSession, seeded_call: Call
) -> None:
    await score_call(seeded_call.id, db=db)

    manual_note = CoachingNote(
        agent_id=seeded_call.agent_id,
        call_id=seeded_call.id,
        source="manual",
        note="Manually written coaching note.",
    )
    db.add(manual_note)
    await db.commit()

    await score_call(seeded_call.id, db=db)

    notes = (
        (
            await db.execute(
                select(CoachingNote).where(
                    CoachingNote.call_id == seeded_call.id,
                    CoachingNote.source == "manual",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notes) == 1, "Manual coaching note must survive reprocess"


async def test_score_call_rollback_on_graph_error(db: AsyncSession, seeded_call: Call) -> None:
    with patch(
        "calllens.services.scoring_service.run_scoring_graph",
        new_callable=AsyncMock,
        side_effect=RuntimeError("graph exploded"),
    ):
        await score_call(seeded_call.id, db=db)

    await db.refresh(seeded_call)
    assert seeded_call.status == CallStatus.failed

    scores = (
        (await db.execute(select(CallScore).where(CallScore.call_id == seeded_call.id)))
        .scalars()
        .all()
    )
    assert len(scores) == 0, "No CallScore rows should survive a failed scoring pass"

    analyses = (
        (await db.execute(select(CallAnalysis).where(CallAnalysis.call_id == seeded_call.id)))
        .scalars()
        .all()
    )
    assert len(analyses) == 0

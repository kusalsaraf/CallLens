"""Tests for calllens.services.scoring_service.score_call."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from calllens.db.models.call import Call, CallStatus
from calllens.db.models.scoring import CallScore, ScoreEvidence
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.seed.rubric import seed_default_rubric
from calllens.services.scoring_service import score_call

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def scored_call_setup(db_engine: object) -> tuple[async_sessionmaker, uuid.UUID]:
    """Seed DB, create a Call with transcript + segments; return (factory, call_id).

    Yields:
        Tuple of (async session factory, call UUID).
    """
    factory = async_sessionmaker(
        bind=db_engine,  # type: ignore[call-arg]
        expire_on_commit=False,
        class_=AsyncSession,
    )

    # Seed default team/agent + default rubric
    async with factory() as db:
        await seed_default_rubric(db)

    # Fetch the default agent to reference from the Call
    from calllens.services.seed import get_default_agent

    async with factory() as db:
        agent = await get_default_agent(db)

    call_id = uuid.uuid4()

    async with factory() as db:
        call = Call(
            id=call_id,
            status=CallStatus.transcribed,
            storage_key=f"{call_id}.wav",
            original_filename="test_call.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.flush()

        transcript = Transcript(id=uuid.uuid4(), call_id=call_id, language="en")
        db.add(transcript)
        await db.flush()

        segments = [
            TranscriptSegment(
                id=uuid.uuid4(),
                transcript_id=transcript.id,
                sequence=0,
                start_ms=0,
                end_ms=3000,
                text="I completely understand your frustration and I will help resolve this now.",
                speaker="agent",
            ),
            TranscriptSegment(
                id=uuid.uuid4(),
                transcript_id=transcript.id,
                sequence=1,
                start_ms=3001,
                end_ms=6000,
                text="I have been waiting for three days and nothing has been fixed.",
                speaker="customer",
            ),
            TranscriptSegment(
                id=uuid.uuid4(),
                transcript_id=transcript.id,
                sequence=2,
                start_ms=6001,
                end_ms=9000,
                text="Let me escalate this to our senior team immediately.",
                speaker="agent",
            ),
        ]
        for seg in segments:
            db.add(seg)
        await db.commit()

    return factory, call_id


# ---------------------------------------------------------------------------
# Test 1: score_call happy path
# ---------------------------------------------------------------------------


async def test_score_call_happy_path(
    scored_call_setup: tuple[async_sessionmaker, uuid.UUID],
) -> None:
    """score_call persists CallScore + ScoreEvidence and sets status=scored."""
    factory, call_id = scored_call_setup

    async with factory() as db:
        with patch(
            "calllens.services.scoring_service.publish_call_event",
            new_callable=AsyncMock,
        ):
            await score_call(call_id, db=db)

    async with factory() as db:
        call_result = await db.execute(select(Call).where(Call.id == call_id))
        call = call_result.scalar_one()
        assert call.status == CallStatus.scored

        score_result = await db.execute(select(CallScore).where(CallScore.call_id == call_id))
        scores = score_result.scalars().all()
        assert len(scores) >= 1, "Expected at least one CallScore row"

        for call_score in scores:
            assert 0 <= call_score.score <= 100

        # Verify that at least one score has evidence referencing real segments
        seg_result = await db.execute(select(TranscriptSegment))
        valid_seg_ids = {seg.id for seg in seg_result.scalars().all()}
        all_evidence = []
        for call_score in scores:
            ev_result = await db.execute(
                select(ScoreEvidence).where(ScoreEvidence.call_score_id == call_score.id)
            )
            all_evidence.extend(ev_result.scalars().all())
        for ev in all_evidence:
            if ev.segment_id is not None:
                assert ev.segment_id in valid_seg_ids


# ---------------------------------------------------------------------------
# Test 2: provider error sets call status to failed
# ---------------------------------------------------------------------------


async def test_score_call_provider_error_sets_failed(
    scored_call_setup: tuple[async_sessionmaker, uuid.UUID],
) -> None:
    """When the LLM provider raises, call status is set to failed with a detail."""
    factory, call_id = scored_call_setup

    async with factory() as db:
        with (
            patch(
                "calllens.services.scoring_service.publish_call_event",
                new_callable=AsyncMock,
            ),
            patch(
                "calllens.services.scoring_service.run_scoring_graph",
                new_callable=AsyncMock,
                side_effect=RuntimeError("provider exploded"),
            ),
        ):
            await score_call(call_id, db=db)

    async with factory() as db:
        call_result = await db.execute(select(Call).where(Call.id == call_id))
        call = call_result.scalar_one()
        assert call.status == CallStatus.failed
        assert call.status_detail is not None
        assert "provider exploded" in call.status_detail


# ---------------------------------------------------------------------------
# Test 3: score_call with no transcript sets status failed
# ---------------------------------------------------------------------------


async def test_score_call_no_transcript_sets_failed(db_engine: object) -> None:
    """A call with no Transcript row results in status=failed."""
    factory = async_sessionmaker(
        bind=db_engine,  # type: ignore[call-arg]
        expire_on_commit=False,
        class_=AsyncSession,
    )

    from calllens.seed.rubric import seed_default_rubric as _seed_rubric
    from calllens.services.seed import get_default_agent

    async with factory() as db:
        await _seed_rubric(db)
        agent = await get_default_agent(db)

    call_id = uuid.uuid4()
    async with factory() as db:
        call = Call(
            id=call_id,
            status=CallStatus.transcribed,
            storage_key=f"{call_id}.wav",
            original_filename="no_transcript.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.commit()

    async with factory() as db:
        with patch(
            "calllens.services.scoring_service.publish_call_event",
            new_callable=AsyncMock,
        ):
            await score_call(call_id, db=db)

    async with factory() as db:
        call_result = await db.execute(select(Call).where(Call.id == call_id))
        call = call_result.scalar_one()
        assert call.status == CallStatus.failed

"""End-to-end integration test for the Phase 3A scoring pipeline."""

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


@pytest_asyncio.fixture
async def e2e_call_id(db_engine: object) -> uuid.UUID:
    """Set up a fully seeded Call ready for e2e scoring and return its UUID.

    Creates the default rubric, team, agent, a Call with status=transcribed,
    a Transcript, and three TranscriptSegment rows.

    Args:
        db_engine: SQLAlchemy async engine pointed at the test database.

    Returns:
        UUID of the prepared Call.
    """
    factory = async_sessionmaker(
        bind=db_engine,  # type: ignore[call-arg]
        expire_on_commit=False,
        class_=AsyncSession,
    )

    async with factory() as db:
        await seed_default_rubric(db)

    from calllens.services.seed import get_default_agent

    async with factory() as db:
        agent = await get_default_agent(db)

    call_id = uuid.uuid4()
    async with factory() as db:
        call = Call(
            id=call_id,
            status=CallStatus.transcribed,
            storage_key=f"{call_id}.wav",
            original_filename="e2e_test.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.flush()

        transcript = Transcript(id=uuid.uuid4(), call_id=call_id, language="en")
        db.add(transcript)
        await db.flush()

        for i, (speaker, text) in enumerate(
            [
                ("agent", "Thank you for calling support, how can I help you today?"),
                ("customer", "I am really frustrated with the billing error on my account."),
                ("agent", "I completely understand your frustration and I sincerely apologize."),
            ]
        ):
            seg = TranscriptSegment(
                id=uuid.uuid4(),
                transcript_id=transcript.id,
                sequence=i,
                start_ms=i * 3000,
                end_ms=(i + 1) * 3000,
                text=text,
                speaker=speaker,
            )
            db.add(seg)
        await db.commit()

    return call_id


# ---------------------------------------------------------------------------
# E2E Test: full pipeline wires together correctly
# ---------------------------------------------------------------------------


async def test_e2e_score_call_pipeline(db_engine: object, e2e_call_id: uuid.UUID) -> None:
    """score_call wires the sentiment agent, evidence validator, and DB persistence.

    Asserts:
    - Call status is set to scored.
    - Exactly one CallScore row exists in [0, 100].
    - At least one ScoreEvidence row exists.
    - All evidence segment_ids reference real TranscriptSegment rows.
    """
    factory = async_sessionmaker(
        bind=db_engine,  # type: ignore[call-arg]
        expire_on_commit=False,
        class_=AsyncSession,
    )

    with patch(
        "calllens.services.scoring_service.publish_call_event",
        new_callable=AsyncMock,
    ):
        async with factory() as db:
            await score_call(e2e_call_id, db=db)

    async with factory() as db:
        # Assert call status is scored.
        call_result = await db.execute(select(Call).where(Call.id == e2e_call_id))
        call = call_result.scalar_one()
        assert call.status == CallStatus.scored, f"Expected scored, got {call.status}"

        # Assert exactly one CallScore with score in valid range.
        score_result = await db.execute(select(CallScore).where(CallScore.call_id == e2e_call_id))
        scores = score_result.scalars().all()
        assert len(scores) == 1, f"Expected 1 CallScore, got {len(scores)}"
        call_score = scores[0]
        assert 0 <= call_score.score <= 100, f"Score {call_score.score} out of range"
        assert 0.0 <= call_score.confidence <= 1.0

        # Assert at least one ScoreEvidence row.
        ev_result = await db.execute(
            select(ScoreEvidence).where(ScoreEvidence.call_score_id == call_score.id)
        )
        evidence_rows = ev_result.scalars().all()
        assert len(evidence_rows) >= 1, "Expected at least one ScoreEvidence row"

        # Assert all evidence segment_ids reference real segments.
        seg_result = await db.execute(select(TranscriptSegment))
        valid_seg_ids = {seg.id for seg in seg_result.scalars().all()}

        for ev in evidence_rows:
            assert ev.segment_id in valid_seg_ids, (
                f"Evidence references unknown segment_id {ev.segment_id}"
            )
            assert isinstance(ev.quote, str) and len(ev.quote) > 0, (
                "Evidence quote must be non-empty"
            )

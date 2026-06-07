"""Scoring service: runs the sentiment/empathy agent and persists results."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.agents.llm import TranscriptSegmentData
from calllens.agents.sentiment import RubricDimensionData, score_sentiment_empathy
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.rubric import Rubric, RubricDimension
from calllens.db.models.scoring import CallScore, ScoreEvidence
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.db.session import get_session_factory
from calllens.services.call_events import publish_call_event

logger = logging.getLogger(__name__)


async def _set_status(
    db: AsyncSession,
    call: Call,
    status: CallStatus,
    detail: str | None = None,
) -> None:
    """Update call status, commit, and publish the event.

    Args:
        db: Active database session.
        call: The Call ORM object to update.
        status: Target CallStatus value.
        detail: Optional human-readable detail (e.g. error message).
    """
    call.status = status
    call.status_detail = detail
    await db.commit()
    await db.refresh(call)
    try:
        await publish_call_event(call.id, status.value, detail)
    except Exception:
        logger.warning(
            "Failed to publish call event",
            extra={"call_id": str(call.id), "status": status.value},
        )


async def score_call(call_id: uuid.UUID, db: AsyncSession | None = None) -> None:
    """Score a transcribed call using the sentiment/empathy agent.

    Loads the transcript and segments, fetches the default rubric's
    sentiment_empathy dimension, runs the scoring agent, persists
    CallScore and validated ScoreEvidence rows, then sets call status
    to scored. On any error, sets status to failed and logs.

    Args:
        call_id: UUID of the Call to score.
        db: Optional open database session; if None, opens a new session.
    """
    _owns_session = db is None
    if _owns_session:
        factory = get_session_factory()
        _ctx = factory()
        db = await _ctx.__aenter__()

    assert db is not None  # guaranteed: either passed in or opened above
    try:
        await _score_call_inner(call_id, db)
    finally:
        if _owns_session:
            await _ctx.__aexit__(None, None, None)


async def _score_call_inner(call_id: uuid.UUID, db: AsyncSession) -> None:
    """Inner implementation of score_call that operates on a provided session.

    Args:
        call_id: UUID of the Call to score.
        db: Active database session.
    """
    # 1. Load the Call.
    call_result = await db.execute(select(Call).where(Call.id == call_id))
    call = call_result.scalar_one_or_none()
    if call is None:
        logger.error("score_call: call not found", extra={"call_id": str(call_id)})
        return

    try:
        # 2. Load the Transcript for this call.
        transcript_result = await db.execute(
            select(Transcript).where(Transcript.call_id == call_id)
        )
        transcript = transcript_result.scalar_one_or_none()
        if transcript is None:
            logger.error(
                "score_call: transcript not found",
                extra={"call_id": str(call_id)},
            )
            await _set_status(db, call, CallStatus.failed, detail="Transcript not found")
            return

        # 3. Load all TranscriptSegment rows, ordered by sequence.
        seg_result = await db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript.id)
            .order_by(TranscriptSegment.sequence)
        )
        segments = seg_result.scalars().all()

        # 4. Find the default rubric.
        rubric_result = await db.execute(select(Rubric).where(Rubric.is_default.is_(True)))
        rubric = rubric_result.scalar_one_or_none()
        if rubric is None:
            raise ValueError("No default rubric found")

        # 5. Find the sentiment_empathy dimension from that rubric.
        dim_result = await db.execute(
            select(RubricDimension).where(
                RubricDimension.rubric_id == rubric.id,
                RubricDimension.key == "sentiment_empathy",
            )
        )
        dimension = dim_result.scalar_one_or_none()
        if dimension is None:
            raise ValueError(f"No 'sentiment_empathy' dimension found on rubric {rubric.id}")

        # 6. Convert segments to TypedDict list.
        segment_data: list[TranscriptSegmentData] = [
            TranscriptSegmentData(
                id=seg.id,
                sequence=seg.sequence,
                text=seg.text,
                speaker=seg.speaker,
            )
            for seg in segments
        ]

        # 7. Convert dimension to RubricDimensionData TypedDict.
        dimension_data: RubricDimensionData = RubricDimensionData(
            id=dimension.id,
            key=dimension.key,
            name=dimension.name,
            weight=dimension.weight,
        )

        # 8. Run the scoring agent.
        agent_score = await score_sentiment_empathy(segment_data, dimension_data)

        # 9. Persist CallScore.
        call_score = CallScore(
            call_id=call_id,
            dimension_id=dimension.id,
            score=agent_score.score,
            confidence=agent_score.confidence,
            rationale=agent_score.rationale,
            is_supported=agent_score.is_supported,
        )
        db.add(call_score)
        await db.flush()

        # 10. Persist ScoreEvidence rows.
        for ref in agent_score.evidence:
            evidence = ScoreEvidence(
                call_score_id=call_score.id,
                segment_id=ref.segment_id,
                quote=ref.quote,
            )
            db.add(evidence)
        await db.flush()

        # 11. Set call status to scored.
        await _set_status(db, call, CallStatus.scored)
        logger.info(
            "Scoring complete",
            extra={
                "call_id": str(call_id),
                "score": agent_score.score,
                "is_supported": agent_score.is_supported,
            },
        )

    except Exception as exc:
        logger.exception("Scoring failed", extra={"call_id": str(call_id)})
        try:
            await _set_status(db, call, CallStatus.failed, detail=str(exc))
        except Exception:
            logger.exception(
                "Failed to update call status to failed after scoring error",
                extra={"call_id": str(call_id)},
            )

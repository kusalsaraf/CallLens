"""Scoring service: runs the LangGraph scoring graph and persists full output."""

from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.agents.graph import ScoringContext, run_scoring_graph
from calllens.agents.llm import TimedTranscriptSegmentData
from calllens.agents.specialists import FullRubricDimensionData
from calllens.core.config import get_settings
from calllens.db.models.agent_run import CallAgentRun
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.audit import AuditLog
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.coaching import CoachingNote
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
    """Update call status, commit, and publish the SSE event.

    Args:
        db: Active database session.
        call: The Call ORM object to update.
        status: Target CallStatus value.
        detail: Optional human-readable detail.
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


async def score_call(
    call_id: uuid.UUID,
    db: AsyncSession | None = None,
    *,
    rebind_rubric: bool = False,
) -> None:
    """Run the LangGraph scoring graph and persist all output for a call.

    Opens its own session if none is provided. On error, rolls back all
    writes and sets the call status to failed.

    Args:
        call_id: UUID of the Call to score.
        db: Optional open database session; if None, opens a new session.
        rebind_rubric: If True, rebind the call to the currently active rubric
            before scoring (used by reprocess to pick up a new rubric).
    """
    _owns_session = db is None
    if _owns_session:
        factory = get_session_factory()
        _ctx = factory()
        db = await _ctx.__aenter__()

    assert db is not None
    try:
        await _score_call_inner(call_id, db, rebind_rubric=rebind_rubric)
    finally:
        if _owns_session:
            await _ctx.__aexit__(None, None, None)


async def _score_call_inner(
    call_id: uuid.UUID,
    db: AsyncSession,
    *,
    rebind_rubric: bool = False,
) -> None:
    """Inner implementation: loads data, runs graph, persists in one transaction.

    Args:
        call_id: UUID of the Call to score.
        db: Active database session.
        rebind_rubric: If True, rebind to the currently active rubric first.
    """
    # 1. Load Call — return silently if missing (Celery retry guard).
    call = (await db.execute(select(Call).where(Call.id == call_id))).scalar_one_or_none()
    if call is None:
        logger.error("score_call: call not found", extra={"call_id": str(call_id)})
        return

    try:
        # 2. Load Transcript.
        transcript = (
            await db.execute(select(Transcript).where(Transcript.call_id == call_id))
        ).scalar_one_or_none()
        if transcript is None:
            await _set_status(db, call, CallStatus.failed, detail="Transcript not found")
            return

        # 3. Load Segments ordered by sequence.
        segments = (
            (
                await db.execute(
                    select(TranscriptSegment)
                    .where(TranscriptSegment.transcript_id == transcript.id)
                    .order_by(TranscriptSegment.sequence)
                )
            )
            .scalars()
            .all()
        )

        # 4. Load rubric: use call's bound rubric, or rebind to active, or fallback to default.
        if rebind_rubric or call.rubric_id is None:
            rubric = (
                await db.execute(select(Rubric).where(Rubric.is_active.is_(True)))
            ).scalar_one_or_none()
            if rubric is None:
                rubric = (
                    await db.execute(select(Rubric).where(Rubric.is_default.is_(True)))
                ).scalar_one_or_none()
            if rubric is not None:
                call.rubric_id = rubric.id
                await db.flush()
        else:
            rubric = (
                await db.execute(select(Rubric).where(Rubric.id == call.rubric_id))
            ).scalar_one_or_none()

        if rubric is None:
            raise ValueError("No rubric found for scoring")

        # 5. Load all Dimensions for the rubric.
        dimensions = (
            (
                await db.execute(
                    select(RubricDimension).where(RubricDimension.rubric_id == rubric.id)
                )
            )
            .scalars()
            .all()
        )

        # 6. Build typed inputs for the graph.
        timed_segments: list[TimedTranscriptSegmentData] = [
            TimedTranscriptSegmentData(
                id=seg.id,
                sequence=seg.sequence,
                text=seg.text,
                speaker=seg.speaker,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
            )
            for seg in segments
        ]
        full_dimensions: list[FullRubricDimensionData] = [
            FullRubricDimensionData(
                id=dim.id,
                key=dim.key,
                name=dim.name,
                weight=dim.weight,
                kind=dim.kind,
                config=dim.config,
            )
            for dim in dimensions
        ]
        context = ScoringContext(
            segments=timed_segments,
            dimensions=full_dimensions,
        )

        # 7. Run the LangGraph scoring graph.
        t_start = time.monotonic()
        scoring_result = await run_scoring_graph(context)
        total_ms = int((time.monotonic() - t_start) * 1000)

        supervisor = scoring_result["supervisor_result"]
        metrics = scoring_result["metrics"]
        dim_scores = scoring_result["dimension_scores"]

        # 8. Idempotent cleanup — delete prior auto data in this same transaction.
        await db.execute(delete(CallScore).where(CallScore.call_id == call_id))
        await db.execute(delete(CallAnalysis).where(CallAnalysis.call_id == call_id))
        await db.execute(delete(CallAgentRun).where(CallAgentRun.call_id == call_id))
        await db.execute(
            delete(CoachingNote).where(
                CoachingNote.call_id == call_id,
                CoachingNote.source == "auto",
            )
        )
        await db.flush()

        # 9. Persist CallScore + ScoreEvidence per dimension.
        dim_by_key = {dim.key: dim for dim in dimensions}
        for key, agent_score in dim_scores.items():
            dim = dim_by_key.get(key)
            if dim is None:
                continue
            call_score = CallScore(
                call_id=call_id,
                dimension_id=dim.id,
                score=agent_score.score,
                confidence=agent_score.confidence,
                rationale=agent_score.rationale,
                is_supported=agent_score.is_supported,
            )
            db.add(call_score)
            await db.flush()
            for ref in agent_score.evidence:
                db.add(
                    ScoreEvidence(
                        call_score_id=call_score.id,
                        segment_id=ref.segment_id,
                        quote=ref.quote,
                    )
                )
        await db.flush()

        # 10. Derive sentiment_overall and compliance_passed.
        sentiment_obj = dim_scores.get("sentiment_empathy")
        sentiment_overall: str | None = None
        if sentiment_obj is not None:
            if sentiment_obj.score >= 70:
                sentiment_overall = "positive"
            elif sentiment_obj.score >= 40:
                sentiment_overall = "neutral"
            else:
                sentiment_overall = "negative"

        compliance_obj = dim_scores.get("compliance")
        compliance_passed = compliance_obj.score >= 50 if compliance_obj is not None else True

        # 11. Persist CallAnalysis.
        analysis = CallAnalysis(
            call_id=call_id,
            overall_score=supervisor.overall_score,
            summary=supervisor.summary,
            key_moments=[
                {"segment_id": str(km.segment_id), "label": km.label}
                for km in supervisor.key_moments
            ],
            action_items=list(supervisor.action_items),
            sentiment_overall=sentiment_overall,
            talk_listen_ratio=metrics.talk_listen_ratio,
            interruptions=metrics.interruptions,
            longest_monologue_ms=metrics.longest_monologue_ms,
            total_turns=metrics.total_turns,
            compliance_passed=compliance_passed,
            escalate_for_review=supervisor.escalate_for_review,
            escalation_reason=supervisor.escalation_reason,
        )
        db.add(analysis)
        await db.flush()

        # 12. Auto CoachingNote if escalated and call has an agent.
        if supervisor.escalate_for_review and call.agent_id is not None:
            db.add(
                CoachingNote(
                    agent_id=call.agent_id,
                    call_id=call_id,
                    source="auto",
                    note=supervisor.escalation_reason or "Flagged for review by automated scoring.",
                )
            )
            await db.flush()

        # 13. Persist CallAgentRun trace.
        settings = get_settings()
        llm_provider_name = settings.llm_provider
        n_nodes = len(dim_scores) + 2  # specialists + preprocess + supervisor
        per_node_ms = total_ms // max(n_nodes, 1)

        db.add(
            CallAgentRun(
                call_id=call_id,
                node="preprocess",
                role="preprocess",
                provider="deterministic",
                score=None,
                confidence=None,
                evidence_kept=0,
                evidence_dropped=0,
                duration_ms=per_node_ms,
                detail={"segments": len(segments)},
            )
        )
        for key, agent_score in dim_scores.items():
            dim = dim_by_key.get(key)
            node_provider = (
                "deterministic" if dim is not None and dim.kind == "ratio" else llm_provider_name
            )
            db.add(
                CallAgentRun(
                    call_id=call_id,
                    node=key,
                    role="specialist",
                    provider=node_provider,
                    score=agent_score.score,
                    confidence=agent_score.confidence,
                    evidence_kept=len(agent_score.evidence),
                    evidence_dropped=0,
                    duration_ms=per_node_ms,
                    detail={"rationale": agent_score.rationale[:200]},
                )
            )
        db.add(
            CallAgentRun(
                call_id=call_id,
                node="supervisor",
                role="supervisor",
                provider=llm_provider_name,
                score=supervisor.overall_score,
                confidence=None,
                evidence_kept=0,
                evidence_dropped=0,
                duration_ms=per_node_ms,
                detail={
                    "escalate": supervisor.escalate_for_review,
                    "escalation_reason": supervisor.escalation_reason,
                },
            )
        )
        await db.flush()

        # 14. AuditLog.
        db.add(
            AuditLog(
                actor="system",
                action="score",
                entity="call",
                entity_id=call_id,
                payload={"overall_score": supervisor.overall_score},
            )
        )
        await db.flush()

        # 15. Commit all via _set_status.
        await _set_status(db, call, CallStatus.scored)
        logger.info(
            "Scoring complete",
            extra={"call_id": str(call_id), "overall_score": supervisor.overall_score},
        )

    except Exception as exc:
        logger.exception("Scoring failed", extra={"call_id": str(call_id)})
        await db.rollback()
        # Reload call after rollback — session state was reset.
        call = (await db.execute(select(Call).where(Call.id == call_id))).scalar_one_or_none()
        if call is not None:
            try:
                await _set_status(db, call, CallStatus.failed, detail=str(exc))
            except Exception:
                logger.exception(
                    "Failed to set call status to failed after scoring error",
                    extra={"call_id": str(call_id)},
                )

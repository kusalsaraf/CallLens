"""Calls API — upload, list, detail, transcript, audio streaming, SSE, delete."""

import json
import logging
import os
import tempfile
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated

import magic
from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from calllens.core.config import get_settings
from calllens.core.deps import get_current_user
from calllens.core.exceptions import NotFoundError, ValidationError
from calllens.db.models.agent_run import CallAgentRun
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.call import Call, CallStatus, is_terminal
from calllens.db.models.rubric import Rubric
from calllens.db.models.scoring import CallScore
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.schemas.analysis import AgentRunOut, CallAnalysisOut, TraceOut
from calllens.schemas.calls import (
    CallListOut,
    CallOut,
    CallScoreOut,
    DimensionInfo,
    EvidenceOut,
    ScoresListOut,
    SegmentOut,
    TranscriptOut,
)
from calllens.services.scoring_service import score_call
from calllens.services.seed import get_default_agent
from calllens.storage.factory import get_storage
from calllens.tasks.pipeline import process_call_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calls", tags=["calls"])


def _call_storage_key(call_id: uuid.UUID, original_filename: str) -> str:
    ext = Path(original_filename).suffix.lower()
    return f"{call_id}{ext}"


async def _get_call_or_404(call_id: uuid.UUID, db: AsyncSession) -> Call:
    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    if call is None:
        raise NotFoundError(f"Call {call_id} not found")
    return call


# ---------------------------------------------------------------------------
# POST / — multipart upload
# ---------------------------------------------------------------------------


@router.post("/", response_model=CallOut, status_code=201)
async def upload_call(
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CallOut:
    """Accept a multipart audio upload, save to storage, enqueue pipeline.

    Args:
        file: The uploaded audio file.
        db: Database session.
        current_user: Authenticated user (enforces auth guard).

    Returns:
        The newly created Call in "uploaded" status.

    Raises:
        ValidationError: If the file is missing, empty, oversized, or wrong MIME type.
    """
    settings = get_settings()

    if not file.filename:
        raise ValidationError("No file provided")

    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise ValidationError("Uploaded file is empty")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise ValidationError(f"File exceeds maximum allowed size of {settings.max_upload_mb} MB")

    # Write to a temp file so magic can inspect the full header reliably
    # (magic.from_buffer is unreliable for RIFF-based formats on some platforms)
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(audio_bytes[:8192])
        tmp_path = tf.name
    try:
        sniffed_mime = magic.from_file(tmp_path, mime=True)
    finally:
        os.unlink(tmp_path)

    if sniffed_mime not in settings.allowed_audio_mimes:
        raise ValidationError(
            f"Unsupported file type: {sniffed_mime!r}. Allowed: {settings.allowed_audio_mimes}"
        )

    call_id = uuid.uuid4()
    storage = get_storage()
    key = _call_storage_key(call_id, file.filename)
    await storage.save(audio_bytes, key)

    agent = await get_default_agent(db)

    # Bind to the currently active rubric (snapshot); fall back to default seed
    active_rubric = (
        await db.execute(select(Rubric).where(Rubric.is_active.is_(True)))
    ).scalar_one_or_none()
    if active_rubric is None:
        active_rubric = (
            await db.execute(select(Rubric).where(Rubric.is_default.is_(True)))
        ).scalar_one_or_none()

    call = Call(
        id=call_id,
        status=CallStatus.uploaded,
        storage_key=key,
        original_filename=file.filename,
        agent_id=agent.id,
        rubric_id=active_rubric.id if active_rubric else None,
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    process_call_task.delay(str(call.id))
    logger.info("Call uploaded", extra={"call_id": str(call.id), "mime": sniffed_mime})

    return CallOut.from_orm_call(call)


# ---------------------------------------------------------------------------
# GET / — list calls
# ---------------------------------------------------------------------------


@router.get("/", response_model=CallListOut)
async def list_calls(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: str | None = None,
    agent_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> CallListOut:
    """List calls newest-first with optional filters and pagination.

    Args:
        db: Database session.
        current_user: Authenticated user.
        status: Optional CallStatus value to filter by.
        agent_id: Optional agent UUID to filter by.
        page: 1-based page number.
        page_size: Items per page (max 100).

    Returns:
        Paginated list of CallOut.
    """
    page_size = min(page_size, 100)
    offset = (page - 1) * page_size

    stmt = select(Call).order_by(Call.created_at.desc())
    if status is not None:
        try:
            stmt = stmt.where(Call.status == CallStatus(status))
        except ValueError:
            raise ValidationError(f"Invalid status: {status!r}") from None
    if agent_id is not None:
        stmt = stmt.where(Call.agent_id == agent_id)

    total_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = total_result.scalar_one()

    rows_result = await db.execute(stmt.offset(offset).limit(page_size))
    calls = rows_result.scalars().all()

    return CallListOut(
        items=[CallOut.from_orm_call(c) for c in calls],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# GET /{id} — call detail
# ---------------------------------------------------------------------------


@router.get("/{call_id}", response_model=CallOut)
async def get_call(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CallOut:
    """Return detail for a single call.

    Args:
        call_id: UUID of the target call.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        CallOut for the requested call.
    """
    call = await _get_call_or_404(call_id, db)
    return CallOut.from_orm_call(call)


# ---------------------------------------------------------------------------
# GET /{id}/transcript
# ---------------------------------------------------------------------------


@router.get("/{call_id}/transcript", response_model=TranscriptOut)
async def get_transcript(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TranscriptOut:
    """Return the transcript and ordered segments for a call.

    Args:
        call_id: UUID of the target call.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        TranscriptOut with all segments in sequence order.

    Raises:
        NotFoundError: If the call does not exist or has no transcript yet.
    """
    await _get_call_or_404(call_id, db)

    t_result = await db.execute(select(Transcript).where(Transcript.call_id == call_id))
    transcript = t_result.scalar_one_or_none()
    if transcript is None:
        raise NotFoundError("Transcript not yet available for this call")

    seg_result = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.sequence)
    )
    segments = seg_result.scalars().all()

    return TranscriptOut(
        id=transcript.id,
        call_id=transcript.call_id,
        language=transcript.language,
        redaction_provider=transcript.redaction_provider,
        entities_redacted=transcript.entities_redacted,
        segments=[
            SegmentOut(
                id=seg.id,
                sequence=seg.sequence,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                text=seg.text,
                redacted_text=seg.redacted_text,
                speaker=seg.speaker,
            )
            for seg in segments
        ],
        created_at=transcript.created_at,
    )


# ---------------------------------------------------------------------------
# GET /{id}/audio — streaming with Range support
# ---------------------------------------------------------------------------


@router.get("/{call_id}/audio")
async def stream_audio(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    range: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """Stream stored audio, honouring HTTP Range requests.

    Args:
        call_id: UUID of the call whose audio to stream.
        db: Database session.
        current_user: Authenticated user.
        range: Optional HTTP Range header (e.g. "bytes=0-1023").

    Returns:
        StreamingResponse — 206 for range requests, 200 for full stream.
    """
    call = await _get_call_or_404(call_id, db)
    storage = get_storage()

    if not await storage.exists(call.storage_key):
        raise NotFoundError("Audio file not found in storage")

    total_size = await storage.file_size(call.storage_key)
    media_type = "audio/mpeg"

    start = 0
    end: int | None = None
    status_code = 200
    headers: dict[str, str] = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(total_size),
    }

    if range:
        try:
            byte_range = range.replace("bytes=", "")
            parts = byte_range.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) + 1 if parts[1] else total_size
        except (ValueError, IndexError):
            raise HTTPException(status_code=416, detail="Invalid Range header") from None

        if start >= total_size or (end is not None and start >= end):
            raise HTTPException(
                status_code=416,
                detail="Range not satisfiable",
                headers={"Content-Range": f"bytes */{total_size}"},
            )

        end = min(end or total_size, total_size)
        content_length = end - start
        status_code = 206
        headers["Content-Range"] = f"bytes {start}-{end - 1}/{total_size}"
        headers["Content-Length"] = str(content_length)

    storage_ref = storage
    key_ref = call.storage_key
    start_ref = start
    end_ref = end

    async def _generator() -> AsyncGenerator[bytes, None]:
        async for chunk in storage_ref.open_stream(key_ref, start=start_ref, end=end_ref):
            yield chunk

    return StreamingResponse(
        _generator(),
        status_code=status_code,
        media_type=media_type,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# GET /{id}/events — SSE
# ---------------------------------------------------------------------------


@router.get("/{call_id}/events")
async def call_events(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """Server-Sent Events stream of call status changes.

    Emits the current status immediately on connect, then subscribes to
    Redis pub/sub and forwards updates until a terminal status is reached.

    Args:
        call_id: UUID of the call to monitor.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        text/event-stream StreamingResponse.
    """
    import redis.asyncio as aioredis

    call = await _get_call_or_404(call_id, db)
    settings = get_settings()
    channel = f"call:{call_id}:events"

    current_status = call.status.value
    already_terminal = is_terminal(call.status)

    async def _generator() -> AsyncGenerator[bytes, None]:
        yield f"data: {json.dumps({'status': current_status})}\n\n".encode()
        if already_terminal:
            return

        r: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=False)
        try:
            async with r.pubsub() as ps:
                await ps.subscribe(channel)
                async for msg in ps.listen():
                    if msg["type"] != "message":
                        continue
                    data_bytes = msg["data"]
                    payload_str = (
                        data_bytes.decode() if isinstance(data_bytes, bytes) else str(data_bytes)
                    )
                    yield f"data: {payload_str}\n\n".encode()
                    parsed = json.loads(payload_str)
                    if parsed.get("status") in ("transcribed", "scored", "failed"):
                        break
        finally:
            await r.aclose()

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# DELETE /{id}
# ---------------------------------------------------------------------------


@router.delete("/{call_id}", status_code=204)
async def delete_call(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a call and its stored audio file.

    Args:
        call_id: UUID of the call to delete.
        db: Database session.
        current_user: Authenticated user.
    """
    call = await _get_call_or_404(call_id, db)
    storage = get_storage()

    if await storage.exists(call.storage_key):
        await storage.delete(call.storage_key)

    await db.delete(call)
    await db.commit()
    logger.info("Call deleted", extra={"call_id": str(call_id)})


# ---------------------------------------------------------------------------
# GET /{id}/scores
# ---------------------------------------------------------------------------


@router.get("/{call_id}/scores", response_model=ScoresListOut)
async def get_call_scores(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ScoresListOut:
    """Return all scored dimensions for a call with evidence.

    Args:
        call_id: UUID of the target call.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        ScoresListOut with all CallScore rows and their evidence.
    """
    await _get_call_or_404(call_id, db)

    scores_result = await db.execute(
        select(CallScore)
        .where(CallScore.call_id == call_id)
        .options(selectinload(CallScore.evidence), selectinload(CallScore.dimension))
        .order_by(CallScore.scored_at)
    )
    scores = scores_result.scalars().all()

    return ScoresListOut(
        call_id=call_id,
        scores=[
            CallScoreOut(
                id=cs.id,
                dimension=DimensionInfo(
                    id=cs.dimension.id,
                    key=cs.dimension.key,
                    name=cs.dimension.name,
                    weight=cs.dimension.weight,
                ),
                score=cs.score,
                confidence=cs.confidence,
                rationale=cs.rationale,
                is_supported=cs.is_supported,
                scored_at=cs.scored_at,
                evidence=[
                    EvidenceOut(id=ev.id, segment_id=ev.segment_id, quote=ev.quote)
                    for ev in cs.evidence
                ],
            )
            for cs in scores
        ],
    )


# ---------------------------------------------------------------------------
# GET /{id}/analysis
# ---------------------------------------------------------------------------


@router.get("/{call_id}/analysis", response_model=CallAnalysisOut)
async def get_call_analysis(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CallAnalysisOut:
    """Return the aggregated analysis for a scored call.

    Args:
        call_id: UUID of the target call.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        CallAnalysisOut with overall score, summary, key moments, and metrics.

    Raises:
        NotFoundError: If the call or its analysis does not exist.
    """
    await _get_call_or_404(call_id, db)

    analysis = (
        await db.execute(select(CallAnalysis).where(CallAnalysis.call_id == call_id))
    ).scalar_one_or_none()
    if analysis is None:
        raise NotFoundError("Analysis not yet available for this call")

    return CallAnalysisOut.model_validate(analysis)


# ---------------------------------------------------------------------------
# GET /{id}/trace
# ---------------------------------------------------------------------------


@router.get("/{call_id}/trace", response_model=TraceOut)
async def get_call_trace(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TraceOut:
    """Return the agent run trace for a scored call.

    Args:
        call_id: UUID of the target call.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        TraceOut listing each LangGraph node execution in order.

    Raises:
        NotFoundError: If the call does not exist.
    """
    await _get_call_or_404(call_id, db)

    runs = (
        (
            await db.execute(
                select(CallAgentRun)
                .where(CallAgentRun.call_id == call_id)
                .order_by(CallAgentRun.created_at)
            )
        )
        .scalars()
        .all()
    )

    return TraceOut(
        call_id=call_id,
        runs=[AgentRunOut.model_validate(r) for r in runs],
    )


# ---------------------------------------------------------------------------
# POST /{id}/reprocess
# ---------------------------------------------------------------------------

_SCOREABLE_STATUSES = {CallStatus.transcribed, CallStatus.scoring, CallStatus.scored}


@router.post("/{call_id}/reprocess", response_model=CallOut)
async def reprocess_call_scores(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    rebind_rubric: bool = False,
) -> CallOut:
    """Re-run scoring for an already-transcribed call (idempotent).

    The scoring service handles idempotent cleanup of prior auto data
    internally. Manual coaching notes are preserved.

    Args:
        call_id: UUID of the call to reprocess.
        db: Database session.
        current_user: Authenticated user.
        rebind_rubric: If True, rebind to the currently active rubric before scoring.

    Returns:
        Updated CallOut reflecting the new scoring status.

    Raises:
        HTTPException 409: If the call status is not in a scoreable state.
    """
    call = await _get_call_or_404(call_id, db)

    if call.status not in _SCOREABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Call cannot be rescored in its current status",
        )

    await score_call(call_id, db=db, rebind_rubric=rebind_rubric)

    await db.refresh(call)
    return CallOut.from_orm_call(call)

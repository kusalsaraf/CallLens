"""Call processing pipeline: transcription, diarization, redaction, embedding, and persistence."""

import logging
import tempfile
import uuid
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.config import get_settings
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.db.session import get_session_factory
from calllens.embeddings.factory import get_embedder
from calllens.redaction.factory import get_redactor
from calllens.services.call_events import publish_call_event
from calllens.storage.factory import get_storage
from calllens.transcription.base import MergedSegment
from calllens.transcription.factory import get_diarizer, get_transcriber
from calllens.transcription.merge import merge

logger = logging.getLogger(__name__)


async def _set_status(
    db: AsyncSession,
    call: Call,
    status: CallStatus,
    detail: str | None = None,
) -> None:
    call.status = status
    call.status_detail = detail
    await db.commit()
    await db.refresh(call)
    try:
        await publish_call_event(call.id, status.value, detail)
    except Exception:
        logger.warning(
            "Failed to publish call event", extra={"call_id": str(call.id), "status": status.value}
        )


async def _redact_segments(db: AsyncSession, transcript: Transcript) -> None:
    """Run PII/PCI redaction on all segments; failures leave redacted_text = raw.

    Resilient: a redaction error per-segment is logged and the segment's
    redacted_text is set to its raw text — never fails the pipeline.

    Args:
        db: Active database session.
        transcript: Transcript whose segments to redact.
    """
    settings = get_settings()
    if not settings.redaction_enabled:
        return

    try:
        redactor = get_redactor()
    except Exception:
        logger.exception("Failed to initialise redactor — skipping redaction")
        return

    result = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.sequence)
    )
    segments = list(result.scalars().all())
    if not segments:
        return

    entity_counter: Counter[str] = Counter()

    for seg in segments:
        try:
            redaction = redactor.redact(seg.text)
            seg.redacted_text = redaction["redacted_text"]
            for ent in redaction["entities"]:
                entity_counter[ent["type"]] += 1
        except Exception:
            logger.exception(
                "Redaction failed for segment — using raw text",
                extra={"segment_id": str(seg.id)},
            )
            seg.redacted_text = seg.text

    transcript.redaction_provider = settings.redaction_provider
    transcript.entities_redacted = dict(entity_counter) if entity_counter else None

    await db.flush()
    logger.info(
        "Redacted %d segments (%d entities found)",
        len(segments),
        sum(entity_counter.values()),
        extra={"transcript_id": str(transcript.id)},
    )


async def _embed_segments(db: AsyncSession, transcript_id: uuid.UUID) -> None:
    """Embed all segments of a transcript; failures are logged but never fatal.

    Args:
        db: Active database session.
        transcript_id: UUID of the transcript whose segments to embed.
    """
    try:
        result = await db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript_id)
            .order_by(TranscriptSegment.sequence)
        )
        segments = list(result.scalars().all())
        if not segments:
            return

        embedder = get_embedder()
        texts = [seg.text for seg in segments]
        vectors = await embedder.embed_texts(texts)

        for seg, vec in zip(segments, vectors, strict=True):
            seg.embedding = vec

        await db.flush()
        logger.info(
            "Embedded %d segments",
            len(segments),
            extra={"transcript_id": str(transcript_id)},
        )
    except Exception:
        logger.exception(
            "Embedding failed — segments left with null embeddings",
            extra={"transcript_id": str(transcript_id)},
        )


async def run_call_pipeline(call_id: uuid.UUID) -> None:
    """Run the full transcription and diarization pipeline for a call.

    Loads the call from the database, runs transcription followed by diarization,
    merges the results, persists Transcript and TranscriptSegment rows, and
    updates the call status at each stage. On any error, sets status to failed
    and records the exception message in status_detail.

    Args:
        call_id: UUID of the Call row to process.
    """
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(Call).where(Call.id == call_id))
        call = result.scalar_one_or_none()
        if call is None:
            logger.error("Pipeline called with unknown call_id", extra={"call_id": str(call_id)})
            return

        try:
            await _set_status(db, call, CallStatus.transcribing)

            storage = get_storage()
            audio_bytes: list[bytes] = []
            async for chunk in storage.open_stream(call.storage_key):
                audio_bytes.append(chunk)
            raw_audio = b"".join(audio_bytes)

            suffix = Path(call.storage_key).suffix or ".audio"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                tf.write(raw_audio)
                audio_path = Path(tf.name)

            try:
                transcriber = get_transcriber()
                transcript_segments = await transcriber.transcribe(audio_path)

                await _set_status(db, call, CallStatus.diarizing)

                diarizer = get_diarizer()
                diarization_turns = await diarizer.diarize(audio_path)
            finally:
                audio_path.unlink(missing_ok=True)

            merged = merge(transcript_segments, diarization_turns)

            transcript = Transcript(call_id=call.id, language=None)
            db.add(transcript)
            await db.flush()

            item: MergedSegment
            for item in merged:
                seg = TranscriptSegment(
                    transcript_id=transcript.id,
                    sequence=int(item["sequence"]),
                    start_ms=int(item["start_ms"]),
                    end_ms=int(item["end_ms"]),
                    text=str(item["text"]),
                    speaker=str(item["speaker"]),
                )
                db.add(seg)

            await db.flush()

            await _redact_segments(db, transcript)

            # NOTE: embedding currently uses raw seg.text — embedding-of-redacted-text
            # is a future toggle (Phase 9B or later).
            await _embed_segments(db, transcript.id)

            await _set_status(db, call, CallStatus.transcribed)

            # Trigger scoring phase within the same session.
            # score_call handles its own errors (sets failed status internally).
            await _set_status(db, call, CallStatus.scoring)
            from calllens.services.scoring_service import score_call

            await score_call(call.id, db=db)

            logger.info("Pipeline complete", extra={"call_id": str(call_id)})

        except Exception as exc:
            logger.exception("Pipeline failed", extra={"call_id": str(call_id)})
            try:
                await _set_status(db, call, CallStatus.failed, detail=str(exc))
            except Exception:
                logger.exception(
                    "Failed to update call status to failed",
                    extra={"call_id": str(call_id)},
                )

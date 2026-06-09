"""Idempotent CLI to backfill redacted_text on segments missing it.

Usage::

    python -m calllens.redaction.backfill          # default batch=100
    python -m calllens.redaction.backfill --batch 500
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from calllens.core.config import get_settings
from calllens.core.logging import configure_logging
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.db.session import get_session_factory
from calllens.redaction.factory import get_redactor

logger = logging.getLogger(__name__)


async def backfill_redaction(
    batch_size: int = 100,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Redact all segments that currently have null redacted_text.

    Processes in batches of *batch_size*, commits after each batch.
    Also updates the parent Transcript's entities_redacted summary.
    Idempotent: a second run with no null redacted_text is a no-op.

    Args:
        batch_size: Number of segments to process per batch.
        session_factory: Optional override for the DB session factory (tests).

    Returns:
        Total number of segments redacted.
    """
    settings = get_settings()
    if not settings.redaction_enabled:
        logger.info("Redaction is disabled — nothing to backfill")
        return 0

    redactor = get_redactor()
    factory = session_factory or get_session_factory()
    total = 0
    transcript_ids_touched: set[str] = set()

    while True:
        async with factory() as db:
            result = await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.redacted_text.is_(None))
                .limit(batch_size)
            )
            segments = list(result.scalars().all())

            if not segments:
                break

            for seg in segments:
                try:
                    redaction = redactor.redact(seg.text)
                    seg.redacted_text = redaction["redacted_text"]
                except Exception:
                    logger.exception(
                        "Redaction failed for segment — using raw text",
                        extra={"segment_id": str(seg.id)},
                    )
                    seg.redacted_text = seg.text

                transcript_ids_touched.add(str(seg.transcript_id))

            for seg in segments:
                await db.merge(seg)
            await db.commit()

            total += len(segments)
            logger.info("Backfilled batch", extra={"batch": len(segments), "total": total})

    # Update transcript summaries for all touched transcripts
    if transcript_ids_touched:
        async with factory() as db:
            for tid_str in transcript_ids_touched:
                await _update_transcript_summary(db, tid_str, redactor, settings.redaction_provider)
            await db.commit()

    logger.info("Redaction backfill complete", extra={"total_redacted": total})
    return total


async def _update_transcript_summary(
    db: AsyncSession,
    transcript_id_str: str,
    redactor: object,
    provider: str,
) -> None:
    """Recompute entities_redacted summary for a transcript.

    Args:
        db: Active database session.
        transcript_id_str: String UUID of the transcript.
        redactor: The configured redactor instance.
        provider: The redaction provider name.
    """
    import uuid

    tid = uuid.UUID(transcript_id_str)
    transcript = (
        await db.execute(
            select(Transcript)
            .where(Transcript.id == tid)
            .options(selectinload(Transcript.segments))
        )
    ).scalar_one_or_none()
    if transcript is None:
        return

    entity_counter: Counter[str] = Counter()
    from calllens.redaction.base import Redactor as RedactorProto

    assert isinstance(redactor, RedactorProto)
    for seg in transcript.segments:
        if seg.text and seg.redacted_text and seg.text != seg.redacted_text:
            result = redactor.redact(seg.text)
            for ent in result["entities"]:
                entity_counter[ent["type"]] += 1

    transcript.redaction_provider = provider
    transcript.entities_redacted = dict(entity_counter) if entity_counter else None


def main() -> None:
    """CLI entry point for the redaction backfill command."""
    parser = argparse.ArgumentParser(description="Backfill null segment redacted_text")
    parser.add_argument("--batch", type=int, default=100, help="Batch size (default 100)")
    args = parser.parse_args()

    configure_logging()
    logger.info("Starting redaction backfill", extra={"batch_size": args.batch})

    total = asyncio.run(backfill_redaction(args.batch))

    if total == 0:
        print("No segments with null redacted_text — nothing to do.")  # noqa: T201
    else:
        print(f"Redacted {total} segment(s).")  # noqa: T201


if __name__ == "__main__":
    main()

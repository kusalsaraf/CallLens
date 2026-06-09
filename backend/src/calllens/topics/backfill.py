"""Idempotent backfill CLI for topic extraction on existing calls."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.topic import CallTopic, Topic
from calllens.db.models.transcript import Transcript
from calllens.db.session import get_session_factory
from calllens.topics.base import TaxonomyEntry
from calllens.topics.factory import get_topic_extractor

logger = logging.getLogger(__name__)


async def backfill_topics(
    *,
    batch_size: int = 50,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Extract and assign topics for calls that have no CallTopic rows.

    Idempotent: calls with existing topics are skipped.

    Args:
        batch_size: Process this many calls per iteration.
        session_factory: Optional session factory (for tests).

    Returns:
        Number of calls processed.
    """
    factory = session_factory or get_session_factory()
    extractor = get_topic_extractor()
    total = 0

    async with factory() as db:
        topics = list((await db.execute(select(Topic))).scalars().all())

    if not topics:
        logger.warning("No topics in taxonomy — run seed first")
        return 0

    taxonomy: list[TaxonomyEntry] = [
        TaxonomyEntry(slug=t.slug, name=t.name, keywords=t.keywords) for t in topics
    ]
    slug_to_id = {t.slug: t.id for t in topics}

    while True:
        async with factory() as db:
            has_topics = select(CallTopic.call_id).distinct()
            stmt = (
                select(Call.id)
                .where(
                    Call.status.in_([CallStatus.scored, CallStatus.transcribed]),
                    Call.id.notin_(has_topics),
                )
                .limit(batch_size)
            )
            call_ids = list((await db.execute(stmt)).scalars().all())

            if not call_ids:
                break

            for call_id in call_ids:
                t_result = await db.execute(select(Transcript).where(Transcript.call_id == call_id))
                transcript = t_result.scalar_one_or_none()
                if transcript is None:
                    continue

                seg_result = await db.execute(
                    select(TranscriptSegment.text)
                    .where(TranscriptSegment.transcript_id == transcript.id)
                    .order_by(TranscriptSegment.sequence)
                )
                full_text = " ".join(row[0] for row in seg_result.all())
                if not full_text.strip():
                    continue

                try:
                    matches = await extractor.extract(full_text, taxonomy)
                except Exception:
                    logger.exception("Topic extraction failed for call %s", call_id)
                    continue

                for m in matches:
                    topic_id = slug_to_id.get(m["topic_slug"])
                    if topic_id is None:
                        continue
                    db.add(
                        CallTopic(
                            call_id=call_id,
                            topic_id=topic_id,
                            relevance=m["relevance"],
                        )
                    )

                total += 1

            await db.commit()

    logger.info("Backfilled topics for %d calls", total)
    return total


async def _main() -> None:
    """Run topic backfill as a standalone async task."""
    total = await backfill_topics()
    print(f"Backfilled {total} calls")  # noqa: T201


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())

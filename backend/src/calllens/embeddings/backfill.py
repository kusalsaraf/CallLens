"""Idempotent CLI to backfill null segment embeddings.

Usage::

    python -m calllens.embeddings.backfill          # default batch=100
    python -m calllens.embeddings.backfill --batch 500
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from calllens.core.logging import configure_logging
from calllens.db.models.segment import TranscriptSegment
from calllens.db.session import get_session_factory
from calllens.embeddings.factory import get_embedder

logger = logging.getLogger(__name__)


async def backfill_embeddings(
    batch_size: int = 100,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """Embed all segments that currently have a null embedding.

    Processes in batches of *batch_size*, commits after each batch.
    Idempotent: a second run with no null embeddings is a no-op.

    Args:
        batch_size: Number of segments to embed per batch.
        session_factory: Optional override for the DB session factory (tests).

    Returns:
        Total number of segments embedded.
    """
    embedder = get_embedder()
    factory = session_factory or get_session_factory()
    total = 0

    while True:
        async with factory() as db:
            result = await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.embedding.is_(None))
                .limit(batch_size)
            )
            segments = list(result.scalars().all())

            if not segments:
                break

            texts = [seg.text for seg in segments]
            vectors = await embedder.embed_texts(texts)

            for seg, vec in zip(segments, vectors, strict=True):
                seg.embedding = vec

            await _update_segments(db, segments)
            total += len(segments)
            logger.info("Backfilled batch", extra={"batch": len(segments), "total": total})

    logger.info("Backfill complete", extra={"total_embedded": total})
    return total


async def _update_segments(db: AsyncSession, segments: list[TranscriptSegment]) -> None:
    """Merge updated segments back into the session and commit.

    Args:
        db: Active database session.
        segments: Segments with newly-set embeddings.
    """
    for seg in segments:
        await db.merge(seg)
    await db.commit()


async def _count_null() -> int:
    """Return the count of segments with null embeddings."""
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(func.count())
            .select_from(TranscriptSegment)
            .where(TranscriptSegment.embedding.is_(None))
        )
        return result.scalar_one()


def main() -> None:
    """CLI entry point for the backfill command."""
    parser = argparse.ArgumentParser(description="Backfill null segment embeddings")
    parser.add_argument("--batch", type=int, default=100, help="Batch size (default 100)")
    args = parser.parse_args()

    configure_logging()
    logger.info("Starting embedding backfill", extra={"batch_size": args.batch})

    total = asyncio.run(backfill_embeddings(args.batch))

    if total == 0:
        print("No segments with null embeddings — nothing to do.")  # noqa: T201
    else:
        print(f"Backfilled {total} segment(s).")  # noqa: T201


if __name__ == "__main__":
    main()

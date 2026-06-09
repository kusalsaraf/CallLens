"""Transcript-direct import CLI for public call-center datasets.

Ingests CSV or JSON transcript files — many public datasets have transcripts
only, no audio — by creating Call + Transcript + segments directly, then
running the rest of the pipeline (scoring, redaction, topics, embeddings).

Usage::

    python -m calllens.seed.import_transcripts data/transcripts.csv
    python -m calllens.seed.import_transcripts data/transcripts.json \\
        --text-col dialogue --speaker-col role --id-col conversation_id

**Public dataset sources** (user must download the file):

- Kaggle: "Customer Support Ticket Dataset", "Call Center Dataset"
- HuggingFace: various customer-service conversation datasets

Supported formats:

- **CSV**: one row per turn (columns: id/call_id, speaker, text) or one row
  per call (column: text/transcript containing the full dialogue).
- **JSON / JSONL**: array of objects, or one object per line.

Column names are configurable via ``--text-col``, ``--speaker-col``, etc.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import select

from calllens.db.models.agent import Agent
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.db.session import get_session_factory
from calllens.seed.rubric import seed_default_rubric
from calllens.seed.topics import seed_topics
from calllens.services.call_pipeline import (
    _embed_segments,
    _extract_topics,
    _redact_segments,
)
from calllens.services.scoring_service import score_call

logger = logging.getLogger(__name__)


def _load_file(path: Path) -> list[dict[str, Any]]:
    """Load a CSV or JSON file into a list of dicts.

    Args:
        path: Path to the input file.

    Returns:
        List of row dicts.

    Raises:
        ValueError: If the file format is unsupported.
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    elif suffix in (".json", ".jsonl"):
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
            if content.startswith("["):
                return json.loads(content)  # type: ignore[no-any-return]
            return [json.loads(line) for line in content.splitlines() if line.strip()]
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use .csv, .json, or .jsonl")


def _group_rows(
    rows: list[dict[str, Any]],
    *,
    id_col: str,
    text_col: str,
    speaker_col: str,
) -> dict[str, list[dict[str, str]]]:
    """Group rows by call/conversation ID.

    If id_col is missing from a row, each row becomes its own call.

    Args:
        rows: List of row dicts.
        id_col: Column name for call/conversation grouping.
        text_col: Column name for the text content.
        speaker_col: Column name for the speaker role.

    Returns:
        Mapping of call_id → list of turn dicts.
    """
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)

    for i, row in enumerate(rows):
        text = row.get(text_col, "")
        if not text or not str(text).strip():
            continue

        call_id = str(row.get(id_col, f"row-{i}"))
        speaker = str(row.get(speaker_col, "agent" if i % 2 == 0 else "customer")).lower()
        if speaker not in ("agent", "customer"):
            speaker = "agent" if "agent" in speaker else "customer"

        groups[call_id].append({"speaker": speaker, "text": str(text).strip()})

    return dict(groups)


async def import_transcripts(
    path: Path,
    *,
    text_col: str = "text",
    speaker_col: str = "speaker",
    id_col: str = "call_id",
) -> dict[str, Any]:
    """Import a transcript dataset file into CallLens.

    Args:
        path: Path to the CSV/JSON file.
        text_col: Column name for text content.
        speaker_col: Column name for speaker role.
        id_col: Column name for call/conversation grouping.

    Returns:
        Summary dict with counts.
    """
    rows = _load_file(path)
    logger.info("Loaded %d rows from %s", len(rows), path)

    groups = _group_rows(rows, id_col=id_col, text_col=text_col, speaker_col=speaker_col)
    logger.info("Grouped into %d calls", len(groups))

    factory = get_session_factory()
    async with factory() as db:
        rubric = await seed_default_rubric(db)
        await seed_topics(db)

        result = await db.execute(select(Agent).limit(1))
        agent = result.scalar_one_or_none()
        if agent is None:
            logger.error("No agent found — run seed_defaults first")
            return {"created": 0, "skipped": 0, "errors": 0}

        created = 0
        skipped = 0
        errors = 0

        for call_key, turns in groups.items():
            try:
                if not turns:
                    skipped += 1
                    continue

                call = Call(
                    storage_key=f"import/{uuid.uuid4().hex}.mp3",
                    original_filename=f"import-{call_key}.txt",
                    agent_id=agent.id,
                    rubric_id=rubric.id,
                    is_demo=True,
                    status=CallStatus.uploaded,
                )
                db.add(call)
                await db.flush()

                transcript = Transcript(call_id=call.id)
                db.add(transcript)
                await db.flush()

                wps = 2.5
                current_ms = 0
                for seq, turn in enumerate(turns):
                    word_count = len(turn["text"].split())
                    duration_ms = int((word_count / wps) * 1000)
                    seg = TranscriptSegment(
                        transcript_id=transcript.id,
                        sequence=seq,
                        speaker=turn["speaker"],
                        text=turn["text"],
                        start_ms=current_ms,
                        end_ms=current_ms + duration_ms,
                    )
                    db.add(seg)
                    current_ms += duration_ms + 400

                call.duration_seconds = current_ms / 1000.0
                await db.commit()

                t_result = await db.execute(select(Transcript).where(Transcript.call_id == call.id))
                tx = t_result.scalar_one()
                await _redact_segments(db, tx)
                await _embed_segments(db, tx.id)

                call.status = CallStatus.transcribed
                await db.commit()

                await score_call(call.id, db=db)
                await _extract_topics(db, call)
                await db.commit()

                created += 1
                logger.info("Imported call %d: %s (%d turns)", created, call_key, len(turns))

            except Exception:
                logger.exception("Failed to import call %s — skipping", call_key)
                errors += 1
                await db.rollback()

    return {"created": created, "skipped": skipped, "errors": errors}


def main() -> None:
    """CLI entrypoint for transcript import."""
    parser = argparse.ArgumentParser(description="Import a transcript dataset into CallLens")
    parser.add_argument("file", type=Path, help="Path to CSV/JSON transcript file")
    parser.add_argument("--text-col", default="text", help="Column name for text content")
    parser.add_argument("--speaker-col", default="speaker", help="Column name for speaker role")
    parser.add_argument("--id-col", default="call_id", help="Column name for call grouping")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if not args.file.exists():
        print(f"Error: file not found: {args.file}")
        return

    summary = asyncio.run(
        import_transcripts(
            args.file,
            text_col=args.text_col,
            speaker_col=args.speaker_col,
            id_col=args.id_col,
        )
    )

    print("\nImport complete:")
    print(f"  Calls created: {summary['created']}")
    print(f"  Rows skipped: {summary['skipped']}")
    print(f"  Errors: {summary['errors']}")


if __name__ == "__main__":
    main()

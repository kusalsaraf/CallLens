"""Demo data seeder CLI.

Creates realistic, PII-safe demo calls so the deployed app opens with
populated analytics. All calls are marked ``is_demo=True`` for safe reset.

Usage::

    # Default: inject transcripts directly, no audio (fully offline)
    python -m calllens.seed.demo --count 16

    # With synthesized audio (requires edge-tts + pydub + ffmpeg)
    python -m calllens.seed.demo --count 16 --audio

    # Reset demo data and reseed
    python -m calllens.seed.demo --reset --count 16
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import uuid
from collections import Counter
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from calllens.db.models.agent import Agent
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.team import Team
from calllens.db.models.topic import CallTopic
from calllens.db.models.transcript import Transcript
from calllens.db.session import get_session_factory
from calllens.seed.rubric import seed_default_rubric
from calllens.seed.scenarios import AGENTS, SCENARIOS, TEAMS, Scenario
from calllens.seed.topics import seed_topics
from calllens.services.call_pipeline import (
    _embed_segments,
    _extract_topics,
    _redact_segments,
)
from calllens.services.scoring_service import score_call
from calllens.storage.factory import get_storage

logger = logging.getLogger(__name__)


async def _ensure_teams_agents(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Ensure all scenario teams and agents exist. Returns agent name → id map.

    Args:
        db: Active database session.

    Returns:
        Mapping of agent name to agent UUID.
    """
    team_map: dict[str, uuid.UUID] = {}
    for team_name in TEAMS:
        result = await db.execute(select(Team).where(Team.name == team_name))
        team = result.scalar_one_or_none()
        if team is None:
            team = Team(name=team_name)
            db.add(team)
            await db.flush()
        team_map[team_name] = team.id

    agent_map: dict[str, uuid.UUID] = {}
    for agent_name, team_name in AGENTS.items():
        agent_result = await db.execute(select(Agent).where(Agent.name == agent_name))
        agent = agent_result.scalar_one_or_none()
        if agent is None:
            agent = Agent(name=agent_name, team_id=team_map[team_name])
            db.add(agent)
            await db.flush()
        agent_map[agent_name] = agent.id

    await db.commit()
    return agent_map


async def _count_demo_calls(db: AsyncSession) -> int:
    """Count existing demo calls.

    Args:
        db: Active database session.

    Returns:
        Number of calls with is_demo=True.
    """
    result = await db.execute(select(func.count()).select_from(Call).where(Call.is_demo.is_(True)))
    return result.scalar_one()


async def _reset_demo_data(db: AsyncSession) -> int:
    """Delete all demo calls and their related data.

    Deletes only calls with ``is_demo=True``. Cascades handle scores,
    analysis, agent-runs, coaching notes, and call-topics. Transcripts
    and segments are cleaned up explicitly.

    Also removes stored audio files for demo calls.

    Args:
        db: Active database session.

    Returns:
        Number of demo calls deleted.
    """
    result = await db.execute(
        select(Call).where(Call.is_demo.is_(True)).options(selectinload(Call.transcript))
    )
    demo_calls = list(result.scalars().all())
    if not demo_calls:
        return 0

    storage = get_storage()
    for call in demo_calls:
        try:
            if await storage.exists(call.storage_key):
                await storage.delete(call.storage_key)
        except Exception:
            logger.warning("Failed to delete storage for demo call %s", call.id)

        if call.transcript:
            await db.execute(
                sa_delete(TranscriptSegment).where(
                    TranscriptSegment.transcript_id == call.transcript.id
                )
            )
            await db.execute(sa_delete(Transcript).where(Transcript.call_id == call.id))

        await db.execute(sa_delete(CallTopic).where(CallTopic.call_id == call.id))

    call_ids = [c.id for c in demo_calls]
    await db.execute(sa_delete(Call).where(Call.id.in_(call_ids)))
    await db.commit()

    logger.info("Deleted %d demo calls", len(demo_calls))
    return len(demo_calls)


async def _inject_transcript_only(
    db: AsyncSession,
    scenario: Scenario,
    call: Call,
) -> Transcript:
    """Create Transcript + TranscriptSegment rows directly from a script.

    Calculates synthetic timing by estimating ~120 words per minute.

    Args:
        db: Active database session.
        scenario: The scenario with turns to inject.
        call: The Call ORM row to attach the transcript to.

    Returns:
        The created Transcript row.
    """
    transcript = Transcript(call_id=call.id)
    db.add(transcript)
    await db.flush()

    words_per_second = 2.5  # ~150 WPM
    current_ms = 0

    for i, turn in enumerate(scenario["turns"]):
        word_count = len(turn["text"].split())
        duration_ms = int((word_count / words_per_second) * 1000)

        seg = TranscriptSegment(
            transcript_id=transcript.id,
            sequence=i,
            speaker=turn["speaker"],
            text=turn["text"],
            start_ms=current_ms,
            end_ms=current_ms + duration_ms,
        )
        db.add(seg)
        current_ms += duration_ms + 400  # 400ms gap between turns

    call.duration_seconds = current_ms / 1000.0
    await db.flush()

    return transcript


async def _process_seeded_call(db: AsyncSession, call: Call) -> None:
    """Run the post-transcription pipeline steps on a seeded call.

    Steps: redaction → embedding → score → topics. Each step is
    resilient — failures are logged but don't abort the seeder.

    Args:
        db: Active database session.
        call: The Call row to process.
    """
    t_result = await db.execute(select(Transcript).where(Transcript.call_id == call.id))
    transcript = t_result.scalar_one_or_none()

    if transcript:
        await _redact_segments(db, transcript)
        await _embed_segments(db, transcript.id)

    call.status = CallStatus.transcribed
    await db.commit()

    await score_call(call.id, db=db)
    await _extract_topics(db, call)
    await db.commit()


async def seed_demo(
    count: int = 16,
    *,
    reset: bool = False,
    audio: bool = False,
) -> dict[str, Any]:
    """Seed demo calls from the scenario library.

    Args:
        count: Number of demo calls to create (cycles scenarios).
        reset: If True, delete existing demo data first.
        audio: If True, synthesize audio via edge-tts + pydub.

    Returns:
        Summary dict with counts and statistics.
    """
    factory = get_session_factory()
    async with factory() as db:
        rubric = await seed_default_rubric(db)
        await seed_topics(db)

        if reset:
            deleted = await _reset_demo_data(db)
            logger.info("Reset: deleted %d demo calls", deleted)

        existing = await _count_demo_calls(db)
        if existing >= count and not reset:
            logger.info(
                "Demo data already seeded (%d calls exist, %d requested) — skipping",
                existing,
                count,
            )
            return {"created": 0, "existing": existing, "skipped": True}

        needed = count - (0 if reset else existing)
        agent_map = await _ensure_teams_agents(db)

        created = 0
        for i in range(needed):
            scenario = SCENARIOS[i % len(SCENARIOS)]
            agent_id = agent_map[scenario["agent"]]

            storage_key = f"demo/{uuid.uuid4().hex}.mp3"

            if audio:
                from calllens.seed.tts import synthesize_call

                audio_bytes = await synthesize_call(scenario["turns"])
                storage = get_storage()
                storage_key = await storage.save(audio_bytes, storage_key)

            call = Call(
                storage_key=storage_key,
                original_filename=f"demo-{scenario['id']}.mp3",
                agent_id=agent_id,
                rubric_id=rubric.id,
                is_demo=True,
                status=CallStatus.uploaded,
            )
            db.add(call)
            await db.flush()

            if not audio:
                await _inject_transcript_only(db, scenario, call)
            await db.commit()

            await _process_seeded_call(db, call)
            created += 1
            logger.info(
                "Seeded demo call %d/%d: %s",
                created,
                needed,
                scenario["title"],
            )

    async with factory() as db:
        summary = await _build_summary(db)

    summary["created"] = created
    return summary


async def _build_summary(db: AsyncSession) -> dict[str, Any]:
    """Build a summary of demo data statistics.

    Args:
        db: Active database session.

    Returns:
        Summary dict with band spread, flagged count, topics covered.
    """
    result = await db.execute(select(Call).where(Call.is_demo.is_(True)))
    demo_calls = list(result.scalars().all())

    band_counter: Counter[str] = Counter()
    flagged = 0
    for call in demo_calls:
        analysis_result = await db.execute(
            select(CallAnalysis).where(CallAnalysis.call_id == call.id)
        )
        analysis = analysis_result.scalar_one_or_none()
        if analysis and analysis.overall_score is not None:
            raw = float(analysis.overall_score)
            if raw >= 80:
                band_counter["quality"] += 1
            elif raw >= 60:
                band_counter["at-risk"] += 1
            else:
                band_counter["fail"] += 1
            if raw < 60:
                flagged += 1

    topic_result = await db.execute(
        select(func.count(func.distinct(CallTopic.topic_id))).where(
            CallTopic.call_id.in_([c.id for c in demo_calls])
        )
    )
    topics_covered = topic_result.scalar_one()

    return {
        "total": len(demo_calls),
        "bands": dict(band_counter),
        "flagged": flagged,
        "topics_covered": topics_covered,
    }


def main() -> None:
    """CLI entrypoint for the demo seeder."""
    parser = argparse.ArgumentParser(description="Seed demo data for CallLens")
    parser.add_argument("--count", type=int, default=16, help="Number of demo calls to create")
    parser.add_argument("--reset", action="store_true", help="Delete existing demo data first")
    parser.add_argument("--audio", action="store_true", help="Synthesize audio via edge-tts")
    parser.add_argument("--no-audio", action="store_true", help="Skip audio (default)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    use_audio = args.audio and not args.no_audio
    summary = asyncio.run(seed_demo(count=args.count, reset=args.reset, audio=use_audio))

    if summary.get("skipped"):
        print(f"Demo data already seeded ({summary['existing']} calls). Use --reset to reseed.")
        return

    print(f"\n{'=' * 50}")
    print("Demo seeding complete!")
    print(f"  Calls created: {summary['created']}")
    print(f"  Total demo calls: {summary['total']}")
    print(f"  Band spread: {summary.get('bands', {})}")
    print(f"  Flagged calls: {summary.get('flagged', 0)}")
    print(f"  Topics covered: {summary.get('topics_covered', 0)}")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()

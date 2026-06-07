"""Tests for POST /api/v1/calls/{call_id}/reprocess."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from calllens.db.models.call import Call, CallStatus
from calllens.db.models.scoring import CallScore
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.seed.rubric import seed_default_rubric
from calllens.services.scoring_service import score_call


async def _create_transcribed_call(factory: async_sessionmaker) -> uuid.UUID:
    """Seed rubric, create a Call with transcript + segments, return call_id.

    Args:
        factory: Async session factory bound to the test DB.

    Returns:
        UUID of the newly created transcribed Call.
    """
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
            original_filename="test_call.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.flush()

        transcript = Transcript(id=uuid.uuid4(), call_id=call_id, language="en")
        db.add(transcript)
        await db.flush()

        for i, (speaker, text) in enumerate(
            [
                ("agent", "Thank you for calling, how may I help you today?"),
                ("customer", "I need help with my account balance please."),
                ("agent", "I understand, I will look into that for you right away."),
            ]
        ):
            seg = TranscriptSegment(
                id=uuid.uuid4(),
                transcript_id=transcript.id,
                sequence=i,
                start_ms=i * 2000,
                end_ms=(i + 1) * 2000,
                text=text,
                speaker=speaker,
            )
            db.add(seg)
        await db.commit()

    return call_id


async def _create_uploaded_call(factory: async_sessionmaker) -> uuid.UUID:
    """Create a Call in 'uploaded' status (no transcript) and return call_id.

    Args:
        factory: Async session factory bound to the test DB.

    Returns:
        UUID of the uploaded Call.
    """
    from calllens.services.seed import get_default_agent

    async with factory() as db:
        await seed_default_rubric(db)
        agent = await get_default_agent(db)

    call_id = uuid.uuid4()
    async with factory() as db:
        call = Call(
            id=call_id,
            status=CallStatus.uploaded,
            storage_key=f"{call_id}.wav",
            original_filename="uploaded_call.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.commit()

    return call_id


@pytest_asyncio.fixture
async def reprocess_setup(
    client: AsyncClient, auth_token: str, db_engine: object
) -> tuple[uuid.UUID, str]:
    """Create a scored call ready for reprocessing.

    Args:
        client: Test HTTP client.
        auth_token: Bearer token.
        db_engine: Test DB engine.

    Returns:
        Tuple of (call_id, auth_token).
    """
    factory = async_sessionmaker(
        bind=db_engine,  # type: ignore[call-arg]
        expire_on_commit=False,
        class_=AsyncSession,
    )
    call_id = await _create_transcribed_call(factory)

    with patch(
        "calllens.services.scoring_service.publish_call_event",
        new_callable=AsyncMock,
    ):
        async with factory() as db:
            await score_call(call_id, db=db)

    return call_id, auth_token


@pytest_asyncio.fixture
async def uploaded_call_setup(
    client: AsyncClient, auth_token: str, db_engine: object
) -> tuple[uuid.UUID, str]:
    """Create a call in 'uploaded' status for the 409 test.

    Args:
        client: Test HTTP client.
        auth_token: Bearer token.
        db_engine: Test DB engine.

    Returns:
        Tuple of (call_id, auth_token).
    """
    factory = async_sessionmaker(
        bind=db_engine,  # type: ignore[call-arg]
        expire_on_commit=False,
        class_=AsyncSession,
    )
    call_id = await _create_uploaded_call(factory)
    return call_id, auth_token


# ---------------------------------------------------------------------------
# Test 1: reprocess replaces old scores with fresh ones
# ---------------------------------------------------------------------------


async def test_reprocess_replaces_scores(
    client: AsyncClient,
    reprocess_setup: tuple[uuid.UUID, str],
    db_engine: object,
) -> None:
    """POST /reprocess deletes old CallScore and creates a new one."""
    call_id, token = reprocess_setup

    factory = async_sessionmaker(
        bind=db_engine,  # type: ignore[call-arg]
        expire_on_commit=False,
        class_=AsyncSession,
    )

    # Record the original score id.
    async with factory() as db:
        result = await db.execute(select(CallScore).where(CallScore.call_id == call_id))
        original_scores = result.scalars().all()
    assert len(original_scores) == 1
    original_score_id = original_scores[0].id

    # Reprocess.
    with (
        patch(
            "calllens.services.scoring_service.publish_call_event",
            new_callable=AsyncMock,
        ),
        patch(
            "calllens.services.call_pipeline.publish_call_event",
            new_callable=AsyncMock,
        ),
    ):
        resp = await client.post(
            f"/api/v1/calls/{call_id}/reprocess",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200, resp.text

    # Verify exactly one score exists and it is a new row.
    async with factory() as db:
        result = await db.execute(select(CallScore).where(CallScore.call_id == call_id))
        new_scores = result.scalars().all()

    assert len(new_scores) == 1, f"Expected 1 score, got {len(new_scores)}"
    assert new_scores[0].id != original_score_id, "Score id should change after reprocess"


# ---------------------------------------------------------------------------
# Test 2: uploaded call returns 409
# ---------------------------------------------------------------------------


async def test_reprocess_uploaded_call_returns_409(
    client: AsyncClient,
    uploaded_call_setup: tuple[uuid.UUID, str],
) -> None:
    """POST /reprocess on an 'uploaded' call returns 409 Conflict."""
    call_id, token = uploaded_call_setup

    resp = await client.post(
        f"/api/v1/calls/{call_id}/reprocess",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Test 3: auth required
# ---------------------------------------------------------------------------


async def test_reprocess_requires_auth(
    client: AsyncClient,
    reprocess_setup: tuple[uuid.UUID, str],
) -> None:
    """POST /reprocess without a token returns 401 or 403."""
    call_id, _token = reprocess_setup

    resp = await client.post(f"/api/v1/calls/{call_id}/reprocess")
    assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

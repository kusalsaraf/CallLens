"""Tests for GET /api/v1/calls/{call_id}/scores."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from calllens.db.models.call import Call, CallStatus
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
                ("agent", "Thank you for calling, how can I help you today?"),
                ("customer", "I have a billing problem I need resolved."),
                ("agent", "I completely understand your frustration, let me help."),
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


@pytest_asyncio.fixture
async def scored_call_setup(
    client: AsyncClient, auth_token: str, db_engine: object
) -> tuple[uuid.UUID, str]:
    """Create a fully scored call in the test DB and return (call_id, auth_token).

    The fixture reuses db_engine so the scored data lives in the same underlying
    database that the test client's session override targets.

    Args:
        client: The test HTTP client (ensures the DB is initialised via its fixture).
        auth_token: Bearer token for the signed-up test user.
        db_engine: SQLAlchemy async engine pointing at the test database.

    Returns:
        Tuple of (call UUID, bearer token string).
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


# ---------------------------------------------------------------------------
# Test 1: correct JSON shape
# ---------------------------------------------------------------------------


async def test_get_scores_correct_shape(
    client: AsyncClient, scored_call_setup: tuple[uuid.UUID, str]
) -> None:
    """GET /{call_id}/scores returns {call_id, scores: [...]} with the right keys."""
    call_id, token = scored_call_setup

    resp = await client.get(
        f"/api/v1/calls/{call_id}/scores",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "call_id" in body
    assert "scores" in body
    assert str(call_id) == body["call_id"]
    assert isinstance(body["scores"], list)
    assert len(body["scores"]) >= 1

    first = body["scores"][0]
    for key in (
        "id",
        "dimension",
        "score",
        "confidence",
        "rationale",
        "is_supported",
        "scored_at",
        "evidence",
    ):
        assert key in first, f"Missing key {key!r} in score object"


# ---------------------------------------------------------------------------
# Test 2: evidence items have the right shape
# ---------------------------------------------------------------------------


async def test_scores_have_evidence(
    client: AsyncClient, scored_call_setup: tuple[uuid.UUID, str]
) -> None:
    """Each score entry contains an evidence list with segment_id and quote fields."""
    call_id, token = scored_call_setup

    resp = await client.get(
        f"/api/v1/calls/{call_id}/scores",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    scores = resp.json()["scores"]
    assert scores, "Expected at least one score"

    for score_obj in scores:
        evidence = score_obj["evidence"]
        assert isinstance(evidence, list)
        for ev in evidence:
            assert "segment_id" in ev
            assert "quote" in ev
            assert isinstance(ev["quote"], str)


# ---------------------------------------------------------------------------
# Test 3: auth required
# ---------------------------------------------------------------------------


async def test_get_scores_requires_auth(
    client: AsyncClient, scored_call_setup: tuple[uuid.UUID, str]
) -> None:
    """GET /{call_id}/scores without a token returns 401 or 403."""
    call_id, _token = scored_call_setup

    resp = await client.get(f"/api/v1/calls/{call_id}/scores")
    assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Test 4: unknown call returns 404
# ---------------------------------------------------------------------------


async def test_get_scores_not_found(client: AsyncClient, auth_token: str) -> None:
    """GET /nonexistent-uuid/scores returns 404."""
    fake_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/calls/{fake_id}/scores",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 404, resp.text

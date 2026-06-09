"""Tests for Phase 7A: segment embeddings and semantic search.

Covers:
- StubEmbedder: determinism, correct dim, L2-normalised
- backfill: embeds null-embedding segments, idempotent
- search: exact-text ranked first, grouped by call, snippets + similarity,
  null-embedding exclusion, agent/date filters, empty q rejected, 401
- pipeline: segments get embeddings after transcription, embedding error
  does not fail the call
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from calllens.db.models.agent import Agent
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.team import Team
from calllens.db.models.transcript import Transcript
from calllens.embeddings.stub import StubEmbedder

# ---------------------------------------------------------------------------
# StubEmbedder unit tests
# ---------------------------------------------------------------------------


class TestStubEmbedder:
    """StubEmbedder must be deterministic, correct-dim, and L2-normalised."""

    async def test_deterministic_same_text(self) -> None:
        """Same text always yields the same vector."""
        embedder = StubEmbedder()
        v1 = await embedder.embed_query("hello world")
        v2 = await embedder.embed_query("hello world")
        assert v1 == v2

    async def test_deterministic_normalised_text(self) -> None:
        """Leading/trailing whitespace and case don't matter."""
        embedder = StubEmbedder()
        v1 = await embedder.embed_query("Hello World")
        v2 = await embedder.embed_query("  hello world  ")
        assert v1 == v2

    async def test_different_text_different_vector(self) -> None:
        """Different texts produce different vectors."""
        embedder = StubEmbedder()
        v1 = await embedder.embed_query("hello world")
        v2 = await embedder.embed_query("goodbye world")
        assert v1 != v2

    async def test_correct_dimension(self) -> None:
        """Output vector has exactly EMBEDDING_DIM elements."""
        embedder = StubEmbedder()
        v = await embedder.embed_query("test text")
        assert len(v) == 384

    async def test_l2_normalised(self) -> None:
        """Output vector has L2 norm ≈ 1.0."""
        embedder = StubEmbedder()
        v = await embedder.embed_query("some test string")
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-6

    async def test_embed_texts_batch(self) -> None:
        """embed_texts returns correct number of vectors."""
        embedder = StubEmbedder()
        texts = ["alpha", "beta", "gamma"]
        vecs = await embedder.embed_texts(texts)
        assert len(vecs) == 3
        for v in vecs:
            assert len(v) == 384

    async def test_embed_query_matches_embed_texts(self) -> None:
        """embed_query and embed_texts produce the same vector for the same text."""
        embedder = StubEmbedder()
        single = await embedder.embed_query("test")
        batch = await embedder.embed_texts(["test"])
        assert single == batch[0]


# ---------------------------------------------------------------------------
# Fixture: calls with embedded/non-embedded segments for search tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def search_dataset(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Create 2 calls with segments; one with embeddings, one partially without.

    call_1 (agent Alpha, team T1, june 1): 2 segments, both embedded
    call_2 (agent Beta, team T2, june 8): 2 segments, seg_3 embedded, seg_4 null
    """
    team1 = Team(name="T1")
    team2 = Team(name="T2")
    db.add_all([team1, team2])
    await db.flush()

    agent_alpha = Agent(name="Alpha", team_id=team1.id)
    agent_beta = Agent(name="Beta", team_id=team2.id)
    db.add_all([agent_alpha, agent_beta])
    await db.flush()

    june_1 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    june_8 = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)

    call1 = Call(
        status=CallStatus.scored,
        storage_key="test/c1.wav",
        original_filename="c1.wav",
        agent_id=agent_alpha.id,
        created_at=june_1,
    )
    call2 = Call(
        status=CallStatus.scored,
        storage_key="test/c2.wav",
        original_filename="c2.wav",
        agent_id=agent_beta.id,
        created_at=june_8,
    )
    db.add_all([call1, call2])
    await db.flush()

    analysis1 = CallAnalysis(
        call_id=call1.id,
        overall_score=85,
        summary="Good call",
        key_moments=[],
        action_items=[],
        compliance_passed=True,
        escalate_for_review=False,
    )
    analysis2 = CallAnalysis(
        call_id=call2.id,
        overall_score=55,
        summary="Needs improvement",
        key_moments=[],
        action_items=[],
        compliance_passed=False,
        escalate_for_review=True,
    )
    db.add_all([analysis1, analysis2])
    await db.flush()

    t1 = Transcript(call_id=call1.id, language="en")
    t2 = Transcript(call_id=call2.id, language="en")
    db.add_all([t1, t2])
    await db.flush()

    embedder = StubEmbedder()

    seg1_text = "Thank you for calling support how can I help you today"
    seg2_text = "I understand your frustration let me help you resolve this"
    seg3_text = "The billing department can assist with refund requests"
    seg4_text = "Is there anything else I can help you with"

    vecs = await embedder.embed_texts([seg1_text, seg2_text, seg3_text])

    seg1 = TranscriptSegment(
        transcript_id=t1.id,
        sequence=0,
        start_ms=0,
        end_ms=3000,
        text=seg1_text,
        speaker="agent",
        embedding=vecs[0],
    )
    seg2 = TranscriptSegment(
        transcript_id=t1.id,
        sequence=1,
        start_ms=3000,
        end_ms=6000,
        text=seg2_text,
        speaker="customer",
        embedding=vecs[1],
    )
    seg3 = TranscriptSegment(
        transcript_id=t2.id,
        sequence=0,
        start_ms=0,
        end_ms=3000,
        text=seg3_text,
        speaker="agent",
        embedding=vecs[2],
    )
    seg4 = TranscriptSegment(
        transcript_id=t2.id,
        sequence=1,
        start_ms=3000,
        end_ms=6000,
        text=seg4_text,
        speaker="agent",
        embedding=None,
    )
    db.add_all([seg1, seg2, seg3, seg4])
    await db.commit()

    return {
        "call1_id": call1.id,
        "call2_id": call2.id,
        "seg1_id": seg1.id,
        "seg2_id": seg2.id,
        "seg3_id": seg3.id,
        "seg4_id": seg4.id,
        "agent_alpha_id": agent_alpha.id,
        "agent_beta_id": agent_beta.id,
        "team1_id": team1.id,
        "team2_id": team2.id,
        "seg1_text": seg1_text,
        "seg4_text": seg4_text,
    }


# ---------------------------------------------------------------------------
# Search API tests
# ---------------------------------------------------------------------------


async def test_search_exact_text_ranked_first(
    client: AsyncClient,
    auth_token: str,
    search_dataset: dict[str, uuid.UUID],
) -> None:
    """Querying a segment's exact text should rank that call/segment first."""
    seg1_text = search_dataset["seg1_text"]
    resp = await client.get(
        "/api/v1/search",
        params={"q": seg1_text},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    top_result = data["results"][0]
    assert top_result["call_id"] == str(search_dataset["call1_id"])
    top_snippet = top_result["snippets"][0]
    assert top_snippet["segment_id"] == str(search_dataset["seg1_id"])
    assert top_snippet["similarity"] > 0.99


async def test_search_grouped_by_call_with_metadata(
    client: AsyncClient,
    auth_token: str,
    search_dataset: dict[str, uuid.UUID],
) -> None:
    """Results are grouped by call with expected metadata fields."""
    resp = await client.get(
        "/api/v1/search",
        params={"q": "support help", "limit": 10},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    for hit in data["results"]:
        assert "call_id" in hit
        assert "agent_name" in hit
        assert "overall_score" in hit
        assert "band" in hit
        assert "uploaded_at" in hit
        assert len(hit["snippets"]) >= 1
        for snippet in hit["snippets"]:
            assert "segment_id" in snippet
            assert "start_ms" in snippet
            assert "text" in snippet
            assert "similarity" in snippet
            assert -1.0 <= snippet["similarity"] <= 1.0


async def test_search_null_embeddings_excluded(
    client: AsyncClient,
    auth_token: str,
    search_dataset: dict[str, uuid.UUID],
) -> None:
    """Segments with null embeddings (seg4) must never appear in results."""
    seg4_text = search_dataset["seg4_text"]
    resp = await client.get(
        "/api/v1/search",
        params={"q": seg4_text, "limit": 100},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    all_seg_ids = [s["segment_id"] for hit in data["results"] for s in hit["snippets"]]
    assert str(search_dataset["seg4_id"]) not in all_seg_ids


async def test_search_filter_by_agent(
    client: AsyncClient,
    auth_token: str,
    search_dataset: dict[str, uuid.UUID],
) -> None:
    """Filtering by agent_id narrows results to that agent's calls."""
    resp = await client.get(
        "/api/v1/search",
        params={"q": "help", "agent_id": str(search_dataset["agent_alpha_id"])},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for hit in data["results"]:
        assert hit["call_id"] == str(search_dataset["call1_id"])


async def test_search_filter_by_date(
    client: AsyncClient,
    auth_token: str,
    search_dataset: dict[str, uuid.UUID],
) -> None:
    """Filtering by date range narrows results."""
    resp = await client.get(
        "/api/v1/search",
        params={
            "q": "help",
            "date_from": "2026-06-05T00:00:00Z",
            "date_to": "2026-06-10T00:00:00Z",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for hit in data["results"]:
        assert hit["call_id"] in [
            str(search_dataset["call1_id"]),
            str(search_dataset["call2_id"]),
        ]

    # Narrow date to exclude call1 (june 1)
    resp2 = await client.get(
        "/api/v1/search",
        params={"q": "help", "date_from": "2026-06-05T00:00:00Z"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    call_ids = [h["call_id"] for h in data2["results"]]
    assert str(search_dataset["call1_id"]) not in call_ids


async def test_search_empty_query_rejected(
    client: AsyncClient,
    auth_token: str,
) -> None:
    """Empty or whitespace-only query should return 422."""
    for q in ["", "   ", "\t\n"]:
        resp = await client.get(
            "/api/v1/search",
            params={"q": q},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 422


async def test_search_401_without_token(client: AsyncClient) -> None:
    """Search without auth token returns 401."""
    resp = await client.get("/api/v1/search", params={"q": "test"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Backfill tests
# ---------------------------------------------------------------------------


async def test_backfill_embeds_null_segments(db_engine: object) -> None:
    """Backfill should embed segments with null embeddings."""
    from calllens.embeddings.backfill import backfill_embeddings

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )

    async with factory() as db:
        team = Team(name="BF Team")
        db.add(team)
        await db.flush()
        agent = Agent(name="BF Agent", team_id=team.id)
        db.add(agent)
        await db.flush()
        call = Call(
            status=CallStatus.transcribed,
            storage_key="test/bf.wav",
            original_filename="bf.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.flush()
        t = Transcript(call_id=call.id, language="en")
        db.add(t)
        await db.flush()
        for i in range(3):
            seg = TranscriptSegment(
                transcript_id=t.id,
                sequence=i,
                start_ms=i * 1000,
                end_ms=(i + 1) * 1000,
                text=f"Segment {i} text",
                speaker="agent",
                embedding=None,
            )
            db.add(seg)
        await db.commit()
        transcript_id = t.id

    total = await backfill_embeddings(batch_size=2, session_factory=factory)
    assert total == 3

    async with factory() as db:
        result = await db.execute(
            select(TranscriptSegment).where(TranscriptSegment.transcript_id == transcript_id)
        )
        for seg in result.scalars().all():
            assert seg.embedding is not None
            assert len(list(seg.embedding)) == 384


async def test_backfill_idempotent(db_engine: object) -> None:
    """A second backfill run when no null embeddings exist is a no-op."""
    from calllens.embeddings.backfill import backfill_embeddings

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )

    embedder = StubEmbedder()
    async with factory() as db:
        team = Team(name="Idem Team")
        db.add(team)
        await db.flush()
        agent = Agent(name="Idem Agent", team_id=team.id)
        db.add(agent)
        await db.flush()
        call = Call(
            status=CallStatus.scored,
            storage_key="test/idem.wav",
            original_filename="idem.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.flush()
        t = Transcript(call_id=call.id, language="en")
        db.add(t)
        await db.flush()
        vec = await embedder.embed_query("already embedded")
        seg = TranscriptSegment(
            transcript_id=t.id,
            sequence=0,
            start_ms=0,
            end_ms=1000,
            text="already embedded",
            speaker="agent",
            embedding=vec,
        )
        db.add(seg)
        await db.commit()

    total = await backfill_embeddings(batch_size=10, session_factory=factory)
    assert total == 0


# ---------------------------------------------------------------------------
# Pipeline embedding tests
# ---------------------------------------------------------------------------


async def test_pipeline_embeds_segments(db_engine: object) -> None:
    """After transcription in the pipeline, segments should have embeddings."""
    from calllens.services.call_pipeline import _embed_segments

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )

    async with factory() as db:
        team = Team(name="Pipe Team")
        db.add(team)
        await db.flush()
        agent = Agent(name="Pipe Agent", team_id=team.id)
        db.add(agent)
        await db.flush()
        call = Call(
            status=CallStatus.transcribing,
            storage_key="test/pipe.wav",
            original_filename="pipe.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.flush()
        t = Transcript(call_id=call.id, language="en")
        db.add(t)
        await db.flush()

        for i in range(2):
            seg = TranscriptSegment(
                transcript_id=t.id,
                sequence=i,
                start_ms=i * 1000,
                end_ms=(i + 1) * 1000,
                text=f"Pipeline segment {i}",
                speaker="agent",
            )
            db.add(seg)
        await db.flush()
        transcript_id = t.id

        await _embed_segments(db, transcript_id)
        await db.commit()

    async with factory() as db:
        result = await db.execute(
            select(TranscriptSegment).where(TranscriptSegment.transcript_id == transcript_id)
        )
        for seg in result.scalars().all():
            assert seg.embedding is not None


async def test_pipeline_embedding_error_does_not_fail_call(db_engine: object) -> None:
    """An embedding error should be logged but not fail the pipeline."""
    from calllens.services.call_pipeline import _embed_segments

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )

    async with factory() as db:
        team = Team(name="Err Team")
        db.add(team)
        await db.flush()
        agent = Agent(name="Err Agent", team_id=team.id)
        db.add(agent)
        await db.flush()
        call = Call(
            status=CallStatus.transcribing,
            storage_key="test/err.wav",
            original_filename="err.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.flush()
        t = Transcript(call_id=call.id, language="en")
        db.add(t)
        await db.flush()
        seg = TranscriptSegment(
            transcript_id=t.id,
            sequence=0,
            start_ms=0,
            end_ms=1000,
            text="Error test segment",
            speaker="agent",
        )
        db.add(seg)
        await db.flush()
        transcript_id = t.id

        with patch(
            "calllens.services.call_pipeline.get_embedder",
        ) as mock_factory:
            mock_embedder = AsyncMock()
            mock_embedder.embed_texts.side_effect = RuntimeError("Model crashed")
            mock_factory.return_value = mock_embedder

            await _embed_segments(db, transcript_id)

        await db.commit()

    async with factory() as db:
        result = await db.execute(
            select(TranscriptSegment).where(TranscriptSegment.transcript_id == transcript_id)
        )
        seg = result.scalar_one()
        assert seg.embedding is None


# ---------------------------------------------------------------------------
# Redacted snippet tests (Phase 9B)
# ---------------------------------------------------------------------------


async def test_search_snippet_prefers_redacted_text(
    client: AsyncClient,
    auth_token: str,
    search_dataset: dict[str, uuid.UUID],
    db: AsyncSession,
) -> None:
    """When a segment has redacted_text, the search snippet should use it."""
    seg1_id = search_dataset["seg1_id"]

    # Set redacted_text on seg1 (simulating post-redaction state)
    result = await db.execute(select(TranscriptSegment).where(TranscriptSegment.id == seg1_id))
    seg = result.scalar_one()
    seg.redacted_text = "Thank you for calling support how can I help you today [REDACTED_EMAIL]"
    await db.commit()

    seg1_text = search_dataset["seg1_text"]
    resp = await client.get(
        "/api/v1/search",
        params={"q": seg1_text},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1

    top_snippet = data["results"][0]["snippets"][0]
    assert "[REDACTED_EMAIL]" in top_snippet["text"]
    assert top_snippet["segment_id"] == str(seg1_id)

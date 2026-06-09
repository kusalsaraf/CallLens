"""Tests for Phase 10A: topic/theme tracking — extraction, analytics, filtering.

Covers:
- StubKeywordExtractor: deterministic, threshold, normalised relevance
- Topic taxonomy seed: idempotent
- Pipeline: assigns CallTopic rows, reprocess replaces, extractor error resilient
- Backfill: idempotent
- /analytics/topics: correct per-topic stats, honours filters
- topic_id filter on /calls and analytics endpoints (no regressions without it)
- /topics + /topics/{id}: taxonomy + stats; auth-guarded
- Call analysis includes topics
"""

from __future__ import annotations

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
from calllens.db.models.topic import CallTopic, Topic
from calllens.db.models.transcript import Transcript
from calllens.seed.topics import seed_topics
from calllens.topics.base import TaxonomyEntry
from calllens.topics.stub import StubKeywordExtractor

# ---------------------------------------------------------------------------
# StubKeywordExtractor unit tests
# ---------------------------------------------------------------------------


class TestStubKeywordExtractor:
    """StubKeywordExtractor must be deterministic, threshold-aware, and normalised."""

    async def test_billing_keywords_match(self) -> None:
        """A transcript with billing keywords returns billing_dispute above threshold."""
        extractor = StubKeywordExtractor()
        taxonomy: list[TaxonomyEntry] = [
            TaxonomyEntry(
                slug="billing_dispute",
                name="Billing Dispute",
                keywords=["billing", "charge", "overcharge", "invoice", "bill", "fee", "charged"],
            ),
            TaxonomyEntry(
                slug="technical_issue",
                name="Technical Issue",
                keywords=["technical", "error", "bug", "not working", "broken", "outage", "crash"],
            ),
        ]
        text = "I was charged twice on my billing statement and the fee is wrong."
        matches = await extractor.extract(text, taxonomy)

        slugs = [m["topic_slug"] for m in matches]
        assert "billing_dispute" in slugs
        assert "technical_issue" not in slugs

    async def test_relevance_normalised(self) -> None:
        """Relevance should be hits/len(keywords), in [0, 1]."""
        extractor = StubKeywordExtractor()
        taxonomy: list[TaxonomyEntry] = [
            TaxonomyEntry(
                slug="test_topic",
                name="Test",
                keywords=["alpha", "beta", "gamma", "delta"],
            ),
        ]
        text = "alpha and beta are here"
        matches = await extractor.extract(text, taxonomy)
        assert len(matches) == 1
        assert matches[0]["relevance"] == 0.5  # 2/4

    async def test_threshold_excludes_low(self) -> None:
        """Topics below the configured threshold are excluded."""
        extractor = StubKeywordExtractor()
        taxonomy: list[TaxonomyEntry] = [
            TaxonomyEntry(
                slug="barely",
                name="Barely",
                keywords=[
                    "xylophone",
                    "yacht",
                    "zebra",
                    "asteroid",
                    "brontosaurus",
                    "chrysanthemum",
                    "dinosaur",
                    "elephant",
                    "flamingo",
                    "giraffe",
                ],
            ),
        ]
        # Only "xylophone" present → relevance 0.1, at the threshold (default 0.1)
        text = "I play the xylophone every day"
        matches = await extractor.extract(text, taxonomy)
        assert len(matches) == 1

        # Nothing matching → empty
        text2 = "absolutely nothing relevant here at all"
        matches2 = await extractor.extract(text2, taxonomy)
        assert matches2 == []

    async def test_deterministic(self) -> None:
        """Same input always produces same output."""
        extractor = StubKeywordExtractor()
        taxonomy: list[TaxonomyEntry] = [
            TaxonomyEntry(slug="a", name="A", keywords=["hello", "world"]),
        ]
        m1 = await extractor.extract("hello world", taxonomy)
        m2 = await extractor.extract("hello world", taxonomy)
        assert m1 == m2


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------


async def test_seed_topics_idempotent(db: AsyncSession) -> None:
    """Running seed_topics twice must not duplicate rows."""
    topics1 = await seed_topics(db)
    count1 = len(topics1)
    assert count1 == 10

    topics2 = await seed_topics(db)
    count2 = len(topics2)
    assert count2 == count1


# ---------------------------------------------------------------------------
# Topic fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def topic_dataset(db: AsyncSession) -> dict[str, object]:
    """Create topics, calls with analyses, and assign topics to calls.

    call_1 (scored 85) -> billing_dispute (0.8), cancellation_churn_risk (0.5)
    call_2 (scored 45) -> billing_dispute (0.6)
    call_3 (scored 70) -> technical_issue (0.9)
    """
    topics = await seed_topics(db)
    slug_map = {t.slug: t for t in topics}

    team = Team(name="Topic Team")
    db.add(team)
    await db.flush()

    agent = Agent(name="Topic Agent", team_id=team.id)
    db.add(agent)
    await db.flush()

    june1 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    june8 = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)

    c1 = Call(
        status=CallStatus.scored,
        storage_key="t/1.wav",
        original_filename="1.wav",
        agent_id=agent.id,
        created_at=june1,
    )
    c2 = Call(
        status=CallStatus.scored,
        storage_key="t/2.wav",
        original_filename="2.wav",
        agent_id=agent.id,
        created_at=june8,
    )
    c3 = Call(
        status=CallStatus.scored,
        storage_key="t/3.wav",
        original_filename="3.wav",
        agent_id=agent.id,
        created_at=june1,
    )
    db.add_all([c1, c2, c3])
    await db.flush()

    db.add_all(
        [
            CallAnalysis(
                call_id=c1.id,
                overall_score=85,
                summary="t",
                key_moments=[],
                action_items=[],
                compliance_passed=True,
                escalate_for_review=False,
            ),
            CallAnalysis(
                call_id=c2.id,
                overall_score=45,
                summary="t",
                key_moments=[],
                action_items=[],
                compliance_passed=False,
                escalate_for_review=True,
            ),
            CallAnalysis(
                call_id=c3.id,
                overall_score=70,
                summary="t",
                key_moments=[],
                action_items=[],
                compliance_passed=True,
                escalate_for_review=False,
            ),
        ]
    )
    await db.flush()

    billing = slug_map["billing_dispute"]
    cancel = slug_map["cancellation_churn_risk"]
    tech = slug_map["technical_issue"]

    db.add_all(
        [
            CallTopic(call_id=c1.id, topic_id=billing.id, relevance=0.8),
            CallTopic(call_id=c1.id, topic_id=cancel.id, relevance=0.5),
            CallTopic(call_id=c2.id, topic_id=billing.id, relevance=0.6),
            CallTopic(call_id=c3.id, topic_id=tech.id, relevance=0.9),
        ]
    )
    await db.commit()

    return {
        "team_id": team.id,
        "agent_id": agent.id,
        "call1_id": c1.id,
        "call2_id": c2.id,
        "call3_id": c3.id,
        "billing_id": billing.id,
        "cancel_id": cancel.id,
        "tech_id": tech.id,
    }


# ---------------------------------------------------------------------------
# Analytics /analytics/topics tests
# ---------------------------------------------------------------------------


async def test_analytics_topics_returns_per_topic_stats(
    client: AsyncClient,
    auth_token: str,
    topic_dataset: dict[str, object],
) -> None:
    """GET /analytics/topics returns correct per-topic stats."""
    resp = await client.get(
        "/api/v1/analytics/topics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    items = data["items"]

    by_slug = {i["slug"]: i for i in items}

    billing = by_slug["billing_dispute"]
    assert billing["call_count"] == 2
    assert billing["avg_overall_score"] is not None
    avg = billing["avg_overall_score"]
    assert 60.0 <= avg <= 70.0  # avg of 85 and 45 ≈ 65

    tech = by_slug["technical_issue"]
    assert tech["call_count"] == 1
    assert tech["avg_overall_score"] == 70.0


async def test_analytics_topics_honours_date_filter(
    client: AsyncClient,
    auth_token: str,
    topic_dataset: dict[str, object],
) -> None:
    """Topic analytics honours the date filter."""
    resp = await client.get(
        "/api/v1/analytics/topics",
        params={"date_from": "2026-06-05T00:00:00Z"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    by_slug = {i["slug"]: i for i in data["items"]}
    billing = by_slug.get("billing_dispute")
    assert billing is not None
    assert billing["call_count"] == 1  # only call_2 is june 8


# ---------------------------------------------------------------------------
# Topic filter on /calls
# ---------------------------------------------------------------------------


async def test_calls_topic_filter(
    client: AsyncClient,
    auth_token: str,
    topic_dataset: dict[str, object],
) -> None:
    """topic_id filter on /calls narrows results correctly."""
    tech_id = topic_dataset["tech_id"]
    resp = await client.get(
        "/api/v1/calls/",
        params={"topic_id": str(tech_id)},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(topic_dataset["call3_id"])


async def test_calls_without_topic_filter_returns_all(
    client: AsyncClient,
    auth_token: str,
    topic_dataset: dict[str, object],
) -> None:
    """Without topic_id, /calls returns all calls (no regression)."""
    resp = await client.get(
        "/api/v1/calls/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3


# ---------------------------------------------------------------------------
# Topic filter on analytics endpoints (no regressions)
# ---------------------------------------------------------------------------


async def test_overview_with_topic_filter(
    client: AsyncClient,
    auth_token: str,
    topic_dataset: dict[str, object],
) -> None:
    """Overview endpoint works with topic_id filter."""
    billing_id = topic_dataset["billing_id"]
    resp = await client.get(
        "/api/v1/analytics/overview",
        params={"topic_id": str(billing_id)},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["calls_scored"] == 2


async def test_overview_without_topic_filter(
    client: AsyncClient,
    auth_token: str,
    topic_dataset: dict[str, object],
) -> None:
    """Overview endpoint still works without topic_id (no regressions)."""
    resp = await client.get(
        "/api/v1/analytics/overview",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["calls_scored"] >= 3


# ---------------------------------------------------------------------------
# /topics CRUD
# ---------------------------------------------------------------------------


async def test_list_topics(
    client: AsyncClient,
    auth_token: str,
    topic_dataset: dict[str, object],
) -> None:
    """GET /topics returns the seeded taxonomy."""
    resp = await client.get(
        "/api/v1/topics/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 10
    slugs = {i["slug"] for i in data["items"]}
    assert "billing_dispute" in slugs
    assert "technical_issue" in slugs


async def test_get_topic_with_stats(
    client: AsyncClient,
    auth_token: str,
    topic_dataset: dict[str, object],
) -> None:
    """GET /topics/{id} returns topic with stats."""
    tech_id = topic_dataset["tech_id"]
    resp = await client.get(
        f"/api/v1/topics/{tech_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "technical_issue"
    assert data["call_count"] == 1
    assert data["avg_overall_score"] == 70.0


async def test_get_topic_404(
    client: AsyncClient,
    auth_token: str,
) -> None:
    """GET /topics/{id} returns 404 for unknown topic."""
    resp = await client.get(
        f"/api/v1/topics/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 404


async def test_topics_auth_guarded(client: AsyncClient) -> None:
    """Topics endpoints return 401 without token."""
    resp = await client.get("/api/v1/topics/")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Call analysis includes topics
# ---------------------------------------------------------------------------


async def test_analysis_includes_topics(
    client: AsyncClient,
    auth_token: str,
    topic_dataset: dict[str, object],
) -> None:
    """GET /calls/{id}/analysis includes topics array."""
    call1_id = topic_dataset["call1_id"]
    resp = await client.get(
        f"/api/v1/calls/{call1_id}/analysis",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    topics = data["topics"]
    assert len(topics) == 2
    slugs = [t["slug"] for t in topics]
    assert "billing_dispute" in slugs
    assert "cancellation_churn_risk" in slugs
    # Ordered by relevance desc
    assert topics[0]["relevance"] >= topics[1]["relevance"]


# ---------------------------------------------------------------------------
# Pipeline topic extraction
# ---------------------------------------------------------------------------


async def test_pipeline_assigns_topics(db_engine: object) -> None:
    """Pipeline _extract_topics assigns CallTopic rows."""
    from calllens.services.call_pipeline import _extract_topics

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )

    async with factory() as db:
        await seed_topics(db)

    async with factory() as db:
        team = Team(name="PipeTopic Team")
        db.add(team)
        await db.flush()
        agent = Agent(name="PipeTopic Agent", team_id=team.id)
        db.add(agent)
        await db.flush()
        call = Call(
            status=CallStatus.scored,
            storage_key="t/p.wav",
            original_filename="p.wav",
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
            end_ms=3000,
            text="I was charged twice and need a refund for the billing error",
            speaker="customer",
        )
        db.add(seg)
        await db.flush()
        call_id = call.id

        await _extract_topics(db, call)
        await db.commit()

    async with factory() as db:
        result = await db.execute(select(CallTopic).where(CallTopic.call_id == call_id))
        topics = list(result.scalars().all())
        assert len(topics) > 0
        slugs = set()
        for ct in topics:
            topic = (await db.execute(select(Topic).where(Topic.id == ct.topic_id))).scalar_one()
            slugs.add(topic.slug)
        assert "billing_dispute" in slugs or "refund_request" in slugs


async def test_pipeline_reprocess_replaces_topics(db_engine: object) -> None:
    """Reprocessing replaces prior topics."""
    from calllens.services.call_pipeline import _extract_topics

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )

    async with factory() as db:
        await seed_topics(db)

    async with factory() as db:
        team = Team(name="Reprocess Team")
        db.add(team)
        await db.flush()
        agent = Agent(name="Reprocess Agent", team_id=team.id)
        db.add(agent)
        await db.flush()
        call = Call(
            status=CallStatus.scored,
            storage_key="t/r.wav",
            original_filename="r.wav",
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
            end_ms=3000,
            text="billing charge error invoice fee",
            speaker="customer",
        )
        db.add(seg)
        await db.flush()
        call_ref = call
        call_id = call.id

        await _extract_topics(db, call_ref)
        await db.commit()

    async with factory() as db:
        r1 = await db.execute(select(CallTopic).where(CallTopic.call_id == call_id))
        count1 = len(list(r1.scalars().all()))
        assert count1 > 0

    # Change segment text and re-extract
    async with factory() as db:
        result = await db.execute(select(Call).where(Call.id == call_id))
        call_row = result.scalar_one()
        seg_result = await db.execute(
            select(TranscriptSegment).join(Transcript).where(Transcript.call_id == call_id)
        )
        seg_row = seg_result.scalar_one()
        seg_row.text = "delivery shipping tracking package shipment"
        await db.flush()

        await _extract_topics(db, call_row)
        await db.commit()

    async with factory() as db:
        r2 = await db.execute(
            select(CallTopic, Topic)
            .join(Topic, Topic.id == CallTopic.topic_id)
            .where(CallTopic.call_id == call_id)
        )
        rows = list(r2.all())
        slugs = {t.slug for _, t in rows}
        assert "delivery_shipping" in slugs


async def test_pipeline_extractor_error_does_not_fail(db_engine: object) -> None:
    """An extractor error should be logged but not fail the pipeline."""
    from calllens.services.call_pipeline import _extract_topics

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )

    async with factory() as db:
        await seed_topics(db)

    async with factory() as db:
        team = Team(name="Err Topic Team")
        db.add(team)
        await db.flush()
        agent = Agent(name="Err Topic Agent", team_id=team.id)
        db.add(agent)
        await db.flush()
        call = Call(
            status=CallStatus.scored,
            storage_key="t/e.wav",
            original_filename="e.wav",
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
            text="some text",
            speaker="agent",
        )
        db.add(seg)
        await db.flush()

        with patch(
            "calllens.services.call_pipeline.get_topic_extractor",
        ) as mock_factory:
            mock_extractor = AsyncMock()
            mock_extractor.extract.side_effect = RuntimeError("Extractor crashed")
            mock_factory.return_value = mock_extractor

            # Should NOT raise
            await _extract_topics(db, call)

        await db.commit()


# ---------------------------------------------------------------------------
# Backfill tests
# ---------------------------------------------------------------------------


async def test_backfill_topics_idempotent(db_engine: object) -> None:
    """Backfill runs on calls without topics; second run is no-op."""
    from calllens.topics.backfill import backfill_topics

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )

    async with factory() as db:
        await seed_topics(db)

    async with factory() as db:
        team = Team(name="BF Topic Team")
        db.add(team)
        await db.flush()
        agent = Agent(name="BF Topic Agent", team_id=team.id)
        db.add(agent)
        await db.flush()
        call = Call(
            status=CallStatus.scored,
            storage_key="t/bf.wav",
            original_filename="bf.wav",
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
            end_ms=3000,
            text="billing charge invoice refund money back",
            speaker="customer",
        )
        db.add(seg)
        await db.commit()
        call_id = call.id

    total1 = await backfill_topics(batch_size=10, session_factory=factory)
    assert total1 >= 1

    # Second run should be a no-op
    total2 = await backfill_topics(batch_size=10, session_factory=factory)
    assert total2 == 0

    async with factory() as db:
        result = await db.execute(select(CallTopic).where(CallTopic.call_id == call_id))
        assert len(list(result.scalars().all())) > 0

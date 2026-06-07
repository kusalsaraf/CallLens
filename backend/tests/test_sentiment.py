"""Tests for calllens.agents.sentiment.score_sentiment_empathy."""

from __future__ import annotations

import uuid

from calllens.agents.llm import AgentScore, StubLLMProvider, TranscriptSegmentData
from calllens.agents.sentiment import RubricDimensionData, score_sentiment_empathy


def _make_dimension() -> RubricDimensionData:
    """Return a minimal RubricDimensionData for sentiment_empathy."""
    return RubricDimensionData(
        id=uuid.uuid4(),
        key="sentiment_empathy",
        name="Sentiment & Empathy",
        weight=0.25,
    )


def _make_segments(
    agent_count: int = 2,
    customer_count: int = 2,
) -> list[TranscriptSegmentData]:
    """Build a mixed list of agent and customer transcript segments."""
    segments: list[TranscriptSegmentData] = []
    seq = 0
    for i in range(agent_count):
        segments.append(
            TranscriptSegmentData(
                id=uuid.uuid4(),
                sequence=seq,
                text=f"Agent segment {i}: I understand your concern and will help you right away.",
                speaker="agent",
            )
        )
        seq += 1
    for i in range(customer_count):
        segments.append(
            TranscriptSegmentData(
                id=uuid.uuid4(),
                sequence=seq,
                text=f"Customer segment {i}: I am really frustrated with this issue.",
                speaker="customer",
            )
        )
        seq += 1
    return segments


# ---------------------------------------------------------------------------
# Test 1: StubLLMProvider returns a valid AgentScore
# ---------------------------------------------------------------------------


async def test_stub_returns_valid_agent_score() -> None:
    """score_sentiment_empathy with StubLLMProvider returns a score in range."""
    segments = _make_segments()
    dimension = _make_dimension()

    result = await score_sentiment_empathy(segments, dimension)

    assert isinstance(result, AgentScore)
    assert 0 <= result.score <= 100
    assert 0.0 <= result.confidence <= 1.0
    assert result.is_supported is True
    assert len(result.evidence) >= 1


# ---------------------------------------------------------------------------
# Test 2: stub picks agent segments preferentially
# ---------------------------------------------------------------------------


async def test_stub_prefers_agent_segments() -> None:
    """Evidence should reference agent speaker segments, not customer segments."""
    agent_id = uuid.uuid4()
    customer_id_1 = uuid.uuid4()
    customer_id_2 = uuid.uuid4()

    segments: list[TranscriptSegmentData] = [
        TranscriptSegmentData(
            id=agent_id,
            sequence=0,
            text="I understand completely and will resolve this for you.",
            speaker="agent",
        ),
        TranscriptSegmentData(
            id=customer_id_1,
            sequence=1,
            text="I am very upset about the service.",
            speaker="customer",
        ),
        TranscriptSegmentData(
            id=customer_id_2,
            sequence=2,
            text="This is unacceptable!",
            speaker="customer",
        ),
    ]
    dimension = _make_dimension()

    result = await score_sentiment_empathy(segments, dimension)

    # All evidence should reference the agent segment only
    evidence_seg_ids = {ev.segment_id for ev in result.evidence}
    assert agent_id in evidence_seg_ids, "Stub should prefer agent segments for evidence"
    assert customer_id_1 not in evidence_seg_ids
    assert customer_id_2 not in evidence_seg_ids


# ---------------------------------------------------------------------------
# Test 3: evidence quotes are verbatim substrings of their segment
# ---------------------------------------------------------------------------


async def test_evidence_quotes_are_substrings_of_segment_text() -> None:
    """After scoring, every evidence quote must appear in the referenced segment text."""
    segments = _make_segments(agent_count=2, customer_count=1)
    dimension = _make_dimension()
    seg_map = {seg["id"]: seg for seg in segments}

    result = await score_sentiment_empathy(segments, dimension)

    for ev in result.evidence:
        seg = seg_map.get(ev.segment_id)
        assert seg is not None, f"Evidence references unknown segment {ev.segment_id}"
        assert ev.quote.lower() in seg["text"].lower(), (
            f"Quote {ev.quote!r} not found in segment text {seg['text']!r}"
        )


# ---------------------------------------------------------------------------
# Test 4: explicit provider override works identically to default
# ---------------------------------------------------------------------------


async def test_explicit_stub_provider_override() -> None:
    """Passing provider=StubLLMProvider() explicitly produces the same valid output."""
    segments = _make_segments()
    dimension = _make_dimension()
    provider = StubLLMProvider()

    result = await score_sentiment_empathy(segments, dimension, provider=provider)

    assert isinstance(result, AgentScore)
    assert 0 <= result.score <= 100
    assert 0.0 <= result.confidence <= 1.0
    assert result.is_supported is True

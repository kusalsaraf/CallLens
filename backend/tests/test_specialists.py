"""Tests for calllens.agents.specialists — all specialist agents."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from calllens.agents.llm import (
    AgentScore,
    StubLLMProvider,
    TimedTranscriptSegmentData,
)
from calllens.agents.metrics import ConversationMetrics
from calllens.agents.specialists import (
    FullRubricDimensionData,
    run_specialist,
    score_talk_listen,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _timed_seg(
    speaker: str,
    start_ms: int,
    end_ms: int,
    text: str,
    seq: int = 0,
) -> TimedTranscriptSegmentData:
    return TimedTranscriptSegmentData(
        id=uuid.uuid4(),
        sequence=seq,
        text=text,
        speaker=speaker,
        start_ms=start_ms,
        end_ms=end_ms,
    )


def _make_timed_segments() -> list[TimedTranscriptSegmentData]:
    """Build a representative 4-segment call transcript with timing."""
    return [
        _timed_seg(
            "agent",
            0,
            3000,
            "Hello, thank you for calling support. I understand your concern completely.",
            seq=0,
        ),
        _timed_seg(
            "customer",
            3500,
            6000,
            "I'm frustrated. This has been happening for weeks.",
            seq=1,
        ),
        _timed_seg(
            "agent",
            6500,
            10000,
            "I apologize for the inconvenience. Is there anything else I can help you with?",
            seq=2,
        ),
        _timed_seg(
            "customer",
            10500,
            12000,
            "No, I think that covers it.",
            seq=3,
        ),
    ]


def _dim(
    key: str,
    kind: str = "score",
    config: dict | None = None,  # type: ignore[type-arg]
    weight: float = 0.25,
) -> FullRubricDimensionData:
    return FullRubricDimensionData(
        id=uuid.uuid4(),
        key=key,
        name=key.replace("_", " ").title(),
        weight=weight,
        kind=kind,
        config=config,
    )


def _sample_metrics() -> ConversationMetrics:
    return ConversationMetrics(
        talk_listen_ratio=0.8,
        interruptions=1,
        longest_monologue_ms=3500,
        total_turns=4,
    )


# ---------------------------------------------------------------------------
# score_talk_listen (deterministic — no LLM)
# ---------------------------------------------------------------------------


class TestScoreTalkListen:
    def test_ideal_ratio_gives_high_score(self) -> None:
        """talk_listen_ratio == ideal -> maximum score."""
        metrics = ConversationMetrics(
            talk_listen_ratio=0.7,
            interruptions=0,
            longest_monologue_ms=1000,
            total_turns=2,
        )
        dim = _dim("talk_listen", kind="ratio")

        result = score_talk_listen(dim, metrics)

        assert result.score == 100
        assert result.confidence == pytest.approx(1.0)
        assert result.is_supported is True
        assert result.evidence == []

    def test_zero_ratio_gives_low_score(self) -> None:
        """talk_listen_ratio = 0.0 (agent never spoke) -> low score."""
        metrics = ConversationMetrics(
            talk_listen_ratio=0.0,
            interruptions=0,
            longest_monologue_ms=0,
            total_turns=1,
        )
        dim = _dim("talk_listen", kind="ratio")

        result = score_talk_listen(dim, metrics)

        assert result.score < 40

    def test_very_high_ratio_penalised(self) -> None:
        """Agent spoke 3x customer time -> score should be below 50."""
        metrics = ConversationMetrics(
            talk_listen_ratio=3.0,
            interruptions=0,
            longest_monologue_ms=5000,
            total_turns=2,
        )
        dim = _dim("talk_listen", kind="ratio")

        result = score_talk_listen(dim, metrics)

        assert result.score < 50


# ---------------------------------------------------------------------------
# run_specialist — LLM-scored dimensions (stub provider)
# ---------------------------------------------------------------------------


class TestRunSpecialistStub:
    async def test_sentiment_empathy_returns_valid_agent_score(self) -> None:
        """sentiment_empathy specialist returns a valid AgentScore on stub."""
        segs = _make_timed_segments()
        dim = _dim("sentiment_empathy", kind="score")
        provider = StubLLMProvider()

        result = await run_specialist(dim, segs, _sample_metrics(), provider=provider)

        assert isinstance(result, AgentScore)
        assert 0 <= result.score <= 100
        assert 0.0 <= result.confidence <= 1.0

    async def test_script_adherence_returns_valid_agent_score(self) -> None:
        """script_adherence specialist returns a valid AgentScore on stub."""
        segs = _make_timed_segments()
        dim = _dim("script_adherence", kind="score")
        provider = StubLLMProvider()

        result = await run_specialist(dim, segs, _sample_metrics(), provider=provider)

        assert isinstance(result, AgentScore)
        assert 0 <= result.score <= 100

    async def test_compliance_returns_valid_agent_score(self) -> None:
        """compliance specialist returns a valid AgentScore on stub."""
        segs = _make_timed_segments()
        config = {"required_phrases": ["I apologize", "Is there anything else"]}
        dim = _dim("compliance", kind="score", config=config)
        provider = StubLLMProvider()

        result = await run_specialist(dim, segs, _sample_metrics(), provider=provider)

        assert isinstance(result, AgentScore)
        assert 0 <= result.score <= 100

    async def test_objection_handling_returns_valid_agent_score(self) -> None:
        """objection_handling specialist returns a valid AgentScore on stub."""
        segs = _make_timed_segments()
        dim = _dim("objection_handling", kind="score")
        provider = StubLLMProvider()

        result = await run_specialist(dim, segs, _sample_metrics(), provider=provider)

        assert isinstance(result, AgentScore)
        assert 0 <= result.score <= 100

    async def test_talk_listen_dispatched_deterministically(self) -> None:
        """run_specialist with kind=ratio returns deterministic result (no LLM call)."""
        segs = _make_timed_segments()
        dim = _dim("talk_listen", kind="ratio")
        # Pass a broken provider to prove no LLM is called for ratio dims
        broken_provider = AsyncMock(spec=StubLLMProvider)
        broken_provider.structured_score.side_effect = RuntimeError("should not be called")

        result = await run_specialist(dim, segs, _sample_metrics(), provider=broken_provider)

        assert isinstance(result, AgentScore)
        broken_provider.structured_score.assert_not_called()

    async def test_evidence_quotes_are_real_segment_substrings(self) -> None:
        """All evidence quotes must be verbatim substrings of the referenced segment text."""
        segs = _make_timed_segments()
        seg_map: dict[uuid.UUID, TimedTranscriptSegmentData] = {s["id"]: s for s in segs}
        dim = _dim("sentiment_empathy", kind="score")
        provider = StubLLMProvider()

        result = await run_specialist(dim, segs, _sample_metrics(), provider=provider)

        for ev in result.evidence:
            seg = seg_map.get(ev.segment_id)
            assert seg is not None, f"Evidence references unknown segment {ev.segment_id}"
            assert ev.quote.lower() in seg["text"].lower(), (
                f"Quote {ev.quote!r} not found in {seg['text']!r}"
            )


# ---------------------------------------------------------------------------
# run_specialist — graceful degradation on provider error
# ---------------------------------------------------------------------------


class TestRunSpecialistErrorPath:
    async def test_provider_error_returns_low_confidence_unscored(self) -> None:
        """When provider.structured_score raises, returns low-confidence unscored result."""
        segs = _make_timed_segments()
        dim = _dim("sentiment_empathy", kind="score")

        failing_provider = AsyncMock(spec=StubLLMProvider)
        failing_provider.structured_score.side_effect = RuntimeError("LLM unavailable")

        result = await run_specialist(dim, segs, _sample_metrics(), provider=failing_provider)

        assert isinstance(result, AgentScore)
        assert result.is_supported is False
        assert result.confidence < 0.5
        assert result.score == 0

    async def test_provider_error_does_not_crash(self) -> None:
        """run_specialist never raises even when the provider raises."""
        segs = _make_timed_segments()
        dim = _dim("objection_handling", kind="score")

        failing_provider = AsyncMock(spec=StubLLMProvider)
        failing_provider.structured_score.side_effect = Exception("Network error")

        try:
            await run_specialist(dim, segs, _sample_metrics(), provider=failing_provider)
        except Exception as exc:
            pytest.fail(f"run_specialist raised unexpectedly: {exc}")

    async def test_unsupported_kind_returns_unscored(self) -> None:
        """Dimension with unknown kind returns an unscored result."""
        segs = _make_timed_segments()
        dim = _dim("some_future_dim", kind="vector_search")

        result = await run_specialist(dim, segs, _sample_metrics())

        assert isinstance(result, AgentScore)
        assert result.is_supported is False

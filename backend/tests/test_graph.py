"""Tests for calllens.agents.graph.run_scoring_graph."""

from __future__ import annotations

import uuid

from calllens.agents.graph import ScoringContext, run_scoring_graph
from calllens.agents.llm import AgentScore, TimedTranscriptSegmentData
from calllens.agents.metrics import ConversationMetrics
from calllens.agents.specialists import FullRubricDimensionData
from calllens.agents.supervisor import SupervisorResult

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


def _make_call_segments() -> list[TimedTranscriptSegmentData]:
    """A representative 6-segment call with agent and customer turns."""
    return [
        _timed_seg(
            "agent",
            0,
            3000,
            "Good afternoon, thank you for calling TechSupport. My name is Alex, "
            "how can I help you today?",
            seq=0,
        ),
        _timed_seg(
            "customer",
            3500,
            6000,
            "Hi, I've been having trouble with my account for the past three days.",
            seq=1,
        ),
        _timed_seg(
            "agent",
            6500,
            10500,
            "I understand, I apologize for the inconvenience. "
            "Let me verify your identity first. Could you confirm your email address?",
            seq=2,
        ),
        _timed_seg(
            "customer",
            11000,
            12500,
            "Sure, it's customer@example.com.",
            seq=3,
        ),
        _timed_seg(
            "agent",
            13000,
            17000,
            "Perfect, I've located your account. I can see the issue and have resolved it now. "
            "Is there anything else I can help you with today?",
            seq=4,
        ),
        _timed_seg(
            "customer",
            17500,
            18500,
            "No, that's great. Thank you!",
            seq=5,
        ),
    ]


def _make_full_dimensions() -> list[FullRubricDimensionData]:
    """All six default dimensions, matching the seed rubric."""
    return [
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="sentiment_empathy",
            name="Sentiment & Empathy",
            weight=0.25,
            kind="score",
            config=None,
        ),
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="script_adherence",
            name="Script Adherence",
            weight=0.20,
            kind="score",
            config=None,
        ),
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="compliance",
            name="Compliance",
            weight=0.20,
            kind="score",
            config={"required_phrases": ["I understand", "I apologize", "Is there anything else"]},
        ),
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="objection_handling",
            name="Objection Handling",
            weight=0.15,
            kind="score",
            config=None,
        ),
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="talk_listen",
            name="Talk/Listen Ratio",
            weight=0.10,
            kind="ratio",
            config=None,
        ),
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="outcome",
            name="Call Outcome",
            weight=0.10,
            kind="bool",
            config=None,
        ),
    ]


def _active_score_dims() -> list[FullRubricDimensionData]:
    """Only the LLM-scored dimensions (kind=score), for dimension filtering tests."""
    return [
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="sentiment_empathy",
            name="Sentiment & Empathy",
            weight=0.5,
            kind="score",
            config=None,
        ),
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="compliance",
            name="Compliance",
            weight=0.5,
            kind="score",
            config={"required_phrases": ["I understand"]},
        ),
    ]


# ---------------------------------------------------------------------------
# End-to-end graph tests
# ---------------------------------------------------------------------------


class TestRunScoringGraph:
    async def test_end_to_end_returns_scoring_result(self) -> None:
        """run_scoring_graph returns a complete ScoringResult on the stub provider."""
        context: ScoringContext = {
            "segments": _make_call_segments(),
            "dimensions": _make_full_dimensions(),
        }

        result = await run_scoring_graph(context)

        assert isinstance(result["metrics"], ConversationMetrics)
        assert isinstance(result["supervisor_result"], SupervisorResult)
        assert isinstance(result["dimension_scores"], dict)

    async def test_metrics_populated_from_segments(self) -> None:
        """ConversationMetrics in result reflects actual segment timing."""
        segs = _make_call_segments()
        context: ScoringContext = {
            "segments": segs,
            "dimensions": _make_full_dimensions(),
        }

        result = await run_scoring_graph(context)

        metrics = result["metrics"]
        assert metrics.total_turns >= 2
        assert metrics.talk_listen_ratio >= 0.0
        assert metrics.longest_monologue_ms > 0

    async def test_dimension_scores_keyed_by_dimension_key(self) -> None:
        """dimension_scores dict keys match dimension keys for active dimensions."""
        dims = _active_score_dims()
        context: ScoringContext = {
            "segments": _make_call_segments(),
            "dimensions": dims,
        }

        result = await run_scoring_graph(context)

        for dim in dims:
            assert dim["key"] in result["dimension_scores"], (
                f"Expected dimension_scores to contain key {dim['key']!r}"
            )

    async def test_parallel_specialist_writes_all_land(self) -> None:
        """All parallel specialist nodes write their scores without clobbering."""
        dims = _active_score_dims()  # 2 score dimensions
        context: ScoringContext = {
            "segments": _make_call_segments(),
            "dimensions": dims,
        }

        result = await run_scoring_graph(context)

        assert len(result["dimension_scores"]) == len(dims), (
            f"Expected {len(dims)} dimension scores, got {len(result['dimension_scores'])}"
        )

    async def test_bool_dimension_not_specialist_scored(self) -> None:
        """Dimensions with kind='bool' are NOT added to dimension_scores by a specialist."""
        dims = [
            FullRubricDimensionData(
                id=uuid.uuid4(),
                key="outcome",
                name="Call Outcome",
                weight=1.0,
                kind="bool",
                config=None,
            )
        ]
        context: ScoringContext = {
            "segments": _make_call_segments(),
            "dimensions": dims,
        }

        result = await run_scoring_graph(context)

        # The 'outcome' bool dim should NOT appear as a specialist-scored dimension
        assert "outcome" not in result["dimension_scores"]

    async def test_supervisor_result_has_required_fields(self) -> None:
        """SupervisorResult has non-empty summary, action_items, and coaching_note."""
        context: ScoringContext = {
            "segments": _make_call_segments(),
            "dimensions": _make_full_dimensions(),
        }

        result = await run_scoring_graph(context)
        sup = result["supervisor_result"]

        assert len(sup.summary) > 0
        assert len(sup.action_items) > 0
        assert len(sup.coaching_note) > 0
        assert 0 <= sup.overall_score <= 100

    async def test_key_moments_reference_real_segments(self) -> None:
        """All key_moment segment_ids must be actual segment IDs from the input."""
        segs = _make_call_segments()
        valid_ids = {s["id"] for s in segs}
        context: ScoringContext = {
            "segments": segs,
            "dimensions": _make_full_dimensions(),
        }

        result = await run_scoring_graph(context)
        sup = result["supervisor_result"]

        for moment in sup.key_moments:
            assert moment.segment_id in valid_ids, (
                f"key_moment.segment_id {moment.segment_id} is not a real segment ID"
            )

    async def test_each_dimension_score_in_range(self) -> None:
        """Every dimension score in dimension_scores is within [0, 100]."""
        context: ScoringContext = {
            "segments": _make_call_segments(),
            "dimensions": _make_full_dimensions(),
        }

        result = await run_scoring_graph(context)

        for key, score in result["dimension_scores"].items():
            assert 0 <= score.score <= 100, (
                f"dimension_scores[{key!r}].score = {score.score} is out of [0, 100]"
            )


# ---------------------------------------------------------------------------
# Escalation rule tests
# ---------------------------------------------------------------------------


class TestEscalationRule:
    async def test_escalation_fires_on_compliance_fail(self) -> None:
        """Escalation triggers when compliance dimension score is very low."""
        from calllens.agents.supervisor import run_supervisor

        segs = _make_call_segments()
        dims = [
            FullRubricDimensionData(
                id=uuid.uuid4(),
                key="compliance",
                name="Compliance",
                weight=1.0,
                kind="score",
                config=None,
            )
        ]
        # Simulate a compliance failure
        compliance_fail_score = AgentScore(
            score=30,  # below threshold of 50
            confidence=0.9,
            rationale="Required phrases not found.",
            evidence=[],
            is_supported=True,
        )
        dimension_scores = {"compliance": compliance_fail_score}

        result = await run_supervisor(
            dimension_scores=dimension_scores,
            dimensions=dims,
            segments=segs,
        )

        assert result.escalate_for_review is True
        assert result.escalation_reason is not None
        assert "compliance" in result.escalation_reason.lower()

    async def test_escalation_fires_on_low_overall_score(self) -> None:
        """Escalation triggers when overall score is below 60."""
        from calllens.agents.supervisor import run_supervisor

        segs = _make_call_segments()
        dims = [
            FullRubricDimensionData(
                id=uuid.uuid4(),
                key="sentiment_empathy",
                name="Sentiment",
                weight=1.0,
                kind="score",
                config=None,
            )
        ]
        low_score = AgentScore(
            score=40,  # overall will be ~40 -> below 60 threshold
            confidence=0.8,
            rationale="Poor sentiment.",
            evidence=[],
            is_supported=True,
        )

        result = await run_supervisor(
            dimension_scores={"sentiment_empathy": low_score},
            dimensions=dims,
            segments=segs,
        )

        assert result.escalate_for_review is True
        assert result.overall_score < 60

    async def test_no_escalation_on_clean_call(self) -> None:
        """No escalation when compliance passes and overall score is above threshold."""
        from calllens.agents.supervisor import run_supervisor

        segs = _make_call_segments()
        dims = [
            FullRubricDimensionData(
                id=uuid.uuid4(),
                key="compliance",
                name="Compliance",
                weight=0.5,
                kind="score",
                config=None,
            ),
            FullRubricDimensionData(
                id=uuid.uuid4(),
                key="sentiment_empathy",
                name="Sentiment",
                weight=0.5,
                kind="score",
                config=None,
            ),
        ]
        good_scores = {
            "compliance": AgentScore(
                score=90,
                confidence=0.9,
                rationale="All phrases present.",
                evidence=[],
                is_supported=True,
            ),
            "sentiment_empathy": AgentScore(
                score=80,
                confidence=0.85,
                rationale="Good empathy.",
                evidence=[],
                is_supported=True,
            ),
        }

        result = await run_supervisor(
            dimension_scores=good_scores,
            dimensions=dims,
            segments=segs,
        )

        assert result.escalate_for_review is False
        assert result.escalation_reason is None
        assert result.overall_score >= 60

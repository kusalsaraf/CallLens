"""Schema tests: band computed field on CallScoreOut; analysis schema roundtrip."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from calllens.schemas.calls import CallScoreOut, DimensionInfo, EvidenceOut


def _make_score(score: int) -> CallScoreOut:
    return CallScoreOut(
        id=uuid.uuid4(),
        dimension=DimensionInfo(
            id=uuid.uuid4(), key="sentiment_empathy", name="Sentiment", weight=0.25
        ),
        score=score,
        confidence=0.8,
        rationale="test",
        is_supported=True,
        scored_at=datetime.now(tz=timezone.utc),
        evidence=[],
    )


def test_band_excellent() -> None:
    assert _make_score(95).band == "excellent"


def test_band_good() -> None:
    assert _make_score(80).band == "good"


def test_band_fair() -> None:
    assert _make_score(55).band == "fair"


def test_band_poor() -> None:
    assert _make_score(30).band == "poor"


def test_analysis_schema_roundtrip() -> None:
    from calllens.schemas.analysis import CallAnalysisOut, KeyMomentOut

    seg_id = uuid.uuid4()
    out = CallAnalysisOut(
        id=uuid.uuid4(),
        call_id=uuid.uuid4(),
        overall_score=78,
        summary="Good call.",
        key_moments=[KeyMomentOut(segment_id=seg_id, label="Greeting")],
        action_items=["Follow up tomorrow"],
        sentiment_overall="positive",
        talk_listen_ratio=0.6,
        interruptions=2,
        longest_monologue_ms=8000,
        total_turns=12,
        compliance_passed=True,
        escalate_for_review=False,
        escalation_reason=None,
        created_at=datetime.now(tz=timezone.utc),
    )
    assert out.overall_score == 78
    assert out.key_moments[0].segment_id == seg_id

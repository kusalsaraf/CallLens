"""Tests for calllens.agents.metrics.compute_metrics."""

from __future__ import annotations

import uuid

import pytest

from calllens.agents.llm import TimedTranscriptSegmentData
from calllens.agents.metrics import compute_metrics


def _seg(
    speaker: str,
    start_ms: int,
    end_ms: int,
    seq: int = 0,
) -> TimedTranscriptSegmentData:
    """Build a minimal timed segment for tests."""
    return TimedTranscriptSegmentData(
        id=uuid.uuid4(),
        sequence=seq,
        text=f"{speaker} speaking from {start_ms} to {end_ms}",
        speaker=speaker,
        start_ms=start_ms,
        end_ms=end_ms,
    )


class TestComputeMetrics:
    def test_empty_segments_returns_zeros(self) -> None:
        """Empty segment list returns all-zero ConversationMetrics."""
        result = compute_metrics([])

        assert result.talk_listen_ratio == pytest.approx(0.0)
        assert result.interruptions == 0
        assert result.longest_monologue_ms == 0
        assert result.total_turns == 0

    def test_single_agent_segment_single_speaker(self) -> None:
        """Single agent segment: ratio=0.0 (no customer), 1 turn, 0 interruptions."""
        segs = [_seg("agent", 0, 5000, seq=0)]

        result = compute_metrics(segs)

        assert result.talk_listen_ratio == pytest.approx(0.0)
        assert result.total_turns == 1
        assert result.interruptions == 0
        assert result.longest_monologue_ms == 5000

    def test_talk_listen_ratio_two_to_one(self) -> None:
        """Agent speaks 4 s, customer speaks 2 s -> ratio = 4000/2000 = 2.0."""
        segs = [
            _seg("agent", 0, 4000, seq=0),
            _seg("customer", 4500, 6500, seq=1),
        ]

        result = compute_metrics(segs)

        assert result.talk_listen_ratio == pytest.approx(2.0)
        assert result.total_turns == 2

    def test_talk_listen_ratio_balanced(self) -> None:
        """Equal agent and customer time -> ratio = 1.0."""
        segs = [
            _seg("agent", 0, 3000, seq=0),
            _seg("customer", 3500, 6500, seq=1),
        ]

        result = compute_metrics(segs)

        assert result.talk_listen_ratio == pytest.approx(1.0)

    def test_interruption_on_overlap(self) -> None:
        """Customer starts 50ms before agent ends -> 1 interruption."""
        segs = [
            _seg("agent", 0, 5000, seq=0),
            _seg("customer", 4950, 7000, seq=1),  # starts 50ms before agent ends
        ]

        result = compute_metrics(segs)

        assert result.interruptions == 1
        assert result.total_turns == 2

    def test_no_interruption_on_long_gap(self) -> None:
        """500ms gap between speakers is not an interruption."""
        segs = [
            _seg("agent", 0, 5000, seq=0),
            _seg("customer", 5500, 8000, seq=1),  # 500ms gap — outside threshold
        ]

        result = compute_metrics(segs)

        assert result.interruptions == 0
        assert result.total_turns == 2

    def test_multiple_interruptions(self) -> None:
        """Three rapid speaker switches each within threshold -> 3 interruptions."""
        segs = [
            _seg("agent", 0, 2000, seq=0),
            _seg("customer", 1900, 3500, seq=1),  # overlap -> interruption
            _seg("agent", 3400, 5000, seq=2),  # overlap -> interruption
            _seg("customer", 4900, 7000, seq=3),  # overlap -> interruption
        ]

        result = compute_metrics(segs)

        assert result.interruptions == 3
        assert result.total_turns == 4

    def test_longest_monologue_contiguous_segments(self) -> None:
        """Two adjacent agent segments with small gap form one monologue."""
        segs = [
            _seg("agent", 0, 3000, seq=0),
            _seg("agent", 3100, 6000, seq=1),  # same speaker, 100ms gap
            _seg("customer", 6500, 8000, seq=2),
        ]

        result = compute_metrics(segs)

        # Agent monologue: 0->3000 + gap + 3100->6000 = 6000ms duration
        assert result.longest_monologue_ms == 6000

    def test_longest_monologue_broken_by_different_speaker(self) -> None:
        """A speaker change resets the monologue counter."""
        segs = [
            _seg("agent", 0, 3000, seq=0),
            _seg("customer", 3100, 4000, seq=1),  # breaks agent monologue
            _seg("agent", 4100, 8100, seq=2),  # new agent monologue: 4000ms
        ]

        result = compute_metrics(segs)

        assert result.longest_monologue_ms == 4000  # second agent block, not first

    def test_total_turns_counts_speaker_changes(self) -> None:
        """ABAB pattern = 4 turns; same-speaker consecutive segments are one turn."""
        segs = [
            _seg("agent", 0, 1000, seq=0),
            _seg("agent", 1100, 2000, seq=1),  # same speaker — not a new turn
            _seg("customer", 2500, 3500, seq=2),
            _seg("agent", 4000, 5000, seq=3),
            _seg("customer", 5500, 6500, seq=4),
        ]

        result = compute_metrics(segs)

        assert result.total_turns == 4  # agent, customer, agent, customer

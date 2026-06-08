"""Deterministic conversation metrics computed from timed transcript segments."""

from __future__ import annotations

from pydantic import BaseModel, Field

from calllens.agents.llm import TimedTranscriptSegmentData

# A speaker switch is counted as an interruption when the new speaker's start_ms
# is less than the previous speaker's end_ms plus this threshold.
# 150 ms captures genuine overlaps and rapid cut-ins while ignoring natural pauses.
_INTERRUPTION_THRESHOLD_MS: int = 150

# Two consecutive segments by the same speaker are merged into one monologue run
# unless the gap between them exceeds this value.
_MONOLOGUE_GAP_MS: int = 500


class ConversationMetrics(BaseModel):
    """Aggregate metrics computed deterministically from timed transcript segments.

    All fields are non-negative. A zero value indicates the metric could not be
    computed (e.g., no customer speaker -> talk_listen_ratio = 0.0).
    """

    talk_listen_ratio: float = Field(ge=0.0)
    """Agent total speaking ms / customer total speaking ms.

    Zero when customer spoke 0 ms (single-speaker call or NullDiarizer output).
    Values above 1.0 mean the agent spoke more than the customer.
    """

    interruptions: int = Field(ge=0)
    """Count of speaker changes where the new speaker's start_ms falls within
    _INTERRUPTION_THRESHOLD_MS of the prior speaker's end_ms.

    Only counts transitions between DIFFERENT speakers. Consecutive same-speaker
    segments (e.g., two agent segments back-to-back) are not counted.
    """

    longest_monologue_ms: int = Field(ge=0)
    """Duration of the longest contiguous single-speaker run in milliseconds.

    A run continues as long as consecutive segments share the same speaker AND
    the gap between them does not exceed _MONOLOGUE_GAP_MS. Measured as
    end_ms of the last segment minus start_ms of the first.
    """

    total_turns: int = Field(ge=0)
    """Number of distinct speaker turns.

    A new turn begins every time the speaker changes. Consecutive segments from
    the same speaker are part of the same turn. Zero for an empty segment list.
    """


def compute_metrics(segments: list[TimedTranscriptSegmentData]) -> ConversationMetrics:
    """Compute conversation metrics from a sorted list of timed transcript segments.

    Handles edge cases:
    - Empty list -> all-zero metrics
    - Single speaker only -> talk_listen_ratio=0.0, interruptions=0

    Args:
        segments: Timed transcript segments, expected in sequence order.

    Returns:
        A ConversationMetrics instance with all fields computed.
    """
    if not segments:
        return ConversationMetrics(
            talk_listen_ratio=0.0,
            interruptions=0,
            longest_monologue_ms=0,
            total_turns=0,
        )

    # --- Talk/listen ratio ---
    agent_ms = sum(
        max(0, seg["end_ms"] - seg["start_ms"])
        for seg in segments
        if seg["speaker"].lower().startswith("agent")
    )
    customer_ms = sum(
        max(0, seg["end_ms"] - seg["start_ms"])
        for seg in segments
        if not seg["speaker"].lower().startswith("agent")
    )
    talk_listen_ratio = round(agent_ms / customer_ms, 4) if customer_ms > 0 else 0.0

    # --- Interruptions and total_turns ---
    interruptions = 0
    total_turns = 1

    for i in range(1, len(segments)):
        prev = segments[i - 1]
        curr = segments[i]
        if curr["speaker"] != prev["speaker"]:
            total_turns += 1
            # Interruption when new speaker starts before prev ends + threshold
            if curr["start_ms"] < prev["end_ms"] + _INTERRUPTION_THRESHOLD_MS:
                interruptions += 1

    # --- Longest monologue ---
    longest_monologue_ms = 0
    run_speaker = segments[0]["speaker"]
    run_start_ms = segments[0]["start_ms"]
    run_end_ms = segments[0]["end_ms"]

    for seg in segments[1:]:
        gap = seg["start_ms"] - run_end_ms
        if seg["speaker"] == run_speaker and gap <= _MONOLOGUE_GAP_MS:
            run_end_ms = seg["end_ms"]
        else:
            duration = run_end_ms - run_start_ms
            longest_monologue_ms = max(longest_monologue_ms, duration)
            run_speaker = seg["speaker"]
            run_start_ms = seg["start_ms"]
            run_end_ms = seg["end_ms"]

    # Flush the last run
    longest_monologue_ms = max(longest_monologue_ms, run_end_ms - run_start_ms)

    return ConversationMetrics(
        talk_listen_ratio=talk_listen_ratio,
        interruptions=interruptions,
        longest_monologue_ms=longest_monologue_ms,
        total_turns=total_turns,
    )

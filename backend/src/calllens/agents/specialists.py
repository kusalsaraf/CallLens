"""Specialist scoring agents for each rubric dimension kind."""

from __future__ import annotations

import logging
import uuid
from typing import Any, TypedDict

from calllens.agents.evidence import validate_evidence
from calllens.agents.llm import (
    AgentScore,
    LLMProvider,
    TimedTranscriptSegmentData,
    TranscriptSegmentData,
    get_llm_provider,
)
from calllens.agents.metrics import ConversationMetrics

logger = logging.getLogger(__name__)

# Agent:customer talk ratio considered ideal for a support call.
# Derived: agent speaks ~41% of the time (ratio ~0.7 means agent:customer ~1:1.43).
_IDEAL_TALK_LISTEN_RATIO: float = 0.7


class FullRubricDimensionData(TypedDict):
    """Full rubric dimension data including kind and config, used by the graph."""

    id: uuid.UUID
    key: str
    name: str
    weight: float
    kind: str
    config: dict[str, Any] | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_segments(timed: list[TimedTranscriptSegmentData]) -> list[TranscriptSegmentData]:
    """Strip timing fields to produce a base TranscriptSegmentData list."""
    return [
        TranscriptSegmentData(
            id=s["id"],
            sequence=s["sequence"],
            text=s["text"],
            speaker=s["speaker"],
        )
        for s in timed
    ]


# ---------------------------------------------------------------------------
# Deterministic dimension: talk/listen ratio
# ---------------------------------------------------------------------------


def score_talk_listen(
    dimension: FullRubricDimensionData,
    metrics: ConversationMetrics,
) -> AgentScore:
    """Compute talk/listen score deterministically from ConversationMetrics.

    Score formula:
        deviation = |actual_ratio - ideal_ratio|   (ideal = _IDEAL_TALK_LISTEN_RATIO)
        score = max(0, min(100, round(100 - deviation * 100)))

    Interpretation: each 0.01 unit of deviation from the ideal costs 1 point.
    A deviation of 1.0 (agent speaks double the ideal) gives score = 0.

    No evidence refs — this metric has no text to cite.

    Args:
        dimension: The talk_listen rubric dimension.
        metrics: Pre-computed ConversationMetrics for the call.

    Returns:
        An AgentScore with confidence=1.0 and empty evidence.
    """
    actual = metrics.talk_listen_ratio
    deviation = abs(actual - _IDEAL_TALK_LISTEN_RATIO)
    score = max(0, min(100, round(100 - deviation * 100)))

    return AgentScore(
        score=score,
        confidence=1.0,
        rationale=(
            f"Talk/listen ratio: {actual:.3f} (ideal ~{_IDEAL_TALK_LISTEN_RATIO:.2f}). "
            f"Deviation from ideal: {deviation:.3f}."
        ),
        evidence=[],
        is_supported=True,
    )


# ---------------------------------------------------------------------------
# LLM-scored specialist agents
# ---------------------------------------------------------------------------


async def score_sentiment_empathy(
    segments: list[TranscriptSegmentData],
    dimension: FullRubricDimensionData,
    provider: LLMProvider | None = None,
) -> AgentScore:
    """Score the agent's sentiment and empathy throughout the call.

    Focuses exclusively on the AGENT's tone, word choice, and empathic
    responses — customer sentiment is not scored.

    Args:
        segments: All transcript segments (base, no timing).
        dimension: The sentiment_empathy rubric dimension.
        provider: LLM provider; defaults to get_llm_provider().

    Returns:
        A validated AgentScore with evidence linked to real agent segments.
    """
    if provider is None:
        provider = get_llm_provider()

    segments_by_id = {seg["id"]: seg for seg in segments}

    system = (
        "You are a call quality analyst scoring a customer service call.\n"
        "Score the AGENT's sentiment and empathy on a scale of 0-100.\n"
        "Focus ONLY on the agent's tone, word choice, and empathy — ignore customer sentiment.\n"
        "You MUST cite evidence as verbatim quotes from the transcript using the exact segment IDs "
        "provided. Only cite segments that exist in the transcript."
    )
    lines = [
        f"Dimension: {dimension['name']} (weight: {dimension['weight']})",
        "Transcript:",
    ]
    for seg in segments:
        lines.append(f"[{seg['id']}] seq={seg['sequence']} speaker={seg['speaker']}: {seg['text']}")
    user = "\n".join(lines)

    raw = await provider.structured_score(system, user, segments)
    return validate_evidence(raw, segments_by_id)


async def score_script_adherence(
    segments: list[TranscriptSegmentData],
    dimension: FullRubricDimensionData,
    provider: LLMProvider | None = None,
) -> AgentScore:
    """Score whether the agent followed the standard support call structure.

    Expected structure (drawn from dimension.config checklist if present,
    otherwise uses the default five-step flow):
    1. Greeting
    2. Identity verification
    3. Issue clarification
    4. Resolution
    5. Closing

    Args:
        segments: All transcript segments.
        dimension: The script_adherence rubric dimension.
        provider: LLM provider; defaults to get_llm_provider().

    Returns:
        A validated AgentScore.
    """
    if provider is None:
        provider = get_llm_provider()

    segments_by_id = {seg["id"]: seg for seg in segments}

    config = dimension.get("config") or {}
    checklist_raw = config.get("checklist")
    if isinstance(checklist_raw, list):
        checklist_items = "\n".join(f"- {item}" for item in checklist_raw)
    else:
        checklist_items = (
            "- Greeting: professional opening\n"
            "- Identity verification: confirm caller identity\n"
            "- Issue clarification: ask clarifying questions\n"
            "- Resolution: provide answer or next steps\n"
            "- Closing: confirm resolution and offer further help"
        )

    system = (
        "You are a call quality analyst scoring a support call for script adherence.\n"
        "Score the agent's adherence to the required call structure on a scale of 0-100.\n"
        "The expected call structure steps are listed below. "
        "Check whether the agent completed each step and cite evidence from the transcript.\n"
        "You MUST use exact verbatim quotes from segment IDs provided."
    )
    lines = [
        f"Dimension: {dimension['name']} (weight: {dimension['weight']})",
        "Required call structure:",
        checklist_items,
        "Transcript:",
    ]
    for seg in segments:
        lines.append(f"[{seg['id']}] seq={seg['sequence']} speaker={seg['speaker']}: {seg['text']}")
    user = "\n".join(lines)

    raw = await provider.structured_score(system, user, segments)
    return validate_evidence(raw, segments_by_id)


async def score_compliance(
    segments: list[TranscriptSegmentData],
    dimension: FullRubricDimensionData,
    provider: LLMProvider | None = None,
) -> AgentScore:
    """Score regulatory/policy compliance by checking for required phrases.

    Required phrases are drawn from dimension.config["required_phrases"].

    Score mapping:
    - All required phrases found -> 100
    - Partial: (found_count / total_required) * 100
    - None found -> 0
    - No required_phrases configured -> 100 (no requirement to check)

    Args:
        segments: All transcript segments.
        dimension: The compliance rubric dimension (config.required_phrases expected).
        provider: LLM provider; defaults to get_llm_provider().

    Returns:
        A validated AgentScore.
    """
    if provider is None:
        provider = get_llm_provider()

    segments_by_id = {seg["id"]: seg for seg in segments}

    config = dimension.get("config") or {}
    phrases_raw = config.get("required_phrases")
    if not isinstance(phrases_raw, list) or not phrases_raw:
        return AgentScore(
            score=100,
            confidence=1.0,
            rationale="No required phrases configured; full compliance assumed.",
            evidence=[],
            is_supported=True,
        )

    phrases: list[str] = [str(p) for p in phrases_raw]
    phrases_block = "\n".join(f'  - "{p}"' for p in phrases)

    system = (
        "You are a compliance analyst auditing a customer service call.\n"
        "Score the agent's compliance on a scale of 0-100.\n"
        "For each required phrase below, determine whether the agent said it (or a "
        "close equivalent). Cite the exact segment where each was said. "
        "If a phrase was NOT said, flag it as MISSED in your rationale.\n"
        "Score = (phrases_found / total_phrases) * 100, rounded to nearest integer.\n"
        "You MUST use exact verbatim quotes from segment IDs provided."
    )
    lines = [
        f"Dimension: {dimension['name']} (weight: {dimension['weight']})",
        "Required phrases:",
        phrases_block,
        "Transcript:",
    ]
    for seg in segments:
        lines.append(f"[{seg['id']}] seq={seg['sequence']} speaker={seg['speaker']}: {seg['text']}")
    user = "\n".join(lines)

    raw = await provider.structured_score(system, user, segments)
    return validate_evidence(raw, segments_by_id)


async def score_objection_handling(
    segments: list[TranscriptSegmentData],
    dimension: FullRubricDimensionData,
    provider: LLMProvider | None = None,
) -> AgentScore:
    """Score how well the agent acknowledged and addressed customer objections.

    Looks for: (a) recognition of customer pushback or frustration,
    (b) empathic acknowledgement, (c) substantive response or resolution offer.

    Args:
        segments: All transcript segments.
        dimension: The objection_handling rubric dimension.
        provider: LLM provider; defaults to get_llm_provider().

    Returns:
        A validated AgentScore.
    """
    if provider is None:
        provider = get_llm_provider()

    segments_by_id = {seg["id"]: seg for seg in segments}

    system = (
        "You are a call quality analyst scoring a support call for objection handling.\n"
        "Score the agent's ability to acknowledge and address customer pushback or "
        "objections on a scale of 0-100.\n"
        "Look for: (1) recognition of customer frustration or pushback, "
        "(2) empathic acknowledgement, (3) substantive resolution or next-step offer.\n"
        "Cite evidence from the transcript using exact verbatim quotes and segment IDs."
    )
    lines = [
        f"Dimension: {dimension['name']} (weight: {dimension['weight']})",
        "Transcript:",
    ]
    for seg in segments:
        lines.append(f"[{seg['id']}] seq={seg['sequence']} speaker={seg['speaker']}: {seg['text']}")
    user = "\n".join(lines)

    raw = await provider.structured_score(system, user, segments)
    return validate_evidence(raw, segments_by_id)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_UNSCORED_RESULT = AgentScore(
    score=0,
    confidence=0.1,
    rationale="Scoring agent encountered an error; result is unreliable.",
    evidence=[],
    is_supported=False,
)


async def run_specialist(
    dimension: FullRubricDimensionData,
    segments: list[TimedTranscriptSegmentData],
    metrics: ConversationMetrics,
    provider: LLMProvider | None = None,
) -> AgentScore:
    """Dispatch to the correct specialist agent based on dimension kind and key.

    Handles:
    - kind="ratio" (talk_listen): deterministic, no LLM
    - kind="score" + known keys: LLM-scored specialist
    - Unknown kind or key: returns unscored result
    - Provider errors: returns low-confidence unscored result, never crashes

    Args:
        dimension: The rubric dimension to score.
        segments: Full timed transcript segments.
        metrics: Pre-computed ConversationMetrics for deterministic dimensions.
        provider: LLM provider; defaults to get_llm_provider().

    Returns:
        A validated AgentScore. Always returns, never raises.
    """
    key = dimension["key"]
    kind = dimension["kind"]

    if kind == "ratio":
        return score_talk_listen(dimension, metrics)

    base = _base_segments(segments)

    try:
        if kind == "score":
            if key == "sentiment_empathy":
                return await score_sentiment_empathy(base, dimension, provider)
            if key == "script_adherence":
                return await score_script_adherence(base, dimension, provider)
            if key == "compliance":
                return await score_compliance(base, dimension, provider)
            if key == "objection_handling":
                return await score_objection_handling(base, dimension, provider)

        logger.warning(
            "run_specialist: unsupported dimension kind=%r key=%r — returning unscored",
            kind,
            key,
        )
        return AgentScore(
            score=0,
            confidence=0.0,
            rationale=f"Unsupported dimension kind={kind!r}, key={key!r}.",
            evidence=[],
            is_supported=False,
        )

    except Exception:
        logger.exception("Specialist failed for dimension key=%r", key)
        return _UNSCORED_RESULT

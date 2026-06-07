"""Sentiment and empathy scoring agent."""

from __future__ import annotations

import uuid
from typing import TypedDict

from calllens.agents.evidence import validate_evidence
from calllens.agents.llm import AgentScore, LLMProvider, TranscriptSegmentData, get_llm_provider


class RubricDimensionData(TypedDict):
    """Lightweight dict representation of a RubricDimension row."""

    id: uuid.UUID
    key: str
    name: str
    weight: float


async def score_sentiment_empathy(
    transcript_segments: list[TranscriptSegmentData],
    dimension: RubricDimensionData,
    provider: LLMProvider | None = None,
) -> AgentScore:
    """Score the sentiment/empathy dimension of a call transcript.

    Builds a prompt listing each segment with its ID, sequence, and speaker.
    Instructs the model to score the AGENT's empathy and tone only (ignore
    customer sentiment). Requires verbatim quotes from real segment IDs as evidence.

    Args:
        transcript_segments: All segments of the transcript.
        dimension: The rubric dimension being scored.
        provider: LLM provider to use; defaults to get_llm_provider().

    Returns:
        A validated AgentScore with evidence linked to real segments.
    """
    if provider is None:
        provider = get_llm_provider()

    segments_by_id: dict[uuid.UUID, TranscriptSegmentData] = {
        seg["id"]: seg for seg in transcript_segments
    }

    system = (
        "You are a call quality analyst scoring a customer service call.\n"
        "Score the AGENT's sentiment and empathy on a scale of 0–100.\n"
        "Focus ONLY on the agent's tone, word choice, and empathy — ignore customer sentiment.\n"
        "You MUST cite evidence as verbatim quotes from the transcript using the exact segment IDs "
        "provided.\n"
        "Only cite segments that exist in the transcript."
    )

    lines: list[str] = [
        f"Dimension: {dimension['name']} (weight: {dimension['weight']})",
        "Transcript segments:",
    ]
    for seg in transcript_segments:
        lines.append(f"[{seg['id']}] seq={seg['sequence']} speaker={seg['speaker']}: {seg['text']}")
    user = "\n".join(lines)

    raw = await provider.structured_score(system, user, transcript_segments)
    return validate_evidence(raw, segments_by_id)

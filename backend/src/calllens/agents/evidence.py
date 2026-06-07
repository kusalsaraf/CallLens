"""Evidence validation for LLM-produced AgentScore instances."""

from __future__ import annotations

import uuid

from calllens.agents.llm import AgentScore, EvidenceRef, TranscriptSegmentData


def _normalize(text: str) -> str:
    """Collapse whitespace and lowercase text for substring matching.

    Args:
        text: Raw string to normalise.

    Returns:
        Lowercased string with runs of whitespace collapsed to a single space.
    """
    return " ".join(text.lower().split())


def validate_evidence(
    result: AgentScore,
    segments_by_id: dict[uuid.UUID, TranscriptSegmentData],
) -> AgentScore:
    """Validate and clean evidence references against actual transcript segments.

    Drops any EvidenceRef where:
    1. segment_id is not a key in segments_by_id
    2. quote (after whitespace+case normalization) is NOT a substring of that
       segment's text

    If ALL evidence is dropped:
    - Lower confidence by 50% (multiply by 0.5)
    - Set is_supported = False

    NEVER fabricates evidence. Returns a new AgentScore (does not mutate).

    Args:
        result: The raw AgentScore from the LLM provider.
        segments_by_id: Map of segment UUID → TranscriptSegmentData.

    Returns:
        A new AgentScore with invalid evidence removed and flags adjusted.
    """
    valid: list[EvidenceRef] = []

    for ref in result.evidence:
        seg = segments_by_id.get(ref.segment_id)
        if seg is None:
            # Unknown segment_id — drop silently
            continue
        if _normalize(ref.quote) in _normalize(seg["text"]):
            valid.append(ref)
        # Quote not a substring — drop silently

    if not valid:
        # All evidence was dropped — penalise confidence and flag as unsupported
        return result.model_copy(
            update={
                "evidence": [],
                "confidence": result.confidence * 0.5,
                "is_supported": False,
            }
        )

    return result.model_copy(update={"evidence": valid})

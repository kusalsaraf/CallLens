"""Tests for calllens.agents.evidence.validate_evidence."""

from __future__ import annotations

import uuid

import pytest

from calllens.agents.evidence import validate_evidence
from calllens.agents.llm import AgentScore, EvidenceRef, TranscriptSegmentData


def _make_segment(
    text: str,
    speaker: str = "agent",
    seg_id: uuid.UUID | None = None,
    sequence: int = 0,
) -> TranscriptSegmentData:
    """Build a TranscriptSegmentData dict for use in tests."""
    return TranscriptSegmentData(
        id=seg_id or uuid.uuid4(),
        sequence=sequence,
        text=text,
        speaker=speaker,
    )


def _make_score(
    evidence: list[EvidenceRef],
    score: int = 75,
    confidence: float = 0.8,
    is_supported: bool = True,
) -> AgentScore:
    """Build an AgentScore for use in tests."""
    return AgentScore(
        score=score,
        confidence=confidence,
        rationale="Test rationale",
        evidence=evidence,
        is_supported=is_supported,
    )


# ---------------------------------------------------------------------------
# Test 1: valid evidence passes through unchanged
# ---------------------------------------------------------------------------


def test_valid_evidence_passes_through() -> None:
    """Valid segment_id + verbatim quote — evidence is kept, flags unchanged."""
    seg_id = uuid.uuid4()
    seg = _make_segment("The customer was very upset about the delay.", seg_id=seg_id)
    ref = EvidenceRef(segment_id=seg_id, quote="customer was very upset")
    score = _make_score([ref])

    result = validate_evidence(score, {seg_id: seg})

    assert len(result.evidence) == 1
    assert result.evidence[0].segment_id == seg_id
    assert result.evidence[0].quote == "customer was very upset"
    assert result.is_supported is True
    assert result.confidence == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Test 2: unknown segment_id is dropped
# ---------------------------------------------------------------------------


def test_unknown_segment_id_is_dropped() -> None:
    """EvidenceRef with a segment_id not in the map is silently removed."""
    known_id = uuid.uuid4()
    ghost_id = uuid.uuid4()
    seg = _make_segment("Hello there.", seg_id=known_id)
    ref = EvidenceRef(segment_id=ghost_id, quote="Hello there.")
    score = _make_score([ref], confidence=0.9)

    result = validate_evidence(score, {known_id: seg})

    assert result.evidence == []
    assert result.is_supported is False
    assert result.confidence == pytest.approx(0.9 * 0.5)


# ---------------------------------------------------------------------------
# Test 3: non-substring quote is dropped
# ---------------------------------------------------------------------------


def test_non_substring_quote_is_dropped() -> None:
    """Quote that is not a substring of the segment text is removed."""
    seg_id = uuid.uuid4()
    seg = _make_segment("I completely understand your frustration.", seg_id=seg_id)
    # Quote does not appear in the segment text
    ref = EvidenceRef(segment_id=seg_id, quote="thank you for your patience")
    score = _make_score([ref], confidence=0.7)

    result = validate_evidence(score, {seg_id: seg})

    assert result.evidence == []
    assert result.is_supported is False
    assert result.confidence == pytest.approx(0.7 * 0.5)


# ---------------------------------------------------------------------------
# Test 4: whitespace normalization — extra spaces in quote still match
# ---------------------------------------------------------------------------


def test_whitespace_normalization_allows_match() -> None:
    """Quote with extra internal spaces matches segment text after normalization."""
    seg_id = uuid.uuid4()
    seg = _make_segment("hello   world", seg_id=seg_id)
    # Normalized form "hello world" should be found in normalized segment "hello world"
    ref = EvidenceRef(segment_id=seg_id, quote="hello world")
    score = _make_score([ref])

    result = validate_evidence(score, {seg_id: seg})

    assert len(result.evidence) == 1
    assert result.is_supported is True


# ---------------------------------------------------------------------------
# Test 5: case normalization — uppercase quote matches lowercase text
# ---------------------------------------------------------------------------


def test_case_normalization_allows_match() -> None:
    """Quote in uppercase matches lowercase segment text after normalization."""
    seg_id = uuid.uuid4()
    seg = _make_segment("hello world", seg_id=seg_id)
    ref = EvidenceRef(segment_id=seg_id, quote="HELLO WORLD")
    score = _make_score([ref])

    result = validate_evidence(score, {seg_id: seg})

    assert len(result.evidence) == 1
    assert result.is_supported is True
    assert result.confidence == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Test 6: partial evidence — some pass, some fail
# ---------------------------------------------------------------------------


def test_partial_evidence_keeps_valid_ref() -> None:
    """One valid ref and one with a bad segment_id: only valid ref survives."""
    good_id = uuid.uuid4()
    bad_id = uuid.uuid4()
    seg = _make_segment("I apologize for the inconvenience.", seg_id=good_id)

    good_ref = EvidenceRef(segment_id=good_id, quote="apologize for the inconvenience")
    bad_ref = EvidenceRef(segment_id=bad_id, quote="nonexistent quote")
    score = _make_score([good_ref, bad_ref])

    result = validate_evidence(score, {good_id: seg})

    assert len(result.evidence) == 1
    assert result.evidence[0].segment_id == good_id
    # Not all evidence was dropped, so is_supported stays True
    assert result.is_supported is True
    assert result.confidence == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Test 7: ALL evidence dropped lowers confidence by 50%
# ---------------------------------------------------------------------------


def test_all_evidence_dropped_halves_confidence() -> None:
    """When every ref is invalid, confidence is multiplied by 0.5 and is_supported=False."""
    real_id = uuid.uuid4()
    seg = _make_segment("Real text here.", seg_id=real_id)

    ghost1 = uuid.uuid4()
    ghost2 = uuid.uuid4()
    refs = [
        EvidenceRef(segment_id=ghost1, quote="fabricated quote one"),
        EvidenceRef(segment_id=ghost2, quote="fabricated quote two"),
    ]
    score = _make_score(refs, confidence=0.6)

    result = validate_evidence(score, {real_id: seg})

    assert result.evidence == []
    assert result.is_supported is False
    assert result.confidence == pytest.approx(0.6 * 0.5)


# ---------------------------------------------------------------------------
# Test 8: empty evidence input halves confidence
# ---------------------------------------------------------------------------


def test_empty_evidence_input_halves_confidence() -> None:
    """AgentScore with no evidence is treated as all-dropped: confidence halved."""
    seg_id = uuid.uuid4()
    seg = _make_segment("Some text.", seg_id=seg_id)
    score = _make_score([], confidence=1.0)

    result = validate_evidence(score, {seg_id: seg})

    assert result.evidence == []
    assert result.is_supported is False
    assert result.confidence == pytest.approx(0.5)

"""Merge transcript segments with diarization turns and assign speaker roles."""

from collections import Counter

from calllens.transcription.base import DiarizationTurn, MergedSegment, TranscriptSegmentData


def _overlap_ms(
    seg_start: int,
    seg_end: int,
    turn_start: int,
    turn_end: int,
) -> int:
    """Compute the overlap in milliseconds between a segment and a turn."""
    return max(0, min(seg_end, turn_end) - max(seg_start, turn_start))


def _best_speaker(segment: TranscriptSegmentData, turns: list[DiarizationTurn]) -> str:
    """Find the diarization turn with the greatest temporal overlap."""
    if not turns:
        return "unknown"
    best = max(
        turns,
        key=lambda t: _overlap_ms(
            segment["start_ms"], segment["end_ms"], t["start_ms"], t["end_ms"]
        ),
    )
    return best["speaker"]


def merge(
    segments: list[TranscriptSegmentData],
    turns: list[DiarizationTurn],
) -> list[MergedSegment]:
    """Align transcript segments with diarization turns and label speakers.

    The two most frequent raw speaker labels are mapped to "agent" and
    "customer" (most frequent → "agent", second → "customer"). All others
    are labelled "unknown".

    Args:
        segments: Ordered transcript segments from the Transcriber.
        turns: Speaker turns from the Diarizer.

    Returns:
        List of MergedSegment dicts with start_ms, end_ms, text, speaker, sequence.
        Speaker values are "agent", "customer", or "unknown".
    """
    raw: list[MergedSegment] = []
    for idx, seg in enumerate(segments):
        raw.append(
            {
                "start_ms": seg["start_ms"],
                "end_ms": seg["end_ms"],
                "text": seg["text"],
                "speaker": _best_speaker(seg, turns),
                "sequence": idx,
            }
        )

    counter: Counter[str] = Counter(str(r["speaker"]) for r in raw)
    most_common = [label for label, _ in counter.most_common(2)]

    role_map: dict[str, str] = {}
    if len(most_common) >= 1:
        role_map[most_common[0]] = "agent"
    if len(most_common) >= 2:
        role_map[most_common[1]] = "customer"

    for item in raw:
        raw_speaker = str(item["speaker"])
        item["speaker"] = role_map.get(raw_speaker, "unknown")

    return raw

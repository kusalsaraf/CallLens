"""Transcriber and Diarizer protocols plus shared data types."""

from pathlib import Path
from typing import Protocol, TypedDict


class TranscriptSegmentData(TypedDict):
    """A single transcribed segment with timing."""

    start_ms: int
    end_ms: int
    text: str


class MergedSegment(TypedDict):
    """A transcript segment with timing, text, speaker role, and sequence index."""

    start_ms: int
    end_ms: int
    text: str
    speaker: str
    sequence: int


class DiarizationTurn(TypedDict):
    """A single speaker turn from diarization."""

    start_ms: int
    end_ms: int
    speaker: str


class Transcriber(Protocol):
    """Contract for speech-to-text implementations."""

    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> list[TranscriptSegmentData]:
        """Convert audio to a list of timed text segments.

        Args:
            audio_path: Path to the audio file on the local filesystem.
            language: BCP-47 language code hint (e.g. "en"). None = auto-detect.

        Returns:
            Ordered list of segments with start_ms, end_ms, text.
        """
        ...


class Diarizer(Protocol):
    """Contract for speaker diarization implementations."""

    async def diarize(self, audio_path: Path) -> list[DiarizationTurn]:
        """Identify speaker turns in an audio file.

        Args:
            audio_path: Path to the audio file on the local filesystem.

        Returns:
            Ordered list of speaker turns with start_ms, end_ms, speaker label.
        """
        ...

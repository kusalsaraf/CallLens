"""StubTranscriber — returns canned segments without reading the audio file."""

from pathlib import Path

from calllens.transcription.base import TranscriptSegmentData

_CANNED_SEGMENTS: list[TranscriptSegmentData] = [
    {"start_ms": 0, "end_ms": 3200, "text": "Hello, thank you for calling support."},
    {"start_ms": 3400, "end_ms": 6800, "text": "Hi, I have an issue with my account."},
    {"start_ms": 7000, "end_ms": 11000, "text": "Sure, I can help you with that today."},
    {"start_ms": 11200, "end_ms": 15000, "text": "My billing statement looks incorrect."},
    {"start_ms": 15300, "end_ms": 19500, "text": "Let me pull up your account right now."},
]


class StubTranscriber:
    """Returns pre-canned transcript segments for testing and development.

    No ML dependencies required. The audio file is never read.
    """

    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> list[TranscriptSegmentData]:
        """Return a realistic-looking set of canned segments.

        Args:
            audio_path: Ignored.
            language: Ignored.

        Returns:
            A fixed list of five transcript segments.
        """
        return list(_CANNED_SEGMENTS)

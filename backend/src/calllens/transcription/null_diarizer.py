"""NullDiarizer — treats the entire recording as a single speaker."""

from pathlib import Path

from calllens.transcription.base import DiarizationTurn

_SINGLE_SPEAKER = "SPEAKER_00"


class NullDiarizer:
    """Returns a single speaker turn spanning the whole file.

    Used as the default diarizer when no diarization is needed.
    """

    async def diarize(self, audio_path: Path) -> list[DiarizationTurn]:
        """Return a single speaker turn of effectively infinite duration.

        Args:
            audio_path: Ignored.

        Returns:
            A single DiarizationTurn spanning 0ms to a large sentinel value.
        """
        return [{"start_ms": 0, "end_ms": 2**31 - 1, "speaker": _SINGLE_SPEAKER}]

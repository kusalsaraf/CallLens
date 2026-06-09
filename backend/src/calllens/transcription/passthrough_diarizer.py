"""PassthroughDiarizer — returns diarization turns cached by a transcriber.

When the transcriber (e.g. AssemblyAI) already provides speaker labels
in its response, the diarization step becomes a no-op: it simply retrieves
the turns that the transcriber cached during its ``transcribe()`` call.

The merge step then maps the raw speaker labels (e.g. "A", "B") to
agent/customer using the same two-most-frequent heuristic.
"""

import logging
from pathlib import Path

from calllens.transcription.assemblyai import pop_cached_turns
from calllens.transcription.base import DiarizationTurn

logger = logging.getLogger(__name__)


class PassthroughDiarizer:
    """Returns speaker turns previously cached by the transcriber.

    Falls back to a single-speaker turn if no cached data is found,
    mirroring NullDiarizer behavior.
    """

    async def diarize(self, audio_path: Path) -> list[DiarizationTurn]:
        """Return cached diarization turns or a single-speaker fallback.

        Args:
            audio_path: Path to the audio file (used as cache key).

        Returns:
            Speaker turns from the transcriber, or a single fallback turn.
        """
        cached = pop_cached_turns(str(audio_path))
        if cached is not None:
            logger.debug(
                "PassthroughDiarizer: returning %d cached turns",
                len(cached),
            )
            return cached

        logger.warning(
            "PassthroughDiarizer: no cached turns found — falling back to single speaker"
        )
        return [{"start_ms": 0, "end_ms": 2**31 - 1, "speaker": "SPEAKER_00"}]

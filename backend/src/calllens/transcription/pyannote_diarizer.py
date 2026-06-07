"""PyannoteDiarizer — speaker diarization via pyannote.audio.

Prerequisites:
  1. uv sync --group transcription-local
  2. Accept the pyannote/speaker-diarization-3.1 model terms at
     https://huggingface.co/pyannote/speaker-diarization-3.1
  3. Set HUGGINGFACE_TOKEN in your environment.
"""

import asyncio
from pathlib import Path

from calllens.core.config import get_settings
from calllens.transcription.base import DiarizationTurn


class PyannoteDiarizer:
    """Speaker diarization using pyannote.audio 3.x.

    Args:
        model_id: HuggingFace model identifier.
    """

    def __init__(self, model_id: str = "pyannote/speaker-diarization-3.1") -> None:
        settings = get_settings()
        try:
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise ImportError(
                "pyannote.audio is not installed. Run: uv sync --group transcription-local"
            ) from exc
        if not settings.huggingface_token:
            raise ValueError("HUGGINGFACE_TOKEN is not configured")
        self._pipeline = Pipeline.from_pretrained(
            model_id, use_auth_token=settings.huggingface_token
        )

    async def diarize(self, audio_path: Path) -> list[DiarizationTurn]:
        """Run speaker diarization and return speaker turns.

        Args:
            audio_path: Path to the audio file on disk.

        Returns:
            Ordered list of speaker turns.
        """

        def _run() -> list[DiarizationTurn]:
            diarization = self._pipeline(str(audio_path))
            turns: list[DiarizationTurn] = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                turns.append(
                    {
                        "start_ms": int(turn.start * 1000),
                        "end_ms": int(turn.end * 1000),
                        "speaker": speaker,
                    }
                )
            return turns

        return await asyncio.get_event_loop().run_in_executor(None, _run)

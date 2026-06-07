"""FasterWhisperTranscriber — requires the transcription-local optional group."""

import asyncio
from pathlib import Path

from calllens.transcription.base import TranscriptSegmentData


class FasterWhisperTranscriber:
    """Speech-to-text using faster-whisper (CTranslate2-based Whisper).

    Install with: uv sync --group transcription-local

    Args:
        model_size: Whisper model size identifier (e.g. "base", "small", "large-v3").
        device: Compute device ("cpu" or "cuda").
        compute_type: CTranslate2 compute type ("int8", "float16", "float32").
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ImportError(
                "faster-whisper is not installed. Run: uv sync --group transcription-local"
            ) from exc
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> list[TranscriptSegmentData]:
        """Transcribe audio using faster-whisper running in the current thread.

        Args:
            audio_path: Path to the audio file.
            language: BCP-47 language hint or None for auto-detect.

        Returns:
            Ordered list of transcript segments.
        """

        def _run() -> list[TranscriptSegmentData]:
            segments, _ = self._model.transcribe(
                str(audio_path),
                language=language,
                beam_size=5,
                word_timestamps=False,
            )
            return [
                {
                    "start_ms": int(seg.start * 1000),
                    "end_ms": int(seg.end * 1000),
                    "text": seg.text.strip(),
                }
                for seg in segments
            ]

        return await asyncio.get_event_loop().run_in_executor(None, _run)

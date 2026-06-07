"""GroqWhisperTranscriber — uses Groq's Whisper API via httpx."""

from pathlib import Path

import httpx

from calllens.core.config import get_settings
from calllens.transcription.base import TranscriptSegmentData

_GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqWhisperTranscriber:
    """Speech-to-text via Groq's hosted Whisper endpoint.

    Requires GROQ_API_KEY to be set in settings.

    Args:
        model: Groq model identifier (default "whisper-large-v3").
    """

    def __init__(self, model: str = "whisper-large-v3") -> None:
        self._model = model

    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> list[TranscriptSegmentData]:
        """Transcribe via Groq Whisper API, returning verbose JSON segments.

        Args:
            audio_path: Path to the audio file to upload.
            language: BCP-47 language hint or None.

        Returns:
            Ordered list of transcript segments.
        """
        settings = get_settings()
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not configured")

        audio_bytes = audio_path.read_bytes()
        form_data: dict[str, str] = {"model": self._model, "response_format": "verbose_json"}
        if language:
            form_data["language"] = language

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                _GROQ_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                files={"file": (audio_path.name, audio_bytes)},
                data=form_data,
            )
            resp.raise_for_status()

        body = resp.json()
        return [
            {
                "start_ms": int(seg["start"] * 1000),
                "end_ms": int(seg["end"] * 1000),
                "text": seg["text"].strip(),
            }
            for seg in body.get("segments", [])
        ]

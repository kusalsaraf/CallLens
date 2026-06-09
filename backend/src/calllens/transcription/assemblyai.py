"""AssemblyAI managed transcription with built-in speaker diarization.

Returns transcription segments AND caches diarization turns so that
PassthroughDiarizer can retrieve them without a second API call.
"""

import asyncio
import logging
from pathlib import Path

import httpx

from calllens.core.config import get_settings
from calllens.transcription.base import DiarizationTurn, TranscriptSegmentData

logger = logging.getLogger(__name__)

_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
_TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
_POLL_INTERVAL_SEC = 3.0
_POLL_TIMEOUT_SEC = 600.0

_cached_diarization_turns: dict[str, list[DiarizationTurn]] = {}


def pop_cached_turns(audio_path: str) -> list[DiarizationTurn] | None:
    """Retrieve and remove cached diarization turns for a given audio path.

    Args:
        audio_path: The string path used as cache key during transcription.

    Returns:
        Cached turns if present, else None.
    """
    return _cached_diarization_turns.pop(audio_path, None)


class AssemblyAITranscriber:
    """Speech-to-text via AssemblyAI with speaker labels.

    Uploads the audio, requests transcription with speaker_labels=true,
    polls for completion, and returns timed segments. Speaker-labeled
    utterances are cached for PassthroughDiarizer.

    Requires ASSEMBLYAI_API_KEY to be set in settings.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    def _headers(self) -> dict[str, str]:
        settings = get_settings()
        if not settings.assemblyai_api_key:
            raise ValueError("ASSEMBLYAI_API_KEY is required when TRANSCRIBER_PROVIDER=assemblyai")
        return {"Authorization": settings.assemblyai_api_key}

    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> list[TranscriptSegmentData]:
        """Upload audio to AssemblyAI, poll for result, return segments.

        Speaker-labeled utterances are cached in the module-level store
        for PassthroughDiarizer to consume.

        Args:
            audio_path: Path to the audio file to upload.
            language: BCP-47 language hint or None for auto-detect.

        Returns:
            Ordered list of transcript segments.

        Raises:
            ValueError: If API key is missing.
            RuntimeError: If transcription fails or times out.
        """
        headers = self._headers()
        should_close = self._client is None
        client = self._client or httpx.AsyncClient(timeout=120)

        try:
            upload_url = await self._upload(client, headers, audio_path)
            transcript_id = await self._request_transcription(client, headers, upload_url, language)
            result = await self._poll(client, headers, transcript_id)
        finally:
            if should_close:
                await client.aclose()

        segments = self._parse_segments(result)
        turns = self._parse_turns(result)

        _cached_diarization_turns[str(audio_path)] = turns

        return segments

    async def _upload(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        audio_path: Path,
    ) -> str:
        """Upload audio file and return the upload URL."""
        audio_bytes = audio_path.read_bytes()
        resp = await client.post(
            _UPLOAD_URL,
            headers={**headers, "Content-Type": "application/octet-stream"},
            content=audio_bytes,
        )
        resp.raise_for_status()
        return str(resp.json()["upload_url"])

    async def _request_transcription(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        audio_url: str,
        language: str | None,
    ) -> str:
        """Submit transcription request, return transcript ID."""
        payload: dict[str, object] = {
            "audio_url": audio_url,
            "speaker_labels": True,
        }
        if language:
            payload["language_code"] = language
        resp = await client.post(_TRANSCRIPT_URL, headers=headers, json=payload)
        resp.raise_for_status()
        return str(resp.json()["id"])

    async def _poll(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        transcript_id: str,
    ) -> dict[str, object]:
        """Poll until transcription completes or times out."""
        elapsed = 0.0
        while elapsed < _POLL_TIMEOUT_SEC:
            resp = await client.get(f"{_TRANSCRIPT_URL}/{transcript_id}", headers=headers)
            resp.raise_for_status()
            data: dict[str, object] = resp.json()
            status = data.get("status")

            if status == "completed":
                return data
            if status == "error":
                error_msg = data.get("error", "Unknown transcription error")
                raise RuntimeError(f"AssemblyAI transcription failed: {error_msg}")

            await asyncio.sleep(_POLL_INTERVAL_SEC)
            elapsed += _POLL_INTERVAL_SEC

        raise RuntimeError(f"AssemblyAI transcription timed out after {_POLL_TIMEOUT_SEC}s")

    def _parse_segments(self, result: dict[str, object]) -> list[TranscriptSegmentData]:
        """Extract transcript segments from the API response."""
        utterances = result.get("utterances", [])
        if not isinstance(utterances, list) or not utterances:
            words = result.get("words", [])
            if isinstance(words, list) and words:
                return self._segments_from_words(words)
            text = result.get("text", "")
            if isinstance(text, str) and text:
                return [{"start_ms": 0, "end_ms": 0, "text": text}]
            return []

        segments: list[TranscriptSegmentData] = []
        for utt in utterances:
            if not isinstance(utt, dict):
                continue
            segments.append(
                {
                    "start_ms": int(utt.get("start", 0)),
                    "end_ms": int(utt.get("end", 0)),
                    "text": str(utt.get("text", "")).strip(),
                }
            )
        return segments

    def _segments_from_words(self, words: list[object]) -> list[TranscriptSegmentData]:
        """Fallback: group words into segments (when utterances unavailable)."""
        if not words:
            return []
        segments: list[TranscriptSegmentData] = []
        current_words: list[str] = []
        start_ms = 0
        end_ms = 0
        for w in words:
            if not isinstance(w, dict):
                continue
            if not current_words:
                start_ms = int(w.get("start", 0))
            current_words.append(str(w.get("text", "")))
            end_ms = int(w.get("end", 0))
            if len(current_words) >= 20:
                segments.append(
                    {
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "text": " ".join(current_words).strip(),
                    }
                )
                current_words = []
        if current_words:
            segments.append(
                {
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "text": " ".join(current_words).strip(),
                }
            )
        return segments

    def _parse_turns(self, result: dict[str, object]) -> list[DiarizationTurn]:
        """Extract speaker-labeled diarization turns from the utterances."""
        utterances = result.get("utterances", [])
        if not isinstance(utterances, list):
            return []
        turns: list[DiarizationTurn] = []
        for utt in utterances:
            if not isinstance(utt, dict):
                continue
            speaker = str(utt.get("speaker", "unknown"))
            turns.append(
                {
                    "start_ms": int(utt.get("start", 0)),
                    "end_ms": int(utt.get("end", 0)),
                    "speaker": speaker,
                }
            )
        return turns

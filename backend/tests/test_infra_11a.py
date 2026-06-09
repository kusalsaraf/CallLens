"""Tests for Phase 11A — AssemblyAI transcription and S3 storage.

All network/AWS calls are mocked; no real keys, network, or broker required.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from calllens.transcription.assemblyai import (
    AssemblyAITranscriber,
    _cached_diarization_turns,
    pop_cached_turns,
)
from calllens.transcription.base import DiarizationTurn
from calllens.transcription.merge import merge
from calllens.transcription.passthrough_diarizer import PassthroughDiarizer

# ── Fixtures ──────────────────────────────────────────────────────────────────

CANNED_ASSEMBLYAI_RESPONSE: dict[str, Any] = {
    "id": "test-transcript-id",
    "status": "completed",
    "text": "Hello there. I have a billing issue. Let me help you.",
    "utterances": [
        {
            "speaker": "A",
            "start": 0,
            "end": 3200,
            "text": "Hello there, thank you for calling support.",
        },
        {
            "speaker": "B",
            "start": 3400,
            "end": 6800,
            "text": "Hi, I have a billing issue with my account.",
        },
        {
            "speaker": "A",
            "start": 7000,
            "end": 11000,
            "text": "Let me help you with that right away.",
        },
    ],
}


def _make_response(status_code: int, body: dict[str, Any]) -> httpx.Response:
    """Create an httpx.Response with a dummy request attached."""
    resp = httpx.Response(
        status_code,
        json=body,
        request=httpx.Request("POST", "https://api.assemblyai.com/test"),
    )
    return resp


def _mock_httpx_responses(
    *,
    upload_url: str = "https://cdn.assemblyai.com/upload/test-audio",
    transcript_id: str = "test-transcript-id",
    poll_response: dict[str, Any] | None = None,
    poll_status_sequence: list[str] | None = None,
    error_message: str | None = None,
) -> list[httpx.Response]:
    """Build a sequence of httpx.Response objects for AssemblyAI API calls."""
    responses: list[httpx.Response] = []

    responses.append(_make_response(200, {"upload_url": upload_url}))
    responses.append(_make_response(200, {"id": transcript_id}))

    if poll_status_sequence:
        for status in poll_status_sequence:
            if status == "error":
                resp_body: dict[str, Any] = {
                    "id": transcript_id,
                    "status": "error",
                    "error": error_message or "Test error",
                }
            elif status == "completed":
                resp_body = poll_response or CANNED_ASSEMBLYAI_RESPONSE
            else:
                resp_body = {"id": transcript_id, "status": status}
            responses.append(_make_response(200, resp_body))
    else:
        final = poll_response or CANNED_ASSEMBLYAI_RESPONSE
        responses.append(_make_response(200, final))

    return responses


# ── AssemblyAI Transcriber ────────────────────────────────────────────────────


class TestAssemblyAITranscriber:
    """Tests for AssemblyAITranscriber with mocked httpx."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        _cached_diarization_turns.clear()

    @pytest.fixture
    def audio_path(self, tmp_path: Path) -> Path:
        p = tmp_path / "test.wav"
        p.write_bytes(b"fake audio data")
        return p

    async def test_parses_utterances_into_segments(self, audio_path: Path) -> None:
        """Mocked httpx client returns diarized response → segments parsed."""
        responses = _mock_httpx_responses()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=[responses[0], responses[1]])
        mock_client.get = AsyncMock(return_value=responses[2])
        mock_client.aclose = AsyncMock()

        with patch("calllens.transcription.assemblyai.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(assemblyai_api_key="test-key")
            transcriber = AssemblyAITranscriber(client=mock_client)
            segments = await transcriber.transcribe(audio_path)

        assert len(segments) == 3
        assert segments[0]["text"] == "Hello there, thank you for calling support."
        assert segments[0]["start_ms"] == 0
        assert segments[0]["end_ms"] == 3200
        assert segments[1]["start_ms"] == 3400
        assert segments[2]["text"] == "Let me help you with that right away."

    async def test_caches_diarization_turns(self, audio_path: Path) -> None:
        """After transcribe(), diarization turns are cached for passthrough."""
        responses = _mock_httpx_responses()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=[responses[0], responses[1]])
        mock_client.get = AsyncMock(return_value=responses[2])
        mock_client.aclose = AsyncMock()

        with patch("calllens.transcription.assemblyai.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(assemblyai_api_key="test-key")
            transcriber = AssemblyAITranscriber(client=mock_client)
            await transcriber.transcribe(audio_path)

        cached = pop_cached_turns(str(audio_path))
        assert cached is not None
        assert len(cached) == 3
        assert cached[0]["speaker"] == "A"
        assert cached[1]["speaker"] == "B"

    async def test_passthrough_maps_speakers_to_agent_customer(self, audio_path: Path) -> None:
        """PassthroughDiarizer + merge maps A/B → agent/customer."""
        responses = _mock_httpx_responses()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=[responses[0], responses[1]])
        mock_client.get = AsyncMock(return_value=responses[2])
        mock_client.aclose = AsyncMock()

        with patch("calllens.transcription.assemblyai.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(assemblyai_api_key="test-key")
            transcriber = AssemblyAITranscriber(client=mock_client)
            segments = await transcriber.transcribe(audio_path)

        diarizer = PassthroughDiarizer()
        turns = await diarizer.diarize(audio_path)

        merged = merge(segments, turns)
        assert len(merged) == 3
        speakers = {m["speaker"] for m in merged}
        assert speakers == {"agent", "customer"}
        assert merged[0]["speaker"] == "agent"
        assert merged[1]["speaker"] == "customer"
        assert merged[2]["speaker"] == "agent"

    async def test_error_response_raises_runtime_error(self, audio_path: Path) -> None:
        """AssemblyAI error status raises RuntimeError with message."""
        responses = _mock_httpx_responses(
            poll_status_sequence=["error"],
            error_message="Audio too short",
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=[responses[0], responses[1]])
        mock_client.get = AsyncMock(return_value=responses[2])
        mock_client.aclose = AsyncMock()

        with patch("calllens.transcription.assemblyai.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(assemblyai_api_key="test-key")
            transcriber = AssemblyAITranscriber(client=mock_client)
            with pytest.raises(RuntimeError, match="Audio too short"):
                await transcriber.transcribe(audio_path)

    async def test_polls_until_completed(self, audio_path: Path) -> None:
        """Transcriber polls through queued/processing before completing."""
        responses = _mock_httpx_responses(
            poll_status_sequence=["queued", "processing", "completed"],
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=[responses[0], responses[1]])
        mock_client.get = AsyncMock(side_effect=responses[2:])
        mock_client.aclose = AsyncMock()

        with (
            patch("calllens.transcription.assemblyai.get_settings") as mock_settings,
            patch("calllens.transcription.assemblyai.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.return_value = MagicMock(assemblyai_api_key="test-key")
            transcriber = AssemblyAITranscriber(client=mock_client)
            segments = await transcriber.transcribe(audio_path)

        assert len(segments) == 3
        assert mock_client.get.call_count == 3

    async def test_missing_api_key_raises(self, audio_path: Path) -> None:
        """Selecting assemblyai without API key raises ValueError."""
        with patch("calllens.transcription.assemblyai.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(assemblyai_api_key="")
            transcriber = AssemblyAITranscriber()
            with pytest.raises(ValueError, match="ASSEMBLYAI_API_KEY"):
                await transcriber.transcribe(audio_path)


class TestPassthroughDiarizer:
    """Tests for PassthroughDiarizer fallback behavior."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        _cached_diarization_turns.clear()

    async def test_fallback_single_speaker_when_no_cache(self, tmp_path: Path) -> None:
        """Without cached turns, falls back to a single NullDiarizer-style turn."""
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"x")
        diarizer = PassthroughDiarizer()
        turns = await diarizer.diarize(audio)
        assert len(turns) == 1
        assert turns[0]["speaker"] == "SPEAKER_00"

    async def test_returns_cached_turns(self, tmp_path: Path) -> None:
        """Returns cached diarization turns and removes them from cache."""
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"x")
        cached: list[DiarizationTurn] = [
            {"start_ms": 0, "end_ms": 3000, "speaker": "A"},
            {"start_ms": 3000, "end_ms": 6000, "speaker": "B"},
        ]
        _cached_diarization_turns[str(audio)] = cached

        diarizer = PassthroughDiarizer()
        turns = await diarizer.diarize(audio)
        assert len(turns) == 2
        assert turns[0]["speaker"] == "A"

        assert pop_cached_turns(str(audio)) is None


# ── S3 Storage ────────────────────────────────────────────────────────────────


class TestS3Storage:
    """Tests for S3Storage using moto (mock AWS)."""

    @pytest.fixture
    def s3_bucket(self) -> str:
        return "test-calllens-audio"

    @pytest.fixture
    def s3_client(self, s3_bucket: str) -> Any:
        """Create a mocked S3 client using moto."""
        import boto3
        from moto import mock_aws

        with mock_aws():
            client = boto3.client("s3", region_name="us-east-1")
            client.create_bucket(Bucket=s3_bucket)
            yield client

    @pytest.fixture
    def storage(self, s3_bucket: str, s3_client: Any) -> Any:
        from calllens.storage.s3 import S3Storage

        return S3Storage(bucket=s3_bucket, client=s3_client)

    async def test_save_then_exists(self, storage: Any) -> None:
        """After save(), exists() returns True."""
        await storage.save(b"hello world", "test/audio.wav")
        assert await storage.exists("test/audio.wav") is True

    async def test_exists_false_for_missing(self, storage: Any) -> None:
        """exists() returns False for a non-existent key."""
        assert await storage.exists("no/such/key.wav") is False

    async def test_open_stream_returns_bytes(self, storage: Any) -> None:
        """open_stream() yields the saved data."""
        data = b"hello world data for streaming"
        await storage.save(data, "stream-test.wav")

        chunks: list[bytes] = []
        async for chunk in storage.open_stream("stream-test.wav"):
            chunks.append(chunk)
        assert b"".join(chunks) == data

    async def test_open_stream_range(self, storage: Any) -> None:
        """open_stream() with start/end yields a byte range."""
        data = b"0123456789abcdef"
        await storage.save(data, "range-test.wav")

        chunks: list[bytes] = []
        async for chunk in storage.open_stream("range-test.wav", start=4, end=10):
            chunks.append(chunk)
        assert b"".join(chunks) == b"456789"

    async def test_file_size(self, storage: Any) -> None:
        """file_size() returns the correct byte count."""
        data = b"x" * 1234
        await storage.save(data, "size-test.wav")
        assert await storage.file_size("size-test.wav") == 1234

    async def test_delete_then_not_exists(self, storage: Any) -> None:
        """After delete(), exists() returns False."""
        await storage.save(b"temp", "delete-me.wav")
        assert await storage.exists("delete-me.wav") is True
        await storage.delete("delete-me.wav")
        assert await storage.exists("delete-me.wav") is False


# ── Factories ─────────────────────────────────────────────────────────────────


class TestFactories:
    """Tests for factory functions with various provider settings."""

    def test_assemblyai_factory_returns_transcriber(self) -> None:
        """get_transcriber() returns AssemblyAITranscriber when configured."""
        with patch("calllens.transcription.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                transcriber_provider="assemblyai",
                assemblyai_api_key="test-key",
            )
            from calllens.transcription.factory import get_transcriber

            t = get_transcriber()
            assert type(t).__name__ == "AssemblyAITranscriber"

    def test_assemblyai_without_key_raises(self) -> None:
        """get_transcriber() raises ValueError without API key."""
        with patch("calllens.transcription.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                transcriber_provider="assemblyai",
                assemblyai_api_key="",
            )
            from calllens.transcription.factory import get_transcriber

            with pytest.raises(ValueError, match="ASSEMBLYAI_API_KEY"):
                get_transcriber()

    def test_assemblyai_implies_passthrough_diarizer(self) -> None:
        """get_diarizer() returns PassthroughDiarizer when transcriber=assemblyai."""
        with patch("calllens.transcription.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                transcriber_provider="assemblyai",
                diarizer_provider="null",
            )
            from calllens.transcription.factory import get_diarizer

            d = get_diarizer()
            assert type(d).__name__ == "PassthroughDiarizer"

    def test_s3_factory_returns_storage(self) -> None:
        """get_storage() returns S3Storage when configured."""
        with patch("calllens.storage.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                storage_backend="s3",
                s3_bucket="test-bucket",
            )
            from calllens.storage.factory import get_storage

            s = get_storage()
            assert type(s).__name__ == "S3Storage"

    def test_s3_without_bucket_raises(self) -> None:
        """get_storage() raises ValueError without S3_BUCKET."""
        with patch("calllens.storage.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                storage_backend="s3",
                s3_bucket="",
            )
            from calllens.storage.factory import get_storage

            with pytest.raises(ValueError, match="S3_BUCKET"):
                get_storage()

    def test_defaults_return_stub_local(self) -> None:
        """Default settings return StubTranscriber and LocalStorage."""
        with patch("calllens.transcription.factory.get_settings") as mock_t:
            mock_t.return_value = MagicMock(transcriber_provider="stub")
            from calllens.transcription.factory import get_transcriber

            assert type(get_transcriber()).__name__ == "StubTranscriber"

        with patch("calllens.storage.factory.get_settings") as mock_s:
            mock_s.return_value = MagicMock(
                storage_backend="local",
                local_storage_dir=Path("/tmp/calllens/audio"),
            )
            from calllens.storage.factory import get_storage

            assert type(get_storage()).__name__ == "LocalStorage"


# ── Audio Endpoint with S3 (mocked) ─────────────────────────────────────────


class TestAudioEndpointS3:
    """Test the /calls/{id}/audio endpoint streams correctly from S3."""

    @pytest.fixture
    def s3_bucket(self) -> str:
        return "test-audio-endpoint"

    @pytest.fixture
    def s3_client(self, s3_bucket: str) -> Any:
        import boto3
        from moto import mock_aws

        with mock_aws():
            client = boto3.client("s3", region_name="us-east-1")
            client.create_bucket(Bucket=s3_bucket)
            yield client

    async def test_s3_range_request(self, s3_client: Any, s3_bucket: str) -> None:
        """S3Storage streams the correct byte range for Range requests."""
        from calllens.storage.s3 import S3Storage

        storage = S3Storage(bucket=s3_bucket, client=s3_client)
        audio_data = b"A" * 100 + b"B" * 100 + b"C" * 100
        await storage.save(audio_data, "call.mp3")

        chunks: list[bytes] = []
        async for chunk in storage.open_stream("call.mp3", start=100, end=200):
            chunks.append(chunk)
        result = b"".join(chunks)
        assert result == b"B" * 100

    async def test_s3_full_stream(self, s3_client: Any, s3_bucket: str) -> None:
        """S3Storage streams full content without Range."""
        from calllens.storage.s3 import S3Storage

        storage = S3Storage(bucket=s3_bucket, client=s3_client)
        audio_data = b"full audio content here"
        await storage.save(audio_data, "full.mp3")

        chunks: list[bytes] = []
        async for chunk in storage.open_stream("full.mp3"):
            chunks.append(chunk)
        assert b"".join(chunks) == audio_data


# ── Regression: stub/local paths ──────────────────────────────────────────────


class TestRegression:
    """Verify existing stub/local paths remain unchanged."""

    async def test_stub_transcriber_unchanged(self) -> None:
        """StubTranscriber still returns 5 canned segments."""
        from calllens.transcription.stub import StubTranscriber

        t = StubTranscriber()
        segments = await t.transcribe(Path("/dev/null"))
        assert len(segments) == 5
        assert segments[0]["text"] == "Hello, thank you for calling support."

    async def test_null_diarizer_unchanged(self) -> None:
        """NullDiarizer still returns a single speaker turn."""
        from calllens.transcription.null_diarizer import NullDiarizer

        d = NullDiarizer()
        turns = await d.diarize(Path("/dev/null"))
        assert len(turns) == 1
        assert turns[0]["speaker"] == "SPEAKER_00"

    async def test_local_storage_round_trip(self, tmp_path: Path) -> None:
        """LocalStorage save/exists/open_stream/delete still works."""
        from calllens.storage.local import LocalStorage

        storage = LocalStorage(root=tmp_path)
        data = b"test local data"
        await storage.save(data, "local-test.wav")
        assert await storage.exists("local-test.wav") is True

        chunks: list[bytes] = []
        async for chunk in storage.open_stream("local-test.wav"):
            chunks.append(chunk)
        assert b"".join(chunks) == data

        await storage.delete("local-test.wav")
        assert await storage.exists("local-test.wav") is False

    async def test_merge_with_null_diarizer(self) -> None:
        """merge() with NullDiarizer turns maps all segments to 'agent'."""
        from calllens.transcription.null_diarizer import NullDiarizer
        from calllens.transcription.stub import StubTranscriber

        t = StubTranscriber()
        d = NullDiarizer()
        segments = await t.transcribe(Path("/dev/null"))
        turns = await d.diarize(Path("/dev/null"))
        merged = merge(segments, turns)
        assert len(merged) == 5
        assert all(m["speaker"] == "agent" for m in merged)

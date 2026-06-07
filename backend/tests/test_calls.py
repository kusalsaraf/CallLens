"""Tests for the calls API and run_call_pipeline service."""

import uuid
from pathlib import Path
from unittest import mock

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from calllens.db.models.call import Call, CallStatus
from calllens.db.models.transcript import Transcript
from calllens.services.call_pipeline import run_call_pipeline
from calllens.storage.local import LocalStorage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _wav_upload(wav_bytes: bytes, filename: str = "call.wav") -> dict[str, object]:
    return {"file": (filename, wav_bytes, "audio/wav")}


# ---------------------------------------------------------------------------
# Upload — validation
# ---------------------------------------------------------------------------


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_upload_rejects_wrong_mime(
    mock_task: mock.Mock, client: AsyncClient, auth_token: str
) -> None:
    """Upload of a non-audio file is rejected with 422."""
    # JSON bytes: magic identifies as application/json
    json_bytes = b'{"key": "value"}'
    resp = await client.post(
        "/api/v1/calls/",
        files={"file": ("data.json", json_bytes, "application/json")},
        headers=_auth_headers(auth_token),
    )
    assert resp.status_code == 422
    assert "Unsupported file type" in resp.json()["message"]
    mock_task.delay.assert_not_called()


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_upload_rejects_empty_file(
    mock_task: mock.Mock, client: AsyncClient, auth_token: str
) -> None:
    """Upload of an empty file is rejected with 422."""
    resp = await client.post(
        "/api/v1/calls/",
        files={"file": ("empty.wav", b"", "audio/wav")},
        headers=_auth_headers(auth_token),
    )
    assert resp.status_code == 422
    assert "empty" in resp.json()["message"].lower()
    mock_task.delay.assert_not_called()


async def test_upload_rejects_oversized_file(client: AsyncClient, auth_token: str) -> None:
    """Upload that exceeds MAX_UPLOAD_MB is rejected with 422."""
    from calllens.core import config as cfg_module

    cfg_module.get_settings.cache_clear()
    import os

    os.environ["MAX_UPLOAD_MB"] = "0"
    try:
        with mock.patch("calllens.api.v1.calls.process_call_task") as mock_task:
            resp = await client.post(
                "/api/v1/calls/",
                files={"file": ("big.wav", b"x" * 10, "audio/wav")},
                headers=_auth_headers(auth_token),
            )
        assert resp.status_code == 422
        assert "maximum" in resp.json()["message"].lower()
        mock_task.delay.assert_not_called()
    finally:
        del os.environ["MAX_UPLOAD_MB"]
        cfg_module.get_settings.cache_clear()


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_upload_accepts_valid_wav(
    mock_task: mock.Mock,
    client: AsyncClient,
    auth_token: str,
    wav_fixture: bytes,
) -> None:
    """Valid WAV upload creates a Call in 'uploaded' status and enqueues the task."""
    resp = await client.post(
        "/api/v1/calls/",
        files=_wav_upload(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "uploaded"
    assert body["original_filename"] == "call.wav"
    assert uuid.UUID(body["id"])
    mock_task.delay.assert_called_once_with(body["id"])


# ---------------------------------------------------------------------------
# Upload — auth required
# ---------------------------------------------------------------------------


async def test_upload_requires_auth(client: AsyncClient, wav_fixture: bytes) -> None:
    """Upload without token returns 401."""
    resp = await client.post(
        "/api/v1/calls/",
        files=_wav_upload(wav_fixture),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Pipeline service tests (no broker, no Redis)
# ---------------------------------------------------------------------------


async def test_pipeline_produces_transcript(
    db_engine: object,
    tmp_path: Path,
    wav_fixture: bytes,
) -> None:
    """run_call_pipeline with Stub/Null produces a Transcript + sets status transcribed."""
    from calllens.services.seed import get_default_agent, seed_defaults

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )
    async with factory() as db:
        await seed_defaults(db)
        agent = await get_default_agent(db)

    storage = LocalStorage(root=tmp_path)
    call_id = uuid.uuid4()
    key = f"{call_id}.wav"
    await storage.save(wav_fixture, key)

    async with factory() as db:
        call = Call(
            id=call_id,
            status=CallStatus.uploaded,
            storage_key=key,
            original_filename="call.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.commit()

    with (
        mock.patch("calllens.services.call_pipeline.get_storage", return_value=storage),
        mock.patch("calllens.services.call_pipeline.get_session_factory", return_value=factory),
        mock.patch(
            "calllens.services.call_pipeline.publish_call_event",
            new=mock.AsyncMock(),
        ),
    ):
        await run_call_pipeline(call_id)

    async with factory() as db:
        result = await db.execute(select(Call).where(Call.id == call_id))
        updated_call = result.scalar_one()
        assert updated_call.status == CallStatus.transcribed

        t_result = await db.execute(select(Transcript).where(Transcript.call_id == call_id))
        transcript = t_result.scalar_one()
        assert transcript is not None

        from calllens.db.models.segment import TranscriptSegment

        seg_result = await db.execute(
            select(TranscriptSegment).where(TranscriptSegment.transcript_id == transcript.id)
        )
        segments = seg_result.scalars().all()
        assert len(segments) == 5  # StubTranscriber returns 5 canned segments
        assert segments[0].speaker in ("agent", "customer", "unknown")


async def test_pipeline_sets_failed_on_error(
    db_engine: object,
    tmp_path: Path,
    wav_fixture: bytes,
) -> None:
    """run_call_pipeline sets status=failed when the transcriber raises."""
    from calllens.services.seed import get_default_agent, seed_defaults

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )
    async with factory() as db:
        await seed_defaults(db)
        agent = await get_default_agent(db)

    storage = LocalStorage(root=tmp_path)
    call_id = uuid.uuid4()
    key = f"{call_id}.wav"
    await storage.save(wav_fixture, key)

    async with factory() as db:
        call = Call(
            id=call_id,
            status=CallStatus.uploaded,
            storage_key=key,
            original_filename="call.wav",
            agent_id=agent.id,
        )
        db.add(call)
        await db.commit()

    async def _boom(audio_path: Path, language: str | None = None) -> list:
        raise RuntimeError("transcriber exploded")

    failing_transcriber = mock.MagicMock()
    failing_transcriber.transcribe = _boom

    with (
        mock.patch("calllens.services.call_pipeline.get_storage", return_value=storage),
        mock.patch("calllens.services.call_pipeline.get_session_factory", return_value=factory),
        mock.patch(
            "calllens.services.call_pipeline.publish_call_event",
            new=mock.AsyncMock(),
        ),
        mock.patch(
            "calllens.services.call_pipeline.get_transcriber",
            return_value=failing_transcriber,
        ),
    ):
        await run_call_pipeline(call_id)

    async with factory() as db:
        result = await db.execute(select(Call).where(Call.id == call_id))
        updated = result.scalar_one()
        assert updated.status == CallStatus.failed
        assert updated.status_detail is not None
        assert "transcriber exploded" in updated.status_detail


# ---------------------------------------------------------------------------
# List / Get
# ---------------------------------------------------------------------------


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_list_calls(
    mock_task: mock.Mock,
    client: AsyncClient,
    auth_token: str,
    wav_fixture: bytes,
) -> None:
    """GET /calls returns a paginated list including the uploaded call."""
    await client.post(
        "/api/v1/calls/",
        files=_wav_upload(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    resp = await client.get("/api/v1/calls/", headers=_auth_headers(auth_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert isinstance(body["items"], list)
    assert body["items"][0]["status"] == "uploaded"


async def test_list_calls_requires_auth(client: AsyncClient) -> None:
    """GET /calls without token returns 401."""
    resp = await client.get("/api/v1/calls/")
    assert resp.status_code == 401


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_get_call_detail(
    mock_task: mock.Mock,
    client: AsyncClient,
    auth_token: str,
    wav_fixture: bytes,
) -> None:
    """GET /calls/{id} returns the correct call."""
    upload = await client.post(
        "/api/v1/calls/",
        files=_wav_upload(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    call_id = upload.json()["id"]
    resp = await client.get(f"/api/v1/calls/{call_id}", headers=_auth_headers(auth_token))
    assert resp.status_code == 200
    assert resp.json()["id"] == call_id


async def test_get_call_not_found(client: AsyncClient, auth_token: str) -> None:
    """GET /calls/{unknown} returns 404."""
    resp = await client.get(f"/api/v1/calls/{uuid.uuid4()}", headers=_auth_headers(auth_token))
    assert resp.status_code == 404


async def test_get_call_requires_auth(client: AsyncClient) -> None:
    """GET /calls/{unknown} without token returns 401."""
    resp = await client.get(f"/api/v1/calls/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


async def test_get_transcript_not_yet_available(
    client: AsyncClient, auth_token: str, wav_fixture: bytes
) -> None:
    """GET /calls/{id}/transcript returns 404 before pipeline completes."""
    with mock.patch("calllens.api.v1.calls.process_call_task"):
        upload = await client.post(
            "/api/v1/calls/",
            files=_wav_upload(wav_fixture),
            headers=_auth_headers(auth_token),
        )
    call_id = upload.json()["id"]
    resp = await client.get(
        f"/api/v1/calls/{call_id}/transcript", headers=_auth_headers(auth_token)
    )
    assert resp.status_code == 404


async def test_get_transcript_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/calls/{uuid.uuid4()}/transcript")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Audio streaming
# ---------------------------------------------------------------------------


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_audio_full_stream(
    mock_task: mock.Mock,
    client: AsyncClient,
    auth_token: str,
    wav_fixture: bytes,
) -> None:
    """GET /calls/{id}/audio returns 200 with the full audio bytes."""
    upload = await client.post(
        "/api/v1/calls/",
        files=_wav_upload(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    call_id = upload.json()["id"]
    resp = await client.get(f"/api/v1/calls/{call_id}/audio", headers=_auth_headers(auth_token))
    assert resp.status_code == 200
    assert resp.content == wav_fixture


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_audio_range_request(
    mock_task: mock.Mock,
    client: AsyncClient,
    auth_token: str,
    wav_fixture: bytes,
) -> None:
    """GET /calls/{id}/audio with Range header returns 206 partial content."""
    upload = await client.post(
        "/api/v1/calls/",
        files=_wav_upload(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    call_id = upload.json()["id"]
    resp = await client.get(
        f"/api/v1/calls/{call_id}/audio",
        headers={**_auth_headers(auth_token), "Range": "bytes=0-99"},
    )
    assert resp.status_code == 206
    assert len(resp.content) == 100
    assert "content-range" in resp.headers


async def test_audio_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/calls/{uuid.uuid4()}/audio")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# SSE events (terminal status — no Redis needed)
# ---------------------------------------------------------------------------


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_events_terminal_status(
    mock_task: mock.Mock,
    client: AsyncClient,
    auth_token: str,
    wav_fixture: bytes,
    db_engine: object,
) -> None:
    """SSE for a transcribed call emits current status and closes without Redis."""
    upload = await client.post(
        "/api/v1/calls/",
        files=_wav_upload(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    call_id = upload.json()["id"]

    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,  # type: ignore[call-arg]
    )
    async with factory() as db:
        await db.execute(
            update(Call).where(Call.id == uuid.UUID(call_id)).values(status=CallStatus.transcribed)
        )
        await db.commit()

    resp = await client.get(
        f"/api/v1/calls/{call_id}/events",
        headers=_auth_headers(auth_token),
    )
    assert resp.status_code == 200
    assert "transcribed" in resp.text


async def test_events_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/calls/{uuid.uuid4()}/events")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_delete_call(
    mock_task: mock.Mock,
    client: AsyncClient,
    auth_token: str,
    wav_fixture: bytes,
) -> None:
    """DELETE /calls/{id} removes the row; subsequent GET returns 404."""
    upload = await client.post(
        "/api/v1/calls/",
        files=_wav_upload(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    call_id = upload.json()["id"]

    delete_resp = await client.delete(f"/api/v1/calls/{call_id}", headers=_auth_headers(auth_token))
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/calls/{call_id}", headers=_auth_headers(auth_token))
    assert get_resp.status_code == 404


async def test_delete_requires_auth(client: AsyncClient) -> None:
    resp = await client.delete(f"/api/v1/calls/{uuid.uuid4()}")
    assert resp.status_code == 401

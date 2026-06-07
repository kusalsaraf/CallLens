# Phase 2A — Async Processing Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the upload, storage, transcription+diarization pipeline, and calls API that forms the async processing backbone of CallLens.

**Architecture:** Files are uploaded via multipart POST, saved to a `StorageBackend`, and a Celery task runs `run_call_pipeline` which transcribes, diarizes, merges, and persists results. Status changes are published to Redis pub/sub and streamed to clients via SSE. Stub/Null providers are the default so the app boots and tests pass without ML dependencies.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Celery+Redis, aiofiles, python-magic, redis.asyncio, pytest-asyncio, httpx

---

## File Map

### New files to create
```
src/calllens/
  db/models/
    team.py               # Team ORM model
    agent.py              # Agent ORM model
    call.py               # Call ORM model + CallStatus enum
    transcript.py         # Transcript ORM model
    segment.py            # TranscriptSegment ORM model
  storage/
    __init__.py
    base.py               # StorageBackend Protocol
    local.py              # LocalStorage (aiofiles)
    s3.py                 # S3Storage stub (NotImplementedError)
    factory.py            # get_storage() factory
  transcription/
    __init__.py
    base.py               # Transcriber + Diarizer Protocols + TypedDicts
    stub.py               # StubTranscriber (canned segments, zero deps)
    null_diarizer.py      # NullDiarizer (single speaker)
    merge.py              # merge() function aligning transcript + diarization
    whisper.py            # FasterWhisperTranscriber (optional group)
    groq_whisper.py       # GroqWhisperTranscriber (optional group)
    pyannote_diarizer.py  # PyannoteDiarizer (optional group)
    factory.py            # get_transcriber() + get_diarizer() factories
  tasks/
    __init__.py
    celery_app.py         # Celery application instance
    pipeline.py           # process_call_task Celery task
  services/
    call_pipeline.py      # run_call_pipeline() async service function
    call_events.py        # publish_call_event() Redis pub/sub helper
    seed.py               # seed_defaults() idempotent seeding
  schemas/
    calls.py              # CallOut, TranscriptOut, SegmentOut, CallListOut
  api/v1/
    calls.py              # All /api/v1/calls endpoints

tests/
  fixtures/
    silence.wav           # 0.5s silent WAV for upload tests
  test_calls.py           # All calls tests
```

### Files to modify
```
pyproject.toml                        # new deps + optional groups + mypy overrides
src/calllens/core/config.py           # new settings fields
src/calllens/db/models/__init__.py    # import new models
src/calllens/main.py                  # lifespan (seeding) + calls router
backend/.env.example                  # new env var docs
tests/conftest.py                     # auth_token + default_agent fixtures
alembic/versions/                     # new migration (auto-generated)
```

---

## Task 1: Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add aiofiles, python-magic to base deps; add optional groups; extend mypy overrides**

Open `pyproject.toml` and apply the following changes:

In `[project]` `dependencies` list, add:
```toml
    "aiofiles>=24.1.0",
    "python-magic>=0.4.27",
```

After the existing `[dependency-groups]` section, add:
```toml
[dependency-groups]
dev = [
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "faker>=25.0.0",
    "aiofiles>=24.1.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "faker>=25.0.0",
]
transcription-local = [
    "faster-whisper>=1.1.0",
    "pyannote.audio>=3.3.0",
    "torchaudio>=2.3.0",
]
transcription-groq = [
    "groq>=0.9.0",
]
```

Add mypy overrides for untyped optional deps — append after the existing `[[tool.mypy.overrides]]` block:
```toml
[[tool.mypy.overrides]]
module = ["magic"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["faster_whisper.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["pyannote.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["torchaudio.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["groq.*"]
ignore_missing_imports = true
```

- [ ] **Step 2: Install new base deps**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
uv sync
```

Expected: resolves and installs `aiofiles` and `python-magic`. Verify:
```bash
uv run python -c "import aiofiles, magic; print('ok')"
```

---

## Task 2: Config

**Files:**
- Modify: `src/calllens/core/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Extend Settings with new fields**

Replace the body of `src/calllens/core/config.py` with:

```python
"""Application configuration via pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables.

    All secrets must be supplied via environment; no defaults for sensitive values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://calllens:calllens@localhost:5432/calllens"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION-use-a-random-32-plus-byte-secret"
    jwt_access_expiry_seconds: int = 900  # 15 minutes
    jwt_refresh_expiry_seconds: int = 604800  # 7 days

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    local_storage_dir: Path = Path("/tmp/calllens/audio")
    max_upload_mb: int = 200

    # Allowed audio MIME types (sniffed, not from Content-Type header)
    allowed_audio_mimes: list[str] = [
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
        "audio/ogg",
        "audio/flac",
        "audio/mp4",
        "audio/x-m4a",
        "audio/webm",
        "video/mp4",
    ]

    # Transcription
    transcriber_provider: Literal["stub", "faster_whisper", "groq"] = "stub"
    diarizer_provider: Literal["null", "pyannote"] = "null"
    huggingface_token: str = ""
    groq_api_key: str = ""

    @field_validator("cors_origins", "allowed_audio_mimes", mode="before")
    @classmethod
    def parse_csv_list(cls, v: object) -> object:
        """Parse comma-separated string into a list."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
```

- [ ] **Step 2: Update .env.example**

Append to `.env.example`:
```
# Storage
STORAGE_BACKEND=local
LOCAL_STORAGE_DIR=/tmp/calllens/audio
MAX_UPLOAD_MB=200

# Transcription
TRANSCRIBER_PROVIDER=stub
DIARIZER_PROVIDER=null

# Optional: set TRANSCRIBER_PROVIDER=faster_whisper or groq
# Optional: set DIARIZER_PROVIDER=pyannote (requires accepting model terms on HF)
HUGGINGFACE_TOKEN=
GROQ_API_KEY=
```

- [ ] **Step 3: Verify config loads**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
uv run python -c "from calllens.core.config import get_settings; s = get_settings(); print(s.transcriber_provider, s.storage_backend)"
```

Expected: `stub local`

---

## Task 3: ORM Models

**Files:**
- Create: `src/calllens/db/models/team.py`
- Create: `src/calllens/db/models/agent.py`
- Create: `src/calllens/db/models/call.py`
- Create: `src/calllens/db/models/transcript.py`
- Create: `src/calllens/db/models/segment.py`
- Modify: `src/calllens/db/models/__init__.py`

- [ ] **Step 1: Create Team model**

`src/calllens/db/models/team.py`:
```python
"""Team ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calllens.db.base import Base


class Team(Base):
    """A team that owns agents."""

    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agents: Mapped[list["Agent"]] = relationship("Agent", back_populates="team")  # noqa: F821
```

- [ ] **Step 2: Create Agent model**

`src/calllens/db/models/agent.py`:
```python
"""Agent ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calllens.db.base import Base
from calllens.db.models.team import Team


class Agent(Base):
    """A call-centre agent belonging to a team."""

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    team_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    team: Mapped[Team] = relationship("Team", back_populates="agents")
    calls: Mapped[list["Call"]] = relationship("Call", back_populates="agent")  # noqa: F821
```

- [ ] **Step 3: Create Call model**

`src/calllens/db/models/call.py`:
```python
"""Call ORM model."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calllens.db.base import Base
from calllens.db.models.agent import Agent


class CallStatus(enum.Enum):
    """Lifecycle states of a call recording."""

    uploaded = "uploaded"
    transcribing = "transcribing"
    diarizing = "diarizing"
    transcribed = "transcribed"
    failed = "failed"


_TERMINAL_STATUSES = {CallStatus.transcribed, CallStatus.failed}


def is_terminal(status: CallStatus) -> bool:
    """Return True if status requires no further processing."""
    return status in _TERMINAL_STATUSES


class Call(Base):
    """A call recording with its processing lifecycle."""

    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[CallStatus] = mapped_column(
        Enum(CallStatus, name="callstatus"), default=CallStatus.uploaded
    )
    storage_key: Mapped[str] = mapped_column(String(512))
    original_filename: Mapped[str] = mapped_column(String(512))
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    agent: Mapped[Agent | None] = relationship("Agent", back_populates="calls")
    transcript: Mapped["Transcript | None"] = relationship(  # noqa: F821
        "Transcript", back_populates="call", uselist=False
    )
```

- [ ] **Step 4: Create Transcript model**

`src/calllens/db/models/transcript.py`:
```python
"""Transcript ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calllens.db.base import Base
from calllens.db.models.call import Call


class Transcript(Base):
    """Full transcript associated with a call."""

    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), unique=True
    )
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    call: Mapped[Call] = relationship("Call", back_populates="transcript")
    segments: Mapped[list["TranscriptSegment"]] = relationship(  # noqa: F821
        "TranscriptSegment",
        back_populates="transcript",
        order_by="TranscriptSegment.sequence",
    )
```

- [ ] **Step 5: Create TranscriptSegment model**

`src/calllens/db/models/segment.py`:
```python
"""TranscriptSegment ORM model."""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY as PgArray
from sqlalchemy.orm import Mapped, mapped_column, relationship

from calllens.db.base import Base
from calllens.db.models.transcript import Transcript


class TranscriptSegment(Base):
    """A single timed text segment in a transcript, with speaker attribution."""

    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    speaker: Mapped[str] = mapped_column(String(64))
    # Nullable — populated in a later phase via pgvector
    embedding: Mapped[list[float] | None] = mapped_column(PgArray(Float), nullable=True)

    transcript: Mapped[Transcript] = relationship("Transcript", back_populates="segments")
```

- [ ] **Step 6: Update models __init__.py**

`src/calllens/db/models/__init__.py`:
```python
"""ORM model registry — import here to ensure models are registered on Base.metadata."""

from calllens.db.models.agent import Agent
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.team import Team
from calllens.db.models.transcript import Transcript
from calllens.db.models.user import User

__all__ = ["Agent", "Call", "CallStatus", "Team", "Transcript", "TranscriptSegment", "User"]
```

- [ ] **Step 7: Verify models import cleanly**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
uv run python -c "import calllens.db.models; print('models ok')"
```

Expected: `models ok`

---

## Task 4: Alembic Migration

**Files:**
- Create: `alembic/versions/<timestamp>_phase2a_models.py` (auto-generated)

- [ ] **Step 1: Generate migration**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
uv run alembic revision --autogenerate -m "phase2a_models"
```

Expected: creates a new file in `alembic/versions/` with `upgrade()` containing `create_table` calls for `teams`, `agents`, `calls`, `transcripts`, `transcript_segments`.

- [ ] **Step 2: Review the generated migration**

Open the new migration file and verify it contains:
- `create_table("teams", ...)` with `id`, `name`, `created_at` columns
- `create_table("agents", ...)` with `id`, `name`, `team_id`, `created_at`
- `create_enum("callstatus", ...)` or inline enum for the `status` column
- `create_table("calls", ...)` with all columns including nullable `agent_id`, `duration_seconds`, `status_detail`
- `create_table("transcripts", ...)` with unique `call_id`
- `create_table("transcript_segments", ...)` with nullable `embedding` ARRAY column

If any table is missing, the model `__init__.py` import is likely missing — fix it and re-run.

- [ ] **Step 3: Apply migration**

Ensure PostgreSQL is running (via `docker compose up -d` from the repo root), then:
```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
uv run alembic upgrade head
```

Expected output ends with: `Running upgrade a192367e747a -> <new_rev>, phase2a_models`

- [ ] **Step 4: Verify schema**

```bash
uv run python -c "
from sqlalchemy import create_engine, inspect, text
from calllens.core.config import get_settings
s = get_settings()
# Use sync URL for inspection
url = s.database_url.replace('postgresql+asyncpg', 'postgresql+psycopg2')
# Actually use asyncpg-compatible check
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
async def check():
    e = create_async_engine(s.database_url)
    async with e.connect() as conn:
        result = await conn.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_schema='public'\"))
        print([r[0] for r in result])
    await e.dispose()
asyncio.run(check())
"
```

Expected: list includes `teams`, `agents`, `calls`, `transcripts`, `transcript_segments`.

---

## Task 5: Seed Service + App Lifespan

**Files:**
- Create: `src/calllens/services/seed.py`
- Modify: `src/calllens/main.py`

- [ ] **Step 1: Create seed service**

`src/calllens/services/seed.py`:
```python
"""Idempotent seeding of required default rows."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.db.models.agent import Agent
from calllens.db.models.team import Team

logger = logging.getLogger(__name__)

_DEFAULT_TEAM_NAME = "Default Team"
_DEFAULT_AGENT_NAME = "Default Agent"


async def seed_defaults(db: AsyncSession) -> None:
    """Create the default Team and Agent if they do not exist.

    Args:
        db: An open async database session.
    """
    team_result = await db.execute(select(Team).where(Team.name == _DEFAULT_TEAM_NAME))
    team = team_result.scalar_one_or_none()

    if team is None:
        team = Team(name=_DEFAULT_TEAM_NAME)
        db.add(team)
        await db.flush()
        logger.info("Created default team", extra={"team_id": str(team.id)})

    agent_result = await db.execute(
        select(Agent).where(Agent.name == _DEFAULT_AGENT_NAME, Agent.team_id == team.id)
    )
    agent = agent_result.scalar_one_or_none()

    if agent is None:
        agent = Agent(name=_DEFAULT_AGENT_NAME, team_id=team.id)
        db.add(agent)
        logger.info("Created default agent", extra={"agent_id": str(agent.id)})

    await db.commit()


async def get_default_agent(db: AsyncSession) -> Agent:
    """Return the default agent, raising ValueError if seeding was skipped.

    Args:
        db: An open async database session.

    Returns:
        The default Agent row.

    Raises:
        ValueError: If no agent exists (should not happen after seeding).
    """
    result = await db.execute(select(Agent).where(Agent.name == _DEFAULT_AGENT_NAME).limit(1))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise ValueError("No default agent found — run seed_defaults first")
    return agent
```

- [ ] **Step 2: Add lifespan to main.py**

Replace `src/calllens/main.py` with:
```python
"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from calllens.api.v1 import auth, health
from calllens.core.config import get_settings
from calllens.core.exceptions import register_exception_handlers
from calllens.core.logging import CorrelationIDMiddleware, configure_logging
from calllens.db.session import get_session_factory
from calllens.services.seed import seed_defaults

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Run startup/shutdown tasks around the application lifespan."""
    factory = get_session_factory()
    async with factory() as db:
        await seed_defaults(db)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A fully configured ``FastAPI`` instance ready to serve requests.
    """
    settings = get_settings()

    configure_logging(level=logging.DEBUG if settings.app_debug else logging.INFO)

    app = FastAPI(
        title="CallLens API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
    )

    # Middleware (registered in reverse order of execution)
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Routers
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")

    logger.info("CallLens API started", extra={"env": settings.app_env})

    return app


app = create_app()
```

NOTE: The calls router import is intentionally omitted here — it will be added in Task 11 once the calls module exists.

---

## Task 6: Storage Layer

**Files:**
- Create: `src/calllens/storage/__init__.py`
- Create: `src/calllens/storage/base.py`
- Create: `src/calllens/storage/local.py`
- Create: `src/calllens/storage/s3.py`
- Create: `src/calllens/storage/factory.py`

- [ ] **Step 1: Create storage package**

`src/calllens/storage/__init__.py`:
```python
"""Storage backends for call audio files."""
```

- [ ] **Step 2: Create StorageBackend Protocol**

`src/calllens/storage/base.py`:
```python
"""StorageBackend Protocol — the contract that all storage implementations must satisfy."""

from collections.abc import AsyncGenerator
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Abstract interface for audio file storage."""

    async def save(self, data: bytes, key: str) -> str:
        """Persist bytes under the given key, returning the key.

        Args:
            data: Raw file bytes to persist.
            key: Storage key (path-like, generated by the upload handler).

        Returns:
            The key used to store the file.
        """
        ...

    async def open_stream(
        self, key: str, *, start: int = 0, end: int | None = None
    ) -> AsyncGenerator[bytes, None]:
        """Yield file bytes, optionally constrained to a byte range.

        Args:
            key: Storage key of the file to stream.
            start: First byte offset (inclusive, default 0).
            end: Last byte offset (exclusive). None means stream to EOF.

        Yields:
            Chunks of file bytes.
        """
        ...

    async def file_size(self, key: str) -> int:
        """Return the total byte size of the stored file.

        Args:
            key: Storage key of the file.

        Returns:
            File size in bytes.
        """
        ...

    async def delete(self, key: str) -> None:
        """Remove the stored file.

        Args:
            key: Storage key of the file to delete.
        """
        ...

    async def exists(self, key: str) -> bool:
        """Check whether a file exists.

        Args:
            key: Storage key to probe.

        Returns:
            True if the file exists.
        """
        ...
```

- [ ] **Step 3: Create LocalStorage**

`src/calllens/storage/local.py`:
```python
"""Local filesystem storage backend using aiofiles."""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import aiofiles
import aiofiles.os

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024  # 64 KiB


class LocalStorage:
    """Stores files on the local filesystem under a configurable root directory.

    Args:
        root: Directory under which all files are stored.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        return self._root / key

    async def save(self, data: bytes, key: str) -> str:
        """Write bytes to disk, creating parent directories as needed.

        Args:
            data: File bytes to write.
            key: Relative path under the storage root.

        Returns:
            The key passed in.
        """
        target = self._path(key)
        await aiofiles.os.makedirs(str(target.parent), exist_ok=True)
        async with aiofiles.open(target, "wb") as f:
            await f.write(data)
        logger.debug("Saved file", extra={"key": key, "bytes": len(data)})
        return key

    async def open_stream(
        self, key: str, *, start: int = 0, end: int | None = None
    ) -> AsyncGenerator[bytes, None]:
        """Yield file bytes within the requested byte range.

        Args:
            key: Storage key of the file.
            start: First byte offset (inclusive).
            end: Last byte offset (exclusive). None streams to EOF.

        Yields:
            Chunks of up to 64 KiB.
        """
        target = self._path(key)
        async with aiofiles.open(target, "rb") as f:
            if start:
                await f.seek(start)
            remaining = (end - start) if end is not None else None
            while True:
                to_read = _CHUNK_SIZE if remaining is None else min(_CHUNK_SIZE, remaining)
                chunk = await f.read(to_read)
                if not chunk:
                    break
                yield chunk
                if remaining is not None:
                    remaining -= len(chunk)
                    if remaining <= 0:
                        break

    async def file_size(self, key: str) -> int:
        """Return the byte size of a stored file.

        Args:
            key: Storage key.

        Returns:
            File size in bytes.
        """
        stat = await aiofiles.os.stat(str(self._path(key)))
        return stat.st_size

    async def delete(self, key: str) -> None:
        """Delete a stored file.

        Args:
            key: Storage key.
        """
        path = self._path(key)
        await aiofiles.os.remove(str(path))
        logger.debug("Deleted file", extra={"key": key})

    async def exists(self, key: str) -> bool:
        """Check whether a file exists.

        Args:
            key: Storage key.

        Returns:
            True if the file exists.
        """
        return Path(self._path(key)).exists()
```

- [ ] **Step 4: Create S3Storage stub**

`src/calllens/storage/s3.py`:
```python
"""S3 storage backend stub — requires the optional boto3 dependency."""

from collections.abc import AsyncGenerator


class S3Storage:
    """AWS S3 storage backend.

    Requires boto3 to be installed. Currently a stub; implement when
    STORAGE_BACKEND=s3 is needed.

    Args:
        bucket: S3 bucket name.
        prefix: Key prefix prepended to every storage key.
    """

    def __init__(self, bucket: str, prefix: str = "") -> None:
        self._bucket = bucket
        self._prefix = prefix

    async def save(self, data: bytes, key: str) -> str:
        """TODO: upload bytes to S3 via boto3."""
        raise NotImplementedError("S3Storage.save is not yet implemented")

    async def open_stream(
        self, key: str, *, start: int = 0, end: int | None = None
    ) -> AsyncGenerator[bytes, None]:
        """TODO: stream object from S3 with Range header support."""
        raise NotImplementedError("S3Storage.open_stream is not yet implemented")
        yield b""  # makes this a generator for the type checker

    async def file_size(self, key: str) -> int:
        """TODO: return object size via HeadObject."""
        raise NotImplementedError("S3Storage.file_size is not yet implemented")

    async def delete(self, key: str) -> None:
        """TODO: delete object from S3."""
        raise NotImplementedError("S3Storage.delete is not yet implemented")

    async def exists(self, key: str) -> bool:
        """TODO: check object existence via HeadObject."""
        raise NotImplementedError("S3Storage.exists is not yet implemented")
```

- [ ] **Step 5: Create storage factory**

`src/calllens/storage/factory.py`:
```python
"""Factory for selecting the configured storage backend."""

from calllens.core.config import get_settings
from calllens.storage.base import StorageBackend


def get_storage() -> StorageBackend:
    """Return a StorageBackend instance configured from application settings.

    Returns:
        The appropriate StorageBackend for the configured STORAGE_BACKEND.

    Raises:
        ValueError: If STORAGE_BACKEND is set to an unrecognised value.
    """
    settings = get_settings()
    if settings.storage_backend == "local":
        from calllens.storage.local import LocalStorage

        return LocalStorage(root=settings.local_storage_dir)  # type: ignore[return-value]
    if settings.storage_backend == "s3":
        from calllens.storage.s3 import S3Storage

        return S3Storage(bucket="calllens")  # type: ignore[return-value]
    raise ValueError(f"Unknown storage backend: {settings.storage_backend!r}")
```

- [ ] **Step 6: Smoke-test storage**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
uv run python -c "
import asyncio
from calllens.storage.factory import get_storage

async def test():
    s = get_storage()
    await s.save(b'hello', 'test/hello.txt')
    size = await s.file_size('test/hello.txt')
    assert size == 5, f'Expected 5, got {size}'
    chunks = []
    async for chunk in s.open_stream('test/hello.txt'):
        chunks.append(chunk)
    assert b''.join(chunks) == b'hello'
    await s.delete('test/hello.txt')
    print('storage ok')

asyncio.run(test())
"
```

Expected: `storage ok`

---

## Task 7: Transcription Layer

**Files:**
- Create: `src/calllens/transcription/__init__.py`
- Create: `src/calllens/transcription/base.py`
- Create: `src/calllens/transcription/stub.py`
- Create: `src/calllens/transcription/null_diarizer.py`
- Create: `src/calllens/transcription/merge.py`
- Create: `src/calllens/transcription/whisper.py`
- Create: `src/calllens/transcription/groq_whisper.py`
- Create: `src/calllens/transcription/pyannote_diarizer.py`
- Create: `src/calllens/transcription/factory.py`

- [ ] **Step 1: Create transcription package**

`src/calllens/transcription/__init__.py`:
```python
"""Transcription and diarization providers."""
```

- [ ] **Step 2: Create protocols and TypedDicts**

`src/calllens/transcription/base.py`:
```python
"""Transcriber and Diarizer protocols plus shared data types."""

from pathlib import Path
from typing import Protocol, TypedDict


class TranscriptSegmentData(TypedDict):
    """A single transcribed segment with timing."""

    start_ms: int
    end_ms: int
    text: str


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
```

- [ ] **Step 3: Create StubTranscriber**

`src/calllens/transcription/stub.py`:
```python
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
```

- [ ] **Step 4: Create NullDiarizer**

`src/calllens/transcription/null_diarizer.py`:
```python
"""NullDiarizer — treats the entire recording as a single speaker."""

from pathlib import Path

from calllens.transcription.base import DiarizationTurn

_SINGLE_SPEAKER = "SPEAKER_00"


class NullDiarizer:
    """Returns a single speaker turn spanning the whole file.

    Used as the default diarizer when no diarization is needed. The stub
    transcriber drives the actual timing.
    """

    async def diarize(self, audio_path: Path) -> list[DiarizationTurn]:
        """Return a single speaker turn of effectively infinite duration.

        Args:
            audio_path: Ignored.

        Returns:
            A single DiarizationTurn spanning 0ms to a large sentinel value.
        """
        return [{"start_ms": 0, "end_ms": 2**31 - 1, "speaker": _SINGLE_SPEAKER}]
```

- [ ] **Step 5: Create merge function**

`src/calllens/transcription/merge.py`:
```python
"""Merge transcript segments with diarization turns and assign speaker roles."""

from collections import Counter

from calllens.transcription.base import DiarizationTurn, TranscriptSegmentData


def _overlap_ms(
    seg_start: int,
    seg_end: int,
    turn_start: int,
    turn_end: int,
) -> int:
    """Compute the overlap in milliseconds between a segment and a turn."""
    return max(0, min(seg_end, turn_end) - max(seg_start, turn_start))


def _best_speaker(segment: TranscriptSegmentData, turns: list[DiarizationTurn]) -> str:
    """Find the diarization turn with the greatest temporal overlap."""
    best = max(
        turns,
        key=lambda t: _overlap_ms(
            segment["start_ms"], segment["end_ms"], t["start_ms"], t["end_ms"]
        ),
        default=None,
    )
    if best is None:
        return "unknown"
    return best["speaker"]


def merge(
    segments: list[TranscriptSegmentData],
    turns: list[DiarizationTurn],
) -> list[dict[str, object]]:
    """Align transcript segments with diarization turns and label speakers.

    The two most frequent raw speaker labels are mapped to "agent" and
    "customer" (most frequent → "agent", second → "customer"). All others
    are labelled "unknown".

    Args:
        segments: Ordered transcript segments from the Transcriber.
        turns: Speaker turns from the Diarizer.

    Returns:
        List of dicts with keys: start_ms, end_ms, text, speaker, sequence.
        Speaker values are "agent", "customer", or "unknown".
    """
    raw: list[dict[str, object]] = []
    for idx, seg in enumerate(segments):
        raw.append(
            {
                "start_ms": seg["start_ms"],
                "end_ms": seg["end_ms"],
                "text": seg["text"],
                "speaker": _best_speaker(seg, turns),
                "sequence": idx,
            }
        )

    # Map raw speaker labels to semantic roles
    counter: Counter[str] = Counter(str(r["speaker"]) for r in raw)
    most_common = [label for label, _ in counter.most_common(2)]

    role_map: dict[str, str] = {}
    if len(most_common) >= 1:
        role_map[most_common[0]] = "agent"
    if len(most_common) >= 2:
        role_map[most_common[1]] = "customer"

    for item in raw:
        raw_speaker = str(item["speaker"])
        item["speaker"] = role_map.get(raw_speaker, "unknown")

    return raw
```

- [ ] **Step 6: Create optional FasterWhisperTranscriber**

`src/calllens/transcription/whisper.py`:
```python
"""FasterWhisperTranscriber — requires the transcription-local optional group."""

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
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "faster-whisper is not installed. "
                "Run: uv sync --group transcription-local"
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
        import asyncio

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
```

- [ ] **Step 7: Create optional GroqWhisperTranscriber**

`src/calllens/transcription/groq_whisper.py`:
```python
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
        data: dict[str, str | bytes] = {
            "model": self._model,
            "response_format": "verbose_json",
        }
        if language:
            data["language"] = language

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                _GROQ_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                files={"file": (audio_path.name, audio_bytes)},
                data=data,
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
```

- [ ] **Step 8: Create optional PyannoteDiarizer**

`src/calllens/transcription/pyannote_diarizer.py`:
```python
"""PyannoteDiarizer — speaker diarization via pyannote.audio.

Prerequisites:
  1. pip install calllens[transcription-local]  (or uv sync --group transcription-local)
  2. Accept the pyannote/speaker-diarization-3.1 model terms at
     https://huggingface.co/pyannote/speaker-diarization-3.1
  3. Set HUGGINGFACE_TOKEN in your environment.
"""

from pathlib import Path

from calllens.core.config import get_settings
from calllens.transcription.base import DiarizationTurn


class PyannoteDiarizer:
    """Speaker diarization using pyannote.audio 3.x.

    Args:
        model_id: HuggingFace model identifier.
    """

    def __init__(
        self, model_id: str = "pyannote/speaker-diarization-3.1"
    ) -> None:
        settings = get_settings()
        try:
            from pyannote.audio import Pipeline  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "pyannote.audio is not installed. "
                "Run: uv sync --group transcription-local"
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
        import asyncio

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
```

- [ ] **Step 9: Create transcription factories**

`src/calllens/transcription/factory.py`:
```python
"""Factories that select Transcriber and Diarizer from application settings."""

from calllens.core.config import get_settings
from calllens.transcription.base import Diarizer, Transcriber


def get_transcriber() -> Transcriber:
    """Return the configured Transcriber implementation.

    Returns:
        A Transcriber selected by TRANSCRIBER_PROVIDER setting.

    Raises:
        ValueError: If TRANSCRIBER_PROVIDER is unrecognised.
    """
    settings = get_settings()
    if settings.transcriber_provider == "stub":
        from calllens.transcription.stub import StubTranscriber

        return StubTranscriber()  # type: ignore[return-value]
    if settings.transcriber_provider == "faster_whisper":
        from calllens.transcription.whisper import FasterWhisperTranscriber

        return FasterWhisperTranscriber()  # type: ignore[return-value]
    if settings.transcriber_provider == "groq":
        from calllens.transcription.groq_whisper import GroqWhisperTranscriber

        return GroqWhisperTranscriber()  # type: ignore[return-value]
    raise ValueError(f"Unknown transcriber provider: {settings.transcriber_provider!r}")


def get_diarizer() -> Diarizer:
    """Return the configured Diarizer implementation.

    Returns:
        A Diarizer selected by DIARIZER_PROVIDER setting.

    Raises:
        ValueError: If DIARIZER_PROVIDER is unrecognised.
    """
    settings = get_settings()
    if settings.diarizer_provider == "null":
        from calllens.transcription.null_diarizer import NullDiarizer

        return NullDiarizer()  # type: ignore[return-value]
    if settings.diarizer_provider == "pyannote":
        from calllens.transcription.pyannote_diarizer import PyannoteDiarizer

        return PyannoteDiarizer()  # type: ignore[return-value]
    raise ValueError(f"Unknown diarizer provider: {settings.diarizer_provider!r}")
```

- [ ] **Step 10: Smoke-test transcription layer**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
uv run python -c "
import asyncio
from pathlib import Path
from calllens.transcription.factory import get_transcriber, get_diarizer
from calllens.transcription.merge import merge

async def test():
    t = get_transcriber()
    d = get_diarizer()
    segments = await t.transcribe(Path('/dev/null'))
    turns = await d.diarize(Path('/dev/null'))
    merged = merge(segments, turns)
    assert len(merged) == 5
    assert merged[0]['speaker'] in ('agent', 'customer', 'unknown')
    print('transcription layer ok')

asyncio.run(test())
"
```

Expected: `transcription layer ok`

---

## Task 8: Celery App

**Files:**
- Create: `src/calllens/tasks/__init__.py`
- Create: `src/calllens/tasks/celery_app.py`

- [ ] **Step 1: Create tasks package**

`src/calllens/tasks/__init__.py`:
```python
"""Celery tasks for asynchronous call processing."""
```

- [ ] **Step 2: Create Celery application**

`src/calllens/tasks/celery_app.py`:
```python
"""Celery application instance wired to Redis broker and result backend."""

from celery import Celery

from calllens.core.config import get_settings


def _make_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "calllens",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["calllens.tasks.pipeline"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )
    return app


celery_app = _make_celery()
```

---

## Task 9: Pipeline Service + Celery Task

**Files:**
- Create: `src/calllens/services/call_events.py`
- Create: `src/calllens/services/call_pipeline.py`
- Create: `src/calllens/tasks/pipeline.py`

- [ ] **Step 1: Create Redis pub/sub event publisher**

`src/calllens/services/call_events.py`:
```python
"""Publish call status changes to Redis pub/sub."""

import json
import logging
import uuid

import redis.asyncio as aioredis

from calllens.core.config import get_settings

logger = logging.getLogger(__name__)


async def publish_call_event(
    call_id: uuid.UUID,
    status: str,
    detail: str | None = None,
) -> None:
    """Publish a status-change event to the call's Redis channel.

    Args:
        call_id: ID of the call whose status changed.
        status: New status string (value of CallStatus enum).
        detail: Optional error detail; present only on failure.
    """
    settings = get_settings()
    channel = f"call:{call_id}:events"
    payload = json.dumps({"status": status, "detail": detail})
    r: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=False)
    try:
        await r.publish(channel, payload)
        logger.debug("Published event", extra={"channel": channel, "status": status})
    finally:
        await r.aclose()
```

- [ ] **Step 2: Create pipeline service**

`src/calllens/services/call_pipeline.py`:
```python
"""Call processing pipeline: transcription, diarization, and persistence."""

import logging
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.db.session import get_session_factory
from calllens.services.call_events import publish_call_event
from calllens.storage.factory import get_storage
from calllens.transcription.factory import get_diarizer, get_transcriber
from calllens.transcription.merge import merge

logger = logging.getLogger(__name__)


async def _set_status(
    db: AsyncSession,
    call: Call,
    status: CallStatus,
    detail: str | None = None,
) -> None:
    call.status = status
    call.status_detail = detail
    await db.commit()
    await db.refresh(call)
    await publish_call_event(call.id, status.value, detail)


async def run_call_pipeline(call_id: uuid.UUID) -> None:
    """Run the full transcription and diarization pipeline for a call.

    Loads the call from the database, runs transcription followed by diarization,
    merges the results, persists Transcript and TranscriptSegment rows, and
    updates the call status at each stage. On any error, sets status to failed
    and records the exception message in status_detail.

    Args:
        call_id: UUID of the Call row to process.
    """
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(Call).where(Call.id == call_id))
        call = result.scalar_one_or_none()
        if call is None:
            logger.error("Pipeline called with unknown call_id", extra={"call_id": str(call_id)})
            return

        try:
            await _set_status(db, call, CallStatus.transcribing)

            # Fetch audio bytes from storage into a temp file
            storage = get_storage()
            audio_bytes: list[bytes] = []
            async for chunk in storage.open_stream(call.storage_key):
                audio_bytes.append(chunk)
            raw_audio = b"".join(audio_bytes)

            suffix = Path(call.storage_key).suffix or ".audio"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                tf.write(raw_audio)
                audio_path = Path(tf.name)

            try:
                transcriber = get_transcriber()
                transcript_segments = await transcriber.transcribe(audio_path)

                await _set_status(db, call, CallStatus.diarizing)

                diarizer = get_diarizer()
                diarization_turns = await diarizer.diarize(audio_path)
            finally:
                audio_path.unlink(missing_ok=True)

            merged = merge(transcript_segments, diarization_turns)

            # Persist Transcript + TranscriptSegments
            transcript = Transcript(call_id=call.id, language=None)
            db.add(transcript)
            await db.flush()

            for item in merged:
                seg = TranscriptSegment(
                    transcript_id=transcript.id,
                    sequence=int(item["sequence"]),
                    start_ms=int(item["start_ms"]),
                    end_ms=int(item["end_ms"]),
                    text=str(item["text"]),
                    speaker=str(item["speaker"]),
                )
                db.add(seg)

            await db.flush()
            await _set_status(db, call, CallStatus.transcribed)
            logger.info("Pipeline complete", extra={"call_id": str(call_id)})

        except Exception as exc:
            logger.exception("Pipeline failed", extra={"call_id": str(call_id)})
            try:
                await _set_status(db, call, CallStatus.failed, detail=str(exc))
            except Exception:
                logger.exception(
                    "Failed to update call status to failed",
                    extra={"call_id": str(call_id)},
                )
```

- [ ] **Step 3: Create Celery task**

`src/calllens/tasks/pipeline.py`:
```python
"""Celery task wrapping run_call_pipeline."""

import asyncio
import logging
import uuid

from celery import Task

from calllens.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="calllens.tasks.pipeline.process_call")
def process_call_task(self: Task, call_id: str) -> None:
    """Run the call processing pipeline asynchronously in a Celery worker.

    Args:
        self: The bound Celery Task instance.
        call_id: String representation of the Call UUID.
    """
    from calllens.services.call_pipeline import run_call_pipeline

    logger.info("Starting pipeline task", extra={"call_id": call_id})
    asyncio.run(run_call_pipeline(uuid.UUID(call_id)))
```

---

## Task 10: Call Schemas

**Files:**
- Create: `src/calllens/schemas/calls.py`

- [ ] **Step 1: Create call schemas**

`src/calllens/schemas/calls.py`:
```python
"""Pydantic schemas for the calls API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CallOut(BaseModel):
    """Public representation of a Call row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    original_filename: str
    duration_seconds: float | None
    agent_id: uuid.UUID | None
    status_detail: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_call(cls, call: object) -> "CallOut":
        """Build from a Call ORM instance, serializing the status enum.

        Args:
            call: A Call ORM model instance.

        Returns:
            Serialised CallOut.
        """
        from calllens.db.models.call import Call as CallModel

        c = call  # type: ignore[assignment]
        assert isinstance(c, CallModel)
        return cls(
            id=c.id,
            status=c.status.value,
            original_filename=c.original_filename,
            duration_seconds=c.duration_seconds,
            agent_id=c.agent_id,
            status_detail=c.status_detail,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )


class SegmentOut(BaseModel):
    """A single transcript segment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    start_ms: int
    end_ms: int
    text: str
    speaker: str


class TranscriptOut(BaseModel):
    """A full transcript with ordered segments."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_id: uuid.UUID
    language: str | None
    segments: list[SegmentOut]
    created_at: datetime


class CallListOut(BaseModel):
    """Paginated list of calls."""

    items: list[CallOut]
    total: int
    page: int
    page_size: int
```

---

## Task 11: Calls API Router

**Files:**
- Create: `src/calllens/api/v1/calls.py`
- Modify: `src/calllens/main.py`

- [ ] **Step 1: Create calls router**

`src/calllens/api/v1/calls.py`:
```python
"""Calls API — upload, list, detail, transcript, audio streaming, SSE, delete."""

import json
import logging
import uuid
from pathlib import Path
from typing import Annotated

import magic
from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.config import get_settings
from calllens.core.deps import get_current_user
from calllens.core.exceptions import NotFoundError, ValidationError
from calllens.db.models.call import Call, CallStatus, is_terminal
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.schemas.calls import CallListOut, CallOut, TranscriptOut
from calllens.services.seed import get_default_agent
from calllens.storage.factory import get_storage
from calllens.tasks.pipeline import process_call_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calls", tags=["calls"])


def _call_storage_key(call_id: uuid.UUID, original_filename: str) -> str:
    ext = Path(original_filename).suffix.lower()
    return f"{call_id}{ext}"


async def _get_call_or_404(call_id: uuid.UUID, db: AsyncSession) -> Call:
    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    if call is None:
        raise NotFoundError(f"Call {call_id} not found")
    return call


# ---------------------------------------------------------------------------
# POST / — multipart upload
# ---------------------------------------------------------------------------


@router.post("/", response_model=CallOut, status_code=201)
async def upload_call(
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CallOut:
    """Accept a multipart audio upload, save to storage, enqueue pipeline.

    Args:
        file: The uploaded audio file.
        db: Database session.
        current_user: Authenticated user (enforces auth guard).

    Returns:
        The newly created Call in "uploaded" status.

    Raises:
        ValidationError: If the file is missing, empty, oversized, or wrong MIME type.
    """
    settings = get_settings()

    if file.filename is None or file.filename == "":
        raise ValidationError("No file provided")

    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise ValidationError("Uploaded file is empty")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise ValidationError(
            f"File exceeds maximum allowed size of {settings.max_upload_mb} MB"
        )

    sniffed_mime = magic.from_buffer(audio_bytes[:4096], mime=True)
    if sniffed_mime not in settings.allowed_audio_mimes:
        raise ValidationError(
            f"Unsupported file type: {sniffed_mime!r}. "
            f"Allowed: {settings.allowed_audio_mimes}"
        )

    call_id = uuid.uuid4()
    storage = get_storage()
    key = _call_storage_key(call_id, file.filename)
    await storage.save(audio_bytes, key)

    agent = await get_default_agent(db)

    call = Call(
        id=call_id,
        status=CallStatus.uploaded,
        storage_key=key,
        original_filename=file.filename,
        agent_id=agent.id,
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    process_call_task.delay(str(call.id))
    logger.info("Call uploaded", extra={"call_id": str(call.id), "mime": sniffed_mime})

    return CallOut.from_orm_call(call)


# ---------------------------------------------------------------------------
# GET / — list calls
# ---------------------------------------------------------------------------


@router.get("/", response_model=CallListOut)
async def list_calls(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: str | None = None,
    agent_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> CallListOut:
    """List calls newest-first with optional filters and pagination.

    Args:
        db: Database session.
        current_user: Authenticated user.
        status: Optional CallStatus value to filter by.
        agent_id: Optional agent UUID to filter by.
        page: 1-based page number.
        page_size: Items per page (max 100).

    Returns:
        Paginated list of CallOut.
    """
    page_size = min(page_size, 100)
    offset = (page - 1) * page_size

    stmt = select(Call).order_by(Call.created_at.desc())
    if status is not None:
        try:
            stmt = stmt.where(Call.status == CallStatus(status))
        except ValueError:
            raise ValidationError(f"Invalid status: {status!r}")
    if agent_id is not None:
        stmt = stmt.where(Call.agent_id == agent_id)

    total_result = await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = total_result.scalar_one()

    rows_result = await db.execute(stmt.offset(offset).limit(page_size))
    calls = rows_result.scalars().all()

    return CallListOut(
        items=[CallOut.from_orm_call(c) for c in calls],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# GET /{id} — call detail
# ---------------------------------------------------------------------------


@router.get("/{call_id}", response_model=CallOut)
async def get_call(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CallOut:
    """Return detail for a single call.

    Args:
        call_id: UUID of the target call.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        CallOut for the requested call.
    """
    call = await _get_call_or_404(call_id, db)
    return CallOut.from_orm_call(call)


# ---------------------------------------------------------------------------
# GET /{id}/transcript
# ---------------------------------------------------------------------------


@router.get("/{call_id}/transcript", response_model=TranscriptOut)
async def get_transcript(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TranscriptOut:
    """Return the transcript and ordered segments for a call.

    Args:
        call_id: UUID of the target call.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        TranscriptOut with all segments in sequence order.

    Raises:
        NotFoundError: If the call does not exist or has no transcript yet.
    """
    await _get_call_or_404(call_id, db)

    t_result = await db.execute(select(Transcript).where(Transcript.call_id == call_id))
    transcript = t_result.scalar_one_or_none()
    if transcript is None:
        raise NotFoundError("Transcript not yet available for this call")

    seg_result = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.sequence)
    )
    segments = seg_result.scalars().all()

    return TranscriptOut(
        id=transcript.id,
        call_id=transcript.call_id,
        language=transcript.language,
        segments=[
            {  # type: ignore[arg-type]
                "id": seg.id,
                "sequence": seg.sequence,
                "start_ms": seg.start_ms,
                "end_ms": seg.end_ms,
                "text": seg.text,
                "speaker": seg.speaker,
            }
            for seg in segments
        ],
        created_at=transcript.created_at,
    )


# ---------------------------------------------------------------------------
# GET /{id}/audio — streaming with Range support
# ---------------------------------------------------------------------------


@router.get("/{call_id}/audio")
async def stream_audio(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    range: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """Stream stored audio, honouring HTTP Range requests.

    Args:
        call_id: UUID of the call whose audio to stream.
        db: Database session.
        current_user: Authenticated user.
        range: Optional HTTP Range header (e.g. "bytes=0-1023").

    Returns:
        StreamingResponse — 206 for range requests, 200 for full stream.
    """
    call = await _get_call_or_404(call_id, db)
    storage = get_storage()

    if not await storage.exists(call.storage_key):
        raise NotFoundError("Audio file not found in storage")

    total_size = await storage.file_size(call.storage_key)
    media_type = "audio/mpeg"

    start = 0
    end: int | None = None
    status_code = 200
    headers: dict[str, str] = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(total_size),
    }

    if range:
        # Parse "bytes=<start>-<end>"
        try:
            byte_range = range.replace("bytes=", "")
            parts = byte_range.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) + 1 if parts[1] else total_size
        except (ValueError, IndexError):
            raise HTTPException(status_code=416, detail="Invalid Range header")

        if start >= total_size or (end is not None and start >= end):
            raise HTTPException(
                status_code=416,
                detail="Range not satisfiable",
                headers={"Content-Range": f"bytes */{total_size}"},
            )

        end = min(end or total_size, total_size)
        content_length = end - start
        status_code = 206
        headers["Content-Range"] = f"bytes {start}-{end - 1}/{total_size}"
        headers["Content-Length"] = str(content_length)

    async def _generator():  # type: ignore[return]
        async for chunk in storage.open_stream(call.storage_key, start=start, end=end):
            yield chunk

    return StreamingResponse(
        _generator(),
        status_code=status_code,
        media_type=media_type,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# GET /{id}/events — SSE
# ---------------------------------------------------------------------------


@router.get("/{call_id}/events")
async def call_events(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """Server-Sent Events stream of call status changes.

    Emits the current status immediately on connect, then subscribes to
    Redis pub/sub and forwards updates until a terminal status is reached.

    Args:
        call_id: UUID of the call to monitor.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        text/event-stream StreamingResponse.
    """
    import redis.asyncio as aioredis

    call = await _get_call_or_404(call_id, db)
    settings = get_settings()
    channel = f"call:{call_id}:events"

    current_status = call.status.value
    already_terminal = is_terminal(call.status)

    async def _generator():  # type: ignore[return]
        yield f"data: {json.dumps({'status': current_status})}\n\n"
        if already_terminal:
            return

        r: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=False)
        try:
            async with r.pubsub() as ps:
                await ps.subscribe(channel)
                async for msg in ps.listen():
                    if msg["type"] != "message":
                        continue
                    data_bytes = msg["data"]
                    payload_str = (
                        data_bytes.decode() if isinstance(data_bytes, bytes) else data_bytes
                    )
                    yield f"data: {payload_str}\n\n"
                    parsed = json.loads(payload_str)
                    if parsed.get("status") in ("transcribed", "failed"):
                        break
        finally:
            await r.aclose()

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# DELETE /{id}
# ---------------------------------------------------------------------------


@router.delete("/{call_id}", status_code=204)
async def delete_call(
    call_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a call and its stored audio file.

    Args:
        call_id: UUID of the call to delete.
        db: Database session.
        current_user: Authenticated user.
    """
    call = await _get_call_or_404(call_id, db)
    storage = get_storage()

    if await storage.exists(call.storage_key):
        await storage.delete(call.storage_key)

    await db.delete(call)
    await db.commit()
    logger.info("Call deleted", extra={"call_id": str(call_id)})
```

- [ ] **Step 2: Register calls router in main.py**

In `src/calllens/main.py`, add the calls router import and registration.

Add to the imports section:
```python
from calllens.api.v1 import auth, calls, health
```

Add to the Routers section (after `app.include_router(auth.router, prefix="/api/v1")`):
```python
    app.include_router(calls.router, prefix="/api/v1")
```

- [ ] **Step 3: Verify app loads**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
uv run python -c "from calllens.main import app; print('app ok', len(app.routes), 'routes')"
```

Expected: `app ok <N> routes` where N > 10 (includes calls endpoints).

---

## Task 12: Tests

**Files:**
- Create: `tests/fixtures/silence.wav` (binary, created via script)
- Modify: `tests/conftest.py`
- Create: `tests/test_calls.py`

- [ ] **Step 1: Create WAV fixture file**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
mkdir -p tests/fixtures
uv run python -c "
import io, wave
buf = io.BytesIO()
with wave.open(buf, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes(b'\\x00' * 32000)  # 1 second of silence
buf.seek(0)
with open('tests/fixtures/silence.wav', 'wb') as f:
    f.write(buf.read())
print('WAV fixture created:', len(open('tests/fixtures/silence.wav','rb').read()), 'bytes')
"
```

Expected: `WAV fixture created: <N> bytes`

- [ ] **Step 2: Update conftest.py**

Replace `tests/conftest.py` with:
```python
"""Shared pytest fixtures for the test suite."""

import os
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import calllens.db.models  # noqa: F401 — registers ORM models on Base.metadata
from calllens.db.base import Base
from calllens.db.session import get_db
from calllens.main import app
from calllens.services.seed import seed_defaults

_TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://calllens:calllens@localhost:5432/calllens",
)

_SIGNUP_PAYLOAD = {
    "email": "test@example.com",
    "password": "SecurePass123!",
    "name": "Test User",
}


@pytest_asyncio.fixture
async def db_engine():
    """Create all tables before the test and drop them afterwards."""
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    """HTTP test client with the DB session overridden to the test engine."""
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    # Seed default team/agent into the test DB
    async with factory() as session:
        await seed_defaults(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


async def signup_and_get_token(client: AsyncClient) -> str:
    """Sign up the test user and return the access token.

    Args:
        client: The test HTTP client.

    Returns:
        Bearer access token string.
    """
    resp = await client.post("/api/v1/auth/signup", json=_SIGNUP_PAYLOAD)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient) -> str:
    """Signed-up user access token for use in calls tests."""
    return await signup_and_get_token(client)


@pytest_asyncio.fixture
def wav_fixture() -> bytes:
    """Return the bytes of the silence.wav test fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "silence.wav"
    return fixture_path.read_bytes()
```

- [ ] **Step 3: Create test_calls.py**

`tests/test_calls.py`:
```python
"""Tests for the calls API and the run_call_pipeline service."""

import uuid
from pathlib import Path
from unittest import mock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from calllens.db.models.call import Call, CallStatus
from calllens.db.models.transcript import Transcript
from calllens.services.call_pipeline import run_call_pipeline
from calllens.storage.local import LocalStorage
from tests.conftest import _TEST_DB_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_upload_files(wav_bytes: bytes, filename: str = "call.wav"):
    return {"file": (filename, wav_bytes, "audio/wav")}


# ---------------------------------------------------------------------------
# Upload — validation
# ---------------------------------------------------------------------------


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_upload_rejects_wrong_mime(mock_task: mock.Mock, client: AsyncClient, auth_token: str) -> None:
    """Upload of a non-audio file is rejected with 422."""
    resp = await client.post(
        "/api/v1/calls/",
        files={"file": ("data.json", b'{"key": "value"}', "application/json")},
        headers=_auth_headers(auth_token),
    )
    assert resp.status_code == 422
    assert "Unsupported file type" in resp.json()["message"]
    mock_task.delay.assert_not_called()


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_upload_rejects_empty_file(mock_task: mock.Mock, client: AsyncClient, auth_token: str) -> None:
    """Upload of an empty file is rejected with 422."""
    resp = await client.post(
        "/api/v1/calls/",
        files={"file": ("empty.wav", b"", "audio/wav")},
        headers=_auth_headers(auth_token),
    )
    assert resp.status_code == 422
    assert "empty" in resp.json()["message"].lower()
    mock_task.delay.assert_not_called()


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_upload_rejects_oversized_file(
    mock_task: mock.Mock,
    client: AsyncClient,
    auth_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upload that exceeds MAX_UPLOAD_MB is rejected with 422."""
    from calllens.core import config as cfg_module

    original_get = cfg_module.get_settings

    def _patched_settings():
        s = original_get()
        object.__setattr__(s, "max_upload_mb", 0)
        return s

    monkeypatch.setattr(cfg_module, "get_settings", _patched_settings)

    resp = await client.post(
        "/api/v1/calls/",
        files={"file": ("big.wav", b"x" * 10, "audio/wav")},
        headers=_auth_headers(auth_token),
    )
    assert resp.status_code == 422
    mock_task.delay.assert_not_called()


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
        files=_make_upload_files(wav_fixture),
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
        files=_make_upload_files(wav_fixture),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Pipeline service
# ---------------------------------------------------------------------------


async def test_pipeline_produces_transcript(
    db_engine,
    tmp_path: Path,
    wav_fixture: bytes,
) -> None:
    """run_call_pipeline with Stub/Null produces a Transcript and sets status transcribed."""
    from calllens.core.config import get_settings
    from calllens.services.seed import seed_defaults

    # Use test DB session factory
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        await seed_defaults(db)
        from calllens.services.seed import get_default_agent

        agent = await get_default_agent(db)

    # Point LocalStorage at tmp_path
    storage = LocalStorage(root=tmp_path)
    call_id = uuid.uuid4()
    key = f"{call_id}.wav"
    await storage.save(wav_fixture, key)

    # Create a Call row in the test DB
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

    # Patch storage factory and session factory, mock Redis publish
    with (
        mock.patch("calllens.services.call_pipeline.get_storage", return_value=storage),
        mock.patch("calllens.services.call_pipeline.get_session_factory", return_value=factory),
        mock.patch("calllens.services.call_events.publish_call_event", return_value=None),
    ):
        await run_call_pipeline(call_id)

    async with factory() as db:
        from sqlalchemy import select

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


async def test_pipeline_sets_failed_on_error(
    db_engine,
    tmp_path: Path,
    wav_fixture: bytes,
) -> None:
    """run_call_pipeline sets status=failed when the transcriber raises."""
    from calllens.services.seed import seed_defaults, get_default_agent

    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
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

    async def _boom(audio_path, language=None):
        raise RuntimeError("transcriber exploded")

    with (
        mock.patch("calllens.services.call_pipeline.get_storage", return_value=storage),
        mock.patch("calllens.services.call_pipeline.get_session_factory", return_value=factory),
        mock.patch("calllens.services.call_events.publish_call_event", return_value=None),
        mock.patch(
            "calllens.services.call_pipeline.get_transcriber",
            return_value=mock.AsyncMock(transcribe=_boom),
        ),
    ):
        await run_call_pipeline(call_id)

    async with factory() as db:
        from sqlalchemy import select

        result = await db.execute(select(Call).where(Call.id == call_id))
        updated = result.scalar_one()
        assert updated.status == CallStatus.failed
        assert updated.status_detail is not None
        assert "transcriber exploded" in updated.status_detail


# ---------------------------------------------------------------------------
# List / Get / Transcript
# ---------------------------------------------------------------------------


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_list_calls(mock_task: mock.Mock, client: AsyncClient, auth_token: str, wav_fixture: bytes) -> None:
    """GET /calls returns a paginated list including the uploaded call."""
    await client.post(
        "/api/v1/calls/",
        files=_make_upload_files(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    resp = await client.get("/api/v1/calls/", headers=_auth_headers(auth_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert isinstance(body["items"], list)


async def test_list_calls_requires_auth(client: AsyncClient) -> None:
    """GET /calls without token returns 401."""
    resp = await client.get("/api/v1/calls/")
    assert resp.status_code == 401


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_get_call_detail(mock_task: mock.Mock, client: AsyncClient, auth_token: str, wav_fixture: bytes) -> None:
    """GET /calls/{id} returns the correct call."""
    upload = await client.post(
        "/api/v1/calls/",
        files=_make_upload_files(wav_fixture),
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


async def test_get_transcript_not_yet_available(client: AsyncClient, auth_token: str, wav_fixture: bytes) -> None:
    """GET /calls/{id}/transcript returns 404 before pipeline completes."""
    with mock.patch("calllens.api.v1.calls.process_call_task"):
        upload = await client.post(
            "/api/v1/calls/",
            files=_make_upload_files(wav_fixture),
            headers=_auth_headers(auth_token),
        )
    call_id = upload.json()["id"]
    resp = await client.get(f"/api/v1/calls/{call_id}/transcript", headers=_auth_headers(auth_token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Audio streaming
# ---------------------------------------------------------------------------


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_audio_full_stream(mock_task: mock.Mock, client: AsyncClient, auth_token: str, wav_fixture: bytes) -> None:
    """GET /calls/{id}/audio returns 200 with the audio bytes."""
    upload = await client.post(
        "/api/v1/calls/",
        files=_make_upload_files(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    call_id = upload.json()["id"]
    resp = await client.get(f"/api/v1/calls/{call_id}/audio", headers=_auth_headers(auth_token))
    assert resp.status_code == 200
    assert resp.content == wav_fixture


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_audio_range_request(mock_task: mock.Mock, client: AsyncClient, auth_token: str, wav_fixture: bytes) -> None:
    """GET /calls/{id}/audio with Range header returns 206 partial content."""
    upload = await client.post(
        "/api/v1/calls/",
        files=_make_upload_files(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    call_id = upload.json()["id"]
    resp = await client.get(
        f"/api/v1/calls/{call_id}/audio",
        headers={**_auth_headers(auth_token), "Range": "bytes=0-99"},
    )
    assert resp.status_code == 206
    assert len(resp.content) == 100
    assert "Content-Range" in resp.headers


async def test_audio_requires_auth(client: AsyncClient) -> None:
    """GET /calls/{unknown}/audio without token returns 401."""
    resp = await client.get(f"/api/v1/calls/{uuid.uuid4()}/audio")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# SSE events endpoint
# ---------------------------------------------------------------------------


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_events_terminal_status_no_redis(
    mock_task: mock.Mock,
    client: AsyncClient,
    auth_token: str,
    wav_fixture: bytes,
    db_engine,
    tmp_path: Path,
) -> None:
    """SSE stream for a transcribed call emits current status and closes without Redis."""
    upload = await client.post(
        "/api/v1/calls/",
        files=_make_upload_files(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    call_id = upload.json()["id"]

    # Force the call to transcribed state directly in DB
    from sqlalchemy import select, update

    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
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


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@mock.patch("calllens.api.v1.calls.process_call_task")
async def test_delete_call(mock_task: mock.Mock, client: AsyncClient, auth_token: str, wav_fixture: bytes) -> None:
    """DELETE /calls/{id} removes the row; subsequent GET returns 404."""
    upload = await client.post(
        "/api/v1/calls/",
        files=_make_upload_files(wav_fixture),
        headers=_auth_headers(auth_token),
    )
    call_id = upload.json()["id"]

    delete_resp = await client.delete(f"/api/v1/calls/{call_id}", headers=_auth_headers(auth_token))
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/calls/{call_id}", headers=_auth_headers(auth_token))
    assert get_resp.status_code == 404


async def test_delete_requires_auth(client: AsyncClient) -> None:
    """DELETE /calls/{unknown} without token returns 401."""
    resp = await client.delete(f"/api/v1/calls/{uuid.uuid4()}")
    assert resp.status_code == 401
```

---

## Task 13: Lint, Type-Check, Tests, Commit

- [ ] **Step 1: Run ruff lint**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
uv run ruff check src/ tests/
```

Expected: No errors. Fix any reported issues before proceeding.

- [ ] **Step 2: Run ruff format check**

```bash
uv run ruff format --check src/ tests/
```

Expected: No issues. If format changes are needed: `uv run ruff format src/ tests/`

- [ ] **Step 3: Run mypy**

```bash
uv run mypy src/
```

Expected: `Success: no issues found`. Common fixes:
- `type: ignore[return-value]` on factory return types (Protocol vs concrete class)
- `type: ignore[arg-type]` where TypedDict merging doesn't perfectly align

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: All tests pass. The test suite runs against the local PostgreSQL (docker-compose must be running). Key test IDs to verify:
- `test_upload_rejects_wrong_mime`
- `test_upload_accepts_valid_wav`
- `test_pipeline_produces_transcript`
- `test_pipeline_sets_failed_on_error`
- `test_audio_range_request`
- `test_delete_call`

- [ ] **Step 5: Verify migration is applied**

```bash
uv run alembic current
```

Expected: shows head revision for the phase2a migration.

- [ ] **Step 6: Update BUILD_LOG.md**

Append to `docs/BUILD_LOG.md`:
```markdown
## Phase 2A — Async Processing Spine (2026-06-07)

### Added
- **Dependencies**: `aiofiles`, `python-magic` in base; optional groups `transcription-local`
  (faster-whisper, pyannote.audio, torchaudio) and `transcription-groq` (groq).
- **Models**: `Team`, `Agent`, `Call` (with `CallStatus` enum), `Transcript`,
  `TranscriptSegment` (embedding column nullable for later pgvector phase).
- **Migration**: Alembic migration creates all Phase 2A tables.
- **Seeding**: `seed_defaults()` idempotently creates Default Team + Agent; called
  from the FastAPI lifespan.
- **Storage**: `StorageBackend` Protocol + `LocalStorage` (aiofiles, async range
  streaming) + `S3Storage` stub + `get_storage()` factory.
- **Transcription**: `Transcriber` / `Diarizer` Protocols + `StubTranscriber` (default,
  zero deps) + `NullDiarizer` (default) + `merge()` function + optional
  `FasterWhisperTranscriber`, `GroqWhisperTranscriber`, `PyannoteDiarizer`.
- **Celery**: `celery_app` wired to Redis; `process_call_task` wraps pipeline service.
- **Pipeline service**: `run_call_pipeline(call_id)` — load → transcribe → diarize →
  merge → persist → set status; publishes status events to Redis pub/sub channel
  `call:{id}:events`.
- **Calls API** (`/api/v1/calls`): POST upload (MIME sniff, size limit), GET list
  (filters + pagination), GET detail, GET transcript, GET audio (Range support),
  GET events (SSE), DELETE.

### Architecture decisions
- Stub/Null providers are the default; heavy ML deps never imported unless explicitly
  configured. App boots and all tests pass without torch/pyannote/groq.
- Pipeline logic lives in a plain `async` service function — Celery task is a thin
  `asyncio.run()` wrapper, making the logic unit-testable without a broker.
- SSE endpoint short-circuits on terminal status without opening a Redis connection,
  keeping tests broker-free.
```

- [ ] **Step 7: Commit**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend
git config user.name "Kusal Saraf"
git config user.email "kusalsaraf5@gmail.com"
cd /Users/kusalsaraf/Desktop/CallLens
git add -A
git commit -m "feat(calls): upload, storage, async transcription+diarization pipeline, and call APIs"
```

---

## Self-Review: Spec Coverage Check

| Spec requirement | Task |
|---|---|
| `aiofiles`, `python-magic` in app group | Task 1 |
| Optional groups `transcription-local`, `transcription-groq` | Task 1 |
| Heavy groups don't affect boot/CI | Task 7 (lazy imports), Task 9 (Stub/Null default) |
| `Team`, `Agent` minimal models | Task 3 |
| `Call`, `Transcript`, `TranscriptSegment` with `CallStatus` enum | Task 3 |
| Seed default Team + Agent | Task 5 |
| `embedding` column nullable | Task 3, Step 5 |
| Alembic migration applied | Task 4 |
| `StorageBackend` Protocol | Task 6 |
| `LocalStorage` (aiofiles, files under `LOCAL_STORAGE_DIR`) | Task 6 |
| `S3Storage` stub with NotImplementedError-TODO | Task 6 |
| `get_storage()` factory | Task 6 |
| Key generated as `{uuid4}{ext}` | Task 11 (`_call_storage_key`) |
| `Transcriber` protocol + `StubTranscriber` default | Task 7 |
| `Diarizer` protocol + `NullDiarizer` default | Task 7 |
| `FasterWhisperTranscriber`, `GroqWhisperTranscriber` optional | Task 7 |
| `PyannoteDiarizer` optional, HF token, model terms note | Task 7, Step 8 |
| Merge function + speaker heuristic | Task 7, Step 5 |
| Factories from settings | Task 7, Step 9 |
| Celery app wired to Redis | Task 8 |
| Correlation-ID propagation in tasks | Task 9 (logger extras) |
| `run_call_pipeline` plain service function | Task 9 |
| Status transitions + status_detail on failure | Task 9 |
| Redis pub/sub `call:{id}:events` | Task 9, Step 1 |
| Thin Celery task wrapper | Task 9, Step 3 |
| `POST /`: MIME sniff, size limit, reject empty | Task 11 |
| `GET /`: list + filters + pagination | Task 11 |
| `GET /{id}`: detail | Task 11 |
| `GET /{id}/transcript` | Task 11 |
| `GET /{id}/audio`: Range support | Task 11 |
| `GET /{id}/events`: SSE | Task 11 |
| `DELETE /{id}`: delete row + file | Task 11 |
| All endpoints auth-guarded | Task 11 (all use `get_current_user`) |
| Config: all new settings fields | Task 2 |
| `.env.example` updated | Task 2 |
| Upload tests: wrong MIME, oversized, missing, valid | Task 12 |
| Pipeline test: transcript + status transcribed | Task 12 |
| Pipeline test: forced error → status failed | Task 12 |
| List/get/transcript/audio: 401 without token | Task 12 |
| Audio Range test: 206 response | Task 12 |
| Delete: row + file removed | Task 12 |
| ruff + mypy + pytest green | Task 13 |
| Migration confirmed | Task 13, Step 5 |
| BUILD_LOG updated | Task 13, Step 6 |
| Single commit, no AI attribution | Task 13, Step 7 |

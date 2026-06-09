"""Application configuration via pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables.

    All secrets must be supplied via environment; no defaults for sensitive values.
    In production, required secrets are validated at startup — the app refuses
    to start with insecure defaults.
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
    db_use_pgbouncer: bool = False

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

    # Allowed audio MIME types (sniffed from file content, not from client Content-Type)
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

    # S3-compatible storage
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_endpoint_url: str = ""

    # Transcription
    transcriber_provider: Literal["stub", "faster_whisper", "groq", "assemblyai"] = "stub"
    diarizer_provider: Literal["null", "pyannote", "passthrough"] = "null"
    huggingface_token: str = ""
    groq_api_key: str = ""
    assemblyai_api_key: str = ""

    # LLM / agents
    llm_provider: Literal["stub", "langchain"] = "stub"
    google_api_key: str = ""
    llm_model_google: str = "gemini-1.5-flash"
    llm_model_groq: str = "llama3-70b-8192"

    # Embeddings
    embedding_provider: Literal["stub", "local", "gemini"] = "stub"
    embedding_dim: int = 384
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"

    # Redaction
    redaction_enabled: bool = True
    redaction_provider: Literal["regex", "presidio"] = "regex"
    redact_before_scoring: bool = True

    # Topics
    topic_extractor: Literal["stub", "llm"] = "stub"
    topic_relevance_threshold: float = 0.1

    # Scoring bands
    score_band_good: int = 80
    score_band_fair: int = 60

    # API docs gating
    enable_api_docs: bool | None = None

    # Demo seeding
    seed_demo_on_start: bool = False

    # Auth rate limiting (in-memory, per single instance)
    auth_rate_limit_per_minute: int = 20

    @field_validator("cors_origins", "allowed_audio_mimes", mode="before")
    @classmethod
    def parse_csv_list(cls, v: object) -> object:
        """Parse comma-separated string into a list."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Reject insecure defaults when running in production."""
        if self.app_env != "production":
            return self

        insecure_jwt = "CHANGE-ME-IN-PRODUCTION-use-a-random-32-plus-byte-secret"
        insecure_db = "postgresql+asyncpg://calllens:calllens@localhost:5432/calllens"

        errors: list[str] = []
        if self.jwt_secret == insecure_jwt:
            errors.append("JWT_SECRET must be set in production (not the default)")
        if self.database_url == insecure_db:
            errors.append("DATABASE_URL must be set in production (not the default)")
        if errors:
            raise ValueError("Production configuration errors:\n  - " + "\n  - ".join(errors))
        return self

    @property
    def docs_enabled(self) -> bool:
        """Whether OpenAPI docs endpoints should be exposed."""
        if self.enable_api_docs is not None:
            return self.enable_api_docs
        return self.app_env != "production"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()

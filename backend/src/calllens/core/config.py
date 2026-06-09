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

    # Transcription
    transcriber_provider: Literal["stub", "faster_whisper", "groq"] = "stub"
    diarizer_provider: Literal["null", "pyannote"] = "null"
    huggingface_token: str = ""
    groq_api_key: str = ""

    # LLM / agents
    llm_provider: Literal["stub", "langchain"] = "stub"
    google_api_key: str = ""
    llm_model_google: str = "gemini-1.5-flash"
    llm_model_groq: str = "llama3-70b-8192"

    # Embeddings
    embedding_provider: Literal["stub", "local", "gemini"] = "stub"
    embedding_dim: int = 384
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"

    # Scoring bands
    score_band_good: int = 80
    score_band_fair: int = 60

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

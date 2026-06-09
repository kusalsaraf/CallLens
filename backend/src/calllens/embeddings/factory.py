"""Embedder factory keyed on ``EMBEDDING_PROVIDER`` setting."""

from __future__ import annotations

import logging

from calllens.core.config import get_settings
from calllens.embeddings.base import Embedder

logger = logging.getLogger(__name__)


def get_embedder() -> Embedder:
    """Return the configured embedder instance.

    Keyed on ``settings.embedding_provider``:

    - ``"stub"``  → StubEmbedder (always available, deterministic, no deps)
    - ``"local"`` → LocalEmbedder (requires ``calllens[embeddings]``)
    - ``"gemini"``→ GeminiEmbedder (requires ``calllens[agents]`` + GOOGLE_API_KEY)

    Returns:
        A concrete Embedder implementation.

    Raises:
        ImportError: If the requested provider's dependencies are missing.
        ValueError: If the provider name is unrecognised.
    """
    settings = get_settings()
    provider = settings.embedding_provider

    if provider == "stub":
        from calllens.embeddings.stub import StubEmbedder

        return StubEmbedder()

    if provider == "local":
        try:
            from calllens.embeddings.local import LocalEmbedder
        except ImportError as exc:
            raise ImportError(
                "Install calllens[embeddings] to use the local embedding provider "
                "(pip install 'calllens[embeddings]')"
            ) from exc
        return LocalEmbedder()

    if provider == "gemini":
        try:
            from calllens.embeddings.gemini import GeminiEmbedder
        except ImportError as exc:
            raise ImportError(
                "Install calllens[agents] to use the gemini embedding provider "
                "(pip install 'calllens[agents]')"
            ) from exc
        if not settings.google_api_key:
            raise ValueError("Set GOOGLE_API_KEY when using the gemini embedding provider.")
        return GeminiEmbedder()

    raise ValueError(f"Unknown embedding_provider: {provider!r}")

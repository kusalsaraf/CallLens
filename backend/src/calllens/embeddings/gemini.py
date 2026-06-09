"""Gemini embedding provider via langchain-google-genai (optional dep).

Requires the ``agents`` optional group (which includes langchain-google-genai)
and a valid ``GOOGLE_API_KEY``.

Gemini ``text-embedding-004`` outputs 768-dim vectors by default — set
``EMBEDDING_DIM=768`` and regenerate (re-embed + migration) if switching to
this provider from the 384-dim default.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from calllens.core.config import get_settings

logger = logging.getLogger(__name__)

_embeddings_model: Any = None


def _get_model() -> Any:
    """Lazy-load the LangChain Google Generative AI embeddings model."""
    global _embeddings_model
    if _embeddings_model is None:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        settings = get_settings()
        _embeddings_model = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=settings.google_api_key,
        )
        logger.info("Loaded Gemini embedding model: text-embedding-004")
    return _embeddings_model


def _l2_normalise(vec: list[float]) -> list[float]:
    """L2-normalise a vector in-place."""
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class GeminiEmbedder:
    """Embedding provider using Google Gemini ``text-embedding-004``.

    Native dimension is 768.  If ``EMBEDDING_DIM`` differs, vectors are
    truncated or padded and re-normalised (truncation is valid for Gemini
    Matryoshka-style embeddings down to ~256-d).
    """

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts via the Gemini API.

        Args:
            texts: List of text strings.

        Returns:
            List of L2-normalised float vectors of length EMBEDDING_DIM.
        """
        model = _get_model()
        dim = get_settings().embedding_dim
        raw: list[list[float]] = await model.aembed_documents(texts)
        return [_l2_normalise(v[:dim]) for v in raw]

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query via the Gemini API.

        Args:
            text: The query text.

        Returns:
            An L2-normalised float vector of length EMBEDDING_DIM.
        """
        model = _get_model()
        dim = get_settings().embedding_dim
        raw: list[float] = await model.aembed_query(text)
        return _l2_normalise(raw[:dim])

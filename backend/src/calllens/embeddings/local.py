"""Local embedding provider using sentence-transformers (optional dep).

Requires the ``embeddings`` optional group::

    pip install 'calllens[embeddings]'

Default model: ``BAAI/bge-small-en-v1.5`` (384-dim, matches default EMBEDDING_DIM).
"""

from __future__ import annotations

import logging
from typing import Any

from calllens.core.config import get_settings

logger = logging.getLogger(__name__)

_model: Any = None


def _get_model() -> Any:
    """Lazy-load the sentence-transformers model once per process."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        logger.info(
            "Loading sentence-transformers model",
            extra={"model": settings.embedding_model_name},
        )
        _model = SentenceTransformer(settings.embedding_model_name)
    return _model


class LocalEmbedder:
    """Embedding provider backed by a local sentence-transformers model.

    The model is loaded lazily on the first call and cached for the process
    lifetime.  Default model ``BAAI/bge-small-en-v1.5`` outputs 384-dim
    vectors — this must match ``EMBEDDING_DIM``.
    """

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using the local model.

        Args:
            texts: List of text strings.

        Returns:
            List of L2-normalised float vectors.
        """
        model = _get_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return [row.tolist() for row in embeddings]

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query using the local model.

        Args:
            text: The query text.

        Returns:
            An L2-normalised float vector.
        """
        model = _get_model()
        embedding = model.encode([text], normalize_embeddings=True)
        return embedding[0].tolist()  # type: ignore[no-any-return]

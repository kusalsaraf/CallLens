"""Embedder protocol defining the contract for all embedding providers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    """Contract for text → vector embedding providers.

    Every implementation must return L2-normalised vectors of length
    ``settings.embedding_dim``.  The pgvector column dimension is fixed at
    ``EMBEDDING_DIM`` — switching to a provider whose native dimension
    differs requires a re-embed migration.
    """

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into dense vectors.

        Args:
            texts: Non-empty list of text strings.

        Returns:
            List of L2-normalised float vectors, each of length EMBEDDING_DIM.
        """
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string.

        Args:
            text: The query text.

        Returns:
            An L2-normalised float vector of length EMBEDDING_DIM.
        """
        ...

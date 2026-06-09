"""Deterministic stub embedder — no deps, no network, fully testable."""

from __future__ import annotations

import hashlib
import math
import struct
import unicodedata

from calllens.core.config import get_settings


def _normalize_text(text: str) -> str:
    """Lowercase, strip, and NFC-normalise for stable hashing."""
    return unicodedata.normalize("NFC", text.strip().lower())


def _deterministic_vector(text: str, dim: int) -> list[float]:
    """Produce a deterministic L2-normalised vector from *text*.

    Seeds a simple RNG from a SHA-256 hash of the normalised text, then
    draws *dim* floats and L2-normalises them.  The same text always yields
    the same vector, making exact-text queries rank that segment first.
    """
    digest = hashlib.sha256(_normalize_text(text).encode()).digest()
    seed = struct.unpack("<I", digest[:4])[0]

    rng_state = seed
    raw: list[float] = []
    for _ in range(dim):
        rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
        raw.append((rng_state / 0x7FFFFFFF) * 2.0 - 1.0)

    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]


class StubEmbedder:
    """Deterministic embedding provider for tests and CI.

    Produces the same L2-normalised vector for the same input text,
    so an exact-text query will always rank its source segment first.
    Requires no model downloads, API keys, or network access.
    """

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts deterministically.

        Args:
            texts: List of text strings.

        Returns:
            List of deterministic L2-normalised vectors.
        """
        dim = get_settings().embedding_dim
        return [_deterministic_vector(t, dim) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string deterministically.

        Args:
            text: The query text.

        Returns:
            A deterministic L2-normalised vector.
        """
        dim = get_settings().embedding_dim
        return _deterministic_vector(text, dim)

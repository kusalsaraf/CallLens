"""Embedding providers for semantic search over transcript segments."""

from calllens.embeddings.base import Embedder
from calllens.embeddings.factory import get_embedder

__all__ = ["Embedder", "get_embedder"]

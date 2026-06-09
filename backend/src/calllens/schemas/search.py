"""Pydantic schemas for the semantic search API."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class SegmentSnippet(BaseModel):
    """A single matching transcript segment snippet."""

    segment_id: uuid.UUID
    start_ms: int
    text: str
    similarity: float


class SearchHit(BaseModel):
    """A call that matched the search query, with its best segment snippets."""

    call_id: uuid.UUID
    agent_name: str | None
    overall_score: int | None
    band: str | None
    uploaded_at: str | None
    snippets: list[SegmentSnippet]


class SearchResponse(BaseModel):
    """Top-level response for the search endpoint."""

    query: str
    results: list[SearchHit]
    total: int

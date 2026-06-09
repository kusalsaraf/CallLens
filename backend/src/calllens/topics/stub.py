"""Deterministic keyword-based topic extractor (default, no deps)."""

from __future__ import annotations

from calllens.core.config import get_settings
from calllens.topics.base import TaxonomyEntry, TopicMatch


class StubKeywordExtractor:
    """Score each taxonomy topic by keyword hits in the transcript.

    For each topic, counts how many of its keywords appear (case-insensitive)
    in the transcript text, then normalises by the keyword list length to
    produce a relevance score in [0, 1]. Topics above the configured
    threshold are returned.

    Deterministic, requires no dependencies or network access.
    """

    async def extract(
        self,
        transcript_text: str,
        taxonomy: list[TaxonomyEntry],
    ) -> list[TopicMatch]:
        """Extract topics by keyword frequency.

        Args:
            transcript_text: Full transcript (all segments joined).
            taxonomy: Available topics.

        Returns:
            Matched topics above the relevance threshold, sorted by relevance desc.
        """
        threshold = get_settings().topic_relevance_threshold
        text_lower = transcript_text.lower()
        matches: list[TopicMatch] = []

        for entry in taxonomy:
            keywords = entry["keywords"]
            if not keywords:
                continue
            hits = sum(1 for kw in keywords if kw.lower() in text_lower)
            relevance = hits / len(keywords)
            if relevance >= threshold:
                matches.append(TopicMatch(topic_slug=entry["slug"], relevance=round(relevance, 4)))

        matches.sort(key=lambda m: m["relevance"], reverse=True)
        return matches

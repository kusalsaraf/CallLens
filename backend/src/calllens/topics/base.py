"""Topic extraction protocol and shared types."""

from __future__ import annotations

from typing import Protocol, TypedDict, runtime_checkable


class TopicMatch(TypedDict):
    """A single detected topic with its relevance score."""

    topic_slug: str
    relevance: float


class TaxonomyEntry(TypedDict):
    """A topic from the taxonomy provided to the extractor."""

    slug: str
    name: str
    keywords: list[str]


@runtime_checkable
class TopicExtractor(Protocol):
    """Protocol for topic/theme extraction from transcript text."""

    async def extract(
        self,
        transcript_text: str,
        taxonomy: list[TaxonomyEntry],
    ) -> list[TopicMatch]:
        """Classify transcript text into taxonomy topics.

        Args:
            transcript_text: Full transcript text (all segments joined).
            taxonomy: Available topics with slugs, names, and keywords.

        Returns:
            List of matched topics with relevance scores (0-1).
            Only topics above the configured threshold should be returned.
        """
        ...

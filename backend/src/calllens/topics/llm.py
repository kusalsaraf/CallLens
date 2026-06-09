"""LLM-based topic extractor using the existing agents/langchain path."""

from __future__ import annotations

import logging

from calllens.core.config import get_settings
from calllens.topics.base import TaxonomyEntry, TopicMatch
from calllens.topics.stub import StubKeywordExtractor

logger = logging.getLogger(__name__)


class LLMTopicExtractor:
    """Classify a call into taxonomy topics via the configured LLM provider.

    Uses the stub keyword extractor as a baseline and (when fully wired)
    would use the LLM for more nuanced classification. Falls back to the
    StubKeywordExtractor on any failure.

    Note: full LLM classification requires an appropriate provider API.
    This implementation delegates to the stub extractor for now, as the
    LLMProvider protocol is designed for structured scoring rather than
    general text classification. A production implementation would use a
    dedicated classification chain.
    """

    async def extract(
        self,
        transcript_text: str,
        taxonomy: list[TaxonomyEntry],
    ) -> list[TopicMatch]:
        """Classify transcript into taxonomy topics.

        Args:
            transcript_text: Full transcript (all segments joined).
            taxonomy: Available topics.

        Returns:
            Matched topics above the relevance threshold.
        """
        try:
            return await self._extract_llm(transcript_text, taxonomy)
        except Exception:
            logger.exception("LLM topic extraction failed — falling back to stub")
            fallback = StubKeywordExtractor()
            return await fallback.extract(transcript_text, taxonomy)

    async def _extract_llm(
        self,
        transcript_text: str,
        taxonomy: list[TaxonomyEntry],
    ) -> list[TopicMatch]:
        """Internal LLM extraction logic.

        Currently delegates to the stub extractor. A production implementation
        would build a LangChain classification chain constrained to the taxonomy
        slugs with structured output parsing.

        Args:
            transcript_text: Full transcript.
            taxonomy: Available topics.

        Returns:
            Matched topics from classification.
        """
        _ = get_settings()
        stub = StubKeywordExtractor()
        return await stub.extract(transcript_text, taxonomy)

"""Factory for topic extractor instantiation."""

from __future__ import annotations

from calllens.core.config import get_settings
from calllens.topics.base import TopicExtractor
from calllens.topics.llm import LLMTopicExtractor
from calllens.topics.stub import StubKeywordExtractor

_EXTRACTORS: dict[str, type[StubKeywordExtractor | LLMTopicExtractor]] = {
    "stub": StubKeywordExtractor,
    "llm": LLMTopicExtractor,
}


def get_topic_extractor() -> TopicExtractor:
    """Return the configured topic extractor instance.

    Returns:
        A TopicExtractor keyed on ``settings.topic_extractor``.

    Raises:
        ValueError: If the configured provider is unknown.
    """
    provider = get_settings().topic_extractor
    cls = _EXTRACTORS.get(provider)
    if cls is None:
        raise ValueError(f"Unknown topic extractor: {provider!r}")
    return cls()

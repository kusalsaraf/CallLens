"""Presidio-based PII/PCI redactor — requires the ``redaction`` optional dependency group.

Provides NER-based entity detection (PERSON, LOCATION, etc.) on top of the
structured patterns. Lazy-loads the Presidio engine once on first use.

Requires::

    uv pip install calllens[redaction]
    python -m spacy download en_core_web_lg
"""

from __future__ import annotations

import logging
import re
from typing import Any

from calllens.redaction.base import RedactedEntity, RedactionResult

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\[REDACTED_\w+\]")

_PRESIDIO_TO_PLACEHOLDER: dict[str, str] = {
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "CREDIT_CARD": "CARD",
    "US_SSN": "SSN",
    "IP_ADDRESS": "IP",
    "PERSON": "PERSON",
    "LOCATION": "LOCATION",
    "DATE_TIME": "DATE",
    "NRP": "NRP",
    "MEDICAL_LICENSE": "MEDICAL",
    "US_BANK_NUMBER": "BANK",
    "US_DRIVER_LICENSE": "DRIVER_LICENSE",
    "US_PASSPORT": "PASSPORT",
    "US_ITIN": "ITIN",
    "IBAN_CODE": "IBAN",
}

_engine: Any = None


def _get_engine() -> Any:
    """Lazy-load the Presidio AnalyzerEngine (singleton).

    Returns:
        A configured ``presidio_analyzer.AnalyzerEngine`` instance.
    """
    global _engine  # noqa: PLW0603
    if _engine is not None:
        return _engine
    try:
        from presidio_analyzer import AnalyzerEngine

        _engine = AnalyzerEngine()
        logger.info("Presidio AnalyzerEngine initialized")
        return _engine
    except ImportError:
        raise ImportError(
            "Presidio is not installed. Install with: uv pip install calllens[redaction] "
            "and download the spaCy model: python -m spacy download en_core_web_lg"
        ) from None


class PresidioRedactor:
    """NER + pattern-based redactor using Microsoft Presidio.

    Detects PERSON, LOCATION, and other NER entities in addition to the
    structured PII/PCI patterns (email, phone, card, SSN, IP).
    """

    def redact(self, text: str) -> RedactionResult:
        """Detect and replace PII/PCI entities using Presidio.

        Args:
            text: Raw transcript text.

        Returns:
            RedactionResult with typed placeholders and entity offsets
            into the ORIGINAL text.
        """
        engine = _get_engine()
        results = engine.analyze(text=text, language="en")

        # Sort by position, longest first for overlaps
        results = sorted(results, key=lambda r: (r.start, -(r.end - r.start)))

        entities: list[RedactedEntity] = []
        matches: list[tuple[int, int, str]] = []
        last_end = -1

        for r in results:
            if r.start >= last_end:
                span_text = text[r.start : r.end]
                if _PLACEHOLDER_RE.search(span_text):
                    continue
                etype = _PRESIDIO_TO_PLACEHOLDER.get(r.entity_type, r.entity_type)
                matches.append((r.start, r.end, etype))
                last_end = r.end

        if not matches:
            return RedactionResult(redacted_text=text, entities=[])

        result_text = text
        for start, end, etype in reversed(matches):
            entities.append(RedactedEntity(type=etype, start=start, end=end))
            placeholder = f"[REDACTED_{etype}]"
            result_text = result_text[:start] + placeholder + result_text[end:]

        entities.reverse()
        return RedactionResult(redacted_text=result_text, entities=entities)

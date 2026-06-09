"""Redactor protocol and shared types."""

from __future__ import annotations

from typing import Protocol, TypedDict, runtime_checkable


class RedactedEntity(TypedDict):
    """A single detected PII/PCI entity with offsets into the ORIGINAL text."""

    type: str
    start: int
    end: int


class RedactionResult(TypedDict):
    """Output of a redaction pass."""

    redacted_text: str
    entities: list[RedactedEntity]


@runtime_checkable
class Redactor(Protocol):
    """Protocol for PII/PCI redaction engines."""

    def redact(self, text: str) -> RedactionResult:
        """Detect and replace PII/PCI entities in *text*.

        Replacements use typed placeholders like ``[REDACTED_EMAIL]``.
        Must be idempotent: re-running on already-redacted text is a no-op.

        Args:
            text: Raw text to redact.

        Returns:
            RedactionResult with the redacted text and entity offsets
            referencing the ORIGINAL text.
        """
        ...

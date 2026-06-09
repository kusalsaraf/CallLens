"""Regex-based PII/PCI redactor — zero external dependencies.

Detects and replaces:
- Email addresses → [REDACTED_EMAIL]
- Phone numbers (common formats) → [REDACTED_PHONE]
- Payment card numbers (Luhn-validated) → [REDACTED_CARD]
- US Social Security Numbers → [REDACTED_SSN]
- IPv4 addresses → [REDACTED_IP]

Idempotent: placeholders are never re-redacted on subsequent passes.
"""

from __future__ import annotations

import re

from calllens.redaction.base import RedactedEntity, RedactionResult

# Placeholder pattern used to detect already-redacted text
_PLACEHOLDER_RE = re.compile(r"\[REDACTED_\w+\]")

# ─── Individual PII patterns ─────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+?1[\s\-.]?)?"
    r"(?:\(?\d{3}\)?[\s\-.]?)"
    r"\d{3}[\s\-.]?\d{4}"
    r"(?!\d)"
)

_SSN_RE = re.compile(r"\b\d{3}[\-\s]\d{2}[\-\s]\d{4}\b")

_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

_CARD_RE = re.compile(r"\b(?:\d[\s\-]?){13,19}\b")


def _luhn_check(digits: str) -> bool:
    """Validate a digit string with the Luhn algorithm.

    Args:
        digits: String of digits (spaces/dashes already stripped).

    Returns:
        True if the digit string passes the Luhn checksum.
    """
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    reverse = digits[::-1]
    for i, ch in enumerate(reverse):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# Order matters: more specific patterns first to avoid double-matching
_PATTERNS: list[tuple[re.Pattern[str], str, bool]] = [
    (_EMAIL_RE, "EMAIL", False),
    (_SSN_RE, "SSN", False),
    (_IPV4_RE, "IP", False),
    (_CARD_RE, "CARD", True),  # requires Luhn validation
    (_PHONE_RE, "PHONE", False),
]


class RegexRedactor:
    """Deterministic regex-based PII/PCI redactor.

    Needs no external dependencies or network access. Luhn-validates
    candidate card numbers to avoid false positives on arbitrary digit
    sequences.
    """

    def redact(self, text: str) -> RedactionResult:
        """Detect and replace PII/PCI entities using regex patterns.

        Args:
            text: Raw transcript text.

        Returns:
            RedactionResult with typed placeholders and entity offsets into
            the ORIGINAL text.
        """
        entities: list[RedactedEntity] = []

        # Collect all matches with their positions, then replace from right to left
        # so earlier offsets remain valid.
        matches: list[tuple[int, int, str]] = []

        for pattern, entity_type, needs_luhn in _PATTERNS:
            for m in pattern.finditer(text):
                span_text = m.group()

                # Skip if the match is inside an existing placeholder
                if _PLACEHOLDER_RE.search(span_text):
                    continue

                if needs_luhn:
                    digits = re.sub(r"\D", "", span_text)
                    if not _luhn_check(digits):
                        continue

                matches.append((m.start(), m.end(), entity_type))

        if not matches:
            return RedactionResult(redacted_text=text, entities=[])

        # De-duplicate overlapping matches: keep the earliest/longest
        matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        deduped: list[tuple[int, int, str]] = []
        last_end = -1
        for start, end, etype in matches:
            if start >= last_end:
                deduped.append((start, end, etype))
                last_end = end

        # Build entities (offsets into original text) and replace right-to-left
        result_text = text
        for start, end, etype in reversed(deduped):
            entities.append(RedactedEntity(type=etype, start=start, end=end))
            placeholder = f"[REDACTED_{etype}]"
            result_text = result_text[:start] + placeholder + result_text[end:]

        # Reverse entities to be in left-to-right order
        entities.reverse()

        return RedactionResult(redacted_text=result_text, entities=entities)

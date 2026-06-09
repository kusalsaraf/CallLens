"""Redactor factory — returns the configured Redactor implementation."""

from __future__ import annotations

from calllens.core.config import get_settings
from calllens.redaction.base import Redactor


def get_redactor() -> Redactor:
    """Return a Redactor instance based on ``settings.REDACTION_PROVIDER``.

    Returns:
        A ``RegexRedactor`` (default) or ``PresidioRedactor``.

    Raises:
        ValueError: If the configured provider is unknown.
    """
    provider = get_settings().redaction_provider

    if provider == "regex":
        from calllens.redaction.regex import RegexRedactor

        return RegexRedactor()

    if provider == "presidio":
        from calllens.redaction.presidio import PresidioRedactor

        return PresidioRedactor()

    raise ValueError(f"Unknown REDACTION_PROVIDER: {provider!r}")

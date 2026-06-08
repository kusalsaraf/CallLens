"""Canonical call quality band thresholds and classification.

This module is the SINGLE source of truth for score band boundaries.
The frontend mirror is ``src/lib/constants/scoreBands.ts`` — its thresholds
must be kept identical to the values here.  The API ``band`` field is
authoritative; frontends must prefer it over local computation.

Canonical partition:
  quality  score >= 80
  at-risk  60 <= score < 80
  fail     score < 60
"""

from __future__ import annotations

QUALITY_THRESHOLD: int = 80
AT_RISK_THRESHOLD: int = 60


def band(score: int) -> str:
    """Classify a 0-100 integer score into the canonical quality band.

    Args:
        score: Integer overall score 0-100.

    Returns:
        One of ``"quality"``, ``"at-risk"``, or ``"fail"``.
    """
    if score >= QUALITY_THRESHOLD:
        return "quality"
    if score >= AT_RISK_THRESHOLD:
        return "at-risk"
    return "fail"

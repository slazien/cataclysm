"""Deterministic content validation for coaching report text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Forbidden cross-dimensional composites (the exact hallucination class observed in prod).
FORBIDDEN_COMPOSITES: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bmph\s+of\s+(?:available\s+)?(?:grip|traction|adhesion|force|load)\b",
        r"(?<![a-zA-Z])g\s+of\s+(?:speed|velocity|mph)\b",
        r"\b(?:percent|%)\s*(?:mph|g|m(?:eter)?s?)\b",
        r"\bmph\s*(?:/|per)\s*g\b",
        r"\bspeed\s+utilization\s+at\s+\d",
    ]
]

_NUMBER_WITH_UNIT = re.compile(
    r"(?P<val>\d+(?:\.\d+)?)\s*(?P<unit>mph|m|g|s|%)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ContentValidationResult:
    """Result of deterministic content validation."""

    passed: bool = True
    forbidden_composites: list[str] = field(default_factory=list)
    orphan_numbers: list[str] = field(default_factory=list)


def find_forbidden_composites(text: str) -> list[str]:
    """Detect nonsensical unit-concept combinations."""
    return [match.group(0) for pattern in FORBIDDEN_COMPOSITES for match in pattern.finditer(text)]


def strip_forbidden_composites(text: str) -> tuple[str, list[str]]:
    """Remove forbidden composite phrases from text and return removed matches."""
    sanitized = text
    removed: list[str] = []
    for pattern in FORBIDDEN_COMPOSITES:
        removed.extend(match.group(0) for match in pattern.finditer(sanitized))
        sanitized = pattern.sub("[redacted invalid metric phrase]", sanitized)
    sanitized = re.sub(r"[ \t]{2,}", " ", sanitized)
    return sanitized, removed


def find_orphan_numbers(
    text: str,
    input_values: set[float],
    tolerance: float = 0.5,
) -> list[str]:
    """Find numbers in output that do not appear in input telemetry values."""
    if not input_values:
        return []

    orphans: list[str] = []
    for match in _NUMBER_WITH_UNIT.finditer(text):
        value = float(match.group("val"))
        if not any(abs(value - input_value) <= tolerance for input_value in input_values):
            orphans.append(match.group(0))
    return orphans


def validate_coaching_content(
    report_text: str,
    *,
    input_values: set[float] | None = None,
) -> ContentValidationResult:
    """Run deterministic content validation on a coaching report."""
    result = ContentValidationResult()
    result.forbidden_composites = find_forbidden_composites(report_text)
    if input_values:
        result.orphan_numbers = find_orphan_numbers(report_text, input_values)
    result.passed = not result.forbidden_composites
    # Orphan numbers are warnings only (derived values can be valid).
    return result

"""Number grounding / anti-hallucination checks for coaching outputs."""

from __future__ import annotations

import re
from typing import Any

from evaluation.types import DimensionResult, Verdict

# Matches numbers (int or float), but we post-filter to exclude corner/turn/lap refs
_NUMBER_RE = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)")

# Patterns where a number is a corner/turn/lap reference, not a data citation
_CORNER_REF_RE = re.compile(r"(?:T|Turn\s+|Corner\s+|Lap\s+|L)(\d+)", re.IGNORECASE)

TOLERANCE = 0.05  # 5% tolerance for number matching


def extract_numbers_from_text(text: str) -> list[float]:
    """Extract numbers from coaching text, ignoring T#/Turn #/Corner #/Lap #/L# refs."""
    # Find all corner/turn/lap reference positions to exclude
    exclude_spans: list[tuple[int, int]] = []
    for m in _CORNER_REF_RE.finditer(text):
        exclude_spans.append(m.span())

    numbers: list[float] = []
    for m in _NUMBER_RE.finditer(text):
        start, end = m.span()
        # Skip if this number is part of a corner/turn/lap reference
        skip = False
        for ex_start, ex_end in exclude_spans:
            if ex_start <= start < ex_end:
                skip = True
                break
        if not skip:
            numbers.append(float(m.group(1)))

    return numbers


def flatten_telemetry(data: dict[str, Any] | list[Any] | Any) -> list[float]:
    """Recursively flatten all numbers from a telemetry dict/list."""
    result: list[float] = []

    if isinstance(data, dict):
        for v in data.values():
            result.extend(flatten_telemetry(v))
    elif isinstance(data, list):
        for item in data:
            result.extend(flatten_telemetry(item))
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        result.append(float(data))

    return result


def _is_grounded(value: float, reference_numbers: set[float]) -> bool:
    """Check if a value matches any reference number within tolerance."""
    if value == 0.0:
        return 0.0 in reference_numbers
    for ref in reference_numbers:
        if ref == 0.0:
            if value == 0.0:
                return True
            continue
        if abs(value - ref) / max(abs(ref), 1e-9) <= TOLERANCE:
            return True
    return False


def check_citation_grounding(
    coaching_text: str,
    telemetry: dict[str, Any],
) -> DimensionResult:
    """Check that numbers in coaching text are grounded in telemetry data.

    Score = grounded/total. PASS >= 0.80, WARN >= 0.60, FAIL below.
    """
    output_numbers = extract_numbers_from_text(coaching_text)

    if not output_numbers:
        return DimensionResult(
            name="citation_grounding",
            score=1.0,
            verdict=Verdict.PASS,
            details="No numbers found in coaching text.",
        )

    reference_numbers = set(flatten_telemetry(telemetry))

    grounded = sum(1 for n in output_numbers if _is_grounded(n, reference_numbers))
    total = len(output_numbers)
    score = grounded / total

    if score >= 0.80:
        verdict = Verdict.PASS
    elif score >= 0.60:
        verdict = Verdict.WARN
    else:
        verdict = Verdict.FAIL

    ungrounded = [n for n in output_numbers if not _is_grounded(n, reference_numbers)]
    details = f"{grounded}/{total} numbers grounded ({score:.0%})."
    if ungrounded:
        details += f" Ungrounded: {ungrounded[:5]}"

    return DimensionResult(
        name="citation_grounding",
        score=score,
        verdict=verdict,
        details=details,
    )


def run_citation_checks(
    coaching_text: str,
    telemetry: dict[str, Any],
) -> list[DimensionResult]:
    """Run all citation/grounding checks."""
    return [check_citation_grounding(coaching_text, telemetry)]

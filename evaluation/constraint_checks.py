"""Deterministic text constraint checks for coaching outputs."""

from __future__ import annotations

import re
from typing import Any

from evaluation.types import DimensionResult, Verdict

_CORNER_FIRST_RE = re.compile(r"^(?:At\s+)?(?:T\d+|Turn\s+\d+|Corner\s+\d+)\b", re.IGNORECASE)
_BECAUSE_WITH_NUMBER_RE = re.compile(r"\bbecause\b.*?\d", re.IGNORECASE | re.DOTALL)


def check_because_clauses(report: dict[str, Any]) -> DimensionResult:
    """Check that tips contain 'because' + a number. >=80% pass rate required."""
    priority_corners = report.get("priority_corners", [])
    if not priority_corners:
        return DimensionResult(
            name="because_clauses",
            score=1.0,
            verdict=Verdict.PASS,
            details="No priority corners to check.",
        )

    texts: list[str] = []
    for pc in priority_corners:
        for field in ("tip", "feedback"):
            val = pc.get(field, "")
            if isinstance(val, str) and val:
                texts.append(val)

    if not texts:
        return DimensionResult(
            name="because_clauses",
            score=0.0,
            verdict=Verdict.FAIL,
            details="No tip/feedback text found.",
        )

    passed = sum(1 for t in texts if _BECAUSE_WITH_NUMBER_RE.search(t))
    rate = passed / len(texts)

    if rate >= 0.80:
        verdict = Verdict.PASS
    elif rate >= 0.50:
        verdict = Verdict.WARN
    else:
        verdict = Verdict.FAIL

    return DimensionResult(
        name="because_clauses",
        score=rate,
        verdict=verdict,
        details=f"{passed}/{len(texts)} texts contain 'because' + number ({rate:.0%}).",
    )


def check_corner_first(report: dict[str, Any]) -> DimensionResult:
    """Check that tip/feedback starts with T#/Turn #/Corner #. >=80% required."""
    priority_corners = report.get("priority_corners", [])
    if not priority_corners:
        return DimensionResult(
            name="corner_first",
            score=1.0,
            verdict=Verdict.PASS,
            details="No priority corners to check.",
        )

    texts: list[str] = []
    for pc in priority_corners:
        for field in ("tip", "feedback"):
            val = pc.get(field, "")
            if isinstance(val, str) and val:
                texts.append(val)

    if not texts:
        return DimensionResult(
            name="corner_first",
            score=0.0,
            verdict=Verdict.FAIL,
            details="No tip/feedback text found.",
        )

    passed = sum(1 for t in texts if _CORNER_FIRST_RE.match(t.strip()))
    rate = passed / len(texts)

    if rate >= 0.80:
        verdict = Verdict.PASS
    elif rate >= 0.50:
        verdict = Verdict.WARN
    else:
        verdict = Verdict.FAIL

    return DimensionResult(
        name="corner_first",
        score=rate,
        verdict=verdict,
        details=f"{passed}/{len(texts)} texts start with corner reference ({rate:.0%}).",
    )


def check_summary_length(report: dict[str, Any]) -> DimensionResult:
    """Check that summary is between 20-500 words."""
    summary = report.get("summary", "")
    word_count = len(summary.split())

    if 20 <= word_count <= 500:
        return DimensionResult(
            name="summary_length",
            score=1.0,
            verdict=Verdict.PASS,
            details=f"Summary has {word_count} words.",
        )

    return DimensionResult(
        name="summary_length",
        score=0.0,
        verdict=Verdict.FAIL,
        details=f"Summary has {word_count} words, expected 20-500.",
    )


def run_constraint_checks(report: dict[str, Any]) -> list[DimensionResult]:
    """Run all deterministic text constraint checks."""
    return [
        check_because_clauses(report),
        check_corner_first(report),
        check_summary_length(report),
    ]

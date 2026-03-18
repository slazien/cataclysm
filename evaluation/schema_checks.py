"""Deterministic JSON schema validation for coaching outputs."""

from __future__ import annotations

import json
from typing import Any

from evaluation.types import DimensionResult, Verdict

REQUIRED_FIELDS: set[str] = {"summary", "priority_corners", "corner_grades", "patterns"}

VALID_GRADES: set[str] = {"A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F", "N/A"}

GRADE_FIELDS: list[str] = ["braking", "trail_braking", "min_speed", "throttle"]


def check_json_valid(raw: str) -> DimensionResult:
    """Check that the raw string is valid JSON."""
    try:
        json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        return DimensionResult(
            name="json_valid",
            score=0.0,
            verdict=Verdict.FAIL,
            details=f"Invalid JSON: {exc}",
        )
    return DimensionResult(name="json_valid", score=1.0, verdict=Verdict.PASS)


def check_required_fields(report: dict[str, Any]) -> DimensionResult:
    """Check that all required top-level fields are present."""
    missing = REQUIRED_FIELDS - set(report.keys())
    if missing:
        return DimensionResult(
            name="required_fields",
            score=0.0,
            verdict=Verdict.FAIL,
            details=f"Missing fields: {sorted(missing)}",
        )
    return DimensionResult(name="required_fields", score=1.0, verdict=Verdict.PASS)


def check_grade_values(report: dict[str, Any]) -> DimensionResult:
    """Check that all grade values in corner_grades are valid letter grades."""
    corner_grades = report.get("corner_grades", [])
    if not corner_grades:
        return DimensionResult(
            name="grade_values",
            score=1.0,
            verdict=Verdict.PASS,
            details="No corner grades to validate.",
        )

    invalid: list[str] = []
    total = 0
    for cg in corner_grades:
        for gf in GRADE_FIELDS:
            val = cg.get(gf)
            if val is not None:
                total += 1
                if val not in VALID_GRADES:
                    invalid.append(f"corner {cg.get('corner', '?')}.{gf}={val}")

    if invalid:
        return DimensionResult(
            name="grade_values",
            score=max(0.0, 1.0 - len(invalid) / max(total, 1)),
            verdict=Verdict.FAIL,
            details=f"Invalid grades: {invalid}",
        )
    return DimensionResult(name="grade_values", score=1.0, verdict=Verdict.PASS)


def check_array_bounds(report: dict[str, Any]) -> DimensionResult:
    """Check that arrays are within expected bounds."""
    issues: list[str] = []

    priority_corners = report.get("priority_corners", [])
    n_pc = len(priority_corners)
    if n_pc < 1 or n_pc > 5:
        issues.append(f"priority_corners count={n_pc}, expected 1-5")

    patterns = report.get("patterns", [])
    n_pat = len(patterns)
    if n_pat > 10:
        issues.append(f"patterns count={n_pat}, expected max 10")

    if issues:
        return DimensionResult(
            name="array_bounds",
            score=0.0,
            verdict=Verdict.FAIL,
            details="; ".join(issues),
        )
    return DimensionResult(name="array_bounds", score=1.0, verdict=Verdict.PASS)


def run_schema_checks(raw: str) -> list[DimensionResult]:
    """Run all schema checks. Hard-fails on invalid JSON or missing fields."""
    results: list[DimensionResult] = []

    json_result = check_json_valid(raw)
    results.append(json_result)
    if json_result.verdict == Verdict.FAIL:
        return results

    report: dict[str, Any] = json.loads(raw)

    fields_result = check_required_fields(report)
    results.append(fields_result)
    if fields_result.verdict == Verdict.FAIL:
        return results

    results.append(check_grade_values(report))
    results.append(check_array_bounds(report))
    return results

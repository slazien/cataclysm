"""Tests for schema_checks and constraint_checks modules."""

from __future__ import annotations

import json

from evaluation.constraint_checks import (
    check_because_clauses,
    check_corner_first,
    check_summary_length,
    run_constraint_checks,
)
from evaluation.schema_checks import (
    check_array_bounds,
    check_grade_values,
    check_json_valid,
    check_required_fields,
    run_schema_checks,
)
from evaluation.types import Verdict

VALID_REPORT: dict = {
    "summary": "Great session at Barber. " + "word " * 30,
    "priority_corners": [
        {
            "corner": 5,
            "tip": "At Turn 5, brake 3m later because you lost 0.2s by braking too early.",
            "feedback": "Turn 5 entry because your 85mph min speed leaves 4mph on the table.",
        },
        {
            "corner": 11,
            "tip": "At T11, stay wider on entry because the current line costs 0.15s.",
            "feedback": "T11 throttle because 60% application at apex is too conservative.",
        },
    ],
    "corner_grades": [
        {
            "corner": 5,
            "braking": "B+",
            "trail_braking": "C",
            "min_speed": "B",
            "throttle": "A-",
            "notes": "Good overall.",
        },
    ],
    "patterns": ["Late braking tendency", "Conservative throttle"],
    "primary_focus": "braking consistency",
    "drills": ["Brake marker drill"],
}


class TestSchemaChecks:
    """Tests for schema validation checks."""

    def test_valid_report_passes(self) -> None:
        raw = json.dumps(VALID_REPORT)
        results = run_schema_checks(raw)
        assert all(r.verdict == Verdict.PASS for r in results)

    def test_invalid_json_fails_and_stops(self) -> None:
        raw = "{not valid json"
        results = run_schema_checks(raw)
        assert len(results) == 1
        assert results[0].name == "json_valid"
        assert results[0].verdict == Verdict.FAIL

    def test_missing_fields_fails(self) -> None:
        report = {"summary": "Hello"}
        raw = json.dumps(report)
        results = run_schema_checks(raw)
        # json_valid passes, then required_fields fails and stops
        assert len(results) == 2
        assert results[0].verdict == Verdict.PASS
        assert results[1].name == "required_fields"
        assert results[1].verdict == Verdict.FAIL

    def test_invalid_grade_values_fails(self) -> None:
        report = {**VALID_REPORT}
        report["corner_grades"] = [
            {
                "corner": 5,
                "braking": "Z+",
                "trail_braking": "C",
                "min_speed": "B",
                "throttle": "A-",
            },
        ]
        raw = json.dumps(report)
        results = run_schema_checks(raw)
        grade_result = next(r for r in results if r.name == "grade_values")
        assert grade_result.verdict == Verdict.FAIL
        assert "Z+" in grade_result.details

    def test_json_valid_passes_valid_json(self) -> None:
        result = check_json_valid('{"a": 1}')
        assert result.verdict == Verdict.PASS

    def test_required_fields_all_present(self) -> None:
        result = check_required_fields(VALID_REPORT)
        assert result.verdict == Verdict.PASS

    def test_grade_values_na_accepted(self) -> None:
        report = {**VALID_REPORT}
        report["corner_grades"] = [
            {"corner": 1, "braking": "N/A", "trail_braking": "N/A"},
        ]
        result = check_grade_values(report)
        assert result.verdict == Verdict.PASS

    def test_array_bounds_too_many_priority_corners(self) -> None:
        report = {**VALID_REPORT}
        report["priority_corners"] = [{"corner": i} for i in range(6)]
        result = check_array_bounds(report)
        assert result.verdict == Verdict.FAIL
        assert "priority_corners" in result.details

    def test_array_bounds_too_many_patterns(self) -> None:
        report = {**VALID_REPORT}
        report["patterns"] = [f"pattern {i}" for i in range(11)]
        result = check_array_bounds(report)
        assert result.verdict == Verdict.FAIL
        assert "patterns" in result.details

    def test_array_bounds_empty_priority_corners_fails(self) -> None:
        report = {**VALID_REPORT}
        report["priority_corners"] = []
        result = check_array_bounds(report)
        assert result.verdict == Verdict.FAIL


class TestConstraintChecks:
    """Tests for text constraint checks."""

    def test_valid_report_passes(self) -> None:
        results = run_constraint_checks(VALID_REPORT)
        assert all(r.verdict == Verdict.PASS for r in results)

    def test_missing_because_clauses_fails(self) -> None:
        report = {**VALID_REPORT}
        report["priority_corners"] = [
            {
                "corner": 5,
                "tip": "At Turn 5, brake later.",
                "feedback": "Turn 5 entry is poor.",
            },
            {
                "corner": 11,
                "tip": "At T11, stay wider on entry.",
                "feedback": "T11 throttle is too conservative.",
            },
        ]
        result = check_because_clauses(report)
        assert result.verdict == Verdict.FAIL
        assert result.score == 0.0

    def test_missing_corner_first_detected(self) -> None:
        report = {**VALID_REPORT}
        report["priority_corners"] = [
            {
                "corner": 5,
                "tip": "Brake later at the turn.",
                "feedback": "Your entry is poor.",
            },
            {
                "corner": 11,
                "tip": "Stay wider because of something 5.",
                "feedback": "Throttle is too conservative because 3.",
            },
        ]
        result = check_corner_first(report)
        assert result.verdict == Verdict.FAIL
        assert result.score == 0.0

    def test_summary_too_short_fails(self) -> None:
        report = {**VALID_REPORT, "summary": "Too short."}
        result = check_summary_length(report)
        assert result.verdict == Verdict.FAIL

    def test_summary_too_long_fails(self) -> None:
        report = {**VALID_REPORT, "summary": "word " * 501}
        result = check_summary_length(report)
        assert result.verdict == Verdict.FAIL

    def test_summary_valid_length_passes(self) -> None:
        result = check_summary_length(VALID_REPORT)
        assert result.verdict == Verdict.PASS

    def test_partial_because_clauses_warn(self) -> None:
        """60% because rate should produce WARN."""
        report = {**VALID_REPORT}
        report["priority_corners"] = [
            {
                "corner": 1,
                "tip": "At T1, brake later because you lost 0.3s.",
            },
            {
                "corner": 2,
                "tip": "At T2, stay wider because the line costs 0.1s.",
            },
            {
                "corner": 3,
                "tip": "At T3, brake later because you lost 0.4s.",
            },
            {
                "corner": 4,
                "tip": "At T4, do something.",
            },
            {
                "corner": 5,
                "tip": "At T5, do something else.",
            },
        ]
        result = check_because_clauses(report)
        assert result.verdict == Verdict.WARN

"""Tests for citation_checks module."""

from __future__ import annotations

from evaluation.citation_checks import (
    check_citation_grounding,
    extract_numbers_from_text,
    flatten_telemetry,
)
from evaluation.types import Verdict


def test_extract_numbers_ignores_corner_refs() -> None:
    text = "At Turn 5, brake 3m later. T11 has 85mph min speed. Lap 7 was 0.2s slower."
    numbers = extract_numbers_from_text(text)
    # Should get: 3, 85, 0.2 — NOT 5, 11, 7
    assert 3.0 in numbers
    assert 85.0 in numbers
    assert 0.2 in numbers
    assert 5.0 not in numbers
    assert 11.0 not in numbers
    assert 7.0 not in numbers


def test_extract_numbers_ignores_l_refs() -> None:
    text = "L3 showed 95mph. L12 was 1.5s off."
    numbers = extract_numbers_from_text(text)
    assert 95.0 in numbers
    assert 1.5 in numbers
    assert 3.0 not in numbers
    assert 12.0 not in numbers


def test_flatten_nested_telemetry() -> None:
    telemetry = {
        "corners": {
            "T5": {"min_speed_mph": 85, "brake_point_m": 120.5},
            "T11": {"min_speed_mph": 60, "throttle_pct": 0.6},
        },
        "lap_times": [92.3, 91.8, 93.1],
        "metadata": {"laps": 18, "track": "Barber"},
    }
    flat = flatten_telemetry(telemetry)
    assert 85.0 in flat
    assert 120.5 in flat
    assert 60.0 in flat
    assert 0.6 in flat
    assert 92.3 in flat
    assert 91.8 in flat
    assert 93.1 in flat
    assert 18.0 in flat
    # Strings should not appear
    assert all(isinstance(v, float) for v in flat)


def test_flatten_telemetry_handles_booleans() -> None:
    """Booleans should NOT be included as numbers."""
    data = {"flag": True, "count": 5}
    flat = flatten_telemetry(data)
    assert 5.0 in flat
    assert len(flat) == 1  # Only the int, not the bool


def test_grounded_numbers_pass() -> None:
    telemetry = {
        "corners": {"T5": {"min_speed": 85, "brake_gap_m": 3.0, "delta_s": 0.2}},
    }
    text = "Brake 3m later because you lost 0.2s. Min speed was 85mph."
    result = check_citation_grounding(text, telemetry)
    assert result.verdict == Verdict.PASS
    assert result.score == 1.0


def test_hallucinated_numbers_fail() -> None:
    telemetry = {
        "corners": {"T5": {"min_speed": 85}},
    }
    # 99, 42, 7.7 are not in telemetry
    text = "You hit 99mph in the straight. Lost 42s total. Gap was 7.7m."
    result = check_citation_grounding(text, telemetry)
    assert result.verdict == Verdict.FAIL
    assert result.score < 0.60


def test_tolerance_within_5_percent() -> None:
    """Numbers within 5% of telemetry values should count as grounded."""
    telemetry = {"speed": 100.0}
    # 104.0 is within 5% of 100.0
    text = "Speed was 104mph."
    result = check_citation_grounding(text, telemetry)
    assert result.verdict == Verdict.PASS
    assert result.score == 1.0


def test_tolerance_outside_5_percent() -> None:
    """Numbers outside 5% should NOT count as grounded."""
    telemetry = {"speed": 100.0}
    # 106.0 is outside 5% of 100.0
    text = "Speed was 106mph."
    result = check_citation_grounding(text, telemetry)
    assert result.verdict == Verdict.FAIL
    assert result.score == 0.0


def test_no_numbers_passes() -> None:
    """Text with no numbers should pass (nothing to ground)."""
    telemetry = {"speed": 100.0}
    text = "Good session overall with consistent braking."
    result = check_citation_grounding(text, telemetry)
    assert result.verdict == Verdict.PASS

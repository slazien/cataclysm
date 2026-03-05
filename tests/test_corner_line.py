"""Tests for cataclysm.corner_line — corner-level line analysis."""

from __future__ import annotations

import numpy as np
import pytest

from cataclysm.corner_line import (
    CornerLineProfile,
    analyze_corner_lines,
    classify_line_error,
    detect_apex_fraction,
    format_line_analysis_for_prompt,
)
from cataclysm.corners import Corner
from cataclysm.gps_line import GPSTrace, ReferenceCenterline, compute_reference_centerline


def _make_straight_traces(
    n_laps: int = 5, n_points: int = 300
) -> tuple[list[GPSTrace], ReferenceCenterline]:
    """Create traces on a simple straight line for testing."""
    rng = np.random.default_rng(42)
    distance = np.linspace(0, n_points * 0.7, n_points)
    traces = []
    for i in range(n_laps):
        e = np.linspace(0, 200, n_points) + rng.normal(0, 0.2, n_points)
        n = np.zeros(n_points) + rng.normal(0, 0.2, n_points)
        traces.append(GPSTrace(e=e, n=n, distance_m=distance, lap_number=i + 1))
    ref = compute_reference_centerline(traces)
    assert ref is not None
    return traces, ref


class TestDetectApexFraction:
    def test_apex_at_midpoint(self) -> None:
        """V-shaped offsets should detect apex at middle."""
        offsets = np.concatenate([np.linspace(2, -1, 50), np.linspace(-1, 2, 50)])
        frac = detect_apex_fraction(offsets, 0, 100)
        assert 0.45 < frac < 0.55

    def test_early_apex(self) -> None:
        """Minimum early in the corner -> early apex."""
        offsets = np.concatenate([np.linspace(2, -1, 20), np.linspace(-1, 2, 80)])
        frac = detect_apex_fraction(offsets, 0, 100)
        assert frac < 0.3

    def test_late_apex(self) -> None:
        """Minimum late in the corner -> late apex."""
        offsets = np.concatenate([np.linspace(2, -1, 80), np.linspace(-1, 2, 20)])
        frac = detect_apex_fraction(offsets, 0, 100)
        assert frac > 0.7

    def test_empty_range(self) -> None:
        offsets = np.array([1.0, 2.0, 3.0])
        frac = detect_apex_fraction(offsets, 5, 5)
        assert frac == 0.5


class TestClassifyLineError:
    def test_early_apex_classified(self) -> None:
        error, severity = classify_line_error(
            apex_fraction=0.25, d_entry=0.0, d_exit=0.0
        )
        assert error == "early_apex"

    def test_late_apex_classified(self) -> None:
        error, severity = classify_line_error(
            apex_fraction=0.75, d_entry=0.0, d_exit=0.0
        )
        assert error == "late_apex"

    def test_good_line(self) -> None:
        error, severity = classify_line_error(
            apex_fraction=0.55, d_entry=0.2, d_exit=0.2
        )
        assert error == "good_line"

    def test_wide_entry(self) -> None:
        error, severity = classify_line_error(
            apex_fraction=0.55, d_entry=1.5, d_exit=0.2
        )
        assert error == "wide_entry"

    def test_pinched_exit(self) -> None:
        error, severity = classify_line_error(
            apex_fraction=0.55, d_entry=0.2, d_exit=-1.5
        )
        assert error == "pinched_exit"

    def test_minor_severity(self) -> None:
        _, severity = classify_line_error(
            apex_fraction=0.55, d_entry=0.1, d_exit=0.1
        )
        assert severity == "minor"

    def test_major_severity(self) -> None:
        _, severity = classify_line_error(
            apex_fraction=0.15, d_entry=2.0, d_exit=2.0
        )
        assert severity == "major"


class TestAnalyzeCornerLines:
    def test_empty_input(self) -> None:
        traces, ref = _make_straight_traces()
        result = analyze_corner_lines([], ref, [])
        assert result == []

    def test_single_corner(self) -> None:
        traces, ref = _make_straight_traces()
        corner = Corner(
            number=1,
            entry_distance_m=30.0,
            exit_distance_m=80.0,
            apex_distance_m=55.0,
            min_speed_mps=20.0,
            brake_point_m=20.0,
            peak_brake_g=-0.5,
            throttle_commit_m=70.0,
            apex_type="mid",
        )
        profiles = analyze_corner_lines(traces, ref, [corner])
        assert len(profiles) == 1
        assert profiles[0].corner_number == 1
        assert profiles[0].n_laps == 5

    def test_profile_fields_populated(self) -> None:
        traces, ref = _make_straight_traces()
        corner = Corner(
            number=1,
            entry_distance_m=30.0,
            exit_distance_m=80.0,
            apex_distance_m=55.0,
            min_speed_mps=20.0,
            brake_point_m=20.0,
            peak_brake_g=-0.5,
            throttle_commit_m=70.0,
            apex_type="mid",
        )
        profiles = analyze_corner_lines(traces, ref, [corner])
        p = profiles[0]
        assert isinstance(p.d_entry_median, float)
        assert isinstance(p.d_apex_sd, float)
        assert p.line_error_type in (
            "early_apex",
            "late_apex",
            "wide_entry",
            "tight_entry",
            "pinched_exit",
            "wide_exit",
            "good_line",
        )
        assert p.severity in ("minor", "moderate", "major")
        assert p.consistency_tier in ("expert", "consistent", "developing", "novice")
        assert p.allen_berg_type in ("A", "B", "C")


class TestFormatLineAnalysis:
    def test_empty_profiles(self) -> None:
        assert format_line_analysis_for_prompt([]) == ""

    def test_produces_xml(self) -> None:
        profile = CornerLineProfile(
            corner_number=5,
            n_laps=10,
            d_entry_median=0.3,
            d_apex_median=-0.5,
            d_exit_median=0.1,
            apex_fraction_median=0.45,
            d_apex_sd=0.4,
            line_error_type="early_apex",
            severity="moderate",
            consistency_tier="consistent",
            allen_berg_type="A",
        )
        text = format_line_analysis_for_prompt([profile])
        assert "<line_analysis>" in text
        assert 'corner number="5"' in text
        assert "early_apex" in text
        assert "consistent" in text

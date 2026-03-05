"""Tests for cataclysm.corner_line — corner-level line analysis."""

from __future__ import annotations

import numpy as np

from cataclysm.corner_line import (
    CornerLineProfile,
    _assign_priority_ranks,
    _infer_berg_type_and_gap,
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
        error, severity = classify_line_error(apex_fraction=0.25, d_entry=0.0, d_exit=0.0)
        assert error == "early_apex"

    def test_late_apex_classified(self) -> None:
        error, severity = classify_line_error(apex_fraction=0.75, d_entry=0.0, d_exit=0.0)
        assert error == "late_apex"

    def test_good_line(self) -> None:
        error, severity = classify_line_error(apex_fraction=0.55, d_entry=0.2, d_exit=0.2)
        assert error == "good_line"

    def test_wide_entry(self) -> None:
        error, severity = classify_line_error(apex_fraction=0.55, d_entry=1.5, d_exit=0.2)
        assert error == "wide_entry"

    def test_pinched_exit(self) -> None:
        error, severity = classify_line_error(apex_fraction=0.55, d_entry=0.2, d_exit=-1.5)
        assert error == "pinched_exit"

    def test_minor_severity(self) -> None:
        _, severity = classify_line_error(apex_fraction=0.55, d_entry=0.1, d_exit=0.1)
        assert severity == "minor"

    def test_major_severity(self) -> None:
        _, severity = classify_line_error(apex_fraction=0.15, d_entry=2.0, d_exit=2.0)
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


def _make_corner(
    number: int,
    entry_distance_m: float,
    exit_distance_m: float,
) -> Corner:
    """Minimal corner helper for priority/gap tests."""
    return Corner(
        number=number,
        entry_distance_m=entry_distance_m,
        exit_distance_m=exit_distance_m,
        apex_distance_m=(entry_distance_m + exit_distance_m) / 2,
        min_speed_mps=20.0,
        brake_point_m=entry_distance_m - 10.0,
        peak_brake_g=-0.5,
        throttle_commit_m=exit_distance_m - 5.0,
        apex_type="mid",
    )


class TestCornerPriority:
    """Tests for straight_after_m and priority_rank (Task 1)."""

    def test_straight_after_m_computed(self) -> None:
        """Gap between corner exit and next corner entry should be straight_after_m."""
        # C1 exits at 100, C2 enters at 300 => gap = 200m (Type A)
        # C2 exits at 350, C3 enters at 380 => gap = 30m (C)
        corners = [
            _make_corner(1, entry_distance_m=50.0, exit_distance_m=100.0),
            _make_corner(2, entry_distance_m=300.0, exit_distance_m=350.0),
            _make_corner(3, entry_distance_m=380.0, exit_distance_m=420.0),
        ]
        traces, ref = _make_straight_traces(n_laps=5, n_points=700)
        profiles = analyze_corner_lines(traces, ref, corners)

        assert len(profiles) == 3
        # C1: gap to C2 = 300 - 100 = 200m
        assert profiles[0].straight_after_m == 200.0
        # C2: gap to C3 = 380 - 350 = 30m
        assert profiles[1].straight_after_m == 30.0
        # C3: last corner, no next corner => 0.0
        assert profiles[2].straight_after_m == 0.0

    def test_type_a_gets_lowest_rank(self) -> None:
        """Type A corners should get the lowest priority rank number."""
        # C1: type A (200m straight after), C2: type C (30m gap), C3: type C (last)
        corners = [
            _make_corner(1, entry_distance_m=50.0, exit_distance_m=100.0),
            _make_corner(2, entry_distance_m=300.0, exit_distance_m=350.0),
            _make_corner(3, entry_distance_m=380.0, exit_distance_m=420.0),
        ]
        traces, ref = _make_straight_traces(n_laps=5, n_points=700)
        profiles = analyze_corner_lines(traces, ref, corners)

        # C1 is Type A (200m straight), should be rank 1
        assert profiles[0].priority_rank == 1
        # C2 and C3 are Type C, rank 2 and 3
        assert profiles[1].priority_rank > profiles[0].priority_rank
        assert profiles[2].priority_rank > profiles[0].priority_rank

    def test_longer_straight_lower_rank_among_type_a(self) -> None:
        """Among Type A corners, longer straight_after_m gets lower rank."""
        # C1: 200m straight after (Type A), C2: 300m straight after (Type A)
        # C3: exits at 850, last corner -> 0m
        corners = [
            _make_corner(1, entry_distance_m=50.0, exit_distance_m=100.0),
            _make_corner(2, entry_distance_m=300.0, exit_distance_m=350.0),
            _make_corner(3, entry_distance_m=650.0, exit_distance_m=700.0),
        ]
        traces, ref = _make_straight_traces(n_laps=5, n_points=1500)
        profiles = analyze_corner_lines(traces, ref, corners)

        # C1: gap = 300-100 = 200m (A), C2: gap = 650-350 = 300m (A), C3: last = 0m (C)
        assert profiles[0].allen_berg_type == "A"
        assert profiles[1].allen_berg_type == "A"
        # C2 has longer straight (300m) => lower rank than C1 (200m)
        assert profiles[1].priority_rank < profiles[0].priority_rank

    def test_infer_berg_type_and_gap_returns_tuple(self) -> None:
        """Refactored function should return (type, gap_distance)."""
        corners = [
            _make_corner(1, entry_distance_m=50.0, exit_distance_m=100.0),
            _make_corner(2, entry_distance_m=300.0, exit_distance_m=350.0),
        ]
        berg_type, gap = _infer_berg_type_and_gap(corners[0], corners)
        assert berg_type == "A"
        assert gap == 200.0

    def test_assign_priority_ranks_in_place(self) -> None:
        """_assign_priority_ranks should mutate profiles in place."""
        profiles = [
            CornerLineProfile(
                corner_number=1,
                n_laps=5,
                d_entry_median=0.0,
                d_apex_median=0.0,
                d_exit_median=0.0,
                apex_fraction_median=0.5,
                d_apex_sd=0.3,
                line_error_type="good_line",
                severity="minor",
                consistency_tier="expert",
                allen_berg_type="C",
                straight_after_m=30.0,
                priority_rank=0,
            ),
            CornerLineProfile(
                corner_number=2,
                n_laps=5,
                d_entry_median=0.0,
                d_apex_median=0.0,
                d_exit_median=0.0,
                apex_fraction_median=0.5,
                d_apex_sd=0.3,
                line_error_type="good_line",
                severity="minor",
                consistency_tier="expert",
                allen_berg_type="A",
                straight_after_m=250.0,
                priority_rank=0,
            ),
        ]
        _assign_priority_ranks(profiles)
        # Type A corner should be rank 1
        assert profiles[1].priority_rank == 1
        assert profiles[0].priority_rank == 2

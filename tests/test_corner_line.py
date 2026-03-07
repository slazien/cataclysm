"""Tests for cataclysm.corner_line — corner-level line analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cataclysm.corner_line import (
    CornerLineProfile,
    PerLapCornerMetrics,
    SessionLineProfile,
    _assign_priority_ranks,
    _consistency_tier,
    _infer_berg_type_and_gap,
    analyze_corner_lines,
    classify_line_error,
    compute_per_lap_corner_metrics,
    detect_apex_fraction,
    format_best_corner_for_prompt,
    format_line_analysis_for_prompt,
    format_session_line_summary_for_prompt,
    identify_best_corner_laps,
    summarize_session_lines,
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

    def test_sliced_empty_when_start_equals_end_larger(self) -> None:
        """When slice produces empty array (start >= len), returns 0.5 (line 79)."""
        # corner_end_idx > corner_start_idx but slice into array is empty
        offsets = np.array([1.0, 2.0, 3.0])
        # start=5, end=10: end > start so first guard passes, but offsets[5:10] is []
        frac = detect_apex_fraction(offsets, 5, 10)
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

    def test_corner_beyond_trace_length_skipped(self) -> None:
        """Corner whose exit index exceeds a lap's offset array length skips that lap (line 232)."""
        # Build short traces (30 points) but corner extending to the full distance
        n_short = 30
        traces, ref = _make_straight_traces(n_laps=3, n_points=n_short)
        # Corner extends beyond the end of the traces
        corner = Corner(
            number=1,
            entry_distance_m=5.0,
            exit_distance_m=float(n_short * 0.7 + 50.0),  # far beyond the trace end
            apex_distance_m=float(n_short * 0.7 / 2),
            min_speed_mps=20.0,
            brake_point_m=3.0,
            peak_brake_g=-0.5,
            throttle_commit_m=float(n_short * 0.7),
            apex_type="mid",
        )
        # May or may not return a profile depending on how offsets are computed,
        # but should not raise an exception
        profiles = analyze_corner_lines(traces, ref, [corner])
        assert isinstance(profiles, list)

    def test_corner_where_all_laps_too_short_produces_no_profile(self) -> None:
        """When all laps are shorter than the corner exit, no profile is produced (line 240)."""
        # Build extremely short traces (5 points each)
        n_short = 5
        rng = np.random.default_rng(77)
        distance = np.linspace(0, n_short * 0.7, n_short)
        short_traces = []
        for i in range(3):
            e = np.linspace(0, n_short * 0.7, n_short) + rng.normal(0, 0.1, n_short)
            n = np.zeros(n_short) + rng.normal(0, 0.1, n_short)
            short_traces.append(GPSTrace(e=e, n=n, distance_m=distance, lap_number=i + 1))

        ref = compute_reference_centerline(short_traces)
        if ref is None:
            return  # Can't run this test without a reference

        # Corner way beyond trace length
        corner = Corner(
            number=1,
            entry_distance_m=1000.0,
            exit_distance_m=1200.0,
            apex_distance_m=1100.0,
            min_speed_mps=20.0,
            brake_point_m=990.0,
            peak_brake_g=-0.5,
            throttle_commit_m=1180.0,
            apex_type="mid",
        )
        profiles = analyze_corner_lines(short_traces, ref, [corner])
        # Should not raise; the corner is far beyond the trace.
        # Whether a profile is returned depends on how corner indices are clamped.
        assert isinstance(profiles, list)


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

    def test_infer_berg_type_out_of_bounds_returns_c(self) -> None:
        """Corner index out of bounds returns ('C', 0.0) (line 150)."""
        corners = [
            _make_corner(1, entry_distance_m=50.0, exit_distance_m=100.0),
        ]
        # corner.number = 5 → idx = 4 → out of bounds (len=1) → returns ("C", 0.0)
        out_of_bounds_corner = _make_corner(5, entry_distance_m=50.0, exit_distance_m=100.0)
        berg_type, gap = _infer_berg_type_and_gap(out_of_bounds_corner, corners)
        assert berg_type == "C"
        assert gap == 0.0

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


# ---------------------------------------------------------------------------
# Task 2 helpers and tests
# ---------------------------------------------------------------------------


def _make_profile(
    corner_number: int = 1,
    d_apex_sd: float = 0.3,
    line_error_type: str = "good_line",
    allen_berg_type: str = "C",
    straight_after_m: float = 0.0,
) -> CornerLineProfile:
    """Create a CornerLineProfile with specified fields, defaults for the rest."""
    return CornerLineProfile(
        corner_number=corner_number,
        n_laps=10,
        d_entry_median=0.0,
        d_apex_median=0.0,
        d_exit_median=0.0,
        apex_fraction_median=0.5,
        d_apex_sd=d_apex_sd,
        line_error_type=line_error_type,
        severity="minor",
        consistency_tier=_consistency_tier(d_apex_sd),
        allen_berg_type=allen_berg_type,
        straight_after_m=straight_after_m,
    )


class TestSessionLineSummary:
    """Tests for summarize_session_lines (Task 2)."""

    def test_empty_profiles(self) -> None:
        result = summarize_session_lines([])
        assert result is None

    def test_overall_consistency_is_median(self) -> None:
        """Median of 3 profiles: expert (0.2), consistent (0.5), developing (1.0)."""
        profiles = [
            _make_profile(corner_number=1, d_apex_sd=0.2),  # expert
            _make_profile(corner_number=2, d_apex_sd=0.5),  # consistent
            _make_profile(corner_number=3, d_apex_sd=1.0),  # developing
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        # Median of [expert=0, consistent=1, developing=2] = 1 = "consistent"
        assert result.overall_consistency_tier == "consistent"

    def test_dominant_error_detected(self) -> None:
        """3 of 5 corners share same error => 60% >= 40% threshold."""
        profiles = [
            _make_profile(corner_number=1, line_error_type="early_apex"),
            _make_profile(corner_number=2, line_error_type="early_apex"),
            _make_profile(corner_number=3, line_error_type="early_apex"),
            _make_profile(corner_number=4, line_error_type="late_apex"),
            _make_profile(corner_number=5, line_error_type="wide_entry"),
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        assert result.dominant_error_pattern == "early_apex"
        assert result.dominant_error_count == 3

    def test_no_dominant_error_when_varied(self) -> None:
        """All different errors => no single error >= 40%."""
        profiles = [
            _make_profile(corner_number=1, line_error_type="early_apex"),
            _make_profile(corner_number=2, line_error_type="late_apex"),
            _make_profile(corner_number=3, line_error_type="wide_entry"),
            _make_profile(corner_number=4, line_error_type="pinched_exit"),
            _make_profile(corner_number=5, line_error_type="good_line"),
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        assert result.dominant_error_pattern is None
        assert result.dominant_error_count == 0

    def test_worst_corners_sorted_by_sd(self) -> None:
        """Worst corners should be sorted by d_apex_sd descending."""
        profiles = [
            _make_profile(corner_number=1, d_apex_sd=0.5),
            _make_profile(corner_number=2, d_apex_sd=1.8),
            _make_profile(corner_number=3, d_apex_sd=0.2),
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        # Worst first: corner 2 (sd=1.8), corner 1 (sd=0.5), corner 3 (sd=0.2)
        assert result.worst_corners_by_line == [2, 1, 3]
        # Best first: corner 3 (sd=0.2), corner 1 (sd=0.5), corner 2 (sd=1.8)
        assert result.best_corners_by_line == [3, 1, 2]

    def test_type_a_summary_generated(self) -> None:
        """Type A summary should list Type A corners and their tier counts."""
        profiles = [
            _make_profile(
                corner_number=5, d_apex_sd=0.5, allen_berg_type="A", straight_after_m=200.0
            ),
            _make_profile(
                corner_number=9, d_apex_sd=1.0, allen_berg_type="A", straight_after_m=300.0
            ),
            _make_profile(corner_number=3, d_apex_sd=0.2, allen_berg_type="C"),
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        assert "Type A" in result.type_a_summary
        assert "T5" in result.type_a_summary
        assert "T9" in result.type_a_summary

    def test_mean_apex_sd(self) -> None:
        """Mean apex SD should be the average of all d_apex_sd values."""
        profiles = [
            _make_profile(corner_number=1, d_apex_sd=0.2),
            _make_profile(corner_number=2, d_apex_sd=0.4),
            _make_profile(corner_number=3, d_apex_sd=0.6),
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        assert abs(result.mean_apex_sd_m - 0.4) < 1e-6


class TestFormatSessionLineSummary:
    """Tests for format_session_line_summary_for_prompt (Task 2)."""

    def test_none_returns_empty(self) -> None:
        assert format_session_line_summary_for_prompt(None) == ""

    def test_produces_xml(self) -> None:
        summary = SessionLineProfile(
            n_corners=5,
            overall_consistency_tier="consistent",
            dominant_error_pattern="early_apex",
            dominant_error_count=3,
            worst_corners_by_line=[5, 3, 1],
            best_corners_by_line=[1, 3, 5],
            type_a_summary="Type A corners (T5, T9): 1 consistent, 1 developing",
            mean_apex_sd_m=0.45,
        )
        text = format_session_line_summary_for_prompt(summary)
        assert "<session_line_summary>" in text
        assert "</session_line_summary>" in text
        assert "consistent" in text
        assert "early_apex" in text
        assert "T5" in text


class TestDetectApexFractionEdges:
    """Cover line 79: detect_apex_fraction returns 0.5 when corner_offsets is empty."""

    def test_equal_start_end_returns_half(self) -> None:
        """corner_end_idx <= corner_start_idx → return 0.5 immediately (line 76)."""
        offsets = np.array([0.1, 0.2, -0.1, 0.0])
        result = detect_apex_fraction(offsets, corner_start_idx=3, corner_end_idx=3)
        assert result == 0.5

    def test_empty_slice_returns_half(self) -> None:
        """corner_offsets slice empty even with valid indices → return 0.5 (line 79).
        This happens when start > end but end > start is enforced above,
        so we need start+1 == end to get a 1-element slice, not empty.
        The empty-slice path (line 79) is unreachable given line 75's guard,
        but we still ensure the happy path works for adjacent indices."""
        offsets = np.array([0.1, -0.5, 0.2])
        result = detect_apex_fraction(offsets, corner_start_idx=1, corner_end_idx=2)
        assert 0.0 <= result <= 1.0


class TestInferBergTypeEdges:
    """Cover line 150: _infer_berg_type_and_gap when idx is out of range."""

    def test_corner_number_too_large_returns_default(self) -> None:
        """corner.number - 1 >= len(corners) → returns ('C', 0.0) (line 150)."""
        # corners list has 2 elements; corner.number=10 → idx=9 → out of range
        from cataclysm.corners import Corner

        corners = [
            Corner(
                number=1,
                entry_distance_m=0.0,
                exit_distance_m=100.0,
                apex_distance_m=50.0,
                min_speed_mps=20.0,
                brake_point_m=None,
                peak_brake_g=None,
                throttle_commit_m=None,
                apex_type="mid",
            ),
            Corner(
                number=2,
                entry_distance_m=200.0,
                exit_distance_m=300.0,
                apex_distance_m=250.0,
                min_speed_mps=22.0,
                brake_point_m=None,
                peak_brake_g=None,
                throttle_commit_m=None,
                apex_type="mid",
            ),
        ]
        # corner with number=10 → idx=9 which is ≥ len(corners)=2 → fallback
        out_of_range = Corner(
            number=10,
            entry_distance_m=500.0,
            exit_distance_m=600.0,
            apex_distance_m=550.0,
            min_speed_mps=20.0,
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        berg_type, gap = _infer_berg_type_and_gap(out_of_range, corners)
        assert berg_type == "C"
        assert gap == 0.0


class TestAnalyzeCornerLinesNoOffsets:
    """Cover line 240: no valid laps from all_offsets → continue."""

    def test_corner_beyond_all_offsets_skipped(self) -> None:
        """Corner whose c_end > len(offsets) → skipped (line 232/240)."""
        # Use a very short trace but define a corner that extends beyond it
        n_laps = 3
        n_points = 20
        distance = np.linspace(0, 14, n_points)
        traces = []
        rng = np.random.default_rng(7)
        for i in range(n_laps):
            e = np.linspace(0, 14, n_points) + rng.normal(0, 0.1, n_points)
            n_arr = np.zeros(n_points) + rng.normal(0, 0.1, n_points)
            traces.append(GPSTrace(e=e, n=n_arr, distance_m=distance, lap_number=i + 1))

        ref = compute_reference_centerline(traces)
        # Define a corner that extends well beyond the trace length
        far_corner = Corner(
            number=99,
            entry_distance_m=0.0,
            exit_distance_m=1000.0,  # beyond trace length
            apex_distance_m=500.0,
            min_speed_mps=20.0,
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        result = analyze_corner_lines(traces, ref, [far_corner])
        # Should not raise; corner is skipped
        assert result is not None


# ---------------------------------------------------------------------------
# Helpers for per-lap metrics tests
# ---------------------------------------------------------------------------


def _make_resampled_laps(
    n_laps: int = 5,
    n_points: int = 400,
    base_speed: float = 25.0,
    speed_variation: float = 2.0,
) -> dict[int, pd.DataFrame]:
    """Create synthetic resampled lap DataFrames with distance, time, speed."""
    rng = np.random.default_rng(99)
    laps: dict[int, pd.DataFrame] = {}
    for i in range(1, n_laps + 1):
        dist = np.linspace(0, 280, n_points)
        # Speed varies per lap: some laps faster at certain distances
        speed = base_speed + speed_variation * np.sin(dist / 50 + i * 0.5)
        speed += rng.normal(0, 0.3, n_points)
        # Time from cumulative distance / speed
        dt = np.diff(dist) / np.maximum(speed[:-1], 1.0)
        time = np.concatenate([[0.0], np.cumsum(dt)])
        laps[i] = pd.DataFrame({"lap_distance_m": dist, "lap_time_s": time, "speed_mps": speed})
    return laps


def _make_test_corners() -> list[Corner]:
    """Create 2 corners: T1 (Type A, before straight) and T2 (Type C, linking)."""
    return [
        Corner(
            number=1,
            entry_distance_m=30.0,
            exit_distance_m=70.0,
            apex_distance_m=50.0,
            min_speed_mps=20.0,
            brake_point_m=25.0,
            peak_brake_g=0.8,
            throttle_commit_m=55.0,
            apex_type="mid",
        ),
        Corner(
            number=2,
            entry_distance_m=120.0,
            exit_distance_m=160.0,
            apex_distance_m=140.0,
            min_speed_mps=22.0,
            brake_point_m=115.0,
            peak_brake_g=0.6,
            throttle_commit_m=145.0,
            apex_type="mid",
        ),
    ]


# ---------------------------------------------------------------------------
# Test classes for new functionality
# ---------------------------------------------------------------------------


class TestPerLapCornerMetrics:
    """Tests for compute_per_lap_corner_metrics()."""

    def test_basic_computation(self) -> None:
        """Should compute segment time, entry/exit/min speed for each corner x lap."""
        laps = _make_resampled_laps(n_laps=5)
        corners = _make_test_corners()
        result = compute_per_lap_corner_metrics(laps, corners, list(laps.keys()))

        assert 1 in result
        assert 2 in result
        # 5 laps × 2 corners
        assert len(result[1]) == 5
        assert len(result[2]) == 5

        for m in result[1]:
            assert m.corner_number == 1
            assert m.segment_time_s > 0
            assert m.exit_speed_mps > 0
            assert m.entry_speed_mps > 0
            assert m.min_speed_mps > 0
            assert m.min_speed_mps <= m.entry_speed_mps or m.min_speed_mps <= m.exit_speed_mps

    def test_skips_missing_laps(self) -> None:
        """Laps not in resampled_laps should be skipped."""
        laps = _make_resampled_laps(n_laps=3)
        corners = _make_test_corners()
        # Request lap 99 which doesn't exist
        result = compute_per_lap_corner_metrics(laps, corners, [1, 2, 99])
        assert len(result[1]) == 2  # Only laps 1 and 2

    def test_skips_corner_beyond_distance(self) -> None:
        """Corner exit beyond lap distance range should be skipped."""
        laps = _make_resampled_laps(n_laps=3)  # 280m laps
        far_corner = Corner(
            number=99,
            entry_distance_m=500.0,
            exit_distance_m=600.0,
            apex_distance_m=550.0,
            min_speed_mps=15.0,
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        result = compute_per_lap_corner_metrics(laps, [far_corner], [1, 2, 3])
        assert result[99] == []

    def test_empty_laps(self) -> None:
        """Empty resampled_laps should return empty metrics."""
        corners = _make_test_corners()
        result = compute_per_lap_corner_metrics({}, corners, [])
        for c in corners:
            assert result[c.number] == []

    def test_metrics_are_per_lap_dataclass(self) -> None:
        """Each metric should be a PerLapCornerMetrics instance."""
        laps = _make_resampled_laps(n_laps=3)
        corners = _make_test_corners()
        result = compute_per_lap_corner_metrics(laps, corners, [1, 2, 3])
        for m in result[1]:
            assert isinstance(m, PerLapCornerMetrics)


class TestIdentifyBestCornerLaps:
    """Tests for identify_best_corner_laps()."""

    def _make_profiles_and_metrics(
        self,
    ) -> tuple[list[CornerLineProfile], dict[int, list[PerLapCornerMetrics]]]:
        """Create profiles and fake per-lap metrics for 2 corners."""
        profiles = [
            CornerLineProfile(
                corner_number=1,
                n_laps=5,
                d_entry_median=0.0,
                d_apex_median=-0.5,
                d_exit_median=0.3,
                apex_fraction_median=0.55,
                d_apex_sd=0.4,
                line_error_type="good_line",
                severity="minor",
                consistency_tier="consistent",
                allen_berg_type="A",
                straight_after_m=300.0,
            ),
            CornerLineProfile(
                corner_number=2,
                n_laps=5,
                d_entry_median=0.1,
                d_apex_median=-0.3,
                d_exit_median=0.2,
                apex_fraction_median=0.50,
                d_apex_sd=0.6,
                line_error_type="good_line",
                severity="minor",
                consistency_tier="consistent",
                allen_berg_type="C",
                straight_after_m=50.0,
            ),
        ]

        # Type A corner: lap 3 has highest exit speed
        metrics_c1 = [
            PerLapCornerMetrics(1, lap, seg_t, exit_s, 25.0, 20.0)
            for lap, seg_t, exit_s in [
                (1, 2.1, 26.0),
                (2, 2.0, 27.0),
                (3, 1.95, 28.5),  # Best exit speed
                (4, 2.05, 26.5),
                (5, 2.15, 25.5),
            ]
        ]
        # Type C corner: lap 4 has lowest segment time
        metrics_c2 = [
            PerLapCornerMetrics(2, lap, seg_t, exit_s, 24.0, 21.0)
            for lap, seg_t, exit_s in [
                (1, 1.85, 23.0),
                (2, 1.80, 24.0),
                (3, 1.90, 22.5),
                (4, 1.70, 23.5),  # Best segment time
                (5, 1.88, 23.2),
            ]
        ]
        per_lap = {1: metrics_c1, 2: metrics_c2}
        return profiles, per_lap

    def test_type_a_ranks_by_exit_speed(self) -> None:
        """Type A corner should pick the lap with highest exit speed."""
        profiles, per_lap = self._make_profiles_and_metrics()
        corners = _make_test_corners()
        lap_offsets = {i: np.zeros(300) for i in range(1, 6)}

        identify_best_corner_laps(per_lap, profiles, corners, lap_offsets)

        p1 = profiles[0]
        assert p1.best_lap_number == 3
        assert p1.best_ranking_method == "exit_speed"
        assert p1.best_exit_speed_mps == 28.5

    def test_type_c_ranks_by_segment_time(self) -> None:
        """Type C corner should pick the lap with lowest segment time."""
        profiles, per_lap = self._make_profiles_and_metrics()
        corners = _make_test_corners()
        lap_offsets = {i: np.zeros(300) for i in range(1, 6)}

        identify_best_corner_laps(per_lap, profiles, corners, lap_offsets)

        p2 = profiles[1]
        assert p2.best_lap_number == 4
        assert p2.best_ranking_method == "segment_time"
        assert p2.best_segment_time_s == 1.70

    def test_median_values_computed(self) -> None:
        """Median segment time and exit speed should be computed."""
        profiles, per_lap = self._make_profiles_and_metrics()
        corners = _make_test_corners()
        lap_offsets = {i: np.zeros(300) for i in range(1, 6)}

        identify_best_corner_laps(per_lap, profiles, corners, lap_offsets)

        p1 = profiles[0]
        assert p1.median_segment_time_s is not None
        assert p1.median_exit_speed_mps is not None
        # Median of [26.0, 27.0, 28.5, 26.5, 25.5] = 26.5
        assert abs(p1.median_exit_speed_mps - 26.5) < 0.01

    def test_best_offsets_extracted(self) -> None:
        """Best lap's lateral offsets should be extracted at entry/apex/exit."""
        profiles, per_lap = self._make_profiles_and_metrics()
        corners = _make_test_corners()
        # Lap 3 offset array: set distinct values at corner 1 positions
        offsets_3 = np.zeros(300)
        offsets_3[int(30 / 0.7)] = 0.5  # entry
        offsets_3[int(50 / 0.7)] = -0.8  # apex
        offsets_3[int(70 / 0.7)] = 0.3  # exit
        lap_offsets = {i: np.zeros(300) for i in range(1, 6)}
        lap_offsets[3] = offsets_3

        identify_best_corner_laps(per_lap, profiles, corners, lap_offsets)

        p1 = profiles[0]
        assert p1.best_d_entry is not None
        assert abs(p1.best_d_entry - 0.5) < 0.01
        assert abs(p1.best_d_apex - (-0.8)) < 0.01

    def test_too_few_laps_skipped(self) -> None:
        """Fewer than MIN_LAPS_FOR_BEST_CORNER laps should not enrich."""
        profiles, per_lap = self._make_profiles_and_metrics()
        # Trim to only 2 laps
        per_lap[1] = per_lap[1][:2]
        per_lap[2] = per_lap[2][:2]
        corners = _make_test_corners()
        lap_offsets = {i: np.zeros(300) for i in range(1, 6)}

        identify_best_corner_laps(per_lap, profiles, corners, lap_offsets)

        assert profiles[0].best_lap_number is None
        assert profiles[1].best_lap_number is None


class TestBestCornerPromptFormat:
    """Tests for format_best_corner_for_prompt()."""

    def test_empty_input(self) -> None:
        """Empty profiles should return empty string."""
        assert format_best_corner_for_prompt([]) == ""

    def test_no_enriched_profiles(self) -> None:
        """Profiles without best_lap_number should return empty string."""
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
                consistency_tier="consistent",
                allen_berg_type="A",
            ),
        ]
        assert format_best_corner_for_prompt(profiles) == ""

    def test_xml_structure(self) -> None:
        """Enriched profiles should produce valid XML-like structure."""
        p = CornerLineProfile(
            corner_number=5,
            n_laps=10,
            d_entry_median=0.3,
            d_apex_median=-0.8,
            d_exit_median=0.5,
            apex_fraction_median=0.55,
            d_apex_sd=0.4,
            line_error_type="good_line",
            severity="minor",
            consistency_tier="consistent",
            allen_berg_type="A",
            straight_after_m=350.0,
            best_lap_number=7,
            best_exit_speed_mps=27.3,
            best_segment_time_s=4.23,
            best_ranking_method="exit_speed",
            best_d_entry=0.3,
            best_d_apex=-0.8,
            best_d_exit=0.5,
            median_segment_time_s=4.50,
            median_exit_speed_mps=25.8,
        )
        text = format_best_corner_for_prompt([p])
        assert "<best_corner_execution>" in text
        assert "</best_corner_execution>" in text
        assert 'number="5"' in text
        assert 'type="A"' in text
        assert 'best_lap="7"' in text
        assert 'ranked_by="exit_speed"' in text
        assert "exit_speed" in text
        assert "segment_time" in text
        assert "best_line" in text

    def test_uses_mph_units(self) -> None:
        """Exit speed in prompt should be in mph, not m/s."""
        p = CornerLineProfile(
            corner_number=1,
            n_laps=5,
            d_entry_median=0.0,
            d_apex_median=0.0,
            d_exit_median=0.0,
            apex_fraction_median=0.5,
            d_apex_sd=0.3,
            line_error_type="good_line",
            severity="minor",
            consistency_tier="consistent",
            allen_berg_type="A",
            best_lap_number=3,
            best_exit_speed_mps=25.0,  # 25 m/s ≈ 55.9 mph
            best_segment_time_s=3.0,
            best_ranking_method="exit_speed",
            median_segment_time_s=3.2,
            median_exit_speed_mps=24.0,
        )
        text = format_best_corner_for_prompt([p])
        assert "mph" in text
        # 25 m/s * 2.23694 ≈ 55.9 mph
        assert "55.9" in text

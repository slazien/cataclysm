"""Tests for cataclysm.corner_analysis."""

from __future__ import annotations

import pytest

from cataclysm.corner_analysis import (
    SessionCornerAnalysis,
    _compute_correlations,
    _correlation_strength,
    _find_gain_for_corner,
    compute_corner_analysis,
)
from cataclysm.corners import Corner
from cataclysm.gains import (
    CompositeGainResult,
    ConsistencyGainResult,
    GainEstimate,
    SegmentDefinition,
    SegmentGain,
    TheoreticalBestResult,
)
from cataclysm.landmarks import Landmark, LandmarkType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_corner(
    number: int,
    *,
    min_speed_mps: float = 18.0,
    brake_point_m: float | None = 500.0,
    peak_brake_g: float | None = -0.8,
    throttle_commit_m: float | None = 700.0,
    apex_type: str = "mid",
    entry_distance_m: float = 400.0,
    exit_distance_m: float = 750.0,
    apex_distance_m: float = 600.0,
) -> Corner:
    return Corner(
        number=number,
        entry_distance_m=entry_distance_m,
        exit_distance_m=exit_distance_m,
        apex_distance_m=apex_distance_m,
        min_speed_mps=min_speed_mps,
        brake_point_m=brake_point_m,
        peak_brake_g=peak_brake_g,
        throttle_commit_m=throttle_commit_m,
        apex_type=apex_type,
    )


def _make_gain_estimate(corner_gains: dict[int, float]) -> GainEstimate:
    """Build a GainEstimate with specified per-corner consistency gains."""
    seg_gains: list[SegmentGain] = []
    total = 0.0
    for cn, gain in corner_gains.items():
        seg = SegmentDefinition(
            name=f"T{cn}",
            entry_distance_m=cn * 100.0,
            exit_distance_m=cn * 100.0 + 80.0,
            is_corner=True,
        )
        seg_gains.append(
            SegmentGain(
                segment=seg,
                best_time_s=3.0,
                avg_time_s=3.0 + gain,
                gain_s=gain,
                best_lap=1,
            )
        )
        total += gain

    return GainEstimate(
        consistency=ConsistencyGainResult(
            segment_gains=seg_gains,
            total_gain_s=total,
            avg_lap_time_s=95.0,
            best_lap_time_s=92.0,
        ),
        composite=CompositeGainResult(
            segment_gains=[],
            composite_time_s=91.5,
            best_lap_time_s=92.0,
            gain_s=0.5,
        ),
        theoretical=TheoreticalBestResult(
            sector_size_m=10.0,
            n_sectors=10,
            theoretical_time_s=91.0,
            best_lap_time_s=92.0,
            gain_s=1.0,
        ),
        clean_lap_numbers=[1, 2, 3],
        best_lap_number=1,
    )


def _make_landmarks() -> list[Landmark]:
    return [
        Landmark("T5 3 board", 490.0, LandmarkType.brake_board),
        Landmark("T5 2 board", 530.0, LandmarkType.brake_board),
        Landmark("pit wall end", 450.0, LandmarkType.structure),
    ]


# ---------------------------------------------------------------------------
# Tests: happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """8 laps with gains and landmarks — full analysis."""

    @pytest.fixture
    def all_lap_corners(self) -> dict[int, list[Corner]]:
        corners: dict[int, list[Corner]] = {}
        for lap in range(1, 9):
            # Vary brake/speed slightly per lap; lap 1 is best
            bp_offset = (lap - 1) * 2.0
            speed_offset = (lap - 1) * 0.3
            corners[lap] = [
                _make_corner(
                    5,
                    min_speed_mps=18.0 - speed_offset,
                    brake_point_m=500.0 + bp_offset,
                    peak_brake_g=-0.8 - (lap - 1) * 0.02,
                    throttle_commit_m=700.0 + bp_offset,
                    apex_type="late" if lap <= 6 else "mid",
                    entry_distance_m=550.0,
                    exit_distance_m=800.0,
                    apex_distance_m=650.0,
                ),
            ]
        return corners

    @pytest.fixture
    def gains(self) -> GainEstimate:
        return _make_gain_estimate({5: 0.42})

    @pytest.fixture
    def landmarks(self) -> list[Landmark]:
        return _make_landmarks()

    def test_returns_session_analysis(
        self,
        all_lap_corners: dict[int, list[Corner]],
        gains: GainEstimate,
        landmarks: list[Landmark],
    ) -> None:
        result = compute_corner_analysis(all_lap_corners, gains, None, landmarks, best_lap=1)
        assert isinstance(result, SessionCornerAnalysis)
        assert result.best_lap == 1
        assert result.n_laps_analyzed == 8

    def test_corner_analysis_populated(
        self,
        all_lap_corners: dict[int, list[Corner]],
        gains: GainEstimate,
        landmarks: list[Landmark],
    ) -> None:
        result = compute_corner_analysis(all_lap_corners, gains, None, landmarks, best_lap=1)
        assert len(result.corners) == 1
        ca = result.corners[0]
        assert ca.corner_number == 5
        assert ca.n_laps == 8

    def test_min_speed_stats(
        self,
        all_lap_corners: dict[int, list[Corner]],
        gains: GainEstimate,
        landmarks: list[Landmark],
    ) -> None:
        result = compute_corner_analysis(all_lap_corners, gains, None, landmarks, best_lap=1)
        ca = result.corners[0]
        # Best (max) min speed should be from lap 1: 18.0 m/s * 2.23694
        expected_best_mph = 18.0 * 2.23694
        assert abs(ca.stats_min_speed.best - expected_best_mph) < 0.1
        assert ca.stats_min_speed.best_lap == 1
        assert ca.stats_min_speed.std > 0

    def test_brake_stats(
        self,
        all_lap_corners: dict[int, list[Corner]],
        gains: GainEstimate,
        landmarks: list[Landmark],
    ) -> None:
        result = compute_corner_analysis(all_lap_corners, gains, None, landmarks, best_lap=1)
        ca = result.corners[0]
        assert ca.stats_brake_point is not None
        # Best (min) brake point is from lap 1: 500.0
        assert ca.stats_brake_point.best == 500.0
        assert ca.stats_brake_point.std > 0

    def test_gain_from_gains_estimate(
        self,
        all_lap_corners: dict[int, list[Corner]],
        gains: GainEstimate,
        landmarks: list[Landmark],
    ) -> None:
        result = compute_corner_analysis(all_lap_corners, gains, None, landmarks, best_lap=1)
        ca = result.corners[0]
        assert ca.recommendation.gain_s == 0.42

    def test_landmark_resolved(
        self,
        all_lap_corners: dict[int, list[Corner]],
        gains: GainEstimate,
        landmarks: list[Landmark],
    ) -> None:
        result = compute_corner_analysis(all_lap_corners, gains, None, landmarks, best_lap=1)
        ca = result.corners[0]
        assert ca.recommendation.target_brake_landmark is not None
        # Best-lap brake at 500.0, nearest brake_board is T5 3 board at 490.0
        assert "3 board" in ca.recommendation.target_brake_landmark.landmark.name

    def test_time_value_computed(
        self,
        all_lap_corners: dict[int, list[Corner]],
        gains: GainEstimate,
        landmarks: list[Landmark],
    ) -> None:
        result = compute_corner_analysis(all_lap_corners, gains, None, landmarks, best_lap=1)
        ca = result.corners[0]
        assert ca.time_value is not None
        assert ca.time_value.approach_speed_mph > 0
        assert ca.time_value.time_per_meter_ms > 0
        assert ca.time_value.brake_variance_time_cost_s >= 0

    def test_correlations_computed(
        self,
        all_lap_corners: dict[int, list[Corner]],
        gains: GainEstimate,
        landmarks: list[Landmark],
    ) -> None:
        result = compute_corner_analysis(all_lap_corners, gains, None, landmarks, best_lap=1)
        ca = result.corners[0]
        # 8 laps with brake data → should have correlations
        assert len(ca.correlations) >= 1
        corr = ca.correlations[0]
        assert corr.kpi_x == "brake_point"
        assert corr.kpi_y == "min_speed"
        assert corr.n_points == 8

    def test_apex_distribution(
        self,
        all_lap_corners: dict[int, list[Corner]],
        gains: GainEstimate,
        landmarks: list[Landmark],
    ) -> None:
        result = compute_corner_analysis(all_lap_corners, gains, None, landmarks, best_lap=1)
        ca = result.corners[0]
        assert "late" in ca.apex_distribution
        assert ca.apex_distribution["late"] == 6
        assert ca.apex_distribution.get("mid", 0) == 2

    def test_total_consistency_gain(
        self,
        all_lap_corners: dict[int, list[Corner]],
        gains: GainEstimate,
        landmarks: list[Landmark],
    ) -> None:
        result = compute_corner_analysis(all_lap_corners, gains, None, landmarks, best_lap=1)
        assert result.total_consistency_gain_s == 0.42


# ---------------------------------------------------------------------------
# Tests: no gains
# ---------------------------------------------------------------------------


class TestNoGains:
    def test_gain_is_zero(self) -> None:
        corners = {
            1: [_make_corner(1)],
            2: [_make_corner(1, min_speed_mps=17.5)],
        }
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        assert result.total_consistency_gain_s == 0.0
        assert result.corners[0].recommendation.gain_s == 0.0

    def test_sorted_by_corner_number_when_no_gains(self) -> None:
        corners: dict[int, list[Corner]] = {}
        for lap in range(1, 4):
            corners[lap] = [
                _make_corner(3, entry_distance_m=300.0, exit_distance_m=500.0),
                _make_corner(1, entry_distance_m=50.0, exit_distance_m=200.0),
                _make_corner(2, entry_distance_m=200.0, exit_distance_m=300.0),
            ]
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        # All gains are 0 → sorted by corner number
        numbers = [ca.corner_number for ca in result.corners]
        assert numbers == [1, 2, 3]


# ---------------------------------------------------------------------------
# Tests: no landmarks
# ---------------------------------------------------------------------------


class TestNoLandmarks:
    def test_target_brake_landmark_is_none(self) -> None:
        corners = {
            1: [_make_corner(5)],
            2: [_make_corner(5, min_speed_mps=17.0)],
        }
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        assert result.corners[0].recommendation.target_brake_landmark is None


# ---------------------------------------------------------------------------
# Tests: fewer than 4 laps → no correlations
# ---------------------------------------------------------------------------


class TestFewLaps:
    def test_three_laps_no_correlations(self) -> None:
        corners = {
            1: [_make_corner(1)],
            2: [_make_corner(1, min_speed_mps=17.0, brake_point_m=510.0)],
            3: [_make_corner(1, min_speed_mps=16.5, brake_point_m=520.0)],
        }
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        assert result.corners[0].correlations == []


# ---------------------------------------------------------------------------
# Tests: single lap
# ---------------------------------------------------------------------------


class TestSingleLap:
    def test_single_lap_std_zero(self) -> None:
        corners = {1: [_make_corner(1)]}
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        assert len(result.corners) == 1
        ca = result.corners[0]
        assert ca.stats_min_speed.std == 0.0
        assert ca.stats_min_speed.value_range == 0.0
        assert ca.n_laps == 1


# ---------------------------------------------------------------------------
# Tests: missing brake data
# ---------------------------------------------------------------------------


class TestMissingBrakeData:
    def test_some_laps_missing_brake(self) -> None:
        corners = {
            1: [_make_corner(1, brake_point_m=500.0)],
            2: [_make_corner(1, brake_point_m=None, peak_brake_g=None)],
            3: [_make_corner(1, brake_point_m=510.0)],
            4: [_make_corner(1, brake_point_m=None, peak_brake_g=None)],
            5: [_make_corner(1, brake_point_m=505.0)],
        }
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        ca = result.corners[0]
        # min_speed stats should use all 5 laps
        assert ca.stats_min_speed.n_laps == 5
        # brake stats should only use 3 laps with data
        assert ca.stats_brake_point is not None
        assert ca.stats_brake_point.n_laps == 3

    def test_all_laps_missing_brake(self) -> None:
        corners = {
            1: [_make_corner(1, brake_point_m=None, peak_brake_g=None)],
            2: [_make_corner(1, brake_point_m=None, peak_brake_g=None)],
        }
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        ca = result.corners[0]
        assert ca.stats_brake_point is None
        assert ca.time_value is None


# ---------------------------------------------------------------------------
# Tests: gain-descending sort order
# ---------------------------------------------------------------------------


class TestSortOrder:
    def test_sorted_by_gain_descending(self) -> None:
        gains = _make_gain_estimate({1: 0.10, 2: 0.50, 3: 0.25})
        corners: dict[int, list[Corner]] = {}
        for lap in range(1, 4):
            corners[lap] = [
                _make_corner(1, entry_distance_m=50.0, exit_distance_m=200.0),
                _make_corner(2, entry_distance_m=200.0, exit_distance_m=350.0),
                _make_corner(3, entry_distance_m=350.0, exit_distance_m=500.0),
            ]
        result = compute_corner_analysis(corners, gains, None, None, best_lap=1)
        gain_values = [ca.recommendation.gain_s for ca in result.corners]
        assert gain_values == sorted(gain_values, reverse=True)
        assert gain_values == [0.50, 0.25, 0.10]


# ---------------------------------------------------------------------------
# Tests: correlation strength thresholds
# ---------------------------------------------------------------------------


class TestCorrelationStrength:
    def test_strong(self) -> None:
        assert _correlation_strength(0.85) == "strong"
        assert _correlation_strength(-0.75) == "strong"

    def test_moderate(self) -> None:
        assert _correlation_strength(0.55) == "moderate"
        assert _correlation_strength(-0.45) == "moderate"

    def test_weak(self) -> None:
        assert _correlation_strength(0.2) == "weak"
        assert _correlation_strength(-0.1) == "weak"

    def test_boundary_070_is_strong(self) -> None:
        assert _correlation_strength(0.7) == "strong"

    def test_boundary_040_is_moderate(self) -> None:
        assert _correlation_strength(0.4) == "moderate"


# ---------------------------------------------------------------------------
# Tests: _compute_correlations
# ---------------------------------------------------------------------------


class TestComputeCorrelations:
    def test_returns_empty_with_few_points(self) -> None:
        result = _compute_correlations(
            [100.0, 110.0, 105.0],
            [40.0, 38.0, 39.0],
            [1, 2, 3],
            [1, 2, 3],
        )
        assert result == []

    def test_returns_correlation_with_enough_points(self) -> None:
        # Perfectly anti-correlated: earlier brake → higher speed
        bps = [100.0, 110.0, 120.0, 130.0]
        speeds = [44.0, 42.0, 40.0, 38.0]
        result = _compute_correlations(bps, speeds, [1, 2, 3, 4], [1, 2, 3, 4])
        assert len(result) == 1
        assert result[0].r < -0.9  # strong negative
        assert result[0].strength == "strong"
        assert result[0].n_points == 4

    def test_handles_mismatched_laps(self) -> None:
        # Only 3 common laps even though each has 4
        bps = [100.0, 110.0, 120.0, 130.0]
        speeds = [44.0, 42.0, 40.0, 38.0]
        bp_laps = [1, 2, 3, 5]
        sp_laps = [1, 2, 3, 4]
        result = _compute_correlations(bps, speeds, bp_laps, sp_laps)
        # Only 3 common → below threshold
        assert result == []


# ---------------------------------------------------------------------------
# Tests: _find_gain_for_corner
# ---------------------------------------------------------------------------


class TestFindGainForCorner:
    def test_returns_gain_for_matching_corner(self) -> None:
        gains = _make_gain_estimate({5: 0.42})
        assert _find_gain_for_corner(5, gains) == 0.42

    def test_returns_zero_for_missing_corner(self) -> None:
        gains = _make_gain_estimate({5: 0.42})
        assert _find_gain_for_corner(3, gains) == 0.0

    def test_returns_zero_for_none_gains(self) -> None:
        assert _find_gain_for_corner(1, None) == 0.0


# ---------------------------------------------------------------------------
# Tests: empty input
# ---------------------------------------------------------------------------


class TestEmptyInput:
    def test_empty_all_lap_corners(self) -> None:
        result = compute_corner_analysis({}, None, None, None, best_lap=1)
        assert result.corners == []
        assert result.n_laps_analyzed == 0

    def test_empty_corner_lists(self) -> None:
        result = compute_corner_analysis({1: [], 2: []}, None, None, None, best_lap=1)
        assert result.corners == []
        assert result.n_laps_analyzed == 2


# ---------------------------------------------------------------------------
# Tests: multiple corners
# ---------------------------------------------------------------------------


class TestMultipleCorners:
    def test_multi_corner_analysis(self) -> None:
        corners: dict[int, list[Corner]] = {}
        for lap in range(1, 6):
            corners[lap] = [
                _make_corner(
                    1,
                    entry_distance_m=50.0,
                    exit_distance_m=200.0,
                    apex_distance_m=130.0,
                    brake_point_m=30.0,
                    min_speed_mps=20.0 - lap * 0.1,
                ),
                _make_corner(
                    2,
                    entry_distance_m=400.0,
                    exit_distance_m=550.0,
                    apex_distance_m=480.0,
                    brake_point_m=350.0,
                    min_speed_mps=15.0 - lap * 0.2,
                ),
            ]
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        assert len(result.corners) == 2
        # Both should have 5 laps
        for ca in result.corners:
            assert ca.n_laps == 5


# ---------------------------------------------------------------------------
# Tests: corner_type in recommendation
# ---------------------------------------------------------------------------


class TestCornerType:
    def test_slow_corner_type(self) -> None:
        # min_speed < 40 mph → slow
        corners = {1: [_make_corner(1, min_speed_mps=15.0)]}  # ~33.5 mph
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        assert result.corners[0].recommendation.corner_type == "slow"

    def test_medium_corner_type(self) -> None:
        # min_speed 40-80 mph → medium
        corners = {1: [_make_corner(1, min_speed_mps=25.0)]}  # ~55.9 mph
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        assert result.corners[0].recommendation.corner_type == "medium"

    def test_fast_corner_type(self) -> None:
        # min_speed > 80 mph → fast
        corners = {1: [_make_corner(1, min_speed_mps=40.0)]}  # ~89.5 mph
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        assert result.corners[0].recommendation.corner_type == "fast"


# ---------------------------------------------------------------------------
# Tests: flat corner character suppresses brake recommendation
# ---------------------------------------------------------------------------


class TestFlatCornerCharacter:
    def test_flat_corner_no_brake_recommendation(self) -> None:
        """When corner has character='flat', target_brake_m should be None."""
        corners = {
            1: [
                Corner(
                    number=10,
                    entry_distance_m=2000.0,
                    exit_distance_m=2200.0,
                    apex_distance_m=2100.0,
                    min_speed_mps=38.0,  # ~85 mph, fast corner
                    brake_point_m=1950.0,  # falsely detected brake point
                    peak_brake_g=-0.3,
                    throttle_commit_m=2150.0,
                    apex_type="mid",
                    character="flat",
                )
            ],
        }
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        rec = result.corners[0].recommendation
        assert rec.target_brake_m is None
        assert rec.target_brake_landmark is None
        assert rec.character == "flat"

    def test_non_flat_corner_keeps_brake_recommendation(self) -> None:
        """Corners without 'flat' character should keep brake recommendations."""
        corners = {
            1: [_make_corner(5, brake_point_m=500.0)],
        }
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        rec = result.corners[0].recommendation
        assert rec.target_brake_m == 500.0
        assert rec.character is None

    def test_lift_corner_keeps_brake_recommendation(self) -> None:
        """Corners with character='lift' should still show brake data."""
        corners = {
            1: [
                Corner(
                    number=11,
                    entry_distance_m=2200.0,
                    exit_distance_m=2400.0,
                    apex_distance_m=2300.0,
                    min_speed_mps=35.0,
                    brake_point_m=2150.0,
                    peak_brake_g=-0.2,
                    throttle_commit_m=2350.0,
                    apex_type="mid",
                    character="lift",
                )
            ],
        }
        result = compute_corner_analysis(corners, None, None, None, best_lap=1)
        rec = result.corners[0].recommendation
        assert rec.target_brake_m == 2150.0
        assert rec.character == "lift"

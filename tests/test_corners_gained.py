"""Tests for cataclysm.corners_gained — gap decomposition by corner."""

from __future__ import annotations

from cataclysm.corner_analysis import (
    CornerAnalysis,
    CornerRecommendation,
    CornerStats,
    SessionCornerAnalysis,
    TimeValue,
)
from cataclysm.corners_gained import (
    CornersGainedResult,
    _estimate_braking_gain,
    _estimate_consistency_gain,
    _estimate_min_speed_gain,
    _estimate_throttle_gain,
    compute_corners_gained,
    format_corners_gained_for_prompt,
)


def _make_stats(
    best: float = 20.0,
    mean: float = 22.0,
    std: float = 2.0,
    n_laps: int = 8,
) -> CornerStats:
    return CornerStats(
        best=best,
        mean=mean,
        std=std,
        value_range=std * 3,
        best_lap=3,
        n_laps=n_laps,
    )


def _make_corner(
    number: int = 1,
    *,
    brake_std: float = 5.0,
    speed_best: float = 24.0,
    speed_mean: float = 22.0,
    throttle_best: float = 290.0,
    throttle_mean: float = 300.0,
    gain_s: float = 0.2,
    n_laps: int = 8,
    time_value: TimeValue | None = None,
) -> CornerAnalysis:
    return CornerAnalysis(
        corner_number=number,
        n_laps=n_laps,
        stats_min_speed=_make_stats(best=speed_best, mean=speed_mean, n_laps=n_laps),
        stats_brake_point=_make_stats(std=brake_std, n_laps=n_laps),
        stats_peak_brake_g=_make_stats(best=0.9, mean=0.8, std=0.05, n_laps=n_laps),
        stats_throttle_commit=_make_stats(
            best=throttle_best, mean=throttle_mean, std=8.0, n_laps=n_laps
        ),
        apex_distribution={"mid": 8},
        recommendation=CornerRecommendation(
            target_brake_m=145.0,
            target_brake_landmark=None,
            target_min_speed_mph=speed_best,
            gain_s=gain_s,
            corner_type="medium",
        ),
        time_value=time_value,
    )


def _make_session(
    corners: list[CornerAnalysis] | None = None,
    n_laps: int = 8,
) -> SessionCornerAnalysis:
    if corners is None:
        corners = [_make_corner(i) for i in range(1, 5)]
    return SessionCornerAnalysis(
        corners=corners,
        best_lap=3,
        total_consistency_gain_s=0.8,
        n_laps_analyzed=n_laps,
    )


class TestEstimateBrakingGain:
    def test_uses_time_value_when_available(self) -> None:
        tv = TimeValue(
            approach_speed_mph=100.0,
            time_per_meter_ms=22.0,
            brake_variance_time_cost_s=0.15,
        )
        ca = _make_corner(1, time_value=tv)
        gain = _estimate_braking_gain(ca)
        assert gain == 0.15

    def test_falls_back_to_heuristic(self) -> None:
        ca = _make_corner(1, brake_std=10.0)
        gain = _estimate_braking_gain(ca)
        assert gain > 0.1

    def test_returns_zero_with_no_brake_data(self) -> None:
        ca = _make_corner(1)
        ca.stats_brake_point = None
        assert _estimate_braking_gain(ca) == 0.0

    def test_returns_zero_with_few_laps(self) -> None:
        ca = _make_corner(1, n_laps=2)
        assert _estimate_braking_gain(ca) == 0.0


class TestEstimateMinSpeedGain:
    def test_positive_gap(self) -> None:
        ca = _make_corner(1, speed_best=24.0, speed_mean=22.0)
        gain = _estimate_min_speed_gain(ca)
        assert gain > 0.0

    def test_zero_gap(self) -> None:
        ca = _make_corner(1, speed_best=22.0, speed_mean=22.0)
        gain = _estimate_min_speed_gain(ca)
        assert gain == 0.0


class TestEstimateThrottleGain:
    def test_positive_gap(self) -> None:
        ca = _make_corner(1, throttle_best=290.0, throttle_mean=300.0)
        gain = _estimate_throttle_gain(ca)
        assert gain > 0.0

    def test_no_throttle_data(self) -> None:
        ca = _make_corner(1)
        ca.stats_throttle_commit = None
        assert _estimate_throttle_gain(ca) == 0.0


class TestEstimateConsistencyGain:
    def test_uses_recommendation_gain(self) -> None:
        ca = _make_corner(1, gain_s=0.35)
        assert _estimate_consistency_gain(ca) == 0.35

    def test_zero_when_no_gain(self) -> None:
        ca = _make_corner(1, gain_s=0.0)
        assert _estimate_consistency_gain(ca) == 0.0


class TestComputeCornersGained:
    def test_returns_none_for_few_corners(self) -> None:
        session = _make_session(corners=[_make_corner(1)])
        assert compute_corners_gained(session, 90.0, 95.0) is None

    def test_returns_none_for_few_laps(self) -> None:
        session = _make_session(n_laps=2)
        assert compute_corners_gained(session, 90.0, 95.0) is None

    def test_zero_gap_when_at_target(self) -> None:
        session = _make_session()
        result = compute_corners_gained(session, 95.0, 90.0)
        assert result is not None
        assert result.total_gap_s == 0.0

    def test_decomposition_sums_to_gap(self) -> None:
        session = _make_session()
        result = compute_corners_gained(session, 90.0, 95.0)
        assert result is not None
        assert result.total_gap_s == 5.0
        # Sum of categories should not exceed the gap.
        category_sum = (
            result.total_braking_s
            + result.total_min_speed_s
            + result.total_throttle_s
            + result.total_consistency_s
        )
        assert category_sum <= result.total_gap_s + 0.01

    def test_top_opportunities_populated(self) -> None:
        session = _make_session()
        result = compute_corners_gained(session, 90.0, 95.0)
        assert result is not None
        assert len(result.top_opportunities) > 0
        assert len(result.top_opportunities) <= 3
        for corner, category, gain in result.top_opportunities:
            assert isinstance(corner, int)
            assert isinstance(category, str)
            assert gain > 0

    def test_coaching_summary_contains_target(self) -> None:
        session = _make_session()
        result = compute_corners_gained(session, 100.0, 105.0)
        assert result is not None
        assert "1:40" in result.coaching_summary

    def test_per_corner_values_are_non_negative(self) -> None:
        session = _make_session()
        result = compute_corners_gained(session, 90.0, 95.0)
        assert result is not None
        for c in result.per_corner:
            assert c.braking_gain_s >= 0
            assert c.min_speed_gain_s >= 0
            assert c.throttle_gain_s >= 0
            assert c.consistency_gain_s >= 0


class TestFormatCornersGainedForPrompt:
    def test_none_returns_empty(self) -> None:
        assert format_corners_gained_for_prompt(None) == ""

    def test_zero_gap_returns_empty(self) -> None:
        result = CornersGainedResult(
            target_lap_s=90.0,
            current_best_s=89.0,
            total_gap_s=0.0,
            per_corner=[],
            total_braking_s=0.0,
            total_min_speed_s=0.0,
            total_throttle_s=0.0,
            total_consistency_s=0.0,
        )
        assert format_corners_gained_for_prompt(result) == ""

    def test_formatting_contains_key_info(self) -> None:
        session = _make_session()
        result = compute_corners_gained(session, 90.0, 95.0)
        assert result is not None
        text = format_corners_gained_for_prompt(result)
        assert "Corners Gained" in text
        assert "95.00" in text  # current best
        assert "90.00" in text  # target

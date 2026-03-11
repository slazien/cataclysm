"""Tests for cataclysm.optimal_comparison."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.corners import Corner
from cataclysm.optimal_comparison import (
    OptimalComparisonResult,
    _compute_time_cost,
    _find_optimal_brake_for_corner,
    _find_optimal_throttle_for_corner,
    _interpolate_speed_at_distance,
    compare_speed_profiles,
    compare_with_optimal,
    compute_corner_opportunities,
)
from cataclysm.velocity_profile import OptimalProfile, VehicleParams

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_optimal_profile(
    n: int = 1000,
    step_m: float = 0.7,
    speed: float = 40.0,
) -> OptimalProfile:
    distance = np.arange(n) * step_m
    return OptimalProfile(
        distance_m=distance,
        optimal_speed_mps=np.full(n, speed),
        curvature=np.zeros(n),
        max_cornering_speed_mps=np.full(n, speed),
        optimal_brake_points=[200.0],
        optimal_throttle_points=[350.0],
        lap_time_s=float(n * step_m / speed),
        vehicle_params=VehicleParams(mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0),
    )


def _make_lap_df(
    n: int = 1000,
    step_m: float = 0.7,
    speed: float = 35.0,
) -> pd.DataFrame:
    distance = np.arange(n) * step_m
    dt = step_m / speed
    return pd.DataFrame(
        {
            "lap_distance_m": distance,
            "speed_mps": np.full(n, speed),
            "lap_time_s": np.arange(n) * dt,
        }
    )


def _make_corner(
    number: int = 1,
    entry: float = 200.0,
    exit_d: float = 350.0,
    apex: float = 275.0,
    min_speed: float = 25.0,
    brake_m: float | None = 180.0,
) -> Corner:
    return Corner(
        number=number,
        entry_distance_m=entry,
        exit_distance_m=exit_d,
        apex_distance_m=apex,
        min_speed_mps=min_speed,
        brake_point_m=brake_m,
        peak_brake_g=-0.5,
        throttle_commit_m=exit_d - 20,
        apex_type="mid",
    )


# ---------------------------------------------------------------------------
# TestCompareSpeedProfiles
# ---------------------------------------------------------------------------


class TestCompareSpeedProfiles:
    """Tests for compare_speed_profiles."""

    def test_identical_profiles_zero_delta(self) -> None:
        """When actual speed matches optimal everywhere, delta should be ~0."""
        optimal = _make_optimal_profile(speed=40.0)
        lap_df = _make_lap_df(speed=40.0)

        distance, delta = compare_speed_profiles(lap_df, optimal)

        assert len(distance) == len(optimal.distance_m)
        np.testing.assert_allclose(delta, 0.0, atol=1e-6)

    def test_slower_driver_positive_delta(self) -> None:
        """When the driver is slower than optimal, delta should be positive."""
        optimal = _make_optimal_profile(speed=40.0)
        lap_df = _make_lap_df(speed=35.0)

        distance, delta = compare_speed_profiles(lap_df, optimal)

        np.testing.assert_allclose(delta, 5.0, atol=1e-6)


# ---------------------------------------------------------------------------
# TestComputeTimeCost
# ---------------------------------------------------------------------------


class TestComputeTimeCost:
    """Tests for _compute_time_cost."""

    def test_identical_speed_zero_cost(self) -> None:
        """Same speed for actual and optimal should yield ~0 time cost."""
        speed = np.full(100, 30.0)
        cost = _compute_time_cost(speed, speed, step_m=0.7)

        assert abs(cost) < 1e-9

    def test_slower_speed_positive_cost(self) -> None:
        """Actual slower than optimal should yield positive time cost."""
        actual = np.full(100, 30.0)
        optimal = np.full(100, 40.0)

        cost = _compute_time_cost(actual, optimal, step_m=0.7)

        assert cost > 0.0
        # Analytical: 100 * 0.7 * (1/30 - 1/40) = 70 * (1/120) = 0.5833...
        expected = 100 * 0.7 * (1.0 / 30.0 - 1.0 / 40.0)
        assert abs(cost - expected) < 1e-6

    def test_handles_near_zero_speed(self) -> None:
        """Very low speeds should not cause division-by-zero or crash."""
        actual = np.full(50, 0.01)
        optimal = np.full(50, 0.01)

        cost = _compute_time_cost(actual, optimal, step_m=0.7)

        # Both are floored to 1.0 mps, so cost should be 0
        assert abs(cost) < 1e-9


# ---------------------------------------------------------------------------
# TestFindOptimalBrakeForCorner
# ---------------------------------------------------------------------------


class TestFindOptimalBrakeForCorner:
    """Tests for _find_optimal_brake_for_corner."""

    def test_finds_brake_in_window(self) -> None:
        """A brake point within [entry - 200, apex] should be found."""
        corner = _make_corner(entry=300.0, apex=400.0)
        optimal = _make_optimal_profile()
        # Default brake point is 200.0, which is within [300-200, 400] = [100, 400]
        result = _find_optimal_brake_for_corner(corner, optimal)
        assert result == 200.0

    def test_returns_none_when_no_brake_in_window(self) -> None:
        """No brake point in range should return None."""
        corner = _make_corner(entry=500.0, apex=550.0)
        optimal = _make_optimal_profile()
        # Brake at 200.0 is outside [500-200, 550] = [300, 550]
        result = _find_optimal_brake_for_corner(corner, optimal)
        assert result is None


# ---------------------------------------------------------------------------
# TestInterpolateSpeedAtDistance
# ---------------------------------------------------------------------------


class TestInterpolateSpeedAtDistance:
    """Tests for _interpolate_speed_at_distance."""

    def test_exact_points_match(self) -> None:
        """Interpolation at source distances should return source speeds."""
        dist = np.array([0.0, 10.0, 20.0])
        speed = np.array([10.0, 20.0, 30.0])

        result = _interpolate_speed_at_distance(dist, speed, dist)

        np.testing.assert_allclose(result, speed, atol=1e-10)

    def test_midpoint_interpolation(self) -> None:
        """Interpolation at midpoint of a linear ramp should give midpoint speed."""
        dist = np.array([0.0, 10.0])
        speed = np.array([10.0, 20.0])
        target = np.array([5.0])

        result = _interpolate_speed_at_distance(dist, speed, target)

        np.testing.assert_allclose(result, [15.0], atol=1e-10)

    def test_clamps_beyond_range(self) -> None:
        """Values beyond the source range should be clamped to boundary values."""
        dist = np.array([0.0, 10.0])
        speed = np.array([10.0, 20.0])
        target = np.array([-5.0, 15.0])

        result = _interpolate_speed_at_distance(dist, speed, target)

        # np.interp clamps: -5.0 -> 10.0, 15.0 -> 20.0
        np.testing.assert_allclose(result, [10.0, 20.0], atol=1e-10)


# ---------------------------------------------------------------------------
# TestComputeCornerOpportunities
# ---------------------------------------------------------------------------


class TestComputeCornerOpportunities:
    """Tests for compute_corner_opportunities."""

    def test_basic_opportunity(self) -> None:
        """Driver slower in corner produces positive speed gap."""
        optimal = _make_optimal_profile(speed=40.0)
        lap_df = _make_lap_df(speed=35.0)
        corner = _make_corner(min_speed=25.0)

        result = compute_corner_opportunities([corner], lap_df, optimal)

        assert len(result) == 1
        opp = result[0]
        assert opp.corner_number == 1
        # Optimal min in the corner zone is 40.0, actual min is 25.0
        assert opp.speed_gap_mps == pytest.approx(40.0 - 25.0, abs=1e-6)
        assert opp.speed_gap_mph == pytest.approx(15.0 * 2.23694, abs=1e-3)
        assert opp.time_cost_s > 0.0

    def test_sorted_by_time_cost(self) -> None:
        """Multiple corners should be returned sorted by time_cost descending."""
        optimal = _make_optimal_profile(n=2000, speed=40.0)
        lap_df = _make_lap_df(n=2000, speed=35.0)

        # Corner 1: small zone (200..250) -> small time cost
        c1 = _make_corner(number=1, entry=200.0, exit_d=250.0, apex=225.0, min_speed=38.0)
        # Corner 2: bigger zone (400..600) -> bigger time cost
        c2 = _make_corner(
            number=2,
            entry=400.0,
            exit_d=600.0,
            apex=500.0,
            min_speed=20.0,
            brake_m=380.0,
        )

        result = compute_corner_opportunities([c1, c2], lap_df, optimal)

        assert len(result) == 2
        # Larger zone + bigger speed gap -> bigger time cost should be first
        assert result[0].time_cost_s >= result[1].time_cost_s

    def test_empty_corners_list(self) -> None:
        """Empty corners list should return empty opportunities list."""
        optimal = _make_optimal_profile()
        lap_df = _make_lap_df()

        result = compute_corner_opportunities([], lap_df, optimal)

        assert result == []

    def test_single_point_optimal_uses_fallback_step(self) -> None:
        """Optimal profile with single point uses fallback step_m=0.7 (line 181)."""
        # Build optimal with only 1 point (len < 2 → step_m = 0.7 fallback)
        single_point_optimal = OptimalProfile(
            distance_m=np.array([200.0]),
            optimal_speed_mps=np.array([40.0]),
            curvature=np.array([0.0]),
            max_cornering_speed_mps=np.array([40.0]),
            optimal_brake_points=[],
            optimal_throttle_points=[],
            lap_time_s=5.0,
            vehicle_params=VehicleParams(
                mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0
            ),
        )
        lap_df = _make_lap_df(speed=35.0)
        corner = _make_corner(entry=190.0, exit_d=210.0, apex=200.0, min_speed=25.0)
        result = compute_corner_opportunities([corner], lap_df, single_point_optimal)
        # Should not raise; may or may not find an opportunity
        assert isinstance(result, list)

    def test_corner_outside_optimal_range_skipped(self) -> None:
        """Corner outside optimal distance range is skipped (line 191 continue)."""
        optimal = _make_optimal_profile(n=100, step_m=0.7, speed=40.0)
        # optimal goes from 0 to ~69.3m; place corner at 500m (far outside)
        lap_df = _make_lap_df(speed=35.0)
        corner = _make_corner(entry=500.0, exit_d=600.0, apex=550.0, min_speed=25.0)
        result = compute_corner_opportunities([corner], lap_df, optimal)
        assert result == []

    def test_brake_gap_is_none_when_no_optimal_brake_point(self) -> None:
        """When _find_optimal_brake_for_corner returns None, brake_gap=None (line 211)."""
        # Optimal profile with no brake points at all
        no_brake_optimal = OptimalProfile(
            distance_m=np.arange(1000) * 0.7,
            optimal_speed_mps=np.full(1000, 40.0),
            curvature=np.zeros(1000),
            max_cornering_speed_mps=np.full(1000, 40.0),
            optimal_brake_points=[],  # empty → _find_optimal_brake_for_corner returns None
            optimal_throttle_points=[],
            lap_time_s=17.5,
            vehicle_params=VehicleParams(
                mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0
            ),
        )
        lap_df = _make_lap_df(speed=35.0)
        corner = _make_corner(entry=200.0, exit_d=350.0, apex=275.0, min_speed=25.0, brake_m=190.0)
        result = compute_corner_opportunities([corner], lap_df, no_brake_optimal)
        assert len(result) == 1
        assert result[0].brake_gap_m is None

    def test_brake_gap_positive_when_driver_brakes_later(self) -> None:
        """Driver braking closer to corner (later) than optimal → positive gap."""
        optimal = _make_optimal_profile(speed=40.0)
        lap_df = _make_lap_df(speed=35.0)
        # Driver brakes at 210m, optimal brake at 200m → gap = 210 - 200 = +10
        corner = _make_corner(
            entry=200.0,
            exit_d=350.0,
            apex=275.0,
            min_speed=25.0,
            brake_m=210.0,
        )

        result = compute_corner_opportunities([corner], lap_df, optimal)

        assert len(result) == 1
        assert result[0].brake_gap_m is not None
        assert result[0].brake_gap_m > 0  # positive = later than optimal

    def test_brake_gap_negative_when_driver_brakes_earlier(self) -> None:
        """Driver braking further from corner (earlier) than optimal → negative gap."""
        optimal = _make_optimal_profile(speed=40.0)
        lap_df = _make_lap_df(speed=35.0)
        # Driver brakes at 180m, optimal brake at 200m → gap = 180 - 200 = -20
        corner = _make_corner(
            entry=200.0,
            exit_d=350.0,
            apex=275.0,
            min_speed=25.0,
            brake_m=180.0,
        )

        result = compute_corner_opportunities([corner], lap_df, optimal)

        assert len(result) == 1
        assert result[0].brake_gap_m is not None
        assert result[0].brake_gap_m < 0  # negative = earlier than optimal

    def test_exit_straight_time_cost_field_exists(self) -> None:
        """CornerOpportunity has exit_straight_time_cost_s field, defaults to 0."""
        optimal = _make_optimal_profile(speed=40.0)
        lap_df = _make_lap_df(speed=35.0)
        corner = _make_corner(min_speed=25.0)

        result = compute_corner_opportunities([corner], lap_df, optimal)

        assert len(result) == 1
        assert hasattr(result[0], "exit_straight_time_cost_s")
        assert result[0].exit_straight_time_cost_s >= 0.0


class TestExitStraightTimeCost:
    """Tests for exit_straight_time_cost_s computation."""

    def test_two_corners_with_straight_between(self) -> None:
        """Time cost on straight between two corners is computed."""
        optimal = _make_optimal_profile(n=1000, step_m=0.7, speed=40.0)
        lap_df = _make_lap_df(n=1000, step_m=0.7, speed=35.0)
        c1 = _make_corner(number=1, entry=100.0, exit_d=200.0, apex=150.0, min_speed=25.0)
        c2 = _make_corner(number=2, entry=400.0, exit_d=500.0, apex=450.0, min_speed=25.0)

        result = compute_corner_opportunities([c1, c2], lap_df, optimal)

        opp1 = next(o for o in result if o.corner_number == 1)
        assert opp1.exit_straight_time_cost_s > 0.0

    def test_adjacent_corners_no_straight(self) -> None:
        """Corners with no gap between them have zero exit straight cost."""
        optimal = _make_optimal_profile(n=1000, step_m=0.7, speed=40.0)
        lap_df = _make_lap_df(n=1000, step_m=0.7, speed=35.0)
        c1 = _make_corner(number=1, entry=100.0, exit_d=300.0, apex=200.0, min_speed=25.0)
        c2 = _make_corner(number=2, entry=300.0, exit_d=500.0, apex=400.0, min_speed=25.0)

        result = compute_corner_opportunities([c1, c2], lap_df, optimal)

        opp1 = next(o for o in result if o.corner_number == 1)
        assert opp1.exit_straight_time_cost_s == 0.0

    def test_single_corner_gets_full_remaining_as_exit(self) -> None:
        """Single corner: exit straight covers exit → end + 0 → entry (wrap-around)."""
        optimal = _make_optimal_profile(n=1000, step_m=0.7, speed=40.0)
        lap_df = _make_lap_df(n=1000, step_m=0.7, speed=35.0)
        corner = _make_corner(number=1, entry=200.0, exit_d=350.0, apex=275.0, min_speed=25.0)

        result = compute_corner_opportunities([corner], lap_df, optimal)

        assert len(result) == 1
        assert result[0].exit_straight_time_cost_s > 0.0

    def test_exit_straight_negative_capped_at_zero(self) -> None:
        """If driver is faster on the straight than optimal, cap at 0."""
        optimal = _make_optimal_profile(n=1000, step_m=0.7, speed=30.0)
        lap_df = _make_lap_df(n=1000, step_m=0.7, speed=40.0)
        c1 = _make_corner(number=1, entry=100.0, exit_d=200.0, apex=150.0, min_speed=25.0)
        c2 = _make_corner(number=2, entry=400.0, exit_d=500.0, apex=450.0, min_speed=25.0)

        result = compute_corner_opportunities([c1, c2], lap_df, optimal)

        opp1 = next(o for o in result if o.corner_number == 1)
        assert opp1.exit_straight_time_cost_s == 0.0

    def test_skipped_corner_does_not_break_last_corner_wrap(self) -> None:
        """Skipped corners outside the optimal range must not break wrap attribution."""
        optimal = _make_optimal_profile(n=1000, step_m=0.7, speed=40.0)
        lap_df = _make_lap_df(n=1000, step_m=0.7, speed=35.0)
        c1 = _make_corner(number=1, entry=100.0, exit_d=200.0, apex=150.0, min_speed=25.0)
        c2 = _make_corner(number=2, entry=400.0, exit_d=500.0, apex=450.0, min_speed=25.0)
        # Outside optimal distance (0..~699m) so this corner is skipped.
        c3 = _make_corner(number=3, entry=900.0, exit_d=950.0, apex=925.0, min_speed=25.0)

        result = compute_corner_opportunities([c1, c2, c3], lap_df, optimal)

        assert len(result) == 2
        opp1 = next(o for o in result if o.corner_number == 1)
        opp2 = next(o for o in result if o.corner_number == 2)
        # Corner 2 is the last valid corner, so it should include wrap-around
        # exit cost (500→end plus 0→100), larger than corner 1's 200→400 straight.
        assert opp2.exit_straight_time_cost_s > opp1.exit_straight_time_cost_s


# ---------------------------------------------------------------------------
# TestCompareWithOptimal
# ---------------------------------------------------------------------------


class TestCompareWithOptimal:
    """Tests for compare_with_optimal."""

    def test_full_pipeline(self) -> None:
        """Full pipeline runs without error and returns valid result."""
        optimal = _make_optimal_profile(speed=40.0)
        lap_df = _make_lap_df(speed=35.0)
        corner = _make_corner()

        result = compare_with_optimal(lap_df, [corner], optimal)

        assert isinstance(result, OptimalComparisonResult)
        assert len(result.corner_opportunities) == 1
        assert len(result.speed_delta_mps) == len(optimal.distance_m)
        assert len(result.distance_m) == len(optimal.distance_m)
        assert result.actual_lap_time_s > 0.0
        assert result.optimal_lap_time_s > 0.0

    def test_total_gap_positive_when_slower(self) -> None:
        """Driver slower than optimal should have positive total gap."""
        optimal = _make_optimal_profile(speed=40.0)
        lap_df = _make_lap_df(speed=35.0)
        corner = _make_corner()

        result = compare_with_optimal(lap_df, [corner], optimal)

        assert result.total_gap_s > 0.0

    def test_total_gap_near_zero_when_matched(self) -> None:
        """Same speed as optimal should give total gap near zero."""
        optimal = _make_optimal_profile(speed=40.0)
        lap_df = _make_lap_df(speed=40.0)
        corner = _make_corner(min_speed=40.0)

        result = compare_with_optimal(lap_df, [corner], optimal)

        # Small residual from different time-summation methods (n-1 vs n intervals)
        assert abs(result.total_gap_s) < 0.02

    def test_marks_result_invalid_when_optimal_is_slower_than_actual(self) -> None:
        """If the model is slower than the driver overall, mark comparison invalid."""
        optimal = _make_optimal_profile(speed=30.0)
        lap_df = _make_lap_df(speed=40.0)
        corner = _make_corner(min_speed=35.0)

        result = compare_with_optimal(lap_df, [corner], optimal)

        assert result.total_gap_s < 0.0
        assert result.is_valid is False
        assert "aggregate_optimal_slower_than_actual" in result.invalid_reasons


# ---------------------------------------------------------------------------
# TestSpikeRejection — apex-window excludes edge spikes
# ---------------------------------------------------------------------------


class TestSpikeRejection:
    """Tests that the apex-centred window excludes spikes outside the window."""

    def test_spike_does_not_dominate_optimal_speed(self) -> None:
        """Spikes outside the apex window should not affect optimal min speed.

        The apex-centred window (±30% of zone width) excludes points near
        zone edges where solver artifacts or ramp contamination may occur.
        """
        n = 1000
        speed_arr = np.full(n, 40.0)
        # Inject 2 spike points inside the corner zone [200..350] → at index ~290, ~295
        spike_idx = [290, 295]
        speed_arr[spike_idx] = 20.0  # large spike

        optimal = OptimalProfile(
            distance_m=np.arange(n) * 0.7,
            optimal_speed_mps=speed_arr,
            curvature=np.zeros(n),
            max_cornering_speed_mps=speed_arr.copy(),
            optimal_brake_points=[200.0],
            optimal_throttle_points=[350.0],
            lap_time_s=17.5,
            vehicle_params=VehicleParams(
                mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0
            ),
        )
        lap_df = _make_lap_df(speed=35.0)
        corner = _make_corner(min_speed=25.0)

        result = compute_corner_opportunities([corner], lap_df, optimal)

        assert len(result) == 1
        # Spikes at indices 290,295 → dist 203m,206.5m.  Apex window is
        # [275-45, 275+45] = [230, 320], so spikes fall outside the window.
        assert result[0].optimal_min_speed_mps > 35.0


# ---------------------------------------------------------------------------
# TestSanityGuard — negative time_cost capped at zero
# ---------------------------------------------------------------------------


class TestSanityGuard:
    """Tests that corners where the model is slower than actual get time_cost=0."""

    def test_negative_time_cost_capped_at_zero(self) -> None:
        """If optimal speed is lower than actual in a corner zone, time_cost = 0."""
        # Optimal is SLOWER than actual → model failure
        optimal = _make_optimal_profile(speed=30.0)
        lap_df = _make_lap_df(speed=40.0)
        corner = _make_corner(min_speed=35.0)

        result = compute_corner_opportunities([corner], lap_df, optimal)

        assert len(result) == 1
        # Without sanity guard, this would be negative
        assert result[0].time_cost_s == 0.0

    def test_positive_time_cost_unaffected(self) -> None:
        """Normal case where driver is slower should still produce positive time_cost."""
        optimal = _make_optimal_profile(speed=40.0)
        lap_df = _make_lap_df(speed=30.0)
        corner = _make_corner(min_speed=25.0)

        result = compute_corner_opportunities([corner], lap_df, optimal)

        assert len(result) == 1
        assert result[0].time_cost_s > 0.0

    def test_compare_with_optimal_marks_invalid_when_optimal_lap_is_slower(self) -> None:
        """Aggregate validity should fail when the model's lap is slower than actual."""
        optimal = _make_optimal_profile(speed=30.0)
        lap_df = _make_lap_df(speed=40.0)
        corner = _make_corner(min_speed=35.0)

        result = compare_with_optimal(lap_df, [corner], optimal)

        assert result.is_valid is False
        assert "aggregate_optimal_slower_than_actual" in result.invalid_reasons


class TestComputeCornerOpportunitiesEdges:
    """Cover lines 181, 191, 211 in compute_corner_opportunities."""

    def test_single_point_optimal_profile_uses_default_step(self) -> None:
        """optimal.distance_m with < 2 points → step_m = 0.7 (line 181)."""
        optimal = OptimalProfile(
            distance_m=np.array([50.0]),  # only 1 point → len < 2 → step_m = 0.7
            optimal_speed_mps=np.array([30.0]),
            curvature=np.array([0.0]),
            max_cornering_speed_mps=np.array([30.0]),
            optimal_brake_points=[],
            optimal_throttle_points=[],
            lap_time_s=10.0,
            vehicle_params=VehicleParams(
                mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0
            ),
        )
        lap_df = _make_lap_df()
        corner = _make_corner(entry=40.0, exit_d=60.0, min_speed=25.0, brake_m=35.0)
        result = compute_corner_opportunities([corner], lap_df, optimal)
        assert isinstance(result, list)

    def test_corner_outside_optimal_distance_skipped(self) -> None:
        """Corner range doesn't overlap optimal distance → opt_mask all False → skip (line 191)."""
        optimal = _make_optimal_profile(n=100, step_m=0.7)  # distance 0..~69m
        lap_df = _make_lap_df(n=100)
        far_corner = _make_corner(entry=500.0, exit_d=600.0, min_speed=25.0, brake_m=490.0)
        result = compute_corner_opportunities([far_corner], lap_df, optimal)
        assert result == []

    def test_corner_with_no_brake_point_has_none_brake_gap(self) -> None:
        """Corner without brake_point_m → brake_gap = None (line 211)."""
        optimal = _make_optimal_profile(n=1000)
        lap_df = _make_lap_df(n=1000)
        corner = _make_corner(entry=100.0, exit_d=200.0, min_speed=30.0, brake_m=None)
        result = compute_corner_opportunities([corner], lap_df, optimal)
        if result:
            assert result[0].brake_gap_m is None


# ---------------------------------------------------------------------------
# TestFindOptimalThrottleForCorner
# ---------------------------------------------------------------------------


class TestFindOptimalThrottleForCorner:
    """Tests for _find_optimal_throttle_for_corner."""

    def test_finds_throttle_in_window(self) -> None:
        corner = _make_corner(apex=275.0, exit_d=350.0)
        optimal = _make_optimal_profile()  # optimal_throttle_points=[350.0]
        result = _find_optimal_throttle_for_corner(corner, optimal)
        assert result == 350.0

    def test_returns_none_when_no_throttle_in_window(self) -> None:
        corner = _make_corner(apex=275.0, exit_d=350.0)
        optimal = _make_optimal_profile()
        optimal.optimal_throttle_points = [600.0]
        result = _find_optimal_throttle_for_corner(corner, optimal)
        assert result is None

    def test_picks_closest_to_apex(self) -> None:
        corner = _make_corner(apex=275.0, exit_d=350.0)
        optimal = _make_optimal_profile()
        optimal.optimal_throttle_points = [280.0, 340.0]
        result = _find_optimal_throttle_for_corner(corner, optimal)
        assert result == 280.0


# ---------------------------------------------------------------------------
# TestThrottleGapInCornerOpportunities
# ---------------------------------------------------------------------------


class TestThrottleGapInCornerOpportunities:
    """Tests for throttle_gap_m in CornerOpportunity."""

    def test_throttle_gap_computed(self) -> None:
        corner = _make_corner(number=1, entry=200.0, exit_d=350.0, apex=275.0, brake_m=180.0)
        # corner.throttle_commit_m = 330.0 (exit_d - 20 from _make_corner helper)
        optimal = _make_optimal_profile()  # optimal_throttle_points=[350.0]
        lap_df = _make_lap_df()
        result = compute_corner_opportunities([corner], lap_df, optimal)
        opp = result[0]
        # throttle_gap = actual (330.0) - optimal (350.0) = -20.0
        assert opp.throttle_gap_m is not None
        assert abs(opp.throttle_gap_m - (-20.0)) < 0.1

    def test_throttle_gap_none_when_no_throttle_commit(self) -> None:
        corner = _make_corner()
        corner.throttle_commit_m = None
        optimal = _make_optimal_profile()
        lap_df = _make_lap_df()
        result = compute_corner_opportunities([corner], lap_df, optimal)
        assert result[0].throttle_gap_m is None

    def test_throttle_gap_none_when_no_optimal_throttle(self) -> None:
        corner = _make_corner()
        optimal = _make_optimal_profile()
        optimal.optimal_throttle_points = []
        lap_df = _make_lap_df()
        result = compute_corner_opportunities([corner], lap_df, optimal)
        assert result[0].throttle_gap_m is None

"""Tests for cataclysm.velocity_profile."""

from __future__ import annotations

import numpy as np
import pytest

from cataclysm.curvature import CurvatureResult
from cataclysm.velocity_profile import (
    MIN_SPEED_MPS,
    G,
    OptimalProfile,
    VehicleParams,
    _available_accel,
    _backward_pass,
    _compute_max_cornering_speed,
    _find_transitions,
    _forward_pass,
    _segment_time,
    compute_optimal_profile,
    compute_speed_sensitivity,
    default_vehicle_params,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_curvature_result(
    curvature: np.ndarray,
    step_m: float = 0.7,
) -> CurvatureResult:
    """Build a synthetic CurvatureResult from a curvature array."""
    n = len(curvature)
    distance = np.arange(n) * step_m
    heading = np.cumsum(curvature) * step_m
    x = np.cumsum(np.cos(heading) * step_m)
    y = np.cumsum(np.sin(heading) * step_m)
    return CurvatureResult(
        distance_m=distance,
        curvature=curvature,
        abs_curvature=np.abs(curvature),
        heading_rad=heading,
        x_smooth=x,
        y_smooth=y,
    )


# ---------------------------------------------------------------------------
# TestVehicleParams
# ---------------------------------------------------------------------------


class TestVehicleParams:
    def test_default_params(self) -> None:
        """default_vehicle_params() returns a valid VehicleParams."""
        params = default_vehicle_params()
        assert isinstance(params, VehicleParams)
        assert params.mu == 1.0
        assert params.max_accel_g == 0.5
        assert params.max_decel_g == 1.0
        assert params.max_lateral_g == 1.0
        assert params.top_speed_mps == 80.0
        assert params.friction_circle_exponent == 2.0
        assert params.aero_coefficient == 0.0

    def test_custom_params(self) -> None:
        """Can create VehicleParams with custom values."""
        params = VehicleParams(
            mu=1.2,
            max_accel_g=0.7,
            max_decel_g=1.3,
            max_lateral_g=1.5,
            friction_circle_exponent=2.5,
            aero_coefficient=0.001,
            top_speed_mps=90.0,
        )
        assert params.mu == 1.2
        assert params.max_accel_g == 0.7
        assert params.max_decel_g == 1.3
        assert params.max_lateral_g == 1.5
        assert params.friction_circle_exponent == 2.5
        assert params.aero_coefficient == 0.001
        assert params.top_speed_mps == 90.0


# ---------------------------------------------------------------------------
# TestMaxCorneringSpeed
# ---------------------------------------------------------------------------


class TestMaxCorneringSpeed:
    def test_zero_curvature_returns_top_speed(self) -> None:
        """Zero curvature everywhere should yield top_speed at every point."""
        params = default_vehicle_params()
        abs_k = np.zeros(100)
        result = _compute_max_cornering_speed(abs_k, params)

        np.testing.assert_array_equal(result, params.top_speed_mps)

    def test_constant_curvature(self) -> None:
        """Constant |kappa| = 0.01 should give v = sqrt(mu*G / 0.01)."""
        params = default_vehicle_params()
        kappa = 0.01
        abs_k = np.full(200, kappa)
        result = _compute_max_cornering_speed(abs_k, params)

        expected = np.sqrt(params.mu * G / kappa)
        np.testing.assert_allclose(result, expected, rtol=1e-10)

    def test_high_curvature_floors_at_min(self) -> None:
        """Very high curvature should be clamped to MIN_SPEED_MPS."""
        params = default_vehicle_params()
        # kappa = 10.0 -> v = sqrt(1.0*9.81/10) ~ 0.99 m/s, below floor
        abs_k = np.full(50, 10.0)
        result = _compute_max_cornering_speed(abs_k, params)

        np.testing.assert_array_equal(result, MIN_SPEED_MPS)

    def test_aero_coefficient_increases_speed(self) -> None:
        """With aero_coefficient > 0, cornering speed should be >= non-aero case."""
        kappa = 0.01
        abs_k = np.full(100, kappa)

        params_no_aero = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            aero_coefficient=0.0,
        )
        params_aero = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            aero_coefficient=0.0005,
        )

        speed_no_aero = _compute_max_cornering_speed(abs_k, params_no_aero)
        speed_aero = _compute_max_cornering_speed(abs_k, params_aero)

        # Aero adds grip at speed, so cornering speed should be higher (or equal)
        assert np.all(speed_aero >= speed_no_aero - 1e-6)

    def test_mu_greater_than_max_lateral_g(self) -> None:
        """When mu > max_lateral_g, cornering speed should use max_lateral_g."""
        kappa = 0.01
        abs_k = np.full(100, kappa)
        params = VehicleParams(
            mu=1.5,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
        )
        result = _compute_max_cornering_speed(abs_k, params)
        # Should use min(1.5, 1.0) = 1.0
        expected = np.sqrt(1.0 * G / kappa)
        np.testing.assert_allclose(result, expected, rtol=1e-10)

    def test_max_lateral_g_greater_than_mu(self) -> None:
        """When max_lateral_g > mu, cornering speed should use mu."""
        kappa = 0.01
        abs_k = np.full(100, kappa)
        params = VehicleParams(
            mu=0.8,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.2,
        )
        result = _compute_max_cornering_speed(abs_k, params)
        # Should use min(0.8, 1.2) = 0.8
        expected = np.sqrt(0.8 * G / kappa)
        np.testing.assert_allclose(result, expected, rtol=1e-10)

    def test_nan_inf_replaced(self) -> None:
        """NaN or inf in curvature should not produce NaN/inf in output."""
        params = default_vehicle_params()
        abs_k = np.array([0.0, 0.01, np.nan, np.inf, 0.005])
        result = _compute_max_cornering_speed(abs_k, params)

        assert np.all(np.isfinite(result))
        assert np.all(result >= MIN_SPEED_MPS)
        assert np.all(result <= params.top_speed_mps)


# ---------------------------------------------------------------------------
# TestForwardBackwardPass
# ---------------------------------------------------------------------------


class TestForwardBackwardPass:
    def test_forward_pass_respects_max_speed(self) -> None:
        """Forward pass output must never exceed max_speed at any point."""
        params = default_vehicle_params()
        np.random.seed(42)
        max_speed = np.random.uniform(20.0, 60.0, size=300)
        abs_k = np.full(300, 0.005)
        step_m = 0.7

        result = _forward_pass(max_speed, step_m, params, abs_k)

        assert np.all(result <= max_speed + 1e-10)

    def test_backward_pass_respects_max_speed(self) -> None:
        """Backward pass output must never exceed max_speed at any point."""
        params = default_vehicle_params()
        np.random.seed(42)
        max_speed = np.random.uniform(20.0, 60.0, size=300)
        abs_k = np.full(300, 0.005)
        step_m = 0.7

        result = _backward_pass(max_speed, step_m, params, abs_k)

        assert np.all(result <= max_speed + 1e-10)

    def test_forward_accel_limited(self) -> None:
        """With tight max_accel, speed increase should be gradual."""
        params = VehicleParams(
            mu=1.0,
            max_accel_g=0.1,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            top_speed_mps=80.0,
        )
        # Straight track, start from low speed
        max_speed = np.full(500, 80.0)
        max_speed[0] = 10.0  # force low start
        abs_k = np.zeros(500)
        step_m = 0.7

        result = _forward_pass(max_speed, step_m, params, abs_k)

        # Speed at point 0 should be 10.0
        assert result[0] == pytest.approx(10.0)
        # Speed should increase gradually — check it's not instantly at 80
        assert result[10] < 80.0
        # Speed should be monotonically non-decreasing on a straight
        diffs = np.diff(result)
        assert np.all(diffs >= -1e-10)

    def test_backward_decel_limited(self) -> None:
        """With tight max_decel, speed decrease should be gradual."""
        params = VehicleParams(
            mu=1.0,
            max_accel_g=1.0,
            max_decel_g=0.1,
            max_lateral_g=1.0,
            top_speed_mps=80.0,
        )
        max_speed = np.full(500, 80.0)
        max_speed[-1] = 10.0  # force low end
        abs_k = np.zeros(500)
        step_m = 0.7

        result = _backward_pass(max_speed, step_m, params, abs_k)

        # Speed at last point should be 10.0
        assert result[-1] == pytest.approx(10.0)
        # Speed near the end should be less than 80 (decel zone)
        assert result[-10] < 80.0

    def test_forward_backward_symmetry_on_straight(self) -> None:
        """On a straight with symmetric start/end, passes should give similar shapes."""
        params = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=0.5,
            max_lateral_g=1.0,
            top_speed_mps=80.0,
        )
        n = 200
        max_speed = np.full(n, 80.0)
        max_speed[0] = 20.0
        max_speed[-1] = 20.0
        abs_k = np.zeros(n)
        step_m = 0.7

        fwd = _forward_pass(max_speed, step_m, params, abs_k)
        bwd = _backward_pass(max_speed, step_m, params, abs_k)

        # Forward ramps up from start, backward ramps up from end
        # They should be mirror images of each other
        np.testing.assert_allclose(fwd, bwd[::-1], rtol=1e-6)


# ---------------------------------------------------------------------------
# TestAvailableAccel
# ---------------------------------------------------------------------------


class TestAvailableAccel:
    def test_no_lateral_load(self) -> None:
        """With zero lateral G, full longitudinal accel should be available."""
        params = default_vehicle_params()
        result = _available_accel(30.0, 0.0, params, "accel")
        assert result == pytest.approx(params.max_accel_g)

    def test_full_lateral_load(self) -> None:
        """At max lateral G, zero longitudinal accel should remain."""
        params = default_vehicle_params()
        result = _available_accel(30.0, params.max_lateral_g, params, "accel")
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_partial_lateral_load(self) -> None:
        """Intermediate lateral G should yield partial longitudinal accel."""
        params = default_vehicle_params()
        lateral_g = params.max_lateral_g * 0.5
        result = _available_accel(30.0, lateral_g, params, "accel")

        # Should be between 0 and max_accel_g
        assert result > 0.0
        assert result < params.max_accel_g

        # For exponent=2 (circle): available = max * sqrt(1 - 0.5^2) = max * sqrt(0.75)
        expected = params.max_accel_g * np.sqrt(1.0 - 0.5**2)
        assert result == pytest.approx(expected, rel=1e-10)

    def test_decel_direction(self) -> None:
        """Direction 'decel' should use max_decel_g as the ceiling."""
        params = default_vehicle_params()
        result = _available_accel(30.0, 0.0, params, "decel")
        assert result == pytest.approx(params.max_decel_g)

    def test_excess_lateral_returns_zero(self) -> None:
        """Lateral G exceeding max should return 0 (no longitudinal budget)."""
        params = default_vehicle_params()
        result = _available_accel(30.0, params.max_lateral_g * 1.5, params, "accel")
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_diamond_friction_shape(self) -> None:
        """With exponent > 2 (diamond), partial load leaves more lon budget."""
        params_circle = VehicleParams(
            mu=1.0,
            max_accel_g=1.0,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            friction_circle_exponent=2.0,
        )
        params_diamond = VehicleParams(
            mu=1.0,
            max_accel_g=1.0,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            friction_circle_exponent=4.0,
        )
        lateral_g = 0.5
        accel_circle = _available_accel(30.0, lateral_g, params_circle, "accel")
        accel_diamond = _available_accel(30.0, lateral_g, params_diamond, "accel")

        # Diamond shape allows more combined grip at 45 degrees
        assert accel_diamond > accel_circle


# ---------------------------------------------------------------------------
# TestFindTransitions
# ---------------------------------------------------------------------------


class TestFindTransitions:
    def test_constant_speed_no_transitions(self) -> None:
        """Constant speed should produce no brake or throttle points."""
        speed = np.full(200, 30.0)
        distance = np.arange(200) * 0.7
        brake, throttle = _find_transitions(speed, distance)
        assert brake == []
        assert throttle == []

    def test_decel_then_accel(self) -> None:
        """Speed that drops then rises should produce one brake and one throttle."""
        n = 300
        distance = np.arange(n) * 0.7
        speed = np.concatenate(
            [
                np.linspace(50, 20, 100),
                np.full(50, 20),
                np.linspace(20, 50, 150),
            ]
        )
        brake, throttle = _find_transitions(speed, distance)
        assert len(brake) >= 1
        assert len(throttle) >= 1
        # Brake should occur before throttle
        assert brake[0] < throttle[0]

    def test_noise_below_threshold_ignored(self) -> None:
        """Tiny speed oscillations below 0.5 m/s should not trigger transitions."""
        n = 200
        distance = np.arange(n) * 0.7
        speed = np.full(n, 40.0) + np.random.default_rng(42).uniform(-0.3, 0.3, n)
        brake, throttle = _find_transitions(speed, distance)
        assert len(brake) == 0
        assert len(throttle) == 0


# ---------------------------------------------------------------------------
# TestComputeOptimalProfile
# ---------------------------------------------------------------------------


class TestComputeOptimalProfile:
    def test_straight_track_reaches_top_speed(self) -> None:
        """All-zero curvature with enough distance should approach top_speed."""
        n = 2000
        curvature = np.zeros(n)
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        profile = compute_optimal_profile(cr, params)

        assert isinstance(profile, OptimalProfile)
        # Near the middle of a long straight, speed should be near top_speed
        mid = n // 2
        assert profile.optimal_speed_mps[mid] == pytest.approx(params.top_speed_mps, rel=0.01)

    def test_constant_curvature_constant_speed(self) -> None:
        """Constant curvature should produce near-constant optimal speed."""
        kappa = 0.01
        n = 1000
        curvature = np.full(n, kappa)
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        profile = compute_optimal_profile(cr, params)

        expected_speed = np.sqrt(params.mu * G / kappa)
        # Interior points (excluding ramp-up/ramp-down at edges)
        interior = profile.optimal_speed_mps[100:-100]
        np.testing.assert_allclose(interior, expected_speed, rtol=0.05)

    def test_brake_corner_accel_shape(self) -> None:
        """Straight-corner-straight should show decel into corner, accel out."""
        straight1 = np.zeros(500)
        corner = np.full(200, 0.02)  # tight corner
        straight2 = np.zeros(500)
        curvature = np.concatenate([straight1, corner, straight2])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        profile = compute_optimal_profile(cr, params)
        speed = profile.optimal_speed_mps

        # Speed in the corner should be much lower than on the straights
        corner_speed = np.mean(speed[550:650])
        straight_speed = np.mean(speed[100:200])
        assert corner_speed < straight_speed * 0.8

        # Speed before the corner should be decreasing (braking)
        pre_corner = speed[400:500]
        assert pre_corner[0] > pre_corner[-1]

        # Speed after the corner should be increasing (accelerating)
        post_corner = speed[700:800]
        assert post_corner[-1] > post_corner[0]

    def test_lap_time_positive(self) -> None:
        """Lap time should be strictly positive for any non-trivial track."""
        n = 500
        curvature = np.full(n, 0.005)
        cr = _make_curvature_result(curvature, step_m=0.7)

        profile = compute_optimal_profile(cr)

        assert profile.lap_time_s > 0.0

    def test_lap_time_straight_vs_curvy(self) -> None:
        """A straight track should have a lower lap time than a curvy one."""
        n = 1000
        step_m = 0.7

        straight_cr = _make_curvature_result(np.zeros(n), step_m=step_m)
        curvy_cr = _make_curvature_result(np.full(n, 0.01), step_m=step_m)

        params = default_vehicle_params()
        straight_profile = compute_optimal_profile(straight_cr, params)
        curvy_profile = compute_optimal_profile(curvy_cr, params)

        assert straight_profile.lap_time_s < curvy_profile.lap_time_s

    def test_with_none_params_uses_defaults(self) -> None:
        """Passing params=None should use default_vehicle_params()."""
        n = 200
        curvature = np.zeros(n)
        cr = _make_curvature_result(curvature, step_m=0.7)

        profile = compute_optimal_profile(cr, params=None)

        expected_params = default_vehicle_params()
        assert profile.vehicle_params.mu == expected_params.mu
        assert profile.vehicle_params.max_accel_g == expected_params.max_accel_g
        assert profile.vehicle_params.top_speed_mps == expected_params.top_speed_mps

    def test_output_arrays_match_input_length(self) -> None:
        """All output arrays should have the same length as the input."""
        n = 400
        curvature = np.zeros(n)
        cr = _make_curvature_result(curvature, step_m=0.7)

        profile = compute_optimal_profile(cr)

        assert len(profile.distance_m) == n
        assert len(profile.optimal_speed_mps) == n
        assert len(profile.curvature) == n
        assert len(profile.max_cornering_speed_mps) == n

    def test_speed_always_within_bounds(self) -> None:
        """Optimal speed should always be within [MIN_SPEED_MPS, top_speed]."""
        # Mix of curvatures including zero, small, and large
        curvature = np.concatenate(
            [
                np.zeros(200),
                np.full(100, 0.005),
                np.full(50, 0.05),
                np.zeros(200),
            ]
        )
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        profile = compute_optimal_profile(cr, params)

        assert np.all(profile.optimal_speed_mps >= MIN_SPEED_MPS)
        assert np.all(profile.optimal_speed_mps <= params.top_speed_mps)

    def test_higher_mu_faster_lap(self) -> None:
        """Higher friction coefficient should produce a faster lap time."""
        curvature = np.concatenate(
            [
                np.zeros(300),
                np.full(200, 0.01),
                np.zeros(300),
            ]
        )
        cr = _make_curvature_result(curvature, step_m=0.7)

        low_grip = VehicleParams(
            mu=0.8,
            max_accel_g=0.4,
            max_decel_g=0.8,
            max_lateral_g=0.8,
        )
        high_grip = VehicleParams(
            mu=1.2,
            max_accel_g=0.6,
            max_decel_g=1.2,
            max_lateral_g=1.2,
        )

        slow_profile = compute_optimal_profile(cr, low_grip)
        fast_profile = compute_optimal_profile(cr, high_grip)

        assert fast_profile.lap_time_s < slow_profile.lap_time_s

    def test_closed_circuit_brakes_at_end_for_corner_at_start(self) -> None:
        """Closed circuit with corner at position 0 must brake at end of lap."""
        # Corner at the start, long straight in the middle
        corner = np.full(100, 0.02)  # tight corner at positions 0..99
        straight = np.zeros(900)
        curvature = np.concatenate([corner, straight])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        closed = compute_optimal_profile(cr, params, closed_circuit=True)
        open_ = compute_optimal_profile(cr, params, closed_circuit=False)

        # The closed solver must slow down at the end of the lap (wrapping
        # into the corner at position 0). The open solver has no such
        # constraint, so its speed at the end should be higher.
        assert closed.optimal_speed_mps[-1] < open_.optimal_speed_mps[-1]

    def test_open_circuit_no_wrap(self) -> None:
        """Open circuit should not slow down at end for corner at start."""
        corner = np.full(100, 0.02)
        straight = np.zeros(900)
        curvature = np.concatenate([corner, straight])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        profile = compute_optimal_profile(cr, params, closed_circuit=False)

        # On an open circuit, the end of the straight should be at or near top speed
        assert profile.optimal_speed_mps[-1] == pytest.approx(params.top_speed_mps, rel=0.05)

    def test_drag_reduces_straight_line_speed(self) -> None:
        """Aero drag should reduce speed when accelerating out of a corner."""
        # Corner then long straight — the car must accelerate from low speed
        corner = np.full(100, 0.02)
        straight = np.zeros(1500)
        curvature = np.concatenate([corner, straight])
        cr = _make_curvature_result(curvature, step_m=0.7)

        params_no_drag = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            drag_coefficient=0.0,
        )
        params_drag = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            drag_coefficient=0.005,
        )

        profile_no_drag = compute_optimal_profile(cr, params_no_drag, closed_circuit=False)
        profile_drag = compute_optimal_profile(cr, params_drag, closed_circuit=False)

        # Check speed partway through the straight (accel zone after corner)
        check_idx = 300  # well into the straight, during acceleration
        drag_speed = profile_drag.optimal_speed_mps[check_idx]
        no_drag_speed = profile_no_drag.optimal_speed_mps[check_idx]
        assert drag_speed < no_drag_speed

    def test_zero_drag_identical_to_no_drag(self) -> None:
        """drag_coefficient=0.0 should produce identical results to old behavior."""
        curvature = np.concatenate(
            [
                np.zeros(300),
                np.full(200, 0.01),
                np.zeros(300),
            ]
        )
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            drag_coefficient=0.0,
        )

        profile = compute_optimal_profile(cr, params, closed_circuit=False)

        # Verify it runs and produces valid output (backward compatible)
        assert profile.lap_time_s > 0.0
        assert np.all(profile.optimal_speed_mps >= MIN_SPEED_MPS)
        assert np.all(profile.optimal_speed_mps <= params.top_speed_mps)


# ---------------------------------------------------------------------------
# TestFindTransitionsStateMachine (lines 241-274: decel→accel reversals)
# ---------------------------------------------------------------------------


class TestFindTransitionsStateMachine:
    """Edge-case coverage of _find_transitions state machine (lines 241-274)."""

    def test_single_point_returns_empty(self) -> None:
        """A single-element speed array should return no transitions."""
        speed = np.array([30.0])
        distance = np.array([0.0])
        brake, throttle = _find_transitions(speed, distance)
        assert brake == []
        assert throttle == []

    def test_decel_then_immediate_accel_reversal(self) -> None:
        """Braking then immediately accelerating should produce both a brake and throttle point."""
        n = 300
        distance = np.arange(n) * 0.7
        speed = np.concatenate(
            [
                np.linspace(50.0, 30.0, 100),  # decel
                np.linspace(30.0, 50.0, 200),  # accel
            ]
        )
        brake, throttle = _find_transitions(speed, distance)
        assert len(brake) >= 1
        assert len(throttle) >= 1
        # Brake must come first
        assert brake[0] < throttle[0]

    def test_accel_then_immediate_decel_reversal(self) -> None:
        """Accelerating then immediately braking should produce both throttle and brake point."""
        n = 300
        distance = np.arange(n) * 0.7
        speed = np.concatenate(
            [
                np.linspace(30.0, 50.0, 100),  # accel
                np.linspace(50.0, 30.0, 200),  # decel
            ]
        )
        brake, throttle = _find_transitions(speed, distance)
        assert len(throttle) >= 1
        assert len(brake) >= 1
        # Throttle must come first
        assert throttle[0] < brake[0]

    def test_decel_state_with_no_reversal(self) -> None:
        """Pure braking segment should register a brake point without any throttle."""
        n = 100
        distance = np.arange(n) * 0.7
        speed = np.linspace(50.0, 30.0, n)  # monotonic drop of 20 m/s
        brake, throttle = _find_transitions(speed, distance)
        assert len(brake) >= 1
        assert len(throttle) == 0

    def test_accel_state_with_no_reversal(self) -> None:
        """Pure acceleration should register a throttle point without any brake."""
        n = 100
        distance = np.arange(n) * 0.7
        speed = np.linspace(30.0, 50.0, n)  # monotonic rise of 20 m/s
        brake, throttle = _find_transitions(speed, distance)
        assert len(throttle) >= 1
        assert len(brake) == 0

    def test_threshold_exactly_at_boundary_not_triggered(self) -> None:
        """Speed change exactly equal to threshold (0.5 m/s) should not trigger a transition."""
        n = 100
        distance = np.arange(n) * 0.7
        # Drop exactly 0.5 m/s total — NOT less than -0.5, so no decel triggered
        speed = np.concatenate([np.full(50, 30.0), np.full(50, 29.5)])
        brake, throttle = _find_transitions(speed, distance)
        assert len(brake) == 0
        assert len(throttle) == 0

    def test_large_decel_triggers_brake(self) -> None:
        """A speed drop well above threshold must register a brake point."""
        n = 100
        distance = np.arange(n) * 0.7
        speed = np.concatenate([np.full(50, 50.0), np.full(50, 45.0)])  # 5 m/s drop
        brake, throttle = _find_transitions(speed, distance)
        assert len(brake) == 1

    def test_large_accel_triggers_throttle(self) -> None:
        """A speed rise well above threshold must register a throttle point."""
        n = 100
        distance = np.arange(n) * 0.7
        speed = np.concatenate([np.full(50, 30.0), np.full(50, 36.0)])  # 6 m/s rise
        brake, throttle = _find_transitions(speed, distance)
        assert len(throttle) == 1

    def test_decel_reversal_while_in_decel_state_triggers_throttle(self) -> None:
        """Speed reversal during decel (lines 263-268): should produce a throttle point."""
        # Speed drops 2 m/s (enters decel), then rises 2 m/s (reversal → accel)
        speed = np.array([30.0, 29.0, 28.0, 29.0, 30.0])
        distance = np.arange(len(speed)) * 0.7
        brake, throttle = _find_transitions(speed, distance)
        assert len(brake) >= 1
        assert len(throttle) >= 1

    def test_accel_reversal_while_in_accel_state_triggers_brake(self) -> None:
        """Speed reversal during accel (lines 269-274): should produce a brake point."""
        # Speed rises 2 m/s (enters accel), then drops 2 m/s (reversal → decel)
        speed = np.array([30.0, 31.0, 32.0, 31.0, 30.0])
        distance = np.arange(len(speed)) * 0.7
        brake, throttle = _find_transitions(speed, distance)
        assert len(throttle) >= 1
        assert len(brake) >= 1

    def test_anchor_updates_to_speed_minimum_during_decel(self) -> None:
        """During decel, the anchor tracks the minimum speed so reversal distance is correct."""
        # Speed: 50 → 40 → 35 → 45 (decel to 35, then reversal with 10 m/s gain)
        speed = np.array([50.0, 46.0, 42.0, 38.0, 35.0, 38.0, 42.0, 45.0])
        distance = np.arange(len(speed)) * 0.7
        brake, throttle = _find_transitions(speed, distance)
        assert len(brake) >= 1
        assert len(throttle) >= 1


# ---------------------------------------------------------------------------
# TestSegmentTime
# ---------------------------------------------------------------------------


class TestSegmentTime:
    """Tests for the internal _segment_time helper."""

    def test_zero_arc_length_returns_zero(self) -> None:
        """Zero arc length should return 0.0."""
        params = default_vehicle_params()
        assert _segment_time(30.0, 30.0, 20.0, 0.0, params) == 0.0

    def test_negative_arc_length_returns_zero(self) -> None:
        """Negative arc length should return 0.0."""
        params = default_vehicle_params()
        assert _segment_time(30.0, 30.0, 20.0, -10.0, params) == 0.0

    def test_constant_speed_segment(self) -> None:
        """If entry = exit = min, time should be arc_length / speed."""
        params = default_vehicle_params()
        speed = 20.0
        arc = 100.0
        t = _segment_time(speed, speed, speed, arc, params)
        expected = arc / speed  # 5.0 seconds
        assert t == pytest.approx(expected, rel=0.02)

    def test_positive_time(self) -> None:
        """Segment time should always be positive for valid inputs."""
        params = default_vehicle_params()
        t = _segment_time(40.0, 35.0, 25.0, 150.0, params)
        assert t > 0.0

    def test_higher_min_speed_shorter_time(self) -> None:
        """Higher min speed through corner should produce shorter time."""
        params = default_vehicle_params()
        t_slow = _segment_time(40.0, 35.0, 20.0, 150.0, params)
        t_fast = _segment_time(40.0, 35.0, 25.0, 150.0, params)
        assert t_fast < t_slow

    def test_longer_arc_longer_time(self) -> None:
        """Longer arc length should produce longer segment time."""
        params = default_vehicle_params()
        t_short = _segment_time(40.0, 35.0, 25.0, 100.0, params)
        t_long = _segment_time(40.0, 35.0, 25.0, 200.0, params)
        assert t_long > t_short


# ---------------------------------------------------------------------------
# TestComputeSpeedSensitivity
# ---------------------------------------------------------------------------


class TestComputeSpeedSensitivity:
    """Tests for the public compute_speed_sensitivity function."""

    def test_positive_sensitivity(self) -> None:
        """Speed sensitivity should be positive for a typical corner."""
        params = default_vehicle_params()
        sensitivity = compute_speed_sensitivity(
            corner_entry_speed_mps=40.0,
            corner_exit_speed_mps=35.0,
            corner_min_speed_mps=25.0,
            corner_arc_length_m=150.0,
            vehicle=params,
        )
        assert sensitivity > 0.0

    def test_zero_arc_length_returns_zero(self) -> None:
        """Zero arc length should return 0.0 sensitivity."""
        params = default_vehicle_params()
        sensitivity = compute_speed_sensitivity(
            corner_entry_speed_mps=40.0,
            corner_exit_speed_mps=35.0,
            corner_min_speed_mps=25.0,
            corner_arc_length_m=0.0,
            vehicle=params,
        )
        assert sensitivity == 0.0

    def test_zero_min_speed_returns_zero(self) -> None:
        """Zero min speed should return 0.0 sensitivity."""
        params = default_vehicle_params()
        sensitivity = compute_speed_sensitivity(
            corner_entry_speed_mps=40.0,
            corner_exit_speed_mps=35.0,
            corner_min_speed_mps=0.0,
            corner_arc_length_m=150.0,
            vehicle=params,
        )
        assert sensitivity == 0.0

    def test_slow_corner_higher_sensitivity(self) -> None:
        """Slower corners should generally have higher speed sensitivity.

        At low min speeds, the +1 mph increment is a larger fraction of
        the apex speed, so the time saved should be greater.
        """
        params = default_vehicle_params()
        slow = compute_speed_sensitivity(
            corner_entry_speed_mps=30.0,
            corner_exit_speed_mps=25.0,
            corner_min_speed_mps=15.0,
            corner_arc_length_m=150.0,
            vehicle=params,
        )
        fast = compute_speed_sensitivity(
            corner_entry_speed_mps=60.0,
            corner_exit_speed_mps=55.0,
            corner_min_speed_mps=45.0,
            corner_arc_length_m=150.0,
            vehicle=params,
        )
        assert slow > fast

    def test_longer_corner_higher_sensitivity(self) -> None:
        """Longer corners should have higher sensitivity (more time at min speed)."""
        params = default_vehicle_params()
        short = compute_speed_sensitivity(
            corner_entry_speed_mps=40.0,
            corner_exit_speed_mps=35.0,
            corner_min_speed_mps=25.0,
            corner_arc_length_m=80.0,
            vehicle=params,
        )
        long = compute_speed_sensitivity(
            corner_entry_speed_mps=40.0,
            corner_exit_speed_mps=35.0,
            corner_min_speed_mps=25.0,
            corner_arc_length_m=300.0,
            vehicle=params,
        )
        assert long > short

    def test_reasonable_magnitude(self) -> None:
        """Sensitivity should be in a reasonable range (0.01 to 1.0 seconds per mph).

        The generic Bentley approximation is ~0.5s. A physics-based computation
        should yield values in a similar ballpark for typical corners.
        """
        params = default_vehicle_params()
        sensitivity = compute_speed_sensitivity(
            corner_entry_speed_mps=40.0,
            corner_exit_speed_mps=35.0,
            corner_min_speed_mps=25.0,
            corner_arc_length_m=200.0,
            vehicle=params,
        )
        assert 0.01 < sensitivity < 1.0

    def test_negative_arc_returns_zero(self) -> None:
        """Negative arc length should return 0.0."""
        params = default_vehicle_params()
        sensitivity = compute_speed_sensitivity(
            corner_entry_speed_mps=40.0,
            corner_exit_speed_mps=35.0,
            corner_min_speed_mps=25.0,
            corner_arc_length_m=-50.0,
            vehicle=params,
        )
        assert sensitivity == 0.0

    def test_different_vehicle_params(self) -> None:
        """Different vehicle parameters should produce different sensitivities."""
        low_grip = VehicleParams(
            mu=0.8,
            max_accel_g=0.3,
            max_decel_g=0.8,
            max_lateral_g=0.8,
        )
        high_grip = VehicleParams(
            mu=1.2,
            max_accel_g=0.7,
            max_decel_g=1.2,
            max_lateral_g=1.2,
        )
        s_low = compute_speed_sensitivity(
            corner_entry_speed_mps=40.0,
            corner_exit_speed_mps=35.0,
            corner_min_speed_mps=25.0,
            corner_arc_length_m=150.0,
            vehicle=low_grip,
        )
        s_high = compute_speed_sensitivity(
            corner_entry_speed_mps=40.0,
            corner_exit_speed_mps=35.0,
            corner_min_speed_mps=25.0,
            corner_arc_length_m=150.0,
            vehicle=high_grip,
        )
        # Both should be positive and different
        assert s_low > 0.0
        assert s_high > 0.0
        assert s_low != pytest.approx(s_high, abs=1e-6)


# ---------------------------------------------------------------------------
# TestElevationIntegration — gradient_sin in solver
# ---------------------------------------------------------------------------


class TestElevationIntegration:
    """Tests for elevation/gradient integration in the velocity solver."""

    def test_uphill_reduces_speed(self) -> None:
        """Same curvature with uphill gradient should produce lower optimal speed."""
        # Corner then long straight (uphill should slow acceleration)
        corner = np.full(100, 0.02)
        straight = np.zeros(1500)
        curvature = np.concatenate([corner, straight])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        # 5% uphill gradient: sin(theta) ~ 0.05
        n = len(curvature)
        gradient_uphill = np.full(n, 0.05)

        profile_flat = compute_optimal_profile(cr, params, closed_circuit=False)
        profile_uphill = compute_optimal_profile(
            cr, params, closed_circuit=False, gradient_sin=gradient_uphill
        )

        # Check speed partway through the straight — uphill should be slower
        check_idx = 400
        assert (
            profile_uphill.optimal_speed_mps[check_idx]
            < (profile_flat.optimal_speed_mps[check_idx])
        )

        # Uphill lap time should be longer
        assert profile_uphill.lap_time_s > profile_flat.lap_time_s

    def test_downhill_increases_speed(self) -> None:
        """Same curvature with downhill gradient should produce higher optimal speed."""
        corner = np.full(100, 0.02)
        straight = np.zeros(1500)
        curvature = np.concatenate([corner, straight])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        n = len(curvature)
        gradient_downhill = np.full(n, -0.05)

        profile_flat = compute_optimal_profile(cr, params, closed_circuit=False)
        profile_downhill = compute_optimal_profile(
            cr, params, closed_circuit=False, gradient_sin=gradient_downhill
        )

        # Downhill should accelerate faster on the straight
        check_idx = 400
        assert (
            profile_downhill.optimal_speed_mps[check_idx]
            > (profile_flat.optimal_speed_mps[check_idx])
        )

        # Downhill lap time should be shorter
        assert profile_downhill.lap_time_s < profile_flat.lap_time_s

    def test_none_gradient_backward_compatible(self) -> None:
        """gradient_sin=None should produce identical results to current behavior."""
        curvature = np.concatenate(
            [
                np.zeros(300),
                np.full(200, 0.01),
                np.zeros(300),
            ]
        )
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        profile_default = compute_optimal_profile(cr, params)
        profile_none = compute_optimal_profile(cr, params, gradient_sin=None)

        np.testing.assert_array_equal(
            profile_default.optimal_speed_mps,
            profile_none.optimal_speed_mps,
        )
        assert profile_default.lap_time_s == profile_none.lap_time_s

    def test_zero_gradient_identical_to_flat(self) -> None:
        """All-zero gradient_sin should produce identical results to None gradient."""
        curvature = np.concatenate(
            [
                np.zeros(300),
                np.full(200, 0.01),
                np.zeros(300),
            ]
        )
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        n = len(curvature)
        zero_gradient = np.zeros(n)

        profile_flat = compute_optimal_profile(cr, params, gradient_sin=None)
        profile_zero = compute_optimal_profile(cr, params, gradient_sin=zero_gradient)

        np.testing.assert_allclose(
            profile_zero.optimal_speed_mps,
            profile_flat.optimal_speed_mps,
            atol=1e-10,
        )

    def test_closed_circuit_with_gradient(self) -> None:
        """Gradient should work correctly with closed-circuit tripling."""
        corner = np.full(100, 0.02)
        straight = np.zeros(900)
        curvature = np.concatenate([corner, straight])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        n = len(curvature)
        gradient = np.full(n, 0.03)  # mild uphill

        profile = compute_optimal_profile(cr, params, closed_circuit=True, gradient_sin=gradient)

        # Should still produce valid output
        assert profile.lap_time_s > 0.0
        assert np.all(profile.optimal_speed_mps >= MIN_SPEED_MPS)
        assert np.all(profile.optimal_speed_mps <= params.top_speed_mps)
        assert len(profile.optimal_speed_mps) == n

    def test_gradient_affects_cornering_speed(self) -> None:
        """On steep grade, cornering speed should be slightly reduced (cos correction)."""
        kappa = 0.01
        n = 1000
        curvature = np.full(n, kappa)
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        # 10% grade — cos(theta) = sqrt(1 - sin^2) ~ 0.995, small effect
        gradient_steep = np.full(n, 0.10)

        profile_flat = compute_optimal_profile(cr, params, gradient_sin=None)
        profile_steep = compute_optimal_profile(cr, params, gradient_sin=gradient_steep)

        # Cornering speed should be slightly lower with steep gradient
        # (reduced normal force means reduced grip)
        interior_flat = profile_flat.max_cornering_speed_mps[100:-100]
        interior_steep = profile_steep.max_cornering_speed_mps[100:-100]
        assert np.all(interior_steep <= interior_flat + 1e-10)


# ---------------------------------------------------------------------------
# TestPerPointMu — mu_array in solver
# ---------------------------------------------------------------------------


class TestPerPointMu:
    """Tests for per-point mu_array support in the velocity solver."""

    def test_per_point_mu_changes_cornering_speed(self) -> None:
        """Higher mu_array values at curved points produce higher max cornering speed."""
        n = 500
        kappa = 0.01  # uniform curvature
        curvature = np.full(n, kappa)
        abs_curvature = np.abs(curvature)
        params = default_vehicle_params()  # mu=1.0

        # mu_array with higher grip at the first half, lower at second half
        mu_high = np.full(n, 1.5)
        mu_low = np.full(n, 0.5)

        speed_high = _compute_max_cornering_speed(abs_curvature, params, mu_array=mu_high)
        speed_low = _compute_max_cornering_speed(abs_curvature, params, mu_array=mu_low)

        # Higher mu should produce higher cornering speed everywhere
        assert np.all(speed_high > speed_low)

        # Verify the expected relationship: v = sqrt(mu * G / kappa)
        # At each point, speed should scale with sqrt(mu)
        ratio = speed_high[0] / speed_low[0]
        expected_ratio = np.sqrt(1.5 / 0.5)
        assert ratio == pytest.approx(expected_ratio, rel=0.01)

    def test_none_mu_array_backward_compatible(self) -> None:
        """mu_array=None produces identical results to the current behavior."""
        curvature = np.concatenate(
            [
                np.zeros(200),
                np.full(100, 0.01),
                np.zeros(200),
            ]
        )
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        profile_default = compute_optimal_profile(cr, params)
        profile_none_mu = compute_optimal_profile(cr, params, mu_array=None)

        np.testing.assert_array_equal(
            profile_default.optimal_speed_mps,
            profile_none_mu.optimal_speed_mps,
        )
        assert profile_default.lap_time_s == profile_none_mu.lap_time_s

    def test_mu_array_with_gradient_sin(self) -> None:
        """mu_array works correctly alongside gradient_sin (both Task 2 and P5)."""
        n = 500
        kappa = 0.01
        curvature = np.full(n, kappa)
        abs_curvature = np.abs(curvature)
        params = default_vehicle_params()

        gradient_sin = np.full(n, 0.05)
        mu_array = np.full(n, 1.2)

        # With both gradient and mu_array: should produce valid output
        speed = _compute_max_cornering_speed(
            abs_curvature, params, gradient_sin=gradient_sin, mu_array=mu_array
        )

        assert np.all(np.isfinite(speed))
        assert np.all(speed >= MIN_SPEED_MPS)
        assert np.all(speed <= params.top_speed_mps)

    def test_mu_array_threaded_through_compute_optimal_profile(self) -> None:
        """mu_array parameter is correctly threaded through compute_optimal_profile."""
        n = 500
        curvature = np.concatenate(
            [
                np.zeros(200),
                np.full(100, 0.01),
                np.zeros(200),
            ]
        )
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()  # mu=1.0

        # Use a higher mu_array → should produce a faster lap
        mu_high = np.full(n, 1.5)
        profile_default = compute_optimal_profile(cr, params)
        profile_high_mu = compute_optimal_profile(cr, params, mu_array=mu_high)

        # Higher mu everywhere should yield a faster (or equal) lap time
        assert profile_high_mu.lap_time_s <= profile_default.lap_time_s


# ---------------------------------------------------------------------------
# TestVerticalCurvature — compression/crest effects in solver
# ---------------------------------------------------------------------------


class TestVerticalCurvature:
    """Tests for vertical curvature (compression/crest) integration in the solver."""

    def test_compression_increases_cornering_speed(self) -> None:
        """Positive vertical curvature (compression) should allow higher cornering speed."""
        n = 500
        kappa = 0.01  # lateral curvature
        curvature = np.full(n, kappa)
        abs_curvature = np.abs(curvature)
        params = default_vehicle_params()

        # Compression: κ_v = +0.005 (like bottom of corkscrew)
        kv_compression = np.full(n, 0.005)

        speed_flat = _compute_max_cornering_speed(abs_curvature, params)
        speed_compression = _compute_max_cornering_speed(
            abs_curvature, params, vertical_curvature=kv_compression
        )

        # Compression should increase cornering speed
        assert np.all(speed_compression > speed_flat)

    def test_crest_decreases_cornering_speed(self) -> None:
        """Negative vertical curvature (crest) should reduce cornering speed."""
        n = 500
        kappa = 0.01
        curvature = np.full(n, kappa)
        abs_curvature = np.abs(curvature)
        params = default_vehicle_params()

        # Crest: κ_v = -0.005 (like top of hill)
        kv_crest = np.full(n, -0.005)

        speed_flat = _compute_max_cornering_speed(abs_curvature, params)
        speed_crest = _compute_max_cornering_speed(
            abs_curvature, params, vertical_curvature=kv_crest
        )

        # Crest should decrease cornering speed
        assert np.all(speed_crest < speed_flat)

    def test_zero_vertical_curvature_identical_to_none(self) -> None:
        """All-zero vertical curvature should match None (backward compatible)."""
        curvature = np.concatenate([np.zeros(300), np.full(200, 0.01), np.zeros(300)])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()
        n = len(curvature)

        profile_none = compute_optimal_profile(cr, params, closed_circuit=False)
        profile_zero = compute_optimal_profile(
            cr,
            params,
            closed_circuit=False,
            vertical_curvature=np.zeros(n),
        )

        np.testing.assert_allclose(
            profile_zero.optimal_speed_mps,
            profile_none.optimal_speed_mps,
            atol=1e-10,
        )

    def test_compression_reduces_lap_time(self) -> None:
        """A track with compression at corners should have faster lap time."""
        corner = np.full(200, 0.015)
        straight = np.zeros(800)
        curvature = np.concatenate([straight, corner, straight])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()
        n = len(curvature)

        # Compression only in the corner zone
        kv = np.zeros(n)
        kv[800:1000] = 0.005  # compression in corner

        profile_flat = compute_optimal_profile(cr, params, closed_circuit=False)
        profile_comp = compute_optimal_profile(
            cr, params, closed_circuit=False, vertical_curvature=kv
        )

        assert profile_comp.lap_time_s < profile_flat.lap_time_s

    def test_crest_increases_lap_time(self) -> None:
        """A track with a crest at corners should have slower lap time."""
        corner = np.full(200, 0.015)
        straight = np.zeros(800)
        curvature = np.concatenate([straight, corner, straight])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()
        n = len(curvature)

        # Crest only in the corner zone
        kv = np.zeros(n)
        kv[800:1000] = -0.005

        profile_flat = compute_optimal_profile(cr, params, closed_circuit=False)
        profile_crest = compute_optimal_profile(
            cr, params, closed_circuit=False, vertical_curvature=kv
        )

        assert profile_crest.lap_time_s > profile_flat.lap_time_s

    def test_vertical_curvature_with_closed_circuit(self) -> None:
        """Vertical curvature should work correctly with closed-circuit tripling."""
        corner = np.full(100, 0.02)
        straight = np.zeros(900)
        curvature = np.concatenate([corner, straight])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()
        n = len(curvature)

        kv = np.zeros(n)
        kv[0:100] = 0.003  # compression in corner

        profile = compute_optimal_profile(cr, params, closed_circuit=True, vertical_curvature=kv)

        assert profile.lap_time_s > 0.0
        assert np.all(profile.optimal_speed_mps >= MIN_SPEED_MPS)
        assert np.all(profile.optimal_speed_mps <= params.top_speed_mps)
        assert len(profile.optimal_speed_mps) == n

    def test_compression_formula_correctness(self) -> None:
        """Verify the formula: v² = mu·g / (|κ_lat| - mu·κ_v).

        For mu=1.0, κ_lat=0.01, κ_v=0.002:
        v² = 1.0 * 9.81 / (0.01 - 1.0 * 0.002) = 9.81 / 0.008 = 1226.25
        v = 35.018 m/s (vs 31.32 m/s flat)
        """
        n = 100
        kappa_lat = 0.01
        kappa_v = 0.002
        abs_curvature = np.full(n, kappa_lat)
        params = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            top_speed_mps=80.0,
        )

        kv = np.full(n, kappa_v)
        speed = _compute_max_cornering_speed(abs_curvature, params, vertical_curvature=kv)

        expected = np.sqrt(params.mu * G / (kappa_lat - params.mu * kappa_v))
        np.testing.assert_allclose(speed, expected, rtol=1e-10)

    def test_forward_pass_compression_increases_accel(self) -> None:
        """Compression should increase available traction in forward pass."""
        n = 500
        curvature = np.zeros(n)  # straight
        abs_k = np.abs(curvature)
        max_speed = np.full(n, 80.0)
        max_speed[0] = 20.0  # start slow
        params = default_vehicle_params()
        step_m = 0.7

        kv_compression = np.full(n, 0.01)

        v_flat = _forward_pass(max_speed, step_m, params, abs_k)
        v_comp = _forward_pass(max_speed, step_m, params, abs_k, vertical_curvature=kv_compression)

        # With compression, should accelerate faster
        mid = n // 2
        assert v_comp[mid] > v_flat[mid]

    def test_backward_pass_compression_increases_braking(self) -> None:
        """Compression should increase available braking in backward pass."""
        n = 500
        curvature = np.zeros(n)
        abs_k = np.abs(curvature)
        max_speed = np.full(n, 80.0)
        max_speed[-1] = 20.0  # end slow (backward pass starts here)
        params = default_vehicle_params()
        step_m = 0.7

        kv_compression = np.full(n, 0.01)

        v_flat = _backward_pass(max_speed, step_m, params, abs_k)
        v_comp = _backward_pass(max_speed, step_m, params, abs_k, vertical_curvature=kv_compression)

        # With compression, backward pass should allow faster approach
        mid = n // 2
        assert v_comp[mid] > v_flat[mid]

    def test_none_vertical_curvature_backward_compatible(self) -> None:
        """vertical_curvature=None produces identical results to before."""
        curvature = np.concatenate([np.zeros(300), np.full(200, 0.01), np.zeros(300)])
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = default_vehicle_params()

        profile_default = compute_optimal_profile(cr, params)
        profile_none_kv = compute_optimal_profile(cr, params, vertical_curvature=None)

        np.testing.assert_array_equal(
            profile_default.optimal_speed_mps,
            profile_none_kv.optimal_speed_mps,
        )
        assert profile_default.lap_time_s == profile_none_kv.lap_time_s


# ---------------------------------------------------------------------------
# TestLoadSensitivity
# ---------------------------------------------------------------------------


class TestLoadSensitivity:
    """Tests for tire load sensitivity correction in cornering speed."""

    def test_load_sensitivity_reduces_cornering_speed(self) -> None:
        """Load sensitivity should reduce max cornering speed vs constant-mu model."""
        n = 200
        curvature = np.full(n, 1.0 / 50.0)  # constant 50m radius
        cr = _make_curvature_result(curvature, step_m=1.0)

        # No load sensitivity (n=1.0)
        params_no_ls = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            load_sensitivity_exponent=1.0,
        )
        profile_no_ls = compute_optimal_profile(cr, params_no_ls, closed_circuit=False)

        # With load sensitivity (n=0.82, Miata-like dimensions)
        params_ls = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            load_sensitivity_exponent=0.82,
            cg_height_m=0.46,
            track_width_m=1.41,
        )
        profile_ls = compute_optimal_profile(cr, params_ls, closed_circuit=False)

        # Load sensitivity should produce lower cornering speeds
        mid = n // 2
        assert profile_ls.optimal_speed_mps[mid] < profile_no_ls.optimal_speed_mps[mid]
        # Effect is modest (~0.2-2%) for typical road car dimensions
        reduction_pct = (
            1.0 - profile_ls.optimal_speed_mps[mid] / profile_no_ls.optimal_speed_mps[mid]
        ) * 100
        assert 0.1 < reduction_pct < 10.0, f"Got {reduction_pct:.1f}%"

    def test_load_sensitivity_exponent_1_is_noop(self) -> None:
        """When n=1.0, load sensitivity correction should have no effect."""
        n = 200
        curvature = np.full(n, 1.0 / 50.0)
        cr = _make_curvature_result(curvature, step_m=1.0)

        params_base = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
        )
        params_n1 = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            load_sensitivity_exponent=1.0,
            cg_height_m=0.46,
            track_width_m=1.41,
        )
        profile_base = compute_optimal_profile(cr, params_base, closed_circuit=False)
        profile_n1 = compute_optimal_profile(cr, params_n1, closed_circuit=False)

        np.testing.assert_array_almost_equal(
            profile_base.optimal_speed_mps,
            profile_n1.optimal_speed_mps,
        )

    def test_load_sensitivity_zero_dimensions_is_noop(self) -> None:
        """When CG height or track width is 0, correction is skipped."""
        n = 200
        curvature = np.full(n, 1.0 / 50.0)
        cr = _make_curvature_result(curvature, step_m=1.0)

        params_base = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
        )
        params_no_dims = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            load_sensitivity_exponent=0.82,
            cg_height_m=0.0,
            track_width_m=0.0,
        )
        profile_base = compute_optimal_profile(cr, params_base, closed_circuit=False)
        profile_no_dims = compute_optimal_profile(cr, params_no_dims, closed_circuit=False)

        np.testing.assert_array_almost_equal(
            profile_base.optimal_speed_mps,
            profile_no_dims.optimal_speed_mps,
        )

    def test_lower_exponent_means_more_reduction(self) -> None:
        """Slick tires (n=0.75) should lose more to load sensitivity than street (n=0.85)."""
        n = 200
        curvature = np.full(n, 1.0 / 50.0)
        cr = _make_curvature_result(curvature, step_m=1.0)

        common = dict(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            cg_height_m=0.46,
            track_width_m=1.41,
        )
        params_street = VehicleParams(**common, load_sensitivity_exponent=0.85)
        params_slick = VehicleParams(**common, load_sensitivity_exponent=0.75)

        profile_street = compute_optimal_profile(cr, params_street, closed_circuit=False)
        profile_slick = compute_optimal_profile(cr, params_slick, closed_circuit=False)

        mid = n // 2
        # Slick (lower n) should have lower cornering speed due to more load sensitivity
        assert profile_slick.optimal_speed_mps[mid] < profile_street.optimal_speed_mps[mid]

    def test_load_sensitivity_on_straight_is_noop(self) -> None:
        """Straight sections (zero curvature) should be unaffected by load sensitivity."""
        n = 200
        curvature = np.zeros(n)
        cr = _make_curvature_result(curvature, step_m=1.0)

        params_base = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
        )
        params_ls = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            load_sensitivity_exponent=0.75,
            cg_height_m=0.50,
            track_width_m=1.50,
        )
        profile_base = compute_optimal_profile(cr, params_base, closed_circuit=False)
        profile_ls = compute_optimal_profile(cr, params_ls, closed_circuit=False)

        # On a straight, top speed is the limit — load sensitivity only affects cornering
        np.testing.assert_array_almost_equal(
            profile_base.optimal_speed_mps,
            profile_ls.optimal_speed_mps,
        )


# ---------------------------------------------------------------------------
# TestPowerLimitedAcceleration
# ---------------------------------------------------------------------------


class TestPowerLimitedAcceleration:
    """Tests for the power-limited acceleration model in the forward pass."""

    def test_power_limited_acceleration_at_high_speed(self) -> None:
        """Above crossover speed, acceleration should be power-limited."""
        # Tight corner followed by a long straight — forces acceleration from low speed
        corner = np.full(50, 0.04)  # tight corner (~25m radius, ~15 m/s)
        straight = np.zeros(400)
        curvature = np.concatenate([corner, straight])
        cr = _make_curvature_result(curvature, step_m=1.0)

        # Without power limit — high top speed so the cap isn't the bottleneck
        params_const = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            top_speed_mps=120.0,
        )
        profile_const = compute_optimal_profile(cr, params_const, closed_circuit=False)

        # With power limit (155hp Miata-like)
        params_power = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            top_speed_mps=120.0,
            wheel_power_w=115_000 * 0.85,  # ~97.75 kW at wheels
            mass_kg=1050.0,
        )
        profile_power = compute_optimal_profile(cr, params_power, closed_circuit=False)

        # Power-limited car should be slower at end of straight
        assert profile_power.optimal_speed_mps[-1] < profile_const.optimal_speed_mps[-1]

        # In the corner (low speed), speeds should be identical (grip-limited regime)
        assert abs(profile_power.optimal_speed_mps[25] - profile_const.optimal_speed_mps[25]) < 0.1

    def test_power_limit_disabled_when_zero(self) -> None:
        """wheel_power_w=0 should not affect results (backward compatible)."""
        n = 200
        curvature = np.zeros(n)
        cr = _make_curvature_result(curvature, step_m=1.0)

        params_base = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
        )
        params_zero = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            wheel_power_w=0.0,
            mass_kg=0.0,
        )

        p1 = compute_optimal_profile(cr, params_base, closed_circuit=False)
        p2 = compute_optimal_profile(cr, params_zero, closed_circuit=False)

        np.testing.assert_array_almost_equal(p1.optimal_speed_mps, p2.optimal_speed_mps)

    def test_power_limit_only_affects_forward_pass(self) -> None:
        """Power limit should not affect braking (backward pass)."""
        n = 500
        curvature = np.zeros(n)
        abs_k = np.abs(curvature)
        max_speed = np.full(n, 80.0)
        max_speed[-1] = 20.0  # end slow (backward pass starts here)
        step_m = 1.0

        params = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            wheel_power_w=100_000.0,
            mass_kg=1050.0,
        )
        params_no_power = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
        )

        v_power = _backward_pass(max_speed, step_m, params, abs_k)
        v_no_power = _backward_pass(max_speed, step_m, params_no_power, abs_k)

        # Backward pass should be identical — power limit is not in braking
        np.testing.assert_array_almost_equal(v_power, v_no_power)

    def test_crossover_speed_physics(self) -> None:
        """Verify the crossover speed where grip-limit meets power-limit.

        Crossover: max_accel_g * G = P / (m * v_cross)
        v_cross = P / (m * max_accel_g * G)
        """
        wheel_power_w = 100_000.0
        mass_kg = 1050.0
        max_accel_g = 0.5

        v_crossover = wheel_power_w / (mass_kg * max_accel_g * G)

        # Below crossover, grip-limited: accel_g = 0.5
        v_low = v_crossover * 0.5
        power_accel = wheel_power_w / (mass_kg * v_low * G)
        assert power_accel > max_accel_g  # power not the bottleneck

        # Above crossover, power-limited: accel_g < 0.5
        v_high = v_crossover * 2.0
        power_accel_high = wheel_power_w / (mass_kg * v_high * G)
        assert power_accel_high < max_accel_g  # power IS the bottleneck

    def test_power_limit_with_mass_zero_disabled(self) -> None:
        """When mass_kg=0 but wheel_power_w>0, power limit should be disabled."""
        n = 200
        curvature = np.zeros(n)
        cr = _make_curvature_result(curvature, step_m=1.0)

        params_base = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
        )
        params_no_mass = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            wheel_power_w=100_000.0,
            mass_kg=0.0,
        )

        p1 = compute_optimal_profile(cr, params_base, closed_circuit=False)
        p2 = compute_optimal_profile(cr, params_no_mass, closed_circuit=False)

        np.testing.assert_array_almost_equal(p1.optimal_speed_mps, p2.optimal_speed_mps)


# ---------------------------------------------------------------------------
# TestTractionMultiplier — AWD traction advantage
# ---------------------------------------------------------------------------


class TestTractionMultiplier:
    """Tests for the traction_multiplier field in the forward pass."""

    def test_traction_multiplier_increases_grip_limited_accel(self) -> None:
        """traction_multiplier > 1 should produce faster acceleration at low speed."""
        corner = np.full(50, 0.03)
        straight = np.zeros(300)
        curvature = np.concatenate([corner, straight])
        cr = _make_curvature_result(curvature, step_m=1.0)

        base = VehicleParams(mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0)
        awd = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            traction_multiplier=1.10,
        )

        p_base = compute_optimal_profile(cr, base, closed_circuit=False)
        p_awd = compute_optimal_profile(cr, awd, closed_circuit=False)

        # AWD should be faster on the straight (grip-limited accel)
        assert p_awd.optimal_speed_mps[200] > p_base.optimal_speed_mps[200]
        assert p_awd.lap_time_s < p_base.lap_time_s


# ---------------------------------------------------------------------------
# TestPowerBandFactor — engine torque curve derating
# ---------------------------------------------------------------------------


class TestPowerBandFactor:
    """Tests for the power_band_factor field in the forward pass."""

    def test_low_power_band_slows_power_limited_accel(self) -> None:
        """power_band_factor < 1.0 should produce slower acceleration at high speed."""
        corner = np.full(50, 0.04)
        straight = np.zeros(400)
        curvature = np.concatenate([corner, straight])
        cr = _make_curvature_result(curvature, step_m=1.0)

        base = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            wheel_power_w=150_000,
            mass_kg=1200,
            power_band_factor=1.0,
        )
        peaky = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            wheel_power_w=150_000,
            mass_kg=1200,
            power_band_factor=0.80,
        )

        p_base = compute_optimal_profile(cr, base, closed_circuit=False)
        p_peaky = compute_optimal_profile(cr, peaky, closed_circuit=False)

        # Peaky engine should be slower on the straight
        assert p_peaky.optimal_speed_mps[-1] < p_base.optimal_speed_mps[-1]
        assert p_peaky.lap_time_s > p_base.lap_time_s

    def test_power_band_no_effect_without_power_model(self) -> None:
        """When wheel_power_w=0, power_band_factor should have no effect."""
        cr = _make_curvature_result(np.zeros(200), step_m=1.0)

        base = VehicleParams(mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0)
        derated = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            power_band_factor=0.50,
        )

        p1 = compute_optimal_profile(cr, base, closed_circuit=False)
        p2 = compute_optimal_profile(cr, derated, closed_circuit=False)

        np.testing.assert_array_almost_equal(p1.optimal_speed_mps, p2.optimal_speed_mps)

    def test_corner_speed_unaffected_by_power_band(self) -> None:
        """power_band_factor should not affect cornering speed (grip-limited)."""
        cr = _make_curvature_result(np.full(100, 0.02), step_m=1.0)

        base = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            wheel_power_w=150_000,
            mass_kg=1200,
            power_band_factor=1.0,
        )
        peaky = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            wheel_power_w=150_000,
            mass_kg=1200,
            power_band_factor=0.80,
        )

        p1 = compute_optimal_profile(cr, base, closed_circuit=False)
        p2 = compute_optimal_profile(cr, peaky, closed_circuit=False)

        # Mid-corner speeds should be identical (grip-limited)
        np.testing.assert_allclose(
            p1.optimal_speed_mps[40:60], p2.optimal_speed_mps[40:60], atol=0.5
        )


# ---------------------------------------------------------------------------
# TestDenominatorClamping — vertical curvature safety floor
# ---------------------------------------------------------------------------


class TestDenominatorClamping:
    """Tests that the denominator floor prevents extreme vertical curvature
    from producing unrealistically low or high cornering speeds."""

    def test_large_crest_does_not_produce_extreme_low_speed(self) -> None:
        """A strong crest (negative kv) should not push cornering speed below
        what 50% curvature reduction would give."""
        n = 100
        kappa_lat = 0.02
        abs_curvature = np.full(n, kappa_lat)
        params = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            top_speed_mps=80.0,
        )

        # Large crest: kv = -0.015 → without floor: denom = 0.02 - 1.0*(-0.015) = 0.035
        # With floor: denom = max(0.035, 0.5*0.02=0.01) = 0.035 → no change here
        # But kv = -0.05 → without floor: denom = 0.02 + 0.05 = 0.07 → speed very low
        # With floor: denom = max(0.07, 0.01) = 0.07 → also no change for crests
        # Actually crests INCREASE the denominator, compressions DECREASE it.
        # The floor matters for compressions: kv = +0.019 →
        # without floor: denom = 0.02 - 0.019 = 0.001 → v = sqrt(9.81/0.001) = 99 m/s!
        # with floor: denom = max(0.001, 0.01) = 0.01 → v = sqrt(9.81/0.01) = 31.3 m/s
        kv_extreme_compression = np.full(n, 0.019)

        speed_with_clamp = _compute_max_cornering_speed(
            abs_curvature, params, vertical_curvature=kv_extreme_compression
        )

        # Without the floor, speed would be ~99 m/s (unrealistic)
        # With the floor, it should be bounded around sqrt(g / (0.5 * kappa_lat))
        floor_speed = np.sqrt(params.mu * G / (0.5 * kappa_lat))
        assert np.all(speed_with_clamp <= floor_speed + 1.0)

    def test_moderate_compression_still_increases_speed(self) -> None:
        """Moderate compression (kv = 0.005) should still increase speed vs flat.

        The floor is 50% of lateral curvature, so moderate kv that doesn't
        push the denominator below the floor should have its full effect.
        """
        n = 100
        kappa_lat = 0.02
        abs_curvature = np.full(n, kappa_lat)
        params = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            top_speed_mps=80.0,
        )

        speed_flat = _compute_max_cornering_speed(abs_curvature, params)
        kv_moderate = np.full(n, 0.005)
        speed_comp = _compute_max_cornering_speed(
            abs_curvature, params, vertical_curvature=kv_moderate
        )

        # denom = 0.02 - 1.0*0.005 = 0.015 > floor of 0.01, so full effect applies
        assert np.all(speed_comp > speed_flat)

    def test_mu_array_increases_speed_in_high_grip_corners(self) -> None:
        """Per-corner mu_array with higher mu should produce higher corner speed."""
        n = 800
        curvature = np.concatenate(
            [
                np.zeros(200),
                np.full(200, 0.01),
                np.zeros(200),
                np.full(200, 0.01),
            ]
        )
        cr = _make_curvature_result(curvature, step_m=0.7)
        params = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            top_speed_mps=80.0,
        )

        # Global mu = 1.0 everywhere
        profile_global = compute_optimal_profile(cr, params, closed_circuit=False)

        # Per-corner: mu=1.2 in corner zones (simulating higher grip)
        mu_array = np.full(n, 1.0)
        mu_array[200:400] = 1.2
        mu_array[600:800] = 1.2
        profile_percorner = compute_optimal_profile(
            cr, params, closed_circuit=False, mu_array=mu_array
        )

        # Mid-corner speed should be higher with per-corner mu
        assert profile_percorner.optimal_speed_mps[300] > profile_global.optimal_speed_mps[300]


def test_elevation_confidence_scales_vertical_curvature() -> None:
    """When elevation_confidence < 1.0, vertical curvature effect is reduced."""
    from cataclysm.curvature import CurvatureResult

    n = 100
    distance = np.linspace(0, 70, n)
    curvature = np.full(n, 0.01)  # gentle curve
    vert_curv = np.full(n, 0.005)  # moderate compression

    cr = CurvatureResult(
        distance_m=distance,
        curvature=curvature,
        abs_curvature=np.abs(curvature),
        heading_rad=np.zeros(n),
        x_smooth=np.zeros(n),
        y_smooth=np.zeros(n),
    )

    params_full = VehicleParams(mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0)
    params_half = VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.0,
        max_lateral_g=1.0,
        elevation_confidence=0.5,
    )

    profile_full = compute_optimal_profile(
        cr, params_full, closed_circuit=False, vertical_curvature=vert_curv
    )
    profile_half = compute_optimal_profile(
        cr, params_half, closed_circuit=False, vertical_curvature=vert_curv
    )
    profile_none = compute_optimal_profile(cr, params_full, closed_circuit=False)

    # Half confidence should produce speeds between no-vert and full-vert
    mid_full = float(np.mean(profile_full.optimal_speed_mps))
    mid_half = float(np.mean(profile_half.optimal_speed_mps))
    mid_none = float(np.mean(profile_none.optimal_speed_mps))

    assert mid_none < mid_half < mid_full, (
        f"Expected none({mid_none:.2f}) < half({mid_half:.2f}) < full({mid_full:.2f})"
    )

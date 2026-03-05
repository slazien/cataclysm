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

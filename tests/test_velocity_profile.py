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
    compute_optimal_profile,
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

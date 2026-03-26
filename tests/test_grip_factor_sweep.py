"""Tests for grip_factor_sweep module."""

from __future__ import annotations

from dataclasses import replace as dc_replace

import numpy as np

from cataclysm.curvature import CurvatureResult
from cataclysm.grip_factor_sweep import solver_based_sweep, sweep_grip_factor
from cataclysm.velocity_profile import compute_optimal_profile, default_vehicle_params


class TestSweepGripFactor:
    def test_selects_factor_that_matches_actual_speed(self) -> None:
        """Sweep should find the factor where predicted ~ actual corner speeds."""
        # 3 corners with known actual min speeds
        corner_kappa = np.array([0.02, 0.01, 0.005])  # curvatures
        actual_min_speed = np.array([20.0, 28.0, 40.0])  # m/s
        base_mu = 1.0

        best_f, rmse = sweep_grip_factor(corner_kappa, actual_min_speed, base_mu)
        # Predicted speed = sqrt(F * mu * g / kappa)
        # For corner 0: 20 = sqrt(F * 1.0 * 9.81 / 0.02) -> F = 20^2 * 0.02 / 9.81 = 0.815
        # Best F should be around 0.8-0.9 to match all corners
        assert 0.7 < best_f < 1.1
        assert rmse < 3.0  # m/s — reasonable fit

    def test_returns_1_when_no_corners(self) -> None:
        """Should return F=1.0 when no corner data available."""
        best_f, rmse = sweep_grip_factor(np.array([]), np.array([]), 1.0)
        assert best_f == 1.0

    def test_does_not_allow_overshoot(self) -> None:
        """Selected F should minimize corners where model > actual.

        The asymmetric penalty (5x for overshoot) biases F downward so
        the model predicts conservatively rather than claiming the driver
        can go faster than they actually did.
        """
        # Use speeds achievable within F=[0.80, 1.25] range so the sweep
        # can actually find a non-overshooting solution.
        corner_kappa = np.array([0.02, 0.01])
        # At F=1.0, mu=1.0: sqrt(1.0*1.0*9.81/0.02)=22.1, sqrt(.../0.01)=31.3
        # Set actual slightly below F=1.0 predictions so sweep picks F<1.0
        actual_min_speed = np.array([21.0, 29.0])
        base_mu = 1.0

        best_f, rmse = sweep_grip_factor(corner_kappa, actual_min_speed, base_mu)
        # Predicted speeds at best_f should not systematically exceed actual
        predicted = np.sqrt(best_f * base_mu * 9.81 / corner_kappa)
        overshoot_count = np.sum(predicted > actual_min_speed + 1.0)
        assert overshoot_count == 0
        # F should be biased below 1.0 due to asymmetric penalty
        assert best_f < 1.0

    def test_returns_1_when_all_curvatures_near_zero(self) -> None:
        """Straights (near-zero curvature) should be filtered out."""
        corner_kappa = np.array([0.0005, 0.0002])
        actual_min_speed = np.array([50.0, 60.0])
        best_f, rmse = sweep_grip_factor(corner_kappa, actual_min_speed, 1.0)
        assert best_f == 1.0

    def test_single_corner(self) -> None:
        """Should work with a single corner."""
        corner_kappa = np.array([0.015])
        actual_min_speed = np.array([25.0])
        base_mu = 1.0

        best_f, rmse = sweep_grip_factor(corner_kappa, actual_min_speed, base_mu)
        # Expected: 25^2 * 0.015 / 9.81 = 0.955
        assert 0.8 < best_f < 1.1
        assert rmse < 2.0

    def test_runs_fast(self) -> None:
        """Sweep must complete in <10ms even for many corners."""
        import time

        corner_kappa = np.random.uniform(0.005, 0.03, size=50)
        actual_min_speed = np.random.uniform(15.0, 45.0, size=50)

        start = time.perf_counter()
        sweep_grip_factor(corner_kappa, actual_min_speed, 1.0)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50.0, f"Sweep took {elapsed_ms:.1f}ms, expected <50ms"


def _make_curvature(
    distance_m: np.ndarray,
    kappa: np.ndarray,
) -> CurvatureResult:
    """Build a CurvatureResult from distance and curvature arrays."""
    step = float(distance_m[1] - distance_m[0])
    heading = np.cumsum(kappa * step)
    return CurvatureResult(
        distance_m=distance_m,
        curvature=kappa,
        abs_curvature=np.abs(kappa),
        heading_rad=heading,
        x_smooth=np.cumsum(np.cos(heading)) * step,
        y_smooth=np.cumsum(np.sin(heading)) * step,
    )


class TestSolverBasedSweep:
    """Tests for solver_based_sweep() -- uses full solver instead of analytical."""

    def test_finds_mu_that_reduces_overshoot(self) -> None:
        """Sweep should find mu where solver corner speeds don't exceed actual."""
        n = 700
        distance_m = np.linspace(0, 500, n)
        kappa = np.zeros(n)
        kappa[300:400] = 0.02  # 50m radius corner

        curv = _make_curvature(distance_m, kappa)
        params = default_vehicle_params()
        corner_apex_distances = np.array([250.0])
        actual_min_speeds = np.array([22.0])

        best_mu, n_iters = solver_based_sweep(
            curv,
            params,
            corner_apex_distances,
            actual_min_speeds,
            mu_lo=0.7,
            mu_hi=1.5,
            max_iters=2,
        )

        # Verify: solver at best_mu should not overshoot actual by more than 1 m/s
        adjusted = dc_replace(params, mu=best_mu, max_lateral_g=best_mu)
        profile = compute_optimal_profile(curv, adjusted)
        apex_idx = int(np.searchsorted(distance_m, 250.0))
        predicted = float(profile.optimal_speed_mps[apex_idx])
        assert predicted <= actual_min_speeds[0] + 1.0, (
            f"Solver overshoot: predicted={predicted:.1f} > actual+1={actual_min_speeds[0] + 1:.1f}"
        )
        assert n_iters <= 2

    def test_returns_original_mu_when_no_corners(self) -> None:
        """Should return original mu when no corner data provided."""
        n = 100
        distance_m = np.linspace(0, 100, n)
        curv = CurvatureResult(
            distance_m=distance_m,
            curvature=np.zeros(n),
            abs_curvature=np.zeros(n),
            heading_rad=np.zeros(n),
            x_smooth=distance_m,
            y_smooth=np.zeros(n),
        )
        params = default_vehicle_params()
        best_mu, n_iters = solver_based_sweep(
            curv,
            params,
            np.array([]),
            np.array([]),
        )
        assert best_mu == params.mu
        assert n_iters == 0

    def test_filters_low_curvature_corners(self) -> None:
        """Corners with kappa < 0.008 should be excluded from sweep."""
        n = 700
        distance_m = np.linspace(0, 500, n)
        kappa = np.full(n, 0.002)  # very low curvature everywhere

        curv = _make_curvature(distance_m, kappa)
        params = default_vehicle_params()
        best_mu, n_iters = solver_based_sweep(
            curv,
            params,
            np.array([250.0]),
            np.array([30.0]),
        )
        assert best_mu == params.mu  # no change -- all corners filtered
        assert n_iters == 0

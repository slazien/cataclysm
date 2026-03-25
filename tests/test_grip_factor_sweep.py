"""Tests for grip_factor_sweep module."""

from __future__ import annotations

import numpy as np

from cataclysm.grip_factor_sweep import sweep_grip_factor


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

        assert elapsed_ms < 10.0, f"Sweep took {elapsed_ms:.1f}ms, expected <10ms"

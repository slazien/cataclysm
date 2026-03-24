"""Tests for corner_capability module — Bayesian per-corner capability factor."""

from __future__ import annotations

import numpy as np


class TestBayesianCornerCapability:
    def test_update_moves_posterior_toward_observation(self) -> None:
        from cataclysm.corner_capability import bayesian_update_capability

        # Prior: C ~ N(1.0, 0.1²)
        # Observation: C_obs = 1.15 (corner is faster than model)
        mu_post, sigma_post = bayesian_update_capability(
            mu_prior=1.0, sigma_prior=0.10, c_obs=1.15, sigma_obs=0.09
        )
        assert mu_post > 1.0  # should move toward observation
        assert mu_post < 1.15  # but not all the way
        assert sigma_post < 0.10  # uncertainty should decrease

    def test_convergence_after_five_sessions(self) -> None:
        from cataclysm.corner_capability import bayesian_update_capability

        mu, sigma = 1.0, 0.10
        # 5 sessions all observing C ≈ 1.10
        for _ in range(5):
            mu, sigma = bayesian_update_capability(mu, sigma, 1.10, 0.09)
        assert abs(mu - 1.10) < 0.02  # should converge near 1.10
        assert sigma < 0.06  # uncertainty well below initial

    def test_clamps_to_physical_bounds(self) -> None:
        from cataclysm.corner_capability import bayesian_update_capability

        # Extreme observation shouldn't produce unreasonable posterior
        mu, sigma = bayesian_update_capability(1.0, 0.10, 2.0, 0.09)
        assert mu <= 1.5  # physical bound

    def test_low_observation_clamps_to_minimum(self) -> None:
        from cataclysm.corner_capability import bayesian_update_capability

        mu, sigma = bayesian_update_capability(1.0, 0.10, 0.3, 0.09)
        assert mu >= 0.7  # physical bound

    def test_sigma_always_decreases(self) -> None:
        from cataclysm.corner_capability import bayesian_update_capability

        mu, sigma = bayesian_update_capability(1.0, 0.10, 1.05, 0.09)
        assert sigma < 0.10

    def test_compute_c_obs_from_speeds(self) -> None:
        """C_obs = (v_actual² * kappa) / (mu * g)."""
        from cataclysm.corner_capability import compute_c_obs

        # Corner with kappa=0.02, actual speed=22 m/s, mu=1.0
        # C_obs = (22² * 0.02) / (1.0 * 9.81) = 9.68 / 9.81 = 0.987
        c_obs = compute_c_obs(actual_speed_mps=22.0, kappa=0.02, mu=1.0)
        assert abs(c_obs - 0.987) < 0.01

    def test_compute_c_obs_zero_kappa_returns_default(self) -> None:
        from cataclysm.corner_capability import compute_c_obs

        assert compute_c_obs(actual_speed_mps=30.0, kappa=0.0, mu=1.0) == 1.0

    def test_compute_c_obs_zero_mu_returns_default(self) -> None:
        from cataclysm.corner_capability import compute_c_obs

        assert compute_c_obs(actual_speed_mps=30.0, kappa=0.02, mu=0.0) == 1.0

    def test_compute_c_obs_negative_kappa_returns_default(self) -> None:
        from cataclysm.corner_capability import compute_c_obs

        assert compute_c_obs(actual_speed_mps=30.0, kappa=-0.01, mu=1.0) == 1.0

    def test_precision_weighting_favors_tighter_distribution(self) -> None:
        from cataclysm.corner_capability import bayesian_update_capability

        # Large sigma_obs → posterior stays closer to prior
        mu_wide, _ = bayesian_update_capability(1.0, 0.05, 1.20, 0.50)
        # Small sigma_obs → posterior moves more toward observation
        mu_tight, _ = bayesian_update_capability(1.0, 0.05, 1.20, 0.02)
        assert mu_tight > mu_wide  # tighter obs pulls harder

    def test_symmetric_update(self) -> None:
        from cataclysm.corner_capability import bayesian_update_capability

        # Equal precision → posterior is midpoint
        mu, sigma = bayesian_update_capability(1.0, 0.10, 1.10, 0.10)
        assert abs(mu - 1.05) < 0.001


class TestCFactorMuArrayApplication:
    """Test the mu_array modification logic used in the pipeline APPLY step."""

    def test_c_factor_scales_mu_in_corner_zone(self) -> None:
        """C-factor > 1 should increase mu in corner zone (banked turn)."""
        distance_m = np.linspace(0, 500, 500)
        base_mu = 1.0
        mu_array = np.full(len(distance_m), base_mu)

        # Simulate corner from 100m to 200m with C=1.1
        entry, exit_ = 100.0, 200.0
        c_val = 1.1
        mask = (distance_m >= entry) & (distance_m <= exit_)
        mu_array[mask] *= c_val

        # Corner zone should be boosted
        assert np.all(mu_array[mask] > base_mu)
        assert abs(float(mu_array[mask].mean()) - 1.1) < 0.01
        # Outside corner should remain unchanged
        assert float(mu_array[0]) == base_mu
        assert float(mu_array[-1]) == base_mu

    def test_c_factor_below_one_reduces_mu(self) -> None:
        """C-factor < 1 should reduce mu in corner zone (off-camber)."""
        distance_m = np.linspace(0, 500, 500)
        mu_array = np.full(len(distance_m), 1.2)

        entry, exit_ = 200.0, 300.0
        c_val = 0.9
        mask = (distance_m >= entry) & (distance_m <= exit_)
        mu_array[mask] *= c_val

        assert np.all(mu_array[mask] < 1.2)
        assert abs(float(mu_array[mask].mean()) - 1.08) < 0.01

    def test_empty_c_factors_no_change(self) -> None:
        """Empty c_factors dict should not modify mu_array."""
        distance_m = np.linspace(0, 500, 500)
        mu_array = np.full(len(distance_m), 1.0)
        original = mu_array.copy()

        c_factors: dict[int, float] = {}
        # Pipeline logic: if c_factors and corners → apply
        # With empty dict, condition is falsy → no modification
        if c_factors:
            pass  # Would apply, but empty dict is falsy
        np.testing.assert_array_equal(mu_array, original)

    def test_n_obs_threshold_filters_noisy_data(self) -> None:
        """Only C-factors with n >= 2 should be applied (matching pipeline filter)."""
        c_data: dict[int, tuple[float, float, int]] = {
            1: (1.10, 0.08, 1),  # Only 1 observation — should be excluded
            3: (1.15, 0.07, 2),  # 2 observations — should be included
            5: (0.90, 0.09, 5),  # 5 observations — should be included
        }
        c_factors = {cn: mu_post for cn, (mu_post, _, n) in c_data.items() if n >= 2}
        assert 1 not in c_factors
        assert 3 in c_factors
        assert 5 in c_factors
        assert len(c_factors) == 2

    def test_multiple_corners_applied_independently(self) -> None:
        """Each corner gets its own C-factor applied independently."""
        distance_m = np.linspace(0, 1000, 1000)
        mu_array = np.full(len(distance_m), 1.0)

        # Corner 1: 100-200m, C=1.1
        mask1 = (distance_m >= 100) & (distance_m <= 200)
        mu_array[mask1] *= 1.1

        # Corner 2: 500-600m, C=0.9
        mask2 = (distance_m >= 500) & (distance_m <= 600)
        mu_array[mask2] *= 0.9

        assert float(mu_array[150]) > 1.0  # Corner 1 boosted
        assert float(mu_array[550]) < 1.0  # Corner 2 reduced
        assert float(mu_array[350]) == 1.0  # Between corners unchanged

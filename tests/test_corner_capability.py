"""Tests for corner_capability module — Bayesian per-corner capability factor."""

from __future__ import annotations


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

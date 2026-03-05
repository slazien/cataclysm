"""Tests for cataclysm.banking — banking/camber corrections for effective grip."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cataclysm.banking import (
    MU_CLAMP_MAX,
    MU_CLAMP_MIN,
    apply_banking_to_mu_array,
    effective_mu_with_banking,
)
from cataclysm.corners import Corner


def _make_corner(
    number: int,
    entry_m: float,
    exit_m: float,
    banking_deg: float | None = None,
) -> Corner:
    """Helper to create a minimal Corner for banking tests."""
    apex_m = (entry_m + exit_m) / 2.0
    return Corner(
        number=number,
        entry_distance_m=entry_m,
        exit_distance_m=exit_m,
        apex_distance_m=apex_m,
        min_speed_mps=20.0,
        brake_point_m=None,
        peak_brake_g=None,
        throttle_commit_m=None,
        apex_type="mid",
        banking_deg=banking_deg,
    )


class TestEffectiveMuWithBanking:
    """Tests for the scalar effective_mu_with_banking function."""

    def test_zero_banking_no_change(self) -> None:
        """0 deg banking should return mu unchanged."""
        mu = 1.2
        result = effective_mu_with_banking(mu, 0.0)
        assert result == pytest.approx(mu, abs=1e-10)

    def test_positive_banking_increases_mu(self) -> None:
        """5 deg banking should increase mu by ~19.2% (full Coulomb formula)."""
        mu = 1.0
        result = effective_mu_with_banking(mu, 5.0)
        assert result > mu
        # Expected: (1.0 + tan(5deg)) / (1.0 - 1.0*tan(5deg))
        tan5 = math.tan(math.radians(5.0))
        expected = (mu + tan5) / (1.0 - mu * tan5)
        assert result == pytest.approx(expected, rel=1e-10)
        # Full Coulomb banking formula: ~+19.2% for mu=1.0 at 5 deg
        pct_increase = (result - mu) / mu * 100
        assert pct_increase == pytest.approx(19.2, abs=0.5)

    def test_negative_banking_decreases_mu(self) -> None:
        """-3 deg (off-camber) should decrease mu."""
        mu = 1.0
        result = effective_mu_with_banking(mu, -3.0)
        assert result < mu

    def test_banking_formula_known_values(self) -> None:
        """Verify against hand-calculated values for various angles."""
        mu = 1.0

        # 3 deg: ~+5.6% grip
        r3 = effective_mu_with_banking(mu, 3.0)
        tan3 = math.tan(math.radians(3.0))
        expected3 = (mu + tan3) / (1.0 - mu * tan3)
        assert r3 == pytest.approx(expected3, rel=1e-10)

        # 10 deg: ~+20.6% grip
        r10 = effective_mu_with_banking(mu, 10.0)
        tan10 = math.tan(math.radians(10.0))
        expected10 = (mu + tan10) / (1.0 - mu * tan10)
        assert r10 == pytest.approx(expected10, rel=1e-10)

        # Monotonicity: more banking -> more grip
        assert r3 < r10

    def test_banking_with_different_mu(self) -> None:
        """Banking correction should work for non-unit mu values."""
        for mu in [0.5, 0.8, 1.0, 1.5]:
            banking_deg = 5.0
            result = effective_mu_with_banking(mu, banking_deg)
            tan_theta = math.tan(math.radians(banking_deg))
            expected = (mu + tan_theta) / (1.0 - mu * tan_theta)
            expected_clamped = max(MU_CLAMP_MIN, min(MU_CLAMP_MAX, expected))
            assert result == pytest.approx(expected_clamped, rel=1e-10)

    def test_banking_result_clamped_high(self) -> None:
        """Extreme positive banking should clamp to MU_CLAMP_MAX."""
        # Very large banking angle should not produce unreasonable mu
        result = effective_mu_with_banking(1.0, 40.0)
        assert result <= MU_CLAMP_MAX

    def test_banking_result_clamped_low(self) -> None:
        """Extreme negative banking should clamp to MU_CLAMP_MIN."""
        result = effective_mu_with_banking(0.5, -25.0)
        assert result >= MU_CLAMP_MIN

    def test_symmetry_direction(self) -> None:
        """Positive and negative banking should go in opposite directions."""
        mu = 1.0
        positive = effective_mu_with_banking(mu, 5.0)
        negative = effective_mu_with_banking(mu, -5.0)
        assert positive > mu > negative


class TestApplyBankingToMuArray:
    """Tests for apply_banking_to_mu_array — array-level banking corrections."""

    def test_no_corners_returns_copy(self) -> None:
        """With no corners, output should equal input (but be a copy)."""
        mu = np.ones(100) * 1.2
        dist = np.linspace(0, 500, 100)
        result = apply_banking_to_mu_array(mu, dist, [])
        np.testing.assert_array_equal(result, mu)
        # Must be a copy, not the same object
        assert result is not mu

    def test_banking_array_applied_to_corners_only(self) -> None:
        """Banking correction should only affect the corner zone, not straights."""
        mu = np.ones(200) * 1.0
        dist = np.linspace(0, 1000, 200)
        # Corner from 200m to 400m with 5 deg banking
        c = _make_corner(1, 200.0, 400.0, banking_deg=5.0)
        result = apply_banking_to_mu_array(mu, dist, [c])

        # Points outside corner zone should be unchanged
        outside_mask = (dist < 200.0) | (dist > 400.0)
        np.testing.assert_array_equal(result[outside_mask], mu[outside_mask])

        # Points inside corner zone should have increased mu
        inside_mask = (dist >= 200.0) & (dist <= 400.0)
        assert np.all(result[inside_mask] > mu[inside_mask])

    def test_banking_array_skips_none_banking(self) -> None:
        """Corners with banking_deg=None should be unchanged."""
        mu = np.ones(200) * 1.0
        dist = np.linspace(0, 1000, 200)
        c = _make_corner(1, 200.0, 400.0, banking_deg=None)
        result = apply_banking_to_mu_array(mu, dist, [c])
        np.testing.assert_array_equal(result, mu)

    def test_multiple_corners_independent(self) -> None:
        """Multiple corners with different banking should be applied independently."""
        mu = np.ones(500) * 1.0
        dist = np.linspace(0, 2500, 500)
        c1 = _make_corner(1, 200.0, 400.0, banking_deg=5.0)  # banked
        c2 = _make_corner(2, 800.0, 1000.0, banking_deg=-3.0)  # off-camber
        c3 = _make_corner(3, 1500.0, 1700.0, banking_deg=None)  # no data
        result = apply_banking_to_mu_array(mu, dist, [c1, c2, c3])

        # Corner 1: increased mu
        mask1 = (dist >= 200.0) & (dist <= 400.0)
        assert np.all(result[mask1] > mu[mask1])

        # Corner 2: decreased mu
        mask2 = (dist >= 800.0) & (dist <= 1000.0)
        assert np.all(result[mask2] < mu[mask2])

        # Corner 3 (None): unchanged
        mask3 = (dist >= 1500.0) & (dist <= 1700.0)
        np.testing.assert_array_equal(result[mask3], mu[mask3])

        # Straight zones: unchanged
        straight_mask = dist < 200.0
        np.testing.assert_array_equal(result[straight_mask], mu[straight_mask])

    def test_non_uniform_mu_preserved(self) -> None:
        """Banking correction should apply to varying mu values, not just constant."""
        rng = np.random.default_rng(42)
        mu = rng.uniform(0.8, 1.5, size=200)
        dist = np.linspace(0, 1000, 200)
        c = _make_corner(1, 300.0, 600.0, banking_deg=3.0)
        result = apply_banking_to_mu_array(mu, dist, [c])

        inside_mask = (dist >= 300.0) & (dist <= 600.0)
        # Each point in the corner zone should have been individually corrected
        for i in np.where(inside_mask)[0]:
            expected = effective_mu_with_banking(float(mu[i]), 3.0)
            assert result[i] == pytest.approx(expected, rel=1e-10)

    def test_empty_arrays(self) -> None:
        """Empty arrays should return an empty array."""
        mu = np.array([])
        dist = np.array([])
        result = apply_banking_to_mu_array(mu, dist, [])
        assert len(result) == 0

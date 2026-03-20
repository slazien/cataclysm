"""Tests for the Fiala brush tire force model."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cataclysm.tire_brush import (
    BrushTireParams,
    compute_combined_forces,
    compute_gg_envelope,
    compute_lateral_force,
)

# ---------------------------------------------------------------------------
# Shared fixture — typical sport tire on a ~1400 kg car (single corner load).
# ---------------------------------------------------------------------------

TYPICAL_PARAMS = BrushTireParams(
    mu=1.1,
    cornering_stiffness=60_000.0,  # N/rad
    normal_load_n=3_500.0,  # ~350 kg per corner
)


class TestPureLateral:
    """Tests for compute_lateral_force (pure cornering)."""

    def test_zero_slip_zero_force(self) -> None:
        fy = compute_lateral_force(0.0, TYPICAL_PARAMS)
        assert fy == 0.0

    def test_linear_region(self) -> None:
        """At very small slip angles the force should be nearly C_alpha * alpha."""
        alpha = math.radians(0.5)  # 0.5 deg — well within linear range
        fy = compute_lateral_force(alpha, TYPICAL_PARAMS)

        # In the linear region Fy ≈ C_alpha * tan(alpha) ≈ C_alpha * alpha.
        linear_estimate = TYPICAL_PARAMS.cornering_stiffness * math.tan(alpha)
        # Allow 5 % tolerance — cubic term is small but non-zero.
        assert fy == pytest.approx(linear_estimate, rel=0.05)
        # Force must be positive for positive slip angle.
        assert fy > 0.0

    def test_saturation(self) -> None:
        """At very large slip angle, force saturates at mu * Fz."""
        alpha = math.radians(30.0)  # far beyond critical slip angle
        fy = compute_lateral_force(alpha, TYPICAL_PARAMS)
        mu_fz = TYPICAL_PARAMS.mu * TYPICAL_PARAMS.normal_load_n
        assert fy == pytest.approx(mu_fz, rel=1e-9)

    def test_peak_force_near_mu_fz(self) -> None:
        """Maximum lateral force should not exceed mu * Fz."""
        mu_fz = TYPICAL_PARAMS.mu * TYPICAL_PARAMS.normal_load_n
        # Sweep slip angles from 0 to 20 deg.
        peak = 0.0
        for deg in range(0, 201):
            alpha = math.radians(deg / 10.0)
            fy = compute_lateral_force(alpha, TYPICAL_PARAMS)
            peak = max(peak, fy)
        # Peak should be at most mu * Fz (within floating-point tolerance).
        assert peak <= mu_fz * (1.0 + 1e-9)
        # And should be very close to mu * Fz.
        assert peak == pytest.approx(mu_fz, rel=0.01)

    def test_negative_slip_angle(self) -> None:
        """Negative slip angle produces negative lateral force."""
        alpha = math.radians(-5.0)
        fy = compute_lateral_force(alpha, TYPICAL_PARAMS)
        assert fy < 0.0
        # Magnitude should match positive slip.
        fy_pos = compute_lateral_force(math.radians(5.0), TYPICAL_PARAMS)
        assert abs(fy) == pytest.approx(fy_pos, rel=1e-9)

    def test_zero_load_returns_zero(self) -> None:
        params = BrushTireParams(mu=1.1, cornering_stiffness=60_000.0, normal_load_n=0.0)
        assert compute_lateral_force(math.radians(5.0), params) == 0.0

    def test_zero_mu_returns_zero(self) -> None:
        params = BrushTireParams(mu=0.0, cornering_stiffness=60_000.0, normal_load_n=3500.0)
        assert compute_lateral_force(math.radians(5.0), params) == 0.0

    def test_negative_load_returns_zero(self) -> None:
        params = BrushTireParams(mu=1.1, cornering_stiffness=60_000.0, normal_load_n=-100.0)
        assert compute_lateral_force(math.radians(5.0), params) == 0.0

    def test_load_sensitivity_natural(self) -> None:
        """Heavier load → more absolute force but lower effective mu.

        The brush model at saturation gives Fy = mu * Fz, so absolute force
        scales linearly. But with the same cornering stiffness, the critical
        slip angle increases, meaning the tire transitions later — a natural
        load sensitivity effect (softer initial response per unit load).
        """
        light = BrushTireParams(mu=1.1, cornering_stiffness=60_000.0, normal_load_n=2_500.0)
        heavy = BrushTireParams(mu=1.1, cornering_stiffness=60_000.0, normal_load_n=4_500.0)

        alpha = math.radians(5.0)
        fy_light = compute_lateral_force(alpha, light)
        fy_heavy = compute_lateral_force(alpha, heavy)

        # Heavier tire produces more absolute force.
        assert abs(fy_heavy) > abs(fy_light)

        # But effective mu (Fy / Fz) is lower for heavy tire — classic load sensitivity.
        mu_eff_light = abs(fy_light) / light.normal_load_n
        mu_eff_heavy = abs(fy_heavy) / heavy.normal_load_n
        assert mu_eff_light > mu_eff_heavy


class TestCombinedForces:
    """Tests for compute_combined_forces (lateral + longitudinal coupling)."""

    def test_combined_zero_longitudinal(self) -> None:
        """Zero slip ratio → combined lateral equals pure lateral."""
        alpha = math.radians(5.0)
        fy_pure = compute_lateral_force(alpha, TYPICAL_PARAMS)
        fx, fy = compute_combined_forces(alpha, 0.0, TYPICAL_PARAMS)
        assert fx == 0.0
        assert fy == pytest.approx(fy_pure, rel=1e-9)

    def test_combined_reduces_lateral(self) -> None:
        """Adding longitudinal slip reduces available lateral force."""
        alpha = math.radians(8.0)  # well into the non-linear region
        fy_pure = compute_lateral_force(alpha, TYPICAL_PARAMS)

        # Add braking slip — should reduce lateral force.
        _fx, fy_combined = compute_combined_forces(alpha, -0.10, TYPICAL_PARAMS)
        assert abs(fy_combined) < abs(fy_pure)

    def test_combined_friction_circle_limit(self) -> None:
        """Resultant force should never exceed mu * Fz."""
        mu_fz = TYPICAL_PARAMS.mu * TYPICAL_PARAMS.normal_load_n
        for alpha_deg in range(-15, 16):
            for sr in [-0.15, -0.05, 0.0, 0.05, 0.15]:
                fx, fy = compute_combined_forces(math.radians(alpha_deg), sr, TYPICAL_PARAMS)
                resultant = math.sqrt(fx * fx + fy * fy)
                assert resultant <= mu_fz * (1.0 + 1e-9)

    def test_combined_zero_load(self) -> None:
        params = BrushTireParams(mu=1.1, cornering_stiffness=60_000.0, normal_load_n=0.0)
        fx, fy = compute_combined_forces(math.radians(5.0), 0.1, params)
        assert fx == 0.0
        assert fy == 0.0


class TestGGEnvelope:
    """Tests for compute_gg_envelope."""

    def test_gg_envelope_shape(self) -> None:
        """Envelope should be roughly circular for an isotropic tire."""
        lat_g, lon_g = compute_gg_envelope(TYPICAL_PARAMS, n_points=72)

        assert len(lat_g) == 72
        assert len(lon_g) == 72

        # Compute radii — should all be approximately equal (circular).
        radii = np.sqrt(lat_g**2 + lon_g**2)
        assert np.std(radii) / np.mean(radii) < 0.05  # < 5 % coefficient of variation

    def test_gg_envelope_magnitude(self) -> None:
        """Envelope radius should be approximately mu in g units."""
        lat_g, lon_g = compute_gg_envelope(TYPICAL_PARAMS, n_points=36)
        radii = np.sqrt(lat_g**2 + lon_g**2)
        # Radius ≈ mu (for single-tire mass = Fz/g).
        assert np.mean(radii) == pytest.approx(TYPICAL_PARAMS.mu, rel=0.01)

    def test_gg_envelope_zero_load(self) -> None:
        params = BrushTireParams(mu=1.1, cornering_stiffness=60_000.0, normal_load_n=0.0)
        lat_g, lon_g = compute_gg_envelope(params)
        assert np.all(lat_g == 0.0)
        assert np.all(lon_g == 0.0)

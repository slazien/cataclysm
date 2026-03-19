"""Tests for friction ellipse (asymmetric braking/cornering grip)."""

from __future__ import annotations

import numpy as np

from cataclysm.curvature import CurvatureResult
from cataclysm.velocity_profile import (
    VehicleParams,
    _available_accel,
    compute_optimal_profile,
)


def _make_curvature_result(curvature: np.ndarray, step_m: float = 0.7) -> CurvatureResult:
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


def test_ellipse_braking_exceeds_cornering() -> None:
    """With max_decel_g > max_lateral_g, max braking G should exceed max lateral G."""
    params = VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.15,
        max_lateral_g=1.0,
        braking_mu_ratio=1.15,
    )
    decel = _available_accel(30.0, 0.0, params, "decel")
    assert abs(decel - 1.15) < 0.01, f"Expected ~1.15G decel, got {decel}"


def test_ellipse_combined_reduces_braking() -> None:
    """Under combined braking+cornering, available braking should drop."""
    params = VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.15,
        max_lateral_g=1.0,
        braking_mu_ratio=1.15,
    )
    full_decel = _available_accel(30.0, 0.0, params, "decel")
    partial_decel = _available_accel(30.0, 0.5, params, "decel")
    assert partial_decel < full_decel, "Combined grip should reduce braking"
    assert partial_decel > 0, "Should still have some braking budget"


def test_circle_backward_compatible() -> None:
    """With braking_mu_ratio=1.0 (default), behavior matches friction circle."""
    params_circle = VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.0,
        max_lateral_g=1.0,
        braking_mu_ratio=1.0,
    )
    params_default = VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.0,
        max_lateral_g=1.0,
    )
    for lat in [0.0, 0.3, 0.7, 0.99]:
        d1 = _available_accel(30.0, lat, params_circle, "decel")
        d2 = _available_accel(30.0, lat, params_default, "decel")
        assert abs(d1 - d2) < 1e-6, f"Should match at lat={lat}"


def test_ellipse_makes_braking_zones_shorter() -> None:
    """With friction ellipse, brake zones should be shorter (brake later/harder)."""
    n = 2000
    curvature = np.zeros(n)
    curvature[800:1200] = 0.02  # tight corner mid-track
    cr = _make_curvature_result(curvature)

    base = VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.0,
        max_lateral_g=1.0,
        mass_kg=1500,
        wheel_power_w=300_000,
    )
    ellipse = VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.15,
        max_lateral_g=1.0,
        braking_mu_ratio=1.15,
        mass_kg=1500,
        wheel_power_w=300_000,
    )

    p_base = compute_optimal_profile(cr, base, closed_circuit=False)
    p_ellipse = compute_optimal_profile(cr, ellipse, closed_circuit=False)

    # Ellipse car should be faster (shorter braking, same cornering)
    assert p_ellipse.lap_time_s < p_base.lap_time_s, (
        f"Ellipse should be faster: {p_ellipse.lap_time_s:.3f} vs {p_base.lap_time_s:.3f}"
    )

"""Fiala brush tire model for first-principles tire force computation.

Computes lateral and combined (lateral + longitudinal) tire forces from
3 core parameters: peak friction coefficient, cornering stiffness, and
normal load. Provides progressive saturation past peak slip angle —
something a parameterized friction ellipse cannot capture.

Reference: Pacejka, "Tire and Vehicle Dynamics", Ch. 3 (Brush Model).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass
class BrushTireParams:
    """Parameters for the Fiala brush tire model.

    Attributes:
        mu: Peak friction coefficient (dimensionless).
        cornering_stiffness: Cornering stiffness C_alpha (N/rad) at reference load.
        normal_load_n: Vertical tire load Fz (N).
        sliding_mu_ratio: Ratio of sliding friction to peak friction (default 0.85).
    """

    mu: float
    cornering_stiffness: float
    normal_load_n: float
    sliding_mu_ratio: float = 0.85


def compute_lateral_force(slip_angle_rad: float, params: BrushTireParams) -> float:
    """Compute pure lateral (cornering) force using the Fiala brush model.

    Below the critical slip angle the force follows the cubic brush formula:
        Fy = C_alpha * tan(alpha) * (1 - x + x²/3)
    where x = C_alpha * |tan(alpha)| / (3 * mu * Fz).

    At or above the critical slip angle the tire is fully sliding:
        Fy = mu * Fz

    Args:
        slip_angle_rad: Tire slip angle in radians (signed).
        params: Brush tire parameters.

    Returns:
        Lateral force in Newtons. Sign matches ``slip_angle_rad``.
        Returns 0.0 for degenerate inputs (Fz <= 0, C_alpha <= 0, mu <= 0).
    """
    mu = params.mu
    c_alpha = params.cornering_stiffness
    fz = params.normal_load_n

    # Guard against degenerate inputs.
    if fz <= 0.0 or c_alpha <= 0.0 or mu <= 0.0:
        return 0.0

    tan_alpha = math.tan(slip_angle_rad)
    abs_tan = abs(tan_alpha)
    sign = 1.0 if slip_angle_rad >= 0.0 else -1.0

    # Critical slip angle: alpha_crit = atan(3 * mu * Fz / C_alpha).
    # We compare |tan(alpha)| against the threshold directly to avoid atan/tan round-trip.
    tan_crit = 3.0 * mu * fz / c_alpha

    if abs_tan >= tan_crit:
        # Full sliding — force saturates at mu * Fz.
        return sign * mu * fz

    # Brush cubic region.
    x = c_alpha * abs_tan / (3.0 * mu * fz)
    fy_mag = c_alpha * abs_tan * (1.0 - x + x * x / 3.0)
    return sign * fy_mag


def compute_combined_forces(
    slip_angle_rad: float,
    slip_ratio: float,
    params: BrushTireParams,
) -> tuple[float, float]:
    """Compute combined lateral and longitudinal tire forces.

    Longitudinal stiffness is estimated as 1.2× the cornering stiffness
    (typical for radial passenger / sport tires). Forces exceeding the
    friction circle are scaled proportionally.

    Args:
        slip_angle_rad: Tire slip angle in radians (signed).
        slip_ratio: Longitudinal slip ratio (signed, dimensionless).
        params: Brush tire parameters.

    Returns:
        Tuple ``(fx, fy)`` — longitudinal and lateral forces in Newtons.
    """
    mu = params.mu
    fz = params.normal_load_n

    if fz <= 0.0 or mu <= 0.0:
        return 0.0, 0.0

    # Pure lateral force.
    fy = compute_lateral_force(slip_angle_rad, params)

    # Longitudinal force — linear stiffness estimate.
    cx = params.cornering_stiffness * 1.2
    fx = cx * slip_ratio

    # Friction circle coupling: scale if resultant exceeds mu * Fz.
    resultant = math.sqrt(fx * fx + fy * fy)
    limit = mu * fz
    if resultant > limit:
        scale = limit / resultant
        fx *= scale
        fy *= scale

    return fx, fy


def compute_gg_envelope(
    params: BrushTireParams,
    n_points: int = 36,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Generate the GG diagram boundary envelope for a tire.

    Sweeps 360° around the friction circle, computing the maximum
    lateral and longitudinal force at each heading angle.

    Args:
        params: Brush tire parameters.
        n_points: Number of sample points around the envelope.

    Returns:
        Tuple ``(lat_g, lon_g)`` — arrays of lateral and longitudinal
        acceleration in *g* units for plotting.
    """
    mu = params.mu
    fz = params.normal_load_n

    if fz <= 0.0 or mu <= 0.0:
        return np.zeros(n_points), np.zeros(n_points)

    g = 9.81
    limit = mu * fz
    angles = np.linspace(0.0, 2.0 * np.pi, n_points, endpoint=False)

    lat_g = limit * np.cos(angles) / (fz / mu * g / mu)
    lon_g = limit * np.sin(angles) / (fz / mu * g / mu)

    # Simplify: Fx_max = mu*Fz at each heading, convert to g.
    # vehicle_mass = Fz / g  (single tire approximation).
    mass_approx = fz / g
    lat_g = limit * np.cos(angles) / (mass_approx * g)
    lon_g = limit * np.sin(angles) / (mass_approx * g)

    return lat_g, lon_g

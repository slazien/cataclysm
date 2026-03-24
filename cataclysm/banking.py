"""Banking / camber corrections for effective lateral grip.

Banking (positive camber toward corner center) increases available lateral
grip by adding a gravity component that assists cornering.  Off-camber
(negative banking) reduces grip.

Physics
-------
For a car on a banked surface at angle theta with friction coefficient mu,
the effective friction coefficient is:

    mu_eff = (mu + tan(theta)) / (1 - mu * tan(theta))

This comes from resolving forces on the banked surface: gravity provides a
centripetal component (g * sin(theta)) while the normal force increases
(g * cos(theta)), and friction acts on the resultant normal force.

Sign convention:
    - Positive banking_deg = banked toward corner center (more grip)
    - Negative banking_deg = off-camber (less grip)
    - 0 = flat

Typical values (mu=1.0):
    - 3 deg banking: ~+10.9% grip
    - 5 deg banking: ~+19.2% grip
    - 10 deg banking: ~+44.2% grip
    - NASCAR oval banking: 24-33 deg
"""

from __future__ import annotations

import math

import numpy as np

from cataclysm.corners import Corner

# Clamp bounds for effective mu to prevent extreme or unphysical values.
# 0.1 prevents near-zero grip; 5.0 prevents singularities near arctan(1/mu).
MU_CLAMP_MIN: float = 0.1
MU_CLAMP_MAX: float = 5.0


def effective_mu_with_banking(
    mu: float,
    banking_deg: float,
) -> float:
    """Compute effective friction coefficient with banking.

    Parameters
    ----------
    mu:
        Base friction coefficient (typically 0.8-1.5 for race tires).
    banking_deg:
        Banking angle in degrees.  Positive = banked toward corner center
        (more grip).  Negative = off-camber (less grip).

    Returns
    -------
    Effective friction coefficient, clamped to [MU_CLAMP_MIN, MU_CLAMP_MAX].

    Examples
    --------
    >>> effective_mu_with_banking(1.0, 0.0)
    1.0
    >>> effective_mu_with_banking(1.0, 5.0)  # ~1.095
    1.0951...
    """
    if banking_deg == 0.0:
        return mu

    tan_theta = math.tan(math.radians(banking_deg))
    denominator = 1.0 - mu * tan_theta

    # Avoid division by zero / near-singularity
    if abs(denominator) < 1e-10:
        return MU_CLAMP_MAX if tan_theta > 0 else MU_CLAMP_MIN

    mu_eff = (mu + tan_theta) / denominator
    return max(MU_CLAMP_MIN, min(MU_CLAMP_MAX, mu_eff))


def apply_banking_to_mu_array(
    mu_array: np.ndarray,
    distance_m: np.ndarray,
    corners: list[Corner],
) -> np.ndarray:
    """Apply per-corner banking corrections to the mu array.

    For each corner that has ``banking_deg`` set (not None), adjust mu
    in that corner's distance zone using :func:`effective_mu_with_banking`.

    Parameters
    ----------
    mu_array:
        Base friction coefficient at each distance point.
    distance_m:
        Distance array corresponding to mu_array (monotonically increasing).
    corners:
        List of corners, each optionally carrying a ``banking_deg`` value.

    Returns
    -------
    A copy of *mu_array* with banking corrections applied.
    Non-corner zones and corners without banking data are unchanged.
    """
    result = mu_array.copy()

    if len(result) == 0:
        return result

    for corner in corners:
        if corner.banking_deg is None:
            continue

        # Find indices within this corner's distance zone
        mask = (distance_m >= corner.entry_distance_m) & (distance_m <= corner.exit_distance_m)
        indices = np.where(mask)[0]

        for idx in indices:
            result[idx] = effective_mu_with_banking(
                float(mu_array[idx]),
                corner.banking_deg,
            )

    return result


def detect_banking_from_telemetry(
    lateral_g: np.ndarray,
    yaw_rate_dps: np.ndarray,
    speed_mps: np.ndarray,
    distance_m: np.ndarray,
    *,
    min_speed_mps: float = 8.0,
    min_coverage: float = 0.8,
) -> np.ndarray | None:
    """Detect track banking from discrepancy between accelerometer and gyroscope.

    When a_y (lateral_g * g) exceeds the centripetal acceleration implied by
    yaw rate (v * psi_dot), the excess comes from gravity on a banked surface:

        banking_rad = arcsin((a_y - v * psi_dot) / g)

    Parameters
    ----------
    lateral_g:
        Lateral acceleration in G (from accelerometer).
    yaw_rate_dps:
        Yaw rate in degrees/second (from gyroscope).
    speed_mps:
        Vehicle speed in m/s.
    distance_m:
        Distance array corresponding to the other arrays.
    min_speed_mps:
        Below this speed both signals are too noisy; banking is zeroed.
    min_coverage:
        Minimum fraction of finite yaw_rate + lateral_g samples required.

    Returns
    -------
    Array of banking in degrees (positive = banked into corner),
    or None if insufficient sensor data.
    """
    valid_yaw = np.isfinite(yaw_rate_dps)
    valid_lat = np.isfinite(lateral_g)
    valid = valid_yaw & valid_lat
    if valid.mean() < min_coverage:
        return None

    g = 9.81

    # Convert yaw rate to rad/s
    yaw_rad_s = np.radians(yaw_rate_dps)

    # Centripetal acceleration from yaw rate: a_centripetal = v * |psi_dot|
    a_centripetal = speed_mps * np.abs(yaw_rad_s)

    # Measured lateral acceleration (absolute value, in m/s^2)
    a_measured = np.abs(lateral_g) * g

    # Excess acceleration from banking
    a_excess = a_measured - a_centripetal

    # banking = arcsin(a_excess / g), clamped to [-1, 1] for arcsin domain
    sin_banking = np.clip(a_excess / g, -1.0, 1.0)
    banking_rad = np.arcsin(sin_banking)
    banking_deg_raw = np.degrees(banking_rad)

    # Zero out low-speed zones where both signals are noisy.
    # Linear ramp from 0 at min_speed_mps to 1 at 2*min_speed_mps.
    speed_weight = np.clip((speed_mps - min_speed_mps) / min_speed_mps, 0.0, 1.0)
    banking_deg_arr = banking_deg_raw * speed_weight

    # Clamp to physically reasonable range (-15 deg to 35 deg)
    banking_deg_arr = np.clip(banking_deg_arr, -15.0, 35.0)

    # Fill NaN from invalid samples with 0
    banking_deg_arr = np.where(valid, banking_deg_arr, 0.0)

    return banking_deg_arr

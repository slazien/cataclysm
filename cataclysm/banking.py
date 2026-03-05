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

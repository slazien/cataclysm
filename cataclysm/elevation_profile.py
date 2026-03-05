"""Full-track gradient and vertical curvature from GPS altitude.

Computes two arrays consumed by ``cataclysm.velocity_profile``:

1. **gradient_sin** — ``sin(theta)`` at every track point.  Used in the
   longitudinal force balance (uphill slows acceleration, downhill assists).

2. **vertical_curvature** — ``d²z/ds²`` (1/m) at every track point.  Used
   to correct the normal force for compressions and crests:

       N = m·(g·cos(θ) + v²·κ_v)

   Positive κ_v = compression (concave road, bottom of dip) → more grip.
   Negative κ_v = crest (convex road, top of hill) → less grip, car goes light.

This is distinct from ``cataclysm.elevation`` which computes per-*corner*
elevation metrics for coaching.
"""

from __future__ import annotations

import numpy as np

# Smoothing window (meters of track distance) to reduce GPS altitude noise.
# GPS altitude is noisier than horizontal position (~3-5 m raw), so we need
# aggressive smoothing to avoid injecting fictitious gradients.
_ALTITUDE_SMOOTH_WINDOW_M = 50.0

# Vertical curvature requires a second derivative, which amplifies noise
# quadratically.  We use a wider window than for gradient.
_VERTICAL_CURVATURE_SMOOTH_WINDOW_M = 120.0

# Physical clamp for vertical curvature (1/m).  Typical race track values:
#   - Gentle crest/dip: ~0.001
#   - Barber corkscrew compression: ~0.005-0.01
#   - Extreme roller-coaster: ~0.02
# We clamp at 0.05 to prevent GPS noise artefacts.
_VERTICAL_CURVATURE_CLAMP = 0.05


def _prepare_altitude(
    altitude_m: np.ndarray,
) -> np.ndarray | None:
    """NaN-fill and copy raw altitude.  Returns None if all-NaN."""
    alt = altitude_m.astype(np.float64, copy=True)
    mask = np.isnan(alt)
    if mask.all():
        return None
    if mask.any():
        last_valid = np.nan
        for i in range(len(alt)):
            if mask[i]:
                alt[i] = last_valid
            else:
                last_valid = alt[i]
        first_valid = alt[~np.isnan(alt)][0]
        alt[np.isnan(alt)] = first_valid
    return alt


def _smooth_array(
    arr: np.ndarray,
    step_m: float,
    smooth_window_m: float,
) -> np.ndarray:
    """Apply symmetric rolling-average smoothing with edge-padding."""
    n = len(arr)
    window_pts = max(1, int(smooth_window_m / step_m))
    if window_pts % 2 == 0:
        window_pts += 1
    half_w = window_pts // 2
    padded = np.pad(arr, half_w, mode="edge")
    kernel = np.ones(window_pts) / window_pts
    return np.convolve(padded, kernel, mode="valid")[:n]


def compute_gradient_array(
    altitude_m: np.ndarray,
    distance_m: np.ndarray,
    smooth_window_m: float = _ALTITUDE_SMOOTH_WINDOW_M,
) -> np.ndarray:
    """Compute sin(theta) at each track point from smoothed altitude.

    Returns array of sin(theta) values.  Positive = uphill, negative = downhill.
    Smoothing prevents GPS altitude noise from creating unrealistic gradients.

    Parameters
    ----------
    altitude_m
        Raw GPS altitude array (meters).  NaN values are forward-filled then
        back-filled before smoothing.
    distance_m
        Cumulative distance array (meters), same length as *altitude_m*.
    smooth_window_m
        Rolling-average window width in meters of track distance.

    Returns
    -------
    np.ndarray
        Array of sin(theta) values, same length as input.
    """
    n = len(altitude_m)
    if n < 2:
        return np.zeros(n, dtype=np.float64)

    alt = _prepare_altitude(altitude_m)
    if alt is None:
        return np.zeros(n, dtype=np.float64)

    step_m = float(distance_m[1] - distance_m[0]) if n >= 2 else 1.0
    smoothed = _smooth_array(alt, step_m, smooth_window_m)

    gradient = np.gradient(smoothed, distance_m)
    sin_theta: np.ndarray = gradient / np.sqrt(1.0 + gradient**2)

    return sin_theta


def compute_vertical_curvature(
    altitude_m: np.ndarray,
    distance_m: np.ndarray,
    smooth_window_m: float = _VERTICAL_CURVATURE_SMOOTH_WINDOW_M,
) -> np.ndarray:
    """Compute vertical curvature κ_v = d²z/ds² at each track point.

    Positive = compression (concave, bottom of dip → more grip).
    Negative = crest (convex, top of hill → less grip).

    The vertical curvature modifies the effective normal force:

        N_eff = m·(g·cos(θ) + v²·κ_v)

    so compressions increase available lateral grip and crests reduce it.

    Parameters
    ----------
    altitude_m
        Raw GPS altitude array (meters).
    distance_m
        Cumulative distance array (meters), same length as *altitude_m*.
    smooth_window_m
        Rolling-average window width in meters.  Defaults to 120 m —
        heavier than gradient smoothing because the second derivative
        amplifies noise quadratically.

    Returns
    -------
    np.ndarray
        Vertical curvature in 1/m, clamped to [-0.05, 0.05].
    """
    n = len(altitude_m)
    if n < 3:
        return np.zeros(n, dtype=np.float64)

    alt = _prepare_altitude(altitude_m)
    if alt is None:
        return np.zeros(n, dtype=np.float64)

    step_m = float(distance_m[1] - distance_m[0]) if n >= 2 else 1.0
    smoothed = _smooth_array(alt, step_m, smooth_window_m)

    # Second derivative of altitude w.r.t. distance = vertical curvature.
    # d²z/ds² > 0 when road curves upward (compression).
    kappa_v: np.ndarray = np.gradient(np.gradient(smoothed, distance_m), distance_m)

    np.clip(kappa_v, -_VERTICAL_CURVATURE_CLAMP, _VERTICAL_CURVATURE_CLAMP, out=kappa_v)

    return kappa_v

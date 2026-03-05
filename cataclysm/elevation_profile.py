"""Full-track gradient computation from GPS altitude for the velocity solver.

Computes sin(theta) at every track point from smoothed GPS altitude, producing
a gradient array that the forward-backward velocity solver uses to account for
elevation changes in the longitudinal force balance.

This is distinct from ``cataclysm.elevation`` which computes per-*corner*
elevation metrics for coaching.  This module produces a full-track gradient
*array* consumed by ``cataclysm.velocity_profile``.
"""

from __future__ import annotations

import numpy as np

# Smoothing window (meters of track distance) to reduce GPS altitude noise.
# GPS altitude is noisier than horizontal position (~3-5 m raw), so we need
# aggressive smoothing to avoid injecting fictitious gradients.
_ALTITUDE_SMOOTH_WINDOW_M = 50.0


def compute_gradient_array(
    altitude_m: np.ndarray,
    distance_m: np.ndarray,
    smooth_window_m: float = _ALTITUDE_SMOOTH_WINDOW_M,
) -> np.ndarray:
    """Compute sin(theta) at each track point from smoothed altitude.

    Returns array of sin(theta) values.  Positive = uphill, negative = downhill.
    Smoothing prevents GPS altitude noise from creating unrealistic gradients.

    Steps
    -----
    1. Smooth altitude with rolling average (window = *smooth_window_m*).
    2. Compute gradient = d(altitude)/d(distance) via ``np.gradient``.
    3. Convert to sin(theta) = gradient / sqrt(1 + gradient**2).
       For small grades this is approximately equal to the gradient itself.

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

    # --- 0. Handle NaN: forward-fill then back-fill --------------------------
    alt = altitude_m.astype(np.float64, copy=True)
    mask = np.isnan(alt)
    if mask.all():
        return np.zeros(n, dtype=np.float64)
    if mask.any():
        # Forward fill
        last_valid = np.nan
        for i in range(n):
            if mask[i]:
                alt[i] = last_valid
            else:
                last_valid = alt[i]
        # Back fill any remaining leading NaNs
        first_valid = alt[~np.isnan(alt)][0]
        alt[np.isnan(alt)] = first_valid

    # --- 1. Smooth altitude with rolling average ------------------------------
    step_m = float(distance_m[1] - distance_m[0]) if n >= 2 else 1.0
    window_pts = max(1, int(smooth_window_m / step_m))
    # Ensure odd window for symmetric convolution
    if window_pts % 2 == 0:
        window_pts += 1
    # Pad with edge values to avoid zero-padding artefacts at boundaries
    half_w = window_pts // 2
    padded = np.pad(alt, half_w, mode="edge")
    kernel = np.ones(window_pts) / window_pts
    smoothed = np.convolve(padded, kernel, mode="valid")

    # --- 2. Compute gradient = d(altitude) / d(distance) ----------------------
    gradient = np.gradient(smoothed, distance_m)

    # --- 3. Convert to sin(theta) = gradient / sqrt(1 + gradient^2) -----------
    sin_theta = gradient / np.sqrt(1.0 + gradient**2)

    return sin_theta

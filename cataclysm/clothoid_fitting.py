"""Piecewise clothoid (Euler spiral) curvature fitting.

Fits piecewise-linear curvature to a GPS track, modelling the track as a
sequence of clothoid segments.  A clothoid has curvature that varies linearly
with arc length: ``kappa(s) = kappa0 + (kappa1 - kappa0) * s / L``.  Real
racing tracks are designed with clothoid transitions between straights and
constant-radius arcs, making this physically correct.

The main entry point is :func:`compute_clothoid_curvature`, which takes XY
coordinates and a distance array and returns a curvature array of the same
length.  The helper :func:`fit_clothoid_segment` fits a single clothoid
between two posed endpoints (position + heading).

Implementation approach:
    1. Compute heading at each point via ``atan2(dy, dx)`` with unwrapping.
    2. Identify *knot points* (segment boundaries) where the rate of heading
       change shifts — detected via sign changes in d^2(theta)/ds^2.
    3. Between consecutive knots, fit a linear curvature model
       ``kappa(s) = a + b * s`` using least-squares on heading data.  Since
       heading is the integral of curvature, a linear curvature profile
       produces a quadratic heading profile:
       ``theta(s) = theta0 + a * s + b * s^2 / 2``.
    4. Evaluate the piecewise-linear curvature at every distance sample.

References:
    Bertolazzi, E. & Frego, M. (2013). Fast and accurate G1 fitting of
    clothoid curves.  *arXiv:1305.6644*.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import savgol_filter

# --- Module constants ---

# Minimum number of points in a segment for a reliable linear fit.
MIN_SEGMENT_POINTS: int = 5

# Smoothing window for heading computation (Savitzky-Golay filter).
# Odd window size, polyorder=3.  Applied to raw heading to reduce
# GPS noise before knot detection and segment fitting.
HEADING_SMOOTH_WINDOW: int = 15

# Smoothing window for the second derivative of heading, used in
# knot detection.  Larger value = fewer knots = longer segments.
KNOT_SMOOTH_WINDOW: int = 31

# Minimum spacing (in samples) between knot points.  Prevents
# over-segmentation in noisy data.
MIN_KNOT_SPACING: int = 20

# Post-fit curvature smoothing window (uniform filter).  Applied
# to the final piecewise-linear curvature to reduce discontinuities
# at segment boundaries.
OUTPUT_SMOOTH_WINDOW: int = 11


def fit_clothoid_segment(
    x0: float,
    y0: float,
    theta0: float,
    x1: float,
    y1: float,
    theta1: float,
) -> tuple[float, float, float]:
    """Fit a single clothoid segment between two posed endpoints.

    Given start pose ``(x0, y0, theta0)`` and end pose ``(x1, y1, theta1)``,
    compute the clothoid parameters that connect them.

    The clothoid has curvature ``kappa(s) = kappa0 + (kappa1 - kappa0) * s / L``
    where ``L`` is the arc length.  For a clothoid:

    - Total heading change: ``delta_theta = (kappa0 + kappa1) * L / 2``
    - The chord vector from start to end constrains L.

    Parameters
    ----------
    x0, y0 : float
        Start position (metres).
    theta0 : float
        Start heading (radians, math convention: 0=East, CCW positive).
    x1, y1 : float
        End position (metres).
    theta1 : float
        End heading (radians).

    Returns
    -------
    tuple[float, float, float]
        ``(kappa0, kappa1, arc_length)`` — curvature at entry, curvature at
        exit, and arc length.  Curvature varies linearly between them.
    """
    dx = x1 - x0
    dy = y1 - y0
    chord = np.hypot(dx, dy)

    if chord < 1e-12:
        return 0.0, 0.0, 0.0

    # Heading change
    delta_theta = _angle_diff(theta1, theta0)

    # Arc length estimate: for small curvatures, arc ~ chord.
    # Better estimate uses the heading-chord angle relationship.
    # For a clothoid/circular arc, L ≈ chord / sinc(delta_theta / 2)
    # where sinc(x) = sin(x)/x.
    half_dtheta = delta_theta / 2.0
    arc_length = chord * half_dtheta / np.sin(half_dtheta) if abs(half_dtheta) > 1e-8 else chord

    arc_length = abs(arc_length)

    if arc_length < 1e-12:
        return 0.0, 0.0, 0.0

    # For a clothoid: delta_theta = (kappa0 + kappa1) * L / 2
    # Mean curvature:
    kappa_mean = delta_theta / arc_length

    # To determine kappa0 vs kappa1, we use the lateral offset.
    # The chord angle (direction from start to end) vs start heading
    # gives information about how curvature is distributed.
    chord_angle = np.arctan2(dy, dx)
    alpha = _angle_diff(chord_angle, theta0)

    # For a clothoid, the chord-heading angle relates to curvature distribution:
    # alpha ≈ (2*kappa0 + kappa1) * L / 6  (first-order approximation)
    # Combined with kappa_mean = (kappa0 + kappa1) / 2:
    #   kappa0 + kappa1 = 2 * kappa_mean
    #   2*kappa0 + kappa1 = 6 * alpha / L
    # Solving:
    #   kappa0 = 6 * alpha / L - 2 * kappa_mean
    #   kappa1 = 2 * kappa_mean - kappa0 = 4 * kappa_mean - 6 * alpha / L
    if arc_length > 1e-8:
        kappa0 = 6.0 * alpha / arc_length - 2.0 * kappa_mean
        kappa1 = 4.0 * kappa_mean - 6.0 * alpha / arc_length
    else:
        kappa0 = kappa_mean
        kappa1 = kappa_mean

    return kappa0, kappa1, arc_length


def compute_clothoid_curvature(
    x: np.ndarray,
    y: np.ndarray,
    distance_m: np.ndarray,
) -> np.ndarray:
    """Compute piecewise-clothoid curvature for a track.

    Fits piecewise-linear curvature by:

    1. Computing heading ``theta(s) = atan2(dy/ds, dx/ds)`` at each point.
    2. Identifying segment boundaries (knots) where ``d^2(theta)/ds^2``
       changes sign.
    3. Fitting a linear curvature model within each segment using
       least-squares on the heading profile.
    4. Evaluating piecewise-linear curvature at all distance points.

    Parameters
    ----------
    x : np.ndarray
        X coordinates (metres), shape ``(N,)``.
    y : np.ndarray
        Y coordinates (metres), shape ``(N,)``.
    distance_m : np.ndarray
        Cumulative distance (metres), shape ``(N,)``.

    Returns
    -------
    np.ndarray
        Signed curvature array, shape ``(N,)``, in 1/m.  Positive curvature
        means the track curves left (counter-clockwise).
    """
    n = len(x)

    if n < 2:
        return np.zeros(n, dtype=np.float64)

    if n < MIN_SEGMENT_POINTS:
        # Too few points for full pipeline — use simple difference
        return _simple_curvature(x, y, distance_m)

    # Step 1: Compute and smooth heading
    heading = _compute_heading(x, y, distance_m)

    # Step 2: Identify knot points
    knots = _find_knots(heading, distance_m)

    # Step 3 & 4: Fit linear curvature in each segment and interpolate
    curvature = _fit_segments(heading, distance_m, knots)

    # Apply light smoothing to reduce boundary discontinuities
    if n >= OUTPUT_SMOOTH_WINDOW:
        curvature = uniform_filter1d(curvature, size=OUTPUT_SMOOTH_WINDOW, mode="nearest")

    return curvature


def _angle_diff(a: float, b: float) -> float:
    """Compute the signed angular difference ``a - b``, wrapped to ``[-pi, pi]``.

    Parameters
    ----------
    a, b : float
        Angles in radians.

    Returns
    -------
    float
        ``a - b`` wrapped to ``[-pi, pi]``.
    """
    d = a - b
    return float((d + np.pi) % (2 * np.pi) - np.pi)


def _compute_heading(
    x: np.ndarray,
    y: np.ndarray,
    distance_m: np.ndarray,
) -> np.ndarray:
    """Compute smoothed heading from XY coordinates.

    Uses central differences for dx/ds, dy/ds, then ``atan2(dy, dx)``
    with unwrapping to produce a continuous heading profile.  A
    Savitzky-Golay filter is applied if enough points are available.

    Parameters
    ----------
    x, y : np.ndarray
        Cartesian coordinates (metres).
    distance_m : np.ndarray
        Cumulative distance (metres).

    Returns
    -------
    np.ndarray
        Unwrapped heading in radians, shape ``(N,)``.
    """
    dx = np.gradient(x, distance_m)
    dy = np.gradient(y, distance_m)
    heading = np.arctan2(dy, dx)
    heading = np.unwrap(heading)

    # Smooth heading to reduce GPS noise
    n = len(heading)
    win = min(HEADING_SMOOTH_WINDOW, n)
    if win >= 5 and win % 2 == 0:
        win -= 1
    if win >= 5:
        heading = savgol_filter(heading, window_length=win, polyorder=3)

    return np.asarray(heading)


def _find_knots(
    heading: np.ndarray,
    distance_m: np.ndarray,
) -> np.ndarray:
    """Identify segment boundary indices (knots) in the heading profile.

    Knots are placed where the second derivative of heading with respect
    to distance (i.e., the rate of change of curvature) changes sign.
    This corresponds to transitions between clothoid segments.

    Parameters
    ----------
    heading : np.ndarray
        Smoothed, unwrapped heading (radians).
    distance_m : np.ndarray
        Cumulative distance (metres).

    Returns
    -------
    np.ndarray
        Sorted array of knot indices, always including ``0`` and ``N-1``.
    """
    n = len(heading)

    # Always include endpoints
    knots_set: set[int] = {0, n - 1}

    if n < 2 * MIN_KNOT_SPACING:
        return np.array(sorted(knots_set), dtype=np.intp)

    # First derivative of heading = curvature
    d_heading = np.gradient(heading, distance_m)

    # Second derivative of heading = rate of curvature change
    dd_heading = np.gradient(d_heading, distance_m)

    # Smooth the second derivative to avoid noise-induced false knots
    win = min(KNOT_SMOOTH_WINDOW, n)
    if win >= 5 and win % 2 == 0:
        win -= 1
    if win >= 5:
        dd_heading = savgol_filter(dd_heading, window_length=win, polyorder=3)

    # Find zero crossings of dd_heading (sign changes in curvature rate)
    signs = np.sign(dd_heading)
    sign_changes = np.where(np.diff(signs) != 0)[0]

    # Filter knots by minimum spacing
    if len(sign_changes) > 0:
        filtered: list[int] = []
        last_knot = -MIN_KNOT_SPACING  # allow first one
        for idx in sign_changes:
            # Keep away from endpoints
            if idx < MIN_KNOT_SPACING or idx > n - 1 - MIN_KNOT_SPACING:
                continue
            if idx - last_knot >= MIN_KNOT_SPACING:
                filtered.append(int(idx))
                last_knot = idx
        knots_set.update(filtered)

    return np.array(sorted(knots_set), dtype=np.intp)


def _fit_segments(
    heading: np.ndarray,
    distance_m: np.ndarray,
    knots: np.ndarray,
) -> np.ndarray:
    """Fit a linear curvature model within each segment defined by knots.

    Within each segment ``[knots[i], knots[i+1]]``, heading is modelled as
    quadratic in distance (since heading = integral of linear curvature):

        ``theta(s) = c0 + c1 * s + c2 * s^2``

    where curvature ``kappa(s) = c1 + 2 * c2 * s`` (the derivative of theta).
    A least-squares fit determines ``c1`` and ``c2``.

    Parameters
    ----------
    heading : np.ndarray
        Smoothed, unwrapped heading (radians).
    distance_m : np.ndarray
        Cumulative distance (metres).
    knots : np.ndarray
        Sorted indices of segment boundaries.

    Returns
    -------
    np.ndarray
        Curvature array, shape ``(N,)``.
    """
    n = len(heading)
    curvature = np.zeros(n, dtype=np.float64)

    for seg_idx in range(len(knots) - 1):
        start = knots[seg_idx]
        end = knots[seg_idx + 1] + 1  # inclusive end
        if end > n:
            end = n

        seg_len = end - start
        if seg_len < 2:
            continue

        # Local distance (zero-based within the segment)
        s_local = distance_m[start:end] - distance_m[start]
        theta_local = heading[start:end]

        if seg_len < MIN_SEGMENT_POINTS:
            # Too few points for quadratic fit — use simple difference
            kappa_seg = (
                np.gradient(theta_local, s_local) if s_local[-1] > 1e-12 else np.zeros(seg_len)
            )
            curvature[start:end] = kappa_seg
            continue

        # Guard against zero-length segments (all-duplicate distances)
        if s_local[-1] < 1e-12:
            curvature[start:end] = 0.0
            continue

        # Fit theta(s) = c0 + c1*s + c2*s^2 via least squares
        # This is a degree-2 polynomial fit
        coeffs = np.polyfit(s_local, theta_local, 2)
        # coeffs = [c2, c1, c0] (numpy convention: highest degree first)
        c2 = coeffs[0]
        c1 = coeffs[1]

        # Curvature = d(theta)/ds = c1 + 2*c2*s
        kappa_seg = c1 + 2.0 * c2 * s_local
        curvature[start:end] = kappa_seg

    return curvature


def _simple_curvature(
    x: np.ndarray,
    y: np.ndarray,
    distance_m: np.ndarray,
) -> np.ndarray:
    """Compute curvature via simple heading differences for short arrays.

    Used as a fallback when the input has fewer than
    :data:`MIN_SEGMENT_POINTS` samples.

    Parameters
    ----------
    x, y : np.ndarray
        Cartesian coordinates (metres).
    distance_m : np.ndarray
        Cumulative distance (metres).

    Returns
    -------
    np.ndarray
        Curvature array (1/m), shape ``(N,)``.
    """
    dx = np.gradient(x, distance_m)
    dy = np.gradient(y, distance_m)
    heading = np.unwrap(np.arctan2(dy, dx))
    curvature: np.ndarray = np.gradient(heading, distance_m)
    return curvature

"""Curvature computation from GPS coordinates via spline fitting."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import UnivariateSpline
from scipy.signal import butter, filtfilt, savgol_filter

# Physical curvature ceiling — corresponds to a 3 m radius hairpin, the
# tightest turn any road car can negotiate.  GPS glitches occasionally
# produce curvatures well above 1.0 1/m; clamping keeps downstream
# corner-detection grounded in reality.
MAX_PHYSICAL_CURVATURE: float = 0.33  # 1/m  (radius ≈ 3 m)

# Maximum rate of curvature change per metre of distance.  Limits
# |d(kappa)/ds| so that curvature cannot jump instantaneously from GPS
# noise.  0.02 1/m^2 allows a full transition from straight to a 50 m
# radius corner in ~1 m of travel — aggressive enough to preserve real
# transitions, conservative enough to squash single-sample spikes.
MAX_CURVATURE_RATE: float = 0.02  # 1/m per metre

# When smoothing=None, use s = n_points * step_m * this factor.
# A value of 1.0 gives a regression spline (not interpolating) that follows
# the overall track shape without chasing GPS noise.
#
# Smoothing tuning guide:
# - Lower values (0.1-0.5): tighter fit to GPS points, noisier curvature.
#   Use for high-quality GPS (RTK/DGPS) or very short tracks.
# - Default (1.0): good balance for 25Hz consumer GPS at 0.7m spacing.
# - Higher values (2.0-5.0): smoother curvature, may round off tight corners.
#   Use for noisy GPS or when only the overall track shape matters.
# - The optional savgol_window parameter in compute_curvature() applies
#   additional post-smoothing to the curvature array if spline smoothing
#   alone isn't sufficient.
DEFAULT_SMOOTHING_FACTOR_PER_POINT = 1.0


@dataclass
class CurvatureResult:
    """Full curvature profile for one lap."""

    distance_m: np.ndarray  # distance array
    curvature: np.ndarray  # signed curvature (1/m), positive=left
    abs_curvature: np.ndarray  # |curvature|
    heading_rad: np.ndarray  # heading in radians
    x_smooth: np.ndarray  # smoothed X coordinates (meters)
    y_smooth: np.ndarray  # smoothed Y coordinates (meters)


def _latlon_to_local_xy(
    lat: np.ndarray,
    lon: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert lat/lon arrays to local XY in meters via equirectangular projection.

    The first point becomes the origin (0, 0).  X points east, Y points north.
    """
    mean_lat_rad = np.radians(np.mean(lat))
    x: np.ndarray = (lon - lon[0]) * np.cos(mean_lat_rad) * 111320.0
    y: np.ndarray = (lat - lat[0]) * 111320.0
    return x, y


def _limit_curvature_rate(
    curvature: np.ndarray,
    step_m: float,
    max_rate: float = MAX_CURVATURE_RATE,
) -> np.ndarray:
    """Forward-backward rate limiter on curvature.

    Constrains the curvature profile so that |kappa[i] - kappa[i-1]| does
    not exceed *max_rate* * *step_m* for any pair of adjacent samples.

    The algorithm makes two passes:

    1. **Forward**: walk left-to-right, clamping each sample so it lies
       within ``prev ± max_rate * step_m``.
    2. **Backward**: walk right-to-left with the same rule.

    The final result is the element-wise value that is closest to zero
    (minimum absolute value) from the two passes, preserving sign.  This
    avoids the directional bias inherent in a single-pass approach.

    Parameters
    ----------
    curvature:
        Signed curvature array (1/m).
    step_m:
        Distance-domain sample spacing (metres).
    max_rate:
        Maximum |d(kappa)/ds| in 1/m per metre.

    Returns
    -------
    np.ndarray
        Rate-limited curvature array of the same length.
    """
    max_delta = max_rate * step_m

    # Forward pass
    fwd = curvature.copy()
    for i in range(1, len(fwd)):
        fwd[i] = np.clip(fwd[i], fwd[i - 1] - max_delta, fwd[i - 1] + max_delta)

    # Backward pass
    bwd = curvature.copy()
    for i in range(len(bwd) - 2, -1, -1):
        bwd[i] = np.clip(bwd[i], bwd[i + 1] - max_delta, bwd[i + 1] + max_delta)

    # Take the value closest to zero from each pass (preserves sign)
    result: np.ndarray = np.where(np.abs(fwd) <= np.abs(bwd), fwd, bwd)
    return result


def compute_curvature(
    lap_df: pd.DataFrame,
    step_m: float = 0.7,
    smoothing: float | None = None,
    savgol_window: int = 0,
) -> CurvatureResult:
    """Compute signed curvature from a resampled lap DataFrame.

    Parameters
    ----------
    lap_df:
        Must contain ``lat``, ``lon``, and ``lap_distance_m`` columns.
    step_m:
        Distance-domain sample spacing (metres).  Used for default smoothing.
    smoothing:
        Explicit smoothing factor ``s`` passed to :class:`UnivariateSpline`.
        If *None*, a default of ``n * step_m * DEFAULT_SMOOTHING_FACTOR_PER_POINT``
        is used for a regression (non-interpolating) fit.
    savgol_window:
        If > 0, apply a Savitzky-Golay post-filter of this window length
        (must be odd; polyorder=3) to the curvature array.

    Returns
    -------
    CurvatureResult
        Curvature, heading, and smoothed coordinates.

    Raises
    ------
    ValueError
        If required columns are missing from *lap_df*.
    """
    for col in ("lat", "lon", "lap_distance_m"):
        if col not in lap_df.columns:
            msg = f"Required column '{col}' missing from lap DataFrame"
            raise ValueError(msg)

    lat = lap_df["lat"].to_numpy(dtype=np.float64)
    lon = lap_df["lon"].to_numpy(dtype=np.float64)
    distance = lap_df["lap_distance_m"].to_numpy(dtype=np.float64)

    x_raw, y_raw = _latlon_to_local_xy(lat, lon)

    n = len(distance)
    s = n * step_m * DEFAULT_SMOOTHING_FACTOR_PER_POINT if smoothing is None else smoothing

    # Fit regression splines for X(d) and Y(d)
    spline_x = UnivariateSpline(distance, x_raw, s=s, k=4)
    spline_y = UnivariateSpline(distance, y_raw, s=s, k=4)

    x_smooth: np.ndarray = spline_x(distance)
    y_smooth: np.ndarray = spline_y(distance)

    # Analytical first and second derivatives from the splines
    dx = spline_x.derivative(n=1)(distance)
    ddx = spline_x.derivative(n=2)(distance)
    dy = spline_y.derivative(n=1)(distance)
    ddy = spline_y.derivative(n=2)(distance)

    # Signed curvature: kappa = (x' * y'' - x'' * y') / (x'^2 + y'^2)^(3/2)
    numerator = dx * ddy - ddx * dy
    denominator = (dx**2 + dy**2) ** 1.5
    # Guard against division by zero at degenerate points
    curvature: np.ndarray = np.where(
        denominator > 1e-12,
        numerator / denominator,
        0.0,
    )

    # Optional Savitzky-Golay post-smoothing
    if savgol_window > 0:
        # savgol_filter requires odd window; enforce it
        win = savgol_window if savgol_window % 2 == 1 else savgol_window + 1
        if win >= len(curvature):
            win = len(curvature) if len(curvature) % 2 == 1 else len(curvature) - 1
        if win >= 5:  # need at least polyorder+2 points
            curvature = savgol_filter(curvature, window_length=win, polyorder=3)

    # --- Physics-constrained post-processing ---
    # 1. Curvature rate limiter: suppress physically impossible transitions
    curvature = _limit_curvature_rate(curvature, step_m)
    # 2. Physical curvature clamp: cap at tightest-possible hairpin
    curvature = np.clip(curvature, -MAX_PHYSICAL_CURVATURE, MAX_PHYSICAL_CURVATURE)

    heading_rad: np.ndarray = np.arctan2(dy, dx)

    return CurvatureResult(
        distance_m=distance,
        curvature=curvature,
        abs_curvature=np.abs(curvature),
        heading_rad=heading_rad,
        x_smooth=x_smooth,
        y_smooth=y_smooth,
    )


def compute_curvature_from_heading(
    heading_deg: np.ndarray,
    distance_m: np.ndarray,
    step_m: float = 0.7,
) -> CurvatureResult:
    """Compute curvature from heading when lat/lon are unavailable.

    Uses central differences of the unwrapped heading to approximate
    d(heading)/d(distance).

    Parameters
    ----------
    heading_deg:
        Heading in degrees (0=North, clockwise).
    distance_m:
        Corresponding cumulative distance array.
    step_m:
        Nominal spacing between samples (metres).

    Returns
    -------
    CurvatureResult
        Curvature derived from heading, with reconstructed XY track.
    """
    heading_rad = np.unwrap(np.radians(heading_deg))

    # Central difference: d(heading)/d(distance)
    curvature = np.gradient(heading_rad, distance_m)

    # Reconstruct XY by integrating heading
    # heading_rad is math-convention here (radians, from East, CCW positive)
    # but GPS heading is from North, clockwise.  Convert: math_angle = pi/2 - gps_angle.
    # Since we already have radians from deg, and np.gradient gives the rate of change,
    # for reconstruction we use the original heading.
    # GPS heading: 0=N,90=E  ->  math: 0=E,90=N  ->  x=sin(heading), y=cos(heading)
    heading_for_xy = np.radians(heading_deg)
    dx = np.sin(heading_for_xy) * step_m
    dy = np.cos(heading_for_xy) * step_m
    x_smooth = np.cumsum(dx)
    y_smooth = np.cumsum(dy)

    return CurvatureResult(
        distance_m=distance_m,
        curvature=curvature,
        abs_curvature=np.abs(curvature),
        heading_rad=heading_rad,
        x_smooth=x_smooth,
        y_smooth=y_smooth,
    )


# ---------------------------------------------------------------------------
# Yaw-rate curvature (κ = ψ̇ / v)
# ---------------------------------------------------------------------------

_YAW_MIN_COVERAGE: float = 0.8  # require ≥80% valid yaw_rate values
_YAW_MIN_SPEED_MPS: float = 5.0  # below this, yaw-rate curvature unreliable
_YAW_BLEND_SPEED_MPS: float = 10.0  # full weight to yaw-rate above this


def compute_yaw_rate_curvature(
    yaw_rate_dps: np.ndarray,
    speed_mps: np.ndarray,
    distance_m: np.ndarray,
    *,
    sample_rate_hz: float = 25.0,
    filter_cutoff_hz: float = 5.0,
) -> np.ndarray | None:
    """Compute curvature from yaw rate: κ = (ψ̇ in rad/s) / v.

    Uses the gyroscope yaw-rate channel from RaceBox/IMU devices.  This
    avoids GPS second-derivative noise and banking contamination that
    plague position-based curvature.

    Returns None if insufficient valid yaw_rate data (<80% non-NaN).
    Zeroes curvature below ``_YAW_MIN_SPEED_MPS`` to avoid
    division-by-near-zero.  Applies 2nd-order Butterworth low-pass
    filter (zero-phase) for noise reduction.

    Parameters
    ----------
    yaw_rate_dps:
        Yaw rate in degrees per second.  May contain NaN for missing
        samples.
    speed_mps:
        Vehicle speed in metres per second.
    distance_m:
        Cumulative distance array (metres).
    sample_rate_hz:
        Sampling rate of the telemetry (Hz).  Used for filter design.
    filter_cutoff_hz:
        Low-pass filter cutoff frequency (Hz).

    Returns
    -------
    np.ndarray | None
        Signed curvature array (1/m), or None if data is insufficient.
    """
    valid_mask = np.isfinite(yaw_rate_dps)
    if valid_mask.mean() < _YAW_MIN_COVERAGE:
        return None

    # Fill NaN gaps with linear interpolation for filtering
    yaw_filled: np.ndarray = np.interp(distance_m, distance_m[valid_mask], yaw_rate_dps[valid_mask])

    # Butterworth low-pass filter (zero-phase)
    nyquist = sample_rate_hz / 2.0
    if filter_cutoff_hz < nyquist:
        b, a = butter(2, filter_cutoff_hz / nyquist, btype="low")
        yaw_filtered: np.ndarray = filtfilt(b, a, yaw_filled)
    else:
        yaw_filtered = yaw_filled

    # Convert deg/s → rad/s and compute curvature
    yaw_rad_s = np.radians(yaw_filtered)
    safe_speed = np.maximum(speed_mps, _YAW_MIN_SPEED_MPS)
    kappa_raw: np.ndarray = yaw_rad_s / safe_speed

    # Blend to zero below _YAW_MIN_SPEED_MPS
    blend_weight = np.clip(
        (speed_mps - _YAW_MIN_SPEED_MPS) / (_YAW_BLEND_SPEED_MPS - _YAW_MIN_SPEED_MPS),
        0.0,
        1.0,
    )
    kappa: np.ndarray = kappa_raw * blend_weight

    # Apply same physical limits as GPS curvature
    kappa = np.clip(kappa, -MAX_PHYSICAL_CURVATURE, MAX_PHYSICAL_CURVATURE)

    return kappa


# ---------------------------------------------------------------------------
# GPS + yaw-rate curvature fusion
# ---------------------------------------------------------------------------


def fuse_curvature_sources(
    kappa_gps: np.ndarray,
    kappa_yaw: np.ndarray | None,
    distance_m: np.ndarray,
    *,
    yaw_weight_at_apex: float = 0.7,
    yaw_weight_on_straight: float = 0.3,
    curvature_threshold: float = 0.005,
) -> np.ndarray:
    """Fuse GPS and yaw-rate curvature, weighting yaw-rate more at high-curvature zones.

    At corners (|kappa| > threshold), yaw-rate is more reliable because GPS
    position-based curvature suffers from second-derivative noise amplification
    and banking contamination.  On straights, GPS position is more reliable
    because gyro drift accumulates over distance.

    Parameters
    ----------
    kappa_gps:
        Signed curvature from GPS position (1/m).
    kappa_yaw:
        Signed curvature from yaw rate (1/m), or *None* if unavailable.
    distance_m:
        Cumulative distance array (metres).  Currently unused but kept for
        future distance-weighted blending.
    yaw_weight_at_apex:
        Weight given to yaw-rate curvature at high-curvature zones.
    yaw_weight_on_straight:
        Weight given to yaw-rate curvature on straights.
    curvature_threshold:
        Absolute curvature above which the apex weight is used (1/m).

    Returns
    -------
    np.ndarray
        Fused signed curvature array (1/m).
    """
    if kappa_yaw is None:
        return kappa_gps.copy()

    abs_kappa = np.maximum(np.abs(kappa_gps), np.abs(kappa_yaw))
    # Weight ramp: more yaw-rate weight at higher curvature
    yaw_weight: np.ndarray = np.where(
        abs_kappa > curvature_threshold,
        yaw_weight_at_apex,
        yaw_weight_on_straight,
    )
    fused: np.ndarray = (1.0 - yaw_weight) * kappa_gps + yaw_weight * kappa_yaw
    return fused

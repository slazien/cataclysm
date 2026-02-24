"""Curvature computation from GPS coordinates via spline fitting."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import UnivariateSpline
from scipy.signal import savgol_filter

# When smoothing=None, use s = n_points * step_m * this factor.
# A value of 1.0 gives a regression spline (not interpolating) that follows
# the overall track shape without chasing GPS noise.
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

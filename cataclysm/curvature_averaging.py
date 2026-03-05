"""Multi-lap curvature averaging for GPS noise reduction.

Averages XY coordinates across multiple laps in the distance domain, then
computes curvature from the averaged track.  N laps reduces random GPS noise
by a factor of sqrt(N): 10 laps -> ~3.2x noise reduction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import UnivariateSpline

from cataclysm.curvature import (
    DEFAULT_SMOOTHING_FACTOR_PER_POINT,
    MAX_PHYSICAL_CURVATURE,
    CurvatureResult,
    _limit_curvature_rate,
)

# Minimum number of distance-domain samples for a valid spline fit (k=4
# requires at least 5 knots, but we need margin for edge-trimming).
MIN_SAMPLES: int = 20


def average_lap_coordinates(
    laps: dict[int, pd.DataFrame],
    step_m: float = 0.7,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Average XY coordinates across multiple laps in the distance domain.

    All laps are re-parameterised by distance.  Coordinates at each distance
    point are averaged across laps.  This reduces random GPS noise by sqrt(N).

    Parameters
    ----------
    laps:
        Mapping of lap number to DataFrame.  Each DataFrame must contain
        ``latitude``, ``longitude``, and ``lap_distance_m`` columns.
    step_m:
        Uniform distance spacing for the output grid (metres).

    Returns
    -------
    tuple[np.ndarray, np.ndarray, np.ndarray]
        ``(distance_m, avg_x, avg_y)`` — uniform distance grid and the
        averaged local XY coordinates (metres).

    Raises
    ------
    ValueError
        If *laps* is empty.
    """
    if not laps:
        msg = "average_lap_coordinates requires at least one lap"
        raise ValueError(msg)

    # ------------------------------------------------------------------
    # 1. Convert each lap's lat/lon to local XY with a common origin
    # ------------------------------------------------------------------
    # Use the first lap's first point as the shared reference origin so that
    # all laps are in the same coordinate frame.  This is critical: without
    # a common origin, GPS noise on each lap's start point would shift the
    # entire coordinate system, defeating the purpose of averaging.
    lap_dfs = list(laps.values())
    ref_lat = float(lap_dfs[0]["latitude"].iloc[0])
    ref_lon = float(lap_dfs[0]["longitude"].iloc[0])

    lap_xy: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for lap_df in lap_dfs:
        lat = lap_df["latitude"].to_numpy(dtype=np.float64)
        lon = lap_df["longitude"].to_numpy(dtype=np.float64)

        # Project using the shared reference origin
        mean_lat_rad = np.radians(np.mean(lat))
        x: np.ndarray = (lon - ref_lon) * np.cos(mean_lat_rad) * 111320.0
        y: np.ndarray = (lat - ref_lat) * 111320.0

        dist = lap_df["lap_distance_m"].to_numpy(dtype=np.float64)
        lap_xy.append((dist, x, y))

    # ------------------------------------------------------------------
    # 2. Common distance range (min of all lap max-distances)
    # ------------------------------------------------------------------
    max_distances = [d[-1] for d, _, _ in lap_xy]
    common_max = min(max_distances)

    # Uniform distance grid
    distance_grid: np.ndarray = np.arange(0.0, common_max, step_m)
    if len(distance_grid) < MIN_SAMPLES:
        distance_grid = np.linspace(0.0, common_max, MIN_SAMPLES)

    # ------------------------------------------------------------------
    # 3. Interpolate each lap onto the grid and accumulate
    # ------------------------------------------------------------------
    n_grid = len(distance_grid)
    x_sum = np.zeros(n_grid, dtype=np.float64)
    y_sum = np.zeros(n_grid, dtype=np.float64)

    for dist, x, y in lap_xy:
        x_interp = np.interp(distance_grid, dist, x)
        y_interp = np.interp(distance_grid, dist, y)
        x_sum += x_interp
        y_sum += y_interp

    n_laps = len(laps)
    avg_x: np.ndarray = x_sum / n_laps
    avg_y: np.ndarray = y_sum / n_laps

    return distance_grid, avg_x, avg_y


def compute_averaged_curvature(
    laps: dict[int, pd.DataFrame],
    step_m: float = 0.7,
    smoothing: float | None = None,
) -> CurvatureResult:
    """Compute curvature from multi-lap averaged coordinates.

    Steps:

    1. Convert each lap's lat/lon to local XY (via ``_latlon_to_local_xy``).
    2. Re-parameterise by distance (interpolate at uniform *step_m* intervals).
    3. Average XY at each distance point across all laps.
    4. Fit smoothing splines to the averaged track.
    5. Compute curvature analytically from the spline derivatives.

    Falls back to single-lap processing when only one lap is provided.

    Parameters
    ----------
    laps:
        Mapping of lap number to DataFrame.  Each DataFrame must have
        ``latitude``, ``longitude``, and ``lap_distance_m`` columns.
    step_m:
        Distance-domain sample spacing (metres).
    smoothing:
        Explicit smoothing factor *s* for ``UnivariateSpline``.  If *None*,
        a default is chosen based on the number of data points.

    Returns
    -------
    CurvatureResult
        Curvature, heading, and smoothed coordinates computed from the
        averaged track.
    """
    # ------------------------------------------------------------------
    # Average coordinates across laps
    # ------------------------------------------------------------------
    distance, avg_x, avg_y = average_lap_coordinates(laps, step_m=step_m)

    n = len(distance)

    # ------------------------------------------------------------------
    # Spline smoothing
    # ------------------------------------------------------------------
    s = n * step_m * DEFAULT_SMOOTHING_FACTOR_PER_POINT if smoothing is None else smoothing

    spline_x = UnivariateSpline(distance, avg_x, s=s, k=4)
    spline_y = UnivariateSpline(distance, avg_y, s=s, k=4)

    x_smooth: np.ndarray = spline_x(distance)
    y_smooth: np.ndarray = spline_y(distance)

    # ------------------------------------------------------------------
    # Analytical derivatives -> signed curvature
    # ------------------------------------------------------------------
    dx = spline_x.derivative(n=1)(distance)
    ddx = spline_x.derivative(n=2)(distance)
    dy = spline_y.derivative(n=1)(distance)
    ddy = spline_y.derivative(n=2)(distance)

    numerator = dx * ddy - ddx * dy
    denominator = (dx**2 + dy**2) ** 1.5

    curvature: np.ndarray = np.where(
        denominator > 1e-12,
        numerator / denominator,
        0.0,
    )

    # ------------------------------------------------------------------
    # Physics-constrained post-processing (same as compute_curvature)
    # ------------------------------------------------------------------
    curvature = _limit_curvature_rate(curvature, step_m)
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

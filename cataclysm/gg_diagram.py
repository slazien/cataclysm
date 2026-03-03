"""G-G diagram computation with traction circle utilization scoring.

Computes the lateral-G vs longitudinal-G scatter (the "G-G diagram") from
resampled telemetry data.  Utilization is measured as the ratio of the convex
hull area of observed (lat_g, lon_g) points to the area of the observed
traction circle (π × max_combined_g²).

GPS-derived G at 25 Hz is noisy.  The approach normalises against *observed*
max combined G rather than a theoretical traction-circle limit, so utilisation
answers "how much of YOUR envelope are you using?" without requiring tyre-mu
or vehicle-mass data.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import ConvexHull

from cataclysm.corners import Corner

logger = logging.getLogger(__name__)

# Minimum number of G-G points for a valid convex hull (need >= 3 non-collinear)
MIN_POINTS_FOR_HULL = 3

# Floor for max combined G to avoid division-by-zero with near-stationary data
MIN_MAX_G = 0.05


@dataclass
class GGPoint:
    """A single point in the G-G diagram."""

    lat_g: float
    lon_g: float
    distance_m: float
    corner_number: int | None = None


@dataclass
class CornerGGSummary:
    """G-G utilization summary for a single corner."""

    corner_number: int
    utilization_pct: float
    max_lat_g: float
    max_lon_g: float
    point_count: int


@dataclass
class GGDiagramResult:
    """Complete G-G diagram computation result."""

    points: list[GGPoint]
    overall_utilization_pct: float
    observed_max_g: float
    per_corner: list[CornerGGSummary] = field(default_factory=list)


def _convex_hull_area(lat_g: np.ndarray, lon_g: np.ndarray) -> float:
    """Compute the convex hull area of a set of 2-D G-G points.

    Returns 0.0 if there are fewer than 3 points or the points are
    degenerate (collinear / coincident).
    """
    if len(lat_g) < MIN_POINTS_FOR_HULL:
        return 0.0

    pts = np.column_stack((lat_g, lon_g))

    # Quick degeneracy check: if all points are essentially the same
    if np.ptp(pts, axis=0).max() < 1e-9:
        return 0.0

    try:
        hull = ConvexHull(pts)
        return float(hull.volume)  # In 2-D, scipy ConvexHull.volume == area
    except Exception:  # noqa: BLE001 – QhullError or degenerate input
        logger.debug("ConvexHull failed (likely collinear points), returning area=0")
        return 0.0


def _utilization_pct(hull_area: float, max_g: float) -> float:
    """Compute utilization as hull_area / (π × max_g²) × 100.

    Returns 0.0 if max_g is below the safety floor.
    """
    if max_g < MIN_MAX_G:
        return 0.0
    circle_area = math.pi * max_g**2
    return min(hull_area / circle_area * 100.0, 100.0)


def _assign_corner_numbers(
    distance_m: np.ndarray,
    corners: list[Corner],
) -> np.ndarray:
    """Return an array of corner numbers (or -1) for each distance point.

    A point is inside corner *c* if ``c.entry_distance_m <= d < c.exit_distance_m``.
    Points not inside any corner are labelled -1.
    """
    n = len(distance_m)
    labels = np.full(n, -1, dtype=np.int32)

    for c in corners:
        mask = (distance_m >= c.entry_distance_m) & (distance_m < c.exit_distance_m)
        labels[mask] = c.number

    return labels


def compute_gg_diagram(
    resampled_lap: dict[str, np.ndarray] | object,
    corners: list[Corner] | None = None,
    corner_number: int | None = None,
) -> GGDiagramResult:
    """Compute the G-G diagram from a single resampled lap.

    Parameters
    ----------
    resampled_lap
        A pandas DataFrame (or dict-like) with columns ``lateral_g``,
        ``longitudinal_g``, and ``lap_distance_m``.
    corners
        Optional list of corners for per-corner breakdown and filtering.
    corner_number
        If provided, return only data for this specific corner.

    Returns
    -------
    GGDiagramResult
        Points, overall utilization, observed max G, and per-corner summaries.
    """
    # Extract arrays — works with both DataFrame and dict-of-arrays
    lat_g = np.asarray(resampled_lap["lateral_g"], dtype=np.float64)  # type: ignore[index]
    lon_g = np.asarray(resampled_lap["longitudinal_g"], dtype=np.float64)  # type: ignore[index]
    distance = np.asarray(resampled_lap["lap_distance_m"], dtype=np.float64)  # type: ignore[index]

    n = len(lat_g)

    # Handle empty or tiny inputs
    if n == 0:
        return GGDiagramResult(points=[], overall_utilization_pct=0.0, observed_max_g=0.0)

    # Remove any NaN rows
    valid_mask = np.isfinite(lat_g) & np.isfinite(lon_g) & np.isfinite(distance)
    lat_g = lat_g[valid_mask]
    lon_g = lon_g[valid_mask]
    distance = distance[valid_mask]
    n = len(lat_g)

    if n == 0:
        return GGDiagramResult(points=[], overall_utilization_pct=0.0, observed_max_g=0.0)

    # Assign corner labels
    corner_labels = np.full(n, -1, dtype=np.int32)
    if corners:
        corner_labels = _assign_corner_numbers(distance, corners)

    # Filter to a single corner if requested
    if corner_number is not None:
        mask = corner_labels == corner_number
        lat_g = lat_g[mask]
        lon_g = lon_g[mask]
        distance = distance[mask]
        corner_labels = corner_labels[mask]
        n = len(lat_g)

        if n == 0:
            return GGDiagramResult(points=[], overall_utilization_pct=0.0, observed_max_g=0.0)

    # Observed max combined G across ALL points (before corner filtering for
    # per-corner normalisation — we want the same reference circle)
    combined_g = np.sqrt(lat_g**2 + lon_g**2)
    observed_max_g = float(np.max(combined_g)) if n > 0 else 0.0

    # Overall utilization
    hull_area = _convex_hull_area(lat_g, lon_g)
    overall_util = _utilization_pct(hull_area, observed_max_g)

    # Build GGPoint list
    points: list[GGPoint] = []
    for i in range(n):
        cn = int(corner_labels[i]) if corner_labels[i] >= 0 else None
        points.append(
            GGPoint(
                lat_g=round(float(lat_g[i]), 4),
                lon_g=round(float(lon_g[i]), 4),
                distance_m=round(float(distance[i]), 2),
                corner_number=cn,
            )
        )

    # Per-corner summaries
    per_corner: list[CornerGGSummary] = []
    if corners and corner_number is None:
        for c in corners:
            mask = corner_labels == c.number
            c_lat = lat_g[mask]
            c_lon = lon_g[mask]
            c_count = int(np.sum(mask))

            if c_count == 0:
                per_corner.append(
                    CornerGGSummary(
                        corner_number=c.number,
                        utilization_pct=0.0,
                        max_lat_g=0.0,
                        max_lon_g=0.0,
                        point_count=0,
                    )
                )
                continue

            c_hull_area = _convex_hull_area(c_lat, c_lon)
            c_util = _utilization_pct(c_hull_area, observed_max_g)

            per_corner.append(
                CornerGGSummary(
                    corner_number=c.number,
                    utilization_pct=round(c_util, 2),
                    max_lat_g=round(float(np.max(np.abs(c_lat))), 4),
                    max_lon_g=round(float(np.max(np.abs(c_lon))), 4),
                    point_count=c_count,
                )
            )

    return GGDiagramResult(
        points=points,
        overall_utilization_pct=round(overall_util, 2),
        observed_max_g=round(observed_max_g, 4),
        per_corner=per_corner,
    )

"""GPS trace processing: ENU projection, smoothing, reference centerline, lateral offsets.

Provides the spatial foundation for driving line analysis. All geometry operates
in local East-North-Up (ENU) meters — never directly in lat/lon.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pymap3d
from scipy.signal import savgol_filter
from scipy.spatial import cKDTree

from cataclysm.gps_quality import GPSQualityReport


@dataclass
class GPSTrace:
    """ENU-projected, smoothed GPS trace for a single lap."""

    e: np.ndarray  # East component (meters from session origin)
    n: np.ndarray  # North component (meters from session origin)
    distance_m: np.ndarray  # Distance along track (matches existing 0.7m grid)
    lap_number: int


@dataclass
class ReferenceCenterline:
    """Multi-lap median reference line for within-session comparison."""

    e: np.ndarray  # East component
    n: np.ndarray  # North component
    kdtree: cKDTree  # For O(N log N) nearest-point queries
    n_laps_used: int  # Number of laps used to build reference
    left_edge: np.ndarray  # 2nd percentile lateral offset (track boundary estimate)
    right_edge: np.ndarray  # 98th percentile lateral offset


def gps_to_enu(
    lat: np.ndarray,
    lon: np.ndarray,
    lat0: float,
    lon0: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert GPS lat/lon to local East-North-Up coordinates.

    Never compute geometry in lat/lon — distances are distorted.
    All laps in a session share the same origin (first point of first lap).
    """
    alt = np.zeros_like(lat, dtype=np.float64)
    e, n, _ = pymap3d.geodetic2enu(lat, lon, alt, lat0, lon0, 0.0)
    return np.asarray(e, dtype=np.float64), np.asarray(n, dtype=np.float64)


def smooth_gps_trace(
    e: np.ndarray,
    n: np.ndarray,
    spacing_m: float = 0.7,
    window_m: float = 15.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Savitzky-Golay smoothing: reduces GPS noise, preserves corner geometry.

    window_m=15 at 0.7m spacing -> window=21 points, polyorder=3.
    Returns smoothed (e, n) arrays.
    """
    window = max(int(window_m / spacing_m) | 1, 5)  # Ensure odd, minimum 5
    if window % 2 == 0:
        window += 1
    # Need at least window_length points for savgol_filter
    if len(e) < window:
        return e.copy(), n.copy()
    e_smooth = savgol_filter(e, window, polyorder=3)
    n_smooth = savgol_filter(n, window, polyorder=3)
    return np.asarray(e_smooth, dtype=np.float64), np.asarray(n_smooth, dtype=np.float64)


def build_gps_trace(
    lat: np.ndarray,
    lon: np.ndarray,
    distance_m: np.ndarray,
    lap_number: int,
    lat0: float,
    lon0: float,
    *,
    smooth: bool = True,
) -> GPSTrace:
    """Full pipeline: lat/lon -> ENU -> smooth -> GPSTrace."""
    e, n = gps_to_enu(lat, lon, lat0, lon0)
    if smooth:
        e, n = smooth_gps_trace(e, n)
    return GPSTrace(e=e, n=n, distance_m=distance_m, lap_number=lap_number)


def compute_reference_centerline(
    traces: list[GPSTrace],
    min_laps: int = 3,
) -> ReferenceCenterline | None:
    """Median of multiple laps -> robust reference line.

    Uses median (not mean) for robustness to off-track excursions.
    Requires at least ``min_laps``; more laps -> better reference.
    Returns None if not enough laps.
    """
    if len(traces) < min_laps:
        return None

    # All traces must be on the same distance grid; take the shortest
    min_len = min(len(t.distance_m) for t in traces)
    e_stack = np.column_stack([t.e[:min_len] for t in traces])
    n_stack = np.column_stack([t.n[:min_len] for t in traces])

    e_median = np.median(e_stack, axis=1)
    n_median = np.median(n_stack, axis=1)

    # Build kd-tree for efficient nearest-neighbour queries
    points = np.column_stack([e_median, n_median])
    kdtree = cKDTree(points)

    # Compute per-point lateral offsets for all traces to estimate track edges
    all_offsets = []
    for t in traces:
        offsets = compute_lateral_offsets_raw(
            t.e[:min_len], t.n[:min_len], e_median, n_median, kdtree
        )
        all_offsets.append(offsets)
    offset_stack = np.column_stack(all_offsets)
    left_edge = np.percentile(offset_stack, 2, axis=1)
    right_edge = np.percentile(offset_stack, 98, axis=1)

    return ReferenceCenterline(
        e=e_median,
        n=n_median,
        kdtree=kdtree,
        n_laps_used=len(traces),
        left_edge=left_edge,
        right_edge=right_edge,
    )


def compute_lateral_offsets_raw(
    e: np.ndarray,
    n: np.ndarray,
    ref_e: np.ndarray,
    ref_n: np.ndarray,
    kdtree: cKDTree,
) -> np.ndarray:
    """Signed perpendicular distance from trace to reference line.

    Positive = right of reference, Negative = left of reference.
    Uses KD-tree for O(N log N) performance + cross product for sign.
    """
    points = np.column_stack([e, n])
    _, nearest_idx = kdtree.query(points)

    # Distance magnitude
    de = e - ref_e[nearest_idx]
    dn = n - ref_n[nearest_idx]
    dist = np.sqrt(de**2 + dn**2)

    # Sign via cross product with local tangent of reference line
    # Tangent at point i: (ref_e[i+1]-ref_e[i-1], ref_n[i+1]-ref_n[i-1])
    idx = np.clip(nearest_idx, 1, len(ref_e) - 2)
    tang_e = ref_e[idx + 1] - ref_e[idx - 1]
    tang_n = ref_n[idx + 1] - ref_n[idx - 1]

    # Cross product: tangent x offset vector -> sign
    cross = tang_e * dn - tang_n * de
    sign = np.where(cross >= 0, 1.0, -1.0)

    result: np.ndarray = dist * sign
    return result


def compute_lateral_offsets(
    lap: GPSTrace,
    ref: ReferenceCenterline,
) -> np.ndarray:
    """Signed lateral offset from lap trace to reference centerline.

    Positive = right of reference, Negative = left of reference.
    Truncates to the shorter of lap or reference length.
    """
    min_len = min(len(lap.e), len(ref.e))
    return compute_lateral_offsets_raw(lap.e[:min_len], lap.n[:min_len], ref.e, ref.n, ref.kdtree)


def should_enable_line_analysis(gps_quality: GPSQualityReport) -> bool:
    """Only enable line analysis for grade A or B sessions."""
    return gps_quality.grade in ("A", "B")

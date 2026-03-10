"""Elevation analysis from GPS altitude telemetry.

Computes per-corner elevation metrics from the existing ``altitude_m`` column
in resampled lap DataFrames.  Altitude is smoothed with a rolling average to
reduce GPS noise (~3-5m raw → <1m smoothed).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from cataclysm.corners import Corner

# Smoothing window for altitude (meters of track distance)
_ALTITUDE_SMOOTH_WINDOW_M = 50.0

# Gradient thresholds for trend classification (percent)
_FLAT_THRESHOLD_PCT = 1.0  # below this is "flat"
_UPHILL_THRESHOLD_PCT = 1.5
_DOWNHILL_THRESHOLD_PCT = -1.5
_MIN_SHAPE_DELTA_M = 0.5


@dataclass
class CornerElevation:
    """Computed elevation metrics for a single corner."""

    corner_number: int
    elevation_change_m: float  # exit - entry (positive = uphill)
    gradient_pct: float  # average gradient percentage
    trend: str  # "uphill" | "downhill" | "flat" | "crest" | "compression"


def _smooth_altitude(altitude: np.ndarray, step_m: float) -> np.ndarray:
    """Apply rolling average to altitude data to reduce GPS noise."""
    window_pts = max(2, int(_ALTITUDE_SMOOTH_WINDOW_M / step_m))
    kernel = np.ones(window_pts) / window_pts
    return np.convolve(altitude, kernel, mode="same")


def _classify_trend(
    smoothed_alt: np.ndarray,
    entry_idx: int,
    exit_idx: int,
    gradient_pct: float,
    apex_idx: int | None = None,
) -> str:
    """Classify elevation trend within a corner zone.

    - "crest": altitude peaks in the middle (rises then falls)
    - "compression": altitude dips in the middle (falls then rises)
    - "flat": gradient < threshold AND no significant crest/compression
    - "uphill" / "downhill": monotonic change
    """
    segment = smoothed_alt[entry_idx : exit_idx + 1]
    if len(segment) < 3:
        if abs(gradient_pct) < _FLAT_THRESHOLD_PCT:
            return "flat"
        return "uphill" if gradient_pct > 0 else "downhill"

    def _shape_from_pivot(segment_alt: np.ndarray, pivot_idx: int) -> str | None:
        """Detect crest/compression around a pivot using grade sign change."""
        if pivot_idx <= 0 or pivot_idx >= len(segment_alt) - 1:
            return None

        pre_apex = segment_alt[: pivot_idx + 1]
        post_apex = segment_alt[pivot_idx:]
        if len(pre_apex) < 2 or len(post_apex) < 2:
            return None

        pre_delta = float(pre_apex[-1] - pre_apex[0])
        post_delta = float(post_apex[-1] - post_apex[0])
        pre_grade_sign = np.sign(np.mean(np.diff(pre_apex)))
        post_grade_sign = np.sign(np.mean(np.diff(post_apex)))

        if (
            pre_grade_sign > 0
            and post_grade_sign < 0
            and pre_delta > _MIN_SHAPE_DELTA_M
            and post_delta < -_MIN_SHAPE_DELTA_M
        ):
            return "crest"
        if (
            pre_grade_sign < 0
            and post_grade_sign > 0
            and pre_delta < -_MIN_SHAPE_DELTA_M
            and post_delta > _MIN_SHAPE_DELTA_M
        ):
            return "compression"
        return None

    if apex_idx is not None and entry_idx < apex_idx < exit_idx:
        apex_local_idx = apex_idx - entry_idx
        apex_shape = _shape_from_pivot(segment, apex_local_idx)
        if apex_shape is not None:
            return apex_shape

    mid_idx = len(segment) // 2
    mid_shape = _shape_from_pivot(segment, mid_idx)
    if mid_shape is not None:
        return mid_shape

    if gradient_pct > _UPHILL_THRESHOLD_PCT:
        return "uphill"
    if gradient_pct < _DOWNHILL_THRESHOLD_PCT:
        return "downhill"
    if abs(gradient_pct) < _FLAT_THRESHOLD_PCT:
        return "flat"

    return "flat"


def compute_corner_elevation(
    lap_df: pd.DataFrame,
    corners: list[Corner],
    step_m: float = 0.7,
) -> list[CornerElevation]:
    """Compute elevation metrics for each corner from resampled lap data.

    Parameters
    ----------
    lap_df:
        Resampled lap DataFrame.  Must have ``lap_distance_m``.
        If ``altitude_m`` is missing, returns an empty list.
    corners:
        Corner objects with entry/exit distances.
    step_m:
        Resampling step size in meters.

    Returns
    -------
    List of CornerElevation, one per corner that has valid data.
    """
    if "altitude_m" not in lap_df.columns:
        return []

    altitude = lap_df["altitude_m"].to_numpy(dtype=float)
    if np.all(np.isnan(altitude)):
        return []

    distance = lap_df["lap_distance_m"].to_numpy(dtype=float)
    smoothed = _smooth_altitude(altitude, step_m)

    results: list[CornerElevation] = []
    for corner in corners:
        entry_idx = int(np.searchsorted(distance, corner.entry_distance_m))
        exit_idx = int(np.searchsorted(distance, corner.exit_distance_m))
        entry_idx = min(entry_idx, len(smoothed) - 1)
        exit_idx = min(exit_idx, len(smoothed) - 1)

        if exit_idx <= entry_idx:
            continue

        entry_alt = float(smoothed[entry_idx])
        exit_alt = float(smoothed[exit_idx])
        elev_change = exit_alt - entry_alt

        horiz_dist = float(distance[exit_idx] - distance[entry_idx])
        gradient = (elev_change / horiz_dist * 100.0) if horiz_dist > 0 else 0.0

        apex_idx = int(np.searchsorted(distance, corner.apex_distance_m))
        apex_idx = min(apex_idx, len(smoothed) - 1)

        trend = _classify_trend(smoothed, entry_idx, exit_idx, gradient, apex_idx=apex_idx)

        results.append(
            CornerElevation(
                corner_number=corner.number,
                elevation_change_m=round(elev_change, 2),
                gradient_pct=round(gradient, 2),
                trend=trend,
            )
        )

    return results


def enrich_corners_with_elevation(
    all_lap_corners: dict[int, list[Corner]],
    elevations: list[CornerElevation],
) -> None:
    """Attach computed elevation data to Corner objects in-place.

    If a corner already has a curated ``elevation_trend`` (from OfficialCorner),
    the curated value takes precedence over the computed one.
    """
    elev_map = {e.corner_number: e for e in elevations}

    for corners in all_lap_corners.values():
        for corner in corners:
            elev = elev_map.get(corner.number)
            if elev is None:
                continue
            corner.elevation_change_m = elev.elevation_change_m
            corner.gradient_pct = elev.gradient_pct
            # Only set computed trend if no curated trend from track_db
            if corner.elevation_trend is None:
                corner.elevation_trend = elev.trend

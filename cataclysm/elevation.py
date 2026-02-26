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

    mid_idx = len(segment) // 2
    first_half = segment[: mid_idx + 1]
    second_half = segment[mid_idx:]

    first_delta = first_half[-1] - first_half[0]
    second_delta = second_half[-1] - second_half[0]

    # Check for crest/compression before flat — a symmetric crest has ~0% net gradient
    # Crest: rises then falls (both deltas significant)
    if first_delta > 0.5 and second_delta < -0.5:
        return "crest"
    # Compression: falls then rises
    if first_delta < -0.5 and second_delta > 0.5:
        return "compression"

    if abs(gradient_pct) < _FLAT_THRESHOLD_PCT:
        return "flat"

    return "uphill" if gradient_pct > 0 else "downhill"


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

        trend = _classify_trend(smoothed, entry_idx, exit_idx, gradient)

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

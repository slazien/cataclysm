"""Corner detection from heading rate and KPI extraction per corner."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Corner:
    """Detected corner with extracted KPIs."""

    number: int
    entry_distance_m: float
    exit_distance_m: float
    apex_distance_m: float
    min_speed_mps: float
    brake_point_m: float | None
    peak_brake_g: float | None
    throttle_commit_m: float | None
    apex_type: str  # "early", "mid", "late"


# Detection parameters
HEADING_RATE_THRESHOLD = 1.0  # deg/m  -- below this is "straight"
SMOOTHING_WINDOW_M = 20.0  # rolling average window
MIN_CORNER_LENGTH_M = 15.0  # discard shorter segments
MERGE_GAP_M = 30.0  # merge corners closer than this

# KPI search parameters
BRAKE_SEARCH_M = 80.0  # search for braking this far before corner entry
BRAKE_G_THRESHOLD = -0.2  # longitudinal G threshold for braking
THROTTLE_G_THRESHOLD = 0.1  # longitudinal G threshold for throttle application
THROTTLE_SUSTAIN_M = 10.0  # throttle must be sustained for this distance


def _compute_heading_rate(heading_deg: np.ndarray, step_m: float) -> np.ndarray:
    """Compute heading rate of change in deg/m, handling 360/0 wrap."""
    diff = np.diff(heading_deg)
    # Normalize angular difference to [-180, 180]
    diff = (diff + 180) % 360 - 180
    rate = diff / step_m
    # Pad to same length as input
    return np.append(rate, rate[-1])


def _smooth(values: np.ndarray, window_points: int) -> np.ndarray:
    """Apply rolling average smoothing."""
    if window_points < 2:
        return values
    kernel = np.ones(window_points) / window_points
    smoothed = np.convolve(values, kernel, mode="same")
    return smoothed


def _find_contiguous_regions(mask: np.ndarray) -> list[tuple[int, int]]:
    """Find start/end indices of contiguous True regions in a boolean mask."""
    if not mask.any():
        return []

    diff = np.diff(mask.astype(int))
    starts = np.where(diff == 1)[0] + 1
    ends = np.where(diff == -1)[0] + 1

    # Handle edge cases
    if mask[0]:
        starts = np.insert(starts, 0, 0)
    if mask[-1]:
        ends = np.append(ends, len(mask))

    return list(zip(starts.tolist(), ends.tolist(), strict=True))


def _merge_regions(regions: list[tuple[int, int]], gap_points: int) -> list[tuple[int, int]]:
    """Merge regions that are within gap_points of each other."""
    if len(regions) <= 1:
        return regions

    merged: list[tuple[int, int]] = [regions[0]]
    for start, end in regions[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= gap_points:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def _find_brake_point(
    longitudinal_g: np.ndarray,
    entry_idx: int,
    step_m: float,
) -> tuple[int | None, float | None]:
    """Find brake point before corner entry.

    Returns (brake_idx, peak_brake_g) or (None, None).
    """
    search_points = int(BRAKE_SEARCH_M / step_m)
    search_start = max(0, entry_idx - search_points)
    segment = longitudinal_g[search_start:entry_idx]

    if len(segment) == 0:
        return None, None

    # Find where braking begins (first crossing below threshold, searching backwards)
    braking_mask = segment < BRAKE_G_THRESHOLD
    if not braking_mask.any():
        return None, None

    # Find the first braking point (earliest in the search window)
    brake_indices = np.where(braking_mask)[0]
    brake_local_idx = int(brake_indices[0])
    brake_idx = search_start + brake_local_idx

    peak_g = float(np.min(segment))

    return brake_idx, peak_g


def _find_throttle_commit(
    longitudinal_g: np.ndarray,
    apex_idx: int,
    exit_idx: int,
    step_m: float,
) -> int | None:
    """Find throttle commit point after apex.

    Throttle commit = first point where longitudinal_g > threshold sustained
    for THROTTLE_SUSTAIN_M.
    """
    sustain_points = int(THROTTLE_SUSTAIN_M / step_m)
    segment = longitudinal_g[apex_idx:exit_idx]

    if len(segment) < sustain_points:
        return None

    above = segment > THROTTLE_G_THRESHOLD
    count = 0
    for i, val in enumerate(above):
        if val:
            count += 1
            if count >= sustain_points:
                return apex_idx + i - sustain_points + 1
        else:
            count = 0

    return None


def _classify_apex(entry_idx: int, apex_idx: int, exit_idx: int) -> str:
    """Classify apex position as early, mid, or late."""
    span = exit_idx - entry_idx
    if span == 0:
        return "mid"
    position = (apex_idx - entry_idx) / span
    if position < 0.4:
        return "early"
    if position > 0.6:
        return "late"
    return "mid"


def detect_corners(
    lap_df: pd.DataFrame,
    step_m: float = 0.7,
    threshold: float = HEADING_RATE_THRESHOLD,
) -> list[Corner]:
    """Detect corners in a resampled lap and extract KPIs.

    Parameters
    ----------
    lap_df:
        Resampled lap DataFrame with lap_distance_m, heading_deg, speed_mps,
        longitudinal_g columns.
    step_m:
        Distance step used in resampling.
    threshold:
        Heading rate threshold for corner detection (deg/m).

    Returns
    -------
    List of detected Corner objects, numbered sequentially.
    """
    heading = lap_df["heading_deg"].to_numpy()
    speed = lap_df["speed_mps"].to_numpy()
    distance = lap_df["lap_distance_m"].to_numpy()
    lon_g = lap_df["longitudinal_g"].to_numpy()

    # Compute heading rate and smooth
    heading_rate = _compute_heading_rate(heading, step_m)
    window_pts = max(2, int(SMOOTHING_WINDOW_M / step_m))
    smoothed_rate = _smooth(np.abs(heading_rate), window_pts)

    # Threshold to find corners
    corner_mask = smoothed_rate > threshold

    # Find contiguous regions
    regions = _find_contiguous_regions(corner_mask)

    # Merge nearby regions
    gap_pts = int(MERGE_GAP_M / step_m)
    regions = _merge_regions(regions, gap_pts)

    # Filter short regions
    min_pts = int(MIN_CORNER_LENGTH_M / step_m)
    regions = [(s, e) for s, e in regions if (e - s) >= min_pts]

    # Extract KPIs for each corner
    corners: list[Corner] = []
    for i, (entry_idx, exit_idx) in enumerate(regions, start=1):
        # Clamp indices
        entry_idx = max(0, entry_idx)
        exit_idx = min(len(speed) - 1, exit_idx)

        corner_speed = speed[entry_idx:exit_idx]
        if len(corner_speed) == 0:
            continue

        apex_local = int(np.argmin(corner_speed))
        apex_idx = entry_idx + apex_local

        # Brake point
        brake_idx, peak_g = _find_brake_point(lon_g, entry_idx, step_m)

        # Throttle commit
        throttle_idx = _find_throttle_commit(lon_g, apex_idx, exit_idx, step_m)

        brake_m = round(float(distance[brake_idx]), 1) if brake_idx is not None else None
        throttle_m = round(float(distance[throttle_idx]), 1) if throttle_idx is not None else None
        corners.append(
            Corner(
                number=i,
                entry_distance_m=round(float(distance[entry_idx]), 1),
                exit_distance_m=round(float(distance[exit_idx]), 1),
                apex_distance_m=round(float(distance[apex_idx]), 1),
                min_speed_mps=round(float(corner_speed[apex_local]), 2),
                brake_point_m=brake_m,
                peak_brake_g=(round(peak_g, 3) if peak_g is not None else None),
                throttle_commit_m=throttle_m,
                apex_type=_classify_apex(entry_idx, apex_idx, exit_idx),
            )
        )

    return corners


def extract_corner_kpis_for_lap(
    lap_df: pd.DataFrame,
    reference_corners: list[Corner],
    step_m: float = 0.7,
) -> list[Corner]:
    """Extract KPIs for a lap using corner boundaries from a reference lap.

    This lets us compare the same corner across different laps.
    """
    speed = lap_df["speed_mps"].to_numpy()
    distance = lap_df["lap_distance_m"].to_numpy()
    lon_g = lap_df["longitudinal_g"].to_numpy()
    max_dist = distance[-1]

    corners: list[Corner] = []
    for ref in reference_corners:
        if ref.entry_distance_m > max_dist or ref.exit_distance_m > max_dist:
            continue

        entry_idx = int(np.searchsorted(distance, ref.entry_distance_m))
        exit_idx = int(np.searchsorted(distance, ref.exit_distance_m))
        entry_idx = min(entry_idx, len(speed) - 1)
        exit_idx = min(exit_idx, len(speed) - 1)

        if exit_idx <= entry_idx:
            continue

        corner_speed = speed[entry_idx:exit_idx]
        if len(corner_speed) == 0:
            continue

        apex_local = int(np.argmin(corner_speed))
        apex_idx = entry_idx + apex_local

        brake_idx, peak_g = _find_brake_point(lon_g, entry_idx, step_m)
        throttle_idx = _find_throttle_commit(lon_g, apex_idx, exit_idx, step_m)

        brake_m = round(float(distance[brake_idx]), 1) if brake_idx is not None else None
        throttle_m = round(float(distance[throttle_idx]), 1) if throttle_idx is not None else None
        corners.append(
            Corner(
                number=ref.number,
                entry_distance_m=ref.entry_distance_m,
                exit_distance_m=ref.exit_distance_m,
                apex_distance_m=round(float(distance[apex_idx]), 1),
                min_speed_mps=round(float(corner_speed[apex_local]), 2),
                brake_point_m=brake_m,
                peak_brake_g=(round(peak_g, 3) if peak_g is not None else None),
                throttle_commit_m=throttle_m,
                apex_type=_classify_apex(entry_idx, apex_idx, exit_idx),
            )
        )

    return corners

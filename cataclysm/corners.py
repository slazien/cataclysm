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
    brake_point_lat: float | None = None
    brake_point_lon: float | None = None
    apex_lat: float | None = None
    apex_lon: float | None = None
    peak_curvature: float | None = None
    mean_curvature: float | None = None
    direction: str | None = None  # "left" | "right" | None
    segment_type: str | None = None  # "corner" | "transition" | None
    parent_complex: int | None = None  # hierarchical grouping ID
    detection_method: str | None = None  # "heading_rate" | "spline" | "pelt" | "css" | "asc"


# Detection parameters
HEADING_RATE_THRESHOLD = 1.0  # deg/m  -- below this is "straight"
SMOOTHING_WINDOW_M = 20.0  # rolling average window
MIN_CORNER_LENGTH_M = 15.0  # discard shorter segments
MERGE_GAP_M = 30.0  # merge corners closer than this

# KPI search parameters
BRAKE_SEARCH_BEFORE_M = 150.0  # search for braking this far before corner entry
BRAKE_SEARCH_INTO_CORNER = 0.4  # search up to 40% of the way to the apex
BRAKE_G_THRESHOLD = -0.1  # longitudinal G threshold for braking
THROTTLE_G_THRESHOLD = 0.1  # longitudinal G threshold for throttle application
THROTTLE_SUSTAIN_M = 10.0  # throttle must be sustained for this distance

# Corner type classification thresholds (mph)
SLOW_CORNER_MPH = 40.0
MEDIUM_CORNER_MPH = 80.0

CornerType = str  # "slow", "medium", "fast"


def classify_corner_type(corner: Corner) -> CornerType:
    """Classify a corner as slow, medium, or fast based on min apex speed.

    - Slow: < 40 mph apex
    - Medium: 40-80 mph apex
    - Fast: > 80 mph apex
    """
    speed_mph = corner.min_speed_mps * 2.23694
    if speed_mph < SLOW_CORNER_MPH:
        return "slow"
    if speed_mph < MEDIUM_CORNER_MPH:
        return "medium"
    return "fast"


# Technique tips for each corner type
CORNER_TYPE_TIPS: dict[str, str] = {
    "slow": (
        "Slow corner (<40 mph): Prioritize exit speed over mid-corner speed. "
        "Brake later, use a late apex, and get on throttle early for the following straight."
    ),
    "medium": (
        "Medium corner (40-80 mph): Balance entry speed with exit speed. "
        "Trail brake to the apex, maintain smooth inputs to maximize grip through the turn."
    ),
    "fast": (
        "Fast corner (>80 mph): Prioritize carrying speed — stay close to the geometric line. "
        "Minimize steering input, use progressive brake release, and trust the car's grip."
    ),
}


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
    apex_idx: int,
    step_m: float,
) -> tuple[int | None, float | None]:
    """Find brake point before corner entry or in the early part of the corner.

    Searches from ``BRAKE_SEARCH_BEFORE_M`` before entry through 40% of the
    way to the apex.  Trail braking means drivers often begin braking at or
    slightly inside the heading-rate corner boundary.

    Returns (brake_idx, peak_brake_g) or (None, None).
    """
    search_before_pts = int(BRAKE_SEARCH_BEFORE_M / step_m)
    search_start = max(0, entry_idx - search_before_pts)

    # Allow search into the corner up to BRAKE_SEARCH_INTO_CORNER of the way to apex
    into_corner_pts = int((apex_idx - entry_idx) * BRAKE_SEARCH_INTO_CORNER)
    search_end = min(len(longitudinal_g), entry_idx + into_corner_pts)

    segment = longitudinal_g[search_start:search_end]

    if len(segment) == 0:
        return None, None

    braking_mask = segment < BRAKE_G_THRESHOLD
    if not braking_mask.any():
        return None, None

    # First braking point (earliest in the search window)
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


def _classify_apex(
    speed_apex_idx: int,
    geo_apex_idx: int,
    entry_idx: int,
    exit_idx: int,
) -> str:
    """Classify apex position relative to geometric apex (peak curvature).

    Compares where the minimum-speed point falls vs the point of maximum
    heading rate (geometric apex).  Using entry/exit midpoint as the reference
    gives a systematic "late" bias because the speed minimum naturally occurs
    past the midpoint of the heading-rate zone.
    """
    span = exit_idx - entry_idx
    if span == 0:
        return "mid"
    offset = (speed_apex_idx - geo_apex_idx) / span
    if offset < -0.10:
        return "early"
    if offset > 0.10:
        return "late"
    return "mid"


def _detect_heading_rate(
    lap_df: pd.DataFrame,
    step_m: float,
    threshold: float,
) -> list[Corner]:
    """Detect corners using heading-rate thresholding (original algorithm)."""
    heading = lap_df["heading_deg"].to_numpy()
    speed = lap_df["speed_mps"].to_numpy()
    distance = lap_df["lap_distance_m"].to_numpy()
    lon_g = lap_df["longitudinal_g"].to_numpy()
    has_gps = "lat" in lap_df.columns and "lon" in lap_df.columns
    lat_arr = lap_df["lat"].to_numpy() if has_gps else None
    lon_arr = lap_df["lon"].to_numpy() if has_gps else None

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

        # Geometric apex = peak curvature (max heading rate) within corner
        corner_rate = smoothed_rate[entry_idx:exit_idx]
        geo_apex_idx = entry_idx + int(np.argmax(corner_rate))

        # Brake point
        brake_idx, peak_g = _find_brake_point(lon_g, entry_idx, apex_idx, step_m)

        # Throttle commit
        throttle_idx = _find_throttle_commit(lon_g, apex_idx, exit_idx, step_m)

        brake_m = round(float(distance[brake_idx]), 1) if brake_idx is not None else None
        throttle_m = round(float(distance[throttle_idx]), 1) if throttle_idx is not None else None

        # Resolve GPS coordinates at brake point and apex
        bp_lat = (
            float(lat_arr[brake_idx]) if brake_idx is not None and lat_arr is not None else None
        )
        bp_lon = (
            float(lon_arr[brake_idx]) if brake_idx is not None and lon_arr is not None else None
        )
        a_lat = float(lat_arr[apex_idx]) if lat_arr is not None else None
        a_lon = float(lon_arr[apex_idx]) if lon_arr is not None else None

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
                apex_type=_classify_apex(apex_idx, geo_apex_idx, entry_idx, exit_idx),
                brake_point_lat=bp_lat,
                brake_point_lon=bp_lon,
                apex_lat=a_lat,
                apex_lon=a_lon,
            )
        )

    return corners


def _detect_advanced(
    lap_df: pd.DataFrame,
    step_m: float,
    method: str,
) -> list[Corner]:
    """Detect corners using spline curvature + segmentation.

    Methods: "spline" (uses ASC default), "pelt", "css", "asc"
    """
    from cataclysm.curvature import compute_curvature
    from cataclysm.segmentation import segment_track

    curvature_result = compute_curvature(lap_df, step_m=step_m)

    seg_method = method if method in ("pelt", "css", "asc") else "asc"
    seg_result = segment_track(curvature_result, method=seg_method)

    # Convert segments to Corner objects
    corners: list[Corner] = []
    corner_num = 0
    distance = lap_df["lap_distance_m"].to_numpy()
    speed = lap_df["speed_mps"].to_numpy()
    lon_g = lap_df["longitudinal_g"].to_numpy()
    has_gps = "lat" in lap_df.columns and "lon" in lap_df.columns
    lat_arr = lap_df["lat"].to_numpy() if has_gps else None
    lon_arr = lap_df["lon"].to_numpy() if has_gps else None

    for seg in seg_result.segments:
        if seg.segment_type != "corner":
            continue
        corner_num += 1

        entry_idx = int(np.searchsorted(distance, seg.entry_distance_m))
        exit_idx = int(np.searchsorted(distance, seg.exit_distance_m))
        entry_idx = max(0, min(entry_idx, len(speed) - 1))
        exit_idx = max(0, min(exit_idx, len(speed) - 1))

        if exit_idx <= entry_idx:
            continue

        corner_speed = speed[entry_idx:exit_idx]
        if len(corner_speed) == 0:
            continue

        apex_local = int(np.argmin(corner_speed))
        apex_idx = entry_idx + apex_local

        # Use curvature peak as geometric apex
        curv_slice = curvature_result.abs_curvature[entry_idx:exit_idx]
        geo_apex_idx = entry_idx + int(np.argmax(curv_slice))

        brake_idx, peak_g = _find_brake_point(
            lon_g,
            entry_idx,
            apex_idx,
            step_m,
        )
        throttle_idx = _find_throttle_commit(
            lon_g,
            apex_idx,
            exit_idx,
            step_m,
        )

        brake_m = round(float(distance[brake_idx]), 1) if brake_idx is not None else None
        throttle_m = round(float(distance[throttle_idx]), 1) if throttle_idx is not None else None

        bp_lat = (
            float(lat_arr[brake_idx]) if brake_idx is not None and lat_arr is not None else None
        )
        bp_lon = (
            float(lon_arr[brake_idx]) if brake_idx is not None and lon_arr is not None else None
        )
        a_lat = float(lat_arr[apex_idx]) if lat_arr is not None else None
        a_lon = float(lon_arr[apex_idx]) if lon_arr is not None else None

        corners.append(
            Corner(
                number=corner_num,
                entry_distance_m=round(float(distance[entry_idx]), 1),
                exit_distance_m=round(float(distance[exit_idx]), 1),
                apex_distance_m=round(float(distance[apex_idx]), 1),
                min_speed_mps=round(float(corner_speed[apex_local]), 2),
                brake_point_m=brake_m,
                peak_brake_g=(round(peak_g, 3) if peak_g is not None else None),
                throttle_commit_m=throttle_m,
                apex_type=_classify_apex(
                    apex_idx,
                    geo_apex_idx,
                    entry_idx,
                    exit_idx,
                ),
                brake_point_lat=bp_lat,
                brake_point_lon=bp_lon,
                apex_lat=a_lat,
                apex_lon=a_lon,
                peak_curvature=round(seg.peak_curvature, 6),
                mean_curvature=round(seg.mean_curvature, 6),
                direction=seg.direction,
                segment_type=seg.segment_type,
                parent_complex=seg.parent_complex,
                detection_method=method,
            )
        )

    return corners


def detect_corners(
    lap_df: pd.DataFrame,
    step_m: float = 0.7,
    threshold: float = HEADING_RATE_THRESHOLD,
    *,
    method: str = "heading_rate",
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
    method:
        Detection algorithm.  ``"heading_rate"`` uses the original heading-rate
        thresholding.  ``"spline"``, ``"pelt"``, ``"css"``, or ``"asc"`` use
        spline-curvature segmentation.

    Returns
    -------
    List of detected Corner objects, numbered sequentially.
    """
    if method == "heading_rate":
        return _detect_heading_rate(lap_df, step_m, threshold)
    if method in ("spline", "pelt", "css", "asc"):
        return _detect_advanced(lap_df, step_m, method)
    msg = f"Unknown detection method: {method!r}"
    raise ValueError(msg)


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
    heading = lap_df["heading_deg"].to_numpy()
    has_gps = "lat" in lap_df.columns and "lon" in lap_df.columns
    lat_arr = lap_df["lat"].to_numpy() if has_gps else None
    lon_arr = lap_df["lon"].to_numpy() if has_gps else None
    max_dist = distance[-1]

    # Compute smoothed heading rate for geometric apex detection
    heading_rate = _compute_heading_rate(heading, step_m)
    window_pts = max(2, int(SMOOTHING_WINDOW_M / step_m))
    smoothed_rate = _smooth(np.abs(heading_rate), window_pts)

    # Compute spline curvature once if reference corners used advanced method
    spline_curvature: np.ndarray | None = None
    if any(ref.peak_curvature is not None for ref in reference_corners):
        try:
            from cataclysm.curvature import compute_curvature

            curv_result = compute_curvature(lap_df, step_m=step_m)
            spline_curvature = curv_result.abs_curvature
        except (ValueError, ImportError):
            pass

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

        # Geometric apex = peak curvature within corner
        corner_rate = smoothed_rate[entry_idx:exit_idx]
        geo_apex_idx = entry_idx + int(np.argmax(corner_rate))

        # Override with spline curvature if available
        if spline_curvature is not None:
            curv_slice = spline_curvature[entry_idx:exit_idx]
            if len(curv_slice) > 0:
                geo_apex_idx = entry_idx + int(np.argmax(curv_slice))

        brake_idx, peak_g = _find_brake_point(lon_g, entry_idx, apex_idx, step_m)
        throttle_idx = _find_throttle_commit(lon_g, apex_idx, exit_idx, step_m)

        brake_m = round(float(distance[brake_idx]), 1) if brake_idx is not None else None
        throttle_m = round(float(distance[throttle_idx]), 1) if throttle_idx is not None else None

        bp_lat = (
            float(lat_arr[brake_idx]) if brake_idx is not None and lat_arr is not None else None
        )
        bp_lon = (
            float(lon_arr[brake_idx]) if brake_idx is not None and lon_arr is not None else None
        )
        a_lat = float(lat_arr[apex_idx]) if lat_arr is not None else None
        a_lon = float(lon_arr[apex_idx]) if lon_arr is not None else None

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
                apex_type=_classify_apex(apex_idx, geo_apex_idx, entry_idx, exit_idx),
                brake_point_lat=bp_lat,
                brake_point_lon=bp_lon,
                apex_lat=a_lat,
                apex_lon=a_lon,
            )
        )

    return corners

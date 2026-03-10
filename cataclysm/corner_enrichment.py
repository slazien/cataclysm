"""Telemetry-driven corner metadata enrichment.

This module fills missing corner metadata fields from lap telemetry while
preserving curated track_db values when present.
"""

from __future__ import annotations

import logging
import math

import numpy as np
from scipy.signal import savgol_filter

from cataclysm.corner_classifier import classify_corner
from cataclysm.corners import Corner

logger = logging.getLogger(__name__)

# Character classification thresholds
CHAR_BRAKE_PCT_THRESHOLD = 5.0
CHAR_BRAKE_DURATION_M = 1.0
CHAR_BRAKE_LONG_G_THRESHOLD = -0.15
CHAR_THROTTLE_DROP_PTS = 15.0
CHAR_MIN_THROTTLE_PCT = 20.0
CHAR_MAX_THROTTLE_PCT = 95.0
CHAR_FLAT_MIN_THROTTLE_PCT = 90.0
CHAR_SPEED_DROP_FLAT_PCT = 3.0
CHAR_SPEED_DROP_LIFT_PCT = 12.0
CHAR_APPROACH_BEFORE_APEX_M = 80.0
CHAR_APPROACH_END_BEFORE_M = 10.0
CHAR_MIN_APPROACH_WINDOW_M = 10.0
CHAR_MAX_PRE_ENTRY_EXTENSION_M = 50.0

# Direction detection
DIRECTION_MIN_HEADING_CHANGE_DEG = 1.0

# Elevation trend detection
ELEVATION_FLAT_THRESHOLD_PCT = 2.0
ELEVATION_GRADE_THRESHOLD_PCT = 2.0
ELEVATION_CREST_GRADE_DELTA_PCT = 3.5
ELEVATION_APEX_WINDOW_M = 40.0
ELEVATION_SAVGOL_WINDOW_M = 50.0
ELEVATION_SAVGOL_POLYORDER = 2
ELEVATION_MIN_LAPS_FOR_MEDIAN = 3

# Camber detection
CAMBER_POSITIVE_THRESHOLD_DEG = 1.5
CAMBER_FLAT_THRESHOLD_DEG = 1.5
CAMBER_OFFCAMBER_THRESHOLD_DEG = 4.0
CAMBER_MIN_LAPS = 3
CAMBER_MIN_SPEED_MPS = 5.0
CAMBER_MAX_BRAKE_PCT = 5.0
CAMBER_QUASI_STEADY_PERCENTILE = 85
CAMBER_MID_START_FRAC = 0.15
CAMBER_MID_END_FRAC = 0.85
CAMBER_MIN_SAMPLES = 6
G_ACCEL = 9.81

# Blind apex detection (telemetry-only proxy)
BLIND_DRIVER_EYE_HEIGHT_M = 1.15
BLIND_APEX_TARGET_HEIGHT_M = 0.0
BLIND_CREST_THRESHOLD_M = 0.50
BLIND_HEADING_OFFSET_DEG = 45.0
BLIND_ALT_SMOOTH_WINDOW_M = 50.0
BLIND_MIN_CONSECUTIVE_EXCEEDANCE = 3


def auto_enrich_corner_metadata(
    corners: list[Corner],
    lap_data: dict[str, np.ndarray],
    all_lap_data: dict[int, dict[str, np.ndarray]] | None = None,
) -> list[Corner]:
    """Fill missing corner metadata fields from telemetry.

    Only fields that are currently unset are populated; curated values from the
    track database are preserved.
    """
    if not corners:
        return corners

    speed_p25, speed_p75 = _compute_speed_percentiles(corners)

    for corner in corners:
        _auto_detect_direction(corner, lap_data)

    for corner in corners:
        _auto_detect_character(corner, lap_data, speed_p25, speed_p75)

    for corner in corners:
        _auto_detect_apex_latlon(corner, lap_data)

    for corner in corners:
        _auto_detect_corner_type(corner, lap_data)

    altitude_profile = _build_altitude_profile(lap_data, all_lap_data)

    for corner in corners:
        _auto_detect_elevation_trend(corner, lap_data, altitude_profile)

    if all_lap_data is not None:
        for corner in corners:
            _auto_detect_camber(corner, all_lap_data)

    for corner in corners:
        _auto_detect_blind_crest(corner, lap_data, altitude_profile)

    for corner in corners:
        _auto_generate_coaching_notes(corner)

    return corners


def _auto_detect_direction(
    corner: Corner,
    lap_data: dict[str, np.ndarray],
) -> None:
    """Detect direction from integrated heading change over the corner zone.

    RaceChrono heading is compass bearing (clockwise-positive). Therefore:
    positive integrated change -> right, negative -> left.
    """
    if corner.direction is not None:
        return

    heading = _get_array(lap_data, "heading_deg")
    distance = _get_array(lap_data, "distance_m")
    if heading is None or distance is None or len(heading) != len(distance):
        return

    entry_idx = _search_index(distance, corner.entry_distance_m)
    exit_idx = _search_index(distance, corner.exit_distance_m)
    if exit_idx <= entry_idx:
        return

    total_heading_change = _integrated_heading_change(heading, entry_idx, exit_idx)
    if abs(total_heading_change) < DIRECTION_MIN_HEADING_CHANGE_DEG:
        return

    corner.direction = "right" if total_heading_change > 0 else "left"


def _auto_detect_character(
    corner: Corner,
    lap_data: dict[str, np.ndarray],
    speed_p25: float,
    speed_p75: float,
) -> None:
    """Detect corner character from approach braking, throttle, and speed traces."""
    if corner.character is not None:
        return

    distance = _get_array(lap_data, "distance_m")
    speed = _get_array(lap_data, "speed_mps")
    brake = _get_array(lap_data, "brake_pct")
    throttle = _get_array(lap_data, "throttle_pct")
    long_g = _get_array(lap_data, "longitudinal_g")

    if distance is None or speed is None or brake is None or throttle is None:
        return

    search_start = corner.apex_distance_m - CHAR_APPROACH_BEFORE_APEX_M
    if corner.brake_point_m is not None:
        search_start = min(search_start, corner.brake_point_m - 10.0)
    pre_entry_floor = corner.entry_distance_m - CHAR_MAX_PRE_ENTRY_EXTENSION_M
    window_start = max(0.0, max(search_start, pre_entry_floor))
    window_end = corner.apex_distance_m - CHAR_APPROACH_END_BEFORE_M
    window_end = min(window_end, corner.apex_distance_m)

    if window_end <= window_start:
        window_start = max(0.0, pre_entry_floor)
        window_end = corner.apex_distance_m

    if window_end <= window_start or (window_end - window_start) < CHAR_MIN_APPROACH_WINDOW_M:
        return

    start_idx, end_idx = _slice_window(distance, window_start, window_end)
    if end_idx - start_idx < 2:
        return

    seg_dist = distance[start_idx:end_idx]
    seg_speed = speed[start_idx:end_idx]
    seg_brake = brake[start_idx:end_idx]
    seg_throttle = throttle[start_idx:end_idx]

    max_brake = float(np.max(seg_brake))
    min_throttle = float(np.min(seg_throttle))
    max_throttle = float(np.max(seg_throttle))
    throttle_drop = max_throttle - min_throttle

    entry_speed = float(seg_speed[0])
    min_speed = float(np.min(seg_speed))
    speed_drop_pct = 0.0
    if entry_speed > 1e-6:
        speed_drop_pct = (entry_speed - min_speed) / entry_speed * 100.0

    brake_distance_m = _masked_distance(seg_dist, seg_brake >= CHAR_BRAKE_PCT_THRESHOLD)
    has_sustained_braking = brake_distance_m >= CHAR_BRAKE_DURATION_M

    # Optional secondary decel signal for regen braking / brake channel miss.
    has_decel = False
    has_sustained_decel = False
    if long_g is not None and len(long_g) >= end_idx:
        seg_long_g = long_g[start_idx:end_idx]
        has_decel = bool(np.min(seg_long_g) <= -0.08)
        decel_distance_m = _masked_distance(seg_dist, seg_long_g <= CHAR_BRAKE_LONG_G_THRESHOLD)
        has_sustained_decel = decel_distance_m >= CHAR_BRAKE_DURATION_M
    brake_channel_missing = bool(np.max(seg_brake) < CHAR_BRAKE_PCT_THRESHOLD)

    if (max_brake >= CHAR_BRAKE_PCT_THRESHOLD and has_sustained_braking) or (
        brake_channel_missing and has_sustained_decel
    ):
        corner.character = "brake"
        return

    # Speed-normalized thresholds across vehicle classes.
    span = max(1e-6, speed_p75 - speed_p25)
    speed_norm = float(np.clip((corner.min_speed_mps - speed_p25) / span, 0.0, 1.0))
    flat_drop_threshold = CHAR_SPEED_DROP_FLAT_PCT + 1.5 * speed_norm
    lift_drop_max = CHAR_SPEED_DROP_LIFT_PCT + 2.0 * (1.0 - speed_norm)

    if (
        max_brake < CHAR_BRAKE_PCT_THRESHOLD
        and min_throttle >= CHAR_FLAT_MIN_THROTTLE_PCT
        and speed_drop_pct < flat_drop_threshold
    ):
        corner.character = "flat"
        return

    if (
        max_brake < CHAR_BRAKE_PCT_THRESHOLD
        and throttle_drop > CHAR_THROTTLE_DROP_PTS
        and CHAR_MIN_THROTTLE_PCT <= min_throttle <= CHAR_MAX_THROTTLE_PCT
        and CHAR_SPEED_DROP_FLAT_PCT <= speed_drop_pct <= lift_drop_max
    ):
        corner.character = "lift"
        return

    if max_brake >= CHAR_BRAKE_PCT_THRESHOLD or (
        speed_drop_pct > 8.0 and (has_decel or has_sustained_decel)
    ):
        corner.character = "brake"


def _auto_detect_apex_latlon(
    corner: Corner,
    lap_data: dict[str, np.ndarray],
) -> None:
    """Fill apex GPS location from telemetry when missing."""
    if corner.apex_lat is not None and corner.apex_lon is not None:
        return

    distance = _get_array(lap_data, "distance_m")
    lat = _get_array(lap_data, "lat")
    lon = _get_array(lap_data, "lon")
    if distance is None or lat is None or lon is None:
        return

    apex_idx = _search_index(distance, corner.apex_distance_m)
    if corner.apex_lat is None:
        corner.apex_lat = float(lat[apex_idx])
    if corner.apex_lon is None:
        corner.apex_lon = float(lon[apex_idx])


def _auto_detect_corner_type(
    corner: Corner,
    lap_data: dict[str, np.ndarray],
) -> None:
    """Classify corner type from geometry + speed-loss features."""
    if corner.corner_type_hint is not None:
        return

    distance = _get_array(lap_data, "distance_m")
    heading = _get_array(lap_data, "heading_deg")
    speed = _get_array(lap_data, "speed_mps")
    if distance is None or heading is None or speed is None:
        return

    entry_idx = _search_index(distance, corner.entry_distance_m)
    exit_idx = _search_index(distance, corner.exit_distance_m)
    if exit_idx <= entry_idx + 1:
        return

    arc_length_m = float(distance[exit_idx] - distance[entry_idx])
    if arc_length_m <= 0.0:
        return

    heading_change_deg = abs(_integrated_heading_change(heading, entry_idx, exit_idx))

    signed_curvature = _compute_signed_curvature(distance, heading)
    curv_slice = signed_curvature[entry_idx : exit_idx + 1]
    peak_curvature = float(np.max(np.abs(curv_slice))) if len(curv_slice) else 0.0

    speed_slice = speed[entry_idx : exit_idx + 1]
    entry_speed = float(speed_slice[0]) if len(speed_slice) else 0.0
    min_speed = float(np.min(speed_slice)) if len(speed_slice) else 0.0
    speed_loss_pct = 0.0
    if entry_speed > 1e-6:
        speed_loss_pct = max(0.0, (entry_speed - min_speed) / entry_speed * 100.0)

    cvi = 0.0
    if len(curv_slice) > 1:
        mean_abs = float(np.mean(np.abs(curv_slice)))
        if mean_abs > 1e-9:
            cvi = float(np.std(curv_slice) / (mean_abs + 1e-9))

    classification = classify_corner(
        peak_curvature=peak_curvature,
        heading_change_deg=heading_change_deg,
        arc_length_m=arc_length_m,
        speed_loss_pct=speed_loss_pct,
        curvature_variation_index=cvi,
    )
    corner.corner_type_hint = classification.corner_type


def _auto_detect_elevation_trend(
    corner: Corner,
    lap_data: dict[str, np.ndarray],
    altitude_profile: np.ndarray | None,
) -> None:
    """Detect elevation trend from altitude profile if not curated."""
    if corner.elevation_trend is not None:
        return

    distance = _get_array(lap_data, "distance_m")
    if distance is None or altitude_profile is None or len(distance) != len(altitude_profile):
        return

    entry_idx = _search_index(distance, corner.entry_distance_m)
    apex_idx = _search_index(distance, corner.apex_distance_m)
    exit_idx = _search_index(distance, corner.exit_distance_m)
    if not (entry_idx < apex_idx < exit_idx):
        return

    entry_alt = float(altitude_profile[entry_idx])
    exit_alt = float(altitude_profile[exit_idx])
    horiz_dist = float(distance[exit_idx] - distance[entry_idx])
    gradient_pct = ((exit_alt - entry_alt) / horiz_dist * 100.0) if horiz_dist > 0 else 0.0

    trend = _classify_elevation_trend(
        distance, altitude_profile, apex_idx, entry_idx, exit_idx, gradient_pct
    )
    corner.elevation_trend = trend


def _auto_detect_camber(
    corner: Corner,
    all_lap_data: dict[int, dict[str, np.ndarray]],
) -> None:
    """Estimate road camber/banking from multi-lap lateral acceleration residuals."""
    if corner.camber is not None:
        return
    if len(all_lap_data) < CAMBER_MIN_LAPS:
        return

    x_kin: list[float] = []
    y_imu: list[float] = []

    total_samples = 0
    quasi_steady_samples = 0
    speed_valid_samples = 0
    brake_valid_samples = 0
    finite_valid_samples = 0
    final_valid_samples = 0

    for lap_num, lap in all_lap_data.items():
        distance = _get_array(lap, "distance_m")
        heading = _get_array(lap, "heading_deg")
        speed = _get_array(lap, "speed_mps")
        lateral_g = _get_array(lap, "lateral_g")
        brake = _get_array(lap, "brake_pct")
        if (
            distance is None
            or heading is None
            or speed is None
            or lateral_g is None
            or brake is None
            or len(distance) < 4
        ):
            continue

        # Mid-corner window avoids entry/exit transients.
        corner_len = max(1.0, corner.exit_distance_m - corner.entry_distance_m)
        zone_start = corner.entry_distance_m + CAMBER_MID_START_FRAC * corner_len
        zone_end = corner.entry_distance_m + CAMBER_MID_END_FRAC * corner_len
        if zone_end <= zone_start:
            continue

        start_idx, end_idx = _slice_window(distance, zone_start, zone_end)
        if end_idx - start_idx < 3:
            continue

        curvature = _compute_signed_curvature(distance, heading)
        curv_seg = curvature[start_idx:end_idx]
        speed_seg = speed[start_idx:end_idx]
        brake_seg = brake[start_idx:end_idx]
        lat_g_seg = lateral_g[start_idx:end_idx]

        # Quasi-steady sample filter.
        kin_seg = speed_seg * speed_seg * curv_seg
        kin_diff = np.abs(np.diff(kin_seg, prepend=kin_seg[0]))
        steady_threshold = float(np.percentile(kin_diff, CAMBER_QUASI_STEADY_PERCENTILE))
        steady_mask = kin_diff <= steady_threshold

        speed_mask = speed_seg >= CAMBER_MIN_SPEED_MPS
        brake_mask = brake_seg <= CAMBER_MAX_BRAKE_PCT
        finite_mask = np.isfinite(kin_seg) & np.isfinite(lat_g_seg)

        valid = speed_mask & brake_mask & finite_mask & steady_mask
        total_samples += len(valid)
        quasi_steady_samples += int(np.sum(steady_mask))
        speed_valid_samples += int(np.sum(speed_mask))
        brake_valid_samples += int(np.sum(brake_mask))
        finite_valid_samples += int(np.sum(finite_mask))
        final_valid_samples += int(np.sum(valid))
        if not np.any(valid):
            logger.debug(
                "T%d camber lap %d rejected: total=%d steady=%d speed=%d brake=%d finite=%d",
                corner.number,
                lap_num,
                len(valid),
                int(np.sum(steady_mask)),
                int(np.sum(speed_mask)),
                int(np.sum(brake_mask)),
                int(np.sum(finite_mask)),
            )
            continue

        x_kin.extend(kin_seg[valid].tolist())
        y_imu.extend((lat_g_seg[valid] * G_ACCEL).tolist())

    logger.debug(
        ("T%d camber aggregate: laps=%d total=%d steady=%d speed=%d brake=%d finite=%d valid=%d"),
        corner.number,
        len(all_lap_data),
        total_samples,
        quasi_steady_samples,
        speed_valid_samples,
        brake_valid_samples,
        finite_valid_samples,
        final_valid_samples,
    )

    if len(x_kin) < CAMBER_MIN_SAMPLES:
        return

    x_arr = np.asarray(x_kin, dtype=float)
    y_arr = np.asarray(y_imu, dtype=float)

    mean_kin = float(np.mean(x_arr))
    if abs(mean_kin) > 1e-6:
        turn_sign = 1.0 if mean_kin > 0 else -1.0
    elif corner.direction is not None:
        turn_sign = 1.0 if corner.direction == "left" else -1.0
    else:
        turn_sign = 1.0

    # y ~= x - sign(turn)*g*sin(phi) + noise, so use mean residual for robust
    # bank angle estimation even when x has limited variance.
    mean_residual = float(np.mean(y_arr - x_arr))
    ratio = float(np.clip((-mean_residual * turn_sign) / G_ACCEL, -0.3, 0.3))
    phi_deg = math.degrees(math.asin(ratio))
    corner.banking_deg = round(phi_deg, 2)

    if phi_deg > CAMBER_POSITIVE_THRESHOLD_DEG:
        corner.camber = "positive"
    elif phi_deg < -CAMBER_OFFCAMBER_THRESHOLD_DEG:
        corner.camber = "off-camber"
    elif phi_deg < -CAMBER_FLAT_THRESHOLD_DEG:
        corner.camber = "negative"
    else:
        corner.camber = "flat"


def _auto_detect_blind_crest(
    corner: Corner,
    lap_data: dict[str, np.ndarray],
    altitude_profile: np.ndarray | None,
) -> None:
    """Mark blind corners using crest and heading-offset proxies.

    Limitation: this is telemetry-only. It cannot detect lateral line-of-sight
    blockers (walls, barriers, trees).
    """
    if corner.blind:
        return

    distance = _get_array(lap_data, "distance_m")
    heading = _get_array(lap_data, "heading_deg")
    lat = _get_array(lap_data, "lat")
    lon = _get_array(lap_data, "lon")
    if (
        distance is None
        or altitude_profile is None
        or heading is None
        or lat is None
        or lon is None
        or len(distance) < 3
    ):
        return

    turnin_dist = (
        corner.brake_point_m if corner.brake_point_m is not None else corner.entry_distance_m
    )
    turnin_idx = _search_index(distance, turnin_dist)
    apex_idx = _search_index(distance, corner.apex_distance_m)
    if apex_idx <= turnin_idx + 2:
        return

    crest_blind = _check_crest_blindness(distance, altitude_profile, turnin_idx, apex_idx)
    horizontal_blind = _check_horizontal_blindness(
        distance, heading, lat, lon, turnin_idx, apex_idx
    )
    corner.blind = crest_blind or horizontal_blind


def _auto_generate_coaching_notes(corner: Corner) -> None:
    """Generate deterministic fallback coaching notes from metadata."""
    if corner.coaching_notes is not None:
        return

    if corner.character is None:
        return

    supporting_signals = (
        int(corner.elevation_trend is not None)
        + int(corner.camber is not None)
        + int(bool(corner.blind))
        + int(corner.corner_type_hint is not None)
    )
    if supporting_signals < 1:
        return

    parts: list[str] = []

    if corner.character == "brake":
        parts.append("Trail-brake to apex")
    elif corner.character == "lift":
        parts.append("Smooth lift before turn-in")

    if corner.elevation_trend == "downhill":
        parts.append("Brake earlier on downhill approach")
    elif corner.elevation_trend == "uphill":
        parts.append("Power may be limited on exit")
    elif corner.elevation_trend == "crest":
        parts.append("Car unloads over crest so keep inputs smooth")
    elif corner.elevation_trend == "compression":
        parts.append("Grip builds in compression so carry speed progressively")

    if corner.camber == "off-camber":
        parts.append("Off-camber surface reduces grip so avoid overdriving")
    elif corner.camber == "negative":
        parts.append("Slightly off-camber so adjust turn-in patience")
    elif corner.camber == "positive":
        parts.append("Banked camber supports extra mid-corner grip")

    if corner.blind:
        parts.append("Blind apex so commit to fixed reference points")

    if corner.corner_type_hint == "hairpin":
        parts.append("Trail-brake to rotate. Slow in, fast out")
    elif corner.corner_type_hint == "sweeper":
        parts.append("Smooth, progressive steering. Maintain constant radius")
    elif corner.corner_type_hint == "kink":
        parts.append("Commit early. Smooth inputs — avoid lifting mid-corner")
    elif corner.corner_type_hint == "carousel":
        parts.append("Maintain steady radius and throttle through the arc")

    if parts:
        corner.coaching_notes = ". ".join(parts) + "."


def _classify_elevation_trend(
    distance: np.ndarray,
    altitude: np.ndarray,
    apex_idx: int,
    entry_idx: int,
    exit_idx: int,
    gradient_pct: float,
) -> str:
    if exit_idx <= entry_idx:
        return "flat"

    grade_pct = np.gradient(altitude, distance, edge_order=1) * 100.0
    apex_dist = float(distance[apex_idx])

    pre_start, pre_end = _slice_window(
        distance,
        max(float(distance[entry_idx]), apex_dist - ELEVATION_APEX_WINDOW_M),
        apex_dist,
    )
    post_start, post_end = _slice_window(
        distance,
        apex_dist,
        min(float(distance[exit_idx]), apex_dist + ELEVATION_APEX_WINDOW_M),
    )

    pre_grade = float(np.mean(grade_pct[pre_start:pre_end])) if pre_end > pre_start else 0.0
    post_grade = float(np.mean(grade_pct[post_start:post_end])) if post_end > post_start else 0.0
    grade_delta = abs(pre_grade - post_grade)

    if pre_grade > 0.0 and post_grade < 0.0 and grade_delta > ELEVATION_CREST_GRADE_DELTA_PCT:
        return "crest"
    if pre_grade < 0.0 and post_grade > 0.0 and grade_delta > ELEVATION_CREST_GRADE_DELTA_PCT:
        return "compression"

    if abs(gradient_pct) < ELEVATION_FLAT_THRESHOLD_PCT:
        return "flat"
    if gradient_pct > ELEVATION_GRADE_THRESHOLD_PCT:
        return "uphill"
    if gradient_pct < -ELEVATION_GRADE_THRESHOLD_PCT:
        return "downhill"
    return "flat"


def _check_crest_blindness(
    distance: np.ndarray,
    altitude: np.ndarray,
    turnin_idx: int,
    apex_idx: int,
) -> bool:
    total_dist = float(distance[apex_idx] - distance[turnin_idx])
    if total_dist < 1.0:
        return False

    # Keep altitude smoothing scale proportional on short approaches so we do
    # not fully erase real crests between turn-in and apex.
    smooth_window_m = min(BLIND_ALT_SMOOTH_WINDOW_M, max(10.0, total_dist / 2.0))
    smooth_alt = _smooth_altitude(altitude, distance, smooth_window_m)

    eye_z = float(smooth_alt[turnin_idx] + BLIND_DRIVER_EYE_HEIGHT_M)
    target_z = float(smooth_alt[apex_idx] + BLIND_APEX_TARGET_HEIGHT_M)

    exceedances: list[bool] = []
    for idx in range(turnin_idx + 1, apex_idx):
        t = float((distance[idx] - distance[turnin_idx]) / total_dist)
        los_z = eye_z + t * (target_z - eye_z)
        exceedances.append(float(smooth_alt[idx] - los_z) > BLIND_CREST_THRESHOLD_M)
    return _has_min_consecutive_true(exceedances, BLIND_MIN_CONSECUTIVE_EXCEEDANCE)


def _check_horizontal_blindness(
    distance: np.ndarray,
    heading: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    turnin_idx: int,
    apex_idx: int,
) -> bool:
    _ = distance  # Keep signature parallel to crest check.
    driver_heading = float(heading[turnin_idx])
    bearing_to_apex = _compute_bearing(
        float(lat[turnin_idx]),
        float(lon[turnin_idx]),
        float(lat[apex_idx]),
        float(lon[apex_idx]),
    )
    offset = abs((bearing_to_apex - driver_heading + 180.0) % 360.0 - 180.0)
    return offset > BLIND_HEADING_OFFSET_DEG


def _compute_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    d_lon = math.radians(lon2 - lon1)
    x = math.sin(d_lon) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def _compute_speed_percentiles(corners: list[Corner]) -> tuple[float, float]:
    speeds = np.asarray([c.min_speed_mps for c in corners if c.min_speed_mps > 0.0], dtype=float)
    if len(speeds) < 3:
        return 15.0, 40.0
    return float(np.percentile(speeds, 25.0)), float(np.percentile(speeds, 75.0))


def _compute_signed_curvature(distance: np.ndarray, heading: np.ndarray) -> np.ndarray:
    if len(distance) < 2 or len(heading) < 2:
        return np.zeros_like(distance, dtype=float)

    d_heading = np.diff(heading)
    d_heading = (d_heading + 180.0) % 360.0 - 180.0
    d_heading_rad = np.deg2rad(d_heading)
    ds = np.diff(distance)
    ds = np.where(np.abs(ds) < 1e-6, 1e-6, ds)

    curvature = np.zeros_like(distance, dtype=float)
    curvature[1:] = d_heading_rad / ds
    if len(curvature) > 1:
        curvature[0] = curvature[1]
    return curvature


def _integrated_heading_change(heading: np.ndarray, entry_idx: int, exit_idx: int) -> float:
    diff = np.diff(heading[entry_idx : exit_idx + 1])
    wrapped = (diff + 180.0) % 360.0 - 180.0
    return float(np.sum(wrapped))


def _smooth_altitude(altitude: np.ndarray, distance: np.ndarray, window_m: float) -> np.ndarray:
    if len(altitude) < 3:
        return altitude
    deltas = np.diff(distance)
    mean_step = float(np.mean(deltas)) if len(deltas) else 1.0
    if mean_step <= 0.0:
        mean_step = 1.0

    window_pts = max(5, int(round(window_m / mean_step)))
    if window_pts % 2 == 0:
        window_pts += 1
    if window_pts >= len(altitude):
        window_pts = len(altitude) - 1 if len(altitude) % 2 == 0 else len(altitude)
    if window_pts < 5:
        return altitude

    polyorder = min(ELEVATION_SAVGOL_POLYORDER, window_pts - 1)
    return np.asarray(savgol_filter(altitude, window_length=window_pts, polyorder=polyorder))


def _build_altitude_profile(
    lap_data: dict[str, np.ndarray],
    all_lap_data: dict[int, dict[str, np.ndarray]] | None,
) -> np.ndarray | None:
    distance = _get_array(lap_data, "distance_m")
    altitude = _get_array(lap_data, "altitude_m")
    if distance is None or altitude is None or len(distance) != len(altitude):
        return None

    altitude_samples: list[np.ndarray] = [altitude]
    if all_lap_data is not None and len(all_lap_data) >= ELEVATION_MIN_LAPS_FOR_MEDIAN:
        for lap in all_lap_data.values():
            lap_distance = _get_array(lap, "distance_m")
            lap_altitude = _get_array(lap, "altitude_m")
            if lap_distance is None or lap_altitude is None:
                continue
            if len(lap_distance) < 3 or len(lap_altitude) != len(lap_distance):
                continue
            finite_mask = np.isfinite(lap_distance) & np.isfinite(lap_altitude)
            if int(np.sum(finite_mask)) < 3:
                continue
            lap_distance_finite = lap_distance[finite_mask]
            lap_altitude_finite = lap_altitude[finite_mask]
            if not np.all(np.diff(lap_distance_finite) > 0):
                continue
            interp_alt = np.interp(
                distance,
                lap_distance_finite,
                lap_altitude_finite,
                left=np.nan,
                right=np.nan,
            )
            altitude_samples.append(interp_alt)

    if len(altitude_samples) >= ELEVATION_MIN_LAPS_FOR_MEDIAN:
        altitude_profile = np.nanmedian(np.vstack(altitude_samples), axis=0)
    else:
        altitude_profile = altitude
    altitude_profile = np.asarray(altitude_profile, dtype=float)
    if not np.all(np.isfinite(altitude_profile)):
        finite_mask = np.isfinite(altitude_profile)
        if int(np.sum(finite_mask)) < 3:
            return None
        altitude_profile = np.interp(
            distance,
            distance[finite_mask],
            altitude_profile[finite_mask],
            left=float(altitude_profile[finite_mask][0]),
            right=float(altitude_profile[finite_mask][-1]),
        )
    return _smooth_altitude(
        np.asarray(altitude_profile, dtype=float), distance, ELEVATION_SAVGOL_WINDOW_M
    )


def _has_min_consecutive_true(values: list[bool], min_run: int) -> bool:
    run = 0
    for is_true in values:
        if is_true:
            run += 1
            if run >= min_run:
                return True
        else:
            run = 0
    return False


def _masked_distance(distance: np.ndarray, mask: np.ndarray) -> float:
    if len(distance) < 2 or len(mask) < 2:
        return 0.0
    deltas = np.diff(distance)
    return float(np.sum(deltas[mask[:-1]]))


def _slice_window(distance: np.ndarray, start_m: float, end_m: float) -> tuple[int, int]:
    start_idx = int(np.searchsorted(distance, start_m, side="left"))
    end_idx = int(np.searchsorted(distance, end_m, side="right"))
    start_idx = max(0, min(start_idx, len(distance) - 1))
    end_idx = max(start_idx + 1, min(end_idx, len(distance)))
    return start_idx, end_idx


def _search_index(distance: np.ndarray, target_m: float) -> int:
    idx = int(np.searchsorted(distance, target_m, side="left"))
    return max(0, min(idx, len(distance) - 1))


def _get_array(lap_data: dict[str, np.ndarray], key: str) -> np.ndarray | None:
    arr = lap_data.get(key)
    if arr is None:
        return None
    return np.asarray(arr, dtype=float)

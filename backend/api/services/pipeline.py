"""Pipeline service: wraps cataclysm/ processing functions.

Orchestrates the full CSV-to-analysis pipeline:
  CSV bytes -> parser.parse_racechrono_csv -> engine.process_session
  -> corners/consistency/gains/grip -> session snapshot

All CPU-bound cataclysm functions are run via asyncio.to_thread().
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import io
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
from cataclysm.banking import apply_banking_to_mu_array
from cataclysm.consistency import compute_session_consistency
from cataclysm.constants import MPS_TO_MPH
from cataclysm.corner_enrichment import auto_enrich_corner_metadata
from cataclysm.corner_line import analyze_corner_lines
from cataclysm.corners import Corner, detect_corners, extract_corner_kpis_for_lap
from cataclysm.curvature import CurvatureResult, compute_curvature
from cataclysm.elevation import compute_corner_elevation, enrich_corners_with_elevation
from cataclysm.elevation_profile import compute_gradient_array, compute_vertical_curvature
from cataclysm.engine import LapSummary, ProcessedSession, find_anomalous_laps, process_session
from cataclysm.equipment import CATEGORY_MU_DEFAULTS, equipment_to_vehicle_params
from cataclysm.gains import (
    GainEstimate,
    build_segments,
    compute_segment_times,
    estimate_gains,
    reconstruct_ideal_lap,
)
from cataclysm.gps_line import (
    build_gps_trace,
    compute_reference_centerline,
    should_enable_line_analysis,
)
from cataclysm.gps_quality import GPSQualityReport, assess_gps_quality
from cataclysm.grip import estimate_grip_limit
from cataclysm.grip_calibration import (
    apply_calibration_to_params,
    calibrate_grip_from_telemetry,
    calibrate_per_corner_grip,
)
from cataclysm.lap_tags import LapTagStore
from cataclysm.linked_corners import detect_linked_corners
from cataclysm.optimal_comparison import (
    APEX_WINDOW_FRACTION,
    MIN_APEX_WINDOW_M,
    compare_with_optimal,
)
from cataclysm.parser import ParsedSession, parse_racechrono_csv
from cataclysm.track_db import TrackLayout, locate_official_corners
from cataclysm.track_match import detect_track_or_lookup
from cataclysm.track_reference import (
    align_reference_to_session,
    get_track_reference,
    maybe_update_track_reference,
    track_slug_from_layout,
)
from cataclysm.trends import SessionSnapshot, build_session_snapshot
from cataclysm.velocity_profile import (
    OptimalProfile,
    VehicleParams,
    compute_optimal_profile,
    default_vehicle_params,
)

from backend.api.services import equipment_store
from backend.api.services.db_physics_cache import (
    db_get_cached,
    db_get_cached_by_track,
    db_invalidate_profile,
    db_invalidate_session,
    db_invalidate_track,
    db_set_cached,
    db_set_cached_by_track,
)
from backend.api.services.session_store import SessionData, store_session
from backend.api.services.track_corners import get_corner_override_version

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Physics result cache: avoids recomputing velocity solver on repeated requests.
# Key = (f"{session_id}:{endpoint}", profile_id_or_None)
# Value = (result_dict, timestamp)
# ---------------------------------------------------------------------------
_physics_cache: dict[tuple[str, str | None], tuple[dict[str, object], float]] = {}
PHYSICS_CACHE_TTL_S = 1800  # 30 minutes
PHYSICS_CACHE_MAX_ENTRIES = 200  # ~100 sessions × 2 endpoints


def _current_profile_id(session_id: str) -> str | None:
    """Return the equipment profile ID assigned to a session, or None."""
    se = equipment_store.get_session_equipment(session_id)
    return se.profile_id if se is not None else None


def _get_physics_cached(
    session_id: str,
    key_suffix: str,
    profile_id: str | None = None,
) -> dict[str, object] | None:
    if profile_id is None:
        profile_id = _current_profile_id(session_id)
    cache_key = (f"{session_id}:{key_suffix}", profile_id)
    entry = _physics_cache.get(cache_key)
    if entry and (time.time() - entry[1]) < PHYSICS_CACHE_TTL_S:
        logger.debug("Physics cache HIT for %s", cache_key)
        return entry[0]
    return None


def _set_physics_cached(
    session_id: str,
    key_suffix: str,
    result: dict[str, object],
    profile_id: str | None = None,
) -> None:
    if profile_id is None:
        profile_id = _current_profile_id(session_id)
    cache_key = (f"{session_id}:{key_suffix}", profile_id)
    _physics_cache[cache_key] = (result, time.time())
    # LRU eviction: drop oldest entry when cache exceeds max size
    if len(_physics_cache) > PHYSICS_CACHE_MAX_ENTRIES:
        oldest_key = min(_physics_cache, key=lambda k: _physics_cache[k][1])
        del _physics_cache[oldest_key]


def invalidate_physics_cache(session_id: str) -> None:
    """Clear all physics cache entries for a session (in-memory + DB)."""
    keys_to_remove = [k for k in _physics_cache if k[0].startswith(f"{session_id}:")]
    for k in keys_to_remove:
        del _physics_cache[k]
    if keys_to_remove:
        logger.info(
            "Invalidated %d in-memory physics cache entries for session %s",
            len(keys_to_remove),
            session_id,
        )
    # Fire-and-forget DB invalidation — only schedule if an event loop is running.
    # get_running_loop() raises RuntimeError in sync/threadpool context; suppress it.
    with contextlib.suppress(RuntimeError):
        asyncio.get_running_loop().create_task(db_invalidate_session(session_id))


async def invalidate_profile_cache(profile_id: str) -> None:
    """Clear all physics cache entries using a specific profile (in-memory + DB)."""
    keys_to_remove = [k for k in _physics_cache if k[1] == profile_id]
    for k in keys_to_remove:
        del _physics_cache[k]
    # Also clear track-level in-memory cache entries for this profile
    track_keys_to_remove = [tk for tk in _track_physics_cache if tk[1] == profile_id]
    for tk in track_keys_to_remove:
        del _track_physics_cache[tk]
    total = len(keys_to_remove) + len(track_keys_to_remove)
    if total:
        logger.info(
            "Invalidated %d in-memory physics cache entries for profile %s "
            "(%d session-level, %d track-level)",
            total,
            profile_id,
            len(keys_to_remove),
            len(track_keys_to_remove),
        )
    await db_invalidate_profile(profile_id)


# ---------------------------------------------------------------------------
# Track-level physics cache: shares optimal profile across sessions on the
# same track with the same equipment. Key includes calibrated_mu (2dp) so
# sessions with materially different grip don't share.
# Key = (f"{track_slug}:{endpoint}", profile_id_or_None, calibrated_mu_str)
# Value = (result_dict, timestamp)
# ---------------------------------------------------------------------------
_track_physics_cache: dict[tuple[str, str | None, str], tuple[dict[str, object], float]] = {}
TRACK_CACHE_TTL_S = 3600  # 1 hour — track geometry doesn't change

_CORNER_METADATA_PROPAGATION_FIELDS: tuple[str, ...] = (
    "character",
    "direction",
    "corner_type_hint",
    "elevation_trend",
    "camber",
    "coaching_notes",
    "banking_deg",
    "apex_lat",
    "apex_lon",
)


def _maybe_float_array(lap_df: Any, column: str) -> np.ndarray | None:
    """Best-effort conversion of a lap DataFrame column to float array."""
    try:
        values = lap_df[column].to_numpy(dtype=float)
    except (KeyError, AttributeError, TypeError, ValueError):
        return None
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1 or len(arr) == 0:
        return None
    return arr


def _build_corner_enrichment_arrays(
    lap_df: Any,
    *,
    include_altitude: bool = True,
    include_throttle: bool = True,
    include_longitudinal: bool = True,
) -> dict[str, np.ndarray]:
    """Build lap arrays consumed by auto_enrich_corner_metadata()."""
    arrays: dict[str, np.ndarray] = {}

    column_map = {
        "distance_m": "lap_distance_m",
        "speed_mps": "speed_mps",
        "heading_deg": "heading_deg",
        "lateral_g": "lateral_g",
        "brake_pct": "brake_pct",
        "lat": "lat",
        "lon": "lon",
    }
    if include_altitude:
        column_map["altitude_m"] = "altitude_m"
    if include_throttle:
        column_map["throttle_pct"] = "throttle_pct"
    if include_longitudinal:
        column_map["longitudinal_g"] = "longitudinal_g"

    for output_key, column_name in column_map.items():
        arr = _maybe_float_array(lap_df, column_name)
        if arr is not None:
            arrays[output_key] = arr

    if "distance_m" not in arrays:
        msg = "corner enrichment requires lap_distance_m"
        raise ValueError(msg)

    return arrays


def _propagate_corner_metadata(
    reference_corners: list[Corner],
    lap_corners: list[Corner],
) -> None:
    """Copy metadata from reference corners to lap corners when missing."""
    ref_by_number = {corner.number: corner for corner in reference_corners}
    for lap_corner in lap_corners:
        ref_corner = ref_by_number.get(lap_corner.number)
        if ref_corner is None:
            continue
        for field_name in _CORNER_METADATA_PROPAGATION_FIELDS:
            if (
                getattr(lap_corner, field_name) is None
                and getattr(ref_corner, field_name) is not None
            ):
                setattr(lap_corner, field_name, getattr(ref_corner, field_name))
        if (not lap_corner.blind) and ref_corner.blind:
            lap_corner.blind = True


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two coordinates."""
    earth_radius_m = 6_371_000.0
    rlat1, rlon1 = np.radians(lat1), np.radians(lon1)
    rlat2, rlon2 = np.radians(lat2), np.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = np.sin(dlat / 2) ** 2 + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
    return float(earth_radius_m * 2 * np.arcsin(np.sqrt(a)))


def _downsample_series(values: np.ndarray, max_points: int = 350) -> np.ndarray:
    """Return evenly sampled values with a hard cap on point count."""
    n = len(values)
    if n <= max_points:
        return values
    idx = np.linspace(0, n - 1, max_points, dtype=int)
    return values[idx]


def _mean_bidirectional_nn_distance_m(
    src_lats: np.ndarray,
    src_lons: np.ndarray,
    dst_lats: np.ndarray,
    dst_lons: np.ndarray,
) -> float:
    """Symmetric nearest-neighbor distance between two traces in meters."""
    if len(src_lats) == 0 or len(dst_lats) == 0:
        return float("inf")
    lat0 = float(np.mean(np.concatenate([src_lats, dst_lats])))
    lon0 = float(np.mean(np.concatenate([src_lons, dst_lons])))
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * np.cos(np.radians(lat0))

    sx = (src_lons - lon0) * lon_scale
    sy = (src_lats - lat0) * lat_scale
    dx = (dst_lons - lon0) * lon_scale
    dy = (dst_lats - lat0) * lat_scale

    spts = np.column_stack([sx, sy])
    dpts = np.column_stack([dx, dy])
    sq_dist = np.sum((spts[:, None, :] - dpts[None, :, :]) ** 2, axis=2)
    src_to_dst = np.sqrt(np.min(sq_dist, axis=1))
    dst_to_src = np.sqrt(np.min(sq_dist, axis=0))
    return float((np.mean(src_to_dst) + np.mean(dst_to_src)) / 2.0)


def _score_osm_candidate(
    *,
    session_lats: np.ndarray,
    session_lons: np.ndarray,
    session_length_m: float,
    centroid_lat: float,
    centroid_lon: float,
    candidate_lats: np.ndarray,
    candidate_lons: np.ndarray,
    candidate_length_m: float,
) -> tuple[float, dict[str, float]]:
    """Score OSM candidate quality using centroid, length, loop closure, and shape."""
    cand_center_lat = float(np.mean(candidate_lats))
    cand_center_lon = float(np.mean(candidate_lons))
    center_dist_m = _haversine_m(centroid_lat, centroid_lon, cand_center_lat, cand_center_lon)
    length_error_m = abs(candidate_length_m - session_length_m)
    loop_gap_m = _haversine_m(
        float(candidate_lats[0]),
        float(candidate_lons[0]),
        float(candidate_lats[-1]),
        float(candidate_lons[-1]),
    )
    loop_tol_m = max(30.0, 0.02 * candidate_length_m)
    loop_penalty = max(0.0, loop_gap_m - loop_tol_m) * 5.0

    shape_error_m = _mean_bidirectional_nn_distance_m(
        _downsample_series(session_lats),
        _downsample_series(session_lons),
        _downsample_series(candidate_lats),
        _downsample_series(candidate_lons),
    )
    score = center_dist_m + (1.8 * length_error_m) + (0.8 * shape_error_m) + loop_penalty
    return score, {
        "center_dist_m": center_dist_m,
        "length_error_m": length_error_m,
        "shape_error_m": shape_error_m,
        "loop_gap_m": loop_gap_m,
        "score": score,
    }


def _layout_to_corner_rows(layout: TrackLayout) -> list[dict[str, object]]:
    """Convert TrackLayout corners to TrackCornerV2 upsert payload rows."""
    rows: list[dict[str, object]] = []
    for c in layout.corners:
        rows.append(
            {
                "number": c.number,
                "name": c.name,
                "fraction": c.fraction,
                "lat": c.lat,
                "lon": c.lon,
                "character": c.character,
                "direction": c.direction,
                "corner_type": c.corner_type,
                "elevation_trend": c.elevation_trend,
                "camber": c.camber,
                "blind": c.blind,
                "coaching_notes": c.coaching_notes,
                "auto_detected": False,
                "confidence": 1.0,
                "detection_method": "manual",
            }
        )
    return rows


def _layout_to_landmark_rows(layout: TrackLayout) -> list[dict[str, object]]:
    """Convert TrackLayout landmarks to TrackLandmark upsert payload rows."""
    rows: list[dict[str, object]] = []
    for lm in layout.landmarks:
        rows.append(
            {
                "name": lm.name,
                "distance_m": lm.distance_m,
                "landmark_type": lm.landmark_type.value,
                "lat": lm.lat,
                "lon": lm.lon,
                "description": lm.description,
                "source": "metadata-bootstrap",
            }
        )
    return rows


def _corner_hash_rows(corners: list[Any]) -> list[dict[str, object]]:
    """Build stable corner dict rows for content-hash versioning."""
    rows: list[dict[str, object]] = []
    for c in corners:
        rows.append(
            {
                "number": c.number,
                "name": c.name,
                "fraction": c.fraction,
                "character": c.character,
                "direction": c.direction,
                "corner_type": c.corner_type,
                "elevation_trend": c.elevation_trend,
                "camber": c.camber,
                "blind": bool(c.blind),
                "coaching_notes": c.coaching_notes,
                "lat": c.lat,
                "lon": c.lon,
            }
        )
    return rows


def _apply_layout_to_session(
    session_data: SessionData,
    layout: TrackLayout,
    corner_version: str | None,
) -> bool:
    """Apply a detected layout to an already processed in-memory session."""
    if not layout.corners:
        return False

    best_lap_df = session_data.processed.resampled_laps[session_data.processed.best_lap]
    skeletons = locate_official_corners(best_lap_df, layout)
    corners = extract_corner_kpis_for_lap(best_lap_df, skeletons)
    if not corners:
        return False

    all_lap_corners: dict[int, list[Corner]] = {}
    for lap_num in session_data.coaching_laps:
        lap_df = session_data.processed.resampled_laps[lap_num]
        if lap_num == session_data.processed.best_lap:
            all_lap_corners[lap_num] = corners
        else:
            all_lap_corners[lap_num] = extract_corner_kpis_for_lap(lap_df, corners)

    try:
        elev = compute_corner_elevation(best_lap_df, corners)
        if elev:
            enrich_corners_with_elevation(all_lap_corners, elev)
    except (ValueError, KeyError, IndexError):
        logger.warning(
            "Failed elevation enrichment while applying layout to session %s",
            session_data.session_id,
            exc_info=True,
        )

    try:
        best_lap_arrays = _build_corner_enrichment_arrays(best_lap_df)
        all_laps_arrays: dict[int, dict[str, np.ndarray]] = {}
        for lap_num in session_data.coaching_laps:
            all_laps_arrays[lap_num] = _build_corner_enrichment_arrays(
                session_data.processed.resampled_laps[lap_num],
                include_throttle=False,
                include_longitudinal=False,
            )

        auto_enrich_corner_metadata(
            corners,
            best_lap_arrays,
            all_laps_arrays if all_laps_arrays else None,
        )

        for lap_num in session_data.coaching_laps:
            _propagate_corner_metadata(corners, all_lap_corners.get(lap_num, []))
    except (ValueError, KeyError, IndexError, TypeError):
        logger.warning(
            "Failed metadata enrichment while applying layout to session %s",
            session_data.session_id,
            exc_info=True,
        )

    consistency = session_data.consistency
    if len(session_data.coaching_laps) >= 2:
        try:
            consistency = compute_session_consistency(
                session_data.processed.lap_summaries,
                all_lap_corners,
                session_data.processed.resampled_laps,
                session_data.processed.best_lap,
                session_data.anomalous_laps,
            )
        except (ValueError, KeyError, IndexError):
            logger.warning(
                "Failed consistency recomputation for %s after layout apply",
                session_data.session_id,
                exc_info=True,
            )

    gains = session_data.gains
    if len(session_data.coaching_laps) >= 2:
        try:
            gains = estimate_gains(
                session_data.processed.resampled_laps,
                corners,
                session_data.processed.lap_summaries,
                session_data.coaching_laps,
                session_data.processed.best_lap,
            )
        except (ValueError, KeyError, IndexError):
            logger.warning(
                "Failed gains recomputation for %s after layout apply",
                session_data.session_id,
                exc_info=True,
            )

    if session_data.reference_centerline is not None and session_data.gps_traces:
        try:
            session_data.corner_line_profiles = analyze_corner_lines(
                session_data.gps_traces,
                session_data.reference_centerline,
                corners,
                resampled_laps=session_data.processed.resampled_laps,
                coaching_laps=session_data.coaching_laps,
            )
        except (ValueError, KeyError, IndexError):
            logger.warning(
                "Failed corner-line reanalysis for %s after layout apply",
                session_data.session_id,
                exc_info=True,
            )

    lap_consistency = (
        consistency.lap_consistency
        if consistency is not None
        else _fallback_lap_consistency(
            session_data.processed.lap_summaries, session_data.anomalous_laps
        )
    )
    corner_consistency = consistency.corner_consistency if consistency else []
    session_data.snapshot = build_session_snapshot(
        metadata=session_data.parsed.metadata,
        summaries=session_data.processed.lap_summaries,
        lap_consistency=lap_consistency,
        corner_consistency=corner_consistency,
        gains=gains,
        all_lap_corners=all_lap_corners,
        anomalous_laps=session_data.anomalous_laps,
        file_key=session_data.session_id,
        gps_quality_score=session_data.snapshot.gps_quality_score,
        gps_quality_grade=session_data.snapshot.gps_quality_grade,
    )
    session_data.corners = corners
    session_data.all_lap_corners = all_lap_corners
    session_data.consistency = consistency
    session_data.gains = gains
    session_data.layout = layout
    session_data.corner_override_version = corner_version
    return True


def _get_track_cached(
    track_slug: str,
    key_suffix: str,
    profile_id: str | None,
    calibrated_mu: str,
) -> dict[str, object] | None:
    cache_key = (f"{track_slug}:{key_suffix}", profile_id, calibrated_mu)
    entry = _track_physics_cache.get(cache_key)
    if entry and (time.time() - entry[1]) < TRACK_CACHE_TTL_S:
        logger.debug("Track cache HIT for %s", cache_key)
        return entry[0]
    return None


def _set_track_cached(
    track_slug: str,
    key_suffix: str,
    result: dict[str, object],
    profile_id: str | None,
    calibrated_mu: str,
) -> None:
    cache_key = (f"{track_slug}:{key_suffix}", profile_id, calibrated_mu)
    _track_physics_cache[cache_key] = (result, time.time())
    if len(_track_physics_cache) > PHYSICS_CACHE_MAX_ENTRIES:
        oldest_key = min(_track_physics_cache, key=lambda k: _track_physics_cache[k][1])
        del _track_physics_cache[oldest_key]


def invalidate_track_physics_cache(track_slug: str) -> None:
    """Clear all track-level cache entries for a track (in-memory + DB)."""
    keys_to_remove = [k for k in _track_physics_cache if k[0].startswith(f"{track_slug}:")]
    for k in keys_to_remove:
        del _track_physics_cache[k]
    if keys_to_remove:
        logger.info(
            "Invalidated %d track-level cache entries for %s",
            len(keys_to_remove),
            track_slug,
        )
    with contextlib.suppress(RuntimeError):
        asyncio.get_running_loop().create_task(db_invalidate_track(track_slug))


def recalculate_coaching_laps(
    all_laps: list[int],
    anomalous: set[int],
    in_out: set[int],
    best_lap: int,
    tags: LapTagStore,
) -> list[int]:
    """Compute coaching laps, excluding anomalous, in/out, and user-tagged laps.

    User-tagged exclusions (traffic, off-line, etc.) override the best-lap
    re-inclusion rule — if a user explicitly marks their best lap as traffic,
    we respect that intent.
    """
    user_excluded = tags.excluded_laps()
    coaching = [
        n for n in all_laps if n not in anomalous and n not in in_out and n not in user_excluded
    ]
    # Re-include best lap if excluded only by in/out (NOT by anomaly or user tag)
    if best_lap not in anomalous and best_lap not in user_excluded and best_lap not in coaching:
        coaching.append(best_lap)
        coaching.sort()
    return coaching


def _run_pipeline_sync(file_bytes: bytes, filename: str) -> SessionData:
    """Synchronous pipeline: parse, process, analyse, snapshot.

    Modeled after app.py's _build_snapshot_from_file.
    """
    # 1. Parse CSV
    parsed: ParsedSession = parse_racechrono_csv(io.BytesIO(file_bytes))

    # 2. Process session (lap splitting, resampling)
    processed: ProcessedSession = process_session(parsed.data)
    summaries: list[LapSummary] = processed.lap_summaries

    # 3. Find anomalous laps and in/out laps
    anomalous: set[int] = find_anomalous_laps(summaries)
    all_laps = sorted(processed.resampled_laps.keys())
    in_out: set[int] = {all_laps[0], all_laps[-1]} if len(all_laps) >= 2 else set()
    coaching_laps = recalculate_coaching_laps(
        all_laps=all_laps,
        anomalous=anomalous,
        in_out=in_out,
        best_lap=processed.best_lap,
        tags=LapTagStore(),
    )

    # 3b. Assess GPS quality
    gps_quality: GPSQualityReport | None = None
    try:
        gps_source = parsed.raw_data if parsed.raw_data is not None else parsed.data
        gps_quality = assess_gps_quality(gps_source, processed, anomalous)
    except (ValueError, KeyError, IndexError):
        logger.warning("Failed to assess GPS quality for %s", filename, exc_info=True)

    # Free unfiltered DataFrame — only needed for GPS quality assessment above
    parsed.raw_data = None

    # 3c. Line analysis: GPS traces + reference centerline (requires grade A/B)
    gps_traces = []
    reference_centerline = None
    line_ok = gps_quality is not None and should_enable_line_analysis(gps_quality)
    if line_ok and len(coaching_laps) >= 3:
        try:
            # Shared ENU origin: first point of first coaching lap
            first_lap_df = processed.resampled_laps[coaching_laps[0]]
            lat0 = float(first_lap_df["lat"].iloc[0])
            lon0 = float(first_lap_df["lon"].iloc[0])

            for lap_num in coaching_laps:
                lap_df = processed.resampled_laps[lap_num]
                trace = build_gps_trace(
                    lat=lap_df["lat"].to_numpy(),
                    lon=lap_df["lon"].to_numpy(),
                    distance_m=lap_df["lap_distance_m"].to_numpy(),
                    lap_number=lap_num,
                    lat0=lat0,
                    lon0=lon0,
                )
                gps_traces.append(trace)

            reference_centerline = compute_reference_centerline(gps_traces)
            logger.info(
                "Line analysis: %d traces, ref=%s for %s",
                len(gps_traces),
                reference_centerline is not None,
                filename,
            )
        except (ValueError, KeyError, IndexError):
            logger.warning("Failed line analysis for %s", filename, exc_info=True)
            gps_traces = []
            reference_centerline = None

    # 4. Detect corners (track_db lookup first, fallback to detect_corners)
    best_lap_df = processed.resampled_laps[processed.best_lap]
    # Use geometry-first matching when supported. Some deployments may run an
    # older detect_track_or_lookup() signature without the allow_name_fallback kwarg.
    matcher: Any = detect_track_or_lookup
    try:
        layout = matcher(
            parsed.data,
            parsed.metadata.track_name,
            allow_name_fallback=False,
        )
    except TypeError:
        layout = matcher(parsed.data, parsed.metadata.track_name)
    corner_version: str | None = None
    if layout is not None:
        # Hybrid cache already has the correct corners (DB-first + Python fallback).
        # Capture version hash for staleness detection by ensure_corners_current().
        slug = track_slug_from_layout(layout)
        corner_version = get_corner_override_version(slug)
        skeletons = locate_official_corners(best_lap_df, layout)
        corners: list[Corner] = extract_corner_kpis_for_lap(best_lap_df, skeletons)
    else:
        corners = detect_corners(best_lap_df)

    # 5. Extract all-lap corners for coaching laps
    all_lap_corners: dict[int, list[Corner]] = {}
    for lap_num in coaching_laps:
        lap_df = processed.resampled_laps[lap_num]
        if lap_num == processed.best_lap:
            all_lap_corners[lap_num] = corners
        else:
            all_lap_corners[lap_num] = extract_corner_kpis_for_lap(lap_df, corners)

    # 5b. Enrich corners with elevation data
    try:
        elev = compute_corner_elevation(best_lap_df, corners)
        if elev:
            enrich_corners_with_elevation(all_lap_corners, elev)
    except (ValueError, KeyError, IndexError):
        logger.warning("Failed to compute elevation for %s", filename, exc_info=True)

    # 5c. Auto-enrich missing corner metadata from telemetry.
    try:
        best_lap_arrays = _build_corner_enrichment_arrays(best_lap_df)
        all_laps_arrays: dict[int, dict[str, np.ndarray]] = {}
        for lap_num in coaching_laps:
            all_laps_arrays[lap_num] = _build_corner_enrichment_arrays(
                processed.resampled_laps[lap_num],
                include_throttle=False,
                include_longitudinal=False,
            )

        auto_enrich_corner_metadata(
            corners,
            best_lap_arrays,
            all_laps_arrays if all_laps_arrays else None,
        )

        for lap_num in coaching_laps:
            _propagate_corner_metadata(corners, all_lap_corners.get(lap_num, []))
    except (ValueError, KeyError, IndexError, TypeError):
        logger.warning("Failed corner metadata enrichment for %s", filename, exc_info=True)

    # 5d. Corner line analysis (if reference centerline available)
    corner_line_profiles = []
    if reference_centerline is not None and gps_traces and corners:
        try:
            corner_line_profiles = analyze_corner_lines(
                gps_traces,
                reference_centerline,
                corners,
                resampled_laps=processed.resampled_laps,
                coaching_laps=coaching_laps,
            )
            logger.info(
                "Corner line profiles: %d corners analysed for %s",
                len(corner_line_profiles),
                filename,
            )
        except (ValueError, KeyError, IndexError):
            logger.warning("Failed corner line analysis for %s", filename, exc_info=True)

    # 6. Compute consistency
    consistency = None
    if len(coaching_laps) >= 2:
        try:
            consistency = compute_session_consistency(
                summaries,
                all_lap_corners,
                processed.resampled_laps,
                processed.best_lap,
                anomalous,
            )
        except (ValueError, KeyError, IndexError):
            logger.warning("Failed to compute consistency for %s", filename, exc_info=True)

    # 7. Estimate gains
    gains: GainEstimate | None = None
    if len(coaching_laps) >= 2:
        try:
            gains = estimate_gains(
                processed.resampled_laps,
                corners,
                summaries,
                coaching_laps,
                processed.best_lap,
            )
        except (ValueError, KeyError, IndexError):
            logger.warning("Failed to estimate gains for %s", filename, exc_info=True)

    # 8. Estimate grip
    grip = None
    if coaching_laps:
        try:
            grip = estimate_grip_limit(processed.resampled_laps, coaching_laps)
        except (ValueError, KeyError, IndexError):
            logger.warning("Failed to estimate grip for %s", filename, exc_info=True)

    # 9. Build session snapshot
    lap_consistency = (
        consistency.lap_consistency
        if consistency
        else _fallback_lap_consistency(summaries, anomalous)
    )
    corner_consistency = consistency.corner_consistency if consistency else []

    snap: SessionSnapshot = build_session_snapshot(
        metadata=parsed.metadata,
        summaries=summaries,
        lap_consistency=lap_consistency,
        corner_consistency=corner_consistency,
        gains=gains,
        all_lap_corners=all_lap_corners,
        anomalous_laps=anomalous,
        file_key=filename,
        gps_quality_score=gps_quality.overall_score if gps_quality else 0.0,
        gps_quality_grade=gps_quality.grade if gps_quality else "unknown",
    )

    # 10. Eagerly build/update canonical track reference for future sessions
    if layout is not None and coaching_laps:
        try:
            quality_score = gps_quality.overall_score if gps_quality else 50.0
            maybe_update_track_reference(
                layout,
                processed,
                coaching_laps,
                snap.session_id,
                quality_score,
            )
            # Invalidate track-level physics cache when reference updates
            slug = track_slug_from_layout(layout)
            invalidate_track_physics_cache(slug)
        except Exception:
            logger.warning("Failed to update track reference for %s", filename, exc_info=True)

    return SessionData(
        session_id=snap.session_id,
        snapshot=snap,
        parsed=parsed,
        processed=processed,
        corners=corners,
        all_lap_corners=all_lap_corners,
        consistency=consistency,
        gains=gains,
        grip=grip,
        gps_quality=gps_quality,
        coaching_laps=coaching_laps,
        anomalous_laps=anomalous,
        gps_traces=gps_traces,
        reference_centerline=reference_centerline,
        corner_line_profiles=corner_line_profiles,
        layout=layout,
        corner_override_version=corner_version,
    )


def _fallback_lap_consistency(summaries: list[LapSummary], anomalous: set[int]) -> Any:
    """Create a minimal LapConsistency when full consistency computation fails."""
    from cataclysm.consistency import compute_lap_consistency

    return compute_lap_consistency(summaries, anomalous)


def compute_session_id_from_csv(file_bytes: bytes, filename: str) -> str:
    """Cheaply compute the session_id from CSV header without full processing.

    Parses only the first 8 metadata lines to extract track name and date,
    then computes the deterministic session_id hash.
    """
    from cataclysm.parser import _parse_metadata
    from cataclysm.trends import _compute_session_id

    text = file_bytes.decode("utf-8", errors="replace")
    lines = text.split("\n", 10)[:9]  # Only need first 8-9 lines
    meta = _parse_metadata(lines)
    return _compute_session_id(filename, meta.track_name, meta.session_date)


async def _try_auto_discover_track(session_data: SessionData) -> None:
    """Try to discover an unknown track via OSM and seed the DB for future uploads.

    This is best-effort — failures are logged and swallowed. The current session
    continues with auto-detected corners; future uploads of the same track will
    benefit from the discovered layout via GPS detection.
    """
    from cataclysm.osm_import import osm_to_track_seed, query_overpass_raceway_sync
    from cataclysm.track_db_hybrid import db_track_to_layout, update_db_tracks_cache_with_aliases
    from cataclysm.track_match import compute_session_centroid

    from backend.api.db.database import async_session_factory
    from backend.api.services.track_corners import update_corner_hash
    from backend.api.services.track_enrichment import enrich_track

    # Compute GPS centroid from the session data
    try:
        clat, clon = compute_session_centroid(session_data.parsed.data)
    except ValueError:
        return  # Not enough GPS points

    # Query OSM in the thread pool (sync httpx)
    results = await asyncio.to_thread(query_overpass_raceway_sync, clat, clon)
    if not results:
        logger.info("No OSM raceways found near %.4f,%.4f", clat, clon)
        return

    # Multi-signal ranking: centroid + length + loop closure + shape distance.
    best_lap_df = session_data.processed.resampled_laps[session_data.processed.best_lap]
    if "lat" not in best_lap_df.columns or "lon" not in best_lap_df.columns:
        return
    session_lats = np.asarray(best_lap_df["lat"].to_numpy(), dtype=float)
    session_lons = np.asarray(best_lap_df["lon"].to_numpy(), dtype=float)
    session_length_m = float(best_lap_df["lap_distance_m"].iloc[-1])

    scored_candidates: list[tuple[float, Any, dict[str, float]]] = []
    for candidate in results:
        cand_lats = np.asarray(candidate.lats, dtype=float)
        cand_lons = np.asarray(candidate.lons, dtype=float)
        score, metrics = _score_osm_candidate(
            session_lats=session_lats,
            session_lons=session_lons,
            session_length_m=session_length_m,
            centroid_lat=clat,
            centroid_lon=clon,
            candidate_lats=cand_lats,
            candidate_lons=cand_lons,
            candidate_length_m=candidate.length_m,
        )
        scored_candidates.append((score, candidate, metrics))
    scored_candidates.sort(key=lambda item: item[0])
    best = scored_candidates[0][1]
    best_metrics = scored_candidates[0][2]
    seed = osm_to_track_seed(best)
    logger.info(
        "Auto-discovered track: %s (%.0fm) via OSM "
        "[score=%.1f center=%.1fm length=%.1fm shape=%.1fm]",
        seed["name"],
        seed["length_m"],
        best_metrics["score"],
        best_metrics["center_dist_m"],
        best_metrics["length_error_m"],
        best_metrics["shape_error_m"],
    )
    session_track_name = session_data.snapshot.metadata.track_name.strip()
    aliases = (
        [session_track_name]
        if session_track_name and session_track_name.casefold() != seed["name"].strip().casefold()
        else []
    )
    centerline_geojson = {
        "type": "LineString",
        "coordinates": [
            [float(lon), float(lat)] for lat, lon in zip(best.lats, best.lons, strict=False)
        ],
    }

    # Create/enrich a track in DB and apply it to the current session.
    try:
        async with async_session_factory() as db:
            from backend.api.services.track_store import (
                create_track,
                get_corners_for_track,
                get_landmarks_for_track,
                get_track_by_slug,
                update_track,
            )

            track = await get_track_by_slug(db, seed["slug"])
            if track is None:
                track = await create_track(
                    db,
                    slug=seed["slug"],
                    name=seed["name"],
                    source="osm-auto",
                    center_lat=seed["center_lat"],
                    center_lon=seed["center_lon"],
                    length_m=seed["length_m"],
                    quality_tier=1,
                    status="draft",
                )
                logger.info("Auto-created draft track: %s", seed["slug"])

            merged_aliases = sorted(
                {
                    *(track.aliases or []),
                    *aliases,
                }
            )
            track = (
                await update_track(
                    db,
                    track.slug,
                    aliases=merged_aliases,
                    centerline_geojson=centerline_geojson,
                )
                or track
            )

            await enrich_track(
                db,
                track.id,
                np.asarray(best.lats, dtype=float),
                np.asarray(best.lons, dtype=float),
                track_length_m=best.length_m,
            )

            db_corners = await get_corners_for_track(db, track.id)
            db_landmarks = await get_landmarks_for_track(db, track.id)
            layout = db_track_to_layout(track, db_corners, db_landmarks)
            update_db_tracks_cache_with_aliases(track.slug, layout, aliases=track.aliases)
            if db_corners:
                update_corner_hash(track.slug, _corner_hash_rows(db_corners))
            await db.commit()
            corner_version = get_corner_override_version(track.slug)
            if _apply_layout_to_session(session_data, layout, corner_version):
                invalidate_physics_cache(session_data.session_id)
                logger.info(
                    "Applied discovered layout '%s' to current session %s (%d corners)",
                    track.slug,
                    session_data.session_id,
                    len(session_data.corners),
                )
    except Exception:
        logger.warning("Failed to persist auto-discovered track", exc_info=True)


async def reprocess_session_from_csv(
    session_id: str,
    csv_bytes: bytes,
    filename: str,
) -> SessionData:
    """Reprocess a session from CSV bytes without side effects.

    Used for lazy rehydration on cache miss. Does NOT generate a new session_id,
    does NOT insert DB rows, does NOT trigger auto-coaching or weather fetching.
    Raises on corrupt/invalid CSV (caller must catch).
    """
    sd = await asyncio.to_thread(_run_pipeline_sync, csv_bytes, filename)
    # Override session_id to match the original (deterministic IDs should match,
    # but this guarantees it even if filename changed)
    sd.session_id = session_id
    sd.snapshot.session_id = session_id
    # Caller (rehydrate_session) is responsible for setting metadata
    # (user_id, weather, lap_tags, etc.) and calling store_session AFTER
    # all fields are populated — prevents a brief window where the session
    # is visible in the cache with incomplete metadata.
    return sd


async def process_upload(file_bytes: bytes, filename: str) -> dict[str, object]:
    """Parse a RaceChrono CSV and run the full processing pipeline.

    Runs CPU-bound work in a thread to avoid blocking the event loop.
    Returns a dict with session_id and summary metadata.
    """
    session_data = await asyncio.to_thread(_run_pipeline_sync, file_bytes, filename)
    store_session(session_data.session_id, session_data)

    # Auto-discovery: if no track was recognized, try OSM import in background
    if session_data.layout is None:
        try:
            await _try_auto_discover_track(session_data)
        except Exception:
            logger.warning("Auto-discovery failed for %s", filename, exc_info=True)

    snap = session_data.snapshot
    return {
        "session_id": session_data.session_id,
        "track_name": snap.metadata.track_name,
        "session_date": snap.metadata.session_date,
        "n_laps": snap.n_laps,
        "n_clean_laps": snap.n_clean_laps,
        "best_lap_time_s": snap.best_lap_time_s,
    }


async def process_file_path(file_path: str | Path) -> dict[str, object]:
    """Process a CSV file from disk (used by track folder loading).

    Returns the same dict as process_upload.
    """
    path = Path(file_path)
    file_bytes = await asyncio.to_thread(path.read_bytes)
    return await process_upload(file_bytes, path.name)


async def get_ideal_lap_data(session_data: SessionData) -> dict[str, object]:
    """Reconstruct the ideal lap for a session.

    Returns columnar data with distance, speed, and segment sources.
    """

    def _compute() -> dict[str, object]:
        corners = session_data.corners
        processed = session_data.processed
        coaching_laps = session_data.coaching_laps
        best_lap = processed.best_lap

        best_lap_df = processed.resampled_laps[best_lap]
        track_length_m = float(best_lap_df["lap_distance_m"].iloc[-1])

        segments = build_segments(corners, track_length_m)
        seg_times = compute_segment_times(processed.resampled_laps, segments, coaching_laps)
        ideal = reconstruct_ideal_lap(
            processed.resampled_laps, segments, seg_times, coaching_laps, best_lap
        )

        return {
            "distance_m": ideal.distance_m.tolist(),
            "speed_mph": (ideal.speed_mps * MPS_TO_MPH).tolist(),
            "segment_sources": ideal.segment_sources,
        }

    return await asyncio.to_thread(_compute)


def resolve_vehicle_params(session_id: str) -> VehicleParams | None:
    """Look up equipment for a session and convert to VehicleParams.

    Returns *None* if the session has no equipment assigned, letting the
    velocity solver fall back to its built-in defaults.
    """
    se = equipment_store.get_session_equipment(session_id)
    if se is None:
        return None
    profile = equipment_store.get_profile(se.profile_id)
    if profile is None:
        return None
    return equipment_to_vehicle_params(profile)


# Margin above CATEGORY_MU_DEFAULTS to account for within-category variation
# (e.g., Yokohama A052 vs Hankook RS4, both 200TW but different grip levels),
# alignment/camber benefits, and better-than-average tire samples.
_COMPOUND_MU_CAP_MARGIN = 1.15


def _get_compound_mu_cap(session_id: str) -> float | None:
    """Get the maximum realistic mu for the session's tire compound category.

    Returns ``CATEGORY_MU_DEFAULTS[category] * 1.15``, or *None* if no
    equipment is assigned.  The 15% margin accounts for within-category
    variation and setup advantages.
    """
    se = equipment_store.get_session_equipment(session_id)
    if se is None:
        return None
    profile = equipment_store.get_profile(se.profile_id)
    if profile is None:
        return None
    base_mu = CATEGORY_MU_DEFAULTS[profile.tires.compound_category]
    return base_mu * _COMPOUND_MU_CAP_MARGIN


async def _try_lidar_elevation(session_data: SessionData) -> np.ndarray | None:
    """Attempt LIDAR elevation fetch for the best lap (async, pre-thread).

    Returns a numpy array of LIDAR altitudes aligned to the best lap, or
    None if the fetch fails or coverage is insufficient.
    """
    processed = session_data.processed
    best_lap_df = processed.resampled_laps[processed.best_lap]
    if "lat" not in best_lap_df.columns or "lon" not in best_lap_df.columns:
        return None
    try:
        from cataclysm.elevation_service import fetch_lidar_elevations

        result = await asyncio.wait_for(
            fetch_lidar_elevations(
                best_lap_df["lat"].to_numpy(),
                best_lap_df["lon"].to_numpy(),
            ),
            timeout=8.0,
        )
        if result.source == "usgs_3dep" and len(result.altitude_m) > 0:
            logger.info("Using USGS 3DEP LIDAR elevation (%d points)", len(result.altitude_m))
            return result.altitude_m
    except TimeoutError:
        logger.warning("LIDAR elevation fetch timed out after 8s, using GPS altitude")
    except Exception:
        logger.debug("LIDAR elevation fetch failed, using GPS altitude", exc_info=True)
    return None


# Track LIDAR prefetch background tasks to prevent GC collection
_lidar_background_tasks: set[asyncio.Task[None]] = set()


def _track_lidar_task(task: asyncio.Task[None]) -> None:
    """Track a LIDAR prefetch task with cleanup callback."""
    _lidar_background_tasks.add(task)

    def _on_done(t: asyncio.Task[None]) -> None:
        _lidar_background_tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.warning("LIDAR prefetch task failed: %s", exc)

    task.add_done_callback(_on_done)


async def _lidar_prefetch_impl(session_data: SessionData) -> None:
    """Pre-warm the LIDAR elevation cache for a session."""
    result = await _try_lidar_elevation(session_data)
    if result is not None:
        logger.info(
            "LIDAR prefetch complete for %s (%d points)",
            session_data.session_id,
            len(result),
        )


def trigger_lidar_prefetch(session_data: SessionData) -> None:
    """Fire-and-forget LIDAR elevation prefetch for a newly uploaded session.

    Warms the USGS 3DEP cache so the Speed Gap panel loads instantly when
    the user opens the session.
    """
    _track_lidar_task(asyncio.create_task(_lidar_prefetch_impl(session_data)))


def _collect_independent_calibration_telemetry(
    session_data: SessionData,
    *,
    target_lap: int,
) -> tuple[np.ndarray, np.ndarray, list[int]] | None:
    """Return telemetry from coaching laps other than the target lap.

    The physics reference should not calibrate itself from the same lap it is
    evaluating. When no independent laps remain, return None so the caller can
    fall back to equipment/default parameters.
    """
    candidate_laps = [
        lap_num
        for lap_num in session_data.coaching_laps
        if lap_num != target_lap and lap_num in session_data.processed.resampled_laps
    ]
    if not candidate_laps:
        return None

    lat_segments: list[np.ndarray] = []
    lon_segments: list[np.ndarray] = []
    used_laps: list[int] = []

    for lap_num in candidate_laps:
        lap_df = session_data.processed.resampled_laps[lap_num]
        if "lateral_g" not in lap_df.columns or "longitudinal_g" not in lap_df.columns:
            continue

        lat_g = lap_df["lateral_g"].to_numpy()
        lon_g = lap_df["longitudinal_g"].to_numpy()

        # Filter to finite values only — interpolation with fill_value="extrapolate"
        # can produce unrealistic edge values that would inflate grip estimates.
        finite_mask = np.isfinite(lat_g) & np.isfinite(lon_g)
        lat_g = lat_g[finite_mask]
        lon_g = lon_g[finite_mask]
        if len(lat_g) == 0 or len(lon_g) == 0:
            continue

        lat_segments.append(lat_g)
        lon_segments.append(lon_g)
        used_laps.append(lap_num)

    if not lat_segments:
        return None

    return np.concatenate(lat_segments), np.concatenate(lon_segments), used_laps


def _build_mu_array(
    distance_m: np.ndarray,
    corners: list[Corner],
    per_corner_mu: dict[int, float],
    global_mu: float,
) -> np.ndarray:
    """Build a per-point mu array from per-corner grip estimates.

    For points inside a corner zone, uses ``max(global_mu, per_corner_mu)``
    — the higher of the two estimates.  This allows per-corner calibration
    to capture corners where the driver demonstrated grip above the global
    average, without penalising corners where they were timid (which would
    make the optimal profile more conservative, the wrong direction for a
    coaching tool).

    For points outside any corner zone, the global mu is used.
    """
    mu_arr = np.full(len(distance_m), global_mu, dtype=np.float64)
    for corner in corners:
        if corner.number not in per_corner_mu:
            continue
        corner_mu = max(global_mu, per_corner_mu[corner.number])
        mask = (distance_m >= corner.entry_distance_m) & (distance_m <= corner.exit_distance_m)
        mu_arr[mask] = corner_mu
    return mu_arr


def _collect_per_corner_mu(
    session_data: SessionData,
) -> dict[int, float]:
    """Estimate per-corner grip from ALL coaching laps combined.

    Concatenates lateral_g and distance_m from all coaching laps, then calls
    calibrate_per_corner_grip on the combined data.  Using all laps gives a
    robust multi-lap estimate: even laps where the driver was conservative in
    one corner contribute near-limit data from other corners, and the p95
    across the combined dataset captures what the car demonstrated it can do.

    Returns an empty dict if telemetry columns are unavailable.
    """
    all_lat_g: list[np.ndarray] = []
    all_dist_m: list[np.ndarray] = []

    for lap_num in session_data.coaching_laps:
        lap_df = session_data.processed.resampled_laps.get(lap_num)
        if lap_df is None:
            continue
        if "lateral_g" not in lap_df.columns:
            continue
        lat_g = lap_df["lateral_g"].to_numpy()
        dist = lap_df["lap_distance_m"].to_numpy()
        finite = np.isfinite(lat_g)
        lat_g = lat_g[finite]
        dist = dist[finite]
        if len(lat_g) == 0:
            continue
        all_lat_g.append(lat_g)
        all_dist_m.append(dist)

    if not all_lat_g:
        return {}

    return calibrate_per_corner_grip(
        np.concatenate(all_lat_g),
        np.concatenate(all_dist_m),
        session_data.corners,
    )


_G_ACCEL = 9.81  # m/s²


def _implied_mu_from_corners(
    corners: list[Corner],
    curvature_result: CurvatureResult,
) -> dict[int, float]:
    """Back-solve friction coefficient from the driver's best observed min speed.

    Uses circular motion physics: ``mu = v² × κ / g``.

    The curvature reference must align with how ``compute_corner_opportunities``
    picks the optimal min speed — an apex-centred window (±30% zone width,
    min ±20 m).  We use the **max** curvature in that window so the resulting
    mu guarantees the solver's minimum speed in the same window is ≥ the
    driver's actual minimum.

    Applied via ``max()`` in ``_build_mu_array``, implied mu can only *raise*
    the corner-level optimal — it never lowers predictions.
    """
    result: dict[int, float] = {}
    for corner in corners:
        zone_width = corner.exit_distance_m - corner.entry_distance_m
        half_win = max(zone_width * APEX_WINDOW_FRACTION, MIN_APEX_WINDOW_M)
        apex_start = max(corner.apex_distance_m - half_win, corner.entry_distance_m)
        apex_end = min(corner.apex_distance_m + half_win, corner.exit_distance_m)

        apex_mask = (curvature_result.distance_m >= apex_start) & (
            curvature_result.distance_m <= apex_end
        )
        if not apex_mask.any():
            continue
        kappa_max = float(np.max(curvature_result.abs_curvature[apex_mask]))
        if kappa_max < 1e-4:  # essentially a straight — skip
            continue
        mu = corner.min_speed_mps**2 * kappa_max / _G_ACCEL
        result[corner.number] = mu
    return result


def _resolve_curvature_and_elevation(
    session_data: SessionData,
    lidar_alt: np.ndarray | None,
) -> tuple[CurvatureResult, np.ndarray | None]:
    """Use canonical track reference if available, else per-session curvature.

    Returns (CurvatureResult, elevation_array_or_None).
    """
    processed = session_data.processed
    best_lap_df = processed.resampled_laps[processed.best_lap]

    # Try canonical track reference first
    layout = session_data.layout
    if layout is not None:
        ref = get_track_reference(layout)
        if ref is not None:
            session_dist = best_lap_df["lap_distance_m"].to_numpy()
            aligned_curv, aligned_elev = align_reference_to_session(ref, session_dist)
            logger.info(
                "Using canonical track reference for %s (built from %d laps, quality=%.1f)",
                ref.track_slug,
                ref.n_laps_averaged,
                ref.gps_quality_score,
            )
            # Prefer canonical elevation, but fall back to LIDAR/GPS if not in reference
            if aligned_elev is not None:
                return aligned_curv, aligned_elev
            return aligned_curv, lidar_alt

    # Fallback: per-session curvature from best lap GPS
    curvature_result = compute_curvature(best_lap_df, savgol_window=15)
    return curvature_result, lidar_alt


async def get_optimal_profile_data(session_data: SessionData) -> dict[str, object]:
    """Compute the physics-optimal velocity profile for a session.

    Uses the best lap's GPS data to derive track curvature, then runs the
    forward-backward velocity solver.  If the session has equipment assigned,
    the equipment-derived VehicleParams are used; otherwise the solver's
    built-in defaults apply.

    Grip calibration is hoisted before cache checks so we can build the
    track-level cache key (which includes calibrated_mu).  The track-level
    cache shares optimal profiles across sessions on the same track with the
    same equipment + grip, avoiding the ~8s velocity solver on repeat visits.

    Returns columnar data suitable for JSON serialisation.
    """
    session_id = session_data.session_id

    # Capture profile_id and vehicle params now, before entering the thread
    # pool.  This prevents a TOCTOU race where the user switches equipment
    # while _compute() is running — we must compute AND cache under the
    # profile that was current at request time.
    profile_id = _current_profile_id(session_id)
    vehicle_params = resolve_vehicle_params(session_id)
    mu_cap = _get_compound_mu_cap(session_id)

    # Hoist grip calibration BEFORE cache checks (~1ms, cheap) so we can
    # include calibrated_mu in the track-level cache key.
    def _calibrate_sync() -> VehicleParams | None:
        calibration_data = _collect_independent_calibration_telemetry(
            session_data,
            target_lap=session_data.processed.best_lap,
        )
        if calibration_data is None:
            return vehicle_params
        lat_g, lon_g, calibration_laps = calibration_data
        grip = calibrate_grip_from_telemetry(lat_g, lon_g)
        if grip is None:
            return vehicle_params
        base = vehicle_params or default_vehicle_params()
        calibrated = apply_calibration_to_params(base, grip, mu_cap=mu_cap)
        logger.info(
            "Grip calibration [profile] sid=%s laps=%s: mu=%.3f lat_g=%.3f "
            "brake_g=%.3f accel_g=%.3f confidence=%s mu_cap=%s",
            session_id,
            calibration_laps,
            calibrated.mu,
            grip.max_lateral_g,
            grip.max_brake_g,
            grip.max_accel_g,
            grip.confidence,
            mu_cap,
        )
        return calibrated

    calibrated_vp = await asyncio.to_thread(_calibrate_sync)
    calibrated_mu_str = f"{calibrated_vp.mu:.2f}" if calibrated_vp else "default"
    track_slug = track_slug_from_layout(session_data.layout) if session_data.layout else None

    # --- Track-level cache (shared across sessions on the same track) ---
    if track_slug is not None:
        track_hit = _get_track_cached(
            track_slug,
            "profile",
            profile_id,
            calibrated_mu_str,
        )
        if track_hit is not None:
            # Populate session-level cache for faster future lookups
            _set_physics_cached(session_id, "profile", track_hit, profile_id)
            return track_hit

        db_track_hit = await db_get_cached_by_track(
            track_slug,
            "profile",
            profile_id,
            calibrated_mu_str,
        )
        if db_track_hit is not None:
            _set_track_cached(
                track_slug,
                "profile",
                db_track_hit,
                profile_id,
                calibrated_mu_str,
            )
            _set_physics_cached(
                session_id,
                "profile",
                db_track_hit,
                profile_id,
            )
            return db_track_hit

    # --- Session-level cache (fallback, also serves unknown tracks) ---
    cached = _get_physics_cached(session_id, "profile", profile_id)
    if cached is not None:
        return cached

    db_cached = await db_get_cached(session_id, "profile", profile_id)
    if db_cached is not None:
        _set_physics_cached(session_id, "profile", db_cached, profile_id)
        return db_cached

    # Try LIDAR elevation (async, before entering sync thread)
    lidar_alt = await _try_lidar_elevation(session_data)

    # Load Bayesian per-corner capability factors (async, before sync thread).
    # Only for authenticated users on known tracks. Pass into _compute via closure.
    c_factors: dict[int, float] = {}
    if track_slug and session_data.user_id and session_data.user_id != "anon":
        try:
            from backend.api.db.database import async_session_factory
            from backend.api.services.corner_capability_store import (
                get_corner_capabilities,
            )

            async with async_session_factory() as db:
                c_data = await get_corner_capabilities(db, track_slug, session_data.user_id)
            # Only apply factors with >= 2 observations to avoid noisy single-session data
            c_factors = {cn: mu_post for cn, (mu_post, _, n) in c_data.items() if n >= 2}
            if c_factors:
                logger.debug(
                    "Loaded %d C-factors for sid=%s track=%s",
                    len(c_factors),
                    session_id,
                    track_slug,
                )
        except Exception:
            logger.debug("Failed to load C-factors", exc_info=True)

    def _compute() -> dict[str, object]:
        processed = session_data.processed
        best_lap_df = processed.resampled_laps[processed.best_lap]

        # Use canonical track reference if available, else per-session curvature
        curvature_result, resolved_alt = _resolve_curvature_and_elevation(
            session_data,
            lidar_alt,
        )

        # Try yaw-rate curvature from best lap for fusion
        if "yaw_rate_dps" in best_lap_df.columns:
            from cataclysm.curvature import compute_yaw_rate_curvature, fuse_curvature_sources

            kappa_yaw = compute_yaw_rate_curvature(
                best_lap_df["yaw_rate_dps"].to_numpy(),
                best_lap_df["speed_mps"].to_numpy(),
                curvature_result.distance_m,
            )
            if kappa_yaw is not None:
                fused = fuse_curvature_sources(
                    curvature_result.curvature, kappa_yaw, curvature_result.distance_m
                )
                curvature_result = dataclasses.replace(
                    curvature_result,
                    curvature=fused,
                    abs_curvature=np.abs(fused),
                )
                logger.info(
                    "Yaw-rate curvature fusion applied for sid=%s",
                    session_id,
                )

        # Build per-corner mu array using all coaching laps combined.
        # Uses max(global_mu, per_corner_mu) so corners where the driver
        # demonstrated above-average grip are predicted correctly without
        # making timid corners more conservative.
        mu_array: np.ndarray | None = None
        if session_data.corners and calibrated_vp is not None:
            per_corner_mu = _collect_per_corner_mu(session_data)
            # Also incorporate mu implied by driver's own best speed at each corner.
            # If GPS curvature is overestimated for a corner the solver would predict
            # a speed below what the driver already achieved — raising the local mu
            # to match the observed speed prevents the model from being less than
            # the driver's own demonstrated capability.
            implied_mu = _implied_mu_from_corners(session_data.corners, curvature_result)
            for cn, mu in implied_mu.items():
                per_corner_mu[cn] = max(per_corner_mu.get(cn, 0.0), mu)
            if per_corner_mu:
                mu_array = _build_mu_array(
                    curvature_result.distance_m,
                    session_data.corners,
                    per_corner_mu,
                    calibrated_vp.mu,
                )
                logger.debug(
                    "Per-corner mu array built for sid=%s: %d calibrated corners, global_mu=%.3f",
                    session_id,
                    len(per_corner_mu),
                    calibrated_vp.mu,
                )

        # Apply Bayesian C-factors to mu_array (loaded in async context above).
        # C-factors encode learned per-corner adjustments from previous sessions —
        # e.g., banked turns get C > 1, off-camber corners get C < 1.
        if c_factors and session_data.corners:
            if mu_array is None:
                base_mu = calibrated_vp.mu if calibrated_vp else 1.0
                mu_array = np.full(len(curvature_result.distance_m), base_mu)
            for corner in session_data.corners:
                c_val = c_factors.get(corner.number)
                if (
                    c_val is not None
                    and corner.entry_distance_m is not None
                    and corner.exit_distance_m is not None
                ):
                    mask = (curvature_result.distance_m >= corner.entry_distance_m) & (
                        curvature_result.distance_m <= corner.exit_distance_m
                    )
                    mu_array[mask] *= c_val
            logger.debug(
                "Applied %d Bayesian C-factors for sid=%s",
                len(c_factors),
                session_id,
            )
        # Compute elevation gradient and vertical curvature for the solver
        # Prefer resolved altitude (canonical/LIDAR), fall back to GPS
        gradient_sin = None
        vert_curvature = None
        alt = resolved_alt
        if alt is None and "altitude_m" in best_lap_df.columns:
            alt = best_lap_df["altitude_m"].to_numpy()
        if alt is not None and not np.all(np.isnan(alt)):
            dist = best_lap_df["lap_distance_m"].to_numpy()
            gradient_sin = compute_gradient_array(alt, dist)
            vert_curvature = compute_vertical_curvature(alt, dist)
            logger.info(
                "Elevation data [profile] sid=%s: source=%s "
                "gradient_range=[%.4f, %.4f] "
                "vert_curv_range=[%.5f, %.5f]",
                session_id,
                "canonical/lidar" if resolved_alt is not None else "gps",
                float(np.min(gradient_sin)),
                float(np.max(gradient_sin)),
                float(np.min(vert_curvature)),
                float(np.max(vert_curvature)),
            )

        # Auto-detect banking from IMU discrepancy (lateral_g vs yaw_rate).
        # When both sensors are present, the accelerometer reads higher than
        # expected from curvature alone on banked surfaces (gravity component).
        # The gyroscope yaw rate is NOT affected by banking, so the difference
        # reveals the banking angle.  Only sets Corner.banking_deg for corners
        # that don't already have it from track_db or manual override.
        if (
            "yaw_rate_dps" in best_lap_df.columns
            and "lateral_g" in best_lap_df.columns
            and session_data.corners
        ):
            from cataclysm.banking import detect_banking_from_telemetry

            banking_array = detect_banking_from_telemetry(
                best_lap_df["lateral_g"].to_numpy(),
                best_lap_df["yaw_rate_dps"].to_numpy(),
                best_lap_df["speed_mps"].to_numpy(),
                curvature_result.distance_m,
            )
            if banking_array is not None:
                banked_count = 0
                for corner in session_data.corners:
                    if corner.banking_deg is not None:
                        continue  # already has banking from track_db or override
                    if corner.apex_distance_m is None:
                        continue
                    entry = corner.entry_distance_m or 0.0
                    exit_ = corner.exit_distance_m or curvature_result.distance_m[-1]
                    mask = (curvature_result.distance_m >= entry) & (
                        curvature_result.distance_m <= exit_
                    )
                    if mask.any():
                        avg_banking = float(np.mean(banking_array[mask]))
                        if abs(avg_banking) > 1.0:  # only set if meaningfully banked
                            corner.banking_deg = round(avg_banking, 1)
                            banked_count += 1
                if banked_count:
                    logger.info(
                        "Auto-detected banking for %d/%d corners in sid=%s",
                        banked_count,
                        len(session_data.corners),
                        session_id,
                    )

        # Apply banking corrections to mu_array.
        # Primary: per-corner banking from telemetry (auto_enrich sets Corner.banking_deg)
        # Fallback: track-level banking from TRACK_BANKING dict via TrackReference.banking_deg
        corners_with_banking = [
            c for c in (session_data.corners or []) if c.banking_deg is not None
        ]
        if corners_with_banking:
            if mu_array is None:
                base_mu = calibrated_vp.mu if calibrated_vp else 1.0
                mu_array = np.full(len(curvature_result.distance_m), base_mu)
            mu_array = apply_banking_to_mu_array(
                mu_array, curvature_result.distance_m, session_data.corners or []
            )
            logger.debug("Applied telemetry banking for %d corners", len(corners_with_banking))
        else:
            # Fallback to track-level banking from reference NPZ or track_db
            track_ref = (
                get_track_reference(session_data.layout)
                if session_data.layout is not None
                else None
            )
            if track_ref is not None and track_ref.banking_deg is not None:
                banking_rad = np.radians(track_ref.banking_deg)
                banking_mu_boost = np.tan(banking_rad)
                if mu_array is None:
                    base_mu = calibrated_vp.mu if calibrated_vp else 1.0
                    mu_array = np.full(len(curvature_result.distance_m), base_mu)
                mu_array = mu_array + banking_mu_boost

        # Solve optimal velocity profile (uses pre-calibrated params)
        optimal = compute_optimal_profile(
            curvature_result,
            params=calibrated_vp,
            gradient_sin=gradient_sin,
            mu_array=mu_array,
            vertical_curvature=vert_curvature,
        )

        return {
            "distance_m": optimal.distance_m.tolist(),
            "optimal_speed_mph": (optimal.optimal_speed_mps * MPS_TO_MPH).tolist(),
            "max_cornering_speed_mph": (optimal.max_cornering_speed_mps * MPS_TO_MPH).tolist(),
            "brake_points": optimal.optimal_brake_points,
            "throttle_points": optimal.optimal_throttle_points,
            "lap_time_s": optimal.lap_time_s,
            "vehicle_params": {
                "mu": optimal.vehicle_params.mu,
                "max_accel_g": optimal.vehicle_params.max_accel_g,
                "max_decel_g": optimal.vehicle_params.max_decel_g,
                "max_lateral_g": optimal.vehicle_params.max_lateral_g,
                "top_speed_mps": optimal.vehicle_params.top_speed_mps,
                "calibrated": optimal.vehicle_params.calibrated,
            },
            "calibrated_mu": calibrated_mu_str,
            "equipment_profile_id": profile_id,
        }

    result = await asyncio.to_thread(_compute)

    # Cache at session level
    _set_physics_cached(session_id, "profile", result, profile_id)
    await db_set_cached(session_id, "profile", result, profile_id)

    # Cache at track level (if known track)
    if track_slug is not None:
        _set_track_cached(
            track_slug,
            "profile",
            result,
            profile_id,
            calibrated_mu_str,
        )
        await db_set_cached_by_track(
            track_slug,
            "profile",
            result,
            profile_id,
            calibrated_mu_str,
        )

    return result


def _reconstruct_optimal_profile(data: dict[str, object]) -> OptimalProfile:
    """Reconstruct an OptimalProfile from a cached profile result dict."""
    vp_dict = data["vehicle_params"]
    assert isinstance(vp_dict, dict)
    dist = data["distance_m"]
    assert isinstance(dist, list)
    speed_mph = data["optimal_speed_mph"]
    assert isinstance(speed_mph, list)
    corner_mph = data["max_cornering_speed_mph"]
    assert isinstance(corner_mph, list)
    brake_pts = data["brake_points"]
    assert isinstance(brake_pts, list)
    throttle_pts = data["throttle_points"]
    assert isinstance(throttle_pts, list)
    lap_time = data["lap_time_s"]
    assert isinstance(lap_time, (int, float))

    return OptimalProfile(
        distance_m=np.array(dist),
        optimal_speed_mps=np.array(speed_mph) / MPS_TO_MPH,
        curvature=np.zeros(len(dist)),  # not stored; not needed for comparison
        max_cornering_speed_mps=np.array(corner_mph) / MPS_TO_MPH,
        optimal_brake_points=brake_pts,
        optimal_throttle_points=throttle_pts,
        lap_time_s=float(lap_time),
        vehicle_params=VehicleParams(
            mu=vp_dict["mu"],
            max_accel_g=vp_dict["max_accel_g"],
            max_decel_g=vp_dict["max_decel_g"],
            max_lateral_g=vp_dict["max_lateral_g"],
            top_speed_mps=vp_dict["top_speed_mps"],
            calibrated=vp_dict["calibrated"],
        ),
    )


async def get_optimal_comparison_data(
    session_data: SessionData,
) -> dict[str, object]:
    """Compare the best lap against the physics-optimal profile per-corner.

    Reuses the track-cached optimal profile from ``get_optimal_profile_data``
    instead of re-solving the velocity model.  The comparison itself (~50ms)
    is always per-session since it depends on the session's best lap telemetry.

    Returns per-corner opportunity gaps sorted by time cost descending,
    plus aggregate lap-time data.
    """
    session_id = session_data.session_id
    profile_id = _current_profile_id(session_id)

    # --- Session-level comparison cache ---
    cached = _get_physics_cached(session_id, "comparison", profile_id)
    if cached is not None:
        return cached

    db_cached = await db_get_cached(session_id, "comparison", profile_id)
    if db_cached is not None:
        _set_physics_cached(
            session_id,
            "comparison",
            db_cached,
            profile_id,
        )
        return db_cached

    # Get optimal profile (reuses track cache — near-instant if cached)
    profile_data = await get_optimal_profile_data(session_data)

    def _compute() -> dict[str, object]:
        optimal = _reconstruct_optimal_profile(profile_data)
        best_lap_df = session_data.processed.resampled_laps[session_data.processed.best_lap]
        corners = session_data.corners

        result = compare_with_optimal(best_lap_df, corners, optimal)

        if not result.is_valid:
            logger.warning(
                "Optimal comparison INVALID sid=%s: total_gap=%.3f reasons=%s",
                session_id,
                result.total_gap_s,
                result.invalid_reasons,
            )

        # Detect linked corner groups (chicanes/esses) from optimal speed profile
        linked = detect_linked_corners(corners, optimal.optimal_speed_mps, optimal.distance_m)

        return {
            "corner_opportunities": [
                {
                    "corner_number": opp.corner_number,
                    "actual_min_speed_mph": round(
                        opp.actual_min_speed_mps * MPS_TO_MPH,
                        2,
                    ),
                    "optimal_min_speed_mph": round(
                        opp.optimal_min_speed_mps * MPS_TO_MPH,
                        2,
                    ),
                    "speed_gap_mph": round(opp.speed_gap_mph, 2),
                    "brake_gap_m": (
                        round(opp.brake_gap_m, 2) if opp.brake_gap_m is not None else None
                    ),
                    "throttle_gap_m": (
                        round(opp.throttle_gap_m, 2) if opp.throttle_gap_m is not None else None
                    ),
                    "time_cost_s": round(opp.time_cost_s, 3),
                    "linked_group_id": linked.corner_to_group.get(opp.corner_number),
                    "exit_straight_time_cost_s": round(opp.exit_straight_time_cost_s, 3),
                }
                for opp in result.corner_opportunities
            ],
            "actual_lap_time_s": round(result.actual_lap_time_s, 3),
            "optimal_lap_time_s": round(result.optimal_lap_time_s, 3),
            "total_gap_s": round(result.total_gap_s, 3),
            "is_valid": result.is_valid,
            "invalid_reasons": result.invalid_reasons,
        }

    result = await asyncio.to_thread(_compute)
    _set_physics_cached(session_id, "comparison", result, profile_id)
    await db_set_cached(session_id, "comparison", result, profile_id)

    # Update Bayesian per-corner capability factors from comparison results.
    # Only for authenticated users on known tracks with valid comparison data.
    track_slug = track_slug_from_layout(session_data.layout) if session_data.layout else None
    vp_mu: float | None = None
    vp_dict = profile_data.get("vehicle_params")
    if isinstance(vp_dict, dict):
        raw_mu = vp_dict.get("mu")
        if isinstance(raw_mu, (int, float)):
            vp_mu = float(raw_mu)
    corner_opps = result.get("corner_opportunities")
    if (
        track_slug
        and session_data.user_id
        and session_data.user_id != "anon"
        and isinstance(corner_opps, list)
        and corner_opps
        and vp_mu is not None
        and vp_mu > 0
    ):
        try:
            from cataclysm.corner_capability import (
                bayesian_update_capability,
                compute_c_obs,
            )

            from backend.api.db.database import async_session_factory
            from backend.api.services.corner_capability_store import (
                get_corner_capabilities,
                upsert_corner_capability,
            )

            # Resolve curvature for apex kappa lookup
            curvature_result, _ = _resolve_curvature_and_elevation(session_data, None)
            # Build corner number → apex distance map
            apex_map: dict[int, float] = {}
            for c in session_data.corners or []:
                if c.apex_distance_m is not None:
                    apex_map[c.number] = c.apex_distance_m

            async with async_session_factory() as db:
                existing = await get_corner_capabilities(db, track_slug, session_data.user_id)
                for opp in corner_opps:
                    cn = opp.get("corner_number")
                    actual_mph = opp.get("actual_min_speed_mph")
                    if cn is None or actual_mph is None or actual_mph <= 0:
                        continue
                    apex_dist = apex_map.get(cn)
                    if apex_dist is None:
                        continue
                    kappa_idx = int(np.searchsorted(curvature_result.distance_m, apex_dist))
                    kappa_idx = min(kappa_idx, len(curvature_result.abs_curvature) - 1)
                    kappa = float(curvature_result.abs_curvature[kappa_idx])
                    if kappa < 0.001:
                        continue
                    # Convert actual speed from mph back to m/s
                    actual_mps = actual_mph / MPS_TO_MPH
                    c_obs = compute_c_obs(actual_mps, kappa, vp_mu)
                    mu_prior, sigma_prior, n_obs = existing.get(cn, (1.0, 0.10, 0))
                    mu_post, sigma_post = bayesian_update_capability(
                        mu_prior, sigma_prior, c_obs, sigma_obs=0.09
                    )
                    await upsert_corner_capability(
                        db,
                        track_slug,
                        cn,
                        session_data.user_id,
                        mu_post,
                        sigma_post,
                        n_obs + 1,
                    )
                await db.commit()
            logger.debug(
                "Updated C-factors for sid=%s track=%s user=%s",
                session_id,
                track_slug,
                session_data.user_id,
            )
        except Exception:
            logger.debug("Failed to update C-factors", exc_info=True)

    return result

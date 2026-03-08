"""Pipeline service: wraps cataclysm/ processing functions.

Orchestrates the full CSV-to-analysis pipeline:
  CSV bytes -> parser.parse_racechrono_csv -> engine.process_session
  -> corners/consistency/gains/grip -> session snapshot

All CPU-bound cataclysm functions are run via asyncio.to_thread().
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
from cataclysm.consistency import compute_session_consistency
from cataclysm.constants import MPS_TO_MPH
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
)
from cataclysm.optimal_comparison import compare_with_optimal
from cataclysm.parser import ParsedSession, parse_racechrono_csv
from cataclysm.track_db import locate_official_corners
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
    # Fire-and-forget DB invalidation (will be awaited by the event loop)
    asyncio.ensure_future(db_invalidate_session(session_id))


def invalidate_profile_cache(profile_id: str) -> None:
    """Clear all physics cache entries using a specific profile (in-memory + DB)."""
    keys_to_remove = [k for k in _physics_cache if k[1] == profile_id]
    for k in keys_to_remove:
        del _physics_cache[k]
    if keys_to_remove:
        logger.info(
            "Invalidated %d in-memory physics cache entries for profile %s",
            len(keys_to_remove),
            profile_id,
        )
    asyncio.ensure_future(db_invalidate_profile(profile_id))


# ---------------------------------------------------------------------------
# Track-level physics cache: shares optimal profile across sessions on the
# same track with the same equipment. Key includes calibrated_mu (2dp) so
# sessions with materially different grip don't share.
# Key = (f"{track_slug}:{endpoint}", profile_id_or_None, calibrated_mu_str)
# Value = (result_dict, timestamp)
# ---------------------------------------------------------------------------
_track_physics_cache: dict[tuple[str, str | None, str], tuple[dict[str, object], float]] = {}
TRACK_CACHE_TTL_S = 3600  # 1 hour — track geometry doesn't change


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
    # ensure_future needs an event loop; suppress RuntimeError when called
    # from a threadpool (sync context).  Stale DB entries self-correct via
    # code_version check on next read.
    with contextlib.suppress(RuntimeError):
        asyncio.ensure_future(db_invalidate_track(track_slug))


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
    coaching_laps = [n for n in all_laps if n not in anomalous and n not in in_out]

    # If the overall best lap was excluded as in/out, include it — a fast
    # first/last lap is clearly not a warm-up or cooldown.
    best = processed.best_lap
    if best not in anomalous and best not in coaching_laps:
        coaching_laps.append(best)
        coaching_laps.sort()

    # 3b. Assess GPS quality
    gps_quality: GPSQualityReport | None = None
    try:
        gps_source = parsed.raw_data if parsed.raw_data is not None else parsed.data
        gps_quality = assess_gps_quality(gps_source, processed, anomalous)
    except (ValueError, KeyError, IndexError):
        logger.warning("Failed to assess GPS quality for %s", filename, exc_info=True)

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
    layout = detect_track_or_lookup(parsed.data, parsed.metadata.track_name)
    if layout is not None:
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

    # 5c. Corner line analysis (if reference centerline available)
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
        gps_quality_score=gps_quality.overall_score if gps_quality else 100.0,
        gps_quality_grade=gps_quality.grade if gps_quality else "A",
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


async def process_upload(file_bytes: bytes, filename: str) -> dict[str, object]:
    """Parse a RaceChrono CSV and run the full processing pipeline.

    Runs CPU-bound work in a thread to avoid blocking the event loop.
    Returns a dict with session_id and summary metadata.
    """
    session_data = await asyncio.to_thread(_run_pipeline_sync, file_bytes, filename)
    store_session(session_data.session_id, session_data)

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

    def _compute() -> dict[str, object]:
        processed = session_data.processed
        best_lap_df = processed.resampled_laps[processed.best_lap]

        # Use canonical track reference if available, else per-session curvature
        curvature_result, resolved_alt = _resolve_curvature_and_elevation(
            session_data,
            lidar_alt,
        )

        mu_array = None

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
                    "time_cost_s": round(opp.time_cost_s, 3),
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
    return result

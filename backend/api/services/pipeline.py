"""Pipeline service: wraps cataclysm/ processing functions.

Orchestrates the full CSV-to-analysis pipeline:
  CSV bytes -> parser.parse_racechrono_csv -> engine.process_session
  -> corners/consistency/gains/grip -> session snapshot

All CPU-bound cataclysm functions are run via asyncio.to_thread().
"""

from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path
from typing import Any

from cataclysm.consistency import compute_session_consistency
from cataclysm.constants import MPS_TO_MPH
from cataclysm.corners import Corner, detect_corners, extract_corner_kpis_for_lap
from cataclysm.curvature import compute_curvature
from cataclysm.elevation import compute_corner_elevation, enrich_corners_with_elevation
from cataclysm.engine import LapSummary, ProcessedSession, find_anomalous_laps, process_session
from cataclysm.equipment import equipment_to_vehicle_params
from cataclysm.gains import (
    GainEstimate,
    build_segments,
    compute_segment_times,
    estimate_gains,
    reconstruct_ideal_lap,
)
from cataclysm.gps_quality import GPSQualityReport, assess_gps_quality
from cataclysm.grip import estimate_grip_limit
from cataclysm.parser import ParsedSession, parse_racechrono_csv
from cataclysm.track_db import locate_official_corners
from cataclysm.track_match import detect_track_or_lookup
from cataclysm.trends import SessionSnapshot, build_session_snapshot
from cataclysm.velocity_profile import VehicleParams, compute_optimal_profile

from backend.api.services import equipment_store
from backend.api.services.session_store import SessionData, store_session

logger = logging.getLogger(__name__)


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

    # 3b. Assess GPS quality
    gps_quality: GPSQualityReport | None = None
    try:
        gps_quality = assess_gps_quality(parsed.data, processed, anomalous)
    except (ValueError, KeyError, IndexError):
        logger.warning("Failed to assess GPS quality for %s", filename, exc_info=True)

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
    )


def _fallback_lap_consistency(summaries: list[LapSummary], anomalous: set[int]) -> Any:
    """Create a minimal LapConsistency when full consistency computation fails."""
    from cataclysm.consistency import compute_lap_consistency

    return compute_lap_consistency(summaries, anomalous)


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


def _resolve_vehicle_params(session_id: str) -> VehicleParams | None:
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


async def get_optimal_profile_data(session_data: SessionData) -> dict[str, object]:
    """Compute the physics-optimal velocity profile for a session.

    Uses the best lap's GPS data to derive track curvature, then runs the
    forward-backward velocity solver.  If the session has equipment assigned,
    the equipment-derived VehicleParams are used; otherwise the solver's
    built-in defaults apply.

    Returns columnar data suitable for JSON serialisation.
    """
    session_id = session_data.session_id

    def _compute() -> dict[str, object]:
        processed = session_data.processed
        best_lap_df = processed.resampled_laps[processed.best_lap]

        # Derive curvature from GPS
        curvature_result = compute_curvature(best_lap_df)

        # Equipment-aware vehicle params
        vehicle_params = _resolve_vehicle_params(session_id)

        # Solve optimal velocity profile
        optimal = compute_optimal_profile(curvature_result, params=vehicle_params)

        # Look up equipment profile ID for the response metadata
        se = equipment_store.get_session_equipment(session_id)
        profile_id = se.profile_id if se is not None else None

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
            },
            "equipment_profile_id": profile_id,
        }

    return await asyncio.to_thread(_compute)

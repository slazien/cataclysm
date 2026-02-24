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
from cataclysm.corners import Corner, detect_corners, extract_corner_kpis_for_lap
from cataclysm.engine import LapSummary, ProcessedSession, find_anomalous_laps, process_session
from cataclysm.gains import (
    GainEstimate,
    build_segments,
    compute_segment_times,
    estimate_gains,
    reconstruct_ideal_lap,
)
from cataclysm.grip import estimate_grip_limit
from cataclysm.parser import ParsedSession, parse_racechrono_csv
from cataclysm.track_db import locate_official_corners, lookup_track
from cataclysm.trends import SessionSnapshot, build_session_snapshot

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

    # 4. Detect corners (track_db lookup first, fallback to detect_corners)
    best_lap_df = processed.resampled_laps[processed.best_lap]
    layout = lookup_track(parsed.metadata.track_name)
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
        except Exception:
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
        except Exception:
            logger.warning("Failed to estimate gains for %s", filename, exc_info=True)

    # 8. Estimate grip
    grip = None
    if coaching_laps:
        try:
            grip = estimate_grip_limit(processed.resampled_laps, coaching_laps)
        except Exception:
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
            "speed_mph": (ideal.speed_mps * 2.23694).tolist(),
            "segment_sources": ideal.segment_sources,
        }

    return await asyncio.to_thread(_compute)

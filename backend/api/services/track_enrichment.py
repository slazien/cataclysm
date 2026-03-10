"""Auto-enrichment orchestrator for track data pipeline v2.

Runs the full enrichment sequence on a track's centerline lat/lon arrays:
  1. Adaptive corner detection
  2. Corner type classification
  3. Elevation fetch (chain)
  4. Brake marker computation
  5. Step logging in track_enrichment_log
  6. Persist corners + landmarks to DB
  7. Update track quality_tier
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd
from cataclysm.brake_markers import compute_brake_markers
from cataclysm.corner_classifier import classify_corner
from cataclysm.corners import Corner, detect_corners_adaptive
from cataclysm.elevation_chain import fetch_best_elevation
from cataclysm.track_db import OfficialCorner
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import Track, TrackEnrichmentLog
from backend.api.services.track_store import upsert_corners, upsert_landmarks

logger = logging.getLogger(__name__)

# Minimum points required for meaningful centerline geometry
_MIN_POINTS = 3


async def _log_step(
    db: AsyncSession,
    track_id: int,
    step: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Write a single enrichment step to the audit log."""
    db.add(
        TrackEnrichmentLog(
            track_id=track_id,
            step=step,
            status=status,
            details=details,
        )
    )
    await db.flush()


def _haversine_cumulative_distance(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Compute cumulative haversine distance (metres) along a lat/lon path."""
    earth_radius_m = 6_371_000.0
    lat_r = np.radians(lats)
    lon_r = np.radians(lons)
    d_lat = np.diff(lat_r)
    dlon = np.diff(lon_r)
    a = np.sin(d_lat / 2) ** 2 + np.cos(lat_r[:-1]) * np.cos(lat_r[1:]) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    seg = earth_radius_m * c
    return np.concatenate([[0.0], np.cumsum(seg)])


def _compute_heading(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Compute forward azimuth (bearing) in degrees at each point."""
    lat_r = np.radians(lats)
    lon_r = np.radians(lons)
    dlon = np.diff(lon_r)
    x = np.sin(dlon) * np.cos(lat_r[1:])
    y = np.cos(lat_r[:-1]) * np.sin(lat_r[1:]) - (
        np.sin(lat_r[:-1]) * np.cos(lat_r[1:]) * np.cos(dlon)
    )
    bearing = np.degrees(np.arctan2(x, y)) % 360
    # Repeat last heading for equal-length array
    return np.append(bearing, bearing[-1])


def _build_centerline_df(
    lats: np.ndarray,
    lons: np.ndarray,
    distance: np.ndarray,
) -> pd.DataFrame:
    """Build a synthetic DataFrame suitable for detect_corners_adaptive.

    The detector needs heading_deg, speed_mps, lap_distance_m, and
    longitudinal_g columns.  speed_mps and longitudinal_g are filled
    with dummy values because the enrichment only cares about geometric
    corner positions, not telemetry-derived KPIs.
    """
    heading = _compute_heading(lats, lons)
    n = len(lats)
    return pd.DataFrame(
        {
            "lap_distance_m": distance,
            "heading_deg": heading,
            "speed_mps": np.full(n, 30.0),  # dummy constant speed
            "longitudinal_g": np.zeros(n),  # dummy zero deceleration
            "lat": lats,
            "lon": lons,
        }
    )


def _integrated_heading_change_deg(
    distance_m: np.ndarray,
    heading_deg: np.ndarray,
    entry_distance_m: float,
    exit_distance_m: float,
) -> float:
    """Return absolute integrated heading change through a corner zone."""
    entry_idx = int(np.searchsorted(distance_m, entry_distance_m))
    exit_idx = int(np.searchsorted(distance_m, exit_distance_m))
    entry_idx = max(0, min(entry_idx, len(heading_deg) - 1))
    exit_idx = max(0, min(exit_idx, len(heading_deg) - 1))
    if exit_idx <= entry_idx:
        return 0.0

    diff = np.diff(heading_deg[entry_idx : exit_idx + 1])
    diff = (diff + 180.0) % 360.0 - 180.0
    return float(abs(np.sum(diff)))


def _corner_to_official(
    corner: Corner,
    track_length_m: float,
    classification: str | None,
) -> OfficialCorner:
    """Convert a detected Corner + classification to OfficialCorner for brake markers."""
    fraction = corner.apex_distance_m / track_length_m if track_length_m > 0 else 0.0
    return OfficialCorner(
        number=corner.number,
        name=corner.name or f"T{corner.number}",
        fraction=fraction,
        lat=corner.apex_lat,
        lon=corner.apex_lon,
        character=corner.character,
        direction=corner.direction,
        corner_type=classification,
    )


def _corner_to_db_dict(
    corner: Corner,
    track_length_m: float,
    classification: str | None,
    confidence: float,
) -> dict[str, Any]:
    """Convert a detected Corner to a dict suitable for upsert_corners."""
    fraction = corner.apex_distance_m / track_length_m if track_length_m > 0 else 0.0
    return {
        "number": corner.number,
        "name": f"T{corner.number}",
        "fraction": round(fraction, 6),
        "lat": corner.apex_lat,
        "lon": corner.apex_lon,
        "character": corner.character,
        "direction": corner.direction,
        "corner_type": classification,
        "auto_detected": True,
        "confidence": round(confidence, 3),
        "detection_method": corner.detection_method or "heading_rate",
    }


def _landmark_to_db_dict(landmark: Any) -> dict[str, Any]:
    """Convert a Landmark dataclass to a dict for upsert_landmarks."""
    d = asdict(landmark)
    # Convert LandmarkType enum to string
    d["landmark_type"] = (
        d["landmark_type"].value
        if hasattr(d["landmark_type"], "value")
        else str(d["landmark_type"])
    )
    d["source"] = "auto_enrichment"
    d["confidence"] = 0.8
    return d


async def enrich_track(
    db: AsyncSession,
    track_id: int,
    lats: np.ndarray,
    lons: np.ndarray,
    *,
    track_length_m: float | None = None,
) -> dict[str, Any]:
    """Run full enrichment pipeline on a track.

    Returns dict with: corners_detected, elevation_source, brake_markers, steps_logged
    """
    steps_logged = 0
    result: dict[str, Any] = {
        "corners_detected": 0,
        "elevation_source": None,
        "brake_markers": 0,
        "steps_logged": 0,
    }

    # --- Guard: insufficient points ---
    if len(lats) < _MIN_POINTS or len(lons) < _MIN_POINTS:
        await _log_step(
            db,
            track_id,
            "validation",
            "error",
            {"reason": "insufficient_points", "count": len(lats)},
        )
        result["steps_logged"] = 1
        result["error"] = "insufficient_points"
        return result

    # --- Compute distance array ---
    distance = _haversine_cumulative_distance(lats, lons)
    total_length = float(distance[-1])
    if track_length_m is None:
        track_length_m = total_length

    step_m = float(np.median(np.diff(distance))) if len(distance) > 1 else 0.7

    # --- Step 1: Corner detection ---
    corners: list[Corner] = []
    try:
        df = _build_centerline_df(lats, lons, distance)
        corners = await asyncio.to_thread(detect_corners_adaptive, df, step_m)
        result["corners_detected"] = len(corners)
        await _log_step(
            db,
            track_id,
            "corner_detect",
            "success",
            {"corners_found": len(corners), "track_length_m": round(track_length_m, 1)},
        )
        steps_logged += 1
    except Exception:
        logger.exception("Corner detection failed for track %d", track_id)
        await _log_step(
            db,
            track_id,
            "corner_detect",
            "error",
            {"reason": "exception"},
        )
        steps_logged += 1

    # --- Step 2: Corner classification ---
    classifications: dict[int, tuple[str, float]] = {}
    try:
        distance_arr = df["lap_distance_m"].to_numpy(dtype=float)
        heading_arr = df["heading_deg"].to_numpy(dtype=float)
        for c in corners:
            if c.peak_curvature is not None:
                heading_deg = _integrated_heading_change_deg(
                    distance_arr,
                    heading_arr,
                    c.entry_distance_m,
                    c.exit_distance_m,
                )
                arc_length = c.exit_distance_m - c.entry_distance_m
                cls = classify_corner(
                    peak_curvature=c.peak_curvature,
                    heading_change_deg=heading_deg,
                    arc_length_m=arc_length,
                )
                classifications[c.number] = (cls.corner_type, cls.confidence)
        await _log_step(
            db,
            track_id,
            "classification",
            "success",
            {"classified": len(classifications)},
        )
        steps_logged += 1
    except Exception:
        logger.exception("Classification failed for track %d", track_id)
        await _log_step(
            db,
            track_id,
            "classification",
            "error",
            {"reason": "exception"},
        )
        steps_logged += 1

    # --- Step 3: Elevation fetch ---
    try:
        elevation = await fetch_best_elevation(lats, lons)
        result["elevation_source"] = elevation.source
        details: dict[str, Any] = {
            "source": elevation.source,
            "points": len(elevation.altitude_m),
            "accuracy_m": elevation.accuracy_m,
        }
        if len(elevation.altitude_m) > 0:
            elev_range = float(np.ptp(elevation.altitude_m))
            details["elevation_range_m"] = round(elev_range, 1)
        await _log_step(db, track_id, "elevation", "success", details)
        steps_logged += 1
    except Exception:
        logger.exception("Elevation fetch failed for track %d", track_id)
        await _log_step(
            db,
            track_id,
            "elevation",
            "error",
            {"reason": "exception"},
        )
        steps_logged += 1

    # --- Step 4: Brake markers ---
    brake_landmarks: list[Any] = []
    try:
        if corners:
            official_corners = [
                _corner_to_official(
                    c,
                    track_length_m,
                    classifications.get(c.number, (None, 0.0))[0],
                )
                for c in corners
            ]
            brake_landmarks = compute_brake_markers(official_corners, track_length_m)
            result["brake_markers"] = len(brake_landmarks)
        await _log_step(
            db,
            track_id,
            "brake_markers",
            "success" if corners else "skipped",
            {"markers": len(brake_landmarks)},
        )
        steps_logged += 1
    except Exception:
        logger.exception("Brake marker computation failed for track %d", track_id)
        await _log_step(
            db,
            track_id,
            "brake_markers",
            "error",
            {"reason": "exception"},
        )
        steps_logged += 1

    # --- Step 5: Persist corners ---
    try:
        if corners:
            corner_dicts = [
                _corner_to_db_dict(
                    c,
                    track_length_m,
                    classifications.get(c.number, (None, 0.0))[0],
                    classifications.get(c.number, (None, 0.0))[1],
                )
                for c in corners
            ]
            await upsert_corners(db, track_id, corner_dicts)
    except Exception:
        logger.exception("Corner persist failed for track %d", track_id)

    # --- Step 6: Persist landmarks ---
    try:
        if brake_landmarks:
            landmark_dicts = [_landmark_to_db_dict(lm) for lm in brake_landmarks]
            await upsert_landmarks(db, track_id, landmark_dicts)
    except Exception:
        logger.exception("Landmark persist failed for track %d", track_id)

    # --- Step 7: Update quality_tier ---
    try:
        track = await db.get(Track, track_id)
        if track is not None:
            track.quality_tier = 1  # auto-detected draft
            await db.flush()
    except Exception:
        logger.exception("Quality tier update failed for track %d", track_id)

    result["steps_logged"] = steps_logged
    return result

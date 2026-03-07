"""Canonical per-track curvature and elevation reference.

Builds a deterministic curvature profile from multi-lap GPS averaging so that
the velocity solver produces the same optimal lap time for the same track +
equipment combination, regardless of per-session GPS noise.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.interpolate import interp1d

from cataclysm.curvature import CurvatureResult, compute_curvature
from cataclysm.curvature_averaging import compute_averaged_curvature
from cataclysm.engine import ProcessedSession
from cataclysm.track_db import TrackLayout

logger = logging.getLogger(__name__)

# Where canonical references are stored on disk.
_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "track_reference"

# If track lengths differ by more than this fraction, log a warning.
LENGTH_MISMATCH_WARN_THRESHOLD = 0.05

# Minimum GPS quality improvement to trigger a rebuild.
GPS_QUALITY_IMPROVEMENT_THRESHOLD = 5.0


@dataclass
class TrackReference:
    """Canonical curvature and elevation for a known track."""

    track_slug: str
    curvature_result: CurvatureResult
    elevation_m: np.ndarray | None
    reference_lats: np.ndarray
    reference_lons: np.ndarray
    gps_quality_score: float
    built_from_session_id: str
    n_laps_averaged: int
    track_length_m: float
    updated_at: str


def track_slug_from_layout(layout: TrackLayout) -> str:
    """Deterministic slug from a TrackLayout name.

    Lowercases, strips non-alphanumeric characters, and joins with hyphens.
    """
    slug = layout.name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _reference_path(slug: str) -> Path:
    return _DATA_DIR / f"{slug}.npz"


def get_track_reference(layout: TrackLayout) -> TrackReference | None:
    """Load a canonical track reference from disk, or return None."""
    slug = track_slug_from_layout(layout)
    path = _reference_path(slug)
    if not path.exists():
        return None

    try:
        # allow_pickle=False is the secure default — npz contains only arrays
        data = np.load(str(path), allow_pickle=False)
        meta = json.loads(str(data["metadata"]))

        elevation = data.get("elevation_m", None)
        if elevation is not None and len(elevation) == 0:
            elevation = None

        return TrackReference(
            track_slug=meta["track_slug"],
            curvature_result=CurvatureResult(
                distance_m=data["distance_m"],
                curvature=data["curvature"],
                abs_curvature=np.abs(data["curvature"]),
                heading_rad=data["heading_rad"],
                x_smooth=data["x_smooth"],
                y_smooth=data["y_smooth"],
            ),
            elevation_m=elevation,
            reference_lats=data["reference_lats"],
            reference_lons=data["reference_lons"],
            gps_quality_score=float(meta["gps_quality_score"]),
            built_from_session_id=meta["built_from_session_id"],
            n_laps_averaged=int(meta["n_laps_averaged"]),
            track_length_m=float(meta["track_length_m"]),
            updated_at=meta["updated_at"],
        )
    except (KeyError, ValueError, json.JSONDecodeError, EOFError, OSError):
        logger.warning("Failed to load track reference from %s", path, exc_info=True)
        return None


def _save_reference(ref: TrackReference) -> None:
    """Atomically write a TrackReference to disk as .npz."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _reference_path(ref.track_slug)

    meta = json.dumps(
        {
            "track_slug": ref.track_slug,
            "gps_quality_score": ref.gps_quality_score,
            "built_from_session_id": ref.built_from_session_id,
            "n_laps_averaged": ref.n_laps_averaged,
            "track_length_m": ref.track_length_m,
            "updated_at": ref.updated_at,
        }
    )

    arrays: dict[str, np.ndarray] = {
        "distance_m": ref.curvature_result.distance_m,
        "curvature": ref.curvature_result.curvature,
        "heading_rad": ref.curvature_result.heading_rad,
        "x_smooth": ref.curvature_result.x_smooth,
        "y_smooth": ref.curvature_result.y_smooth,
        "reference_lats": ref.reference_lats,
        "reference_lons": ref.reference_lons,
        "metadata": np.array(meta),
    }
    if ref.elevation_m is not None:
        arrays["elevation_m"] = ref.elevation_m

    # Atomic write: write to temp file then rename.
    # np.savez_compressed appends .npz if not present, so use .npz suffix
    # and rename after writing.
    fd, tmp_path = tempfile.mkstemp(dir=str(_DATA_DIR), suffix=".tmp.npz")
    try:
        os.close(fd)
        # savez_compressed won't append .npz since the path already ends with it
        np.savez_compressed(tmp_path, **arrays)  # type: ignore[arg-type]
        os.replace(tmp_path, str(path))
        logger.info(
            "Saved track reference: %s (%d laps, %.0fm, quality=%.1f)",
            ref.track_slug,
            ref.n_laps_averaged,
            ref.track_length_m,
            ref.gps_quality_score,
        )
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def build_track_reference(
    layout: TrackLayout,
    session_data: ProcessedSession,
    coaching_laps: list[int],
    session_id: str,
    gps_quality_score: float,
    lidar_alt: np.ndarray | None = None,
) -> TrackReference:
    """Build a canonical track reference from a session's coaching laps.

    If >= 3 coaching laps, uses multi-lap averaged curvature.
    Otherwise, uses single best-lap curvature.
    """
    slug = track_slug_from_layout(layout)
    best_lap_df = session_data.resampled_laps[session_data.best_lap]

    if len(coaching_laps) >= 3:
        laps = {n: session_data.resampled_laps[n] for n in coaching_laps}
        curvature_result = compute_averaged_curvature(laps, step_m=0.7, smoothing=None)
        n_averaged = len(coaching_laps)
    else:
        curvature_result = compute_curvature(best_lap_df, savgol_window=21)
        n_averaged = 1

    track_length_m = float(curvature_result.distance_m[-1])

    # Align LIDAR elevation to the curvature distance grid if lengths differ.
    # lidar_alt comes from best_lap_df (M points), while curvature_result may
    # have N points from the averaged distance grid. Interpolate to match.
    aligned_elev = lidar_alt
    if lidar_alt is not None and len(lidar_alt) != len(curvature_result.distance_m):
        best_dist = best_lap_df["lap_distance_m"].to_numpy()
        best_norm = best_dist / best_dist[-1]
        curv_norm = curvature_result.distance_m / curvature_result.distance_m[-1]
        aligned_elev = np.interp(curv_norm, best_norm, lidar_alt)

    ref = TrackReference(
        track_slug=slug,
        curvature_result=curvature_result,
        elevation_m=aligned_elev,
        reference_lats=best_lap_df["lat"].to_numpy(dtype=np.float64),
        reference_lons=best_lap_df["lon"].to_numpy(dtype=np.float64),
        gps_quality_score=gps_quality_score,
        built_from_session_id=session_id,
        n_laps_averaged=n_averaged,
        track_length_m=track_length_m,
        updated_at=datetime.now(UTC).isoformat(),
    )
    _save_reference(ref)
    return ref


def maybe_update_track_reference(
    layout: TrackLayout,
    session_data: ProcessedSession,
    coaching_laps: list[int],
    session_id: str,
    gps_quality_score: float,
    lidar_alt: np.ndarray | None = None,
) -> TrackReference | None:
    """Rebuild the track reference if the new session has better GPS quality.

    Returns the new reference if rebuilt, or None if the existing one is kept.
    """
    existing = get_track_reference(layout)
    if existing is None:
        return build_track_reference(
            layout, session_data, coaching_laps, session_id, gps_quality_score, lidar_alt
        )

    improvement = gps_quality_score - existing.gps_quality_score
    if improvement >= GPS_QUALITY_IMPROVEMENT_THRESHOLD:
        logger.info(
            "Rebuilding track reference for %s: quality %.1f -> %.1f (+%.1f)",
            track_slug_from_layout(layout),
            existing.gps_quality_score,
            gps_quality_score,
            improvement,
        )
        return build_track_reference(
            layout, session_data, coaching_laps, session_id, gps_quality_score, lidar_alt
        )

    return None


def align_reference_to_session(
    ref: TrackReference,
    session_distance_m: np.ndarray,
) -> tuple[CurvatureResult, np.ndarray | None]:
    """Interpolate canonical curvature/elevation onto a session's distance grid.

    Handles slight track-length differences between the reference and the
    session (GPS line variation). Warns if lengths differ by > 5%.
    """
    ref_dist = ref.curvature_result.distance_m
    session_length = float(session_distance_m[-1])
    ref_length = ref.track_length_m

    length_diff = abs(session_length - ref_length) / ref_length
    if length_diff > LENGTH_MISMATCH_WARN_THRESHOLD:
        logger.warning(
            "Track length mismatch: reference=%.1fm, session=%.1fm (%.1f%% diff)",
            ref_length,
            session_length,
            length_diff * 100,
        )

    # Normalise distances to [0, 1] for interpolation
    ref_norm = ref_dist / ref_dist[-1]
    session_norm = session_distance_m / session_distance_m[-1]

    # Clamp session normalised distances to reference range (handles tiny overflows)
    session_norm_clamped = np.clip(session_norm, ref_norm[0], ref_norm[-1])

    # Interpolate curvature arrays
    curvature = np.interp(session_norm_clamped, ref_norm, ref.curvature_result.curvature)
    # Unwrap heading before interpolation to avoid errors at ±π boundary,
    # then re-wrap to [-π, π] after.
    unwrapped = np.unwrap(ref.curvature_result.heading_rad)
    heading_interp = np.interp(session_norm_clamped, ref_norm, unwrapped)
    heading = (heading_interp + np.pi) % (2 * np.pi) - np.pi
    x_smooth = np.interp(session_norm_clamped, ref_norm, ref.curvature_result.x_smooth)
    y_smooth = np.interp(session_norm_clamped, ref_norm, ref.curvature_result.y_smooth)

    aligned_curvature = CurvatureResult(
        distance_m=session_distance_m,
        curvature=curvature,
        abs_curvature=np.abs(curvature),
        heading_rad=heading,
        x_smooth=x_smooth,
        y_smooth=y_smooth,
    )

    # Interpolate elevation if available
    aligned_elevation: np.ndarray | None = None
    if ref.elevation_m is not None:
        ref_elev_norm = np.linspace(0.0, 1.0, len(ref.elevation_m))
        f_elev = interp1d(ref_elev_norm, ref.elevation_m, kind="linear", fill_value="extrapolate")
        aligned_elevation = np.asarray(f_elev(session_norm_clamped))

    return aligned_curvature, aligned_elevation

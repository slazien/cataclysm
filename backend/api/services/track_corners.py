"""Track corner version tracking and staleness detection.

The hybrid cache (track_db_hybrid) is the single source of truth for corners.
Legacy TrackCornerConfig entries are migrated to TrackCornerV2 at startup.
A content-hash cache enables the pipeline to detect stale corners and reapply.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from cataclysm.consistency import compute_session_consistency
from cataclysm.corner_line import analyze_corner_lines
from cataclysm.corners import Corner, extract_corner_kpis_for_lap
from cataclysm.elevation import compute_corner_elevation, enrich_corners_with_elevation
from cataclysm.gains import estimate_gains
from cataclysm.track_db import OfficialCorner, TrackLayout, locate_official_corners
from cataclysm.track_reference import track_slug_from_layout
from cataclysm.trends import build_session_snapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.api.services.session_store import SessionData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Version hash cache: track_slug → content hash of corners
# Used by ensure_corners_current() to detect admin edits after upload.
# ---------------------------------------------------------------------------
_corner_hashes: dict[str, str] = {}


def _corners_content_hash(corners_json: list[dict]) -> str:
    """Deterministic hash of corner JSON for restart-safe staleness detection."""
    return hashlib.sha256(json.dumps(corners_json, sort_keys=True).encode()).hexdigest()[:16]


def _official_corners_to_dicts(corners: list[OfficialCorner]) -> list[dict]:
    """Convert OfficialCorner list to JSON-serializable dicts for hashing."""
    return [
        {
            "number": c.number,
            "name": c.name,
            "fraction": c.fraction,
            "character": c.character,
            "direction": c.direction,
            "corner_type": c.corner_type,
            "elevation_trend": c.elevation_trend,
            "camber": c.camber,
            "blind": c.blind,
            "coaching_notes": c.coaching_notes,
            "lat": c.lat,
            "lon": c.lon,
        }
        for c in corners
    ]


def get_corner_override_version(track_slug: str) -> str | None:
    """Return the content hash for a track's corners, or None.

    Uses a content hash (not a counter) so the version is restart-safe — the same
    corners produce the same hash regardless of process lifetime.
    """
    return _corner_hashes.get(track_slug)


def override_layout_corners(
    layout: TrackLayout,
    db_corners: list[OfficialCorner],
) -> TrackLayout:
    """Return a new TrackLayout with corners replaced by DB-edited ones."""
    return replace(layout, corners=db_corners)


def update_corner_hash(track_slug: str, corners_json: list[dict]) -> None:
    """Update the version hash after admin saves corners.

    Called by both admin.py and track_admin.py after corner mutations.
    """
    _corner_hashes[track_slug] = _corners_content_hash(corners_json)
    logger.info("Corner hash updated for %s (%d corners)", track_slug, len(corners_json))


# Legacy alias — callers that still use the old name
update_corner_cache = update_corner_hash


def compute_all_corner_hashes() -> None:
    """Compute content hashes for all tracks in the hybrid cache.

    Called at startup after the hybrid cache is fully populated.
    """
    from cataclysm.track_db_hybrid import get_all_tracks_hybrid

    _corner_hashes.clear()
    for layout in get_all_tracks_hybrid():
        if not layout.corners:
            continue
        slug = track_slug_from_layout(layout)
        dicts = _official_corners_to_dicts(layout.corners)
        _corner_hashes[slug] = _corners_content_hash(dicts)
    logger.info("Computed corner hashes for %d track(s)", len(_corner_hashes))


async def migrate_legacy_corner_configs(db: AsyncSession) -> int:
    """Migrate TrackCornerConfig entries to TrackCornerV2 rows.

    For each legacy entry, if the track exists in the DB but has no TrackCornerV2
    rows, create them from the JSONB blob. Returns the number migrated.
    """
    from cataclysm.track_db_hybrid import db_track_to_layout, update_db_tracks_cache
    from sqlalchemy import select

    from backend.api.db.models import Track, TrackCornerConfig, TrackCornerV2
    from backend.api.services.track_store import upsert_corners

    result = await db.execute(select(TrackCornerConfig))
    configs = result.scalars().all()
    migrated = 0

    for cfg in configs:
        # Find matching Track row
        track_result = await db.execute(select(Track).where(Track.slug == cfg.track_slug))
        track = track_result.scalar_one_or_none()
        if track is None:
            logger.debug("No Track row for legacy config '%s' — skipping migration", cfg.track_slug)
            continue

        # Check if TrackCornerV2 rows already exist
        v2_result = await db.execute(
            select(TrackCornerV2.id).where(TrackCornerV2.track_id == track.id).limit(1)
        )
        if v2_result.scalar_one_or_none() is not None:
            continue  # Already migrated

        # Migrate JSONB corners → TrackCornerV2 rows
        await upsert_corners(db, track.id, cfg.corners_json)
        await db.commit()

        # Refresh hybrid cache with the migrated corners
        from backend.api.services.track_store import get_corners_for_track, get_landmarks_for_track

        corners = await get_corners_for_track(db, track.id)
        landmarks = await get_landmarks_for_track(db, track.id)
        layout = db_track_to_layout(track, corners, landmarks)
        update_db_tracks_cache(track.slug, layout)

        migrated += 1
        logger.info(
            "Migrated legacy corners for '%s' → TrackCornerV2 (%d corners)",
            cfg.track_slug,
            len(cfg.corners_json),
        )

    return migrated


def reapply_corner_overrides_if_stale(sd: SessionData) -> bool:
    """Re-extract corners if the session's corner version is stale.

    Compares the hash captured at upload time against the current hash in
    _corner_hashes. If they differ, the admin edited corners after upload,
    so we re-derive all corner-dependent analytics.

    Mutates sd.corners, sd.all_lap_corners, sd.layout, sd.corner_override_version
    in place. Returns True if corners were updated, False if no change needed.
    """
    if sd.layout is None:
        return False

    slug = track_slug_from_layout(sd.layout)
    current_version = get_corner_override_version(slug)

    if current_version is None:
        return False
    if sd.corner_override_version == current_version:
        return False

    # Session is stale — fetch updated corners from hybrid cache
    from cataclysm.track_db_hybrid import lookup_track_hybrid

    updated_layout = lookup_track_hybrid(slug)
    if updated_layout is None or not updated_layout.corners:
        return False

    new_layout = replace(sd.layout, corners=updated_layout.corners)
    best_lap_df = sd.processed.resampled_laps[sd.processed.best_lap]
    skeletons = locate_official_corners(best_lap_df, new_layout)
    new_best_corners = extract_corner_kpis_for_lap(best_lap_df, skeletons)

    new_all_lap_corners: dict[int, list[Corner]] = {}
    for lap_num in sd.coaching_laps:
        if lap_num == sd.processed.best_lap:
            new_all_lap_corners[lap_num] = new_best_corners
        else:
            lap_df = sd.processed.resampled_laps[lap_num]
            new_all_lap_corners[lap_num] = extract_corner_kpis_for_lap(lap_df, new_best_corners)

    # Elevation enrichment (wrapped in try/except like pipeline does)
    try:
        elev = compute_corner_elevation(best_lap_df, new_best_corners)
        if elev:
            enrich_corners_with_elevation(new_all_lap_corners, elev)
    except (ValueError, KeyError, IndexError):
        logger.warning(
            "Failed elevation during corner reapply for %s",
            sd.session_id,
            exc_info=True,
        )

    # Corner line re-analysis (if GPS data available)
    if sd.gps_traces and sd.reference_centerline:
        try:
            sd.corner_line_profiles = analyze_corner_lines(
                sd.gps_traces,
                sd.reference_centerline,
                new_best_corners,
                resampled_laps=sd.processed.resampled_laps,
                coaching_laps=sd.coaching_laps,
            )
        except (ValueError, KeyError, IndexError):
            logger.warning(
                "Failed corner line re-analysis for %s",
                sd.session_id,
                exc_info=True,
            )

    # Re-derive consistency (corner_consistency depends on all_lap_corners)
    if len(sd.coaching_laps) >= 2:
        try:
            sd.consistency = compute_session_consistency(
                sd.processed.lap_summaries,
                new_all_lap_corners,
                sd.processed.resampled_laps,
                sd.processed.best_lap,
                sd.anomalous_laps,
            )
        except (ValueError, KeyError, IndexError):
            logger.warning(
                "Failed consistency recomputation for %s",
                sd.session_id,
                exc_info=True,
            )

    # Re-estimate gains (uses corners as segment boundaries)
    if len(sd.coaching_laps) >= 2:
        try:
            sd.gains = estimate_gains(
                sd.processed.resampled_laps,
                new_best_corners,
                sd.processed.lap_summaries,
                sd.coaching_laps,
                sd.processed.best_lap,
            )
        except (ValueError, KeyError, IndexError):
            logger.warning(
                "Failed gains recomputation for %s",
                sd.session_id,
                exc_info=True,
            )

    # Rebuild snapshot
    try:
        lap_consistency = (
            sd.consistency.lap_consistency if sd.consistency else sd.snapshot.lap_consistency
        )
        corner_consistency = sd.consistency.corner_consistency if sd.consistency else []
        sd.snapshot = build_session_snapshot(
            metadata=sd.parsed.metadata,
            summaries=sd.processed.lap_summaries,
            lap_consistency=lap_consistency,
            corner_consistency=corner_consistency,
            gains=sd.gains,
            all_lap_corners=new_all_lap_corners,
            anomalous_laps=sd.anomalous_laps,
            file_key=sd.session_id,
            gps_quality_score=sd.snapshot.gps_quality_score,
            gps_quality_grade=sd.snapshot.gps_quality_grade,
        )
    except (ValueError, KeyError, IndexError, AttributeError):
        logger.warning(
            "Failed snapshot rebuild for %s",
            sd.session_id,
            exc_info=True,
        )

    # Mutate in place
    sd.corners = new_best_corners
    sd.all_lap_corners = new_all_lap_corners
    sd.layout = new_layout
    sd.corner_override_version = current_version

    logger.info(
        "Re-applied corner overrides for session %s (v=%s)",
        sd.session_id,
        current_version,
    )
    return True


async def ensure_corners_current(sd: SessionData) -> None:
    """Re-apply corner overrides if stale, invalidating downstream caches."""
    if reapply_corner_overrides_if_stale(sd):
        from backend.api.services.coaching_store import clear_coaching_data
        from backend.api.services.pipeline import invalidate_physics_cache

        invalidate_physics_cache(sd.session_id)
        await clear_coaching_data(sd.session_id)

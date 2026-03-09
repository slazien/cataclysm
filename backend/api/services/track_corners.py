"""Load track corner configs from PostgreSQL (admin-edited overrides).

Maintains an in-memory cache so the synchronous pipeline thread can look up
DB-edited corners without async DB access.
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import TrackCornerConfig

if TYPE_CHECKING:
    from backend.api.services.session_store import SessionData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache: track_slug → list[dict] (raw JSON from DB)
# ---------------------------------------------------------------------------
_corner_overrides: dict[str, list[dict]] = {}
_corner_override_hashes: dict[str, str] = {}
_cache_loaded: bool = False


def _corners_content_hash(corners_json: list[dict]) -> str:
    """Deterministic hash of corner JSON for restart-safe staleness detection."""
    return hashlib.sha256(json.dumps(corners_json, sort_keys=True).encode()).hexdigest()[:16]


def _db_dict_to_official(c: dict) -> OfficialCorner:
    """Convert a single DB corner dict to an OfficialCorner."""
    return OfficialCorner(
        number=c["number"],
        name=c["name"],
        fraction=c["fraction"],
        direction=c.get("direction"),
        corner_type=c.get("corner_type"),
        elevation_trend=c.get("elevation_trend"),
        camber=c.get("camber"),
        coaching_notes=c.get("coaching_note"),
        lat=c.get("lat"),
        lon=c.get("lon"),
    )


def get_corner_override_sync(track_slug: str) -> list[OfficialCorner] | None:
    """Sync getter for the pipeline thread.  Returns None if no DB override."""
    if not _cache_loaded:
        return None
    corners_json = _corner_overrides.get(track_slug)
    if corners_json is None:
        return None
    return [_db_dict_to_official(c) for c in corners_json]


def get_corner_override_version(track_slug: str) -> str | None:
    """Return the content hash for a track's corner override, or None.

    Uses a content hash (not a counter) so the version is restart-safe — the same
    DB corners produce the same hash regardless of process lifetime.
    """
    return _corner_override_hashes.get(track_slug)


def override_layout_corners(
    layout: TrackLayout,
    db_corners: list[OfficialCorner],
) -> TrackLayout:
    """Return a new TrackLayout with corners replaced by DB-edited ones."""
    return replace(layout, corners=db_corners)


def reapply_corner_overrides_if_stale(sd: SessionData) -> bool:
    """Re-extract corners if the session's corner override version is stale.

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

    # Session is stale — re-extract corners from updated DB override
    db_corners = get_corner_override_sync(slug)
    if db_corners is None:
        return False

    new_layout = override_layout_corners(sd.layout, db_corners)
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

    # Rebuild snapshot with updated corner_metrics, corner_consistency,
    # theoretical_best_s, composite_best_s
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


# ---------------------------------------------------------------------------
# Async DB operations
# ---------------------------------------------------------------------------


async def get_track_corners(
    track_slug: str,
    db: AsyncSession,
) -> list[dict] | None:
    """Load corners from DB if available, else return None.

    Caller falls back to ``track_db.py`` hardcoded corners when None.
    """
    result = await db.execute(
        select(TrackCornerConfig).where(TrackCornerConfig.track_slug == track_slug)
    )
    config = result.scalar_one_or_none()
    if config is None:
        return None
    return config.corners_json  # type: ignore[return-value]


async def load_all_corner_overrides(db: AsyncSession) -> None:
    """Load all DB corner overrides into the in-memory cache."""
    global _cache_loaded  # noqa: PLW0603
    result = await db.execute(select(TrackCornerConfig))
    configs = result.scalars().all()
    _corner_overrides.clear()
    _corner_override_hashes.clear()
    for cfg in configs:
        _corner_overrides[cfg.track_slug] = cfg.corners_json
        _corner_override_hashes[cfg.track_slug] = _corners_content_hash(cfg.corners_json)
    _cache_loaded = True
    logger.info("Loaded %d track corner override(s) from DB", len(_corner_overrides))


def update_corner_cache(track_slug: str, corners_json: list[dict]) -> None:
    """Update the in-memory cache after admin saves corners."""
    _corner_overrides[track_slug] = corners_json
    _corner_override_hashes[track_slug] = _corners_content_hash(corners_json)
    logger.info("Corner cache updated for %s (%d corners)", track_slug, len(corners_json))

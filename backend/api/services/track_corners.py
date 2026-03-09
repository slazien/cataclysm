"""Load track corner configs from PostgreSQL (admin-edited overrides).

Maintains an in-memory cache so the synchronous pipeline thread can look up
DB-edited corners without async DB access.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from cataclysm.track_db import OfficialCorner, TrackLayout
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import TrackCornerConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache: track_slug → list[dict] (raw JSON from DB)
# ---------------------------------------------------------------------------
_corner_overrides: dict[str, list[dict]] = {}
_cache_loaded: bool = False


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


def override_layout_corners(
    layout: TrackLayout,
    db_corners: list[OfficialCorner],
) -> TrackLayout:
    """Return a new TrackLayout with corners replaced by DB-edited ones."""
    return replace(layout, corners=db_corners)


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
    for cfg in configs:
        _corner_overrides[cfg.track_slug] = cfg.corners_json
    _cache_loaded = True
    logger.info("Loaded %d track corner override(s) from DB", len(_corner_overrides))


def update_corner_cache(track_slug: str, corners_json: list[dict]) -> None:
    """Update the in-memory cache after admin saves corners."""
    _corner_overrides[track_slug] = corners_json
    logger.info("Corner cache updated for %s (%d corners)", track_slug, len(corners_json))

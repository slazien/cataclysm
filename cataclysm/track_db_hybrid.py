"""Hybrid track lookup: DB-first with Python constants fallback."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from cataclysm.landmarks import Landmark, LandmarkType
from cataclysm.track_db import (
    OfficialCorner,
    TrackLayout,
    _normalize_name,
    get_all_tracks,
    lookup_track,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# In-memory cache populated at startup from DB
_db_tracks: dict[str, TrackLayout] = {}
_db_loaded: bool = False


def db_track_to_layout(
    db_track: Any,
    db_corners: list[Any],
    db_landmarks: list[Any],
) -> TrackLayout:
    """Convert DB models (Track, TrackCornerV2, TrackLandmark) to TrackLayout."""
    corners = [
        OfficialCorner(
            number=c.number,
            name=c.name,
            fraction=c.fraction,
            lat=c.lat,
            lon=c.lon,
            character=c.character,
            direction=c.direction,
            corner_type=c.corner_type,
            elevation_trend=c.elevation_trend,
            camber=c.camber,
            blind=c.blind or False,
            coaching_notes=c.coaching_notes,
        )
        for c in db_corners
    ]
    landmarks = [
        Landmark(
            name=lm.name,
            distance_m=lm.distance_m,
            landmark_type=(
                LandmarkType(lm.landmark_type) if lm.landmark_type else LandmarkType.structure
            ),
            description=lm.description or "",
            lat=lm.lat,
            lon=lm.lon,
        )
        for lm in db_landmarks
    ]
    return TrackLayout(
        name=db_track.name,
        corners=corners,
        landmarks=landmarks,
        center_lat=db_track.center_lat,
        center_lon=db_track.center_lon,
        country=db_track.country or "",
        length_m=db_track.length_m,
        elevation_range_m=db_track.elevation_range_m,
    )


def lookup_track_hybrid(
    track_name: str,
    db_tracks: dict[str, TrackLayout] | None = None,
) -> TrackLayout | None:
    """Check DB cache first, fall back to Python constants."""
    cache = db_tracks if db_tracks is not None else _db_tracks
    key = _normalize_name(track_name)

    # DB first
    if key in cache:
        return cache[key]

    # Fall back to Python constants
    return lookup_track(track_name)


def get_all_tracks_hybrid(
    db_tracks: dict[str, TrackLayout] | None = None,
) -> list[TrackLayout]:
    """Merge DB tracks with Python constants. DB wins on collision."""
    cache = db_tracks if db_tracks is not None else _db_tracks

    # Start with Python tracks keyed by normalized name
    result: dict[str, TrackLayout] = {}
    for layout in get_all_tracks():
        key = _normalize_name(layout.name)
        result[key] = layout

    # DB tracks override — deduplicate by keying on normalized name only
    seen_names: set[str] = set()
    for layout in cache.values():
        name_key = _normalize_name(layout.name)
        if name_key not in seen_names:
            result[name_key] = layout
            seen_names.add(name_key)

    return list(result.values())


def update_db_tracks_cache(slug: str, layout: TrackLayout) -> None:
    """Update the in-memory cache after DB changes."""
    _db_tracks[_normalize_name(slug)] = layout
    # Also key by name for lookup
    _db_tracks[_normalize_name(layout.name)] = layout
    logger.info("Hybrid cache updated for %s", slug)


def clear_db_tracks_cache() -> None:
    """Clear the DB tracks cache (for testing)."""
    global _db_loaded  # noqa: PLW0603
    _db_tracks.clear()
    _db_loaded = False


async def load_db_tracks(db: AsyncSession) -> int:
    """Load all DB tracks into the in-memory cache at startup.

    Returns the number of tracks loaded.
    """
    global _db_loaded  # noqa: PLW0603
    from sqlalchemy import select

    from backend.api.db.models import Track, TrackCornerV2, TrackLandmark

    result = await db.execute(select(Track))
    tracks = result.scalars().all()
    count = 0
    for track in tracks:
        corners_result = await db.execute(
            select(TrackCornerV2)
            .where(TrackCornerV2.track_id == track.id)
            .order_by(TrackCornerV2.number)
        )
        corners = list(corners_result.scalars().all())
        landmarks_result = await db.execute(
            select(TrackLandmark)
            .where(TrackLandmark.track_id == track.id)
            .order_by(TrackLandmark.distance_m)
        )
        landmarks = list(landmarks_result.scalars().all())
        layout = db_track_to_layout(track, corners, landmarks)
        update_db_tracks_cache(track.slug, layout)
        count += 1

    _db_loaded = True
    logger.info("Loaded %d track(s) from DB into hybrid cache", count)
    return count

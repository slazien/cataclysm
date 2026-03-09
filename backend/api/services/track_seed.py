"""Seed existing track_db.py tracks into the database.

Iterates the hardcoded TrackLayout definitions from cataclysm.track_db
and creates corresponding Track, TrackCornerV2, and TrackLandmark rows.
Idempotent — skips tracks whose slug already exists.
"""

from __future__ import annotations

import logging
import re

from cataclysm.track_db import TrackLayout, get_all_tracks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.services.track_store import (
    create_track,
    get_track_by_slug,
    upsert_corners,
    upsert_landmarks,
)

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a track name to a URL-safe slug.

    >>> _slugify("Barber Motorsports Park")
    'barber-motorsports-park'
    """
    return re.sub(r"\s+", "-", name.strip().lower())


def _layout_to_corner_dicts(layout: TrackLayout) -> list[dict[str, object]]:
    """Convert OfficialCorner list to dicts matching TrackCornerV2 columns."""
    result: list[dict[str, object]] = []
    for oc in layout.corners:
        result.append(
            {
                "number": oc.number,
                "name": oc.name,
                "fraction": oc.fraction,
                "lat": oc.lat,
                "lon": oc.lon,
                "character": oc.character,
                "direction": oc.direction,
                "corner_type": oc.corner_type,
                "elevation_trend": oc.elevation_trend,
                "camber": oc.camber,
                "blind": oc.blind,
                "coaching_notes": oc.coaching_notes,
                "auto_detected": False,
                "confidence": 1.0,
                "detection_method": "manual",
            }
        )
    return result


def _layout_to_landmark_dicts(layout: TrackLayout) -> list[dict[str, object]]:
    """Convert Landmark list to dicts matching TrackLandmark columns."""
    result: list[dict[str, object]] = []
    for lm in layout.landmarks:
        result.append(
            {
                "name": lm.name,
                "distance_m": lm.distance_m,
                "landmark_type": lm.landmark_type.value,
                "lat": lm.lat,
                "lon": lm.lon,
                "description": lm.description,
                "source": "seed",
            }
        )
    return result


async def seed_tracks_from_hardcoded(db: AsyncSession) -> int:
    """Seed existing track_db.py tracks into the database. Returns count of new tracks seeded."""
    layouts = get_all_tracks()
    seeded = 0

    for layout in layouts:
        slug = _slugify(layout.name)
        existing = await get_track_by_slug(db, slug)
        if existing is not None:
            logger.debug("Track %s already exists, skipping", slug)
            continue

        track = await create_track(
            db,
            slug=slug,
            name=layout.name,
            source="seed",
            country=layout.country or None,
            center_lat=layout.center_lat,
            center_lon=layout.center_lon,
            length_m=layout.length_m,
            elevation_range_m=layout.elevation_range_m,
            quality_tier=3,
            status="published",
        )

        corners = _layout_to_corner_dicts(layout)
        await upsert_corners(db, track.id, corners)

        landmarks = _layout_to_landmark_dicts(layout)
        await upsert_landmarks(db, track.id, landmarks)

        logger.info(
            "Seeded track %s: %d corners, %d landmarks",
            slug,
            len(corners),
            len(landmarks),
        )
        seeded += 1

    return seeded

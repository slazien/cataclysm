"""Track data store — CRUD for the v2 track pipeline tables."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import Track, TrackCornerV2, TrackLandmark

logger = logging.getLogger(__name__)


async def create_track(
    db: AsyncSession,
    *,
    slug: str,
    name: str,
    source: str,
    country: str | None = None,
    center_lat: float | None = None,
    center_lon: float | None = None,
    length_m: float | None = None,
    elevation_range_m: float | None = None,
    quality_tier: int = 1,
    status: str = "draft",
) -> Track:
    track = Track(
        slug=slug,
        name=name,
        source=source,
        country=country,
        center_lat=center_lat,
        center_lon=center_lon,
        length_m=length_m,
        elevation_range_m=elevation_range_m,
        quality_tier=quality_tier,
        status=status,
    )
    db.add(track)
    await db.commit()
    await db.refresh(track)
    return track


async def get_track_by_slug(db: AsyncSession, slug: str) -> Track | None:
    result = await db.execute(select(Track).where(Track.slug == slug))
    return result.scalar_one_or_none()


async def get_all_tracks_from_db(db: AsyncSession) -> list[Track]:
    result = await db.execute(select(Track).order_by(Track.name))
    return list(result.scalars().all())


async def update_track(db: AsyncSession, slug: str, **kwargs: Any) -> Track | None:
    track = await get_track_by_slug(db, slug)
    if track is None:
        return None
    for key, value in kwargs.items():
        setattr(track, key, value)
    await db.commit()
    await db.refresh(track)
    return track


async def upsert_corners(db: AsyncSession, track_id: int, corners: list[dict[str, Any]]) -> None:
    await db.execute(delete(TrackCornerV2).where(TrackCornerV2.track_id == track_id))
    for c in corners:
        db.add(TrackCornerV2(track_id=track_id, **c))
    await db.commit()


async def get_corners_for_track(db: AsyncSession, track_id: int) -> list[TrackCornerV2]:
    result = await db.execute(
        select(TrackCornerV2)
        .where(TrackCornerV2.track_id == track_id)
        .order_by(TrackCornerV2.number)
    )
    return list(result.scalars().all())


async def upsert_landmarks(
    db: AsyncSession, track_id: int, landmarks: list[dict[str, Any]]
) -> None:
    await db.execute(delete(TrackLandmark).where(TrackLandmark.track_id == track_id))
    for lm in landmarks:
        db.add(TrackLandmark(track_id=track_id, **lm))
    await db.commit()


async def get_landmarks_for_track(db: AsyncSession, track_id: int) -> list[TrackLandmark]:
    result = await db.execute(
        select(TrackLandmark)
        .where(TrackLandmark.track_id == track_id)
        .order_by(TrackLandmark.distance_m)
    )
    return list(result.scalars().all())

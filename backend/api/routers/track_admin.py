"""Track admin CRUD REST API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.db.models import Track
from backend.api.dependencies import AuthenticatedUser, get_user_or_anon
from backend.api.routers.admin import require_admin
from backend.api.services.track_corners import update_corner_cache
from backend.api.services.track_store import (
    create_track,
    get_all_tracks_from_db,
    get_corners_for_track,
    get_landmarks_for_track,
    get_track_by_slug,
    update_track,
    upsert_corners,
    upsert_landmarks,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TrackCreate(BaseModel):
    """Request body for creating a track."""

    slug: str
    name: str
    source: str
    country: str | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    length_m: float | None = None
    elevation_range_m: float | None = None
    quality_tier: int = 1
    status: str = "draft"


class TrackUpdate(BaseModel):
    """Request body for updating a track (all fields optional)."""

    name: str | None = None
    country: str | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    length_m: float | None = None
    elevation_range_m: float | None = None
    quality_tier: int | None = None
    status: str | None = None
    source: str | None = None
    direction_of_travel: str | None = None
    track_type: str | None = None
    aliases: list[str] | None = None
    centerline_geojson: dict[str, Any] | None = None


class CornerInput(BaseModel):
    """A single corner in a PUT corners request."""

    number: int
    name: str | None = None
    fraction: float
    lat: float | None = None
    lon: float | None = None
    character: str | None = None
    direction: str | None = None
    corner_type: str | None = None
    elevation_trend: str | None = None
    camber: str | None = None
    blind: bool | None = None
    coaching_notes: str | None = None
    auto_detected: bool | None = None
    confidence: float | None = None
    detection_method: str | None = None


class LandmarkInput(BaseModel):
    """A single landmark in a PUT landmarks request."""

    name: str
    distance_m: float | None = None
    landmark_type: str | None = None
    lat: float | None = None
    lon: float | None = None
    description: str | None = None
    source: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _track_to_dict(track: Track) -> dict[str, Any]:
    """Serialize a Track ORM model to a JSON-safe dict."""
    return {
        "id": track.id,
        "slug": track.slug,
        "name": track.name,
        "aliases": track.aliases,
        "country": track.country,
        "center_lat": track.center_lat,
        "center_lon": track.center_lon,
        "length_m": track.length_m,
        "elevation_range_m": track.elevation_range_m,
        "quality_tier": track.quality_tier,
        "status": track.status,
        "source": track.source,
        "direction_of_travel": track.direction_of_travel,
        "track_type": track.track_type,
        "created_at": track.created_at.isoformat() if track.created_at else None,
        "updated_at": track.updated_at.isoformat() if track.updated_at else None,
        "verified_by": track.verified_by,
        "verified_at": (track.verified_at.isoformat() if track.verified_at else None),
    }


async def _get_track_or_404(db: AsyncSession, slug: str) -> Track:
    """Return track by slug or raise 404."""
    track = await get_track_by_slug(db, slug)
    if track is None:
        raise HTTPException(status_code=404, detail=f"Track '{slug}' not found")
    return track


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def list_tracks(
    _user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List all tracks."""
    tracks = await get_all_tracks_from_db(db)
    return [_track_to_dict(t) for t in tracks]


@router.post("/", status_code=201)
async def create_track_endpoint(
    body: TrackCreate,
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Create a new track."""
    try:
        track = await create_track(
            db,
            slug=body.slug,
            name=body.name,
            source=body.source,
            country=body.country,
            center_lat=body.center_lat,
            center_lon=body.center_lon,
            length_m=body.length_m,
            elevation_range_m=body.elevation_range_m,
            quality_tier=body.quality_tier,
            status=body.status,
        )
        return _track_to_dict(track)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"Track with slug '{body.slug}' already exists",
        ) from None


@router.get("/{slug}")
async def get_track(
    slug: str,
    _user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get a single track by slug."""
    track = await _get_track_or_404(db, slug)
    return _track_to_dict(track)


@router.patch("/{slug}")
async def update_track_endpoint(
    slug: str,
    body: TrackUpdate,
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Update track fields."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        # No fields to update — just return the current track
        track = await _get_track_or_404(db, slug)
        return _track_to_dict(track)

    updated = await update_track(db, slug, **updates)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Track '{slug}' not found")
    return _track_to_dict(updated)


@router.put("/{slug}/corners")
async def set_corners(
    slug: str,
    body: list[CornerInput],
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Replace all corners for a track."""
    track = await _get_track_or_404(db, slug)
    corner_dicts = [c.model_dump(exclude_unset=False) for c in body]
    await upsert_corners(db, track.id, corner_dicts)

    # Update the in-memory corner cache for the pipeline
    update_corner_cache(slug, corner_dicts)

    return {"track_slug": slug, "corners_count": len(body)}


@router.get("/{slug}/corners")
async def get_corners(
    slug: str,
    _user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List corners for a track."""
    track = await _get_track_or_404(db, slug)
    corners = await get_corners_for_track(db, track.id)
    return [
        {
            "id": c.id,
            "number": c.number,
            "name": c.name,
            "fraction": c.fraction,
            "lat": c.lat,
            "lon": c.lon,
            "character": c.character,
            "direction": c.direction,
            "corner_type": c.corner_type,
            "elevation_trend": c.elevation_trend,
            "camber": c.camber,
            "blind": c.blind,
            "coaching_notes": c.coaching_notes,
            "auto_detected": c.auto_detected,
            "confidence": c.confidence,
            "detection_method": c.detection_method,
        }
        for c in corners
    ]


@router.put("/{slug}/landmarks")
async def set_landmarks(
    slug: str,
    body: list[LandmarkInput],
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Replace all landmarks for a track."""
    track = await _get_track_or_404(db, slug)
    lm_dicts = [lm.model_dump(exclude_unset=False) for lm in body]
    await upsert_landmarks(db, track.id, lm_dicts)
    return {"track_slug": slug, "landmarks_count": len(body)}


@router.get("/{slug}/landmarks")
async def get_landmarks(
    slug: str,
    _user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List landmarks for a track."""
    track = await _get_track_or_404(db, slug)
    landmarks = await get_landmarks_for_track(db, track.id)
    return [
        {
            "id": lm.id,
            "name": lm.name,
            "distance_m": lm.distance_m,
            "landmark_type": lm.landmark_type,
            "lat": lm.lat,
            "lon": lm.lon,
            "description": lm.description,
            "source": lm.source,
        }
        for lm in landmarks
    ]

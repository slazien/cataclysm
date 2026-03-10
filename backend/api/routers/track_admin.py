"""Track admin CRUD REST API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated, Any

import numpy as np
from cataclysm.osm_import import osm_to_track_seed, query_overpass_raceway
from cataclysm.track_db import OfficialCorner
from cataclysm.track_db_hybrid import db_track_to_layout, update_db_tracks_cache
from cataclysm.track_validation import validate_track
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.db.models import Track, TrackElevationProfile
from backend.api.dependencies import AuthenticatedUser, get_user_or_anon
from backend.api.routers.admin import require_admin
from backend.api.services.track_corners import update_corner_cache
from backend.api.services.track_enrichment import enrich_track
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


class ValidationIssueResponse(BaseModel):
    """A single validation issue."""

    severity: str
    message: str


class ValidationResponse(BaseModel):
    """Result of track data validation."""

    is_valid: bool
    issues: list[ValidationIssueResponse]
    quality_score: float


class OsmImportRequest(BaseModel):
    """Request body for importing tracks from OSM Overpass."""

    lat: float
    lon: float
    radius_m: float = Field(default=5000.0, gt=0, le=50000)


class GeoJsonImportRequest(BaseModel):
    """Request body for importing a track from GeoJSON."""

    name: str
    slug: str
    geojson: dict[str, Any]


class ImportResult(BaseModel):
    """Result of a track import operation."""

    tracks_created: list[str]
    enrichment_results: list[dict[str, Any]]


class EnrichmentResult(BaseModel):
    """Result of a track enrichment run."""

    corners_detected: int
    elevation_source: str | None
    brake_markers: int
    steps_logged: int


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


async def _refresh_hybrid_cache(db: AsyncSession, track: Track) -> None:
    """Rebuild the hybrid cache entry for a track after mutations."""
    corners = await get_corners_for_track(db, track.id)
    landmarks = await get_landmarks_for_track(db, track.id)
    layout = db_track_to_layout(track, corners, landmarks)
    update_db_tracks_cache(track.slug, layout)


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
        await _refresh_hybrid_cache(db, track)
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
    await _refresh_hybrid_cache(db, updated)
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

    # Update both caches: legacy corner override + hybrid track cache
    update_corner_cache(slug, corner_dicts)
    await _refresh_hybrid_cache(db, track)

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
    await _refresh_hybrid_cache(db, track)
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


@router.post("/{slug}/validate", response_model=ValidationResponse)
async def validate_track_endpoint(
    slug: str,
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ValidationResponse:
    """Run validation gates on a track's corners and elevation data."""
    track = await _get_track_or_404(db, slug)

    # Get corners from DB and convert to OfficialCorner dataclasses
    db_corners = await get_corners_for_track(db, track.id)
    corners = [
        OfficialCorner(
            number=c.number,
            name=c.name or f"T{c.number}",
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

    # Get elevation profile if available (prefer highest-accuracy source)
    result = await db.execute(
        select(TrackElevationProfile)
        .where(TrackElevationProfile.track_id == track.id)
        .order_by(TrackElevationProfile.accuracy_m.asc().nullslast())
        .limit(1)
    )
    elevation = result.scalar_one_or_none()

    elevation_distances: list[float] | None = None
    elevation_values: list[float] | None = None
    if elevation is not None:
        elevation_distances = elevation.distances_m
        elevation_values = elevation.elevations_m

    # Run validation
    vr = validate_track(
        corners,
        length_m=track.length_m,
        elevation_distances=elevation_distances,
        elevation_values=elevation_values,
    )

    return ValidationResponse(
        is_valid=vr.is_valid,
        issues=[ValidationIssueResponse(severity=i.severity, message=i.message) for i in vr.issues],
        quality_score=vr.quality_score,
    )


# ---------------------------------------------------------------------------
# Import endpoints
# ---------------------------------------------------------------------------


def _extract_geojson_coordinates(geojson: dict[str, Any]) -> list[list[float]]:
    """Extract coordinate pairs from GeoJSON geometry.

    Supports top-level Geometry objects (LineString, Polygon) and
    Feature/FeatureCollection wrappers.  Returns list of [lon, lat] pairs.
    Raises HTTPException(422) on unsupported or empty geometries.
    """
    geometry = geojson

    # Unwrap FeatureCollection → first Feature
    if geometry.get("type") == "FeatureCollection":
        features = geometry.get("features", [])
        if not features:
            raise HTTPException(status_code=422, detail="FeatureCollection has no features")
        geometry = features[0].get("geometry", {})

    # Unwrap Feature → geometry
    if geometry.get("type") == "Feature":
        geometry = geometry.get("geometry", {})

    geom_type = geometry.get("type", "")
    coords = geometry.get("coordinates", [])

    if geom_type == "LineString":
        if len(coords) < 3:
            raise HTTPException(
                status_code=422,
                detail="LineString must have at least 3 coordinate pairs",
            )
        return coords  # type: ignore[no-any-return]

    if geom_type == "Polygon":
        # Use the exterior ring (first ring)
        if not coords or len(coords[0]) < 3:
            raise HTTPException(
                status_code=422,
                detail="Polygon exterior ring must have at least 3 coordinate pairs",
            )
        return coords[0]  # type: ignore[no-any-return]

    raise HTTPException(
        status_code=422,
        detail=f"Unsupported GeoJSON geometry type: '{geom_type}'. Expected LineString or Polygon.",
    )


@router.post("/import/osm", response_model=ImportResult, status_code=201)
async def import_from_osm(
    body: OsmImportRequest,
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportResult:
    """Import raceways from OSM Overpass near a lat/lon coordinate."""
    results = await query_overpass_raceway(body.lat, body.lon, radius_m=int(body.radius_m))
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No raceways found within {body.radius_m}m of ({body.lat}, {body.lon})",
        )

    tracks_created: list[str] = []
    enrichment_results: list[dict[str, Any]] = []

    for osm_result in results:
        seed = osm_to_track_seed(osm_result)
        try:
            track = await create_track(
                db,
                slug=seed["slug"],
                name=seed["name"],
                source=seed["source"],
                center_lat=seed.get("center_lat"),
                center_lon=seed.get("center_lon"),
                length_m=seed.get("length_m"),
            )
        except IntegrityError:
            # Track with this slug already exists — skip
            await db.rollback()
            logger.info("Skipping OSM import: slug '%s' already exists", seed["slug"])
            continue

        # Run enrichment on the OSM centerline
        lats = np.array(osm_result.lats)
        lons = np.array(osm_result.lons)
        enrich_result = await enrich_track(
            db, track.id, lats, lons, track_length_m=osm_result.length_m
        )
        await _refresh_hybrid_cache(db, track)

        tracks_created.append(seed["slug"])
        enrichment_results.append(enrich_result)

    return ImportResult(tracks_created=tracks_created, enrichment_results=enrichment_results)


@router.post("/import/geojson", response_model=ImportResult, status_code=201)
async def import_from_geojson(
    body: GeoJsonImportRequest,
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportResult:
    """Import a track from a GeoJSON geometry (LineString or Polygon ring)."""
    coords = _extract_geojson_coordinates(body.geojson)

    # GeoJSON coordinates are [lon, lat] — extract to arrays
    lons = np.array([c[0] for c in coords])
    lats = np.array([c[1] for c in coords])

    center_lat = float(np.mean(lats))
    center_lon = float(np.mean(lons))

    # Compute approximate length from coordinate deltas
    dlat = np.diff(lats) * 111320.0
    dlon = np.diff(lons) * 111320.0 * np.cos(np.radians(np.mean(lats)))
    length_m = float(np.sum(np.sqrt(dlat**2 + dlon**2)))

    try:
        track = await create_track(
            db,
            slug=body.slug,
            name=body.name,
            source="geojson",
            center_lat=center_lat,
            center_lon=center_lon,
            length_m=length_m,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"Track with slug '{body.slug}' already exists",
        ) from None

    # Store the raw GeoJSON on the track record
    track.centerline_geojson = body.geojson
    await db.flush()

    enrich_result = await enrich_track(db, track.id, lats, lons, track_length_m=length_m)
    await _refresh_hybrid_cache(db, track)

    return ImportResult(
        tracks_created=[body.slug],
        enrichment_results=[enrich_result],
    )


# ---------------------------------------------------------------------------
# Enrichment trigger
# ---------------------------------------------------------------------------


@router.post("/{slug}/enrich", response_model=EnrichmentResult)
async def trigger_enrichment(
    slug: str,
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnrichmentResult:
    """Re-run the enrichment pipeline on an existing track.

    Extracts the centerline from corners (lat/lon) or the stored
    centerline_geojson.  Returns 422 if no centerline data is available.
    """
    track = await _get_track_or_404(db, slug)

    lats: np.ndarray | None = None
    lons: np.ndarray | None = None

    # Strategy 1: Stored centerline GeoJSON
    if track.centerline_geojson is not None:
        try:
            coords = _extract_geojson_coordinates(track.centerline_geojson)
            lons = np.array([c[0] for c in coords])
            lats = np.array([c[1] for c in coords])
        except HTTPException:
            pass  # Fall through to other strategies

    # Strategy 2: Corners with lat/lon
    if lats is None:
        corners = await get_corners_for_track(db, track.id)
        corner_coords = [(c.lat, c.lon) for c in corners if c.lat is not None and c.lon is not None]
        if len(corner_coords) >= 3:
            lats = np.array([c[0] for c in corner_coords])
            lons = np.array([c[1] for c in corner_coords])

    if lats is None or lons is None:
        raise HTTPException(
            status_code=422,
            detail=f"Track '{slug}' has no centerline data. "
            "Upload GeoJSON or add corners with lat/lon coordinates first.",
        )

    enrich_result = await enrich_track(db, track.id, lats, lons, track_length_m=track.length_m)
    await _refresh_hybrid_cache(db, track)

    return EnrichmentResult(
        corners_detected=enrich_result["corners_detected"],
        elevation_source=enrich_result.get("elevation_source"),
        brake_markers=enrich_result["brake_markers"],
        steps_logged=enrich_result["steps_logged"],
    )

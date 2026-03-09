"""Admin endpoints for track editor (corner placement)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.db.models import TrackCornerConfig
from backend.api.dependencies import AuthenticatedUser, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

ADMIN_EMAIL = "p.zientala.1995@gmail.com"

# Where canonical track references (NPZ) are stored on disk.
_TRACK_REF_DIR = Path(
    os.environ.get(
        "TRACK_REF_DIR",
        str(Path(__file__).resolve().parent.parent.parent.parent / "data" / "track_reference"),
    )
)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def require_admin(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    """Require the authenticated user to be the admin."""
    if user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class CornerInput(BaseModel):
    """A single corner definition submitted by the admin."""

    number: int
    name: str
    fraction: float
    direction: str
    corner_type: str
    elevation_trend: str | None = None
    camber: str | None = None
    coaching_note: str | None = None

    @field_validator("fraction")
    @classmethod
    def fraction_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            msg = "fraction must be between 0.0 and 1.0"
            raise ValueError(msg)
        return v


class CornersPayload(BaseModel):
    """PUT body for saving corners."""

    corners: list[CornerInput]


class EditorResponse(BaseModel):
    """Track editor data returned to the frontend."""

    track_slug: str
    track_length_m: float
    geometry: dict
    corners: list[dict]


class SaveResult(BaseModel):
    """Response after saving corners."""

    saved: bool
    corner_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/tracks")
async def list_tracks(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
) -> dict:
    """List all known track slugs (from track_db.py)."""
    from cataclysm.track_db import get_all_tracks
    from cataclysm.track_reference import track_slug_from_layout

    layouts = get_all_tracks()
    slugs = sorted({track_slug_from_layout(lay) for lay in layouts})
    return {"tracks": slugs}


@router.get("/tracks/{slug}/editor")
async def get_track_editor(
    slug: str,
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EditorResponse:
    """Return track geometry + corners for the editor UI."""
    from cataclysm.track_db import get_all_tracks
    from cataclysm.track_reference import track_slug_from_layout

    # Find the matching TrackLayout
    layout = None
    for lay in get_all_tracks():
        if track_slug_from_layout(lay) == slug:
            layout = lay
            break
    if layout is None:
        raise HTTPException(status_code=404, detail=f"Track '{slug}' not found")

    # Load NPZ geometry
    npz_path = _TRACK_REF_DIR / f"{slug}.npz"
    if not npz_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No track reference file for '{slug}'",
        )

    # allow_pickle=False is the secure default — npz contains only arrays
    data = np.load(str(npz_path), allow_pickle=False)
    meta = json.loads(str(data["metadata"]))
    track_length_m = float(meta["track_length_m"])

    x_smooth = data["x_smooth"]
    y_smooth = data["y_smooth"]
    curvature = data["curvature"]

    # Downsample to ~1000 points
    step = max(1, len(x_smooth) // 1000)
    geometry = {
        "x": x_smooth[::step].tolist(),
        "y": y_smooth[::step].tolist(),
        "curvature": curvature[::step].tolist(),
    }

    # Load corners: DB first, then fallback to track_db.py
    result = await db.execute(select(TrackCornerConfig).where(TrackCornerConfig.track_slug == slug))
    db_config = result.scalar_one_or_none()

    corners: list[dict]
    if db_config is not None:
        corners = db_config.corners_json  # type: ignore[assignment]
    else:
        corners = [
            {
                "number": c.number,
                "name": c.name,
                "fraction": c.fraction,
                "direction": c.direction,
                "corner_type": c.corner_type,
                "elevation_trend": c.elevation_trend,
                "camber": c.camber,
                "coaching_note": c.coaching_notes,
                "lat": c.lat,
                "lon": c.lon,
            }
            for c in layout.corners
        ]

    return EditorResponse(
        track_slug=slug,
        track_length_m=track_length_m,
        geometry=geometry,
        corners=corners,
    )


@router.put("/tracks/{slug}/corners")
async def save_corners(
    slug: str,
    payload: CornersPayload,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SaveResult:
    """Save admin-edited corners for a track."""
    from cataclysm.track_db import get_all_tracks
    from cataclysm.track_reference import track_slug_from_layout

    # Verify track exists
    found = any(track_slug_from_layout(lay) == slug for lay in get_all_tracks())
    if not found:
        raise HTTPException(status_code=404, detail=f"Track '{slug}' not found")

    # Validate: fractions sorted ascending, no duplicates
    fractions = [c.fraction for c in payload.corners]
    if fractions != sorted(fractions):
        raise HTTPException(status_code=422, detail="Corner fractions must be sorted ascending")
    if len(set(fractions)) != len(fractions):
        raise HTTPException(status_code=422, detail="Corner fractions must be unique")

    corners_data = [c.model_dump() for c in payload.corners]

    # Upsert
    result = await db.execute(select(TrackCornerConfig).where(TrackCornerConfig.track_slug == slug))
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.corners_json = corners_data  # type: ignore[assignment]
        existing.updated_by = user.email
    else:
        db.add(
            TrackCornerConfig(
                track_slug=slug,
                corners_json=corners_data,  # type: ignore[arg-type]
                updated_by=user.email,
            )
        )

    await db.commit()

    return SaveResult(saved=True, corner_count=len(payload.corners))

"""Admin endpoints for track editor (corner placement)."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Annotated, Any, Literal

import numpy as np
from cataclysm.llm_gateway import get_routing_status, set_routing_enabled_override
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.config import Settings
from backend.api.db.database import get_db
from backend.api.db.models import LlmTaskRoute, TrackCornerConfig
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.services.llm_usage_store import (
    get_llm_usage_dashboard_db,
    get_llm_usage_summary_db,
    get_recent_llm_usage_events_db,
)
from backend.api.services.runtime_settings import (
    LLM_ROUTING_SETTING_KEY,
    get_runtime_setting,
    get_runtime_setting_bool,
    set_runtime_setting_bool,
    sync_task_routes_once,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_SETTINGS = Settings()

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
    allowlist = {
        email.strip().lower() for email in _SETTINGS.admin_allowlist_emails if email.strip()
    }
    if user.email.strip().lower() not in allowlist:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


_SLUG_RE = re.compile(r"[a-z0-9-]+")


def _validate_slug(slug: str) -> str:
    """Reject slugs that aren't simple lowercase-alphanum-dash."""
    if not _SLUG_RE.fullmatch(slug):
        raise HTTPException(status_code=400, detail="Invalid track slug")
    return slug


class CornerInput(BaseModel):
    """A single corner definition submitted by the admin."""

    number: int
    name: str
    fraction: float
    direction: Literal["left", "right"]
    corner_type: Literal["sweeper", "hairpin", "kink", "esses", "chicane", "carousel", "complex"]
    elevation_trend: Literal["flat", "uphill", "downhill", "crest", "compression"] | None = None
    camber: Literal["flat", "positive", "negative", "off-camber"] | None = None
    coaching_notes: str | None = None
    lat: float | None = None
    lon: float | None = None
    character: Literal["flat", "lift", "brake"] | None = None

    @field_validator("number")
    @classmethod
    def number_positive(cls, v: int) -> int:
        if v < 1:
            msg = "number must be >= 1"
            raise ValueError(msg)
        return v

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
    geometry: dict[str, Any]
    corners: list[dict[str, Any]]


class SaveResult(BaseModel):
    """Response after saving corners."""

    saved: bool
    corner_count: int


class LLMRoutingTogglePayload(BaseModel):
    """PUT body for enabling/disabling global LLM routing."""

    enabled: bool


KNOWN_TASKS = [
    "coaching_report",
    "coaching_chat",
    "topic_classifier",
    "coaching_validator",
    "track_draft",
    "share_comparison",
]

MODEL_REGISTRY = [
    {
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "display": "Haiku 4.5",
        "cost_in": 1.0,
        "cost_out": 5.0,
    },
    {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "display": "Sonnet 4.6",
        "cost_in": 3.0,
        "cost_out": 15.0,
    },
    {
        "provider": "openai",
        "model": "gpt-5-nano",
        "display": "GPT-5 Nano",
        "cost_in": 0.05,
        "cost_out": 0.4,
    },
    {
        "provider": "openai",
        "model": "gpt-5-mini",
        "display": "GPT-5 Mini",
        "cost_in": 0.25,
        "cost_out": 2.0,
    },
    {
        "provider": "google",
        "model": "gemini-2.5-flash-lite",
        "display": "Flash Lite",
        "cost_in": 0.10,
        "cost_out": 0.40,
    },
    {
        "provider": "google",
        "model": "gemini-2.5-flash",
        "display": "Flash 2.5",
        "cost_in": 0.30,
        "cost_out": 2.50,
    },
]


class ChainEntry(BaseModel):
    """Single provider/model pair in a routing chain."""

    provider: Literal["anthropic", "openai", "google"]
    model: str


class TaskRoutePayload(BaseModel):
    """PUT body for per-task LLM routing configuration."""

    chain: list[ChainEntry]

    @field_validator("chain")
    @classmethod
    def chain_non_empty(cls, v: list[ChainEntry]) -> list[ChainEntry]:
        if not v:
            msg = "chain must have at least one entry"
            raise ValueError(msg)
        return v


@router.get("/me")
async def admin_me(
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
) -> dict[str, str]:
    """Return current admin identity for frontend access checks."""
    return {"email": user.email, "name": user.name}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/tracks")
async def list_tracks(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
) -> dict:
    """List all known track slugs (from DB + constants)."""
    from cataclysm.track_db_hybrid import get_all_tracks_hybrid
    from cataclysm.track_reference import track_slug_from_layout

    layouts = get_all_tracks_hybrid()
    slugs = sorted({track_slug_from_layout(lay) for lay in layouts})
    return {"tracks": slugs}


@router.get("/tracks/{slug}/editor")
async def get_track_editor(
    slug: str,
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EditorResponse:
    """Return track geometry + corners for the editor UI."""
    _validate_slug(slug)
    from cataclysm.track_db_hybrid import get_all_tracks_hybrid
    from cataclysm.track_reference import track_slug_from_layout

    # Find the matching TrackLayout
    layout = None
    for lay in get_all_tracks_hybrid():
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
        corners = db_config.corners_json
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
                "coaching_notes": c.coaching_notes,
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
    _validate_slug(slug)
    from cataclysm.track_db_hybrid import get_all_tracks_hybrid
    from cataclysm.track_reference import track_slug_from_layout

    # Verify track exists
    found = any(track_slug_from_layout(lay) == slug for lay in get_all_tracks_hybrid())
    if not found:
        raise HTTPException(status_code=404, detail=f"Track '{slug}' not found")

    # Validate: fractions sorted ascending, no duplicates
    fractions = [c.fraction for c in payload.corners]
    if fractions != sorted(fractions):
        raise HTTPException(status_code=422, detail="Corner fractions must be sorted ascending")
    if len(set(fractions)) != len(fractions):
        raise HTTPException(status_code=422, detail="Corner fractions must be unique")

    corners_data = [c.model_dump() for c in payload.corners]

    # Legacy: upsert TrackCornerConfig (kept for backward compat during migration)
    result = await db.execute(select(TrackCornerConfig).where(TrackCornerConfig.track_slug == slug))
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.corners_json = corners_data
        existing.updated_by = user.email
    else:
        db.add(
            TrackCornerConfig(
                track_slug=slug,
                corners_json=corners_data,
                updated_by=user.email,
            )
        )

    # New: also write to TrackCornerV2 + refresh hybrid cache (single source of truth)
    from cataclysm.track_db_hybrid import db_track_to_layout, update_db_tracks_cache

    from backend.api.services.track_store import (
        get_corners_for_track,
        get_landmarks_for_track,
        get_track_by_slug,
        upsert_corners,
    )

    track = await get_track_by_slug(db, slug)
    if track is not None:
        await upsert_corners(db, track.id, corners_data)
        await db.commit()
        corners_rows = await get_corners_for_track(db, track.id)
        landmarks_rows = await get_landmarks_for_track(db, track.id)
        layout = db_track_to_layout(track, corners_rows, landmarks_rows)
        update_db_tracks_cache(track.slug, layout)
    else:
        await db.commit()

    # Update corner version hash for staleness detection
    from backend.api.services.track_corners import update_corner_cache

    update_corner_cache(slug, corners_data)

    return SaveResult(saved=True, corner_count=len(payload.corners))


@router.get("/llm-usage/summary")
async def llm_usage_summary(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 30,
) -> dict[str, Any]:
    """Return aggregate persisted LLM usage telemetry."""
    return await get_llm_usage_summary_db(db, days=max(0, days))


@router.get("/llm-usage/events")
async def llm_usage_events(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
) -> dict[str, list[dict[str, Any]]]:
    """Return recent persisted LLM usage telemetry events (newest-first)."""
    events = await get_recent_llm_usage_events_db(db, limit=limit)
    return {"events": events}


@router.get("/llm-usage/dashboard")
async def llm_usage_dashboard(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 30,
) -> dict[str, Any]:
    """Return dashboard-focused cost and model usage aggregates."""
    return await get_llm_usage_dashboard_db(db, days=max(0, days))


@router.get("/llm-routing/status")
async def llm_routing_status(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Return global LLM routing status."""
    env_default = bool(_SETTINGS.llm_routing_enabled)
    status = get_routing_status(default=env_default)
    row = await get_runtime_setting(db, LLM_ROUTING_SETTING_KEY)
    if row is not None:
        status["updated_at"] = row.updated_at.isoformat()
        status["updated_by"] = row.updated_by
    else:
        status["updated_by"] = None
    return status


@router.put("/llm-routing/status")
async def update_llm_routing_status(
    payload: LLMRoutingTogglePayload,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Persist and apply a global LLM routing toggle."""
    await set_runtime_setting_bool(
        db,
        LLM_ROUTING_SETTING_KEY,
        payload.enabled,
        updated_by=user.email,
    )
    await db.commit()

    set_routing_enabled_override(payload.enabled, source="db")
    os.environ["LLM_ROUTING_ENABLED"] = "1" if payload.enabled else "0"

    env_default = bool(_SETTINGS.llm_routing_enabled)
    status = get_routing_status(default=env_default)
    current_enabled = await get_runtime_setting_bool(
        db,
        LLM_ROUTING_SETTING_KEY,
        default=env_default,
    )
    status["enabled"] = current_enabled
    row = await get_runtime_setting(db, LLM_ROUTING_SETTING_KEY)
    status["updated_at"] = row.updated_at.isoformat() if row is not None else None
    status["updated_by"] = row.updated_by if row is not None else None
    return status


# ---------------------------------------------------------------------------
# Per-task LLM routing CRUD
# ---------------------------------------------------------------------------


@router.get("/llm-routing/models")
async def list_available_models(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
) -> dict[str, Any]:
    """Return known models, tasks, and which providers have API keys configured."""
    available_providers: list[str] = []
    key_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    for provider, env_var in key_vars.items():
        if os.environ.get(env_var):
            available_providers.append(provider)
    return {
        "models": MODEL_REGISTRY,
        "tasks": KNOWN_TASKS,
        "available_providers": available_providers,
    }


@router.get("/llm-routing/tasks")
async def list_task_routes(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Return all per-task routing configurations."""
    result = await db.execute(select(LlmTaskRoute))
    rows = result.scalars().all()
    configs: dict[str, Any] = {}
    for row in rows:
        try:
            configs[row.task] = json.loads(row.config_json)
        except json.JSONDecodeError:
            configs[row.task] = {"chain": []}
    return {"task_routes": configs, "tasks": KNOWN_TASKS}


@router.put("/llm-routing/tasks/{task}")
async def upsert_task_route(
    task: str,
    payload: TaskRoutePayload,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Create or update routing config for a specific task."""
    if task not in KNOWN_TASKS:
        raise HTTPException(400, f"Unknown task: {task}")

    chain_dicts = [{"provider": e.provider, "model": e.model} for e in payload.chain]
    config_json = json.dumps({"chain": chain_dicts})
    row = await db.get(LlmTaskRoute, task)
    if row is None:
        row = LlmTaskRoute(task=task, config_json=config_json, updated_by=user.email)
        db.add(row)
    else:
        row.config_json = config_json
        row.updated_by = user.email
    await db.commit()

    # Immediately apply to gateway cache
    await sync_task_routes_once()
    return {"task": task, "config": {"chain": chain_dicts}}


@router.delete("/llm-routing/tasks/{task}")
async def delete_task_route(
    task: str,
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Remove per-task routing config (revert to caller defaults)."""
    if task not in KNOWN_TASKS:
        raise HTTPException(400, f"Unknown task: {task}")
    row = await db.get(LlmTaskRoute, task)
    if row is not None:
        await db.delete(row)
        await db.commit()
    await sync_task_routes_once()
    return {"status": "deleted", "task": task}


# ---------------------------------------------------------------------------
# Weather re-backfill
# ---------------------------------------------------------------------------


@router.post("/weather/rebackfill")
async def trigger_weather_rebackfill(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
) -> dict[str, int]:
    """Re-run the surface water model for all sessions.

    Skips sessions where the user has manually tagged the condition.
    Returns stats: {updated, skipped_manual, skipped_no_coords, failed, total}.
    """
    from backend.api.services.weather_backfill import rebackfill_all_sessions

    return await rebackfill_all_sessions()

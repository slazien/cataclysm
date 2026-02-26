"""Session management endpoints: upload, list, get, delete."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.config import Settings
from backend.api.db.database import get_db
from backend.api.db.models import SessionFile as SessionFileModel
from backend.api.dependencies import AuthenticatedUser, get_current_user, get_settings
from backend.api.routers.coaching import trigger_auto_coaching
from backend.api.schemas.comparison import ComparisonResult
from backend.api.schemas.session import (
    LapData,
    LapSummary,
    SessionList,
    SessionSummary,
    UploadResponse,
)
from backend.api.services import equipment_store, session_store
from backend.api.services.coaching_store import clear_coaching_data
from backend.api.services.comparison import compare_sessions as run_comparison
from backend.api.services.db_session_store import (
    delete_session_db,
    ensure_user_exists,
    list_sessions_for_user,
    store_session_db,
)
from backend.api.services.pipeline import process_upload

logger = logging.getLogger(__name__)

router = APIRouter()

MPS_TO_MPH = 2.23694


def _equipment_fields(session_id: str) -> dict[str, str | None]:
    """Look up equipment for a session and return fields for SessionSummary."""
    tire_model: str | None = None
    compound_category: str | None = None
    profile_name: str | None = None
    se = equipment_store.get_session_equipment(session_id)
    if se is not None:
        profile = equipment_store.get_profile(se.profile_id)
        if profile is not None:
            tire_model = profile.tires.model
            compound_category = profile.tires.compound_category.value
            profile_name = profile.name
    return {
        "tire_model": tire_model,
        "compound_category": compound_category,
        "equipment_profile_name": profile_name,
    }


@router.post("/upload", response_model=UploadResponse)
async def upload_sessions(
    files: list[UploadFile],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadResponse:
    """Upload one or more RaceChrono CSV files and create sessions."""
    await ensure_user_exists(db, current_user)

    session_ids: list[str] = []
    errors: list[str] = []

    for f in files:
        if not f.filename:
            errors.append("File with no name skipped")
            continue
        try:
            file_bytes = await f.read()
            result = await process_upload(file_bytes, f.filename)
            sid = str(result["session_id"])
            session_ids.append(sid)

            # Persist session metadata to DB for user scoping
            sd = session_store.get_session(sid)
            if sd is not None:
                await store_session_db(db, current_user.user_id, sd)

                # Persist raw CSV bytes so sessions survive redeployments
                await db.merge(
                    SessionFileModel(
                        session_id=sid,
                        filename=f.filename or "",
                        csv_bytes=file_bytes,
                    )
                )
                await db.commit()

                # Auto-generate coaching report in the background
                await trigger_auto_coaching(sid, sd)
        except Exception as exc:
            logger.warning("Failed to process %s: %s", f.filename, exc, exc_info=True)
            errors.append(f"{f.filename}: {exc}")

    msg = f"Processed {len(session_ids)} file(s)"
    if errors:
        msg += f"; {len(errors)} error(s): {'; '.join(errors)}"

    return UploadResponse(session_ids=session_ids, message=msg)


@router.get("", response_model=SessionList)
async def list_sessions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionList:
    """List user's sessions ordered by date descending.

    Uses DB metadata for the list; enriches from in-memory store if available.
    """
    db_rows = await list_sessions_for_user(db, current_user.user_id)
    items: list[SessionSummary] = []
    for row in db_rows:
        # Try in-memory store for richer data (e.g. after upload)
        sd = session_store.get_session(row.session_id)
        if sd is not None:
            items.append(
                SessionSummary(
                    session_id=sd.session_id,
                    track_name=sd.snapshot.metadata.track_name,
                    session_date=sd.snapshot.metadata.session_date,
                    n_laps=sd.snapshot.n_laps,
                    n_clean_laps=sd.snapshot.n_clean_laps,
                    best_lap_time_s=sd.snapshot.best_lap_time_s,
                    top3_avg_time_s=sd.snapshot.top3_avg_time_s,
                    avg_lap_time_s=sd.snapshot.avg_lap_time_s,
                    consistency_score=sd.snapshot.consistency_score,
                    **_equipment_fields(sd.session_id),
                )
            )
        else:
            # Fallback to DB metadata (telemetry not in memory — needs re-upload)
            date_str = row.session_date.isoformat() if row.session_date else ""
            items.append(
                SessionSummary(
                    session_id=row.session_id,
                    track_name=row.track_name,
                    session_date=date_str,
                    n_laps=row.n_laps,
                    n_clean_laps=row.n_clean_laps,
                    best_lap_time_s=row.best_lap_time_s,
                    top3_avg_time_s=row.top3_avg_time_s,
                    avg_lap_time_s=row.avg_lap_time_s,
                    consistency_score=row.consistency_score,
                )
            )
    return SessionList(items=items, total=len(items))


@router.get("/{session_id}", response_model=SessionSummary)
async def get_session(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> SessionSummary:
    """Get metadata and summary for a single session."""
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return SessionSummary(
        session_id=sd.session_id,
        track_name=sd.snapshot.metadata.track_name,
        session_date=sd.snapshot.metadata.session_date,
        n_laps=sd.snapshot.n_laps,
        n_clean_laps=sd.snapshot.n_clean_laps,
        best_lap_time_s=sd.snapshot.best_lap_time_s,
        top3_avg_time_s=sd.snapshot.top3_avg_time_s,
        avg_lap_time_s=sd.snapshot.avg_lap_time_s,
        consistency_score=sd.snapshot.consistency_score,
        **_equipment_fields(sd.session_id),
    )


@router.get("/{session_id}/compare/{other_id}", response_model=ComparisonResult)
async def compare_sessions(
    session_id: str,
    other_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ComparisonResult:
    """Compare best laps of two sessions (multi-driver comparison)."""
    sd_a = session_store.get_session(session_id)
    if sd_a is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    sd_b = session_store.get_session(other_id)
    if sd_b is None:
        raise HTTPException(status_code=404, detail=f"Session {other_id} not found")

    result = await run_comparison(sd_a, sd_b)
    return ComparisonResult(**result)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Delete a session owned by the current user."""
    db_deleted = await delete_session_db(db, session_id, current_user.user_id)
    if not db_deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    # Also remove from in-memory store and clear coaching cache
    session_store.delete_session(session_id)
    await clear_coaching_data(session_id)
    return {"message": f"Session {session_id} deleted"}


@router.delete("/all/clear")
async def delete_all_sessions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Delete all sessions for the current user."""
    db_rows = await list_sessions_for_user(db, current_user.user_id)
    count = 0
    for row in db_rows:
        await delete_session_db(db, row.session_id, current_user.user_id)
        session_store.delete_session(row.session_id)
        await clear_coaching_data(row.session_id)
        count += 1
    return {"message": f"Deleted {count} session(s)"}


@router.get("/{session_id}/laps", response_model=list[LapSummary])
async def get_lap_summaries(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[LapSummary]:
    """Get lap summaries for a session."""
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return [
        LapSummary(
            lap_number=s.lap_number,
            lap_time_s=s.lap_time_s,
            lap_distance_m=s.lap_distance_m,
            max_speed_mps=s.max_speed_mps,
            is_clean=s.lap_number not in sd.anomalous_laps,
            tags=sorted(sd.lap_tags.get_tags(s.lap_number)),
        )
        for s in sd.processed.lap_summaries
    ]


@router.get("/{session_id}/laps/{lap_number}/data", response_model=LapData)
async def get_lap_data(
    session_id: str,
    lap_number: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> LapData:
    """Get resampled telemetry data for a specific lap (columnar JSON)."""
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if lap_number not in sd.processed.resampled_laps:
        raise HTTPException(
            status_code=404, detail=f"Lap {lap_number} not found in session {session_id}"
        )

    df = sd.processed.resampled_laps[lap_number]
    return LapData(
        lap_number=lap_number,
        distance_m=df["lap_distance_m"].tolist(),
        speed_mph=(df["speed_mps"] * MPS_TO_MPH).tolist(),
        lat=df["lat"].tolist(),
        lon=df["lon"].tolist(),
        heading_deg=df["heading_deg"].tolist(),
        lateral_g=df["lateral_g"].tolist(),
        longitudinal_g=df["longitudinal_g"].tolist(),
        lap_time_s=df["lap_time_s"].tolist(),
    )


@router.get("/{session_id}/laps/{lap_number}/tags")
async def get_lap_tags(
    session_id: str,
    lap_number: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, object]:
    """Get tags for a specific lap."""
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if lap_number not in sd.processed.resampled_laps:
        raise HTTPException(
            status_code=404,
            detail=f"Lap {lap_number} not found in session {session_id}",
        )

    return {"lap_number": lap_number, "tags": sorted(sd.lap_tags.get_tags(lap_number))}


@router.put("/{session_id}/laps/{lap_number}/tags")
async def set_lap_tags(
    session_id: str,
    lap_number: int,
    tags: list[str],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, object]:
    """Set tags for a specific lap."""
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if lap_number not in sd.processed.resampled_laps:
        raise HTTPException(
            status_code=404,
            detail=f"Lap {lap_number} not found in session {session_id}",
        )

    # Clear existing tags and set new ones
    sd.lap_tags.tags[lap_number] = set(tags)
    return {"lap_number": lap_number, "tags": sorted(tags)}

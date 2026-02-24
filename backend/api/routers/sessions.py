"""Session management endpoints: upload, list, get, delete."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from backend.api.config import Settings
from backend.api.dependencies import get_settings
from backend.api.schemas.session import (
    LapData,
    LapSummary,
    SessionList,
    SessionSummary,
    UploadResponse,
)
from backend.api.services import session_store
from backend.api.services.pipeline import process_upload

logger = logging.getLogger(__name__)

router = APIRouter()

MPS_TO_MPH = 2.23694


@router.post("/upload", response_model=UploadResponse)
async def upload_sessions(
    files: list[UploadFile],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadResponse:
    """Upload one or more RaceChrono CSV files and create sessions."""
    session_ids: list[str] = []
    errors: list[str] = []

    for f in files:
        if not f.filename:
            errors.append("File with no name skipped")
            continue
        try:
            file_bytes = await f.read()
            result = await process_upload(file_bytes, f.filename)
            session_ids.append(str(result["session_id"]))
        except Exception as exc:
            logger.warning("Failed to process %s: %s", f.filename, exc, exc_info=True)
            errors.append(f"{f.filename}: {exc}")

    msg = f"Processed {len(session_ids)} file(s)"
    if errors:
        msg += f"; {len(errors)} error(s): {'; '.join(errors)}"

    return UploadResponse(session_ids=session_ids, message=msg)


@router.get("", response_model=SessionList)
async def list_sessions() -> SessionList:
    """List all stored sessions ordered by date descending."""
    all_sessions = session_store.list_sessions()
    items = [
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
        )
        for sd in all_sessions
    ]
    return SessionList(items=items, total=len(items))


@router.get("/{session_id}", response_model=SessionSummary)
async def get_session(session_id: str) -> SessionSummary:
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
    )


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete a session and its associated data."""
    deleted = session_store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"message": f"Session {session_id} deleted"}


@router.delete("/all/clear")
async def delete_all_sessions() -> dict[str, str]:
    """Delete all sessions."""
    count = session_store.clear_all()
    return {"message": f"Deleted {count} session(s)"}


@router.get("/{session_id}/laps", response_model=list[LapSummary])
async def get_lap_summaries(session_id: str) -> list[LapSummary]:
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
        )
        for s in sd.processed.lap_summaries
    ]


@router.get("/{session_id}/laps/{lap_number}/data", response_model=LapData)
async def get_lap_data(session_id: str, lap_number: int) -> LapData:
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

"""Session management endpoints: upload, list, get, delete."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.config import Settings
from backend.api.dependencies import get_db, get_settings
from backend.api.schemas.session import (
    LapData,
    LapSummary,
    SessionList,
    SessionSummary,
    UploadResponse,
)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_sessions(
    files: list[UploadFile],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadResponse:
    """Upload one or more RaceChrono CSV files and create sessions."""
    # TODO: Phase 1 — parse CSVs via cataclysm.parser, run pipeline, persist
    return UploadResponse(session_ids=[], message="Upload not yet implemented")


@router.get("/", response_model=SessionList)
async def list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionList:
    """List all stored sessions ordered by date descending."""
    # TODO: Phase 1 — query sessions table
    return SessionList(items=[], total=0)


@router.get("/{session_id}", response_model=SessionSummary)
async def get_session(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionSummary:
    """Get metadata and summary for a single session."""
    # TODO: Phase 1 — fetch from DB, raise 404 if missing
    raise NotImplementedError


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Delete a session and its associated data."""
    # TODO: Phase 1 — cascade delete session + files
    return {"message": f"Session {session_id} deleted"}


@router.delete("/")
async def delete_all_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Delete all sessions."""
    # TODO: Phase 1 — truncate sessions table
    return {"message": "All sessions deleted"}


@router.get("/{session_id}/laps", response_model=list[LapSummary])
async def get_lap_summaries(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LapSummary]:
    """Get lap summaries for a session."""
    # TODO: Phase 1 — load ProcessedSession, return summaries
    return []


@router.get("/{session_id}/laps/{lap_number}/data", response_model=LapData)
async def get_lap_data(
    session_id: str,
    lap_number: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LapData:
    """Get resampled telemetry data for a specific lap (columnar JSON)."""
    # TODO: Phase 1 — load resampled DataFrame, serialize columns
    raise NotImplementedError

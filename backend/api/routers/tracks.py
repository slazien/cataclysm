"""Track folder scanning endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.config import Settings
from backend.api.dependencies import get_db, get_settings

router = APIRouter()


class TrackFolder(dict[str, object]):
    """Inline schema for a track folder entry."""


@router.get("/")
async def list_track_folders(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[dict[str, object]]:
    """List available track folders in the data directory.

    Scans ``settings.session_data_dir`` for subdirectories containing CSV files.
    """
    # TODO: Phase 1 — scan filesystem for track folders
    return []


@router.post("/{folder}/load")
async def load_track_folder(
    folder: str,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Load all RaceChrono CSV files from a track folder.

    Parses and processes each CSV, stores sessions in the database.
    Returns a summary of loaded sessions.
    """
    # TODO: Phase 1 — iterate CSVs in folder, parse+process each, persist
    return {
        "folder": folder,
        "sessions_loaded": 0,
        "message": "Track folder loading not yet implemented",
    }

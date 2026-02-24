"""Track folder scanning and loading endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.api.config import Settings
from backend.api.dependencies import get_settings
from backend.api.services.pipeline import process_file_path

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def list_track_folders(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[dict[str, object]]:
    """List available track folders in the data directory.

    Scans ``settings.session_data_dir`` for subdirectories containing CSV files.
    """
    data_dir = Path(settings.session_data_dir)
    if not data_dir.is_dir():
        return []

    folders: list[dict[str, object]] = []
    for child in sorted(data_dir.iterdir()):
        if not child.is_dir():
            continue
        csv_files = list(child.glob("*.csv"))
        if csv_files:
            folders.append(
                {
                    "folder": child.name,
                    "n_files": len(csv_files),
                    "path": str(child),
                }
            )

    return folders


@router.post("/{folder}/load")
async def load_track_folder(
    folder: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Load all RaceChrono CSV files from a track folder.

    Parses and processes each CSV, stores sessions in the in-memory store.
    Returns a summary of loaded sessions.
    """
    data_dir = Path(settings.session_data_dir) / folder
    if not data_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Track folder '{folder}' not found")

    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise HTTPException(status_code=404, detail=f"No CSV files found in '{folder}'")

    session_ids: list[str] = []
    errors: list[str] = []

    for csv_path in csv_files:
        try:
            result = await process_file_path(csv_path)
            session_ids.append(str(result["session_id"]))
        except Exception as exc:
            logger.warning("Failed to process %s: %s", csv_path.name, exc, exc_info=True)
            errors.append(f"{csv_path.name}: {exc}")

    return {
        "folder": folder,
        "sessions_loaded": len(session_ids),
        "session_ids": session_ids,
        "errors": errors,
    }

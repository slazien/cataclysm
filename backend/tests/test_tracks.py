"""Tests for track folder scanning and loading endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from backend.api.config import Settings
from backend.api.dependencies import get_settings
from backend.api.main import app


def _override_settings(data_dir: str) -> Settings:
    """Create a Settings override pointing to a custom data dir."""
    return Settings(session_data_dir=data_dir)


@pytest.mark.asyncio
async def test_list_track_folders_empty(client: AsyncClient, tmp_path: Path) -> None:
    """GET /api/tracks/ returns empty list when data dir has no track folders."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    app.dependency_overrides[get_settings] = lambda: _override_settings(str(empty_dir))
    try:
        response = await client.get("/api/tracks/")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_list_track_folders_with_data(client: AsyncClient, tmp_path: Path) -> None:
    """GET /api/tracks/ returns folders containing CSV files."""
    track_dir = tmp_path / "test_track"
    track_dir.mkdir()
    (track_dir / "session1.csv").write_text("data")

    app.dependency_overrides[get_settings] = lambda: _override_settings(str(tmp_path))
    try:
        response = await client.get("/api/tracks/")
        assert response.status_code == 200
        folders = response.json()
        assert len(folders) == 1
        assert folders[0]["folder"] == "test_track"
        assert folders[0]["n_files"] == 1
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_load_track_folder_not_found(client: AsyncClient, tmp_path: Path) -> None:
    """POST /api/tracks/{folder}/load with nonexistent folder returns 404."""
    app.dependency_overrides[get_settings] = lambda: _override_settings(str(tmp_path))
    try:
        response = await client.post("/api/tracks/nonexistent_folder/load")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_load_track_folder_no_csvs(client: AsyncClient, tmp_path: Path) -> None:
    """POST /api/tracks/{folder}/load with no CSVs returns 404."""
    folder = tmp_path / "empty_track"
    folder.mkdir()

    app.dependency_overrides[get_settings] = lambda: _override_settings(str(tmp_path))
    try:
        response = await client.post("/api/tracks/empty_track/load")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_load_track_folder_with_valid_csvs(
    client: AsyncClient, tmp_path: Path, synthetic_csv_bytes: bytes
) -> None:
    """POST /api/tracks/{folder}/load processes CSVs and returns session_ids."""
    folder = tmp_path / "test_track"
    folder.mkdir()
    (folder / "session1.csv").write_bytes(synthetic_csv_bytes)

    app.dependency_overrides[get_settings] = lambda: _override_settings(str(tmp_path))
    try:
        response = await client.post("/api/tracks/test_track/load")
        assert response.status_code == 200
        data = response.json()
        assert data["folder"] == "test_track"
        assert data["sessions_loaded"] == 1
        assert len(data["session_ids"]) == 1
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_load_track_folder_with_invalid_csv(client: AsyncClient, tmp_path: Path) -> None:
    """POST /api/tracks/{folder}/load reports errors for invalid CSVs."""
    folder = tmp_path / "bad_track"
    folder.mkdir()
    (folder / "bad.csv").write_text("not,valid,csv")

    app.dependency_overrides[get_settings] = lambda: _override_settings(str(tmp_path))
    try:
        response = await client.post("/api/tracks/bad_track/load")
        assert response.status_code == 200
        data = response.json()
        assert data["sessions_loaded"] == 0
        assert len(data["errors"]) == 1
    finally:
        app.dependency_overrides.pop(get_settings, None)

"""Extended tests for tracks router — covers uncovered lines [30, 35, 70].

Line 30: list_track_folders returns [] when data_dir doesn't exist
Line 35: list_track_folders skips non-directory entries
Line 70: load_track_folder uses limit parameter to restrict CSV files
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from httpx import AsyncClient

from backend.api.config import Settings
from backend.api.dependencies import get_settings
from backend.api.main import app


def _make_settings_with_dir(path: str) -> Settings:
    s = Settings()
    s.session_data_dir = path
    return s


class TestListTrackFolders:
    """Tests for GET /api/tracks."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_dir_does_not_exist(self, client: AsyncClient) -> None:
        """Returns [] when session_data_dir does not exist (line 30)."""
        app.dependency_overrides[get_settings] = lambda: _make_settings_with_dir(
            "/tmp/no-such-tracks-dir-xyz"
        )
        try:
            resp = await client.get("/api/tracks")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            app.dependency_overrides.pop(get_settings, None)

    @pytest.mark.asyncio
    async def test_skips_non_directory_entries(self, client: AsyncClient) -> None:
        """list_track_folders skips files inside the data dir (line 35)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file (not a dir) alongside a valid subdir
            (Path(tmpdir) / "readme.txt").write_text("not a dir")
            subdir = Path(tmpdir) / "barber"
            subdir.mkdir()
            (subdir / "session1.csv").write_text("data")

            app.dependency_overrides[get_settings] = lambda: _make_settings_with_dir(tmpdir)
            try:
                resp = await client.get("/api/tracks")
                assert resp.status_code == 200
                data = resp.json()
                # Should only see "barber", not "readme.txt"
                assert len(data) == 1
                assert data[0]["folder"] == "barber"
            finally:
                app.dependency_overrides.pop(get_settings, None)

    @pytest.mark.asyncio
    async def test_skips_dirs_without_csv_files(self, client: AsyncClient) -> None:
        """list_track_folders skips subdirs with no CSV files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir) / "empty_track"
            empty_dir.mkdir()
            (empty_dir / "notes.txt").write_text("no csvs here")

            app.dependency_overrides[get_settings] = lambda: _make_settings_with_dir(tmpdir)
            try:
                resp = await client.get("/api/tracks")
                assert resp.status_code == 200
                assert resp.json() == []
            finally:
                app.dependency_overrides.pop(get_settings, None)

    @pytest.mark.asyncio
    async def test_returns_folder_metadata(self, client: AsyncClient) -> None:
        """list_track_folders returns folder name, n_files, and path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "road_atlanta"
            subdir.mkdir()
            (subdir / "lap1.csv").write_text("data")
            (subdir / "lap2.csv").write_text("data")

            app.dependency_overrides[get_settings] = lambda: _make_settings_with_dir(tmpdir)
            try:
                resp = await client.get("/api/tracks")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) == 1
                folder = data[0]
                assert folder["folder"] == "road_atlanta"
                assert folder["n_files"] == 2
                assert "folder" in folder
            finally:
                app.dependency_overrides.pop(get_settings, None)


class TestLoadTrackFolder:
    """Tests for POST /api/tracks/{folder}/load."""

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, client: AsyncClient) -> None:
        """POST on a nonexistent folder returns 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app.dependency_overrides[get_settings] = lambda: _make_settings_with_dir(tmpdir)
            try:
                resp = await client.post("/api/tracks/nonexistent-folder/load")
                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"].lower()
            finally:
                app.dependency_overrides.pop(get_settings, None)

    @pytest.mark.asyncio
    async def test_empty_folder_returns_404(self, client: AsyncClient) -> None:
        """POST on a folder with no CSVs returns 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty = Path(tmpdir) / "empty"
            empty.mkdir()
            app.dependency_overrides[get_settings] = lambda: _make_settings_with_dir(tmpdir)
            try:
                resp = await client.post("/api/tracks/empty/load")
                assert resp.status_code == 404
                assert "no csv" in resp.json()["detail"].lower()
            finally:
                app.dependency_overrides.pop(get_settings, None)

    @pytest.mark.asyncio
    async def test_limit_parameter_restricts_loaded_files(self, client: AsyncClient) -> None:
        """POST with limit=1 only processes the first CSV (line 70)."""
        from backend.tests.conftest import build_synthetic_csv

        with tempfile.TemporaryDirectory() as tmpdir:
            track_dir = Path(tmpdir) / "test_track"
            track_dir.mkdir()
            # Write two valid CSV files
            (track_dir / "a_session.csv").write_bytes(build_synthetic_csv(n_laps=2))
            (track_dir / "b_session.csv").write_bytes(build_synthetic_csv(n_laps=2))

            app.dependency_overrides[get_settings] = lambda: _make_settings_with_dir(tmpdir)
            try:
                resp = await client.post("/api/tracks/test_track/load?limit=1")
                assert resp.status_code == 200
                data = resp.json()
                # With limit=1, only one session should be loaded
                assert data["sessions_loaded"] + len(data["errors"]) <= 1
            finally:
                app.dependency_overrides.pop(get_settings, None)

    @pytest.mark.asyncio
    async def test_load_folder_returns_error_for_bad_csv(self, client: AsyncClient) -> None:
        """POST logs errors for unparseable CSVs and returns them in response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            track_dir = Path(tmpdir) / "bad_track"
            track_dir.mkdir()
            (track_dir / "bad.csv").write_text("this is not valid RaceChrono CSV data")

            app.dependency_overrides[get_settings] = lambda: _make_settings_with_dir(tmpdir)
            try:
                resp = await client.post("/api/tracks/bad_track/load")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data["errors"]) >= 1
                assert data["sessions_loaded"] == 0
            finally:
                app.dependency_overrides.pop(get_settings, None)

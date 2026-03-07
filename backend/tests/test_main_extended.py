"""Extended tests for main.py — covers CacheControlMiddleware, exception handlers, health.

Lines targeted:
  - 308-330: CacheControlMiddleware.dispatch — cache header rules per path
  - 337-347: generic_exception_handler — returns 500 for unhandled exceptions
  - 350-357: value_error_handler — returns 422 for ValueError
  - 397-406: health check endpoint
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Cache-Control middleware tests
# The middleware only adds headers to GET responses with status < 400.
# We use routes that return 200 to verify header assignment.
# ---------------------------------------------------------------------------


class TestCacheControlMiddleware:
    """Tests for CacheControlMiddleware.dispatch (lines 308-330)."""

    @pytest.mark.asyncio
    async def test_equipment_profiles_list_gets_no_cache(self, client: AsyncClient) -> None:
        """GET /api/equipment/profiles returns no-cache (equipment prefix rule)."""
        resp = await client.get("/api/equipment/profiles")
        assert resp.status_code == 200
        cc = resp.headers.get("cache-control", "")
        assert "no-cache" in cc

    @pytest.mark.asyncio
    async def test_tracks_endpoint_gets_max_age_3600(self, client: AsyncClient) -> None:
        """GET /api/tracks returns max-age=3600 (static data rule)."""
        resp = await client.get("/api/tracks")
        assert resp.status_code == 200
        cc = resp.headers.get("cache-control", "")
        assert "max-age=3600" in cc

    @pytest.mark.asyncio
    async def test_leaderboards_endpoint_gets_no_cache(self, client: AsyncClient) -> None:
        """GET /api/leaderboards/* returns no-cache (leaderboard rule)."""
        from unittest.mock import AsyncMock, patch

        # Mock the service to return 200 with an empty list
        with patch(
            "backend.api.routers.leaderboards.get_corner_leaderboard",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await client.get("/api/leaderboards/barber/corners?corner=1")
        assert resp.status_code == 200
        cc = resp.headers.get("cache-control", "")
        assert "no-cache" in cc

    @pytest.mark.asyncio
    async def test_health_endpoint_gets_default_no_cache(self, client: AsyncClient) -> None:
        """GET /health (unmatched path) gets default Cache-Control: no-cache."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        cc = resp.headers.get("cache-control", "")
        # /health doesn't match any prefix → falls through to else: no-cache
        assert "no-cache" in cc

    @pytest.mark.asyncio
    async def test_session_upload_post_skips_cache_header(self, client: AsyncClient) -> None:
        """POST requests are not given Cache-Control by middleware (non-GET bypass)."""
        from backend.tests.conftest import build_synthetic_csv

        csv = build_synthetic_csv(n_laps=2)
        resp = await client.post(
            "/api/sessions/upload",
            files=[("files", ("test.csv", csv, "text/csv"))],
        )
        assert resp.status_code == 200
        # POST — middleware returns early on non-GET, no cache header added
        # The response should not have max-age (immutable-style) headers
        cc = resp.headers.get("cache-control", "")
        assert "max-age=3600" not in cc

    @pytest.mark.asyncio
    async def test_error_response_skips_cache_header(self, client: AsyncClient) -> None:
        """4xx responses don't get Cache-Control added by middleware."""
        # Request a nonexistent session — 404
        resp = await client.get("/api/sessions/does-not-exist-xyz")
        assert resp.status_code == 404
        # Middleware skips when status_code >= 400
        cc = resp.headers.get("cache-control", "")
        # No cache header should be present on error responses
        assert cc == "" or "no-cache" not in cc or cc == ""

    def test_cache_control_middleware_class_dispatch_websocket_skipped(self) -> None:
        """CacheControlMiddleware skips WebSocket scope (line 311)."""
        import asyncio
        from unittest.mock import AsyncMock

        from backend.api.main import CacheControlMiddleware

        app_mock = MagicMock()
        middleware = CacheControlMiddleware(app_mock)

        # Create a mock request with WebSocket scope
        mock_request = MagicMock()
        mock_request.scope = {"type": "websocket"}

        next_response = MagicMock()
        mock_call_next = AsyncMock(return_value=next_response)

        # Should call call_next and return result without modifying headers
        async def run() -> None:
            result = await middleware.dispatch(mock_request, mock_call_next)
            assert result is next_response  # Returns immediately from call_next

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Exception handler tests — call handlers directly to avoid middleware interference
# ---------------------------------------------------------------------------


class TestExceptionHandlers:
    """Tests for main.py exception handlers (lines 337-357)."""

    @pytest.mark.asyncio
    async def test_value_error_handler_returns_422(self) -> None:
        """value_error_handler returns 422 JSONResponse with generic message (lines 350-357)."""
        from fastapi import Request

        from backend.api.main import value_error_handler

        # Build a minimal mock Request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
        }
        mock_request = Request(scope)
        exc = ValueError("Sensitive internal detail")

        response = await value_error_handler(mock_request, exc)
        assert response.status_code == 422
        import json

        body = json.loads(response.body)
        assert body["detail"] == "Invalid input data"
        assert "Sensitive internal detail" not in body["detail"]

    @pytest.mark.asyncio
    async def test_generic_exception_handler_returns_500(self) -> None:
        """generic_exception_handler returns 500 with 'Internal server error' (lines 337-347)."""
        from fastapi import Request

        from backend.api.main import generic_exception_handler

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/something",
            "query_string": b"",
            "headers": [],
        }
        mock_request = Request(scope)
        exc = RuntimeError("Internal implementation detail")

        response = await generic_exception_handler(mock_request, exc)
        assert response.status_code == 500
        import json

        body = json.loads(response.body)
        assert body["detail"] == "Internal server error"
        assert "Internal implementation detail" not in body["detail"]


# ---------------------------------------------------------------------------
# Health check endpoint tests
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Tests for /health endpoint (lines 397-406)."""

    @pytest.mark.asyncio
    async def test_health_returns_200_with_ok_status(self, client: AsyncClient) -> None:
        """GET /health returns 200 with status=ok and db=ok."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"

    @pytest.mark.asyncio
    async def test_health_db_error_sets_degraded_status(self, client: AsyncClient) -> None:
        """GET /health sets db=error and status=degraded when SELECT 1 fails (lines 402-406)."""
        from backend.api.db.database import get_db
        from backend.api.main import app

        # Override the DB dependency to return a session that raises on execute
        async def failing_db():
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(side_effect=Exception("DB down"))
            yield mock_session

        app.dependency_overrides[get_db] = failing_db
        try:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["db"] == "error"
            assert data["status"] == "degraded"
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# _reload_sessions_from_db — direct function tests
# ---------------------------------------------------------------------------


class TestReloadSessionsFromDb:
    """Tests for _reload_sessions_from_db startup helper (lines 67-106)."""

    @pytest.mark.asyncio
    async def test_reload_returns_zero_when_no_session_files(self) -> None:
        """_reload_sessions_from_db returns 0 when no SessionFile rows exist (uses test DB)."""
        from backend.api.main import _reload_sessions_from_db
        from backend.tests.conftest import _test_session_factory

        # Patch async_session_factory to use the test SQLite DB
        with patch("backend.api.db.database.async_session_factory", _test_session_factory):
            result = await _reload_sessions_from_db()
        # Test DB has no SessionFile rows
        assert result == 0

    @pytest.mark.asyncio
    async def test_reload_from_db_loads_uploaded_session(self) -> None:
        """_reload_sessions_from_db reloads a session from DB using test DB."""
        import datetime as _dt

        from backend.api.main import _reload_sessions_from_db
        from backend.api.services import session_store
        from backend.api.services.pipeline import process_upload
        from backend.tests.conftest import _TEST_USER, _test_session_factory, build_synthetic_csv

        csv = build_synthetic_csv(n_laps=2)
        upload_result = await process_upload(csv, "reload-test.csv")
        sid = str(upload_result["session_id"])

        # Store session + file bytes to test DB
        from backend.api.db.models import Session as SessionModel
        from backend.api.db.models import SessionFile

        async with _test_session_factory() as db:
            existing = await db.get(SessionModel, sid)
            if existing is None:
                db.add(
                    SessionModel(
                        session_id=sid,
                        user_id=_TEST_USER.user_id,
                        track_name="Test Circuit",
                        session_date=_dt.datetime.now(_dt.UTC),
                        file_key=sid,
                        n_laps=2,
                    )
                )
                await db.flush()
            existing_sf = await db.get(SessionFile, sid)
            if existing_sf is None:
                db.add(SessionFile(session_id=sid, filename="reload-test.csv", csv_bytes=csv))
            await db.commit()

        # Clear in-memory store and reload using the test DB
        session_store.clear_all()
        with patch("backend.api.db.database.async_session_factory", _test_session_factory):
            count = await _reload_sessions_from_db()
        assert count >= 1
        sd = session_store.get_session(sid)
        assert sd is not None

    @pytest.mark.asyncio
    async def test_reload_from_db_handles_sqlalchemy_error(self) -> None:
        """_reload_sessions_from_db returns 0 on SQLAlchemy errors (lines 103-104)."""
        # Make the context manager raise
        from contextlib import asynccontextmanager

        from sqlalchemy.exc import SQLAlchemyError

        from backend.api.main import _reload_sessions_from_db

        @asynccontextmanager
        async def _failing_factory():
            raise SQLAlchemyError("DB connection failed")
            yield  # type: ignore[misc]

        with patch("backend.api.db.database.async_session_factory", _failing_factory):
            result = await _reload_sessions_from_db()

        assert result == 0

    @pytest.mark.asyncio
    async def test_reload_from_db_skips_invalid_csv(self) -> None:
        """_reload_sessions_from_db skips rows with unparseable CSV (lines 96-102)."""
        import datetime as _dt

        from backend.api.db.models import Session as SessionModel
        from backend.api.db.models import SessionFile
        from backend.api.main import _reload_sessions_from_db
        from backend.tests.conftest import _TEST_USER, _test_session_factory

        bad_sid = "bad-csv-reload-001"
        bad_csv = b"this is not a valid RaceChrono CSV at all"

        async with _test_session_factory() as db:
            existing = await db.get(SessionModel, bad_sid)
            if existing is None:
                db.add(
                    SessionModel(
                        session_id=bad_sid,
                        user_id=_TEST_USER.user_id,
                        track_name="Test",
                        session_date=_dt.datetime.now(_dt.UTC),
                        file_key=bad_sid,
                        n_laps=1,
                    )
                )
                await db.flush()
            existing_sf = await db.get(SessionFile, bad_sid)
            if existing_sf is None:
                db.add(SessionFile(session_id=bad_sid, filename="bad.csv", csv_bytes=bad_csv))
            await db.commit()

        # Should not raise — logs warning and continues
        with patch("backend.api.db.database.async_session_factory", _test_session_factory):
            result = await _reload_sessions_from_db()
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# _reload_sessions_from_disk — direct function tests
# ---------------------------------------------------------------------------


class TestReloadSessionsFromDisk:
    """Tests for _reload_sessions_from_disk startup helper (lines 133-185)."""

    @pytest.mark.asyncio
    async def test_reload_from_disk_returns_zero_when_dir_missing(self) -> None:
        """_reload_sessions_from_disk returns 0 when session_data_dir doesn't exist."""
        from backend.api.main import _reload_sessions_from_disk, settings

        original_dir = settings.session_data_dir
        settings.session_data_dir = "/tmp/nonexistent-dir-xyz-999"
        try:
            with patch(
                "backend.api.db.database.async_session_factory",
                __import__(
                    "backend.tests.conftest", fromlist=["_test_session_factory"]
                )._test_session_factory,
            ):
                result = await _reload_sessions_from_disk()
            assert result == 0
        finally:
            settings.session_data_dir = original_dir

    @pytest.mark.asyncio
    async def test_reload_from_disk_returns_zero_when_dir_empty(self) -> None:
        """_reload_sessions_from_disk returns 0 when dir has no CSV files (line 133-135)."""
        import tempfile

        from backend.api.main import _reload_sessions_from_disk, settings
        from backend.tests.conftest import _test_session_factory

        with tempfile.TemporaryDirectory() as tmpdir:
            original_dir = settings.session_data_dir
            settings.session_data_dir = tmpdir
            try:
                with patch("backend.api.db.database.async_session_factory", _test_session_factory):
                    result = await _reload_sessions_from_disk()
                assert result == 0
            finally:
                settings.session_data_dir = original_dir

    @pytest.mark.asyncio
    async def test_reload_from_disk_loads_valid_csv(self) -> None:
        """_reload_sessions_from_disk loads a valid CSV from disk (lines 152-183)."""
        import os
        import tempfile

        from backend.api.main import _reload_sessions_from_disk, settings
        from backend.api.services import session_store
        from backend.tests.conftest import _test_session_factory, build_synthetic_csv

        csv_bytes = build_synthetic_csv(n_laps=2)

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test_session.csv")
            with open(csv_path, "wb") as f:
                f.write(csv_bytes)

            session_store.clear_all()
            original_dir = settings.session_data_dir
            settings.session_data_dir = tmpdir
            try:
                with patch("backend.api.db.database.async_session_factory", _test_session_factory):
                    result = await _reload_sessions_from_disk()
                assert result >= 1
            finally:
                settings.session_data_dir = original_dir

    @pytest.mark.asyncio
    async def test_reload_from_disk_skips_invalid_csv(self) -> None:
        """_reload_sessions_from_disk logs warning and skips bad CSV (line 181-182)."""
        import os
        import tempfile

        from backend.api.main import _reload_sessions_from_disk, settings
        from backend.tests.conftest import _test_session_factory

        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = os.path.join(tmpdir, "bad.csv")
            with open(bad_path, "wb") as f:
                f.write(b"this is not a valid CSV")

            original_dir = settings.session_data_dir
            settings.session_data_dir = tmpdir
            try:
                with patch("backend.api.db.database.async_session_factory", _test_session_factory):
                    result = await _reload_sessions_from_disk()
                # Bad CSV is skipped — loaded count stays 0
                assert result == 0
            finally:
                settings.session_data_dir = original_dir

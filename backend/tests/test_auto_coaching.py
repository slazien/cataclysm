"""Tests for auto-coaching on upload and coaching report DB persistence."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from cataclysm.coaching import CoachingContext, CoachingReport, CornerGrade
from httpx import AsyncClient

from backend.api.schemas.coaching import (
    CoachingReportResponse,
    CornerGradeSchema,
    PriorityCornerSchema,
)
from backend.api.services.coaching_store import (
    clear_all_coaching,
    clear_coaching_data,
    get_coaching_report,
    store_coaching_context,
    store_coaching_report,
)
from backend.api.services.db_coaching_store import (
    get_coaching_context_db,
    get_coaching_report_db,
)
from backend.tests.conftest import _test_session_factory, build_synthetic_csv


def _mock_coaching_report() -> CoachingReport:
    """Create a mock coaching report for testing."""
    return CoachingReport(
        summary="Auto-generated report for testing.",
        priority_corners=[
            {
                "corner": 1,
                "time_cost_s": 0.30,
                "issue": "Late apex",
                "tip": "Turn in earlier",
            },
        ],
        corner_grades=[
            CornerGrade(
                corner=1,
                braking="B",
                trail_braking="C",
                min_speed="B",
                throttle="A",
                notes="Solid braking, work on trail.",
            ),
        ],
        patterns=["Consistent braking across laps"],
        drills=["Trail brake drill for T1"],
        raw_response="mock response",
    )


@pytest.fixture(autouse=True)
def _clear() -> None:
    """Clear coaching store before each test."""
    clear_all_coaching()


@pytest.fixture(autouse=True)
def _disable_auto_coaching() -> None:  # type: ignore[override]
    """Override the conftest fixture to re-enable auto-coaching in this module."""
    # Same name as conftest fixture so pytest uses this local no-op version.


class TestAutoCoachingOnUpload:
    """Tests for automatic coaching report generation on CSV upload."""

    @pytest.mark.asyncio
    async def test_upload_triggers_auto_coaching(self, client: AsyncClient) -> None:
        """Upload should trigger coaching generation in the background."""
        csv_bytes = build_synthetic_csv(n_laps=5)

        with patch(
            "cataclysm.coaching.generate_coaching_report",
            return_value=_mock_coaching_report(),
        ):
            resp = await client.post(
                "/api/sessions/upload",
                files=[("files", ("test.csv", csv_bytes, "text/csv"))],
            )
            assert resp.status_code == 200
            session_id = resp.json()["session_ids"][0]

            # Let background task finish
            await asyncio.sleep(0.5)

        # Report should now be available
        report_resp = await client.get(f"/api/coaching/{session_id}/report")
        assert report_resp.status_code == 200
        data = report_resp.json()
        assert data["status"] == "ready"
        assert "Auto-generated" in data["summary"]

    @pytest.mark.asyncio
    async def test_upload_auto_coaching_does_not_block_upload(self, client: AsyncClient) -> None:
        """Upload should return immediately; coaching runs in background."""
        csv_bytes = build_synthetic_csv(n_laps=5)

        with patch(
            "cataclysm.coaching.generate_coaching_report",
            side_effect=lambda *a, **kw: _mock_coaching_report(),
        ):
            resp = await client.post(
                "/api/sessions/upload",
                files=[("files", ("test.csv", csv_bytes, "text/csv"))],
            )
            assert resp.status_code == 200
            # Upload completes without waiting for coaching
            assert len(resp.json()["session_ids"]) == 1


class TestCoachingPersistence:
    """Tests for PostgreSQL persistence of coaching reports."""

    @pytest.mark.asyncio
    async def test_store_and_load_report(self) -> None:
        """Stored reports should be persisted to DB and retrievable."""
        report = CoachingReportResponse(
            session_id="test-session-1",
            status="ready",
            summary="Great driving session.",
            priority_corners=[
                PriorityCornerSchema(
                    corner=1, time_cost_s=0.3, issue="Late apex", tip="Turn in earlier"
                ),
            ],
            corner_grades=[
                CornerGradeSchema(
                    corner=1,
                    braking="A",
                    trail_braking="B",
                    min_speed="A",
                    throttle="A",
                    notes="Excellent.",
                ),
            ],
            patterns=["Consistent braking"],
            drills=["Trail brake drill"],
        )

        await store_coaching_report("test-session-1", report)

        # Verify it's in DB
        async with _test_session_factory() as db:
            db_report = await get_coaching_report_db(db, "test-session-1")
        assert db_report is not None
        assert db_report.session_id == "test-session-1"
        assert db_report.status == "ready"
        assert db_report.summary == "Great driving session."
        assert len(db_report.priority_corners) == 1
        assert len(db_report.corner_grades) == 1

    @pytest.mark.asyncio
    async def test_error_reports_not_cached_on_lazy_load(self) -> None:
        """Error reports in DB should not be cached by lazy loader."""
        error_report = CoachingReportResponse(
            session_id="error-session",
            status="error",
            summary="AI coaching is temporarily unavailable.",
        )
        await store_coaching_report("error-session", error_report)

        # Clear in-memory cache, then try lazy load
        clear_all_coaching()
        loaded = await get_coaching_report("error-session")
        # Lazy loader skips non-"ready" reports
        assert loaded is None

    @pytest.mark.asyncio
    async def test_clear_coaching_data_removes_db_rows(self) -> None:
        """Clearing coaching data should remove from both memory and DB."""
        report = CoachingReportResponse(
            session_id="delete-me",
            status="ready",
            summary="Will be deleted.",
        )
        await store_coaching_report("delete-me", report)

        ctx = CoachingContext(messages=[{"role": "user", "content": "How can I brake later?"}])
        await store_coaching_context("delete-me", ctx)

        # Verify both exist in DB
        async with _test_session_factory() as db:
            assert await get_coaching_report_db(db, "delete-me") is not None
            assert await get_coaching_context_db(db, "delete-me") is not None

        # Clear
        await clear_coaching_data("delete-me")

        # Verify gone from DB
        async with _test_session_factory() as db:
            assert await get_coaching_report_db(db, "delete-me") is None
            assert await get_coaching_context_db(db, "delete-me") is None

        # And from memory
        assert await get_coaching_report("delete-me") is None

    @pytest.mark.asyncio
    async def test_lazy_load_from_db(self) -> None:
        """After clearing memory cache, get should lazy-load from DB."""
        report = CoachingReportResponse(
            session_id="lazy-session",
            status="ready",
            summary="Lazy loading test.",
        )
        await store_coaching_report("lazy-session", report)

        # Clear memory only — DB still has the report
        clear_all_coaching()
        assert await get_coaching_report("lazy-session") is not None

        loaded = await get_coaching_report("lazy-session")
        assert loaded is not None
        assert loaded.summary == "Lazy loading test."

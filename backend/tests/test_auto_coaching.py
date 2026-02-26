"""Tests for auto-coaching on upload and coaching report persistence."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from cataclysm.coaching import CoachingReport, CornerGrade
from httpx import AsyncClient

from backend.api.schemas.coaching import (
    CoachingReportResponse,
    CornerGradeSchema,
    PriorityCornerSchema,
)
from backend.api.services.coaching_store import (
    clear_all_coaching,
    get_coaching_report,
    init_coaching_dir,
    load_persisted_reports,
    store_coaching_report,
)
from backend.tests.conftest import build_synthetic_csv


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
    """Tests for JSON disk persistence of coaching reports."""

    def test_init_coaching_dir_creates_directory(self, tmp_path: Path) -> None:
        """init_coaching_dir should create the directory if missing."""
        coaching_dir = tmp_path / "coaching"
        assert not coaching_dir.exists()
        init_coaching_dir(str(coaching_dir))
        assert coaching_dir.exists()

    def test_store_and_load_report(self, tmp_path: Path) -> None:
        """Stored reports should be persisted to JSON and loadable."""
        coaching_dir = tmp_path / "coaching"
        init_coaching_dir(str(coaching_dir))

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

        store_coaching_report("test-session-1", report)

        # Verify JSON file was written
        json_path = coaching_dir / "test-session-1.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["session_id"] == "test-session-1"
        assert data["status"] == "ready"

        # Clear in-memory store, then reload from disk
        clear_all_coaching()
        assert get_coaching_report("test-session-1") is None

        count = load_persisted_reports()
        assert count == 1
        loaded = get_coaching_report("test-session-1")
        assert loaded is not None
        assert loaded.summary == "Great driving session."
        assert len(loaded.priority_corners) == 1
        assert len(loaded.corner_grades) == 1

    def test_error_reports_not_loaded(self, tmp_path: Path) -> None:
        """Error reports should not be loaded from disk."""
        coaching_dir = tmp_path / "coaching"
        init_coaching_dir(str(coaching_dir))

        error_report = CoachingReportResponse(
            session_id="error-session",
            status="error",
            summary="AI coaching is temporarily unavailable.",
        )
        store_coaching_report("error-session", error_report)

        clear_all_coaching()
        count = load_persisted_reports()
        assert count == 0
        assert get_coaching_report("error-session") is None

    def test_clear_coaching_data_removes_file(self, tmp_path: Path) -> None:
        """Clearing coaching data should also delete the persisted JSON."""
        from backend.api.services.coaching_store import clear_coaching_data

        coaching_dir = tmp_path / "coaching"
        init_coaching_dir(str(coaching_dir))

        report = CoachingReportResponse(
            session_id="delete-me",
            status="ready",
            summary="Will be deleted.",
        )
        store_coaching_report("delete-me", report)

        json_path = coaching_dir / "delete-me.json"
        assert json_path.exists()

        clear_coaching_data("delete-me")
        assert not json_path.exists()
        assert get_coaching_report("delete-me") is None

"""Tests for the PDF export endpoint."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from cataclysm.coaching import CoachingReport, CornerGrade
from httpx import AsyncClient

from backend.api.services.coaching_store import clear_all_coaching
from backend.tests.conftest import build_synthetic_csv


async def _upload_session(
    client: AsyncClient,
    csv_bytes: bytes | None = None,
    filename: str = "test.csv",
) -> str:
    """Helper: upload a CSV and return the session_id."""
    if csv_bytes is None:
        csv_bytes = build_synthetic_csv(n_laps=5)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", (filename, csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200
    session_id: str = resp.json()["session_ids"][0]
    return session_id


def _mock_coaching_report() -> CoachingReport:
    """Create a mock coaching report for testing."""
    return CoachingReport(
        summary="Great session with solid consistency. Focus on T3 braking.",
        priority_corners=[
            {
                "corner": 3,
                "time_cost_s": 0.45,
                "issue": "Late braking causing entry overshoot",
                "tip": "Brake 10m earlier and trail in",
            },
        ],
        corner_grades=[
            CornerGrade(
                corner=1,
                braking="A",
                trail_braking="B",
                min_speed="A",
                throttle="A",
                notes="Consistent braking and apex speed across all laps.",
            ),
            CornerGrade(
                corner=3,
                braking="C",
                trail_braking="D",
                min_speed="B",
                throttle="C",
                notes="Brake point varies by 15m between laps.",
            ),
        ],
        patterns=[
            "Lap times improved through first 3 laps, then plateaued",
        ],
        drills=[
            "Brake marker drill for T3: Pick a fixed cone and hit it 3 laps straight.",
        ],
        raw_response="mock response",
    )


@pytest.fixture(autouse=True)
def _clear_coaching() -> None:
    """Clear coaching store before each test."""
    clear_all_coaching()


@pytest.mark.asyncio
async def test_pdf_download_success(client: AsyncClient) -> None:
    """Upload CSV, generate coaching report (mocked), download PDF -> 200 with PDF content."""
    session_id = await _upload_session(client)

    # Generate a coaching report first
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=_mock_coaching_report(),
    ):
        resp = await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        assert resp.status_code == 200
        # Let the background task complete
        await asyncio.sleep(0.3)

    # Verify coaching report is ready
    resp = await client.get(f"/api/coaching/{session_id}/report")
    assert resp.json()["status"] == "ready"

    # Download PDF
    resp = await client.get(f"/api/coaching/{session_id}/report/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "content-disposition" in resp.headers
    assert "coaching-report-" in resp.headers["content-disposition"]
    assert resp.headers["content-disposition"].endswith('.pdf"')
    # PDF files start with %PDF
    assert resp.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_pdf_download_no_session(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report/pdf with unknown session_id returns 404."""
    resp = await client.get("/api/coaching/nonexistent-session/report/pdf")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pdf_download_no_report(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report/pdf with session but no coaching report returns 404."""
    session_id = await _upload_session(client)

    resp = await client.get(f"/api/coaching/{session_id}/report/pdf")
    assert resp.status_code == 404

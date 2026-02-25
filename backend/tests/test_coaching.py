"""Tests for coaching endpoints."""

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
            {
                "corner": 5,
                "time_cost_s": 0.22,
                "issue": "Early throttle application",
                "tip": "Wait for car rotation before throttle",
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
            "Braking is most consistent in slow corners",
        ],
        drills=[
            "Brake marker drill for T3: Pick a fixed cone and hit it 3 laps straight.",
            "Trail brake drill for T5: Slowly release brake after turn-in.",
        ],
        raw_response="mock response",
    )


@pytest.fixture(autouse=True)
def _clear_coaching() -> None:
    """Clear coaching store before each test."""
    clear_all_coaching()


@pytest.mark.asyncio
async def test_generate_report(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/report triggers generation, GET returns the report."""
    session_id = await _upload_session(client)

    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=_mock_coaching_report(),
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "generating"

        # Let the background task complete
        await asyncio.sleep(0.2)

    # GET should now return the completed report
    response = await client.get(f"/api/coaching/{session_id}/report")
    data = response.json()
    assert data["session_id"] == session_id
    assert data["status"] == "ready"
    assert data["summary"] is not None
    assert "consistency" in data["summary"].lower() or "session" in data["summary"].lower()
    assert len(data["priority_corners"]) == 2
    assert data["priority_corners"][0]["corner"] == 3
    assert len(data["corner_grades"]) == 2
    assert data["corner_grades"][0]["braking"] == "A"
    assert len(data["patterns"]) == 2
    assert len(data["drills"]) == 2


@pytest.mark.asyncio
async def test_generate_report_session_not_found(client: AsyncClient) -> None:
    """POST /api/coaching/{id}/report with nonexistent session returns 404."""
    response = await client.post(
        "/api/coaching/nonexistent/report",
        json={"skill_level": "intermediate"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_report_default_skill_level(client: AsyncClient) -> None:
    """POST with empty body uses default skill_level 'intermediate'."""
    session_id = await _upload_session(client)

    mock_report = _mock_coaching_report()
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=mock_report,
    ) as mock_gen:
        response = await client.post(
            f"/api/coaching/{session_id}/report",
            json={},
        )

    assert response.status_code == 200
    # The mock was called — verify skill_level passed
    call_kwargs = mock_gen.call_args
    assert call_kwargs.kwargs.get("skill_level") == "intermediate"


@pytest.mark.asyncio
async def test_get_report_after_generation(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report returns stored report after generation."""
    session_id = await _upload_session(client)

    # Generate first
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=_mock_coaching_report(),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        # Let the background task complete
        await asyncio.sleep(0.2)

    # Now GET should return the stored report
    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["status"] == "ready"
    assert data["summary"] is not None
    assert len(data["priority_corners"]) == 2
    assert len(data["corner_grades"]) == 2


@pytest.mark.asyncio
async def test_get_report_not_found(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report with no generated report returns 404."""
    session_id = await _upload_session(client)

    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_report_nonexistent_session(client: AsyncClient) -> None:
    """GET /api/coaching/{id}/report with nonexistent session returns 404."""
    response = await client.get("/api/coaching/nonexistent/report")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_report_with_advanced_skill(client: AsyncClient) -> None:
    """POST with skill_level='advanced' passes it to the coaching function."""
    session_id = await _upload_session(client)

    mock_report = _mock_coaching_report()
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=mock_report,
    ) as mock_gen:
        response = await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "advanced"},
        )

    assert response.status_code == 200
    call_kwargs = mock_gen.call_args
    assert call_kwargs.kwargs.get("skill_level") == "advanced"


@pytest.mark.asyncio
async def test_generate_report_returns_existing(client: AsyncClient) -> None:
    """POST returns existing report without regenerating when one exists."""
    session_id = await _upload_session(client)

    # Generate first report
    report1 = _mock_coaching_report()
    report1.summary = "First report summary"
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=report1,
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await asyncio.sleep(0.2)

    # Second POST should return existing report without regenerating
    response = await client.post(
        f"/api/coaching/{session_id}/report",
        json={"skill_level": "advanced"},
    )
    assert response.status_code == 200
    assert response.json()["summary"] == "First report summary"


@pytest.mark.asyncio
async def test_generate_report_retries_after_error(client: AsyncClient) -> None:
    """POST allows regeneration when previous report has status='error'."""
    session_id = await _upload_session(client)

    # First generation fails (API overloaded)
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        side_effect=Exception("API overloaded"),
    ):
        await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        await asyncio.sleep(0.2)

    # GET should show error status
    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.json()["status"] == "error"

    # Retry should trigger a new generation (not return the error)
    report = _mock_coaching_report()
    with patch(
        "cataclysm.coaching.generate_coaching_report",
        return_value=report,
    ):
        response = await client.post(
            f"/api/coaching/{session_id}/report",
            json={"skill_level": "intermediate"},
        )
        assert response.json()["status"] == "generating"
        await asyncio.sleep(0.2)

    # GET should now return the successful report
    response = await client.get(f"/api/coaching/{session_id}/report")
    assert response.json()["status"] == "ready"
    assert response.json()["summary"] is not None

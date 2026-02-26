"""Tests for session management endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.api.schemas.coaching import CoachingReportResponse
from backend.api.services.coaching_store import get_coaching_report, store_coaching_report
from backend.api.services.db_coaching_store import get_coaching_report_db
from backend.tests.conftest import _test_session_factory


@pytest.mark.asyncio
async def test_upload_valid_csv(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """POST /api/sessions/upload with valid CSV returns 200 with session_id."""
    response = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test_session.csv", synthetic_csv_bytes, "text/csv"))],
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["session_ids"]) == 1
    assert data["session_ids"][0]  # non-empty string


@pytest.mark.asyncio
async def test_upload_multiple_csvs(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """POST /api/sessions/upload with multiple files returns multiple session_ids."""
    response = await client.post(
        "/api/sessions/upload",
        files=[
            ("files", ("session_a.csv", synthetic_csv_bytes, "text/csv")),
            ("files", ("session_b.csv", synthetic_csv_bytes, "text/csv")),
        ],
    )
    assert response.status_code == 200
    data = response.json()
    # Same data yields same session_id because it's deterministic from filename+track+date
    # But different filenames produce different IDs
    assert len(data["session_ids"]) == 2


@pytest.mark.asyncio
async def test_upload_invalid_file(client: AsyncClient) -> None:
    """POST /api/sessions/upload with non-CSV data reports errors."""
    response = await client.post(
        "/api/sessions/upload",
        files=[("files", ("bad.csv", b"this is not a CSV", "text/csv"))],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_ids"] == []
    assert "error" in data["message"].lower()


@pytest.mark.asyncio
async def test_list_sessions_empty(client: AsyncClient) -> None:
    """GET /api/sessions/ on empty store returns empty list."""
    response = await client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_sessions_after_upload(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """GET /api/sessions/ after upload contains the uploaded session."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    response = await client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    ids = [item["session_id"] for item in data["items"]]
    assert session_id in ids


@pytest.mark.asyncio
async def test_get_session_by_id(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """GET /api/sessions/{id} returns session metadata."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    response = await client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["track_name"] == "Test Circuit"
    assert data["n_laps"] is not None
    assert data["best_lap_time_s"] is not None


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient) -> None:
    """GET /api/sessions/{id} with nonexistent ID returns 404."""
    response = await client.get("/api/sessions/nonexistent_id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_laps(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """GET /api/sessions/{id}/laps returns lap summaries."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    response = await client.get(f"/api/sessions/{session_id}/laps")
    assert response.status_code == 200
    laps = response.json()
    assert isinstance(laps, list)
    assert len(laps) >= 1
    first_lap = laps[0]
    assert "lap_number" in first_lap
    assert "lap_time_s" in first_lap
    assert "lap_distance_m" in first_lap
    assert "max_speed_mps" in first_lap
    assert "is_clean" in first_lap


@pytest.mark.asyncio
async def test_get_lap_data(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """GET /api/sessions/{id}/laps/{n}/data returns columnar telemetry."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    # Get available laps first
    laps_resp = await client.get(f"/api/sessions/{session_id}/laps")
    first_lap = laps_resp.json()[0]["lap_number"]

    response = await client.get(f"/api/sessions/{session_id}/laps/{first_lap}/data")
    assert response.status_code == 200
    data = response.json()
    assert data["lap_number"] == first_lap
    expected_keys = [
        "distance_m",
        "speed_mph",
        "lat",
        "lon",
        "heading_deg",
        "lateral_g",
        "longitudinal_g",
        "lap_time_s",
    ]
    for key in expected_keys:
        assert key in data, f"Missing key: {key}"
        assert isinstance(data[key], list), f"{key} should be a list"
        assert len(data[key]) > 0, f"{key} should not be empty"


@pytest.mark.asyncio
async def test_get_lap_data_includes_altitude(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """GET /api/sessions/{id}/laps/{n}/data includes altitude_m when available."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    laps_resp = await client.get(f"/api/sessions/{session_id}/laps")
    first_lap = laps_resp.json()[0]["lap_number"]

    response = await client.get(f"/api/sessions/{session_id}/laps/{first_lap}/data")
    assert response.status_code == 200
    data = response.json()
    # altitude_m is present since synthetic CSV includes altitude column
    assert "altitude_m" in data
    assert isinstance(data["altitude_m"], list)
    assert len(data["altitude_m"]) > 0


@pytest.mark.asyncio
async def test_get_lap_data_not_found(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """GET /api/sessions/{id}/laps/999/data returns 404 for nonexistent lap."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    response = await client.get(f"/api/sessions/{session_id}/laps/999/data")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """DELETE /api/sessions/{id} removes the session, then GET returns 404."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    del_resp = await client.delete(f"/api/sessions/{session_id}")
    assert del_resp.status_code == 200

    get_resp = await client.get(f"/api/sessions/{session_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_not_found(client: AsyncClient) -> None:
    """DELETE /api/sessions/{id} with nonexistent ID returns 404."""
    response = await client.delete("/api/sessions/nonexistent_id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_all_sessions(client: AsyncClient, synthetic_csv_bytes: bytes) -> None:
    """DELETE /api/sessions/all/clear removes all sessions."""
    # Upload two sessions
    await client.post(
        "/api/sessions/upload",
        files=[("files", ("a.csv", synthetic_csv_bytes, "text/csv"))],
    )
    await client.post(
        "/api/sessions/upload",
        files=[("files", ("b.csv", synthetic_csv_bytes, "text/csv"))],
    )

    del_resp = await client.delete("/api/sessions/all/clear")
    assert del_resp.status_code == 200

    list_resp = await client.get("/api/sessions")
    assert list_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_session_clears_coaching(
    client: AsyncClient, synthetic_csv_bytes: bytes
) -> None:
    """DELETE /api/sessions/{id} should also clear coaching from memory and DB."""
    upload_resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", synthetic_csv_bytes, "text/csv"))],
    )
    session_id = upload_resp.json()["session_ids"][0]

    # Manually store a coaching report for this session
    report = CoachingReportResponse(
        session_id=session_id,
        status="ready",
        summary="Test report for cascade delete.",
    )
    await store_coaching_report(session_id, report)

    # Verify coaching is stored
    assert await get_coaching_report(session_id) is not None

    # Delete the session
    del_resp = await client.delete(f"/api/sessions/{session_id}")
    assert del_resp.status_code == 200

    # Coaching should be gone from memory
    from backend.api.services.coaching_store import _reports

    assert session_id not in _reports

    # Coaching should be gone from DB (CASCADE from session delete + explicit clear)
    async with _test_session_factory() as db:
        assert await get_coaching_report_db(db, session_id) is None

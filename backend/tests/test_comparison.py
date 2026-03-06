"""Tests for multi-driver session comparison endpoint."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from cataclysm.engine import LapSummary
from fastapi import HTTPException
from httpx import AsyncClient

from backend.api.services.comparison import validate_session_comparison
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


def _make_session_stub(
    *,
    session_id: str,
    track_name: str,
    lap_distance_m: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        session_id=session_id,
        snapshot=SimpleNamespace(metadata=SimpleNamespace(track_name=track_name)),
        processed=SimpleNamespace(
            best_lap=1,
            lap_summaries=[
                LapSummary(
                    lap_number=1,
                    lap_time_s=90.0,
                    lap_distance_m=lap_distance_m,
                    max_speed_mps=40.0,
                )
            ],
        ),
    )


def test_validate_session_comparison_rejects_different_tracks() -> None:
    session_a = _make_session_stub(session_id="a", track_name="Barber", lap_distance_m=1000.0)
    session_b = _make_session_stub(session_id="b", track_name="Road Atlanta", lap_distance_m=1000.0)

    with pytest.raises(HTTPException) as exc_info:
        validate_session_comparison(session_a, session_b)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 400
    assert "same track" in str(exc_info.value.detail).lower()


def test_validate_session_comparison_rejects_layout_mismatch_on_same_track() -> None:
    session_a = _make_session_stub(
        session_id="a",
        track_name="Barber Motorsports Park",
        lap_distance_m=3800.0,
    )
    session_b = _make_session_stub(
        session_id="b",
        track_name="barber motorsports park",
        lap_distance_m=4200.0,
    )

    with pytest.raises(HTTPException) as exc_info:
        validate_session_comparison(session_a, session_b)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 400
    assert "layout" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_compare_two_sessions(client: AsyncClient) -> None:
    """GET /api/sessions/{a}/compare/{b} returns delta data for two valid sessions."""
    sid_a = await _upload_session(client, filename="session_a.csv")
    sid_b = await _upload_session(client, filename="session_b.csv")

    response = await client.get(f"/api/sessions/{sid_a}/compare/{sid_b}")
    assert response.status_code == 200

    data = response.json()
    assert data["session_a_id"] == sid_a
    assert data["session_b_id"] == sid_b
    assert data["session_a_track"] == "Test Circuit"
    assert data["session_b_track"] == "Test Circuit"
    assert isinstance(data["session_a_best_lap"], float)
    assert isinstance(data["session_b_best_lap"], float)
    assert isinstance(data["delta_s"], float)
    assert isinstance(data["distance_m"], list)
    assert isinstance(data["delta_time_s"], list)
    assert len(data["distance_m"]) == len(data["delta_time_s"])
    assert len(data["distance_m"]) > 0
    assert isinstance(data["corner_deltas"], list)

    # Validate corner delta schema if corners were detected
    for cd in data["corner_deltas"]:
        assert "corner_number" in cd
        assert "speed_diff_mph" in cd
        assert "a_min_speed_mph" in cd
        assert "b_min_speed_mph" in cd
        assert "entry_distance_m" in cd
        assert "exit_distance_m" in cd
        assert isinstance(cd["corner_number"], int)
        assert isinstance(cd["speed_diff_mph"], float)
        assert isinstance(cd["entry_distance_m"], float)
        assert isinstance(cd["exit_distance_m"], float)
        assert cd["entry_distance_m"] < cd["exit_distance_m"]


@pytest.mark.asyncio
async def test_compare_session_not_found(client: AsyncClient) -> None:
    """GET /api/sessions/{a}/compare/{b} returns 404 when session_id not found."""
    response = await client.get("/api/sessions/nonexistent-a/compare/nonexistent-b")
    assert response.status_code == 404
    assert "nonexistent-a" in response.json()["detail"]


@pytest.mark.asyncio
async def test_compare_other_session_not_found(client: AsyncClient) -> None:
    """GET /api/sessions/{a}/compare/{b} returns 404 when other_id not found."""
    sid_a = await _upload_session(client)

    response = await client.get(f"/api/sessions/{sid_a}/compare/nonexistent-b")
    assert response.status_code == 404
    assert "nonexistent-b" in response.json()["detail"]


@pytest.mark.asyncio
async def test_compare_sessions_rejects_different_tracks(client: AsyncClient) -> None:
    sid_a = await _upload_session(
        client,
        csv_bytes=build_synthetic_csv(track_name="Barber Motorsports Park", n_laps=5),
        filename="barber.csv",
    )
    sid_b = await _upload_session(
        client,
        csv_bytes=build_synthetic_csv(track_name="Road Atlanta", n_laps=5),
        filename="road-atlanta.csv",
    )

    response = await client.get(f"/api/sessions/{sid_a}/compare/{sid_b}")

    assert response.status_code == 400
    assert "same track" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_compare_sessions_rejects_layout_mismatch(client: AsyncClient) -> None:
    sid_a = await _upload_session(
        client,
        csv_bytes=build_synthetic_csv(
            track_name="Barber Motorsports Park",
            n_laps=5,
            points_per_lap=200,
        ),
        filename="layout-a.csv",
    )
    sid_b = await _upload_session(
        client,
        csv_bytes=build_synthetic_csv(
            track_name="Barber Motorsports Park",
            n_laps=5,
            points_per_lap=280,
        ),
        filename="layout-b.csv",
    )

    response = await client.get(f"/api/sessions/{sid_a}/compare/{sid_b}")

    assert response.status_code == 400
    assert "layout" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_compare_session_with_itself(client: AsyncClient) -> None:
    """Comparing a session to itself returns zero delta."""
    sid = await _upload_session(client)

    response = await client.get(f"/api/sessions/{sid}/compare/{sid}")
    assert response.status_code == 200

    data = response.json()
    assert data["session_a_id"] == sid
    assert data["session_b_id"] == sid
    assert data["delta_s"] == 0.0
    assert all(d == 0.0 for d in data["delta_time_s"])
    # Speed diffs should also be zero when comparing same session
    for cd in data["corner_deltas"]:
        assert cd["speed_diff_mph"] == 0.0

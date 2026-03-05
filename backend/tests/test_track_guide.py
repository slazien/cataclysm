"""Tests for the track guide endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.tests.conftest import build_synthetic_csv


async def _upload(client: AsyncClient, track_name: str = "Barber Motorsports Park") -> str:
    """Upload a synthetic session and return its session_id."""
    csv_bytes = build_synthetic_csv(track_name=track_name, n_laps=2)
    response = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", csv_bytes, "text/csv"))],
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["session_ids"]) == 1
    return str(data["session_ids"][0])


@pytest.mark.asyncio
async def test_track_guide_known_track(client: AsyncClient) -> None:
    """Known track returns full guide data with correct structure."""
    sid = await _upload(client, "Barber Motorsports Park")
    response = await client.get(f"/api/sessions/{sid}/track-guide")
    assert response.status_code == 200
    data = response.json()

    assert data["track_name"] == "Barber Motorsports Park"
    assert data["n_corners"] == 16
    assert data["length_m"] == pytest.approx(3662.4)
    assert data["elevation_range_m"] == pytest.approx(60.0)
    assert data["country"] == "US"

    # Corners
    assert len(data["corners"]) == 16
    c1 = data["corners"][0]
    assert c1["number"] == 1
    assert c1["direction"] == "left"
    assert c1["corner_type"] == "sweeper"

    # Key corners
    assert len(data["key_corners"]) > 0
    for kc in data["key_corners"]:
        assert kc["straight_after_m"] > 150

    # Peculiarities
    assert len(data["peculiarities"]) > 0
    descs = [p["description"] for p in data["peculiarities"]]
    assert any("blind" in d for d in descs)

    # Landmarks
    assert len(data["landmarks"]) > 0


@pytest.mark.asyncio
async def test_track_guide_unknown_track(client: AsyncClient) -> None:
    """Unknown track returns 404."""
    sid = await _upload(client, "Unknown Circuit")
    response = await client.get(f"/api/sessions/{sid}/track-guide")
    assert response.status_code == 404
    assert "not in database" in response.json()["detail"]


@pytest.mark.asyncio
async def test_track_guide_nonexistent_session(client: AsyncClient) -> None:
    """Nonexistent session returns 404."""
    response = await client.get("/api/sessions/nonexistent-id/track-guide")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_track_guide_amp(client: AsyncClient) -> None:
    """AMP Full alias resolves correctly."""
    sid = await _upload(client, "AMP Full")
    response = await client.get(f"/api/sessions/{sid}/track-guide")
    assert response.status_code == 200
    data = response.json()
    assert data["track_name"] == "Atlanta Motorsports Park"
    assert data["n_corners"] == 16


@pytest.mark.asyncio
async def test_track_guide_roebling(client: AsyncClient) -> None:
    """Roebling Road returns correct corner count."""
    sid = await _upload(client, "Roebling Road")
    response = await client.get(f"/api/sessions/{sid}/track-guide")
    assert response.status_code == 200
    data = response.json()
    assert data["track_name"] == "Roebling Road Raceway"
    assert data["n_corners"] == 9


@pytest.mark.asyncio
async def test_track_guide_landmarks_have_types(client: AsyncClient) -> None:
    """Landmarks include type information."""
    sid = await _upload(client, "Barber Motorsports Park")
    response = await client.get(f"/api/sessions/{sid}/track-guide")
    data = response.json()
    types = {lm["landmark_type"] for lm in data["landmarks"]}
    assert "brake_board" in types
    assert "structure" in types

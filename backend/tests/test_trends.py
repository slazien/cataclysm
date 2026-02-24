"""Tests for tracks and trends endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.tests.conftest import build_synthetic_csv


async def _upload_session(
    client: AsyncClient,
    filename: str = "test.csv",
    track_name: str = "Test Circuit",
    n_laps: int = 3,
) -> str:
    """Helper: upload a CSV and return the session_id."""
    csv_bytes = build_synthetic_csv(track_name=track_name, n_laps=n_laps)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", (filename, csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200
    session_id: str = resp.json()["session_ids"][0]
    return session_id


@pytest.mark.asyncio
async def test_list_track_folders(client: AsyncClient) -> None:
    """GET /api/tracks/ returns a list (may be empty if no data dir)."""
    response = await client.get("/api/tracks/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_trends_needs_two_sessions(client: AsyncClient) -> None:
    """GET /api/trends/{track} with 0 sessions returns 422."""
    response = await client.get("/api/trends/Test Circuit")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_trends_with_one_session(client: AsyncClient) -> None:
    """GET /api/trends/{track} with only 1 session returns 422."""
    await _upload_session(client, filename="s1.csv", track_name="Trend Track")
    response = await client.get("/api/trends/Trend Track")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_trends_with_two_sessions(client: AsyncClient) -> None:
    """GET /api/trends/{track} with 2+ sessions returns trend analysis."""
    await _upload_session(client, filename="s1.csv", track_name="Test Circuit")
    await _upload_session(client, filename="s2.csv", track_name="Test Circuit")

    response = await client.get("/api/trends/Test Circuit")
    assert response.status_code == 200
    data = response.json()
    assert data["track_name"] == "Test Circuit"
    assert "data" in data


@pytest.mark.asyncio
async def test_get_milestones_needs_two_sessions(client: AsyncClient) -> None:
    """GET /api/trends/{track}/milestones with <2 sessions returns 422."""
    response = await client.get("/api/trends/Test Circuit/milestones")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_milestones_with_sessions(client: AsyncClient) -> None:
    """GET /api/trends/{track}/milestones returns milestones list."""
    await _upload_session(client, filename="m1.csv", track_name="Test Circuit")
    await _upload_session(client, filename="m2.csv", track_name="Test Circuit")

    response = await client.get("/api/trends/Test Circuit/milestones")
    assert response.status_code == 200
    data = response.json()
    assert data["track_name"] == "Test Circuit"
    assert "milestones" in data
    assert isinstance(data["milestones"], list)

"""Tests for session sharing and comparison endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

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


@pytest.mark.asyncio
async def test_create_share_link(client: AsyncClient) -> None:
    """POST /api/sharing/create returns a share token and URL."""
    sid = await _upload_session(client)

    resp = await client.post(
        "/api/sharing/create",
        json={"session_id": sid},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["share_url"].startswith("/share/")
    assert data["track_name"] == "Test Circuit"
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_create_share_link_session_not_found(client: AsyncClient) -> None:
    """POST /api/sharing/create returns 404 for nonexistent session."""
    resp = await client.post(
        "/api/sharing/create",
        json={"session_id": "nonexistent"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_share_metadata(client: AsyncClient) -> None:
    """GET /api/sharing/{token} returns share metadata."""
    sid = await _upload_session(client)
    create_resp = await client.post(
        "/api/sharing/create",
        json={"session_id": sid},
    )
    token = create_resp.json()["token"]

    resp = await client.get(f"/api/sharing/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] == token
    assert data["track_name"] == "Test Circuit"
    assert data["is_expired"] is False
    assert "inviter_name" in data
    assert "best_lap_time_s" in data


@pytest.mark.asyncio
async def test_get_share_metadata_not_found(client: AsyncClient) -> None:
    """GET /api/sharing/{token} returns 404 for invalid token."""
    resp = await client.get("/api/sharing/nonexistent-token")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_to_share(client: AsyncClient) -> None:
    """POST /api/sharing/{token}/upload processes CSV and returns comparison."""
    sid = await _upload_session(client, filename="original.csv")
    create_resp = await client.post(
        "/api/sharing/create",
        json={"session_id": sid},
    )
    token = create_resp.json()["token"]

    # Upload a challenger CSV
    challenger_csv = build_synthetic_csv(n_laps=3)
    resp = await client.post(
        f"/api/sharing/{token}/upload",
        files=[("files", ("challenger.csv", challenger_csv, "text/csv"))],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] == token
    assert data["session_a_id"] == sid
    assert "session_b_id" in data
    assert isinstance(data["delta_s"], float)
    assert isinstance(data["distance_m"], list)
    assert isinstance(data["delta_time_s"], list)
    assert len(data["distance_m"]) > 0


@pytest.mark.asyncio
async def test_upload_to_share_not_found(client: AsyncClient) -> None:
    """POST /api/sharing/{token}/upload returns 404 for invalid token."""
    csv_bytes = build_synthetic_csv(n_laps=2)
    resp = await client.post(
        "/api/sharing/nonexistent-token/upload",
        files=[("files", ("test.csv", csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_to_share_no_files(client: AsyncClient) -> None:
    """POST /api/sharing/{token}/upload returns 400 when no files are uploaded."""
    sid = await _upload_session(client)
    create_resp = await client.post(
        "/api/sharing/create",
        json={"session_id": sid},
    )
    token = create_resp.json()["token"]

    # Upload with empty files list - use the query parameter approach
    resp = await client.post(f"/api/sharing/{token}/upload")
    # FastAPI returns 422 when required field 'files' is missing
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_share_comparison(client: AsyncClient) -> None:
    """GET /api/sharing/{token}/comparison returns last comparison."""
    sid = await _upload_session(client, filename="original.csv")
    create_resp = await client.post(
        "/api/sharing/create",
        json={"session_id": sid},
    )
    token = create_resp.json()["token"]

    # First upload to create a comparison
    challenger_csv = build_synthetic_csv(n_laps=3)
    upload_resp = await client.post(
        f"/api/sharing/{token}/upload",
        files=[("files", ("challenger.csv", challenger_csv, "text/csv"))],
    )
    assert upload_resp.status_code == 200

    # Now fetch the comparison
    resp = await client.get(f"/api/sharing/{token}/comparison")
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] == token
    assert data["session_a_id"] == sid
    assert isinstance(data["delta_s"], float)


@pytest.mark.asyncio
async def test_get_share_comparison_not_available(client: AsyncClient) -> None:
    """GET /api/sharing/{token}/comparison returns 404 if no upload yet."""
    sid = await _upload_session(client)
    create_resp = await client.post(
        "/api/sharing/create",
        json={"session_id": sid},
    )
    token = create_resp.json()["token"]

    resp = await client.get(f"/api/sharing/{token}/comparison")
    assert resp.status_code == 404

"""Tests for the notes CRUD API."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient

from backend.api.db.models import Session as SessionModel


@pytest_asyncio.fixture
async def seed_session(_test_db: None) -> str:
    """Seed a session row so FK constraints pass for session-scoped notes."""
    from backend.tests.conftest import _test_session_factory

    session_id = "test-session-for-notes"
    async with _test_session_factory() as db:
        db.add(
            SessionModel(
                session_id=session_id,
                user_id="test-user-123",
                track_name="Test Circuit",
                session_date=datetime.now(tz=UTC),
                file_key=session_id,
            )
        )
        await db.commit()
    return session_id


@pytest.mark.asyncio
async def test_create_note(client: AsyncClient) -> None:
    """Create a simple session note."""
    resp = await client.post(
        "/api/notes",
        json={"content": "Late braking into @T5", "session_id": None, "color": "yellow"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Late braking into @T5"
    assert data["color"] == "yellow"
    assert data["is_pinned"] is False
    assert data["id"]


@pytest.mark.asyncio
async def test_create_note_with_anchor(client: AsyncClient) -> None:
    """Create a note anchored to a corner."""
    resp = await client.post(
        "/api/notes",
        json={
            "content": "Apex speed too low here",
            "anchor_type": "corner",
            "anchor_id": "T5",
            "anchor_meta": {"corner_number": 5},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["anchor_type"] == "corner"
    assert data["anchor_id"] == "T5"
    assert data["anchor_meta"] == {"corner_number": 5}


@pytest.mark.asyncio
async def test_create_note_invalid_anchor_type(client: AsyncClient) -> None:
    """Invalid anchor_type returns 422."""
    resp = await client.post(
        "/api/notes",
        json={"content": "Test", "anchor_type": "invalid"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_note_invalid_color(client: AsyncClient) -> None:
    """Invalid color returns 422."""
    resp = await client.post(
        "/api/notes",
        json={"content": "Test", "color": "red"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_note_empty_content(client: AsyncClient) -> None:
    """Empty content returns 422."""
    resp = await client.post("/api/notes", json={"content": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_notes_empty(client: AsyncClient) -> None:
    """Empty list when no notes exist."""
    resp = await client.get("/api/notes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_notes(client: AsyncClient) -> None:
    """List returns created notes."""
    await client.post("/api/notes", json={"content": "Note 1"})
    await client.post("/api/notes", json={"content": "Note 2"})
    resp = await client.get("/api/notes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_notes_global_only(client: AsyncClient, seed_session: str) -> None:
    """global_only=true filters out session-scoped notes."""
    await client.post("/api/notes", json={"content": "Global note"})
    await client.post("/api/notes", json={"content": "Session note", "session_id": seed_session})
    resp = await client.get("/api/notes", params={"global_only": "true"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["content"] == "Global note"


@pytest.mark.asyncio
async def test_list_notes_by_anchor_type(client: AsyncClient) -> None:
    """Filter by anchor_type."""
    await client.post(
        "/api/notes",
        json={"content": "Corner note", "anchor_type": "corner", "anchor_id": "T1"},
    )
    await client.post(
        "/api/notes",
        json={"content": "Lap note", "anchor_type": "lap", "anchor_id": "7"},
    )
    resp = await client.get("/api/notes", params={"anchor_type": "corner"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["anchor_type"] == "corner"


@pytest.mark.asyncio
async def test_get_note(client: AsyncClient) -> None:
    """Get a single note by ID."""
    create_resp = await client.post("/api/notes", json={"content": "Test note"})
    note_id = create_resp.json()["id"]
    resp = await client.get(f"/api/notes/{note_id}")
    assert resp.status_code == 200
    assert resp.json()["content"] == "Test note"


@pytest.mark.asyncio
async def test_get_note_not_found(client: AsyncClient) -> None:
    """404 for non-existent note."""
    resp = await client.get("/api/notes/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_note(client: AsyncClient) -> None:
    """Partial update of a note."""
    create_resp = await client.post("/api/notes", json={"content": "Original"})
    note_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/notes/{note_id}",
        json={"content": "Updated", "is_pinned": True, "color": "blue"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Updated"
    assert data["is_pinned"] is True
    assert data["color"] == "blue"


@pytest.mark.asyncio
async def test_update_note_partial(client: AsyncClient) -> None:
    """Update only content, leaving other fields unchanged."""
    create_resp = await client.post("/api/notes", json={"content": "Original", "color": "green"})
    note_id = create_resp.json()["id"]
    resp = await client.patch(f"/api/notes/{note_id}", json={"content": "New content"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "New content"
    assert data["color"] == "green"


@pytest.mark.asyncio
async def test_delete_note(client: AsyncClient) -> None:
    """Delete a note."""
    create_resp = await client.post("/api/notes", json={"content": "To delete"})
    note_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/notes/{note_id}")
    assert resp.status_code == 204
    # Verify it's gone
    get_resp = await client.get(f"/api/notes/{note_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_note_not_found(client: AsyncClient) -> None:
    """404 when deleting non-existent note."""
    resp = await client.delete("/api/notes/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pinned_notes_first(client: AsyncClient) -> None:
    """Pinned notes appear before unpinned in listing."""
    await client.post("/api/notes", json={"content": "Unpinned"})
    await client.post("/api/notes", json={"content": "Pinned", "is_pinned": True})
    resp = await client.get("/api/notes")
    items = resp.json()["items"]
    assert items[0]["content"] == "Pinned"
    assert items[1]["content"] == "Unpinned"

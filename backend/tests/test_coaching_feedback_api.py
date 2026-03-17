"""API-level tests for coaching feedback PUT/GET endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.api.services.session_store import clear_all


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an async HTTP test client wired to the FastAPI app."""
    clear_all()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    clear_all()


class TestSubmitFeedback:
    @pytest.mark.asyncio
    async def test_thumbs_up(self, client: AsyncClient) -> None:
        """PUT feedback with rating=1 returns 200 and rating=1."""
        resp = await client.put(
            "/api/coaching/feedback",
            json={
                "session_id": "sess-1",
                "section": "summary",
                "rating": 1,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-1"
        assert data["section"] == "summary"
        assert data["rating"] == 1
        assert data["comment"] is None

    @pytest.mark.asyncio
    async def test_thumbs_down_with_comment(self, client: AsyncClient) -> None:
        """PUT feedback with rating=-1 and a comment."""
        resp = await client.put(
            "/api/coaching/feedback",
            json={
                "session_id": "sess-1",
                "section": "patterns",
                "rating": -1,
                "comment": "Advice was wrong",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rating"] == -1
        assert data["comment"] == "Advice was wrong"

    @pytest.mark.asyncio
    async def test_toggle_replaces_existing(self, client: AsyncClient) -> None:
        """Submitting feedback for the same section replaces the old entry."""
        await client.put(
            "/api/coaching/feedback",
            json={"session_id": "sess-1", "section": "summary", "rating": 1},
        )
        resp = await client.put(
            "/api/coaching/feedback",
            json={"session_id": "sess-1", "section": "summary", "rating": -1},
        )
        assert resp.status_code == 200
        assert resp.json()["rating"] == -1

        # Verify only one entry exists via GET
        get_resp = await client.get("/api/coaching/sess-1/feedback")
        assert get_resp.status_code == 200
        feedback = get_resp.json()["feedback"]
        assert len(feedback) == 1
        assert feedback[0]["rating"] == -1

    @pytest.mark.asyncio
    async def test_rating_zero_removes_feedback(self, client: AsyncClient) -> None:
        """Rating=0 deletes existing feedback for that section."""
        # First submit a thumbs up
        await client.put(
            "/api/coaching/feedback",
            json={"session_id": "sess-1", "section": "summary", "rating": 1},
        )
        # Now remove it
        resp = await client.put(
            "/api/coaching/feedback",
            json={"session_id": "sess-1", "section": "summary", "rating": 0},
        )
        assert resp.status_code == 200
        assert resp.json()["rating"] == 0

        # Verify it was actually removed
        get_resp = await client.get("/api/coaching/sess-1/feedback")
        assert get_resp.status_code == 200
        assert get_resp.json()["feedback"] == []

    @pytest.mark.asyncio
    async def test_invalid_rating_rejected(self, client: AsyncClient) -> None:
        """Rating values outside {-1, 0, 1} return 422."""
        resp = await client.put(
            "/api/coaching/feedback",
            json={"session_id": "sess-1", "section": "summary", "rating": 5},
        )
        assert resp.status_code == 422


class TestGetFeedback:
    @pytest.mark.asyncio
    async def test_empty_session(self, client: AsyncClient) -> None:
        """GET feedback for a session with no feedback returns empty list."""
        resp = await client.get("/api/coaching/no-feedback/feedback")
        assert resp.status_code == 200
        assert resp.json()["feedback"] == []

    @pytest.mark.asyncio
    async def test_returns_all_sections(self, client: AsyncClient) -> None:
        """GET returns feedback across all sections for the session."""
        await client.put(
            "/api/coaching/feedback",
            json={"session_id": "sess-2", "section": "summary", "rating": 1},
        )
        await client.put(
            "/api/coaching/feedback",
            json={
                "session_id": "sess-2",
                "section": "corner_5",
                "rating": -1,
                "comment": "Not helpful",
            },
        )
        await client.put(
            "/api/coaching/feedback",
            json={"session_id": "sess-2", "section": "drills", "rating": 1},
        )

        resp = await client.get("/api/coaching/sess-2/feedback")
        assert resp.status_code == 200
        feedback = resp.json()["feedback"]
        assert len(feedback) == 3

        sections = {f["section"] for f in feedback}
        assert sections == {"summary", "corner_5", "drills"}

    @pytest.mark.asyncio
    async def test_isolated_per_session(self, client: AsyncClient) -> None:
        """Feedback from one session does not leak into another."""
        await client.put(
            "/api/coaching/feedback",
            json={"session_id": "sess-a", "section": "summary", "rating": 1},
        )
        await client.put(
            "/api/coaching/feedback",
            json={"session_id": "sess-b", "section": "summary", "rating": -1},
        )

        resp_a = await client.get("/api/coaching/sess-a/feedback")
        resp_b = await client.get("/api/coaching/sess-b/feedback")

        assert len(resp_a.json()["feedback"]) == 1
        assert resp_a.json()["feedback"][0]["rating"] == 1

        assert len(resp_b.json()["feedback"]) == 1
        assert resp_b.json()["feedback"][0]["rating"] == -1

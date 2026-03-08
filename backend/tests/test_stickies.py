"""Tests for the stickies CRUD API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.main import app


@pytest.fixture()
def sticky_payload() -> dict:
    return {
        "pos_x": 0.75,
        "pos_y": 0.15,
        "content": "Check braking point",
        "tone": "amber",
        "collapsed": True,
        "view_scope": "report",
    }


class TestCreateSticky:
    async def test_create_minimal(self, client: AsyncClient) -> None:
        resp = await client.post("/api/stickies", json={"pos_x": 0.5, "pos_y": 0.5})
        assert resp.status_code == 201
        data = resp.json()
        assert data["pos_x"] == 0.5
        assert data["pos_y"] == 0.5
        assert data["content"] == ""
        assert data["tone"] == "amber"
        assert data["collapsed"] is True
        assert data["view_scope"] == "global"
        assert "user_id" in data

    async def test_create_full(self, client: AsyncClient, sticky_payload: dict) -> None:
        resp = await client.post("/api/stickies", json=sticky_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "Check braking point"
        assert data["tone"] == "amber"
        assert data["view_scope"] == "report"

    async def test_invalid_tone(self, client: AsyncClient) -> None:
        resp = await client.post("/api/stickies", json={"pos_x": 0.5, "pos_y": 0.5, "tone": "neon"})
        assert resp.status_code == 422

    async def test_invalid_view_scope(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/stickies",
            json={"pos_x": 0.5, "pos_y": 0.5, "view_scope": "invalid"},
        )
        assert resp.status_code == 422

    async def test_pos_out_of_range(self, client: AsyncClient) -> None:
        resp = await client.post("/api/stickies", json={"pos_x": 1.5, "pos_y": 0.5})
        assert resp.status_code == 422

    async def test_pos_negative(self, client: AsyncClient) -> None:
        resp = await client.post("/api/stickies", json={"pos_x": -0.1, "pos_y": 0.5})
        assert resp.status_code == 422


class TestListStickies:
    async def test_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/stickies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_own_stickies(self, client: AsyncClient, sticky_payload: dict) -> None:
        await client.post("/api/stickies", json=sticky_payload)
        await client.post(
            "/api/stickies",
            json={**sticky_payload, "view_scope": "deep-dive", "tone": "sky"},
        )
        resp = await client.get("/api/stickies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    async def test_filter_by_view_scope(self, client: AsyncClient, sticky_payload: dict) -> None:
        await client.post("/api/stickies", json=sticky_payload)  # report
        await client.post("/api/stickies", json={**sticky_payload, "view_scope": "deep-dive"})
        resp = await client.get("/api/stickies?view_scope=report")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["view_scope"] == "report"


class TestUpdateSticky:
    async def test_move(self, client: AsyncClient, sticky_payload: dict) -> None:
        create = await client.post("/api/stickies", json=sticky_payload)
        sid = create.json()["id"]

        resp = await client.patch(f"/api/stickies/{sid}", json={"pos_x": 0.1, "pos_y": 0.9})
        assert resp.status_code == 200
        assert resp.json()["pos_x"] == 0.1
        assert resp.json()["pos_y"] == 0.9

    async def test_update_content(self, client: AsyncClient, sticky_payload: dict) -> None:
        create = await client.post("/api/stickies", json=sticky_payload)
        sid = create.json()["id"]

        resp = await client.patch(f"/api/stickies/{sid}", json={"content": "Updated note"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated note"

    async def test_change_tone(self, client: AsyncClient, sticky_payload: dict) -> None:
        create = await client.post("/api/stickies", json=sticky_payload)
        sid = create.json()["id"]

        resp = await client.patch(f"/api/stickies/{sid}", json={"tone": "violet"})
        assert resp.status_code == 200
        assert resp.json()["tone"] == "violet"

    async def test_not_found(self, client: AsyncClient) -> None:
        resp = await client.patch("/api/stickies/nonexistent", json={"content": "x"})
        assert resp.status_code == 404

    async def test_invalid_tone_update(self, client: AsyncClient, sticky_payload: dict) -> None:
        create = await client.post("/api/stickies", json=sticky_payload)
        sid = create.json()["id"]
        resp = await client.patch(f"/api/stickies/{sid}", json={"tone": "neon"})
        assert resp.status_code == 422


class TestDeleteSticky:
    async def test_delete(self, client: AsyncClient, sticky_payload: dict) -> None:
        create = await client.post("/api/stickies", json=sticky_payload)
        sid = create.json()["id"]

        resp = await client.delete(f"/api/stickies/{sid}")
        assert resp.status_code == 204

        # Verify it's gone
        list_resp = await client.get("/api/stickies")
        assert list_resp.json()["total"] == 0

    async def test_delete_not_found(self, client: AsyncClient) -> None:
        resp = await client.delete("/api/stickies/nonexistent")
        assert resp.status_code == 404


class TestUserIsolation:
    """Verify that user A cannot access user B's stickies."""

    async def test_other_user_cannot_read(self, client: AsyncClient, sticky_payload: dict) -> None:
        # Create as default test user
        create = await client.post("/api/stickies", json=sticky_payload)
        assert create.status_code == 201

        # Switch to a different user
        other = AuthenticatedUser(user_id="other-user", email="other@test.com", name="Other")
        app.dependency_overrides[get_current_user] = lambda: other
        try:
            resp = await client.get("/api/stickies")
            assert resp.json()["total"] == 0
        finally:
            # Restore original user
            app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
                user_id="test-user-123", email="test@example.com", name="Test Driver"
            )

    async def test_other_user_cannot_update(
        self, client: AsyncClient, sticky_payload: dict
    ) -> None:
        create = await client.post("/api/stickies", json=sticky_payload)
        sid = create.json()["id"]

        other = AuthenticatedUser(user_id="other-user", email="other@test.com", name="Other")
        app.dependency_overrides[get_current_user] = lambda: other
        try:
            resp = await client.patch(f"/api/stickies/{sid}", json={"content": "hacked"})
            assert resp.status_code == 404
        finally:
            app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
                user_id="test-user-123", email="test@example.com", name="Test Driver"
            )

    async def test_other_user_cannot_delete(
        self, client: AsyncClient, sticky_payload: dict
    ) -> None:
        create = await client.post("/api/stickies", json=sticky_payload)
        sid = create.json()["id"]

        other = AuthenticatedUser(user_id="other-user", email="other@test.com", name="Other")
        app.dependency_overrides[get_current_user] = lambda: other
        try:
            resp = await client.delete(f"/api/stickies/{sid}")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
                user_id="test-user-123", email="test@example.com", name="Test Driver"
            )


class TestRateLimit:
    async def test_max_stickies_per_user(self, client: AsyncClient) -> None:
        """Creating more than 50 stickies returns 429."""
        for _ in range(50):
            resp = await client.post("/api/stickies", json={"pos_x": 0.5, "pos_y": 0.5})
            assert resp.status_code == 201

        resp = await client.post("/api/stickies", json={"pos_x": 0.5, "pos_y": 0.5})
        assert resp.status_code == 429


class TestViewScopeFilter:
    async def test_invalid_view_scope_query(self, client: AsyncClient) -> None:
        """Invalid view_scope query param returns 422."""
        resp = await client.get("/api/stickies?view_scope=invalid")
        assert resp.status_code == 422

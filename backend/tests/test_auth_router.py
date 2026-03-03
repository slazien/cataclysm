"""Tests for the auth router (/api/auth/me endpoints)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.api.db.models import User
from backend.tests.conftest import _TEST_USER, _test_session_factory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_user_with_skill(skill_level: str) -> None:
    """Update the test user's skill_level directly in the DB."""
    async with _test_session_factory() as db:
        user = await db.get(User, _TEST_USER.user_id)
        if user is not None:
            user.skill_level = skill_level
            await db.commit()


# ===========================================================================
# GET /api/auth/me — get_me
# ===========================================================================


class TestGetMe:
    """Tests for GET /api/auth/me."""

    @pytest.mark.asyncio
    async def test_get_me_creates_user_on_first_call(self, client: AsyncClient) -> None:
        """GET /api/auth/me for a user who is already seeded returns their profile.

        The conftest seeds the test user, so this verifies the existing-user
        branch (update mutable fields from JWT claims).
        """
        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == _TEST_USER.user_id
        assert data["email"] == _TEST_USER.email
        assert data["name"] == _TEST_USER.name

    @pytest.mark.asyncio
    async def test_get_me_returns_user_schema_fields(self, client: AsyncClient) -> None:
        """GET /api/auth/me response has all required UserSchema fields."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "name" in data
        assert "skill_level" in data
        # avatar_url may be null — just check key presence
        assert "avatar_url" in data

    @pytest.mark.asyncio
    async def test_get_me_creates_new_user_when_not_in_db(self, client: AsyncClient) -> None:
        """GET /api/auth/me for a user not yet in DB auto-creates the record."""
        # Remove the test user from the DB so the upsert path runs
        async with _test_session_factory() as db:
            user = await db.get(User, _TEST_USER.user_id)
            if user is not None:
                await db.delete(user)
                await db.commit()

        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == _TEST_USER.user_id
        assert data["email"] == _TEST_USER.email

    @pytest.mark.asyncio
    async def test_get_me_updates_name_and_email_from_claims(self, client: AsyncClient) -> None:
        """Calling GET /api/auth/me syncs name/email from the JWT claims to the DB."""
        # The _mock_auth fixture in conftest sets name="Test Driver"
        # Directly dirty the DB to a different name, then verify it gets corrected
        async with _test_session_factory() as db:
            user = await db.get(User, _TEST_USER.user_id)
            if user is not None:
                user.name = "Old Stale Name"
                await db.commit()

        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["name"] == _TEST_USER.name  # updated from JWT

    @pytest.mark.asyncio
    async def test_get_me_default_skill_level_is_intermediate(self, client: AsyncClient) -> None:
        """A newly created user has skill_level='intermediate' by default."""
        # Remove the test user so it gets created fresh
        async with _test_session_factory() as db:
            user = await db.get(User, _TEST_USER.user_id)
            if user is not None:
                await db.delete(user)
                await db.commit()

        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        # Default from the ORM model is "intermediate"
        assert response.json()["skill_level"] == "intermediate"


# ===========================================================================
# PATCH /api/auth/me — update_me
# ===========================================================================


class TestUpdateMe:
    """Tests for PATCH /api/auth/me."""

    @pytest.mark.asyncio
    async def test_patch_me_updates_skill_level_to_novice(self, client: AsyncClient) -> None:
        """PATCH /api/auth/me sets skill_level to 'novice'."""
        response = await client.patch("/api/auth/me", json={"skill_level": "novice"})
        assert response.status_code == 200
        assert response.json()["skill_level"] == "novice"

    @pytest.mark.asyncio
    async def test_patch_me_updates_skill_level_to_intermediate(self, client: AsyncClient) -> None:
        """PATCH /api/auth/me sets skill_level to 'intermediate'."""
        response = await client.patch("/api/auth/me", json={"skill_level": "intermediate"})
        assert response.status_code == 200
        assert response.json()["skill_level"] == "intermediate"

    @pytest.mark.asyncio
    async def test_patch_me_updates_skill_level_to_advanced(self, client: AsyncClient) -> None:
        """PATCH /api/auth/me sets skill_level to 'advanced'."""
        response = await client.patch("/api/auth/me", json={"skill_level": "advanced"})
        assert response.status_code == 200
        assert response.json()["skill_level"] == "advanced"

    @pytest.mark.asyncio
    async def test_patch_me_invalid_skill_level_returns_422(self, client: AsyncClient) -> None:
        """PATCH with an invalid skill_level returns 422."""
        response = await client.patch("/api/auth/me", json={"skill_level": "expert"})
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "invalid skill_level" in detail.lower()

    @pytest.mark.asyncio
    async def test_patch_me_invalid_skill_level_lists_valid_options(
        self, client: AsyncClient
    ) -> None:
        """Error message from invalid skill_level lists the valid options."""
        response = await client.patch("/api/auth/me", json={"skill_level": "pro"})
        assert response.status_code == 422
        detail = response.json()["detail"]
        # Error message must mention valid levels
        assert "advanced" in detail
        assert "intermediate" in detail
        assert "novice" in detail

    @pytest.mark.asyncio
    async def test_patch_me_null_skill_level_does_not_change(self, client: AsyncClient) -> None:
        """PATCH with skill_level=null leaves the existing value unchanged."""
        # First set to a known state
        await client.patch("/api/auth/me", json={"skill_level": "advanced"})

        # Then PATCH with null — should be a no-op
        response = await client.patch("/api/auth/me", json={"skill_level": None})
        assert response.status_code == 200
        assert response.json()["skill_level"] == "advanced"

    @pytest.mark.asyncio
    async def test_patch_me_user_not_found_returns_404(self, client: AsyncClient) -> None:
        """PATCH /api/auth/me when user doesn't exist in DB returns 404."""
        async with _test_session_factory() as db:
            user = await db.get(User, _TEST_USER.user_id)
            if user is not None:
                await db.delete(user)
                await db.commit()

        response = await client.patch("/api/auth/me", json={"skill_level": "novice"})
        assert response.status_code == 404
        assert "user not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_patch_me_returns_full_user_schema(self, client: AsyncClient) -> None:
        """PATCH /api/auth/me returns the full UserSchema (all required fields present)."""
        response = await client.patch("/api/auth/me", json={"skill_level": "intermediate"})
        assert response.status_code == 200
        data = response.json()
        required_keys = {"id", "email", "name", "skill_level"}
        assert required_keys.issubset(data.keys())

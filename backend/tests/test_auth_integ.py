"""Integration tests for the /api/auth router.

Uses the `client` fixture to exercise the actual router code through real HTTP
requests against an in-memory SQLite database.  No service functions are mocked.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.main import app

# ---------------------------------------------------------------------------
# Constants mirroring conftest.py seeded user
# ---------------------------------------------------------------------------

_TEST_USER_ID = "test-user-123"
_TEST_EMAIL = "test@example.com"
_TEST_NAME = "Test Driver"

# A user_id that is NOT seeded into the test database
_NEW_USER = AuthenticatedUser(
    user_id="new-user-999",
    email="new@test.com",
    name="New User",
    picture="http://pic.example.com/avatar.jpg",
)


# ---------------------------------------------------------------------------
# GET /api/auth/me — return existing user profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_returns_seeded_user(client: AsyncClient) -> None:
    """GET /api/auth/me returns the profile for the pre-seeded test user."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == _TEST_USER_ID
    assert data["email"] == _TEST_EMAIL
    assert data["name"] == _TEST_NAME


@pytest.mark.asyncio
async def test_get_me_response_shape(client: AsyncClient) -> None:
    """GET /api/auth/me response includes all expected UserSchema fields."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "email" in data
    assert "name" in data
    assert "skill_level" in data
    assert "created_at" in data  # may be None in SQLite but key must exist
    assert data["skill_level"] == "intermediate"  # default value


@pytest.mark.asyncio
async def test_get_me_updates_name_from_auth_claims(client: AsyncClient) -> None:
    """GET /api/auth/me overwrites the stored name with the latest JWT claim."""
    # Override auth with a user having the same user_id but a changed name
    updated_user = AuthenticatedUser(
        user_id=_TEST_USER_ID,
        email=_TEST_EMAIL,
        name="Updated Name",
    )
    app.dependency_overrides[get_current_user] = lambda: updated_user

    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"

    # Restore default override
    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


# ---------------------------------------------------------------------------
# GET /api/auth/me — auto-creates user on first login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_auto_creates_new_user(client: AsyncClient) -> None:
    """GET /api/auth/me creates a new user row when the user_id is unknown."""
    app.dependency_overrides[get_current_user] = lambda: _NEW_USER

    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "new-user-999"
    assert data["email"] == "new@test.com"
    assert data["name"] == "New User"

    # Restore
    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


@pytest.mark.asyncio
async def test_get_me_auto_create_stores_avatar_url(client: AsyncClient) -> None:
    """Auto-created user has avatar_url populated from the JWT picture claim."""
    app.dependency_overrides[get_current_user] = lambda: _NEW_USER

    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["avatar_url"] == "http://pic.example.com/avatar.jpg"

    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


@pytest.mark.asyncio
async def test_get_me_idempotent_second_call(client: AsyncClient) -> None:
    """Calling GET /api/auth/me twice for a new user does not create duplicates."""
    app.dependency_overrides[get_current_user] = lambda: _NEW_USER

    resp1 = await client.get("/api/auth/me")
    resp2 = await client.get("/api/auth/me")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Both calls return the same user_id — no duplicate-key error
    assert resp1.json()["id"] == resp2.json()["id"] == "new-user-999"

    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


# ---------------------------------------------------------------------------
# PATCH /api/auth/me — update skill_level
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_me_valid_skill_level(client: AsyncClient) -> None:
    """PATCH /api/auth/me with a valid skill_level persists the change."""
    for level in ("novice", "intermediate", "advanced"):
        resp = await client.patch("/api/auth/me", json={"skill_level": level})
        assert resp.status_code == 200, f"Failed for skill_level={level!r}"
        assert resp.json()["skill_level"] == level


@pytest.mark.asyncio
async def test_patch_me_invalid_skill_level_returns_422(client: AsyncClient) -> None:
    """PATCH /api/auth/me with an unrecognised skill_level returns 422."""
    resp = await client.patch("/api/auth/me", json={"skill_level": "expert"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "invalid skill_level" in detail.lower()


@pytest.mark.asyncio
async def test_patch_me_null_skill_level_is_noop(client: AsyncClient) -> None:
    """PATCH /api/auth/me with skill_level=null leaves the existing value unchanged."""
    # First set a known level
    await client.patch("/api/auth/me", json={"skill_level": "advanced"})

    # Now send null — should be a no-op
    resp = await client.patch("/api/auth/me", json={"skill_level": None})
    assert resp.status_code == 200
    assert resp.json()["skill_level"] == "advanced"


@pytest.mark.asyncio
async def test_patch_me_empty_body_returns_current_profile(client: AsyncClient) -> None:
    """PATCH /api/auth/me with an empty body returns the current profile unchanged."""
    resp = await client.patch("/api/auth/me", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == _TEST_USER_ID
    assert data["skill_level"] == "intermediate"  # untouched default

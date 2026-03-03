"""Integration tests for the /api/orgs router.

These tests use the `client` fixture to make real HTTP requests against the FastAPI
app wired to an in-memory SQLite database. No service-layer functions are mocked —
the full router → service → DB path is exercised.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORG_PAYLOAD = {
    "name": "Barber HPDE Club",
    "slug": "barber-hpde",
    "logo_url": "https://example.com/logo.png",
    "brand_color": "#FF0000",
}

_ORG_MINIMAL = {"name": "Minimal Club", "slug": "minimal-club"}

# The test user (seeded by _test_db fixture)
_TEST_USER_ID = "test-user-123"

# A second user seeded into the DB for permission tests
_OTHER_USER_ID = "other-user-456"
_OTHER_USER = AuthenticatedUser(
    user_id=_OTHER_USER_ID,
    email="other@example.com",
    name="Other Driver",
)


async def _seed_other_user(client: AsyncClient) -> None:
    """Seed the secondary user by hitting GET /api/auth/me while overriding auth.

    The auth /me endpoint auto-creates the user on first call.
    """
    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    app.dependency_overrides[get_current_user] = lambda: _OTHER_USER
    await client.get("/api/auth/me")
    # Restore to primary test user
    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


# ---------------------------------------------------------------------------
# POST /api/orgs — create org
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_org_returns_org_summary(client: AsyncClient) -> None:
    """Creating an org returns 200 with the org summary including id, name, slug."""
    resp = await client.post("/api/orgs", json=_ORG_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Barber HPDE Club"
    assert data["slug"] == "barber-hpde"
    assert data["logo_url"] == "https://example.com/logo.png"
    assert data["brand_color"] == "#FF0000"
    assert data["member_count"] == 1  # creator is auto-added as owner
    assert "id" in data


@pytest.mark.asyncio
async def test_create_org_minimal_fields(client: AsyncClient) -> None:
    """Creating an org with only required fields (name, slug) succeeds."""
    resp = await client.post("/api/orgs", json=_ORG_MINIMAL)
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "minimal-club"
    assert data["logo_url"] is None
    assert data["brand_color"] is None


# ---------------------------------------------------------------------------
# GET /api/orgs — list user's orgs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_orgs_empty_initially(client: AsyncClient) -> None:
    """A fresh user has no orgs."""
    resp = await client.get("/api/orgs")
    assert resp.status_code == 200
    assert resp.json()["organizations"] == []


@pytest.mark.asyncio
async def test_list_orgs_shows_created_org(client: AsyncClient) -> None:
    """After creating an org, it appears in the list."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    resp = await client.get("/api/orgs")
    assert resp.status_code == 200
    orgs = resp.json()["organizations"]
    assert len(orgs) == 1
    assert orgs[0]["slug"] == "barber-hpde"


@pytest.mark.asyncio
async def test_list_orgs_shows_multiple_orgs(client: AsyncClient) -> None:
    """User who creates two orgs sees both in the list."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    await client.post("/api/orgs", json={"name": "Org B", "slug": "org-b"})
    resp = await client.get("/api/orgs")
    slugs = {o["slug"] for o in resp.json()["organizations"]}
    assert slugs == {"barber-hpde", "org-b"}


# ---------------------------------------------------------------------------
# GET /api/orgs/{slug} — get org by slug
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_org_by_slug_returns_summary(client: AsyncClient) -> None:
    """Fetching an existing org by slug returns its details."""
    create_resp = await client.post("/api/orgs", json=_ORG_PAYLOAD)
    org_id = create_resp.json()["id"]

    resp = await client.get("/api/orgs/barber-hpde")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == org_id
    assert data["name"] == "Barber HPDE Club"
    assert data["member_count"] >= 1


@pytest.mark.asyncio
async def test_get_org_by_slug_404_unknown(client: AsyncClient) -> None:
    """GET /api/orgs/{slug} returns 404 for non-existent slug."""
    resp = await client.get("/api/orgs/does-not-exist")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /api/orgs/{slug}/members — list members
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_members_owner_can_see_members(client: AsyncClient) -> None:
    """Org owner (test user) can list members; creator appears as owner."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    resp = await client.get("/api/orgs/barber-hpde/members")
    assert resp.status_code == 200
    members = resp.json()["members"]
    assert len(members) == 1
    assert members[0]["user_id"] == _TEST_USER_ID
    assert members[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_list_members_404_unknown_org(client: AsyncClient) -> None:
    """GET members on unknown org slug returns 404."""
    resp = await client.get("/api/orgs/no-such-org/members")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_members_403_non_member(client: AsyncClient) -> None:
    """A user who is not a member of the org gets 403 when listing members."""
    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    # Create org as the test user
    await client.post("/api/orgs", json=_ORG_PAYLOAD)

    # Seed and switch to other user
    await _seed_other_user(client)
    app.dependency_overrides[get_current_user] = lambda: _OTHER_USER

    resp = await client.get("/api/orgs/barber-hpde/members")
    assert resp.status_code == 403
    assert "not a member" in resp.json()["detail"].lower()

    # Restore
    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


# ---------------------------------------------------------------------------
# POST /api/orgs/{slug}/members — add member
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_member_succeeds(client: AsyncClient) -> None:
    """Owner can add another user as a student."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    await _seed_other_user(client)

    resp = await client.post(
        "/api/orgs/barber-hpde/members",
        json={"user_id": _OTHER_USER_ID, "role": "student"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "added"


@pytest.mark.asyncio
async def test_add_member_404_unknown_org(client: AsyncClient) -> None:
    """Adding a member to a non-existent org returns 404."""
    resp = await client.post(
        "/api/orgs/ghost-org/members",
        json={"user_id": _OTHER_USER_ID, "role": "student"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_member_403_non_owner(client: AsyncClient) -> None:
    """A student cannot add new members (403)."""
    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    await _seed_other_user(client)

    # Add other user as student
    await client.post(
        "/api/orgs/barber-hpde/members",
        json={"user_id": _OTHER_USER_ID, "role": "student"},
    )

    # Switch to other user and try to add a third user
    app.dependency_overrides[get_current_user] = lambda: _OTHER_USER
    resp = await client.post(
        "/api/orgs/barber-hpde/members",
        json={"user_id": "third-user-789", "role": "student"},
    )
    assert resp.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


@pytest.mark.asyncio
async def test_add_member_409_duplicate(client: AsyncClient) -> None:
    """Adding a user who is already a member returns 409 Conflict."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    await _seed_other_user(client)

    await client.post(
        "/api/orgs/barber-hpde/members",
        json={"user_id": _OTHER_USER_ID, "role": "student"},
    )
    # Second add — duplicate
    resp = await client.post(
        "/api/orgs/barber-hpde/members",
        json={"user_id": _OTHER_USER_ID, "role": "student"},
    )
    assert resp.status_code == 409
    assert "already a member" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# DELETE /api/orgs/{slug}/members/{user_id} — remove member
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_member_succeeds(client: AsyncClient) -> None:
    """Owner can remove a member."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    await _seed_other_user(client)

    await client.post(
        "/api/orgs/barber-hpde/members",
        json={"user_id": _OTHER_USER_ID, "role": "student"},
    )

    resp = await client.delete(f"/api/orgs/barber-hpde/members/{_OTHER_USER_ID}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "removed"


@pytest.mark.asyncio
async def test_remove_member_404_unknown_org(client: AsyncClient) -> None:
    """Removing from an unknown org returns 404."""
    resp = await client.delete("/api/orgs/ghost/members/some-user")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remove_member_403_non_owner(client: AsyncClient) -> None:
    """A student cannot remove members (403)."""
    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    await _seed_other_user(client)

    await client.post(
        "/api/orgs/barber-hpde/members",
        json={"user_id": _OTHER_USER_ID, "role": "student"},
    )

    # Switch to student, try to remove themselves
    app.dependency_overrides[get_current_user] = lambda: _OTHER_USER
    resp = await client.delete(f"/api/orgs/barber-hpde/members/{_OTHER_USER_ID}")
    assert resp.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


@pytest.mark.asyncio
async def test_remove_member_404_nonexistent_member(client: AsyncClient) -> None:
    """Removing a user_id that is not a member returns 404."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    resp = await client.delete("/api/orgs/barber-hpde/members/nobody")
    assert resp.status_code == 404
    assert "member not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/orgs/{slug}/events — create event
# ---------------------------------------------------------------------------

_EVENT_PAYLOAD = {
    "name": "Spring HPDE",
    "track_name": "Barber Motorsports Park",
    "event_date": "2026-04-15T08:00:00",
    "run_groups": ["novice", "intermediate"],
}


@pytest.mark.asyncio
async def test_create_event_succeeds(client: AsyncClient) -> None:
    """Owner can create an event; response includes id and org_id."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    resp = await client.post("/api/orgs/barber-hpde/events", json=_EVENT_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Spring HPDE"
    assert data["track_name"] == "Barber Motorsports Park"
    assert "id" in data
    assert "org_id" in data


@pytest.mark.asyncio
async def test_create_event_404_unknown_org(client: AsyncClient) -> None:
    """Creating an event on a non-existent org returns 404."""
    resp = await client.post("/api/orgs/ghost/events", json=_EVENT_PAYLOAD)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_event_403_non_owner(client: AsyncClient) -> None:
    """A student cannot create events (403)."""
    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    await _seed_other_user(client)

    await client.post(
        "/api/orgs/barber-hpde/members",
        json={"user_id": _OTHER_USER_ID, "role": "student"},
    )

    app.dependency_overrides[get_current_user] = lambda: _OTHER_USER
    resp = await client.post("/api/orgs/barber-hpde/events", json=_EVENT_PAYLOAD)
    assert resp.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


# ---------------------------------------------------------------------------
# GET /api/orgs/{slug}/events — list events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_events_empty_initially(client: AsyncClient) -> None:
    """Org owner sees empty event list when no events exist."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    resp = await client.get("/api/orgs/barber-hpde/events")
    assert resp.status_code == 200
    assert resp.json()["events"] == []


@pytest.mark.asyncio
async def test_list_events_shows_created_event(client: AsyncClient) -> None:
    """After creating an event it appears in the list."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    await client.post("/api/orgs/barber-hpde/events", json=_EVENT_PAYLOAD)
    resp = await client.get("/api/orgs/barber-hpde/events")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 1
    assert events[0]["name"] == "Spring HPDE"


@pytest.mark.asyncio
async def test_list_events_403_non_member(client: AsyncClient) -> None:
    """A non-member cannot list events (403)."""
    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    await _seed_other_user(client)

    app.dependency_overrides[get_current_user] = lambda: _OTHER_USER
    resp = await client.get("/api/orgs/barber-hpde/events")
    assert resp.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


# ---------------------------------------------------------------------------
# DELETE /api/orgs/{slug}/events/{event_id} — delete event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_event_succeeds(client: AsyncClient) -> None:
    """Owner can delete an event they created."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    create_resp = await client.post("/api/orgs/barber-hpde/events", json=_EVENT_PAYLOAD)
    event_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/orgs/barber-hpde/events/{event_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_delete_event_404_unknown_event(client: AsyncClient) -> None:
    """Deleting a non-existent event_id returns 404."""
    await client.post("/api/orgs", json=_ORG_PAYLOAD)
    resp = await client.delete("/api/orgs/barber-hpde/events/no-such-event")
    assert resp.status_code == 404
    assert "event not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_event_404_unknown_org(client: AsyncClient) -> None:
    """Deleting an event on an unknown org returns 404."""
    resp = await client.delete("/api/orgs/ghost/events/some-event")
    assert resp.status_code == 404

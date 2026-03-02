"""Tests for the organizations router endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.api.db.models import Organization, OrgMembership, User
from backend.tests.conftest import _TEST_USER, _test_session_factory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORG_SLUG = "test-club"
_ORG_NAME = "Test Club HPDE"


async def _seed_org(*, owner_id: str = _TEST_USER.user_id) -> str:
    """Insert an Organization row and return its ID.

    We go straight to the DB to avoid the auth layer in create_org.
    The org_id is deterministic enough for tests.
    """
    org_id = "org-test-01"
    async with _test_session_factory() as db:
        db.add(
            Organization(
                id=org_id,
                name=_ORG_NAME,
                slug=_ORG_SLUG,
                logo_url=None,
                brand_color=None,
            )
        )
        await db.flush()
        db.add(
            OrgMembership(
                org_id=org_id,
                user_id=owner_id,
                role="owner",
            )
        )
        await db.commit()
    return org_id


async def _seed_user(user_id: str, email: str, name: str) -> None:
    """Insert a secondary User row for membership tests."""
    async with _test_session_factory() as db:
        existing = await db.get(User, user_id)
        if existing is None:
            db.add(User(id=user_id, email=email, name=name))
            await db.commit()


# ===========================================================================
# POST /api/orgs — create_organization
# ===========================================================================


class TestCreateOrganization:
    """Tests for POST /api/orgs."""

    @pytest.mark.asyncio
    async def test_create_org_returns_org_summary(self, client: AsyncClient) -> None:
        """Creating a new org returns an OrgSummary with member_count=1."""
        response = await client.post(
            "/api/orgs",
            json={"name": "Speed Club", "slug": "speed-club"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Speed Club"
        assert data["slug"] == "speed-club"
        assert data["member_count"] == 1
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_org_with_optional_fields(self, client: AsyncClient) -> None:
        """Creating an org with logo_url and brand_color stores them."""
        response = await client.post(
            "/api/orgs",
            json={
                "name": "Fast Club",
                "slug": "fast-club",
                "logo_url": "https://example.com/logo.png",
                "brand_color": "#FF0000",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["logo_url"] == "https://example.com/logo.png"
        assert data["brand_color"] == "#FF0000"

    @pytest.mark.asyncio
    async def test_create_org_null_optional_fields(self, client: AsyncClient) -> None:
        """Creating an org without optional fields returns null for them."""
        response = await client.post(
            "/api/orgs",
            json={"name": "Plain Club", "slug": "plain-club"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["logo_url"] is None
        assert data["brand_color"] is None


# ===========================================================================
# GET /api/orgs — list_user_orgs
# ===========================================================================


class TestListUserOrgs:
    """Tests for GET /api/orgs."""

    @pytest.mark.asyncio
    async def test_list_orgs_empty_when_no_memberships(self, client: AsyncClient) -> None:
        """A user with no org memberships gets an empty list."""
        response = await client.get("/api/orgs")
        assert response.status_code == 200
        assert response.json()["organizations"] == []

    @pytest.mark.asyncio
    async def test_list_orgs_returns_joined_org(self, client: AsyncClient) -> None:
        """After creating an org, it appears in the user's org list."""
        # Create org via the API so the user is automatically owner
        await client.post(
            "/api/orgs",
            json={"name": "My Club", "slug": "my-club"},
        )
        response = await client.get("/api/orgs")
        assert response.status_code == 200
        orgs = response.json()["organizations"]
        assert len(orgs) == 1
        assert orgs[0]["slug"] == "my-club"

    @pytest.mark.asyncio
    async def test_list_orgs_returns_multiple_orgs(self, client: AsyncClient) -> None:
        """A user belonging to multiple orgs sees all of them."""
        await client.post("/api/orgs", json={"name": "Club A", "slug": "club-a"})
        await client.post("/api/orgs", json={"name": "Club B", "slug": "club-b"})
        response = await client.get("/api/orgs")
        assert response.status_code == 200
        slugs = {o["slug"] for o in response.json()["organizations"]}
        assert slugs == {"club-a", "club-b"}


# ===========================================================================
# GET /api/orgs/{slug} — get_organization
# ===========================================================================


class TestGetOrganization:
    """Tests for GET /api/orgs/{slug}."""

    @pytest.mark.asyncio
    async def test_get_org_by_slug(self, client: AsyncClient) -> None:
        """GET by valid slug returns the organization summary."""
        await _seed_org()
        response = await client.get(f"/api/orgs/{_ORG_SLUG}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == _ORG_NAME
        assert data["slug"] == _ORG_SLUG
        assert data["member_count"] == 1

    @pytest.mark.asyncio
    async def test_get_org_nonexistent_slug_returns_404(self, client: AsyncClient) -> None:
        """GET on a slug that doesn't exist returns 404."""
        response = await client.get("/api/orgs/no-such-org")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ===========================================================================
# GET /api/orgs/{slug}/members — list_members
# ===========================================================================


class TestListMembers:
    """Tests for GET /api/orgs/{slug}/members."""

    @pytest.mark.asyncio
    async def test_list_members_as_owner(self, client: AsyncClient) -> None:
        """An owner can list organization members."""
        await _seed_org()
        response = await client.get(f"/api/orgs/{_ORG_SLUG}/members")
        assert response.status_code == 200
        members = response.json()["members"]
        assert len(members) == 1
        assert members[0]["user_id"] == _TEST_USER.user_id
        assert members[0]["role"] == "owner"

    @pytest.mark.asyncio
    async def test_list_members_org_not_found_returns_404(self, client: AsyncClient) -> None:
        """Requesting members for a non-existent org returns 404."""
        response = await client.get("/api/orgs/ghost-org/members")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_members_non_member_returns_403(self, client: AsyncClient) -> None:
        """A user who is not a member gets a 403 when listing members."""
        other_owner = "other-owner-id"
        await _seed_user(other_owner, "other@example.com", "Other Owner")
        # Seed an org that the TEST_USER does NOT belong to
        org_id = "org-other-01"
        async with _test_session_factory() as db:
            db.add(Organization(id=org_id, name="Other Club", slug="other-club"))
            await db.flush()
            db.add(OrgMembership(org_id=org_id, user_id=other_owner, role="owner"))
            await db.commit()

        response = await client.get("/api/orgs/other-club/members")
        assert response.status_code == 403
        assert "not a member" in response.json()["detail"].lower()


# ===========================================================================
# POST /api/orgs/{slug}/members — add_org_member
# ===========================================================================


class TestAddOrgMember:
    """Tests for POST /api/orgs/{slug}/members."""

    @pytest.mark.asyncio
    async def test_add_member_as_owner_succeeds(self, client: AsyncClient) -> None:
        """An owner can add a new member to the organization."""
        await _seed_org()
        new_user_id = "new-member-001"
        await _seed_user(new_user_id, "newmember@example.com", "New Member")
        response = await client.post(
            f"/api/orgs/{_ORG_SLUG}/members",
            json={"user_id": new_user_id, "role": "student"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "added"}

    @pytest.mark.asyncio
    async def test_add_member_org_not_found_returns_404(self, client: AsyncClient) -> None:
        """Adding a member to a non-existent org returns 404."""
        response = await client.post(
            "/api/orgs/no-org/members",
            json={"user_id": "some-user", "role": "student"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_add_member_without_permission_returns_403(self, client: AsyncClient) -> None:
        """A student trying to add members gets a 403."""
        org_id = "org-student-01"
        async with _test_session_factory() as db:
            db.add(Organization(id=org_id, name="Student Club", slug="student-club"))
            await db.flush()
            # TEST_USER is only a student here
            db.add(
                OrgMembership(org_id=org_id, user_id=_TEST_USER.user_id, role="student")
            )
            await db.commit()

        response = await client.post(
            "/api/orgs/student-club/members",
            json={"user_id": "another-user", "role": "student"},
        )
        assert response.status_code == 403
        assert "insufficient permissions" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_add_member_duplicate_returns_409(self, client: AsyncClient) -> None:
        """Adding an already-existing member returns 409 Conflict."""
        await _seed_org()
        # TEST_USER is already the owner — attempting to add again triggers conflict
        response = await client.post(
            f"/api/orgs/{_ORG_SLUG}/members",
            json={"user_id": _TEST_USER.user_id, "role": "student"},
        )
        assert response.status_code == 409
        assert "already a member" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_add_member_with_run_group(self, client: AsyncClient) -> None:
        """Adding a member with a run group stores the group."""
        await _seed_org()
        new_user_id = "run-group-member"
        await _seed_user(new_user_id, "rungroup@example.com", "Run Group Driver")
        response = await client.post(
            f"/api/orgs/{_ORG_SLUG}/members",
            json={"user_id": new_user_id, "role": "student", "run_group": "Group B"},
        )
        assert response.status_code == 200
        # Verify membership is stored with run_group by listing members
        members_resp = await client.get(f"/api/orgs/{_ORG_SLUG}/members")
        members = members_resp.json()["members"]
        member = next((m for m in members if m["user_id"] == new_user_id), None)
        assert member is not None
        assert member["run_group"] == "Group B"


# ===========================================================================
# DELETE /api/orgs/{slug}/members/{user_id} — remove_org_member
# ===========================================================================


class TestRemoveOrgMember:
    """Tests for DELETE /api/orgs/{slug}/members/{user_id}."""

    @pytest.mark.asyncio
    async def test_remove_member_as_owner_succeeds(self, client: AsyncClient) -> None:
        """An owner can remove a member from the org."""
        await _seed_org()
        # First add a student member to remove
        student_id = "student-to-remove"
        await _seed_user(student_id, "student@example.com", "Student Driver")
        await client.post(
            f"/api/orgs/{_ORG_SLUG}/members",
            json={"user_id": student_id, "role": "student"},
        )
        response = await client.delete(f"/api/orgs/{_ORG_SLUG}/members/{student_id}")
        assert response.status_code == 200
        assert response.json() == {"status": "removed"}

    @pytest.mark.asyncio
    async def test_remove_member_org_not_found_returns_404(self, client: AsyncClient) -> None:
        """Removing a member from a non-existent org returns 404."""
        response = await client.delete("/api/orgs/ghost-org/members/some-user")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_remove_member_non_owner_returns_403(self, client: AsyncClient) -> None:
        """A non-owner (instructor) trying to remove members gets a 403."""
        org_id = "org-instructor-01"
        async with _test_session_factory() as db:
            db.add(Organization(id=org_id, name="Instr Club", slug="instr-club"))
            await db.flush()
            db.add(
                OrgMembership(org_id=org_id, user_id=_TEST_USER.user_id, role="instructor")
            )
            await db.commit()

        response = await client.delete(f"/api/orgs/instr-club/members/anyone")
        assert response.status_code == 403
        assert "only org owners" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_remove_member_not_in_org_returns_404(self, client: AsyncClient) -> None:
        """Trying to remove a user who is not a member returns 404."""
        await _seed_org()
        response = await client.delete(f"/api/orgs/{_ORG_SLUG}/members/nonexistent-user")
        assert response.status_code == 404
        assert "member not found" in response.json()["detail"].lower()


# ===========================================================================
# POST /api/orgs/{slug}/events — create_org_event
# ===========================================================================


class TestCreateOrgEvent:
    """Tests for POST /api/orgs/{slug}/events."""

    @pytest.mark.asyncio
    async def test_create_event_as_owner_succeeds(self, client: AsyncClient) -> None:
        """An owner can create an event and gets back an EventSchema."""
        await _seed_org()
        response = await client.post(
            f"/api/orgs/{_ORG_SLUG}/events",
            json={
                "name": "Spring HPDE",
                "track_name": "Barber Motorsports Park",
                "event_date": "2026-05-15T09:00:00",
                "run_groups": ["Novice", "Intermediate"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Spring HPDE"
        assert data["track_name"] == "Barber Motorsports Park"
        assert data["run_groups"] == ["Novice", "Intermediate"]
        assert "id" in data
        assert "org_id" in data

    @pytest.mark.asyncio
    async def test_create_event_org_not_found_returns_404(self, client: AsyncClient) -> None:
        """Creating an event for a non-existent org returns 404."""
        response = await client.post(
            "/api/orgs/no-org/events",
            json={
                "name": "Ghost Event",
                "track_name": "Unknown",
                "event_date": "2026-06-01T09:00:00",
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_event_without_permission_returns_403(
        self, client: AsyncClient
    ) -> None:
        """A student cannot create events."""
        org_id = "org-student-ev-01"
        async with _test_session_factory() as db:
            db.add(Organization(id=org_id, name="Student Ev Club", slug="student-ev-club"))
            await db.flush()
            db.add(
                OrgMembership(org_id=org_id, user_id=_TEST_USER.user_id, role="student")
            )
            await db.commit()

        response = await client.post(
            "/api/orgs/student-ev-club/events",
            json={
                "name": "Unauthorized Event",
                "track_name": "Barber",
                "event_date": "2026-07-01T09:00:00",
            },
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_event_without_run_groups(self, client: AsyncClient) -> None:
        """Creating an event with no run_groups stores null."""
        await _seed_org()
        response = await client.post(
            f"/api/orgs/{_ORG_SLUG}/events",
            json={
                "name": "Solo Event",
                "track_name": "Road America",
                "event_date": "2026-08-20T08:00:00",
            },
        )
        assert response.status_code == 200
        assert response.json()["run_groups"] is None


# ===========================================================================
# GET /api/orgs/{slug}/events — list_org_events
# ===========================================================================


class TestListOrgEvents:
    """Tests for GET /api/orgs/{slug}/events."""

    @pytest.mark.asyncio
    async def test_list_events_empty(self, client: AsyncClient) -> None:
        """An org with no events returns an empty list."""
        await _seed_org()
        response = await client.get(f"/api/orgs/{_ORG_SLUG}/events")
        assert response.status_code == 200
        assert response.json()["events"] == []

    @pytest.mark.asyncio
    async def test_list_events_returns_created_events(self, client: AsyncClient) -> None:
        """Created events appear in the list response."""
        await _seed_org()
        await client.post(
            f"/api/orgs/{_ORG_SLUG}/events",
            json={
                "name": "Fall HPDE",
                "track_name": "Road Atlanta",
                "event_date": "2026-09-01T08:00:00",
            },
        )
        response = await client.get(f"/api/orgs/{_ORG_SLUG}/events")
        assert response.status_code == 200
        events = response.json()["events"]
        assert len(events) == 1
        assert events[0]["name"] == "Fall HPDE"

    @pytest.mark.asyncio
    async def test_list_events_org_not_found_returns_404(self, client: AsyncClient) -> None:
        """Listing events for a non-existent org returns 404."""
        response = await client.get("/api/orgs/ghost-org/events")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_events_non_member_returns_403(self, client: AsyncClient) -> None:
        """A non-member cannot list events."""
        other_owner = "event-other-owner"
        await _seed_user(other_owner, "eventother@example.com", "Event Other Owner")
        org_id = "org-event-other"
        async with _test_session_factory() as db:
            db.add(Organization(id=org_id, name="Event Other Club", slug="event-other-club"))
            await db.flush()
            db.add(OrgMembership(org_id=org_id, user_id=other_owner, role="owner"))
            await db.commit()

        response = await client.get("/api/orgs/event-other-club/events")
        assert response.status_code == 403


# ===========================================================================
# DELETE /api/orgs/{slug}/events/{event_id} — delete_org_event
# ===========================================================================


class TestDeleteOrgEvent:
    """Tests for DELETE /api/orgs/{slug}/events/{event_id}."""

    @pytest.mark.asyncio
    async def test_delete_event_as_owner_succeeds(self, client: AsyncClient) -> None:
        """An owner can delete an event and gets {"status": "deleted"}."""
        await _seed_org()
        create_resp = await client.post(
            f"/api/orgs/{_ORG_SLUG}/events",
            json={
                "name": "Delete Me",
                "track_name": "VIR",
                "event_date": "2026-10-01T09:00:00",
            },
        )
        event_id = create_resp.json()["id"]

        response = await client.delete(f"/api/orgs/{_ORG_SLUG}/events/{event_id}")
        assert response.status_code == 200
        assert response.json() == {"status": "deleted"}

    @pytest.mark.asyncio
    async def test_delete_event_org_not_found_returns_404(self, client: AsyncClient) -> None:
        """Deleting from a non-existent org returns 404."""
        response = await client.delete("/api/orgs/no-org/events/ev-123")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_event_without_permission_returns_403(
        self, client: AsyncClient
    ) -> None:
        """A student cannot delete events."""
        org_id = "org-del-ev-01"
        async with _test_session_factory() as db:
            db.add(Organization(id=org_id, name="Del Ev Club", slug="del-ev-club"))
            await db.flush()
            db.add(
                OrgMembership(org_id=org_id, user_id=_TEST_USER.user_id, role="student")
            )
            await db.commit()

        response = await client.delete("/api/orgs/del-ev-club/events/some-event-id")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_event_not_found_returns_404(self, client: AsyncClient) -> None:
        """Deleting a non-existent event ID returns 404."""
        await _seed_org()
        response = await client.delete(f"/api/orgs/{_ORG_SLUG}/events/nonexistent-event")
        assert response.status_code == 404
        assert "event not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_event_as_instructor_succeeds(self, client: AsyncClient) -> None:
        """An instructor (not just owner) can also delete events."""
        org_id = "org-instr-del-01"
        async with _test_session_factory() as db:
            db.add(Organization(id=org_id, name="Instr Del Club", slug="instr-del-club"))
            await db.flush()
            db.add(
                OrgMembership(org_id=org_id, user_id=_TEST_USER.user_id, role="instructor")
            )
            await db.commit()

        create_resp = await client.post(
            "/api/orgs/instr-del-club/events",
            json={
                "name": "Instructor Event",
                "track_name": "Barber",
                "event_date": "2026-11-01T09:00:00",
            },
        )
        assert create_resp.status_code == 200
        event_id = create_resp.json()["id"]

        response = await client.delete(f"/api/orgs/instr-del-club/events/{event_id}")
        assert response.status_code == 200
        assert response.json() == {"status": "deleted"}

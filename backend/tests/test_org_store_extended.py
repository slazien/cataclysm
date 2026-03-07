"""Extended unit tests for backend.api.services.org_store.

Targets the missing coverage lines in org_store.py:
- 28-30: create_org body (db.add, flush, return)
- 36-45: get_org_by_slug — org found path, member_count query, return dict
- 62-79: get_user_orgs — loop body, member_count query, append
- 89-102: get_org_members — loop body, append dict
- 114-119: add_member — duplicate check, add OrgMembership, flush, return True
- 129-135: remove_member — found path, delete, flush, return True
- 145-146: check_org_role — role found, return bool
- 171: create_event — flush, return event_id
- 179-191: get_org_events — loop body, append dict
- 199-204: delete_event — found path, delete, flush, return True

Strategy: call the service functions directly using the test SQLite session.
"""

from __future__ import annotations

import pytest

from backend.api.db.models import Organization, OrgMembership, User
from backend.api.services import org_store
from backend.tests.conftest import _TEST_USER, _test_session_factory

# ---------------------------------------------------------------------------
# Shared seed helpers
# ---------------------------------------------------------------------------


async def _seed_org_direct(
    org_id: str = "os-org-01",
    slug: str = "os-club",
    owner_id: str = _TEST_USER.user_id,
) -> str:
    """Insert org + owner membership, return org_id."""
    async with _test_session_factory() as db:
        db.add(Organization(id=org_id, name="OS Club", slug=slug))
        await db.flush()
        db.add(OrgMembership(org_id=org_id, user_id=owner_id, role="owner"))
        await db.commit()
    return org_id


async def _seed_user(user_id: str, email: str, name: str) -> None:
    async with _test_session_factory() as db:
        existing = await db.get(User, user_id)
        if existing is None:
            db.add(User(id=user_id, email=email, name=name))
            await db.commit()


# ===========================================================================
# create_org (lines 28-30)
# ===========================================================================


class TestCreateOrg:
    """Direct unit tests for org_store.create_org."""

    @pytest.mark.asyncio
    async def test_create_org_returns_id(self) -> None:
        """create_org inserts an org + owner membership and returns a non-empty ID."""
        async with _test_session_factory() as db:
            org_id = await org_store.create_org(
                db,
                name="Direct Create Club",
                slug="direct-create-club",
                owner_id=_TEST_USER.user_id,
                logo_url=None,
                brand_color=None,
            )
            await db.commit()

        assert isinstance(org_id, str)
        assert len(org_id) > 0

    @pytest.mark.asyncio
    async def test_create_org_with_optional_fields(self) -> None:
        """create_org stores logo_url and brand_color correctly."""
        async with _test_session_factory() as db:
            await org_store.create_org(
                db,
                name="Branded Club",
                slug="branded-club",
                owner_id=_TEST_USER.user_id,
                logo_url="https://example.com/logo.png",
                brand_color="#ABCDEF",
            )
            await db.commit()

        # Verify by reading back
        async with _test_session_factory() as db:
            result = await org_store.get_org_by_slug(db, "branded-club")

        assert result is not None
        assert result["logo_url"] == "https://example.com/logo.png"
        assert result["brand_color"] == "#ABCDEF"
        assert result["member_count"] == 1

    @pytest.mark.asyncio
    async def test_create_org_owner_membership_is_added(self) -> None:
        """After create_org, the owner is counted as a member."""
        async with _test_session_factory() as db:
            org_id = await org_store.create_org(
                db,
                name="Membership Club",
                slug="membership-club",
                owner_id=_TEST_USER.user_id,
                logo_url=None,
                brand_color=None,
            )
            await db.commit()

        async with _test_session_factory() as db:
            result = await org_store.get_org_by_slug(db, "membership-club")

        assert result is not None
        assert result["member_count"] == 1
        assert result["id"] == org_id


# ===========================================================================
# get_org_by_slug (lines 36-52)
# ===========================================================================


class TestGetOrgBySlug:
    """Tests for org_store.get_org_by_slug."""

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_slug(self) -> None:
        """Returns None when the slug does not exist in the DB."""
        async with _test_session_factory() as db:
            result = await org_store.get_org_by_slug(db, "does-not-exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dict_with_all_fields(self) -> None:
        """Returns a dict with id, name, slug, logo_url, brand_color, member_count."""
        await _seed_org_direct(org_id="gobs-org-01", slug="gobs-club")

        async with _test_session_factory() as db:
            result = await org_store.get_org_by_slug(db, "gobs-club")

        assert result is not None
        assert result["slug"] == "gobs-club"
        assert result["name"] == "OS Club"
        assert result["logo_url"] is None
        assert result["brand_color"] is None
        assert result["member_count"] == 1
        assert "id" in result

    @pytest.mark.asyncio
    async def test_member_count_increments_after_add(self) -> None:
        """member_count reflects additional members added directly."""
        await _seed_org_direct(org_id="gobs-cnt-01", slug="gobs-cnt-club")
        second_user_id = "gobs-user-2"
        await _seed_user(second_user_id, "second@example.com", "Second User")

        async with _test_session_factory() as db:
            db.add(OrgMembership(org_id="gobs-cnt-01", user_id=second_user_id, role="student"))
            await db.commit()

        async with _test_session_factory() as db:
            result = await org_store.get_org_by_slug(db, "gobs-cnt-club")

        assert result is not None
        assert result["member_count"] == 2


# ===========================================================================
# get_user_orgs (lines 62-79)
# ===========================================================================


class TestGetUserOrgs:
    """Tests for org_store.get_user_orgs."""

    @pytest.mark.asyncio
    async def test_empty_list_when_no_memberships(self) -> None:
        """Returns empty list when the user has no memberships."""
        async with _test_session_factory() as db:
            result = await org_store.get_user_orgs(db, "nonexistent-user")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_user_orgs(self) -> None:
        """Returns all orgs for a user with memberships."""
        await _seed_org_direct(org_id="guo-org-01", slug="guo-club-a")

        async with _test_session_factory() as db:
            result = await org_store.get_user_orgs(db, _TEST_USER.user_id)

        slugs = [r["slug"] for r in result]
        assert "guo-club-a" in slugs

    @pytest.mark.asyncio
    async def test_returns_multiple_orgs(self) -> None:
        """get_user_orgs loops over all org memberships."""
        await _seed_org_direct(org_id="guo-org-x1", slug="guo-multi-a")

        async with _test_session_factory() as db:
            await org_store.create_org(
                db,
                name="Multi B",
                slug="guo-multi-b",
                owner_id=_TEST_USER.user_id,
                logo_url=None,
                brand_color=None,
            )
            await db.commit()

        async with _test_session_factory() as db:
            result = await org_store.get_user_orgs(db, _TEST_USER.user_id)

        slugs = {r["slug"] for r in result}
        assert "guo-multi-a" in slugs
        assert "guo-multi-b" in slugs

    @pytest.mark.asyncio
    async def test_returns_member_count_in_each_org(self) -> None:
        """Each dict in the returned list has a member_count field."""
        await _seed_org_direct(org_id="guo-cnt-01", slug="guo-cnt-club")

        async with _test_session_factory() as db:
            result = await org_store.get_user_orgs(db, _TEST_USER.user_id)

        matching = [r for r in result if r["slug"] == "guo-cnt-club"]
        assert len(matching) == 1
        assert matching[0]["member_count"] >= 1


# ===========================================================================
# get_org_members (lines 89-102)
# ===========================================================================


class TestGetOrgMembers:
    """Tests for org_store.get_org_members."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_unknown_org(self) -> None:
        """Returns empty list when org_id has no memberships."""
        async with _test_session_factory() as db:
            result = await org_store.get_org_members(db, "no-such-org")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_owner_member(self) -> None:
        """Returns dict with user_id, name, email, role, run_group, joined_at."""
        await _seed_org_direct(org_id="gom-org-01", slug="gom-club")

        async with _test_session_factory() as db:
            result = await org_store.get_org_members(db, "gom-org-01")

        assert len(result) == 1
        member = result[0]
        assert member["user_id"] == _TEST_USER.user_id
        assert member["role"] == "owner"
        assert "name" in member
        assert "email" in member
        assert "run_group" in member
        assert "joined_at" in member

    @pytest.mark.asyncio
    async def test_multiple_members_returned(self) -> None:
        """All members are returned when there are multiple."""
        await _seed_org_direct(org_id="gom-multi-01", slug="gom-multi-club")
        extra_user_id = "gom-extra-user"
        await _seed_user(extra_user_id, "extra@example.com", "Extra Driver")

        async with _test_session_factory() as db:
            await org_store.add_member(db, "gom-multi-01", extra_user_id, "student", "Group A")
            await db.commit()

        async with _test_session_factory() as db:
            result = await org_store.get_org_members(db, "gom-multi-01")

        assert len(result) == 2
        roles = {m["role"] for m in result}
        assert "owner" in roles
        assert "student" in roles

    @pytest.mark.asyncio
    async def test_run_group_is_present_in_member_dict(self) -> None:
        """run_group value is present in the returned member dict."""
        await _seed_org_direct(org_id="gom-rg-01", slug="gom-rg-club")
        rg_user_id = "gom-rg-user"
        await _seed_user(rg_user_id, "rg@example.com", "Run Group Driver")

        async with _test_session_factory() as db:
            await org_store.add_member(db, "gom-rg-01", rg_user_id, "student", "Novice")
            await db.commit()

        async with _test_session_factory() as db:
            result = await org_store.get_org_members(db, "gom-rg-01")

        rg_member = next(m for m in result if m["user_id"] == rg_user_id)
        assert rg_member["run_group"] == "Novice"


# ===========================================================================
# add_member (lines 114-119)
# ===========================================================================


class TestAddMember:
    """Tests for org_store.add_member."""

    @pytest.mark.asyncio
    async def test_add_new_member_returns_true(self) -> None:
        """Returns True when the user is successfully added."""
        await _seed_org_direct(org_id="am-org-01", slug="am-club")
        new_user = "am-new-user"
        await _seed_user(new_user, "amuser@example.com", "AM User")

        async with _test_session_factory() as db:
            result = await org_store.add_member(db, "am-org-01", new_user, "student", None)
            await db.commit()

        assert result is True

    @pytest.mark.asyncio
    async def test_add_duplicate_member_returns_false(self) -> None:
        """Returns False when the user is already a member (lines 114-115)."""
        await _seed_org_direct(org_id="am-dup-01", slug="am-dup-club")

        async with _test_session_factory() as db:
            result = await org_store.add_member(
                db, "am-dup-01", _TEST_USER.user_id, "instructor", None
            )
            await db.commit()

        assert result is False

    @pytest.mark.asyncio
    async def test_add_member_with_run_group(self) -> None:
        """Member is stored with the specified run_group (lines 117-119)."""
        await _seed_org_direct(org_id="am-rg-01", slug="am-rg-club")
        rg_user = "am-rg-user"
        await _seed_user(rg_user, "amrg@example.com", "RG User")

        async with _test_session_factory() as db:
            await org_store.add_member(db, "am-rg-01", rg_user, "student", "Intermediate")
            await db.commit()

        async with _test_session_factory() as db:
            members = await org_store.get_org_members(db, "am-rg-01")

        added = next(m for m in members if m["user_id"] == rg_user)
        assert added["run_group"] == "Intermediate"


# ===========================================================================
# remove_member (lines 129-135)
# ===========================================================================


class TestRemoveMember:
    """Tests for org_store.remove_member."""

    @pytest.mark.asyncio
    async def test_remove_existing_member_returns_true(self) -> None:
        """Returns True when the member was found and deleted (lines 133-135)."""
        await _seed_org_direct(org_id="rm-org-01", slug="rm-club")
        rm_user = "rm-user-to-remove"
        await _seed_user(rm_user, "rm@example.com", "Remove Me")

        async with _test_session_factory() as db:
            await org_store.add_member(db, "rm-org-01", rm_user, "student", None)
            await db.commit()

        async with _test_session_factory() as db:
            result = await org_store.remove_member(db, "rm-org-01", rm_user)
            await db.commit()

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_nonexistent_member_returns_false(self) -> None:
        """Returns False when the user is not a member (lines 130-131)."""
        await _seed_org_direct(org_id="rm-nf-01", slug="rm-nf-club")

        async with _test_session_factory() as db:
            result = await org_store.remove_member(db, "rm-nf-01", "ghost-user")
            await db.commit()

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_member_actually_removes(self) -> None:
        """After removal the member no longer appears in get_org_members."""
        await _seed_org_direct(org_id="rm-verify-01", slug="rm-verify-club")
        rm_user2 = "rm-verify-user"
        await _seed_user(rm_user2, "rmv@example.com", "Removed Driver")

        async with _test_session_factory() as db:
            await org_store.add_member(db, "rm-verify-01", rm_user2, "student", None)
            await db.commit()

        async with _test_session_factory() as db:
            await org_store.remove_member(db, "rm-verify-01", rm_user2)
            await db.commit()

        async with _test_session_factory() as db:
            members = await org_store.get_org_members(db, "rm-verify-01")

        user_ids = [m["user_id"] for m in members]
        assert rm_user2 not in user_ids


# ===========================================================================
# check_org_role (lines 140-146)
# ===========================================================================


class TestCheckOrgRole:
    """Tests for org_store.check_org_role."""

    @pytest.mark.asyncio
    async def test_returns_true_when_role_matches(self) -> None:
        """Returns True when user has a role in the given set (lines 145-146)."""
        await _seed_org_direct(org_id="cor-org-01", slug="cor-club")

        async with _test_session_factory() as db:
            result = await org_store.check_org_role(
                db, "cor-org-01", _TEST_USER.user_id, {"owner", "instructor"}
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_role_not_in_set(self) -> None:
        """Returns False when user's role is not in the provided set."""
        await _seed_org_direct(org_id="cor-org-02", slug="cor-club2")

        async with _test_session_factory() as db:
            result = await org_store.check_org_role(
                db, "cor-org-02", _TEST_USER.user_id, {"student"}
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_nonmember(self) -> None:
        """Returns False when user is not in the org at all."""
        await _seed_org_direct(org_id="cor-org-03", slug="cor-club3")

        async with _test_session_factory() as db:
            result = await org_store.check_org_role(
                db, "cor-org-03", "totally-different-user", {"owner"}
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_instructor_role(self) -> None:
        """check_org_role works for non-owner roles too."""
        await _seed_org_direct(org_id="cor-instr-01", slug="cor-instr-club")
        instr_user = "cor-instr-user"
        await _seed_user(instr_user, "instr@example.com", "Instructor")

        async with _test_session_factory() as db:
            await org_store.add_member(db, "cor-instr-01", instr_user, "instructor", None)
            await db.commit()

        async with _test_session_factory() as db:
            result = await org_store.check_org_role(
                db, "cor-instr-01", instr_user, {"instructor", "owner"}
            )

        assert result is True


# ===========================================================================
# create_event (lines 158-171)
# ===========================================================================


class TestCreateEvent:
    """Tests for org_store.create_event."""

    @pytest.mark.asyncio
    async def test_create_event_returns_event_id(self) -> None:
        """Returns a non-empty event ID after inserting the event (line 171)."""
        await _seed_org_direct(org_id="ce-org-01", slug="ce-club")

        async with _test_session_factory() as db:
            event_id = await org_store.create_event(
                db,
                org_id="ce-org-01",
                name="Spring HPDE",
                track_name="Barber",
                event_date_str="2026-05-15T09:00:00",
                run_groups=["Novice", "Intermediate"],
            )
            await db.commit()

        assert isinstance(event_id, str)
        assert len(event_id) > 0

    @pytest.mark.asyncio
    async def test_create_event_without_run_groups(self) -> None:
        """create_event stores null run_groups correctly."""
        await _seed_org_direct(org_id="ce-null-01", slug="ce-null-club")

        async with _test_session_factory() as db:
            event_id = await org_store.create_event(
                db,
                org_id="ce-null-01",
                name="Solo Track Day",
                track_name="Road Atlanta",
                event_date_str="2026-08-10T08:00:00",
                run_groups=None,
            )
            await db.commit()

        async with _test_session_factory() as db:
            events = await org_store.get_org_events(db, "ce-null-01")

        assert len(events) == 1
        assert events[0]["run_groups"] is None
        assert events[0]["id"] == event_id

    @pytest.mark.asyncio
    async def test_event_date_is_stored_and_retrievable(self) -> None:
        """The event_date is persisted (verified via get_org_events)."""
        await _seed_org_direct(org_id="ce-date-01", slug="ce-date-club")

        async with _test_session_factory() as db:
            await org_store.create_event(
                db,
                org_id="ce-date-01",
                name="Dated Event",
                track_name="VIR",
                event_date_str="2026-09-20T07:00:00",
                run_groups=None,
            )
            await db.commit()

        async with _test_session_factory() as db:
            events = await org_store.get_org_events(db, "ce-date-01")

        assert len(events) == 1
        assert "2026-09-20" in events[0]["event_date"]


# ===========================================================================
# get_org_events (lines 179-191)
# ===========================================================================


class TestGetOrgEvents:
    """Tests for org_store.get_org_events."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_org_with_no_events(self) -> None:
        """Returns empty list when org has no events."""
        await _seed_org_direct(org_id="goe-org-01", slug="goe-club")

        async with _test_session_factory() as db:
            result = await org_store.get_org_events(db, "goe-org-01")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_event_dict_with_all_fields(self) -> None:
        """Each event dict has id, org_id, name, track_name, event_date, run_groups."""
        await _seed_org_direct(org_id="goe-org-02", slug="goe-club2")

        async with _test_session_factory() as db:
            await org_store.create_event(
                db,
                org_id="goe-org-02",
                name="Fall Classic",
                track_name="Roebling Road",
                event_date_str="2026-10-01T09:00:00",
                run_groups=["A", "B"],
            )
            await db.commit()

        async with _test_session_factory() as db:
            events = await org_store.get_org_events(db, "goe-org-02")

        assert len(events) == 1
        ev = events[0]
        assert ev["name"] == "Fall Classic"
        assert ev["track_name"] == "Roebling Road"
        assert ev["org_id"] == "goe-org-02"
        assert ev["run_groups"] == ["A", "B"]
        assert "id" in ev
        assert "event_date" in ev

    @pytest.mark.asyncio
    async def test_multiple_events_all_returned(self) -> None:
        """get_org_events returns all events for an org (tests loop body)."""
        await _seed_org_direct(org_id="goe-org-03", slug="goe-multi-club")

        async with _test_session_factory() as db:
            for i in range(3):
                await org_store.create_event(
                    db,
                    org_id="goe-org-03",
                    name=f"Event {i}",
                    track_name="Barber",
                    event_date_str=f"2026-0{i + 5}-01T09:00:00",
                    run_groups=None,
                )
            await db.commit()

        async with _test_session_factory() as db:
            events = await org_store.get_org_events(db, "goe-org-03")

        assert len(events) == 3
        names = {e["name"] for e in events}
        assert {"Event 0", "Event 1", "Event 2"} == names


# ===========================================================================
# delete_event (lines 199-204)
# ===========================================================================


class TestDeleteEvent:
    """Tests for org_store.delete_event."""

    @pytest.mark.asyncio
    async def test_delete_existing_event_returns_true(self) -> None:
        """Returns True and removes the event from the DB (lines 202-204)."""
        await _seed_org_direct(org_id="de-org-01", slug="de-club")

        async with _test_session_factory() as db:
            event_id = await org_store.create_event(
                db,
                org_id="de-org-01",
                name="Delete Me",
                track_name="Barber",
                event_date_str="2026-11-01T09:00:00",
                run_groups=None,
            )
            await db.commit()

        async with _test_session_factory() as db:
            result = await org_store.delete_event(db, event_id, "de-org-01")
            await db.commit()

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_event_returns_false(self) -> None:
        """Returns False when event_id is not found (lines 200-201)."""
        await _seed_org_direct(org_id="de-nf-01", slug="de-nf-club")

        async with _test_session_factory() as db:
            result = await org_store.delete_event(db, "ghost-event-id", "de-nf-01")
            await db.commit()

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_event_wrong_org_returns_false(self) -> None:
        """Returns False when event exists but belongs to a different org."""
        await _seed_org_direct(org_id="de-wo-01", slug="de-wo-club")
        await _seed_org_direct(org_id="de-wo-02", slug="de-wo-club2")

        async with _test_session_factory() as db:
            event_id = await org_store.create_event(
                db,
                org_id="de-wo-01",
                name="Wrong Org Event",
                track_name="Barber",
                event_date_str="2026-12-01T09:00:00",
                run_groups=None,
            )
            await db.commit()

        async with _test_session_factory() as db:
            # Wrong org_id for this event
            result = await org_store.delete_event(db, event_id, "de-wo-02")
            await db.commit()

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_event_is_actually_gone(self) -> None:
        """After deletion the event is absent from get_org_events."""
        await _seed_org_direct(org_id="de-gone-01", slug="de-gone-club")

        async with _test_session_factory() as db:
            event_id = await org_store.create_event(
                db,
                org_id="de-gone-01",
                name="Gone Event",
                track_name="Barber",
                event_date_str="2026-07-04T09:00:00",
                run_groups=None,
            )
            await db.commit()

        async with _test_session_factory() as db:
            await org_store.delete_event(db, event_id, "de-gone-01")
            await db.commit()

        async with _test_session_factory() as db:
            events = await org_store.get_org_events(db, "de-gone-01")

        assert events == []

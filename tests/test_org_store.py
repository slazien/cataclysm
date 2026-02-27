"""Unit tests for the organization store service."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.db.models import Base, User
from backend.api.services.org_store import (
    add_member,
    check_org_role,
    create_event,
    create_org,
    delete_event,
    get_org_by_slug,
    get_org_events,
    get_org_members,
    get_user_orgs,
    remove_member,
)

# In-memory SQLite for isolated unit tests
_engine = create_async_engine("sqlite+aiosqlite:///", echo=False)


@event.listens_for(_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn: object, connection_record: object) -> None:
    cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Patch JSONB -> JSON for SQLite
for table in Base.metadata.tables.values():
    for column in table.columns:
        if isinstance(column.type, JSONB):
            column.type = JSON()

_session_factory = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _setup_db() -> None:  # type: ignore[misc]
    """Create tables and seed test users before each test."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _session_factory() as session:
        session.add(User(id="owner-1", email="owner@test.com", name="Owner", role="instructor"))
        session.add(
            User(id="instructor-1", email="inst@test.com", name="Instructor", role="instructor")
        )
        session.add(User(id="student-1", email="student@test.com", name="Student", role="driver"))
        session.add(
            User(id="outsider-1", email="outsider@test.com", name="Outsider", role="driver")
        )
        await session.commit()

    yield  # type: ignore[misc]

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:  # type: ignore[misc]
    """Yield a fresh database session for each test."""
    async with _session_factory() as session:
        yield session  # type: ignore[misc]


@pytest.mark.asyncio
async def test_create_org(db: AsyncSession) -> None:
    """Creating an org should add the creator as owner."""
    org_id = await create_org(db, "My Club", "my-club", "owner-1", None, None)
    await db.commit()
    assert org_id

    org = await get_org_by_slug(db, "my-club")
    assert org is not None
    assert org["name"] == "My Club"
    assert org["member_count"] == 1


@pytest.mark.asyncio
async def test_get_user_orgs(db: AsyncSession) -> None:
    """User should see orgs they belong to."""
    await create_org(db, "Club A", "club-a", "owner-1", None, None)
    await create_org(db, "Club B", "club-b", "owner-1", None, "#ff0000")
    await db.commit()

    orgs = await get_user_orgs(db, "owner-1")
    assert len(orgs) == 2


@pytest.mark.asyncio
async def test_add_and_list_members(db: AsyncSession) -> None:
    """Adding members and listing them."""
    org_id = await create_org(db, "Test Org", "test-org", "owner-1", None, None)
    await db.commit()

    success = await add_member(db, org_id, "student-1", "student", "Novice")
    await db.commit()
    assert success is True

    members = await get_org_members(db, org_id)
    assert len(members) == 2
    names = {m["name"] for m in members}
    assert "Owner" in names
    assert "Student" in names


@pytest.mark.asyncio
async def test_add_duplicate_member(db: AsyncSession) -> None:
    """Adding the same member twice should fail."""
    org_id = await create_org(db, "Dup Org", "dup-org", "owner-1", None, None)
    await db.commit()

    success1 = await add_member(db, org_id, "student-1", "student", None)
    await db.commit()
    assert success1 is True

    success2 = await add_member(db, org_id, "student-1", "student", None)
    assert success2 is False


@pytest.mark.asyncio
async def test_remove_member(db: AsyncSession) -> None:
    """Removing a member should succeed."""
    org_id = await create_org(db, "Rm Org", "rm-org", "owner-1", None, None)
    await add_member(db, org_id, "student-1", "student", None)
    await db.commit()

    members_before = await get_org_members(db, org_id)
    assert len(members_before) == 2

    success = await remove_member(db, org_id, "student-1")
    await db.commit()
    assert success is True

    members_after = await get_org_members(db, org_id)
    assert len(members_after) == 1


@pytest.mark.asyncio
async def test_remove_nonexistent_member(db: AsyncSession) -> None:
    """Removing a non-member should return False."""
    org_id = await create_org(db, "No Member", "no-member", "owner-1", None, None)
    await db.commit()

    success = await remove_member(db, org_id, "outsider-1")
    assert success is False


@pytest.mark.asyncio
async def test_check_org_role(db: AsyncSession) -> None:
    """check_org_role should correctly identify roles."""
    org_id = await create_org(db, "Role Org", "role-org", "owner-1", None, None)
    await add_member(db, org_id, "student-1", "student", None)
    await db.commit()

    assert await check_org_role(db, org_id, "owner-1", {"owner"}) is True
    assert await check_org_role(db, org_id, "owner-1", {"student"}) is False
    assert await check_org_role(db, org_id, "student-1", {"student"}) is True
    assert await check_org_role(db, org_id, "outsider-1", {"owner", "student"}) is False


@pytest.mark.asyncio
async def test_create_and_list_events(db: AsyncSession) -> None:
    """Creating and listing events."""
    org_id = await create_org(db, "Event Org", "event-org", "owner-1", None, None)
    await db.commit()

    event_id = await create_event(
        db,
        org_id,
        "Track Day #1",
        "Barber Motorsports Park",
        "2026-03-15T09:00:00",
        ["Novice", "Advanced"],
    )
    await db.commit()
    assert event_id

    events = await get_org_events(db, org_id)
    assert len(events) == 1
    assert events[0]["name"] == "Track Day #1"
    assert events[0]["track_name"] == "Barber Motorsports Park"
    assert events[0]["run_groups"] == ["Novice", "Advanced"]


@pytest.mark.asyncio
async def test_delete_event(db: AsyncSession) -> None:
    """Deleting an event should succeed."""
    org_id = await create_org(db, "Del Org", "del-org", "owner-1", None, None)
    event_id = await create_event(db, org_id, "To Delete", "Track X", "2026-04-01T10:00:00", None)
    await db.commit()

    success = await delete_event(db, event_id, org_id)
    await db.commit()
    assert success is True

    events = await get_org_events(db, org_id)
    assert len(events) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_event(db: AsyncSession) -> None:
    """Deleting a nonexistent event should return False."""
    org_id = await create_org(db, "NE Org", "ne-org", "owner-1", None, None)
    await db.commit()

    success = await delete_event(db, "nonexistent", org_id)
    assert success is False


@pytest.mark.asyncio
async def test_get_org_by_slug_not_found(db: AsyncSession) -> None:
    """Getting a nonexistent org returns None."""
    result = await get_org_by_slug(db, "does-not-exist")
    assert result is None

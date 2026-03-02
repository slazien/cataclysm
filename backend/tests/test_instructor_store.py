"""Unit tests for the instructor store service."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import JSON, event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.db.models import (
    Base,
    InstructorStudent,
    StudentFlag,
    User,
)
from backend.api.db.models import (
    Session as SessionModel,
)
from backend.api.services.instructor_store import (
    _generate_invite_code,
    accept_invite,
    add_manual_flag,
    create_invite,
    get_student_flags,
    get_student_sessions,
    get_students,
    remove_student,
)

# ---------------------------------------------------------------------------
# In-memory SQLite test engine
# ---------------------------------------------------------------------------

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

_INSTRUCTOR_ID = "instructor-1"
_STUDENT_ID = "student-1"
_STUDENT2_ID = "student-2"


@pytest_asyncio.fixture(autouse=True)
async def _setup_db() -> None:  # type: ignore[misc]
    """Create tables and seed test users before each test."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _session_factory() as session:
        session.add(
            User(
                id=_INSTRUCTOR_ID, email="instructor@test.com", name="Instructor", role="instructor"
            )
        )
        session.add(
            User(
                id="other-instructor",
                email="other@test.com",
                name="Other Instructor",
                role="instructor",
            )
        )
        session.add(User(id=_STUDENT_ID, email="student1@test.com", name="Student One"))
        session.add(User(id=_STUDENT2_ID, email="student2@test.com", name="Student Two"))
        await session.commit()

    yield  # type: ignore[misc]

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:  # type: ignore[misc]
    """Yield a fresh database session for each test."""
    async with _session_factory() as session:
        yield session  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _link_student(
    db: AsyncSession,
    instructor_id: str = _INSTRUCTOR_ID,
    student_id: str = _STUDENT_ID,
    status: str = "active",
) -> InstructorStudent:
    """Create an active InstructorStudent link."""
    link = InstructorStudent(
        instructor_id=instructor_id,
        student_id=student_id,
        invite_code=None,
        status=status,
        created_at=datetime.now(UTC),
    )
    db.add(link)
    await db.flush()
    return link


async def _seed_session(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    track_name: str = "Barber Motorsports Park",
    n_laps: int = 5,
    session_date: datetime | None = None,
) -> None:
    """Insert a Session row for testing."""
    db.add(
        SessionModel(
            session_id=session_id,
            user_id=user_id,
            track_name=track_name,
            session_date=session_date or datetime(2026, 1, 15, tzinfo=UTC),
            file_key=f"key-{session_id}",
            n_laps=n_laps,
        )
    )
    await db.flush()


async def _seed_flag(
    db: AsyncSession,
    student_id: str,
    flag_type: str = "attention",
    description: str = "Test flag",
    session_id: str | None = None,
    auto_generated: bool = True,
    created_at: datetime | None = None,
) -> StudentFlag:
    """Insert a StudentFlag row for testing."""
    flag = StudentFlag(
        student_id=student_id,
        flag_type=flag_type,
        description=description,
        session_id=session_id,
        auto_generated=auto_generated,
        created_at=created_at or datetime.now(UTC),
    )
    db.add(flag)
    await db.flush()
    return flag


# ---------------------------------------------------------------------------
# Tests: _generate_invite_code
# ---------------------------------------------------------------------------


class TestGenerateInviteCode:
    """Tests for the _generate_invite_code utility."""

    def test_returns_string(self) -> None:
        """Result is a non-empty string."""
        code = _generate_invite_code()
        assert isinstance(code, str)
        assert len(code) > 0

    def test_codes_are_unique(self) -> None:
        """Two generated codes are almost certainly different."""
        codes = {_generate_invite_code() for _ in range(20)}
        assert len(codes) == 20

    def test_url_safe_characters(self) -> None:
        """Generated code contains only URL-safe characters."""
        import re

        for _ in range(10):
            code = _generate_invite_code()
            assert re.match(r"^[A-Za-z0-9_\-]+$", code), f"Non-URL-safe chars in: {code}"


# ---------------------------------------------------------------------------
# Tests: get_students
# ---------------------------------------------------------------------------


class TestGetStudents:
    """Tests for get_students."""

    @pytest.mark.asyncio
    async def test_empty_when_no_students(self, db: AsyncSession) -> None:
        """Instructor with no students returns empty list."""
        students = await get_students(db, _INSTRUCTOR_ID)
        assert students == []

    @pytest.mark.asyncio
    async def test_returns_active_students(self, db: AsyncSession) -> None:
        """Returns students with active links."""
        await _link_student(db, student_id=_STUDENT_ID, status="active")
        await db.commit()

        students = await get_students(db, _INSTRUCTOR_ID)
        assert len(students) == 1
        assert students[0]["student_id"] == _STUDENT_ID
        assert students[0]["name"] == "Student One"

    @pytest.mark.asyncio
    async def test_excludes_pending_links(self, db: AsyncSession) -> None:
        """Pending (not yet accepted) links are not returned."""
        await _link_student(db, student_id=_STUDENT_ID, status="pending")
        await db.commit()

        students = await get_students(db, _INSTRUCTOR_ID)
        assert students == []

    @pytest.mark.asyncio
    async def test_excludes_removed_links(self, db: AsyncSession) -> None:
        """Removed links are not returned."""
        await _link_student(db, student_id=_STUDENT_ID, status="removed")
        await db.commit()

        students = await get_students(db, _INSTRUCTOR_ID)
        assert students == []

    @pytest.mark.asyncio
    async def test_multiple_students(self, db: AsyncSession) -> None:
        """Multiple active students are all returned."""
        await _link_student(db, student_id=_STUDENT_ID, status="active")
        await _link_student(db, student_id=_STUDENT2_ID, status="active")
        await db.commit()

        students = await get_students(db, _INSTRUCTOR_ID)
        assert len(students) == 2
        student_ids = {s["student_id"] for s in students}
        assert student_ids == {_STUDENT_ID, _STUDENT2_ID}

    @pytest.mark.asyncio
    async def test_includes_recent_flags(self, db: AsyncSession) -> None:
        """Returned student dicts include a recent_flags list."""
        await _link_student(db, student_id=_STUDENT_ID, status="active")
        await _seed_flag(db, _STUDENT_ID, flag_type="attention")
        await _seed_flag(db, _STUDENT_ID, flag_type="improvement")
        await db.commit()

        students = await get_students(db, _INSTRUCTOR_ID)
        assert len(students) == 1
        assert "recent_flags" in students[0]
        recent = students[0]["recent_flags"]
        assert "attention" in recent
        assert "improvement" in recent

    @pytest.mark.asyncio
    async def test_student_dict_has_correct_fields(self, db: AsyncSession) -> None:
        """Student dict includes all expected fields."""
        await _link_student(db, student_id=_STUDENT_ID, status="active")
        await db.commit()

        students = await get_students(db, _INSTRUCTOR_ID)
        expected_keys = {"student_id", "name", "email", "avatar_url", "linked_at", "recent_flags"}
        assert expected_keys.issubset(students[0].keys())

    @pytest.mark.asyncio
    async def test_does_not_return_other_instructors_students(self, db: AsyncSession) -> None:
        """Students linked to a different instructor are not returned."""
        other_instructor_id = "other-instructor"
        # Link student-2 to the OTHER instructor only
        await _link_student(
            db, instructor_id=other_instructor_id, student_id=_STUDENT2_ID, status="active"
        )
        await db.commit()

        students = await get_students(db, _INSTRUCTOR_ID)
        assert students == []

    @pytest.mark.asyncio
    async def test_recent_flags_limited_to_20(self, db: AsyncSession) -> None:
        """Recent flags are limited to at most 20 entries per student."""
        await _link_student(db, student_id=_STUDENT_ID, status="active")
        # Seed 25 flags
        for i in range(25):
            await _seed_flag(db, _STUDENT_ID, flag_type="attention", description=f"flag {i}")
        await db.commit()

        students = await get_students(db, _INSTRUCTOR_ID)
        assert len(students[0]["recent_flags"]) == 20


# ---------------------------------------------------------------------------
# Tests: create_invite
# ---------------------------------------------------------------------------


class TestCreateInvite:
    """Tests for create_invite."""

    @pytest.mark.asyncio
    async def test_returns_code_string(self, db: AsyncSession) -> None:
        """create_invite returns a non-empty string code."""
        code = await create_invite(db, _INSTRUCTOR_ID)
        await db.commit()
        assert isinstance(code, str)
        assert len(code) > 0

    @pytest.mark.asyncio
    async def test_creates_pending_link(self, db: AsyncSession) -> None:
        """A pending InstructorStudent row is created with the code."""
        code = await create_invite(db, _INSTRUCTOR_ID)
        await db.commit()

        result = await db.execute(
            select(InstructorStudent).where(InstructorStudent.invite_code == code)
        )
        link = result.scalar_one()
        assert link.status == "pending"
        assert link.instructor_id == _INSTRUCTOR_ID
        assert link.student_id == ""  # placeholder

    @pytest.mark.asyncio
    async def test_each_invite_has_unique_code(self, db: AsyncSession) -> None:
        """Two invites from different instructors get different codes."""
        code1 = await create_invite(db, _INSTRUCTOR_ID)
        # Use "other-instructor" which is seeded in _setup_db
        code2 = await create_invite(db, "other-instructor")
        await db.commit()

        assert code1 != code2


# ---------------------------------------------------------------------------
# Tests: accept_invite
# ---------------------------------------------------------------------------


class TestAcceptInvite:
    """Tests for accept_invite."""

    @pytest.mark.asyncio
    async def test_accept_valid_code(self, db: AsyncSession) -> None:
        """Accepting a valid pending code links the student and returns True."""
        code = await create_invite(db, _INSTRUCTOR_ID)
        await db.commit()

        success = await accept_invite(db, _STUDENT_ID, code)
        await db.commit()

        assert success is True

    @pytest.mark.asyncio
    async def test_link_becomes_active_after_accept(self, db: AsyncSession) -> None:
        """After accepting, the link status is active."""
        code = await create_invite(db, _INSTRUCTOR_ID)
        await db.commit()

        await accept_invite(db, _STUDENT_ID, code)
        await db.commit()

        result = await db.execute(
            select(InstructorStudent).where(
                InstructorStudent.instructor_id == _INSTRUCTOR_ID,
                InstructorStudent.student_id == _STUDENT_ID,
            )
        )
        link = result.scalar_one()
        assert link.status == "active"
        assert link.student_id == _STUDENT_ID
        assert link.invite_code is None  # cleared after use

    @pytest.mark.asyncio
    async def test_invite_code_cleared_after_accept(self, db: AsyncSession) -> None:
        """The invite_code field is set to None after acceptance (one-time use)."""
        code = await create_invite(db, _INSTRUCTOR_ID)
        await db.commit()

        await accept_invite(db, _STUDENT_ID, code)
        await db.commit()

        result = await db.execute(
            select(InstructorStudent).where(InstructorStudent.instructor_id == _INSTRUCTOR_ID)
        )
        link = result.scalar_one()
        assert link.invite_code is None

    @pytest.mark.asyncio
    async def test_accept_invalid_code_returns_false(self, db: AsyncSession) -> None:
        """Accepting a nonexistent code returns False."""
        success = await accept_invite(db, _STUDENT_ID, "no-such-code")
        assert success is False

    @pytest.mark.asyncio
    async def test_accept_already_used_code_returns_false(self, db: AsyncSession) -> None:
        """A code that has already been accepted cannot be used again."""
        code = await create_invite(db, _INSTRUCTOR_ID)
        await db.commit()

        await accept_invite(db, _STUDENT_ID, code)
        await db.commit()

        # Try to accept the same code with a different student
        success = await accept_invite(db, _STUDENT2_ID, code)
        assert success is False


# ---------------------------------------------------------------------------
# Tests: remove_student
# ---------------------------------------------------------------------------


class TestRemoveStudent:
    """Tests for remove_student."""

    @pytest.mark.asyncio
    async def test_remove_existing_student(self, db: AsyncSession) -> None:
        """Removing a linked student returns True."""
        await _link_student(db, student_id=_STUDENT_ID, status="active")
        await db.commit()

        success = await remove_student(db, _INSTRUCTOR_ID, _STUDENT_ID)
        await db.commit()

        assert success is True

    @pytest.mark.asyncio
    async def test_link_status_becomes_removed(self, db: AsyncSession) -> None:
        """After removal, link status is 'removed'."""
        await _link_student(db, student_id=_STUDENT_ID, status="active")
        await db.commit()

        await remove_student(db, _INSTRUCTOR_ID, _STUDENT_ID)
        await db.commit()

        result = await db.execute(
            select(InstructorStudent).where(
                InstructorStudent.instructor_id == _INSTRUCTOR_ID,
                InstructorStudent.student_id == _STUDENT_ID,
            )
        )
        link = result.scalar_one()
        assert link.status == "removed"

    @pytest.mark.asyncio
    async def test_remove_nonexistent_student(self, db: AsyncSession) -> None:
        """Removing a student with no link returns False."""
        success = await remove_student(db, _INSTRUCTOR_ID, "ghost-student")
        assert success is False

    @pytest.mark.asyncio
    async def test_removed_student_no_longer_in_list(self, db: AsyncSession) -> None:
        """After removal, student does not appear in get_students."""
        await _link_student(db, student_id=_STUDENT_ID, status="active")
        await db.commit()

        await remove_student(db, _INSTRUCTOR_ID, _STUDENT_ID)
        await db.commit()

        students = await get_students(db, _INSTRUCTOR_ID)
        assert students == []


# ---------------------------------------------------------------------------
# Tests: get_student_sessions
# ---------------------------------------------------------------------------


class TestGetStudentSessions:
    """Tests for get_student_sessions."""

    @pytest.mark.asyncio
    async def test_empty_when_no_sessions(self, db: AsyncSession) -> None:
        """Student with no sessions returns empty list."""
        sessions = await get_student_sessions(db, _STUDENT_ID)
        assert sessions == []

    @pytest.mark.asyncio
    async def test_returns_student_sessions(self, db: AsyncSession) -> None:
        """Returns sessions belonging to the student."""
        await _seed_session(db, "sess-1", _STUDENT_ID)
        await db.commit()

        sessions = await get_student_sessions(db, _STUDENT_ID)
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_sessions_ordered_by_date_descending(self, db: AsyncSession) -> None:
        """Most recent session is first."""
        await _seed_session(
            db, "sess-old", _STUDENT_ID, session_date=datetime(2026, 1, 1, tzinfo=UTC)
        )
        await _seed_session(
            db, "sess-new", _STUDENT_ID, session_date=datetime(2026, 2, 1, tzinfo=UTC)
        )
        await db.commit()

        sessions = await get_student_sessions(db, _STUDENT_ID)
        assert sessions[0]["session_id"] == "sess-new"
        assert sessions[1]["session_id"] == "sess-old"

    @pytest.mark.asyncio
    async def test_respects_limit(self, db: AsyncSession) -> None:
        """Limit parameter caps the number of returned sessions."""
        for i in range(5):
            await _seed_session(
                db,
                f"sess-{i}",
                _STUDENT_ID,
                session_date=datetime(2026, 1, i + 1, tzinfo=UTC),
            )
        await db.commit()

        sessions = await get_student_sessions(db, _STUDENT_ID, limit=3)
        assert len(sessions) == 3

    @pytest.mark.asyncio
    async def test_session_dict_has_correct_fields(self, db: AsyncSession) -> None:
        """Returned session dicts have the expected keys."""
        await _seed_session(db, "sess-1", _STUDENT_ID)
        await db.commit()

        sessions = await get_student_sessions(db, _STUDENT_ID)
        expected_keys = {
            "session_id",
            "track_name",
            "session_date",
            "best_lap_time_s",
            "consistency_score",
            "n_laps",
            "flags",
        }
        assert expected_keys.issubset(sessions[0].keys())

    @pytest.mark.asyncio
    async def test_session_includes_flags(self, db: AsyncSession) -> None:
        """Flags attached to a session appear in the session dict."""
        await _seed_session(db, "sess-1", _STUDENT_ID)
        await _seed_flag(db, _STUDENT_ID, flag_type="attention", session_id="sess-1")
        await db.commit()

        sessions = await get_student_sessions(db, _STUDENT_ID)
        flags = sessions[0]["flags"]
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "attention"

    @pytest.mark.asyncio
    async def test_does_not_return_other_students_sessions(self, db: AsyncSession) -> None:
        """Sessions from other students are not included."""
        await _seed_session(db, "sess-s2", _STUDENT2_ID)
        await db.commit()

        sessions = await get_student_sessions(db, _STUDENT_ID)
        assert sessions == []


# ---------------------------------------------------------------------------
# Tests: get_student_flags
# ---------------------------------------------------------------------------


class TestGetStudentFlags:
    """Tests for get_student_flags."""

    @pytest.mark.asyncio
    async def test_empty_when_no_flags(self, db: AsyncSession) -> None:
        """Student with no flags returns empty list."""
        flags = await get_student_flags(db, _STUDENT_ID)
        assert flags == []

    @pytest.mark.asyncio
    async def test_returns_flags(self, db: AsyncSession) -> None:
        """Returns flags for the student."""
        await _seed_flag(db, _STUDENT_ID, flag_type="attention", description="Check braking")
        await db.commit()

        flags = await get_student_flags(db, _STUDENT_ID)
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "attention"
        assert flags[0]["description"] == "Check braking"

    @pytest.mark.asyncio
    async def test_ordered_newest_first(self, db: AsyncSession) -> None:
        """Flags are returned newest first."""
        await _seed_flag(
            db,
            _STUDENT_ID,
            flag_type="attention",
            description="old flag",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        await _seed_flag(
            db,
            _STUDENT_ID,
            flag_type="improvement",
            description="new flag",
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        await db.commit()

        flags = await get_student_flags(db, _STUDENT_ID)
        assert flags[0]["flag_type"] == "improvement"
        assert flags[1]["flag_type"] == "attention"

    @pytest.mark.asyncio
    async def test_limit_50(self, db: AsyncSession) -> None:
        """No more than 50 flags are returned."""
        for i in range(60):
            await _seed_flag(db, _STUDENT_ID, description=f"flag {i}")
        await db.commit()

        flags = await get_student_flags(db, _STUDENT_ID)
        assert len(flags) == 50

    @pytest.mark.asyncio
    async def test_flag_dict_has_correct_fields(self, db: AsyncSession) -> None:
        """Flag dicts include all expected keys."""
        await _seed_flag(db, _STUDENT_ID, session_id="sess-1")
        await db.commit()

        flags = await get_student_flags(db, _STUDENT_ID)
        expected_keys = {
            "id",
            "flag_type",
            "description",
            "session_id",
            "auto_generated",
            "created_at",
        }
        assert expected_keys.issubset(flags[0].keys())

    @pytest.mark.asyncio
    async def test_does_not_return_other_students_flags(self, db: AsyncSession) -> None:
        """Flags for other students are not included."""
        await _seed_flag(db, _STUDENT2_ID, flag_type="improvement")
        await db.commit()

        flags = await get_student_flags(db, _STUDENT_ID)
        assert flags == []


# ---------------------------------------------------------------------------
# Tests: add_manual_flag
# ---------------------------------------------------------------------------


class TestAddManualFlag:
    """Tests for add_manual_flag."""

    @pytest.mark.asyncio
    async def test_returns_integer_id(self, db: AsyncSession) -> None:
        """add_manual_flag returns the new flag's integer ID."""
        flag_id = await add_manual_flag(db, _STUDENT_ID, None, "attention", "Check entry speed")
        await db.commit()
        assert isinstance(flag_id, int)
        assert flag_id > 0

    @pytest.mark.asyncio
    async def test_flag_is_persisted(self, db: AsyncSession) -> None:
        """The created flag exists in the database."""
        flag_id = await add_manual_flag(db, _STUDENT_ID, "sess-1", "improvement", "Great late apex")
        await db.commit()

        result = await db.execute(select(StudentFlag).where(StudentFlag.id == flag_id))
        flag = result.scalar_one()
        assert flag.student_id == _STUDENT_ID
        assert flag.session_id == "sess-1"
        assert flag.flag_type == "improvement"
        assert flag.description == "Great late apex"

    @pytest.mark.asyncio
    async def test_auto_generated_is_false(self, db: AsyncSession) -> None:
        """Manual flags have auto_generated=False."""
        flag_id = await add_manual_flag(db, _STUDENT_ID, None, "attention", "Manual note")
        await db.commit()

        result = await db.execute(select(StudentFlag).where(StudentFlag.id == flag_id))
        flag = result.scalar_one()
        assert flag.auto_generated is False

    @pytest.mark.asyncio
    async def test_flag_with_no_session_id(self, db: AsyncSession) -> None:
        """Manual flags can be created without a session_id."""
        flag_id = await add_manual_flag(db, _STUDENT_ID, None, "praise", "Excellent session")
        await db.commit()

        result = await db.execute(select(StudentFlag).where(StudentFlag.id == flag_id))
        flag = result.scalar_one()
        assert flag.session_id is None

    @pytest.mark.asyncio
    async def test_multiple_flags_get_different_ids(self, db: AsyncSession) -> None:
        """Each add_manual_flag call returns a unique ID."""
        id1 = await add_manual_flag(db, _STUDENT_ID, None, "attention", "Flag one")
        id2 = await add_manual_flag(db, _STUDENT_ID, None, "attention", "Flag two")
        await db.commit()
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_flag_appears_in_get_student_flags(self, db: AsyncSession) -> None:
        """A manually added flag appears in get_student_flags results."""
        await add_manual_flag(db, _STUDENT_ID, None, "praise", "Well done")
        await db.commit()

        flags = await get_student_flags(db, _STUDENT_ID)
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "praise"
        assert flags[0]["auto_generated"] is False

    @pytest.mark.asyncio
    async def test_flag_has_created_at_timestamp(self, db: AsyncSession) -> None:
        """The created flag has a non-None created_at timestamp."""
        flag_id = await add_manual_flag(db, _STUDENT_ID, None, "attention", "Timestamp check")
        await db.commit()

        result = await db.execute(select(StudentFlag).where(StudentFlag.id == flag_id))
        flag = result.scalar_one()
        assert flag.created_at is not None

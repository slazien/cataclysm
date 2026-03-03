"""Integration tests for the instructor router (/api/instructor).

All endpoints require the user to hold the 'instructor' role in the DB.
Tests cover role enforcement (403 for plain drivers), the invite/accept
flow, student unlinking, session and flag retrieval, and flag validation.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.api.db.models import InstructorStudent, StudentFlag, User
from backend.api.db.models import Session as SessionModel
from backend.tests.conftest import _test_session_factory

# IDs used across test helpers
_STUDENT_ID = "student-999"
_STUDENT_EMAIL = "student@integ.test"
_STUDENT_NAME = "Integ Student"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _seed_student_user() -> None:  # type: ignore[misc]
    """Seed a student user so FK constraints work when linking to them."""
    async with _test_session_factory() as session:
        existing = await session.get(User, _STUDENT_ID)
        if existing is None:
            session.add(
                User(
                    id=_STUDENT_ID,
                    email=_STUDENT_EMAIL,
                    name=_STUDENT_NAME,
                )
            )
            await session.commit()


async def _promote_test_user_to_instructor() -> None:
    """Upgrade the seeded test-user-123 to instructor role in the test DB."""
    async with _test_session_factory() as session:
        result = await session.execute(select(User).where(User.id == "test-user-123"))
        user = result.scalar_one()
        user.role = "instructor"
        await session.commit()


async def _demote_test_user_to_driver() -> None:
    """Downgrade test-user-123 back to driver role."""
    async with _test_session_factory() as session:
        result = await session.execute(select(User).where(User.id == "test-user-123"))
        user = result.scalar_one()
        user.role = "driver"
        await session.commit()


async def _link_student(
    instructor_id: str = "test-user-123",
    student_id: str = _STUDENT_ID,
    status: str = "active",
) -> None:
    """Insert an InstructorStudent link directly into the test DB."""
    async with _test_session_factory() as session:
        session.add(
            InstructorStudent(
                instructor_id=instructor_id,
                student_id=student_id,
                invite_code=None,
                status=status,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def _seed_session_for_student(
    session_id: str,
    student_id: str = _STUDENT_ID,
    track_name: str = "Test Circuit",
) -> None:
    """Insert a Session row owned by the student."""
    async with _test_session_factory() as session:
        session.add(
            SessionModel(
                session_id=session_id,
                user_id=student_id,
                track_name=track_name,
                session_date=datetime(2026, 1, 15, tzinfo=UTC),
                file_key=f"key-{session_id}",
                n_laps=3,
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# GET /api/instructor/students
# ---------------------------------------------------------------------------


class TestListStudents:
    """Integration tests for GET /api/instructor/students."""

    @pytest.mark.asyncio
    async def test_returns_403_when_not_instructor(self, client: AsyncClient) -> None:
        """A driver-role user receives 403 Forbidden."""
        # test-user-123 is seeded as driver by default
        resp = await client.get("/api/instructor/students")

        assert resp.status_code == 403
        assert "instructor" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_instructor_with_no_students(
        self, client: AsyncClient
    ) -> None:
        """An instructor with no linked students gets an empty students list."""
        await _promote_test_user_to_instructor()

        resp = await client.get("/api/instructor/students")

        assert resp.status_code == 200
        assert resp.json()["students"] == []

    @pytest.mark.asyncio
    async def test_returns_linked_students(self, client: AsyncClient) -> None:
        """Returns summary entries for each active linked student."""
        await _promote_test_user_to_instructor()
        await _link_student()

        resp = await client.get("/api/instructor/students")

        assert resp.status_code == 200
        students = resp.json()["students"]
        assert len(students) == 1
        assert students[0]["student_id"] == _STUDENT_ID
        assert students[0]["name"] == _STUDENT_NAME
        assert students[0]["email"] == _STUDENT_EMAIL

    @pytest.mark.asyncio
    async def test_excludes_pending_and_removed_links(self, client: AsyncClient) -> None:
        """Pending and removed links do not appear in the student list."""
        await _promote_test_user_to_instructor()
        await _link_student(status="pending")

        resp = await client.get("/api/instructor/students")

        assert resp.status_code == 200
        assert resp.json()["students"] == []


# ---------------------------------------------------------------------------
# POST /api/instructor/invite
# ---------------------------------------------------------------------------


class TestGenerateInvite:
    """Integration tests for POST /api/instructor/invite."""

    @pytest.mark.asyncio
    async def test_returns_403_when_not_instructor(self, client: AsyncClient) -> None:
        """Driver role returns 403."""
        resp = await client.post("/api/instructor/invite")

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_invite_code(self, client: AsyncClient) -> None:
        """Instructor gets a non-empty invite_code string."""
        await _promote_test_user_to_instructor()

        resp = await client.post("/api/instructor/invite")

        assert resp.status_code == 200
        data = resp.json()
        assert "invite_code" in data
        assert isinstance(data["invite_code"], str)
        assert len(data["invite_code"]) > 0

    @pytest.mark.asyncio
    async def test_invite_code_is_url_safe_string(self, client: AsyncClient) -> None:
        """The invite code is a non-empty URL-safe string."""
        import re

        await _promote_test_user_to_instructor()

        resp = await client.post("/api/instructor/invite")

        code = resp.json()["invite_code"]
        assert re.match(r"^[A-Za-z0-9_\-]+$", code), f"Non URL-safe characters in: {code}"

    @pytest.mark.asyncio
    async def test_invite_creates_pending_link_in_db(self, client: AsyncClient) -> None:
        """The generated invite code results in a pending InstructorStudent row."""
        await _promote_test_user_to_instructor()

        resp = await client.post("/api/instructor/invite")
        code = resp.json()["invite_code"]

        async with _test_session_factory() as session:
            result = await session.execute(
                select(InstructorStudent).where(InstructorStudent.invite_code == code)
            )
            link = result.scalar_one_or_none()

        assert link is not None
        assert link.status == "pending"
        assert link.instructor_id == "test-user-123"


# ---------------------------------------------------------------------------
# POST /api/instructor/accept/{code}
# ---------------------------------------------------------------------------


class TestAcceptInviteCode:
    """Integration tests for POST /api/instructor/accept/{code}."""

    @pytest.mark.asyncio
    async def test_accept_valid_code_returns_linked(self, client: AsyncClient) -> None:
        """Accepting a valid pending code returns status 'linked'."""
        await _promote_test_user_to_instructor()
        invite_resp = await client.post("/api/instructor/invite")
        code = invite_resp.json()["invite_code"]

        # Demote back to driver so the current user can act as a student
        await _demote_test_user_to_driver()

        resp = await client.post(f"/api/instructor/accept/{code}")

        assert resp.status_code == 200
        assert resp.json()["status"] == "linked"

    @pytest.mark.asyncio
    async def test_accept_invalid_code_returns_404(self, client: AsyncClient) -> None:
        """Accepting a bogus code returns 404."""
        resp = await client.post("/api/instructor/accept/totally-fake-code")

        assert resp.status_code == 404
        assert "invalid" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_accept_sets_link_active_in_db(self, client: AsyncClient) -> None:
        """After acceptance the InstructorStudent row is active."""
        await _promote_test_user_to_instructor()
        invite_resp = await client.post("/api/instructor/invite")
        code = invite_resp.json()["invite_code"]
        await _demote_test_user_to_driver()

        await client.post(f"/api/instructor/accept/{code}")

        async with _test_session_factory() as session:
            result = await session.execute(
                select(InstructorStudent).where(InstructorStudent.student_id == "test-user-123")
            )
            link = result.scalar_one_or_none()

        assert link is not None
        assert link.status == "active"
        assert link.invite_code is None  # consumed

    @pytest.mark.asyncio
    async def test_code_cannot_be_reused(self, client: AsyncClient) -> None:
        """Accepting the same code twice fails on the second attempt."""
        await _promote_test_user_to_instructor()
        invite_resp = await client.post("/api/instructor/invite")
        code = invite_resp.json()["invite_code"]
        await _demote_test_user_to_driver()

        first = await client.post(f"/api/instructor/accept/{code}")
        assert first.status_code == 200

        second = await client.post(f"/api/instructor/accept/{code}")
        assert second.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/instructor/students/{student_id}
# ---------------------------------------------------------------------------


class TestUnlinkStudent:
    """Integration tests for DELETE /api/instructor/students/{student_id}."""

    @pytest.mark.asyncio
    async def test_returns_403_when_not_instructor(self, client: AsyncClient) -> None:
        """Driver role returns 403."""
        resp = await client.delete(f"/api/instructor/students/{_STUDENT_ID}")

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unlinks_active_student(self, client: AsyncClient) -> None:
        """Returns status 'removed' for a linked student."""
        await _promote_test_user_to_instructor()
        await _link_student()

        resp = await client.delete(f"/api/instructor/students/{_STUDENT_ID}")

        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

    @pytest.mark.asyncio
    async def test_returns_404_for_unlinked_student(self, client: AsyncClient) -> None:
        """404 is returned when the student is not linked to this instructor."""
        await _promote_test_user_to_instructor()

        resp = await client.delete("/api/instructor/students/nobody")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_student_no_longer_appears_in_list_after_unlink(
        self, client: AsyncClient
    ) -> None:
        """After unlinking, the student does not appear in GET /students."""
        await _promote_test_user_to_instructor()
        await _link_student()

        await client.delete(f"/api/instructor/students/{_STUDENT_ID}")

        list_resp = await client.get("/api/instructor/students")
        student_ids = [s["student_id"] for s in list_resp.json()["students"]]
        assert _STUDENT_ID not in student_ids


# ---------------------------------------------------------------------------
# GET /api/instructor/students/{student_id}/sessions
# ---------------------------------------------------------------------------


class TestStudentSessions:
    """Integration tests for GET /api/instructor/students/{student_id}/sessions."""

    @pytest.mark.asyncio
    async def test_returns_403_when_not_instructor(self, client: AsyncClient) -> None:
        """Driver role returns 403."""
        resp = await client.get(f"/api/instructor/students/{_STUDENT_ID}/sessions")

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_404_when_student_not_linked(self, client: AsyncClient) -> None:
        """404 is returned when the student is not linked to this instructor."""
        await _promote_test_user_to_instructor()

        resp = await client.get(f"/api/instructor/students/{_STUDENT_ID}/sessions")

        assert resp.status_code == 404
        assert "not linked" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_returns_empty_sessions_for_linked_student_with_none(
        self, client: AsyncClient
    ) -> None:
        """An empty sessions list is returned for a linked student with no sessions."""
        await _promote_test_user_to_instructor()
        await _link_student()

        resp = await client.get(f"/api/instructor/students/{_STUDENT_ID}/sessions")

        assert resp.status_code == 200
        assert resp.json()["sessions"] == []

    @pytest.mark.asyncio
    async def test_returns_student_sessions(self, client: AsyncClient) -> None:
        """Sessions belonging to a linked student are returned."""
        await _promote_test_user_to_instructor()
        await _link_student()
        await _seed_session_for_student("sess-integ-1")

        resp = await client.get(f"/api/instructor/students/{_STUDENT_ID}/sessions")

        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "sess-integ-1"
        assert sessions[0]["track_name"] == "Test Circuit"

    @pytest.mark.asyncio
    async def test_session_response_includes_flags_key(self, client: AsyncClient) -> None:
        """Each session entry contains a flags list."""
        await _promote_test_user_to_instructor()
        await _link_student()
        await _seed_session_for_student("sess-integ-2")

        resp = await client.get(f"/api/instructor/students/{_STUDENT_ID}/sessions")

        sessions = resp.json()["sessions"]
        assert "flags" in sessions[0]
        assert isinstance(sessions[0]["flags"], list)


# ---------------------------------------------------------------------------
# GET /api/instructor/students/{student_id}/flags
# ---------------------------------------------------------------------------


class TestStudentFlags:
    """Integration tests for GET /api/instructor/students/{student_id}/flags."""

    @pytest.mark.asyncio
    async def test_returns_403_when_not_instructor(self, client: AsyncClient) -> None:
        """Driver role returns 403."""
        resp = await client.get(f"/api/instructor/students/{_STUDENT_ID}/flags")

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_empty_flags_when_none(self, client: AsyncClient) -> None:
        """An empty flags list is returned when the student has no flags."""
        await _promote_test_user_to_instructor()

        resp = await client.get(f"/api/instructor/students/{_STUDENT_ID}/flags")

        assert resp.status_code == 200
        assert resp.json()["flags"] == []

    @pytest.mark.asyncio
    async def test_returns_flags_for_student(self, client: AsyncClient) -> None:
        """Flags seeded for the student are returned."""
        await _promote_test_user_to_instructor()
        async with _test_session_factory() as session:
            session.add(
                StudentFlag(
                    student_id=_STUDENT_ID,
                    flag_type="attention",
                    description="Late braking at T1",
                    auto_generated=False,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()

        resp = await client.get(f"/api/instructor/students/{_STUDENT_ID}/flags")

        assert resp.status_code == 200
        flags = resp.json()["flags"]
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "attention"
        assert flags[0]["description"] == "Late braking at T1"


# ---------------------------------------------------------------------------
# POST /api/instructor/students/{student_id}/flags
# ---------------------------------------------------------------------------


class TestCreateFlag:
    """Integration tests for POST /api/instructor/students/{student_id}/flags."""

    @pytest.mark.asyncio
    async def test_returns_403_when_not_instructor(self, client: AsyncClient) -> None:
        """Driver role returns 403."""
        resp = await client.post(
            f"/api/instructor/students/{_STUDENT_ID}/flags",
            json={"flag_type": "attention", "description": "Bad braking"},
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_creates_flag_successfully(self, client: AsyncClient) -> None:
        """Valid flag request returns the created flag with expected fields."""
        await _promote_test_user_to_instructor()

        resp = await client.post(
            f"/api/instructor/students/{_STUDENT_ID}/flags",
            json={"flag_type": "improvement", "description": "Better exit speed"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["flag_type"] == "improvement"
        assert data["description"] == "Better exit speed"
        assert data["auto_generated"] is False
        assert "id" in data

    @pytest.mark.asyncio
    async def test_creates_flag_with_session_id(self, client: AsyncClient) -> None:
        """A flag linked to a specific session_id is accepted."""
        await _promote_test_user_to_instructor()

        resp = await client.post(
            f"/api/instructor/students/{_STUDENT_ID}/flags",
            json={
                "flag_type": "praise",
                "description": "Perfect lap",
                "session_id": "some-session-123",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["session_id"] == "some-session-123"

    @pytest.mark.asyncio
    async def test_all_valid_flag_types_accepted(self, client: AsyncClient) -> None:
        """All four valid flag types are accepted without error."""
        await _promote_test_user_to_instructor()
        valid_types = ["attention", "safety", "improvement", "praise"]

        for flag_type in valid_types:
            resp = await client.post(
                f"/api/instructor/students/{_STUDENT_ID}/flags",
                json={"flag_type": flag_type, "description": f"Test {flag_type}"},
            )
            assert resp.status_code == 200, f"Expected 200 for flag_type={flag_type}"

    @pytest.mark.asyncio
    async def test_returns_422_for_invalid_flag_type(self, client: AsyncClient) -> None:
        """An unrecognised flag_type returns 422 Unprocessable Entity."""
        await _promote_test_user_to_instructor()

        resp = await client.post(
            f"/api/instructor/students/{_STUDENT_ID}/flags",
            json={"flag_type": "nonsense", "description": "Should fail"},
        )

        assert resp.status_code == 422
        assert "flag_type" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_flag_persisted_in_db(self, client: AsyncClient) -> None:
        """Created flag is retrievable from the database."""
        await _promote_test_user_to_instructor()

        resp = await client.post(
            f"/api/instructor/students/{_STUDENT_ID}/flags",
            json={"flag_type": "safety", "description": "Missed apex consistently"},
        )
        assert resp.status_code == 200
        flag_id = resp.json()["id"]

        async with _test_session_factory() as session:
            result = await session.execute(select(StudentFlag).where(StudentFlag.id == flag_id))
            flag = result.scalar_one_or_none()

        assert flag is not None
        assert flag.student_id == _STUDENT_ID
        assert flag.flag_type == "safety"
        assert flag.auto_generated is False

    @pytest.mark.asyncio
    async def test_flag_appears_in_subsequent_get_flags(self, client: AsyncClient) -> None:
        """A created flag shows up in GET /students/{id}/flags."""
        await _promote_test_user_to_instructor()

        await client.post(
            f"/api/instructor/students/{_STUDENT_ID}/flags",
            json={"flag_type": "attention", "description": "Follow-up check"},
        )

        get_resp = await client.get(f"/api/instructor/students/{_STUDENT_ID}/flags")
        flags = get_resp.json()["flags"]
        descriptions = [f["description"] for f in flags]
        assert "Follow-up check" in descriptions

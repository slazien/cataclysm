"""DB-level tests for the CoachingFeedback model."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import CoachingFeedback
from backend.tests.conftest import _test_session_factory


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh async session from the test factory."""
    async with _test_session_factory() as session:
        yield session


class TestCoachingFeedbackCreate:
    @pytest.mark.asyncio
    async def test_create_and_read(self, db_session: AsyncSession) -> None:
        """A CoachingFeedback can be inserted and read back."""
        fb = CoachingFeedback(
            session_id="sess-1",
            user_id="user-1",
            section="summary",
            rating=1,
        )
        db_session.add(fb)
        await db_session.commit()

        result = await db_session.execute(
            select(CoachingFeedback).where(CoachingFeedback.session_id == "sess-1")
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].rating == 1
        assert rows[0].section == "summary"
        assert rows[0].comment is None
        assert rows[0].created_at is not None

    @pytest.mark.asyncio
    async def test_create_with_comment(self, db_session: AsyncSession) -> None:
        """Feedback can include an optional comment."""
        fb = CoachingFeedback(
            session_id="sess-1",
            user_id="user-1",
            section="patterns",
            rating=-1,
            comment="The advice about trail braking was incorrect.",
        )
        db_session.add(fb)
        await db_session.commit()

        result = await db_session.execute(
            select(CoachingFeedback).where(CoachingFeedback.section == "patterns")
        )
        row = result.scalar_one()
        assert row.rating == -1
        assert row.comment == "The advice about trail braking was incorrect."

    @pytest.mark.asyncio
    async def test_multiple_sections(self, db_session: AsyncSession) -> None:
        """Same user can rate different sections of the same session."""
        db_session.add(CoachingFeedback(session_id="s1", user_id="u1", section="summary", rating=1))
        db_session.add(
            CoachingFeedback(
                session_id="s1",
                user_id="u1",
                section="corner_3",
                rating=-1,
                comment="Bad advice",
            )
        )
        await db_session.commit()

        result = await db_session.execute(
            select(CoachingFeedback).where(CoachingFeedback.session_id == "s1")
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        sections = {r.section for r in rows}
        assert sections == {"summary", "corner_3"}

    @pytest.mark.asyncio
    async def test_different_users_same_section(self, db_session: AsyncSession) -> None:
        """Different users can rate the same section of the same session."""
        db_session.add(
            CoachingFeedback(session_id="s1", user_id="user-a", section="summary", rating=1)
        )
        db_session.add(
            CoachingFeedback(session_id="s1", user_id="user-b", section="summary", rating=-1)
        )
        await db_session.commit()

        result = await db_session.execute(
            select(CoachingFeedback).where(CoachingFeedback.session_id == "s1")
        )
        rows = result.scalars().all()
        assert len(rows) == 2


class TestCoachingFeedbackConstraints:
    @pytest.mark.asyncio
    async def test_unique_constraint(self, db_session: AsyncSession) -> None:
        """Duplicate (session_id, user_id, section) raises IntegrityError."""
        fb1 = CoachingFeedback(session_id="s1", user_id="u1", section="summary", rating=1)
        db_session.add(fb1)
        await db_session.commit()

        fb2 = CoachingFeedback(session_id="s1", user_id="u1", section="summary", rating=-1)
        db_session.add(fb2)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_thumbs_down_rating(self, db_session: AsyncSession) -> None:
        """Rating of -1 (thumbs down) is accepted."""
        fb = CoachingFeedback(session_id="s1", user_id="u1", section="drills", rating=-1)
        db_session.add(fb)
        await db_session.commit()

        result = await db_session.execute(
            select(CoachingFeedback).where(CoachingFeedback.section == "drills")
        )
        assert result.scalar_one().rating == -1

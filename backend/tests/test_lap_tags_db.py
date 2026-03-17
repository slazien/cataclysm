"""DB-level tests for the LapTag model (composite PK)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import LapTag
from backend.tests.conftest import _test_session_factory


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh async session from the test factory."""
    async with _test_session_factory() as session:
        yield session


class TestLapTagCreate:
    @pytest.mark.asyncio
    async def test_create_and_read(self, db_session: AsyncSession) -> None:
        """A LapTag can be inserted and read back."""
        tag = LapTag(session_id="sess-1", lap_number=3, tag="traffic")
        db_session.add(tag)
        await db_session.commit()

        result = await db_session.execute(
            select(LapTag).where(
                LapTag.session_id == "sess-1",
                LapTag.lap_number == 3,
                LapTag.tag == "traffic",
            )
        )
        loaded = result.scalar_one()
        assert loaded.session_id == "sess-1"
        assert loaded.lap_number == 3
        assert loaded.tag == "traffic"
        assert loaded.created_at is not None

    @pytest.mark.asyncio
    async def test_multiple_tags_per_lap(self, db_session: AsyncSession) -> None:
        """Multiple distinct tags can be attached to the same (session, lap)."""
        tags = [
            LapTag(session_id="sess-2", lap_number=5, tag="traffic"),
            LapTag(session_id="sess-2", lap_number=5, tag="off_track"),
            LapTag(session_id="sess-2", lap_number=5, tag="mechanical"),
        ]
        db_session.add_all(tags)
        await db_session.commit()

        result = await db_session.execute(
            select(LapTag).where(
                LapTag.session_id == "sess-2",
                LapTag.lap_number == 5,
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 3
        assert {r.tag for r in rows} == {"traffic", "off_track", "mechanical"}

    @pytest.mark.asyncio
    async def test_same_tag_different_laps(self, db_session: AsyncSession) -> None:
        """Same tag applied to different laps of the same session is allowed."""
        tags = [
            LapTag(session_id="sess-3", lap_number=1, tag="traffic"),
            LapTag(session_id="sess-3", lap_number=2, tag="traffic"),
            LapTag(session_id="sess-3", lap_number=7, tag="traffic"),
        ]
        db_session.add_all(tags)
        await db_session.commit()

        result = await db_session.execute(
            select(LapTag).where(
                LapTag.session_id == "sess-3",
                LapTag.tag == "traffic",
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 3
        assert {r.lap_number for r in rows} == {1, 2, 7}

    @pytest.mark.asyncio
    async def test_same_tag_different_sessions(self, db_session: AsyncSession) -> None:
        """Same (lap, tag) pair under different session IDs is allowed."""
        tags = [
            LapTag(session_id="sess-A", lap_number=1, tag="traffic"),
            LapTag(session_id="sess-B", lap_number=1, tag="traffic"),
        ]
        db_session.add_all(tags)
        await db_session.commit()

        result = await db_session.execute(select(LapTag).where(LapTag.tag == "traffic"))
        rows = result.scalars().all()
        assert len(rows) == 2
        assert {r.session_id for r in rows} == {"sess-A", "sess-B"}


class TestLapTagCompositePK:
    @pytest.mark.asyncio
    async def test_duplicate_composite_pk_raises(self, db_session: AsyncSession) -> None:
        """Inserting identical (session_id, lap_number, tag) raises IntegrityError."""
        tag1 = LapTag(session_id="sess-dup", lap_number=4, tag="traffic")
        db_session.add(tag1)
        await db_session.commit()

        tag2 = LapTag(session_id="sess-dup", lap_number=4, tag="traffic")
        db_session.add(tag2)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_partial_pk_match_is_allowed(self, db_session: AsyncSession) -> None:
        """Rows sharing only part of the composite PK do not conflict."""
        # Same session_id + lap_number, different tag — allowed
        t1 = LapTag(session_id="sess-pk", lap_number=2, tag="traffic")
        t2 = LapTag(session_id="sess-pk", lap_number=2, tag="slow")
        # Same session_id + tag, different lap_number — allowed
        t3 = LapTag(session_id="sess-pk", lap_number=3, tag="traffic")
        db_session.add_all([t1, t2, t3])
        # Must not raise
        await db_session.commit()

        result = await db_session.execute(select(LapTag).where(LapTag.session_id == "sess-pk"))
        rows = result.scalars().all()
        assert len(rows) == 3

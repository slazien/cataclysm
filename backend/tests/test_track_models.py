"""Tests for track data pipeline v2 DB models."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import Track
from backend.tests.conftest import _test_session_factory


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh async session from the test factory."""
    async with _test_session_factory() as session:
        yield session


class TestTrackModel:
    @pytest.mark.asyncio
    async def test_create_track(self, db_session: AsyncSession) -> None:
        track = Track(
            slug="barber-motorsports-park",
            name="Barber Motorsports Park",
            country="US",
            center_lat=33.5302,
            center_lon=-86.6215,
            length_m=3662.4,
            quality_tier=3,
            status="published",
            source="seed",
        )
        db_session.add(track)
        await db_session.commit()

        result = await db_session.execute(
            select(Track).where(Track.slug == "barber-motorsports-park")
        )
        loaded = result.scalar_one()
        assert loaded.name == "Barber Motorsports Park"
        assert loaded.quality_tier == 3

    @pytest.mark.asyncio
    async def test_slug_unique_constraint(self, db_session: AsyncSession) -> None:
        t1 = Track(slug="test-track", name="Test 1", source="manual")
        t2 = Track(slug="test-track", name="Test 2", source="manual")
        db_session.add(t1)
        await db_session.commit()
        db_session.add(t2)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_defaults(self, db_session: AsyncSession) -> None:
        track = Track(slug="defaults-test", name="Defaults", source="manual")
        db_session.add(track)
        await db_session.commit()
        await db_session.refresh(track)
        assert track.quality_tier == 1
        assert track.status == "draft"
        assert track.aliases == []

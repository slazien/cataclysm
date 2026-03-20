"""Tests for seeding existing track_db.py tracks into the database."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.services.track_seed import seed_tracks_from_hardcoded
from backend.api.services.track_store import (
    get_corners_for_track,
    get_landmarks_for_track,
    get_track_by_slug,
)
from backend.tests.conftest import _test_session_factory


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh async session from the test factory."""
    async with _test_session_factory() as session:
        yield session


class TestSeedTracks:
    @pytest.mark.asyncio
    async def test_seeds_all_tracks(self, db_session: AsyncSession) -> None:
        count = await seed_tracks_from_hardcoded(db_session)
        assert count == 7

    @pytest.mark.asyncio
    async def test_barber_seeded_correctly(self, db_session: AsyncSession) -> None:
        await seed_tracks_from_hardcoded(db_session)
        track = await get_track_by_slug(db_session, "barber-motorsports-park")
        assert track is not None
        assert track.name == "Barber Motorsports Park"
        assert track.quality_tier == 3
        assert track.status == "published"
        assert track.center_lat == pytest.approx(33.5302)

    @pytest.mark.asyncio
    async def test_barber_corners_seeded(self, db_session: AsyncSession) -> None:
        await seed_tracks_from_hardcoded(db_session)
        track = await get_track_by_slug(db_session, "barber-motorsports-park")
        assert track is not None
        corners = await get_corners_for_track(db_session, track.id)
        assert len(corners) == 16
        t5 = [c for c in corners if c.number == 5][0]
        assert t5.name == "Charlotte's Web"
        assert t5.direction == "right"
        assert t5.corner_type == "hairpin"

    @pytest.mark.asyncio
    async def test_barber_landmarks_seeded(self, db_session: AsyncSession) -> None:
        await seed_tracks_from_hardcoded(db_session)
        track = await get_track_by_slug(db_session, "barber-motorsports-park")
        assert track is not None
        landmarks = await get_landmarks_for_track(db_session, track.id)
        assert len(landmarks) >= 20

    @pytest.mark.asyncio
    async def test_idempotent(self, db_session: AsyncSession) -> None:
        count1 = await seed_tracks_from_hardcoded(db_session)
        count2 = await seed_tracks_from_hardcoded(db_session)
        assert count1 == 7
        assert count2 == 0

    @pytest.mark.asyncio
    async def test_amp_seeded(self, db_session: AsyncSession) -> None:
        await seed_tracks_from_hardcoded(db_session)
        track = await get_track_by_slug(db_session, "atlanta-motorsports-park")
        assert track is not None
        corners = await get_corners_for_track(db_session, track.id)
        assert len(corners) == 16

    @pytest.mark.asyncio
    async def test_roebling_seeded(self, db_session: AsyncSession) -> None:
        await seed_tracks_from_hardcoded(db_session)
        track = await get_track_by_slug(db_session, "roebling-road-raceway")
        assert track is not None
        corners = await get_corners_for_track(db_session, track.id)
        assert len(corners) == 9

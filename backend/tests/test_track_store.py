"""Tests for the track data store service."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.services.track_store import (
    create_track,
    get_all_tracks_from_db,
    get_corners_for_track,
    get_landmarks_for_track,
    get_track_by_slug,
    update_track,
    upsert_corners,
    upsert_landmarks,
)
from backend.tests.conftest import _test_session_factory


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh async session from the test factory."""
    async with _test_session_factory() as session:
        yield session


class TestCreateTrack:
    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, db_session: AsyncSession) -> None:
        track = await create_track(
            db=db_session,
            slug="test-track",
            name="Test Track",
            source="manual",
            country="US",
            center_lat=33.53,
            center_lon=-86.62,
            length_m=3662.4,
        )
        assert track.slug == "test-track"
        loaded = await get_track_by_slug(db_session, "test-track")
        assert loaded is not None
        assert loaded.name == "Test Track"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, db_session: AsyncSession) -> None:
        result = await get_track_by_slug(db_session, "does-not-exist")
        assert result is None


class TestGetAllTracks:
    @pytest.mark.asyncio
    async def test_returns_all(self, db_session: AsyncSession) -> None:
        await create_track(db=db_session, slug="a", name="A", source="manual")
        await create_track(db=db_session, slug="b", name="B", source="manual")
        tracks = await get_all_tracks_from_db(db_session)
        assert len(tracks) >= 2


class TestUpdateTrack:
    @pytest.mark.asyncio
    async def test_update_quality_tier(self, db_session: AsyncSession) -> None:
        await create_track(db=db_session, slug="upd", name="Upd", source="manual")
        updated = await update_track(db_session, "upd", quality_tier=3, status="published")
        assert updated is not None
        assert updated.quality_tier == 3
        assert updated.status == "published"


class TestUpsertCorners:
    @pytest.mark.asyncio
    async def test_upsert_creates_corners(self, db_session: AsyncSession) -> None:
        track = await create_track(db=db_session, slug="corners", name="Corners", source="manual")
        await upsert_corners(
            db_session,
            track.id,
            [
                {"number": 1, "name": "T1", "fraction": 0.05, "direction": "left"},
                {"number": 2, "name": "T2", "fraction": 0.20, "direction": "right"},
            ],
        )
        loaded = await get_corners_for_track(db_session, track.id)
        assert len(loaded) == 2
        assert loaded[0].number == 1

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing(self, db_session: AsyncSession) -> None:
        track = await create_track(db=db_session, slug="replace", name="Replace", source="manual")
        await upsert_corners(db_session, track.id, [{"number": 1, "fraction": 0.05}])
        await upsert_corners(
            db_session,
            track.id,
            [
                {"number": 1, "fraction": 0.06, "name": "Updated"},
                {"number": 2, "fraction": 0.20},
            ],
        )
        loaded = await get_corners_for_track(db_session, track.id)
        assert len(loaded) == 2
        assert loaded[0].fraction == pytest.approx(0.06)


class TestUpsertLandmarks:
    @pytest.mark.asyncio
    async def test_upsert_creates_landmarks(self, db_session: AsyncSession) -> None:
        track = await create_track(db=db_session, slug="lm", name="LM", source="manual")
        await upsert_landmarks(
            db_session,
            track.id,
            [
                {
                    "name": "S/F gantry",
                    "distance_m": 0.0,
                    "landmark_type": "structure",
                    "source": "manual",
                },
            ],
        )
        loaded = await get_landmarks_for_track(db_session, track.id)
        assert len(loaded) == 1
        assert loaded[0].name == "S/F gantry"

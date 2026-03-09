"""Tests for track data pipeline v2 DB models."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import (
    Track,
    TrackCornerV2,
    TrackElevationProfile,
    TrackEnrichmentLog,
    TrackLandmark,
)
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


# ---------------------------------------------------------------------------
# Helper to create a parent track for FK-dependent tests
# ---------------------------------------------------------------------------


async def _make_track(db_session: AsyncSession, slug: str = "test-track") -> Track:
    """Insert and return a minimal Track row."""
    track = Track(slug=slug, name="Test Track", source="manual")
    db_session.add(track)
    await db_session.commit()
    await db_session.refresh(track)
    return track


# ---------------------------------------------------------------------------
# TrackCornerV2
# ---------------------------------------------------------------------------


class TestTrackCornerV2Model:
    @pytest.mark.asyncio
    async def test_create_corner(self, db_session: AsyncSession) -> None:
        track = await _make_track(db_session, slug="corner-test")
        corner = TrackCornerV2(track_id=track.id, number=1, fraction=0.12)
        db_session.add(corner)
        await db_session.commit()

        result = await db_session.execute(
            select(TrackCornerV2).where(TrackCornerV2.track_id == track.id)
        )
        loaded = result.scalar_one()
        assert loaded.number == 1
        assert loaded.fraction == pytest.approx(0.12)

    @pytest.mark.asyncio
    async def test_unique_track_number(self, db_session: AsyncSession) -> None:
        track = await _make_track(db_session, slug="uniq-corner")
        db_session.add(TrackCornerV2(track_id=track.id, number=5, fraction=0.5))
        await db_session.commit()
        db_session.add(TrackCornerV2(track_id=track.id, number=5, fraction=0.51))
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_cascade_delete(self, db_session: AsyncSession) -> None:
        track = await _make_track(db_session, slug="cascade-corner")
        db_session.add(TrackCornerV2(track_id=track.id, number=1, fraction=0.1))
        db_session.add(TrackCornerV2(track_id=track.id, number=2, fraction=0.3))
        await db_session.commit()

        await db_session.delete(track)
        await db_session.commit()

        result = await db_session.execute(
            select(TrackCornerV2).where(TrackCornerV2.track_id == track.id)
        )
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_all_officialcorner_fields_present(self, db_session: AsyncSession) -> None:
        track = await _make_track(db_session, slug="full-corner")
        corner = TrackCornerV2(
            track_id=track.id,
            number=5,
            name="Turn 5",
            fraction=0.45,
            lat=33.5302,
            lon=-86.6215,
            character="brake",
            direction="left",
            corner_type="hairpin",
            elevation_trend="downhill",
            camber="off-camber",
            blind=True,
            coaching_notes="Trailbrake deep into the apex",
            auto_detected=False,
            confidence=0.95,
            detection_method="manual",
        )
        db_session.add(corner)
        await db_session.commit()
        await db_session.refresh(corner)

        assert corner.character == "brake"
        assert corner.blind is True
        assert corner.coaching_notes == "Trailbrake deep into the apex"
        assert corner.auto_detected is False
        assert corner.confidence == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# TrackLandmark
# ---------------------------------------------------------------------------


class TestTrackLandmarkModel:
    @pytest.mark.asyncio
    async def test_create_landmark(self, db_session: AsyncSession) -> None:
        track = await _make_track(db_session, slug="landmark-test")
        lm = TrackLandmark(
            track_id=track.id,
            name="Start/Finish Gantry",
            distance_m=0.0,
            landmark_type="gantry",
            source="manual",
        )
        db_session.add(lm)
        await db_session.commit()

        result = await db_session.execute(
            select(TrackLandmark).where(TrackLandmark.track_id == track.id)
        )
        loaded = result.scalar_one()
        assert loaded.name == "Start/Finish Gantry"
        assert loaded.landmark_type == "gantry"


# ---------------------------------------------------------------------------
# TrackElevationProfile
# ---------------------------------------------------------------------------


class TestTrackElevationProfileModel:
    @pytest.mark.asyncio
    async def test_create_profile(self, db_session: AsyncSession) -> None:
        track = await _make_track(db_session, slug="elev-test")
        ep = TrackElevationProfile(
            track_id=track.id,
            source="lidar_3dep",
            accuracy_m=0.5,
            distances_m=[0.0, 100.0, 200.0],
            elevations_m=[150.0, 152.3, 148.1],
        )
        db_session.add(ep)
        await db_session.commit()

        result = await db_session.execute(
            select(TrackElevationProfile).where(TrackElevationProfile.track_id == track.id)
        )
        loaded = result.scalar_one()
        assert loaded.source == "lidar_3dep"
        assert len(loaded.distances_m) == 3

    @pytest.mark.asyncio
    async def test_unique_track_source(self, db_session: AsyncSession) -> None:
        track = await _make_track(db_session, slug="elev-uniq")
        db_session.add(
            TrackElevationProfile(
                track_id=track.id,
                source="copernicus",
                distances_m=[0.0],
                elevations_m=[100.0],
            )
        )
        await db_session.commit()
        db_session.add(
            TrackElevationProfile(
                track_id=track.id,
                source="copernicus",
                distances_m=[0.0],
                elevations_m=[101.0],
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()


# ---------------------------------------------------------------------------
# TrackEnrichmentLog
# ---------------------------------------------------------------------------


class TestTrackEnrichmentLogModel:
    @pytest.mark.asyncio
    async def test_create_log_entry(self, db_session: AsyncSession) -> None:
        track = await _make_track(db_session, slug="log-test")
        log = TrackEnrichmentLog(
            track_id=track.id,
            step="osm_import",
            status="success",
            details={"nodes": 142, "duration_s": 1.3},
        )
        db_session.add(log)
        await db_session.commit()

        result = await db_session.execute(
            select(TrackEnrichmentLog).where(TrackEnrichmentLog.track_id == track.id)
        )
        loaded = result.scalar_one()
        assert loaded.step == "osm_import"
        assert loaded.status == "success"
        assert loaded.details["nodes"] == 142

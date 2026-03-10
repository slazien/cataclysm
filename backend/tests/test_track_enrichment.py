"""Tests for the track auto-enrichment orchestrator."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import TrackEnrichmentLog
from backend.api.services.track_enrichment import enrich_track
from backend.api.services.track_store import create_track
from backend.tests.conftest import _test_session_factory


@dataclass
class _MockElevationResult:
    altitude_m: np.ndarray
    source: str
    accuracy_m: float


@dataclass
class _MockCorner:
    number: int
    entry_distance_m: float
    exit_distance_m: float
    apex_distance_m: float
    min_speed_mps: float
    brake_point_m: float | None
    peak_brake_g: float | None
    throttle_commit_m: float | None
    apex_type: str
    apex_lat: float | None = None
    apex_lon: float | None = None
    peak_curvature: float | None = None
    direction: str | None = None
    character: str | None = None
    detection_method: str | None = "heading_rate"
    name: str | None = None


@dataclass
class _MockClassification:
    corner_type: str
    confidence: float
    reasoning: str


@dataclass(frozen=True)
class _MockLandmark:
    name: str
    distance_m: float
    landmark_type: _MockLandmarkType
    lat: float | None = None
    lon: float | None = None
    description: str | None = None


class _MockLandmarkType:
    def __init__(self, value: str) -> None:
        self.value = value


def _make_circle_latlons(n: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """Generate lat/lon arrays forming a circle (simulates a circuit)."""
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    center_lat, center_lon = 33.5, -86.6  # Approximate Barber location
    radius_deg = 0.005
    lats = center_lat + radius_deg * np.cos(angles)
    lons = center_lon + radius_deg * np.sin(angles)
    return lats, lons


def _make_sample_corners() -> list[_MockCorner]:
    return [
        _MockCorner(
            number=1,
            entry_distance_m=100.0,
            exit_distance_m=200.0,
            apex_distance_m=150.0,
            min_speed_mps=20.0,
            brake_point_m=80.0,
            peak_brake_g=-1.2,
            throttle_commit_m=170.0,
            apex_type="mid",
            apex_lat=33.501,
            apex_lon=-86.601,
            peak_curvature=0.015,
            direction="left",
            character="brake",
        ),
        _MockCorner(
            number=2,
            entry_distance_m=400.0,
            exit_distance_m=500.0,
            apex_distance_m=450.0,
            min_speed_mps=25.0,
            brake_point_m=380.0,
            peak_brake_g=-0.8,
            throttle_commit_m=470.0,
            apex_type="mid",
            apex_lat=33.502,
            apex_lon=-86.602,
            peak_curvature=0.008,
            direction="right",
            character="lift",
        ),
    ]


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh async session from the test factory."""
    async with _test_session_factory() as session:
        yield session


class TestEnrichTrack:
    """Full enrichment pipeline tests."""

    @pytest.mark.asyncio
    async def test_enrichment_runs_all_steps(self, db_session: AsyncSession) -> None:
        """Enrichment runs all steps and returns correct summary."""
        track = await create_track(
            db=db_session, slug="test-enrich", name="Test Track", source="test"
        )
        lats, lons = _make_circle_latlons(100)
        corners = _make_sample_corners()
        elevation = _MockElevationResult(
            altitude_m=np.linspace(100, 120, 100),
            source="usgs_3dep",
            accuracy_m=0.1,
        )
        classification = _MockClassification(
            corner_type="sweeper", confidence=0.85, reasoning="test"
        )
        brake_lm = _MockLandmark(
            name="T1 3 board",
            distance_m=50.0,
            landmark_type=_MockLandmarkType("brake_board"),
        )

        with (
            patch(
                "backend.api.services.track_enrichment.detect_corners_adaptive",
                return_value=corners,
            ),
            patch(
                "backend.api.services.track_enrichment.fetch_best_elevation",
                new_callable=AsyncMock,
                return_value=elevation,
            ),
            patch(
                "backend.api.services.track_enrichment.classify_corner",
                return_value=classification,
            ),
            patch(
                "backend.api.services.track_enrichment.compute_brake_markers",
                return_value=[brake_lm],
            ),
        ):
            result = await enrich_track(db_session, track.id, lats, lons, track_length_m=3500.0)

        assert result["corners_detected"] == 2
        assert result["elevation_source"] == "usgs_3dep"
        assert result["brake_markers"] == 1
        assert result["steps_logged"] == 4

    @pytest.mark.asyncio
    async def test_enrichment_logs_written(self, db_session: AsyncSession) -> None:
        """Enrichment logs are written to DB for each step."""
        track = await create_track(db=db_session, slug="test-logs", name="Log Track", source="test")
        lats, lons = _make_circle_latlons(50)
        elevation = _MockElevationResult(
            altitude_m=np.linspace(100, 110, 50),
            source="copernicus",
            accuracy_m=4.0,
        )

        with (
            patch(
                "backend.api.services.track_enrichment.detect_corners_adaptive",
                return_value=[],
            ),
            patch(
                "backend.api.services.track_enrichment.fetch_best_elevation",
                new_callable=AsyncMock,
                return_value=elevation,
            ),
        ):
            await enrich_track(db_session, track.id, lats, lons)

        logs = (
            (
                await db_session.execute(
                    select(TrackEnrichmentLog).where(TrackEnrichmentLog.track_id == track.id)
                )
            )
            .scalars()
            .all()
        )

        step_names = {log.step for log in logs}
        assert "corner_detect" in step_names
        assert "elevation" in step_names
        # classification and brake_markers also logged
        assert len(logs) >= 3

    @pytest.mark.asyncio
    async def test_corners_persisted(self, db_session: AsyncSession) -> None:
        """Detected corners are persisted via upsert_corners."""
        track = await create_track(
            db=db_session, slug="test-persist", name="Persist Track", source="test"
        )
        lats, lons = _make_circle_latlons(80)
        corners = _make_sample_corners()
        elevation = _MockElevationResult(
            altitude_m=np.linspace(100, 110, 80),
            source="gps_fallback",
            accuracy_m=3.0,
        )

        with (
            patch(
                "backend.api.services.track_enrichment.detect_corners_adaptive",
                return_value=corners,
            ),
            patch(
                "backend.api.services.track_enrichment.fetch_best_elevation",
                new_callable=AsyncMock,
                return_value=elevation,
            ),
            patch(
                "backend.api.services.track_enrichment.classify_corner",
                return_value=_MockClassification("hairpin", 0.9, "test"),
            ),
            patch(
                "backend.api.services.track_enrichment.compute_brake_markers",
                return_value=[],
            ),
        ):
            result = await enrich_track(db_session, track.id, lats, lons, track_length_m=2000.0)

        assert result["corners_detected"] == 2

        # Verify corners actually in DB
        from backend.api.services.track_store import get_corners_for_track

        saved = await get_corners_for_track(db_session, track.id)
        assert len(saved) == 2
        assert saved[0].number == 1
        assert saved[0].corner_type == "hairpin"
        assert saved[0].auto_detected is True

    @pytest.mark.asyncio
    async def test_error_in_one_step_others_still_run(self, db_session: AsyncSession) -> None:
        """If corner detection fails, elevation and subsequent steps still execute."""
        track = await create_track(
            db=db_session, slug="test-error", name="Error Track", source="test"
        )
        lats, lons = _make_circle_latlons(60)
        elevation = _MockElevationResult(
            altitude_m=np.linspace(200, 210, 60),
            source="copernicus",
            accuracy_m=4.0,
        )

        with (
            patch(
                "backend.api.services.track_enrichment.detect_corners_adaptive",
                side_effect=RuntimeError("detector crashed"),
            ),
            patch(
                "backend.api.services.track_enrichment.fetch_best_elevation",
                new_callable=AsyncMock,
                return_value=elevation,
            ),
        ):
            result = await enrich_track(db_session, track.id, lats, lons)

        # Corner detection failed but elevation still ran
        assert result["corners_detected"] == 0
        assert result["elevation_source"] == "copernicus"
        # steps_logged should include error log for corner_detect + success logs for others
        assert result["steps_logged"] >= 3

        # Check logs contain the error step
        logs = (
            (
                await db_session.execute(
                    select(TrackEnrichmentLog).where(TrackEnrichmentLog.track_id == track.id)
                )
            )
            .scalars()
            .all()
        )
        error_logs = [log for log in logs if log.status == "error"]
        assert len(error_logs) >= 1
        assert error_logs[0].step == "corner_detect"

    @pytest.mark.asyncio
    async def test_empty_centerline_returns_early(self, db_session: AsyncSession) -> None:
        """Centerline with < 3 points returns early with error."""
        track = await create_track(
            db=db_session, slug="test-empty", name="Empty Track", source="test"
        )
        lats = np.array([33.5, 33.501])
        lons = np.array([-86.6, -86.601])

        result = await enrich_track(db_session, track.id, lats, lons)

        assert result["error"] == "insufficient_points"
        assert result["corners_detected"] == 0
        assert result["steps_logged"] == 1

        # Verify validation error logged
        logs = (
            (
                await db_session.execute(
                    select(TrackEnrichmentLog).where(TrackEnrichmentLog.track_id == track.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(logs) == 1
        assert logs[0].step == "validation"
        assert logs[0].status == "error"

    @pytest.mark.asyncio
    async def test_elevation_error_still_continues(self, db_session: AsyncSession) -> None:
        """If elevation fetch fails, brake markers still attempt to run."""
        track = await create_track(
            db=db_session, slug="test-elev-err", name="Elev Error", source="test"
        )
        lats, lons = _make_circle_latlons(70)
        corners = _make_sample_corners()

        with (
            patch(
                "backend.api.services.track_enrichment.detect_corners_adaptive",
                return_value=corners,
            ),
            patch(
                "backend.api.services.track_enrichment.fetch_best_elevation",
                new_callable=AsyncMock,
                side_effect=ConnectionError("network error"),
            ),
            patch(
                "backend.api.services.track_enrichment.classify_corner",
                return_value=_MockClassification("sweeper", 0.7, "test"),
            ),
            patch(
                "backend.api.services.track_enrichment.compute_brake_markers",
                return_value=[],
            ),
        ):
            result = await enrich_track(db_session, track.id, lats, lons, track_length_m=2500.0)

        assert result["corners_detected"] == 2
        assert result["elevation_source"] is None
        assert result["steps_logged"] == 4

    @pytest.mark.asyncio
    async def test_no_corners_skips_brake_markers(self, db_session: AsyncSession) -> None:
        """When no corners detected, brake markers step is skipped."""
        track = await create_track(
            db=db_session, slug="test-nocorners", name="No Corners", source="test"
        )
        lats, lons = _make_circle_latlons(40)
        elevation = _MockElevationResult(
            altitude_m=np.linspace(100, 105, 40),
            source="gps_fallback",
            accuracy_m=3.0,
        )

        with (
            patch(
                "backend.api.services.track_enrichment.detect_corners_adaptive",
                return_value=[],
            ),
            patch(
                "backend.api.services.track_enrichment.fetch_best_elevation",
                new_callable=AsyncMock,
                return_value=elevation,
            ),
        ):
            result = await enrich_track(db_session, track.id, lats, lons)

        assert result["corners_detected"] == 0
        assert result["brake_markers"] == 0

        logs = (
            (
                await db_session.execute(
                    select(TrackEnrichmentLog).where(TrackEnrichmentLog.track_id == track.id)
                )
            )
            .scalars()
            .all()
        )
        brake_log = next(log for log in logs if log.step == "brake_markers")
        assert brake_log.status == "skipped"

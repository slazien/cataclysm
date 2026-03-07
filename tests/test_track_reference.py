"""Tests for cataclysm.track_reference — canonical track curvature map."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from cataclysm.curvature import CurvatureResult
from cataclysm.track_db import TrackLayout
from cataclysm.track_reference import (
    GPS_QUALITY_IMPROVEMENT_THRESHOLD,
    TrackReference,
    align_reference_to_session,
    build_track_reference,
    get_track_reference,
    maybe_update_track_reference,
    track_slug_from_layout,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CENTER_LAT: float = 33.53
CENTER_LON: float = -86.62


def _make_layout(name: str = "Barber Motorsports Park") -> TrackLayout:
    return TrackLayout(name=name, corners=[])


def _circle_lap_df(
    radius_m: float = 100.0,
    n: int = 500,
    fraction: float = 0.8,
    noise_m: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a lap DataFrame tracing a circular arc."""
    theta = np.linspace(0, 2 * np.pi * fraction, n)
    x = radius_m * np.cos(theta)
    y = radius_m * np.sin(theta)

    if noise_m > 0.0:
        rng = np.random.default_rng(seed)
        x = x + rng.normal(0, noise_m, n)
        y = y + rng.normal(0, noise_m, n)

    cos_lat = np.cos(np.radians(CENTER_LAT))
    lat = CENTER_LAT + y / 111320.0
    lon = CENTER_LON + x / (111320.0 * cos_lat)
    distance = radius_m * theta

    return pd.DataFrame(
        {
            "lat": lat,
            "lon": lon,
            "lap_distance_m": distance,
            "speed_mps": np.full(n, 30.0),
        }
    )


@dataclass
class FakeProcessedSession:
    """Minimal stand-in for ProcessedSession."""

    resampled_laps: dict[int, pd.DataFrame] = field(default_factory=dict)
    best_lap: int = 1
    lap_summaries: list[object] = field(default_factory=list)


def _make_session(n_laps: int = 5) -> FakeProcessedSession:
    laps = {}
    for i in range(1, n_laps + 1):
        laps[i] = _circle_lap_df(radius_m=100.0, n=500, fraction=0.8, seed=100 + i)
    return FakeProcessedSession(resampled_laps=laps, best_lap=1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTrackSlug:
    def test_basic_slug(self) -> None:
        layout = _make_layout("Barber Motorsports Park")
        assert track_slug_from_layout(layout) == "barber-motorsports-park"

    def test_special_characters(self) -> None:
        layout = _make_layout("Road Atlanta (Full Course)")
        assert track_slug_from_layout(layout) == "road-atlanta-full-course"

    def test_numbers(self) -> None:
        layout = _make_layout("Circuit of the Americas - F1")
        assert track_slug_from_layout(layout) == "circuit-of-the-americas-f1"

    def test_extra_whitespace(self) -> None:
        layout = _make_layout("  Spa Francorchamps  ")
        assert track_slug_from_layout(layout) == "spa-francorchamps"


class TestBuildAndLoadReference:
    def test_build_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Build a reference, save it, reload it, verify all fields match."""
        layout = _make_layout()
        session = _make_session(n_laps=5)

        with patch("cataclysm.track_reference._DATA_DIR", tmp_path):
            ref = build_track_reference(
                layout,
                session,  # type: ignore[arg-type]
                coaching_laps=[1, 2, 3, 4, 5],
                session_id="test-session-001",
                gps_quality_score=85.0,
            )

            assert ref.track_slug == "barber-motorsports-park"
            assert ref.n_laps_averaged == 5
            assert ref.gps_quality_score == 85.0
            assert ref.built_from_session_id == "test-session-001"
            assert ref.track_length_m > 0
            assert len(ref.curvature_result.curvature) > 0

            # Load from disk
            loaded = get_track_reference(layout)
            assert loaded is not None
            assert loaded.track_slug == ref.track_slug
            assert loaded.n_laps_averaged == ref.n_laps_averaged
            assert loaded.gps_quality_score == ref.gps_quality_score
            assert loaded.built_from_session_id == ref.built_from_session_id
            np.testing.assert_allclose(
                loaded.curvature_result.distance_m,
                ref.curvature_result.distance_m,
                atol=1e-6,
            )
            np.testing.assert_allclose(
                loaded.curvature_result.curvature,
                ref.curvature_result.curvature,
                atol=1e-6,
            )

    def test_build_few_laps_uses_single(self, tmp_path: Path) -> None:
        """With < 3 coaching laps, build uses single-lap curvature."""
        layout = _make_layout()
        session = _make_session(n_laps=2)

        with patch("cataclysm.track_reference._DATA_DIR", tmp_path):
            ref = build_track_reference(
                layout,
                session,  # type: ignore[arg-type]
                coaching_laps=[1, 2],
                session_id="test-session-002",
                gps_quality_score=80.0,
            )
            assert ref.n_laps_averaged == 1

    def test_build_with_lidar(self, tmp_path: Path) -> None:
        """LIDAR elevation is stored and loaded correctly."""
        layout = _make_layout()
        session = _make_session(n_laps=3)
        lidar = np.linspace(200.0, 210.0, 500)

        with patch("cataclysm.track_reference._DATA_DIR", tmp_path):
            ref = build_track_reference(
                layout,
                session,  # type: ignore[arg-type]
                coaching_laps=[1, 2, 3],
                session_id="test-session-003",
                gps_quality_score=90.0,
                lidar_alt=lidar,
            )
            assert ref.elevation_m is not None
            # LIDAR is interpolated onto the curvature distance grid,
            # so length matches curvature, not the original LIDAR array.
            assert len(ref.elevation_m) == len(ref.curvature_result.distance_m)
            # Interpolated values should span the same range as the original.
            np.testing.assert_allclose(ref.elevation_m[0], 200.0, atol=0.1)
            np.testing.assert_allclose(ref.elevation_m[-1], 210.0, atol=0.1)

            loaded = get_track_reference(layout)
            assert loaded is not None
            assert loaded.elevation_m is not None
            assert len(loaded.elevation_m) == len(loaded.curvature_result.distance_m)
            np.testing.assert_allclose(loaded.elevation_m, ref.elevation_m, atol=1e-6)

    def test_no_reference_returns_none(self, tmp_path: Path) -> None:
        """get_track_reference returns None when no .npz exists."""
        layout = _make_layout("Nonexistent Track")
        with patch("cataclysm.track_reference._DATA_DIR", tmp_path):
            assert get_track_reference(layout) is None


class TestMaybeUpdateReference:
    def test_creates_if_none_exists(self, tmp_path: Path) -> None:
        layout = _make_layout()
        session = _make_session(n_laps=5)

        with patch("cataclysm.track_reference._DATA_DIR", tmp_path):
            result = maybe_update_track_reference(
                layout,
                session,  # type: ignore[arg-type]
                coaching_laps=[1, 2, 3, 4, 5],
                session_id="new-session",
                gps_quality_score=75.0,
            )
            assert result is not None
            assert result.gps_quality_score == 75.0

    def test_replaces_on_better_quality(self, tmp_path: Path) -> None:
        layout = _make_layout()
        session = _make_session(n_laps=5)

        with patch("cataclysm.track_reference._DATA_DIR", tmp_path):
            # Build initial with quality 70
            build_track_reference(
                layout,
                session,  # type: ignore[arg-type]
                coaching_laps=[1, 2, 3, 4, 5],
                session_id="session-old",
                gps_quality_score=70.0,
            )

            # Attempt with quality 76 (>= 5 improvement) — should replace
            result = maybe_update_track_reference(
                layout,
                session,  # type: ignore[arg-type]
                coaching_laps=[1, 2, 3, 4, 5],
                session_id="session-better",
                gps_quality_score=70.0 + GPS_QUALITY_IMPROVEMENT_THRESHOLD,
            )
            assert result is not None
            assert result.built_from_session_id == "session-better"

    def test_keeps_on_worse_quality(self, tmp_path: Path) -> None:
        layout = _make_layout()
        session = _make_session(n_laps=5)

        with patch("cataclysm.track_reference._DATA_DIR", tmp_path):
            build_track_reference(
                layout,
                session,  # type: ignore[arg-type]
                coaching_laps=[1, 2, 3, 4, 5],
                session_id="session-good",
                gps_quality_score=90.0,
            )

            # Attempt with quality 92 (< 5 improvement) — should keep
            result = maybe_update_track_reference(
                layout,
                session,  # type: ignore[arg-type]
                coaching_laps=[1, 2, 3, 4, 5],
                session_id="session-slightly-better",
                gps_quality_score=92.0,
            )
            assert result is None

            loaded = get_track_reference(layout)
            assert loaded is not None
            assert loaded.built_from_session_id == "session-good"


class TestAlignReferenceToSession:
    def _make_reference(self, n: int = 500) -> TrackReference:
        distance = np.linspace(0, 500.0, n)
        curvature = np.sin(distance / 50.0) * 0.01
        return TrackReference(
            track_slug="test-track",
            curvature_result=CurvatureResult(
                distance_m=distance,
                curvature=curvature,
                abs_curvature=np.abs(curvature),
                heading_rad=np.zeros(n),
                x_smooth=np.zeros(n),
                y_smooth=np.zeros(n),
            ),
            elevation_m=np.linspace(200.0, 220.0, n),
            reference_lats=np.full(n, 33.5),
            reference_lons=np.full(n, -86.6),
            gps_quality_score=85.0,
            built_from_session_id="ref-session",
            n_laps_averaged=5,
            track_length_m=500.0,
            updated_at="2026-01-01T00:00:00+00:00",
        )

    def test_same_grid_identity(self) -> None:
        """Aligning to the same distance grid should produce identical results."""
        ref = self._make_reference()
        session_dist = np.linspace(0, 500.0, 500)

        aligned_curv, aligned_elev = align_reference_to_session(ref, session_dist)

        np.testing.assert_allclose(
            aligned_curv.curvature, ref.curvature_result.curvature, atol=1e-6
        )
        assert aligned_elev is not None
        np.testing.assert_allclose(aligned_elev, ref.elevation_m, atol=1e-6)

    def test_different_grid_size(self) -> None:
        """Aligning to a different grid should interpolate smoothly."""
        ref = self._make_reference(n=500)
        session_dist = np.linspace(0, 502.0, 300)  # slightly longer, fewer points

        aligned_curv, aligned_elev = align_reference_to_session(ref, session_dist)

        assert len(aligned_curv.curvature) == 300
        assert len(aligned_curv.distance_m) == 300
        assert aligned_elev is not None
        assert len(aligned_elev) == 300

    def test_no_elevation(self) -> None:
        """When reference has no elevation, aligned_elev is None."""
        ref = self._make_reference()
        ref.elevation_m = None
        session_dist = np.linspace(0, 500.0, 200)

        _, aligned_elev = align_reference_to_session(ref, session_dist)
        assert aligned_elev is None

    def test_length_mismatch_runs_without_error(self) -> None:
        """Large length mismatch should still produce valid results."""
        ref = self._make_reference()
        session_dist = np.linspace(0, 600.0, 300)  # 20% longer

        aligned_curv, aligned_elev = align_reference_to_session(ref, session_dist)
        assert len(aligned_curv.curvature) == 300
        assert aligned_elev is not None
        assert len(aligned_elev) == 300


class TestUnknownTrack:
    def test_no_layout_returns_none(self, tmp_path: Path) -> None:
        """Unknown track with no layout returns None from get_track_reference."""
        layout = _make_layout("Unknown Track 12345")
        with patch("cataclysm.track_reference._DATA_DIR", tmp_path):
            assert get_track_reference(layout) is None

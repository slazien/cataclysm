"""Tests for cataclysm.track_db."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.corners import Corner
from cataclysm.track_db import (
    TrackLayout,
    OfficialCorner,
    locate_official_corners,
    lookup_track,
)


class TestLookupTrack:
    def test_known_track(self) -> None:
        layout = lookup_track("Barber Motorsports Park")
        assert layout is not None
        assert len(layout.corners) == 16

    def test_case_insensitive(self) -> None:
        layout = lookup_track("barber motorsports park")
        assert layout is not None

    def test_unknown_track(self) -> None:
        assert lookup_track("Unknown Circuit") is None

    def test_whitespace_stripped(self) -> None:
        layout = lookup_track("  Barber Motorsports Park  ")
        assert layout is not None


class TestLocateOfficialCorners:
    def _make_lap_df(
        self, n: int, lats: list[float], lons: list[float]
    ) -> pd.DataFrame:
        """Build a simple lap DataFrame with evenly spaced points."""
        assert len(lats) == n
        assert len(lons) == n
        return pd.DataFrame({
            "lap_distance_m": np.linspace(0, 1000, n),
            "lat": lats,
            "lon": lons,
        })

    def test_returns_all_corners(self) -> None:
        """Every official corner should appear in the output."""
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(1, "Turn 1", 0.0, 0.0),
                OfficialCorner(2, "Turn 2", 1.0, 0.0),
                OfficialCorner(3, "Turn 3", 2.0, 0.0),
            ],
        )
        n = 100
        lap_df = self._make_lap_df(
            n,
            lats=np.linspace(0, 3, n).tolist(),
            lons=[0.0] * n,
        )
        result = locate_official_corners(lap_df, layout)
        assert len(result) == 3
        assert [c.number for c in result] == [1, 2, 3]

    def test_corners_sorted_by_distance(self) -> None:
        """Corners should be sorted by their position on track."""
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(3, "Turn 3", 2.0, 0.0),
                OfficialCorner(1, "Turn 1", 0.0, 0.0),
                OfficialCorner(2, "Turn 2", 1.0, 0.0),
            ],
        )
        n = 100
        lap_df = self._make_lap_df(
            n,
            lats=np.linspace(0, 3, n).tolist(),
            lons=[0.0] * n,
        )
        result = locate_official_corners(lap_df, layout)
        # Should be in track order (by distance), not by number
        distances = [c.apex_distance_m for c in result]
        assert distances == sorted(distances)

    def test_entry_exit_boundaries(self) -> None:
        """Entry/exit should be midpoints between adjacent corners."""
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(1, "A", 0.0, 0.0),
                OfficialCorner(2, "B", 1.0, 0.0),
            ],
        )
        n = 100
        lap_df = self._make_lap_df(
            n,
            lats=np.linspace(0, 2, n).tolist(),
            lons=[0.0] * n,
        )
        result = locate_official_corners(lap_df, layout)
        assert len(result) == 2
        # The exit of corner 1 should equal the entry of corner 2
        assert result[0].exit_distance_m == pytest.approx(
            result[1].entry_distance_m, abs=1.0
        )

    def test_finds_correct_apex_position(self) -> None:
        """Apex should be at the lap point closest to the official GPS."""
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(1, "Turn 1", 5.0, 10.0),
            ],
        )
        # Place a point exactly at (5.0, 10.0) at distance 500m
        n = 11
        lats = np.linspace(0, 10, n).tolist()  # [0, 1, 2, ..., 10]
        lons = np.linspace(0, 20, n).tolist()  # [0, 2, 4, ..., 20]
        # Point at index 5 is (5.0, 10.0) which matches the official corner
        lap_df = self._make_lap_df(n, lats, lons)
        result = locate_official_corners(lap_df, layout)
        assert len(result) == 1
        assert result[0].apex_distance_m == pytest.approx(500.0, abs=1.0)

    def test_skeleton_has_placeholder_kpis(self) -> None:
        """Returned corners should have placeholder KPI values."""
        layout = TrackLayout(
            name="Test",
            corners=[OfficialCorner(1, "T1", 0.0, 0.0)],
        )
        n = 20
        lap_df = self._make_lap_df(
            n, lats=np.linspace(0, 1, n).tolist(), lons=[0.0] * n
        )
        result = locate_official_corners(lap_df, layout)
        assert result[0].min_speed_mps == 0.0
        assert result[0].brake_point_m is None
        assert result[0].peak_brake_g is None
        assert result[0].throttle_commit_m is None

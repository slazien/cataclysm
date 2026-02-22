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
    def _make_lap_df(self, max_dist: float = 1000.0, n: int = 100) -> pd.DataFrame:
        """Build a simple lap DataFrame."""
        return pd.DataFrame({
            "lap_distance_m": np.linspace(0, max_dist, n),
        })

    def test_returns_all_corners(self) -> None:
        """Every official corner should appear in the output."""
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(1, "Turn 1", 0.10),
                OfficialCorner(2, "Turn 2", 0.50),
                OfficialCorner(3, "Turn 3", 0.90),
            ],
        )
        lap_df = self._make_lap_df()
        result = locate_official_corners(lap_df, layout)
        assert len(result) == 3
        assert [c.number for c in result] == [1, 2, 3]

    def test_corners_sorted_by_distance(self) -> None:
        """Corners should be sorted by their position on track."""
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(3, "Turn 3", 0.90),
                OfficialCorner(1, "Turn 1", 0.10),
                OfficialCorner(2, "Turn 2", 0.50),
            ],
        )
        lap_df = self._make_lap_df()
        result = locate_official_corners(lap_df, layout)
        distances = [c.apex_distance_m for c in result]
        assert distances == sorted(distances)

    def test_apex_at_fraction_of_distance(self) -> None:
        """Apex should be at fraction * max_distance."""
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(1, "Turn 1", 0.25),
                OfficialCorner(2, "Turn 2", 0.75),
            ],
        )
        lap_df = self._make_lap_df(max_dist=2000.0)
        result = locate_official_corners(lap_df, layout)
        assert result[0].apex_distance_m == pytest.approx(500.0, abs=1.0)
        assert result[1].apex_distance_m == pytest.approx(1500.0, abs=1.0)

    def test_entry_exit_boundaries(self) -> None:
        """Entry/exit should be midpoints between adjacent corners."""
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(1, "A", 0.20),
                OfficialCorner(2, "B", 0.60),
            ],
        )
        lap_df = self._make_lap_df()
        result = locate_official_corners(lap_df, layout)
        assert len(result) == 2
        # The exit of corner 1 should equal the entry of corner 2
        assert result[0].exit_distance_m == pytest.approx(
            result[1].entry_distance_m, abs=1.0
        )

    def test_skeleton_has_placeholder_kpis(self) -> None:
        """Returned corners should have placeholder KPI values."""
        layout = TrackLayout(
            name="Test",
            corners=[OfficialCorner(1, "T1", 0.50)],
        )
        lap_df = self._make_lap_df()
        result = locate_official_corners(lap_df, layout)
        assert result[0].min_speed_mps == 0.0
        assert result[0].brake_point_m is None
        assert result[0].peak_brake_g is None
        assert result[0].throttle_commit_m is None

    def test_scales_with_lap_distance(self) -> None:
        """Same fraction should produce different apex_m for different lap lengths."""
        layout = TrackLayout(
            name="Test",
            corners=[OfficialCorner(1, "T1", 0.50)],
        )
        short = self._make_lap_df(max_dist=1000.0)
        long = self._make_lap_df(max_dist=4000.0)
        r_short = locate_official_corners(short, layout)
        r_long = locate_official_corners(long, layout)
        assert r_short[0].apex_distance_m == pytest.approx(500.0, abs=1.0)
        assert r_long[0].apex_distance_m == pytest.approx(2000.0, abs=1.0)

"""Tests for cataclysm.track_db."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.corners import Corner
from cataclysm.track_db import (
    _haversine_m,
    assign_official_numbers,
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


class TestHaversine:
    def test_same_point(self) -> None:
        d = _haversine_m(33.5, -86.6, 33.5, -86.6)
        assert d == pytest.approx(0.0, abs=0.01)

    def test_known_distance(self) -> None:
        # ~111 km per degree of latitude
        d = _haversine_m(33.0, -86.0, 34.0, -86.0)
        assert d == pytest.approx(111_195, rel=0.01)


class TestAssignOfficialNumbers:
    def _make_corner(self, number: int, apex_m: float) -> Corner:
        return Corner(
            number=number,
            entry_distance_m=apex_m - 20,
            exit_distance_m=apex_m + 20,
            apex_distance_m=apex_m,
            min_speed_mps=20.0,
            brake_point_m=apex_m - 40,
            peak_brake_g=-0.5,
            throttle_commit_m=apex_m + 10,
            apex_type="mid",
        )

    def _make_lap_df(
        self, distances: list[float], lats: list[float], lons: list[float]
    ) -> pd.DataFrame:
        return pd.DataFrame({
            "lap_distance_m": distances,
            "lat": lats,
            "lon": lons,
        })

    def test_unknown_track_returns_unchanged(self) -> None:
        corners = [self._make_corner(1, 100.0), self._make_corner(2, 200.0)]
        lap_df = self._make_lap_df(
            [0.0, 100.0, 200.0, 300.0],
            [33.53, 33.53, 33.53, 33.53],
            [-86.62, -86.62, -86.62, -86.62],
        )
        result = assign_official_numbers(corners, "Unknown Track", lap_df)
        assert result is corners  # exact same object

    def test_empty_corners(self) -> None:
        lap_df = self._make_lap_df([0.0], [33.53], [-86.62])
        result = assign_official_numbers([], "Barber Motorsports Park", lap_df)
        assert result == []

    def test_matches_nearby_official_corner(self) -> None:
        """A detected corner near official T5 (Charlotte's Web) should get number 5."""
        # T5 is at (33.5348, -86.6163) in the database
        corners = [self._make_corner(1, 50.0)]
        lap_df = self._make_lap_df(
            [0.0, 50.0, 100.0],
            [33.534, 33.5348, 33.535],
            [-86.617, -86.6163, -86.616],
        )
        result = assign_official_numbers(corners, "Barber Motorsports Park", lap_df)
        assert len(result) == 1
        assert result[0].number == 5

    def test_no_match_too_far(self) -> None:
        """A corner far from any official corner gets a fallback number."""
        corners = [self._make_corner(1, 50.0)]
        # GPS position far from any Barber corner
        lap_df = self._make_lap_df(
            [0.0, 50.0, 100.0],
            [34.0, 34.0, 34.0],
            [-87.0, -87.0, -87.0],
        )
        result = assign_official_numbers(corners, "Barber Motorsports Park", lap_df)
        assert len(result) == 1
        assert result[0].number >= 100  # fallback numbering

    def test_preserves_kpi_data(self) -> None:
        """Official numbering should not lose corner KPI data."""
        corners = [self._make_corner(1, 50.0)]
        lap_df = self._make_lap_df(
            [0.0, 50.0, 100.0],
            [33.534, 33.5348, 33.535],
            [-86.617, -86.6163, -86.616],
        )
        result = assign_official_numbers(corners, "Barber Motorsports Park", lap_df)
        assert result[0].min_speed_mps == 20.0
        assert result[0].brake_point_m == 10.0
        assert result[0].apex_type == "mid"

    def test_no_duplicate_assignments(self) -> None:
        """Two detected corners near the same official corner: only closest gets it."""
        corners = [
            self._make_corner(1, 50.0),
            self._make_corner(2, 60.0),
        ]
        # Both near T5, but corner 1 is closer
        lap_df = self._make_lap_df(
            [0.0, 50.0, 60.0, 100.0],
            [33.534, 33.5348, 33.5347, 33.535],
            [-86.617, -86.6163, -86.6164, -86.616],
        )
        result = assign_official_numbers(corners, "Barber Motorsports Park", lap_df)
        numbers = [c.number for c in result]
        # Only one should get 5, the other gets a fallback
        assert numbers.count(5) == 1

"""Tests for cataclysm.track_db."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.landmarks import Landmark, LandmarkType
from cataclysm.track_db import (
    ATLANTA_MOTORSPORTS_PARK,
    BARBER_MOTORSPORTS_PARK,
    OfficialCorner,
    TrackLayout,
    get_all_tracks,
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


class TestGPSFields:
    """Tests for GPS-enriched fields on OfficialCorner and TrackLayout."""

    def test_official_corner_gps_defaults_none(self) -> None:
        c = OfficialCorner(1, "T1", 0.5)
        assert c.lat is None
        assert c.lon is None

    def test_official_corner_gps_populated(self) -> None:
        c = OfficialCorner(1, "T1", 0.5, lat=33.53, lon=-86.62)
        assert c.lat == 33.53
        assert c.lon == -86.62

    def test_track_layout_gps_defaults(self) -> None:
        layout = TrackLayout(name="Test", corners=[])
        assert layout.center_lat is None
        assert layout.center_lon is None
        assert layout.country == ""
        assert layout.length_m is None

    def test_barber_has_gps_metadata(self) -> None:
        assert BARBER_MOTORSPORTS_PARK.center_lat == pytest.approx(33.5302)
        assert BARBER_MOTORSPORTS_PARK.center_lon == pytest.approx(-86.6215)
        assert BARBER_MOTORSPORTS_PARK.country == "US"
        assert BARBER_MOTORSPORTS_PARK.length_m == pytest.approx(3662.4)

    def test_get_all_tracks_returns_list(self) -> None:
        tracks = get_all_tracks()
        assert isinstance(tracks, list)
        assert len(tracks) >= 1
        assert any(t.name == "Barber Motorsports Park" for t in tracks)


class TestLocateOfficialCorners:
    def _make_lap_df(self, max_dist: float = 1000.0, n: int = 100) -> pd.DataFrame:
        """Build a simple lap DataFrame."""
        return pd.DataFrame(
            {
                "lap_distance_m": np.linspace(0, max_dist, n),
            }
        )

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
        assert result[0].exit_distance_m == pytest.approx(result[1].entry_distance_m, abs=1.0)

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


class TestTrackLayoutLandmarks:
    """Tests for the landmarks field on TrackLayout."""

    def test_default_empty_landmarks(self) -> None:
        """TrackLayout with no landmarks should have empty list."""
        layout = TrackLayout(
            name="Empty",
            corners=[OfficialCorner(1, "T1", 0.50)],
        )
        assert layout.landmarks == []

    def test_landmarks_populated(self) -> None:
        lm = [Landmark("test board", 100.0, LandmarkType.brake_board)]
        layout = TrackLayout(
            name="Test",
            corners=[OfficialCorner(1, "T1", 0.50)],
            landmarks=lm,
        )
        assert len(layout.landmarks) == 1
        assert layout.landmarks[0].name == "test board"

    def test_barber_has_landmarks(self) -> None:
        """Barber Motorsports Park should have curated landmarks."""
        assert len(BARBER_MOTORSPORTS_PARK.landmarks) > 0

    def test_barber_landmarks_have_brake_boards(self) -> None:
        """Barber should include brake board landmarks."""
        brake_boards = [
            lm
            for lm in BARBER_MOTORSPORTS_PARK.landmarks
            if lm.landmark_type == LandmarkType.brake_board
        ]
        assert len(brake_boards) >= 4  # T1, T5, T8, T12, T15, T16

    def test_barber_landmarks_sorted_by_distance(self) -> None:
        """Landmarks should be roughly sorted by distance around the track."""
        distances = [lm.distance_m for lm in BARBER_MOTORSPORTS_PARK.landmarks]
        assert distances == sorted(distances)

    def test_barber_landmarks_positive_distances(self) -> None:
        for lm in BARBER_MOTORSPORTS_PARK.landmarks:
            assert lm.distance_m >= 0.0

    def test_barber_landmarks_have_names(self) -> None:
        for lm in BARBER_MOTORSPORTS_PARK.landmarks:
            assert len(lm.name) > 0

    def test_lookup_track_returns_landmarks(self) -> None:
        """lookup_track for Barber should include landmarks."""
        layout = lookup_track("Barber Motorsports Park")
        assert layout is not None
        assert len(layout.landmarks) > 0


class TestAtlantaMotorsportsPark:
    def test_lookup_by_name(self) -> None:
        layout = lookup_track("Atlanta Motorsports Park")
        assert layout is not None
        assert layout.name == "Atlanta Motorsports Park"

    def test_lookup_case_insensitive(self) -> None:
        layout = lookup_track("atlanta motorsports park")
        assert layout is not None
        assert layout.name == "Atlanta Motorsports Park"

    def test_has_twelve_corners(self) -> None:
        assert len(ATLANTA_MOTORSPORTS_PARK.corners) == 12

    def test_corner_numbering(self) -> None:
        numbers = [c.number for c in ATLANTA_MOTORSPORTS_PARK.corners]
        assert numbers == list(range(1, 13))

    def test_fractions_monotonic(self) -> None:
        fractions = [c.fraction for c in ATLANTA_MOTORSPORTS_PARK.corners]
        for i in range(1, len(fractions)):
            assert fractions[i] > fractions[i - 1]

    def test_fractions_in_range(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert 0.0 < c.fraction < 1.0

    def test_gps_metadata(self) -> None:
        assert ATLANTA_MOTORSPORTS_PARK.center_lat == pytest.approx(34.42, abs=0.01)
        assert ATLANTA_MOTORSPORTS_PARK.center_lon == pytest.approx(-84.12, abs=0.01)

    def test_landmarks_present(self) -> None:
        assert len(ATLANTA_MOTORSPORTS_PARK.landmarks) >= 10

    def test_landmarks_sorted(self) -> None:
        distances = [lm.distance_m for lm in ATLANTA_MOTORSPORTS_PARK.landmarks]
        for i in range(1, len(distances)):
            assert distances[i] >= distances[i - 1]

    def test_landmarks_in_range(self) -> None:
        length = ATLANTA_MOTORSPORTS_PARK.length_m
        assert length is not None
        for lm in ATLANTA_MOTORSPORTS_PARK.landmarks:
            assert 0.0 <= lm.distance_m < length

    def test_track_length(self) -> None:
        assert ATLANTA_MOTORSPORTS_PARK.length_m == pytest.approx(3220.0)

    def test_in_all_tracks(self) -> None:
        tracks = get_all_tracks()
        assert any(t.name == "Atlanta Motorsports Park" for t in tracks)

    def test_country(self) -> None:
        assert ATLANTA_MOTORSPORTS_PARK.country == "US"

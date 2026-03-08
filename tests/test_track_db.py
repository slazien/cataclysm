"""Tests for cataclysm.track_db."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.landmarks import Landmark, LandmarkType
from cataclysm.track_db import (
    ATLANTA_MOTORSPORTS_PARK,
    BARBER_MOTORSPORTS_PARK,
    ROEBLING_ROAD_RACEWAY,
    OfficialCorner,
    TrackLayout,
    get_all_tracks,
    get_key_corners,
    get_peculiarities,
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

    def test_lookup_csv_alias(self) -> None:
        """RaceChrono CSV metadata reports 'AMP Full' as the track name."""
        layout = lookup_track("AMP Full")
        assert layout is not None
        assert layout.name == "Atlanta Motorsports Park"

    def test_has_sixteen_corners(self) -> None:
        assert len(ATLANTA_MOTORSPORTS_PARK.corners) == 16

    def test_corner_numbering(self) -> None:
        numbers = [c.number for c in ATLANTA_MOTORSPORTS_PARK.corners]
        assert numbers == list(range(1, 17))

    def test_fractions_monotonic(self) -> None:
        fractions = [c.fraction for c in ATLANTA_MOTORSPORTS_PARK.corners]
        for i in range(1, len(fractions)):
            assert fractions[i] > fractions[i - 1]

    def test_fractions_in_range(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert 0.0 < c.fraction < 1.0

    def test_gps_metadata_corrected(self) -> None:
        """Center coords verified from real GPS telemetry centroid."""
        assert ATLANTA_MOTORSPORTS_PARK.center_lat == pytest.approx(34.435, abs=0.01)
        assert ATLANTA_MOTORSPORTS_PARK.center_lon == pytest.approx(-84.178, abs=0.01)

    def test_track_length_corrected(self) -> None:
        """Median lap distance from 10 telemetry laps."""
        assert ATLANTA_MOTORSPORTS_PARK.length_m == pytest.approx(2935.0, abs=10.0)

    def test_elevation_range(self) -> None:
        assert ATLANTA_MOTORSPORTS_PARK.elevation_range_m == pytest.approx(30.0, abs=2.0)

    def test_landmarks_present(self) -> None:
        assert len(ATLANTA_MOTORSPORTS_PARK.landmarks) >= 17

    def test_landmarks_sorted(self) -> None:
        distances = [lm.distance_m for lm in ATLANTA_MOTORSPORTS_PARK.landmarks]
        for i in range(1, len(distances)):
            assert distances[i] >= distances[i - 1]

    def test_landmarks_in_range(self) -> None:
        length = ATLANTA_MOTORSPORTS_PARK.length_m
        assert length is not None
        for lm in ATLANTA_MOTORSPORTS_PARK.landmarks:
            assert 0.0 <= lm.distance_m < length

    def test_in_all_tracks(self) -> None:
        tracks = get_all_tracks()
        assert any(t.name == "Atlanta Motorsports Park" for t in tracks)

    def test_country(self) -> None:
        assert ATLANTA_MOTORSPORTS_PARK.country == "US"

    def test_all_corners_have_direction(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert c.direction in ("left", "right"), f"T{c.number} missing direction"

    def test_all_corners_have_corner_type(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert c.corner_type is not None, f"T{c.number} missing corner_type"

    def test_all_corners_have_elevation_trend(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert c.elevation_trend is not None, f"T{c.number} missing elevation_trend"

    def test_all_corners_have_coaching_notes(self) -> None:
        for c in ATLANTA_MOTORSPORTS_PARK.corners:
            assert c.coaching_notes is not None, f"T{c.number} missing coaching_notes"
            assert len(c.coaching_notes) > 10, f"T{c.number} coaching_notes too short"


class TestAMPEnrichedData:
    """Tests that specific AMP corners have expected curated values."""

    def _get_corner(self, number: int) -> OfficialCorner:
        matches = [c for c in ATLANTA_MOTORSPORTS_PARK.corners if c.number == number]
        assert len(matches) == 1
        return matches[0]

    def test_t1_downhill_hairpin(self) -> None:
        c = self._get_corner(1)
        assert c.direction == "left"
        assert c.corner_type == "hairpin"
        assert c.elevation_trend == "downhill"
        assert c.camber == "off-camber"

    def test_t4_carousel(self) -> None:
        c = self._get_corner(4)
        assert c.direction == "left"
        assert "carousel" in c.name.lower() or "carousel" in (c.coaching_notes or "").lower()

    def test_t6_blind_countdown_hairpin(self) -> None:
        c = self._get_corner(6)
        assert c.direction == "right"
        assert c.blind is True

    def test_t10_compression(self) -> None:
        c = self._get_corner(10)
        assert c.elevation_trend == "compression"

    def test_t14_eau_rouge(self) -> None:
        c = self._get_corner(14)
        assert "eau rouge" in c.name.lower() or "eau rouge" in (c.coaching_notes or "").lower()

    def test_t16_blind_final(self) -> None:
        c = self._get_corner(16)
        assert c.blind is True
        assert c.direction == "right"

    def test_has_character_annotations(self) -> None:
        """At least some fast corners should have character annotations."""
        char_count = sum(1 for c in ATLANTA_MOTORSPORTS_PARK.corners if c.character is not None)
        assert char_count >= 4, "Need character annotations on fast kinks/esses"

    def test_landmarks_have_brake_boards(self) -> None:
        brake_boards = [
            lm
            for lm in ATLANTA_MOTORSPORTS_PARK.landmarks
            if lm.landmark_type == LandmarkType.brake_board
        ]
        assert len(brake_boards) >= 3


class TestOfficialCornerCharacter:
    """Tests for corner character propagation through locate_official_corners."""

    def _make_lap_df(self, max_dist: float = 1000.0, n: int = 100) -> pd.DataFrame:
        return pd.DataFrame({"lap_distance_m": np.linspace(0, max_dist, n)})

    def test_official_corner_character_default_none(self) -> None:
        c = OfficialCorner(1, "T1", 0.5)
        assert c.character is None

    def test_official_corner_character_set(self) -> None:
        c = OfficialCorner(10, "Esses Left", 0.58, character="flat")
        assert c.character == "flat"

    def test_character_propagated_to_skeleton(self) -> None:
        """character flows from OfficialCorner through locate_official_corners."""
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(1, "Brake Corner", 0.20, character="brake"),
                OfficialCorner(2, "Flat Kink", 0.50, character="flat"),
                OfficialCorner(3, "Normal Turn", 0.80),
            ],
        )
        lap_df = self._make_lap_df()
        result = locate_official_corners(lap_df, layout)
        assert len(result) == 3
        assert result[0].character == "brake"
        assert result[1].character == "flat"
        assert result[2].character is None

    def test_barber_flat_corners(self) -> None:
        """Barber T6, T10, T13 should have flat character."""
        flat_numbers = {6, 10, 13}
        for c in BARBER_MOTORSPORTS_PARK.corners:
            if c.number in flat_numbers:
                assert c.character == "flat", f"T{c.number} should be flat"

    def test_barber_lift_corner(self) -> None:
        """Barber T11 should have lift character."""
        t11 = [c for c in BARBER_MOTORSPORTS_PARK.corners if c.number == 11]
        assert len(t11) == 1
        assert t11[0].character == "lift"

    def test_barber_most_corners_none(self) -> None:
        """Most Barber corners should have None character (auto-detect)."""
        none_count = sum(1 for c in BARBER_MOTORSPORTS_PARK.corners if c.character is None)
        assert none_count >= 10  # 16 total, 4 have explicit character


class TestOfficialCornerCoachingFields:
    """Tests for coaching knowledge fields on OfficialCorner."""

    def test_defaults_none_and_false(self) -> None:
        c = OfficialCorner(1, "T1", 0.5)
        assert c.direction is None
        assert c.corner_type is None
        assert c.elevation_trend is None
        assert c.camber is None
        assert c.blind is False
        assert c.coaching_notes is None

    def test_populated_values(self) -> None:
        c = OfficialCorner(
            5,
            "Charlotte's Web",
            0.30,
            direction="right",
            corner_type="hairpin",
            elevation_trend="flat",
            camber="positive",
            blind=False,
            coaching_notes="Very late apex.",
        )
        assert c.direction == "right"
        assert c.corner_type == "hairpin"
        assert c.elevation_trend == "flat"
        assert c.camber == "positive"
        assert c.blind is False
        assert c.coaching_notes == "Very late apex."


class TestEnrichedFieldPropagation:
    """Tests that locate_official_corners carries coaching fields to Corner."""

    def _make_lap_df(self, max_dist: float = 1000.0, n: int = 100) -> pd.DataFrame:
        return pd.DataFrame({"lap_distance_m": np.linspace(0, max_dist, n)})

    def test_coaching_fields_propagated(self) -> None:
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(
                    1,
                    "Test Corner",
                    0.50,
                    direction="left",
                    corner_type="hairpin",
                    elevation_trend="downhill",
                    camber="off-camber",
                    blind=True,
                    coaching_notes="Brake early.",
                ),
            ],
        )
        lap_df = self._make_lap_df()
        result = locate_official_corners(lap_df, layout)
        c = result[0]
        assert c.direction == "left"
        assert c.corner_type_hint == "hairpin"
        assert c.elevation_trend == "downhill"
        assert c.camber == "off-camber"
        assert c.blind is True
        assert c.coaching_notes == "Brake early."

    def test_none_fields_propagated(self) -> None:
        layout = TrackLayout(
            name="Test",
            corners=[OfficialCorner(1, "Plain", 0.50)],
        )
        lap_df = self._make_lap_df()
        result = locate_official_corners(lap_df, layout)
        c = result[0]
        assert c.direction is None
        assert c.corner_type_hint is None
        assert c.coaching_notes is None
        assert c.blind is False


class TestBarberEnrichedData:
    """Tests that specific Barber corners have expected curated values."""

    def _get_corner(self, number: int) -> OfficialCorner:
        matches = [c for c in BARBER_MOTORSPORTS_PARK.corners if c.number == number]
        assert len(matches) == 1
        return matches[0]

    def test_t1_downhill_left(self) -> None:
        c = self._get_corner(1)
        assert c.direction == "left"
        assert c.corner_type == "sweeper"
        assert c.elevation_trend == "downhill"

    def test_t5_hairpin(self) -> None:
        c = self._get_corner(5)
        assert c.direction == "right"
        assert c.corner_type == "hairpin"
        assert c.coaching_notes is not None
        assert "late apex" in c.coaching_notes.lower()

    def test_t12_blind_offcamber(self) -> None:
        c = self._get_corner(12)
        assert c.blind is True
        assert c.camber == "off-camber"
        assert c.elevation_trend == "downhill"

    def test_t15_blind(self) -> None:
        c = self._get_corner(15)
        assert c.blind is True
        assert c.direction == "right"

    def test_t16_exit_critical(self) -> None:
        c = self._get_corner(16)
        assert c.direction == "left"
        assert c.coaching_notes is not None
        assert "exit" in c.coaching_notes.lower()

    def test_all_corners_have_direction(self) -> None:
        for c in BARBER_MOTORSPORTS_PARK.corners:
            assert c.direction in ("left", "right"), f"T{c.number} missing direction"

    def test_all_corners_have_coaching_notes(self) -> None:
        for c in BARBER_MOTORSPORTS_PARK.corners:
            assert c.coaching_notes is not None, f"T{c.number} missing coaching_notes"
            assert len(c.coaching_notes) > 10, f"T{c.number} coaching_notes too short"

    def test_elevation_range(self) -> None:
        """Barber min-to-max altitude range is ~24m (80 feet), not cumulative gain."""
        assert BARBER_MOTORSPORTS_PARK.elevation_range_m == pytest.approx(24.0)
        assert BARBER_MOTORSPORTS_PARK.elevation_range_m is not None
        assert BARBER_MOTORSPORTS_PARK.elevation_range_m < 30.0


class TestRoeblingRoadRaceway:
    """Tests for Roebling Road Raceway track definition."""

    def test_lookup_by_name(self) -> None:
        layout = lookup_track("Roebling Road Raceway")
        assert layout is not None
        assert layout.name == "Roebling Road Raceway"

    def test_lookup_short_name(self) -> None:
        layout = lookup_track("Roebling Road")
        assert layout is not None
        assert layout.name == "Roebling Road Raceway"

    def test_lookup_case_insensitive(self) -> None:
        layout = lookup_track("roebling road raceway")
        assert layout is not None

    def test_has_nine_corners(self) -> None:
        assert len(ROEBLING_ROAD_RACEWAY.corners) == 9

    def test_corner_numbering(self) -> None:
        numbers = [c.number for c in ROEBLING_ROAD_RACEWAY.corners]
        assert numbers == list(range(1, 10))

    def test_fractions_monotonic(self) -> None:
        fractions = [c.fraction for c in ROEBLING_ROAD_RACEWAY.corners]
        for i in range(1, len(fractions)):
            assert fractions[i] > fractions[i - 1], (
                f"T{i + 1} frac {fractions[i]} <= T{i} frac {fractions[i - 1]}"
            )

    def test_fractions_in_range(self) -> None:
        for c in ROEBLING_ROAD_RACEWAY.corners:
            assert 0.0 < c.fraction < 1.0, f"T{c.number} fraction {c.fraction} out of range"

    def test_all_corners_have_direction(self) -> None:
        for c in ROEBLING_ROAD_RACEWAY.corners:
            assert c.direction in ("left", "right"), f"T{c.number} missing direction"

    def test_all_corners_have_coaching_notes(self) -> None:
        for c in ROEBLING_ROAD_RACEWAY.corners:
            assert c.coaching_notes is not None, f"T{c.number} missing coaching_notes"
            assert len(c.coaching_notes) > 10, f"T{c.number} coaching_notes too short"

    def test_gps_metadata(self) -> None:
        assert ROEBLING_ROAD_RACEWAY.center_lat == pytest.approx(32.168, abs=0.01)
        assert ROEBLING_ROAD_RACEWAY.center_lon == pytest.approx(-81.322, abs=0.01)
        assert ROEBLING_ROAD_RACEWAY.country == "US"
        assert ROEBLING_ROAD_RACEWAY.length_m == pytest.approx(3200.4, abs=10.0)

    def test_elevation_range(self) -> None:
        assert ROEBLING_ROAD_RACEWAY.elevation_range_m == pytest.approx(8.0, abs=2.0)

    def test_landmarks_present(self) -> None:
        assert len(ROEBLING_ROAD_RACEWAY.landmarks) >= 7

    def test_landmarks_sorted(self) -> None:
        distances = [lm.distance_m for lm in ROEBLING_ROAD_RACEWAY.landmarks]
        for i in range(1, len(distances)):
            assert distances[i] >= distances[i - 1]

    def test_landmarks_in_range(self) -> None:
        length = ROEBLING_ROAD_RACEWAY.length_m
        assert length is not None
        for lm in ROEBLING_ROAD_RACEWAY.landmarks:
            assert 0.0 <= lm.distance_m < length

    def test_in_all_tracks(self) -> None:
        tracks = get_all_tracks()
        assert any(t.name == "Roebling Road Raceway" for t in tracks)


class TestGetKeyCorners:
    """Tests for the get_key_corners utility function."""

    def test_barber_key_corners_include_t5_t9_t16(self) -> None:
        """Barber's T5 (hairpin), T9 (corkscrew exit), T16 (final) must be key."""
        result = get_key_corners(BARBER_MOTORSPORTS_PARK)
        numbers = {c.number for c, _ in result}
        assert 5 in numbers, "T5 (Charlotte's Web hairpin) must be a key corner"
        assert 9 in numbers, "T9 (Corkscrew Exit) must be a key corner"
        assert 16 in numbers, "T16 (Final Left) must be a key corner"

    def test_barber_key_corners_gap_minimum(self) -> None:
        """All key corners should have at least 100m gap to the next corner."""
        result = get_key_corners(BARBER_MOTORSPORTS_PARK)
        assert len(result) > 0
        assert len(result) <= 5
        for _corner, gap_m in result:
            assert gap_m > 100

    def test_barber_flat_out_corners_excluded(self) -> None:
        """Flat-out corners (character='flat') should not appear as key corners."""
        result = get_key_corners(BARBER_MOTORSPORTS_PARK)
        for corner, _ in result:
            assert corner.character != "flat", (
                f"T{corner.number} is flat-out and should not be a key corner"
            )

    def test_amp_key_corners(self) -> None:
        result = get_key_corners(ATLANTA_MOTORSPORTS_PARK)
        assert len(result) > 0
        for _corner, gap_m in result:
            assert gap_m > 100

    def test_roebling_key_corners(self) -> None:
        result = get_key_corners(ROEBLING_ROAD_RACEWAY)
        assert len(result) > 0

    def test_empty_layout(self) -> None:
        layout = TrackLayout(name="Empty", corners=[], length_m=1000.0)
        assert get_key_corners(layout) == []

    def test_single_corner(self) -> None:
        layout = TrackLayout(
            name="One",
            corners=[OfficialCorner(1, "T1", 0.5)],
            length_m=1000.0,
        )
        assert get_key_corners(layout) == []

    def test_no_length(self) -> None:
        layout = TrackLayout(
            name="NoLen",
            corners=[OfficialCorner(1, "T1", 0.2), OfficialCorner(2, "T2", 0.8)],
        )
        assert get_key_corners(layout) == []

    def test_max_five_returned(self) -> None:
        """Even if more than 5 qualify, only top 5 are returned."""
        corners = [OfficialCorner(i, f"T{i}", i * 0.1) for i in range(1, 10)]
        layout = TrackLayout(name="Wide", corners=corners, length_m=10000.0)
        result = get_key_corners(layout)
        assert len(result) <= 5

    def test_wrap_around_gap(self) -> None:
        """Last corner to first corner through S/F should be detected."""
        layout = TrackLayout(
            name="Wrap",
            corners=[
                OfficialCorner(1, "T1", 0.05),
                OfficialCorner(2, "T2", 0.50),
                OfficialCorner(3, "T3", 0.55),
            ],
            length_m=1000.0,
        )
        result = get_key_corners(layout)
        # T2→T3 is only 50m, but T3→T1 wrap-around is 500m
        gaps = {c.number: gap for c, gap in result}
        assert 3 in gaps  # T3 should be a key corner (500m wrap)

    def test_all_surrounding_corners_flat_returns_full_track_length(self) -> None:
        """When all other corners are flat, gap falls back to full track length (line 827)."""
        # One real corner + two flat-out corners — after the real corner, only flat ones remain
        layout = TrackLayout(
            name="FlatTrack",
            corners=[
                OfficialCorner(1, "T1 Real", 0.10),  # This is the key corner
                OfficialCorner(2, "T2 Flat", 0.50, character="flat"),
                OfficialCorner(3, "T3 Flat", 0.80, character="flat"),
            ],
            length_m=2000.0,
        )
        result = get_key_corners(layout)
        # T1 has gap = full track_len because T2 and T3 are both flat
        gaps = {c.number: gap for c, gap in result}
        assert 1 in gaps
        assert gaps[1] == pytest.approx(2000.0)

    def test_hairpin_ranks_above_kink_with_longer_straight(self) -> None:
        """A hairpin onto a moderate straight should outrank a kink onto a long straight."""
        layout = TrackLayout(
            name="Score",
            corners=[
                OfficialCorner(1, "Hairpin", 0.10, corner_type="hairpin"),
                OfficialCorner(2, "Kink", 0.30, corner_type="kink"),
                OfficialCorner(3, "Sweeper", 0.80, corner_type="sweeper"),
            ],
            length_m=2000.0,
        )
        result = get_key_corners(layout)
        numbers = [c.number for c, _ in result]
        # Hairpin (gap=400m, severity=3.0, score=1200) should rank above
        # Kink (gap=1000m, severity=0.5, score=500)
        assert numbers.index(1) < numbers.index(2)


class TestGetPeculiarities:
    """Tests for the get_peculiarities utility function."""

    def test_barber_has_blind_corners(self) -> None:
        result = get_peculiarities(BARBER_MOTORSPORTS_PARK)
        descs = [desc for _, desc in result]
        assert any("blind" in d for d in descs)

    def test_barber_has_off_camber(self) -> None:
        result = get_peculiarities(BARBER_MOTORSPORTS_PARK)
        descs = [desc for _, desc in result]
        assert any("off-camber" in d for d in descs)

    def test_barber_has_crests(self) -> None:
        result = get_peculiarities(BARBER_MOTORSPORTS_PARK)
        descs = [desc for _, desc in result]
        assert any("crest" in d for d in descs)

    def test_barber_has_compression(self) -> None:
        result = get_peculiarities(BARBER_MOTORSPORTS_PARK)
        descs = [desc for _, desc in result]
        assert any("compression" in d for d in descs)

    def test_amp_has_peculiarities(self) -> None:
        result = get_peculiarities(ATLANTA_MOTORSPORTS_PARK)
        assert len(result) > 0

    def test_empty_layout(self) -> None:
        layout = TrackLayout(name="Empty", corners=[])
        assert get_peculiarities(layout) == []

    def test_plain_corner_no_peculiarities(self) -> None:
        layout = TrackLayout(
            name="Plain",
            corners=[OfficialCorner(1, "T1", 0.5, camber="positive")],
        )
        assert get_peculiarities(layout) == []

    def test_multiple_flags_per_corner(self) -> None:
        """A corner can have multiple peculiarities (e.g. blind + off-camber)."""
        layout = TrackLayout(
            name="Multi",
            corners=[
                OfficialCorner(
                    1,
                    "Scary",
                    0.5,
                    blind=True,
                    camber="off-camber",
                    elevation_trend="crest",
                ),
            ],
        )
        result = get_peculiarities(layout)
        assert len(result) == 3
        descs = [desc for _, desc in result]
        assert "blind apex/exit" in descs
        assert "off-camber camber" in descs
        assert "crest" in descs

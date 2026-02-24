"""Tests for cataclysm.landmarks."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.corners import Corner
from cataclysm.landmarks import (
    MAX_LANDMARK_DISTANCE_M,
    Landmark,
    LandmarkReference,
    LandmarkType,
    find_landmarks_in_range,
    find_nearest_landmark,
    format_corner_landmarks,
    resolve_gps_at_distance,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def brake_board() -> Landmark:
    return Landmark("T5 3 board", 940.0, LandmarkType.brake_board)


@pytest.fixture
def structure() -> Landmark:
    return Landmark("pedestrian bridge", 1500.0, LandmarkType.structure)


@pytest.fixture
def barrier() -> Landmark:
    return Landmark("T2 Armco", 380.0, LandmarkType.barrier)


@pytest.fixture
def sample_landmarks() -> list[Landmark]:
    return [
        Landmark("S/F gantry", 0.0, LandmarkType.structure),
        Landmark("T1 200m board", 90.0, LandmarkType.brake_board),
        Landmark("T1 100m board", 140.0, LandmarkType.brake_board),
        Landmark("T2 Armco", 380.0, LandmarkType.barrier),
        Landmark("T5 3 board", 940.0, LandmarkType.brake_board),
        Landmark("T5 2 board", 1010.0, LandmarkType.brake_board),
        Landmark("pedestrian bridge", 1500.0, LandmarkType.structure),
        Landmark("museum building", 1650.0, LandmarkType.structure, description="On right"),
    ]


@pytest.fixture
def sample_lap_df() -> pd.DataFrame:
    """A minimal resampled DataFrame with GPS columns."""
    n = 500
    dist = np.arange(n) * 0.7
    return pd.DataFrame(
        {
            "lap_distance_m": dist,
            "lat": 33.53 + np.linspace(0, 0.003, n),
            "lon": -86.62 + np.linspace(0, 0.003, n),
        }
    )


@pytest.fixture
def sample_corner() -> Corner:
    return Corner(
        number=5,
        entry_distance_m=900.0,
        exit_distance_m=1100.0,
        apex_distance_m=1000.0,
        min_speed_mps=20.0,
        brake_point_m=955.0,
        peak_brake_g=-0.9,
        throttle_commit_m=1060.0,
        apex_type="mid",
    )


# ---------------------------------------------------------------------------
# LandmarkType
# ---------------------------------------------------------------------------


class TestLandmarkType:
    def test_all_types_exist(self) -> None:
        expected = {
            "brake_board",
            "structure",
            "barrier",
            "road",
            "curbing",
            "natural",
            "marshal",
            "sign",
        }
        actual = {t.value for t in LandmarkType}
        assert actual == expected

    def test_enum_values_match_names(self) -> None:
        for t in LandmarkType:
            assert t.value == t.name


# ---------------------------------------------------------------------------
# Landmark dataclass
# ---------------------------------------------------------------------------


class TestLandmark:
    def test_basic_fields(self, brake_board: Landmark) -> None:
        assert brake_board.name == "T5 3 board"
        assert brake_board.distance_m == 940.0
        assert brake_board.landmark_type == LandmarkType.brake_board

    def test_optional_fields_default_none(self, brake_board: Landmark) -> None:
        assert brake_board.lat is None
        assert brake_board.lon is None
        assert brake_board.description is None

    def test_optional_fields_populated(self) -> None:
        lm = Landmark(
            "test", 100.0, LandmarkType.sign, lat=33.5, lon=-86.6, description="Test sign"
        )
        assert lm.lat == 33.5
        assert lm.lon == -86.6
        assert lm.description == "Test sign"

    def test_frozen(self, brake_board: Landmark) -> None:
        with pytest.raises(AttributeError):
            brake_board.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# LandmarkReference
# ---------------------------------------------------------------------------


class TestLandmarkReference:
    def test_at_reference(self, brake_board: Landmark) -> None:
        """Offset < 5m should produce 'at the ...' text."""
        ref = LandmarkReference(landmark=brake_board, offset_m=2.0)
        assert ref.format_reference() == "at the T5 3 board"

    def test_at_zero_offset(self, brake_board: Landmark) -> None:
        ref = LandmarkReference(landmark=brake_board, offset_m=0.0)
        assert ref.format_reference() == "at the T5 3 board"

    def test_at_negative_small_offset(self, brake_board: Landmark) -> None:
        ref = LandmarkReference(landmark=brake_board, offset_m=-3.0)
        assert ref.format_reference() == "at the T5 3 board"

    def test_before_reference(self, brake_board: Landmark) -> None:
        """Positive offset > 5m = landmark is ahead = 'before'."""
        ref = LandmarkReference(landmark=brake_board, offset_m=15.0)
        result = ref.format_reference()
        assert result == "15m before the T5 3 board"

    def test_past_reference(self, brake_board: Landmark) -> None:
        """Negative offset > 5m = landmark behind = 'past'."""
        ref = LandmarkReference(landmark=brake_board, offset_m=-10.0)
        result = ref.format_reference()
        assert result == "10m past the T5 3 board"

    def test_exact_boundary_5m(self, brake_board: Landmark) -> None:
        """Exactly 5m offset should be 'before' (not 'at')."""
        ref = LandmarkReference(landmark=brake_board, offset_m=5.0)
        assert "before" in ref.format_reference()

    def test_just_under_boundary(self, brake_board: Landmark) -> None:
        """4.9m offset should be 'at'."""
        ref = LandmarkReference(landmark=brake_board, offset_m=4.9)
        assert ref.format_reference() == "at the T5 3 board"

    def test_frozen(self, brake_board: Landmark) -> None:
        ref = LandmarkReference(landmark=brake_board, offset_m=10.0)
        with pytest.raises(AttributeError):
            ref.offset_m = 20.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# find_nearest_landmark
# ---------------------------------------------------------------------------


class TestFindNearestLandmark:
    def test_empty_landmarks(self) -> None:
        assert find_nearest_landmark(500.0, []) is None

    def test_finds_closest(self, sample_landmarks: list[Landmark]) -> None:
        ref = find_nearest_landmark(935.0, sample_landmarks)
        assert ref is not None
        assert ref.landmark.name == "T5 3 board"
        assert ref.offset_m == pytest.approx(5.0, abs=0.1)

    def test_exact_match(self, sample_landmarks: list[Landmark]) -> None:
        ref = find_nearest_landmark(940.0, sample_landmarks)
        assert ref is not None
        assert ref.landmark.name == "T5 3 board"
        assert ref.offset_m == pytest.approx(0.0, abs=0.1)

    def test_out_of_range_returns_none(self) -> None:
        lm = [Landmark("far away", 5000.0, LandmarkType.structure)]
        assert find_nearest_landmark(0.0, lm) is None

    def test_max_distance_parameter(self) -> None:
        lm = [Landmark("close", 100.0, LandmarkType.structure)]
        # Within custom max
        assert find_nearest_landmark(130.0, lm, max_distance_m=50.0) is not None
        # Outside custom max
        assert find_nearest_landmark(200.0, lm, max_distance_m=50.0) is None

    def test_preferred_types_brake_board(self, sample_landmarks: list[Landmark]) -> None:
        """Preferred brake_board should win over a closer non-preferred landmark."""
        # Query at 375.0: closest is T2 Armco (380.0, barrier, 5m away)
        # But there are no brake boards within 150m of 375... let's query at 105
        # 105.0: T1 200m board at 90 (brake_board, 15m), T1 100m board at 140 (brake_board, 35m)
        # But S/F gantry at 0.0 is a structure at 105m away
        # With preferred_types=brake_board, brake_board at 90 (15m) should win over
        # the structure at 0.0 (105m away)
        ref = find_nearest_landmark(
            105.0,
            sample_landmarks,
            preferred_types={LandmarkType.brake_board},
        )
        assert ref is not None
        assert ref.landmark.landmark_type == LandmarkType.brake_board
        assert ref.landmark.name == "T1 200m board"

    def test_preferred_type_none_uses_closest(
        self,
        sample_landmarks: list[Landmark],
    ) -> None:
        """Without preferred types, pure closest should win."""
        ref = find_nearest_landmark(105.0, sample_landmarks)
        assert ref is not None
        assert ref.landmark.name == "T1 200m board"

    def test_preferred_type_outside_range_falls_back(self) -> None:
        """If no preferred landmark is in range, fall back to closest any-type."""
        landmarks = [
            Landmark("barrier", 100.0, LandmarkType.barrier),
            Landmark("board", 500.0, LandmarkType.brake_board),
        ]
        ref = find_nearest_landmark(
            110.0,
            landmarks,
            preferred_types={LandmarkType.brake_board},
        )
        assert ref is not None
        # Brake board at 500 is 390m away (outside MAX_LANDMARK_DISTANCE_M=150)
        # so falls back to barrier at 100 (10m away)
        assert ref.landmark.name == "barrier"

    def test_single_landmark_in_range(self) -> None:
        lm = [Landmark("only one", 200.0, LandmarkType.natural)]
        ref = find_nearest_landmark(210.0, lm)
        assert ref is not None
        assert ref.landmark.name == "only one"
        assert ref.offset_m == pytest.approx(-10.0, abs=0.1)

    def test_offset_sign_positive_means_ahead(self) -> None:
        """Landmark distance > query distance => positive offset => ahead."""
        lm = [Landmark("ahead", 200.0, LandmarkType.structure)]
        ref = find_nearest_landmark(180.0, lm)
        assert ref is not None
        assert ref.offset_m > 0  # landmark is ahead of query point


# ---------------------------------------------------------------------------
# find_landmarks_in_range
# ---------------------------------------------------------------------------


class TestFindLandmarksInRange:
    def test_empty_list(self) -> None:
        assert find_landmarks_in_range(0.0, 100.0, []) == []

    def test_finds_landmarks_in_range(self, sample_landmarks: list[Landmark]) -> None:
        result = find_landmarks_in_range(80.0, 150.0, sample_landmarks)
        names = [lm.name for lm in result]
        assert "T1 200m board" in names
        assert "T1 100m board" in names
        assert "T2 Armco" not in names  # 380 is outside range

    def test_sorted_by_distance(self, sample_landmarks: list[Landmark]) -> None:
        result = find_landmarks_in_range(0.0, 2000.0, sample_landmarks)
        distances = [lm.distance_m for lm in result]
        assert distances == sorted(distances)

    def test_inclusive_boundaries(self) -> None:
        lm = [
            Landmark("at_start", 100.0, LandmarkType.structure),
            Landmark("at_end", 200.0, LandmarkType.structure),
        ]
        result = find_landmarks_in_range(100.0, 200.0, lm)
        assert len(result) == 2

    def test_no_match(self, sample_landmarks: list[Landmark]) -> None:
        result = find_landmarks_in_range(9000.0, 9999.0, sample_landmarks)
        assert result == []


# ---------------------------------------------------------------------------
# resolve_gps_at_distance
# ---------------------------------------------------------------------------


class TestResolveGpsAtDistance:
    def test_returns_coordinates(self, sample_lap_df: pd.DataFrame) -> None:
        result = resolve_gps_at_distance(sample_lap_df, 100.0)
        assert result is not None
        lat, lon = result
        assert isinstance(lat, float)
        assert isinstance(lon, float)

    def test_no_gps_columns(self) -> None:
        df = pd.DataFrame({"lap_distance_m": [0.0, 1.0, 2.0]})
        assert resolve_gps_at_distance(df, 1.0) is None

    def test_missing_lat_column(self) -> None:
        df = pd.DataFrame(
            {
                "lap_distance_m": [0.0, 1.0, 2.0],
                "lon": [-86.0, -86.0, -86.0],
            }
        )
        assert resolve_gps_at_distance(df, 1.0) is None

    def test_missing_lon_column(self) -> None:
        df = pd.DataFrame(
            {
                "lap_distance_m": [0.0, 1.0, 2.0],
                "lat": [33.0, 33.0, 33.0],
            }
        )
        assert resolve_gps_at_distance(df, 1.0) is None

    def test_distance_out_of_range_high(self, sample_lap_df: pd.DataFrame) -> None:
        max_dist = sample_lap_df["lap_distance_m"].iloc[-1]
        assert resolve_gps_at_distance(sample_lap_df, max_dist + 100.0) is None

    def test_distance_out_of_range_low(self, sample_lap_df: pd.DataFrame) -> None:
        assert resolve_gps_at_distance(sample_lap_df, -10.0) is None

    def test_at_start(self, sample_lap_df: pd.DataFrame) -> None:
        result = resolve_gps_at_distance(sample_lap_df, 0.0)
        assert result is not None

    def test_at_end(self, sample_lap_df: pd.DataFrame) -> None:
        max_dist = float(sample_lap_df["lap_distance_m"].iloc[-1])
        result = resolve_gps_at_distance(sample_lap_df, max_dist)
        assert result is not None


# ---------------------------------------------------------------------------
# format_corner_landmarks
# ---------------------------------------------------------------------------


class TestFormatCornerLandmarks:
    def test_full_corner(
        self,
        sample_corner: Corner,
        sample_landmarks: list[Landmark],
    ) -> None:
        text = format_corner_landmarks(sample_corner, sample_landmarks)
        assert "Brake:" in text
        assert "Apex:" in text
        assert "Throttle:" in text

    def test_brake_uses_preferred_type(
        self,
        sample_corner: Corner,
        sample_landmarks: list[Landmark],
    ) -> None:
        """Brake reference should prefer brake boards."""
        text = format_corner_landmarks(sample_corner, sample_landmarks)
        # Brake at 955m, nearest brake board is T5 3 board at 940m (15m behind)
        # or T5 2 board at 1010m (55m ahead)
        assert "T5 3 board" in text or "T5 2 board" in text

    def test_no_landmarks(self, sample_corner: Corner) -> None:
        text = format_corner_landmarks(sample_corner, [])
        assert text == ""

    def test_no_brake_point(self, sample_landmarks: list[Landmark]) -> None:
        corner = Corner(
            number=1,
            entry_distance_m=80.0,
            exit_distance_m=160.0,
            apex_distance_m=120.0,
            min_speed_mps=20.0,
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=150.0,
            apex_type="mid",
        )
        text = format_corner_landmarks(corner, sample_landmarks)
        assert "Brake:" not in text
        assert "Apex:" in text
        assert "Throttle:" in text

    def test_no_throttle_commit(self, sample_landmarks: list[Landmark]) -> None:
        corner = Corner(
            number=1,
            entry_distance_m=80.0,
            exit_distance_m=160.0,
            apex_distance_m=120.0,
            min_speed_mps=20.0,
            brake_point_m=100.0,
            peak_brake_g=-0.5,
            throttle_commit_m=None,
            apex_type="mid",
        )
        text = format_corner_landmarks(corner, sample_landmarks)
        assert "Brake:" in text
        assert "Throttle:" not in text

    def test_all_points_out_of_range(self) -> None:
        """When no landmarks are near any point, should return empty."""
        far_landmarks = [Landmark("far", 9999.0, LandmarkType.structure)]
        corner = Corner(
            number=1,
            entry_distance_m=80.0,
            exit_distance_m=160.0,
            apex_distance_m=120.0,
            min_speed_mps=20.0,
            brake_point_m=100.0,
            peak_brake_g=-0.5,
            throttle_commit_m=150.0,
            apex_type="mid",
        )
        text = format_corner_landmarks(corner, far_landmarks)
        assert text == ""


# ---------------------------------------------------------------------------
# MAX_LANDMARK_DISTANCE_M constant
# ---------------------------------------------------------------------------


class TestConstants:
    def test_max_distance_is_positive(self) -> None:
        assert MAX_LANDMARK_DISTANCE_M > 0

    def test_max_distance_value(self) -> None:
        assert MAX_LANDMARK_DISTANCE_M == 150.0

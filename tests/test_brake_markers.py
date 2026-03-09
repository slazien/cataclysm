"""Tests for automatic brake marker computation."""

from __future__ import annotations

from cataclysm.brake_markers import compute_brake_markers
from cataclysm.landmarks import Landmark, LandmarkType
from cataclysm.track_db import OfficialCorner


class TestComputeBrakeMarkers:
    def test_generates_three_boards(self) -> None:
        corners = [OfficialCorner(5, "T5", 0.30, corner_type="hairpin")]
        markers = compute_brake_markers(corners, track_length_m=3662.4)
        assert len(markers) == 3
        assert all(isinstance(m, Landmark) for m in markers)
        assert all(m.landmark_type == LandmarkType.brake_board for m in markers)

    def test_markers_before_corner_entry(self) -> None:
        corners = [OfficialCorner(1, "T1", 0.50)]
        markers = compute_brake_markers(corners, track_length_m=4000.0)
        apex_dist = 0.50 * 4000.0  # 2000m — plenty of room for boards
        for m in markers:
            assert m.distance_m < apex_dist

    def test_skips_flat_corners(self) -> None:
        corners = [OfficialCorner(1, "Kink", 0.30, character="flat", corner_type="kink")]
        markers = compute_brake_markers(corners, track_length_m=1000.0)
        assert len(markers) == 0

    def test_skips_kink_corners(self) -> None:
        corners = [OfficialCorner(1, "Kink", 0.30, corner_type="kink")]
        markers = compute_brake_markers(corners, track_length_m=1000.0)
        assert len(markers) == 0

    def test_no_negative_distances(self) -> None:
        corners = [
            OfficialCorner(1, "T1", 0.10),
            OfficialCorner(2, "T2", 0.12),
        ]
        markers = compute_brake_markers(corners, track_length_m=1000.0)
        for m in markers:
            assert m.distance_m >= 0

    def test_marker_naming(self) -> None:
        corners = [OfficialCorner(5, "T5", 0.30)]
        markers = compute_brake_markers(corners, track_length_m=3000.0)
        names = [m.name for m in markers]
        assert "T5 3 board" in names
        assert "T5 2 board" in names
        assert "T5 1 board" in names

    def test_wraps_around_lap_start(self) -> None:
        corners = [OfficialCorner(1, "T1", 0.02)]
        markers = compute_brake_markers(corners, track_length_m=3000.0)
        for m in markers:
            assert 0 <= m.distance_m < 3000.0

    def test_wrap_around_produces_high_distances(self) -> None:
        """Markers for T1 near lap start should wrap to end of previous lap."""
        corners = [OfficialCorner(1, "T1", 0.02)]
        markers = compute_brake_markers(corners, track_length_m=3000.0)
        # apex at 60m, entry at 10m, boards at -290, -190, -90
        # after wrapping: 2710, 2810, 2910
        assert any(m.distance_m > 2500.0 for m in markers)

    def test_empty_corners(self) -> None:
        markers = compute_brake_markers([], track_length_m=3000.0)
        assert markers == []

    def test_zero_track_length(self) -> None:
        corners = [OfficialCorner(1, "T1", 0.30)]
        markers = compute_brake_markers(corners, track_length_m=0.0)
        assert markers == []

    def test_multiple_corners(self) -> None:
        corners = [
            OfficialCorner(1, "T1", 0.20, corner_type="hairpin"),
            OfficialCorner(2, "T2", 0.50, corner_type="sweeper"),
        ]
        markers = compute_brake_markers(corners, track_length_m=4000.0)
        assert len(markers) == 6  # 3 per corner
        t1_markers = [m for m in markers if m.name.startswith("T1")]
        t2_markers = [m for m in markers if m.name.startswith("T2")]
        assert len(t1_markers) == 3
        assert len(t2_markers) == 3

    def test_flat_skipped_but_brake_included(self) -> None:
        """Flat corners skipped, braking corners included."""
        corners = [
            OfficialCorner(1, "Flat Kink", 0.20, character="flat"),
            OfficialCorner(2, "T2", 0.50, corner_type="hairpin"),
        ]
        markers = compute_brake_markers(corners, track_length_m=3000.0)
        assert len(markers) == 3
        assert all("T2" in m.name for m in markers)

    def test_marker_distances_ordered(self) -> None:
        """3-board is furthest from corner, 1-board is closest."""
        corners = [OfficialCorner(5, "T5", 0.50)]
        markers = compute_brake_markers(corners, track_length_m=4000.0)
        by_name = {m.name: m.distance_m for m in markers}
        assert by_name["T5 3 board"] < by_name["T5 2 board"] < by_name["T5 1 board"]

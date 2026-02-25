"""Tests for cataclysm.sectors: sector time analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.corners import Corner
from cataclysm.sectors import (
    SectorAnalysis,
    compute_sector_analysis,
)


def _make_resampled_lap(
    max_dist: float = 1000.0,
    lap_time: float = 60.0,
    n_points: int = 500,
) -> pd.DataFrame:
    """Build a simple resampled lap with linear time progression."""
    distance = np.linspace(0, max_dist, n_points)
    time = np.linspace(0, lap_time, n_points)
    speed = np.full(n_points, max_dist / lap_time)
    return pd.DataFrame(
        {
            "lap_distance_m": distance,
            "lap_time_s": time,
            "speed_mps": speed,
        }
    )


def _make_corners(max_dist: float = 1000.0) -> list[Corner]:
    """Build two simple corners at known positions."""
    return [
        Corner(
            number=1,
            entry_distance_m=200.0,
            exit_distance_m=400.0,
            apex_distance_m=300.0,
            min_speed_mps=15.0,
            brake_point_m=180.0,
            peak_brake_g=-0.8,
            throttle_commit_m=350.0,
            apex_type="mid",
        ),
        Corner(
            number=2,
            entry_distance_m=600.0,
            exit_distance_m=800.0,
            apex_distance_m=700.0,
            min_speed_mps=20.0,
            brake_point_m=580.0,
            peak_brake_g=-0.6,
            throttle_commit_m=750.0,
            apex_type="late",
        ),
    ]


class TestComputeSectorAnalysis:
    def test_basic_two_corner_two_lap(self) -> None:
        resampled = {
            1: _make_resampled_lap(lap_time=60.0),
            2: _make_resampled_lap(lap_time=62.0),
        }
        corners = _make_corners()
        result = compute_sector_analysis(resampled, corners, [1, 2], best_lap=1)
        assert isinstance(result, SectorAnalysis)
        assert len(result.lap_splits) == 2
        assert result.lap_splits[0].lap_number == 1
        assert result.lap_splits[1].lap_number == 2

    def test_segments_cover_full_track(self) -> None:
        resampled = {1: _make_resampled_lap(), 2: _make_resampled_lap(lap_time=62.0)}
        corners = _make_corners()
        result = compute_sector_analysis(resampled, corners, [1, 2], best_lap=1)
        # Segments should alternate: straight, corner, straight, corner, straight
        assert len(result.segments) >= 3  # At least corners + straights
        corner_segs = [s for s in result.segments if s.is_corner]
        assert len(corner_segs) == 2

    def test_personal_best_identification(self) -> None:
        # Lap 1 is faster overall
        resampled = {
            1: _make_resampled_lap(lap_time=60.0),
            2: _make_resampled_lap(lap_time=62.0),
        }
        corners = _make_corners()
        result = compute_sector_analysis(resampled, corners, [1, 2], best_lap=1)
        # Lap 1 should have all personal bests (since uniform speed, all sectors faster)
        lap1_splits = result.lap_splits[0]
        pb_count = sum(1 for s in lap1_splits.splits if s.is_personal_best)
        assert pb_count > 0

    def test_composite_time_is_sum_of_bests(self) -> None:
        resampled = {
            1: _make_resampled_lap(lap_time=60.0),
            2: _make_resampled_lap(lap_time=62.0),
        }
        corners = _make_corners()
        result = compute_sector_analysis(resampled, corners, [1, 2], best_lap=1)
        assert result.composite_time_s == pytest.approx(
            sum(result.best_sector_times.values()), abs=0.01
        )

    def test_no_corners_single_sector(self) -> None:
        resampled = {
            1: _make_resampled_lap(lap_time=60.0),
            2: _make_resampled_lap(lap_time=62.0),
        }
        result = compute_sector_analysis(resampled, [], [1, 2], best_lap=1)
        # With no corners, should be one big straight segment
        assert len(result.segments) == 1
        assert not result.segments[0].is_corner
        assert len(result.lap_splits[0].splits) == 1

    def test_single_lap(self) -> None:
        resampled = {1: _make_resampled_lap(lap_time=60.0)}
        corners = _make_corners()
        result = compute_sector_analysis(resampled, corners, [1], best_lap=1)
        assert len(result.lap_splits) == 1
        # Single lap: all sectors are personal bests
        pb_count = sum(1 for s in result.lap_splits[0].splits if s.is_personal_best)
        assert pb_count == len(result.segments)

    def test_best_sector_laps_populated(self) -> None:
        resampled = {
            1: _make_resampled_lap(lap_time=60.0),
            2: _make_resampled_lap(lap_time=62.0),
        }
        corners = _make_corners()
        result = compute_sector_analysis(resampled, corners, [1, 2], best_lap=1)
        assert len(result.best_sector_laps) == len(result.segments)
        for _seg_name, lap_num in result.best_sector_laps.items():
            assert lap_num in [1, 2]

    def test_split_times_round_trip(self) -> None:
        """Each lap's sector times should sum to approximately the total."""
        resampled = {
            1: _make_resampled_lap(lap_time=60.0),
            2: _make_resampled_lap(lap_time=62.0),
        }
        corners = _make_corners()
        result = compute_sector_analysis(resampled, corners, [1, 2], best_lap=1)
        for ls in result.lap_splits:
            split_sum = sum(s.time_s for s in ls.splits)
            assert split_sum == pytest.approx(ls.total_time_s, abs=0.01)

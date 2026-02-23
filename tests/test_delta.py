"""Tests for cataclysm.delta."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cataclysm.corners import Corner
from cataclysm.delta import DeltaResult, compute_delta


def _make_lap(n_points: int, speed: float, step_m: float = 0.7) -> pd.DataFrame:
    """Create a synthetic resampled lap."""
    distance = np.arange(n_points) * step_m
    time = distance / speed  # constant speed
    return pd.DataFrame(
        {
            "lap_distance_m": distance,
            "lap_time_s": time,
            "speed_mps": np.full(n_points, speed),
        }
    )


class TestComputeDelta:
    def test_identical_laps_zero_delta(self) -> None:
        lap = _make_lap(500, speed=30.0)
        result = compute_delta(lap, lap)
        np.testing.assert_allclose(result.delta_time_s, 0.0, atol=1e-10)
        assert result.total_delta_s == 0.0

    def test_slower_comp_positive_delta(self) -> None:
        ref = _make_lap(500, speed=30.0)
        comp = _make_lap(500, speed=25.0)  # slower
        result = compute_delta(ref, comp)
        # Slower comparison -> positive delta
        assert result.delta_time_s[-1] > 0
        assert result.total_delta_s > 0

    def test_faster_comp_negative_delta(self) -> None:
        ref = _make_lap(500, speed=25.0)
        comp = _make_lap(500, speed=30.0)  # faster
        result = compute_delta(ref, comp)
        assert result.delta_time_s[-1] < 0
        assert result.total_delta_s < 0

    def test_truncates_to_shorter_lap(self) -> None:
        ref = _make_lap(500, speed=30.0)
        comp = _make_lap(300, speed=30.0)  # shorter
        result = compute_delta(ref, comp)
        max_comp_dist = comp["lap_distance_m"].iloc[-1]
        assert result.distance_m[-1] <= max_comp_dist

    def test_corner_deltas(self) -> None:
        ref = _make_lap(500, speed=30.0)
        comp = _make_lap(500, speed=25.0)
        corners = [
            Corner(1, 50.0, 100.0, 75.0, 20.0, None, None, None, "mid"),
            Corner(2, 200.0, 250.0, 225.0, 18.0, None, None, None, "mid"),
        ]
        result = compute_delta(ref, comp, corners=corners)
        assert len(result.corner_deltas) == 2
        for cd in result.corner_deltas:
            assert cd.corner_number in (1, 2)
            # Slower comp -> positive corner delta
            assert cd.delta_s > 0

    def test_result_type(self) -> None:
        ref = _make_lap(500, speed=30.0)
        comp = _make_lap(500, speed=30.0)
        result = compute_delta(ref, comp)
        assert isinstance(result, DeltaResult)
        assert isinstance(result.distance_m, np.ndarray)
        assert isinstance(result.delta_time_s, np.ndarray)
        assert len(result.distance_m) == len(result.delta_time_s)

    def test_empty_corners_list(self) -> None:
        ref = _make_lap(500, speed=30.0)
        comp = _make_lap(500, speed=25.0)
        result = compute_delta(ref, comp, corners=[])
        assert result.corner_deltas == []

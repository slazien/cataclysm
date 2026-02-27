"""Tests for mini_sectors module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.mini_sectors import compute_mini_sectors


def _make_lap(lap_num: int, speed_factor: float = 1.0) -> pd.DataFrame:
    """Create a synthetic resampled lap DataFrame."""
    n_points = 1000
    distance = np.linspace(0, 3000, n_points)
    # Simulate varying speed
    speed = 30.0 * speed_factor + 5.0 * np.sin(distance / 200)
    elapsed = np.cumsum(np.diff(distance, prepend=0) / np.maximum(speed, 1.0))
    lat = 33.5 + distance / 3000 * 0.01
    lon = -86.6 + np.sin(distance / 500) * 0.005
    return pd.DataFrame(
        {
            "lap_distance_m": distance,
            "lap_time_s": elapsed,
            "speed_mps": speed,
            "lat": lat,
            "lon": lon,
        }
    )


def test_basic_mini_sectors() -> None:
    """Test that mini sectors are computed correctly with synthetic data."""
    resampled = {
        1: _make_lap(1, 1.0),
        2: _make_lap(2, 1.1),  # faster (higher speed_factor = higher speed = lower time)
        3: _make_lap(3, 0.9),  # slower
    }
    clean_laps = [1, 2, 3]
    best_lap = 2

    result = compute_mini_sectors(resampled, clean_laps, best_lap, n_sectors=10)

    assert result.n_sectors == 10
    assert len(result.sectors) == 10
    assert len(result.best_sector_times_s) == 10
    assert len(result.best_sector_laps) == 10
    assert len(result.lap_data) == 3

    # Sectors should cover the track
    assert result.sectors[0].entry_distance_m == 0.0
    assert result.sectors[-1].exit_distance_m == pytest.approx(3000.0)

    # Each sector should have GPS points
    for sector in result.sectors:
        assert len(sector.gps_points) > 0

    # Best sector times should be positive
    for t in result.best_sector_times_s:
        assert t > 0

    # Lap 2 (fastest) should have the most PB sectors
    lap2 = result.lap_data[2]
    assert "pb" in lap2.classifications


def test_single_lap() -> None:
    """Test with only one lap."""
    resampled = {1: _make_lap(1)}
    result = compute_mini_sectors(resampled, [1], 1, n_sectors=5)

    assert result.n_sectors == 5
    assert len(result.sectors) == 5
    assert len(result.lap_data) == 1
    # With only one lap, all sectors should be PB
    assert all(c == "pb" for c in result.lap_data[1].classifications)


def test_empty_input() -> None:
    """Test with empty input."""
    result = compute_mini_sectors({}, [], 1, n_sectors=10)
    assert result.n_sectors == 10
    assert len(result.sectors) == 0
    assert len(result.lap_data) == 0


def test_sector_count() -> None:
    """Test different sector counts."""
    resampled = {1: _make_lap(1)}
    for n in [3, 10, 50]:
        result = compute_mini_sectors(resampled, [1], 1, n_sectors=n)
        assert len(result.sectors) == n
        assert len(result.best_sector_times_s) == n


def test_delta_calculation() -> None:
    """Test that deltas are computed correctly."""
    resampled = {
        1: _make_lap(1, 1.0),
        2: _make_lap(2, 1.2),  # faster (higher speed = less time)
    }
    result = compute_mini_sectors(resampled, [1, 2], 2, n_sectors=5)

    # Lap 1 (slower) should have positive deltas vs best
    lap1 = result.lap_data[1]
    assert all(d >= -0.001 for d in lap1.deltas_s)

    # Lap 2 (best in each sector) should have zero or near-zero deltas
    lap2 = result.lap_data[2]
    assert all(abs(d) < 0.01 for d in lap2.deltas_s)

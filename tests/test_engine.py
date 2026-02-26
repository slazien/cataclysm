"""Tests for cataclysm.engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.engine import (
    RESAMPLE_STEP_M,
    LapSummary,
    ProcessedSession,
    _compute_lap_distance,
    _compute_lap_time,
    _filter_short_laps,
    _resample_lap,
    _split_laps,
    find_anomalous_laps,
    process_session,
)


class TestSplitLaps:
    def test_splits_by_lap_number(self) -> None:
        df = pd.DataFrame(
            {
                "lap_number": [np.nan] * 5 + [1.0] * 20 + [2.0] * 20,
                "elapsed_time": np.arange(45, dtype=float),
                "distance_m": np.arange(45, dtype=float) * 10,
                "speed_mps": np.ones(45) * 30,
                "lat": np.ones(45) * 33.5,
                "lon": np.ones(45) * -86.6,
            }
        )
        laps = _split_laps(df)
        assert set(laps.keys()) == {1, 2}
        assert len(laps[1]) == 20
        assert len(laps[2]) == 20

    def test_excludes_nan_lap_number(self) -> None:
        df = pd.DataFrame(
            {
                "lap_number": [np.nan] * 10,
                "elapsed_time": np.arange(10, dtype=float),
            }
        )
        laps = _split_laps(df)
        assert len(laps) == 0

    def test_excludes_short_laps(self) -> None:
        df = pd.DataFrame(
            {
                "lap_number": [1.0] * 5,  # only 5 rows, below threshold of 10
                "elapsed_time": np.arange(5, dtype=float),
            }
        )
        laps = _split_laps(df)
        assert len(laps) == 0


class TestComputeLapDistance:
    def test_subtracts_start_distance(self) -> None:
        df = pd.DataFrame({"distance_m": [100.0, 200.0, 300.0]})
        result = _compute_lap_distance(df)
        assert result["lap_distance_m"].iloc[0] == 0.0
        assert result["lap_distance_m"].iloc[-1] == 200.0

    def test_original_unchanged(self) -> None:
        df = pd.DataFrame({"distance_m": [100.0, 200.0, 300.0]})
        _compute_lap_distance(df)
        assert df["distance_m"].iloc[0] == 100.0


class TestComputeLapTime:
    def test_subtracts_start_time(self) -> None:
        df = pd.DataFrame({"elapsed_time": [10.0, 11.0, 12.0]})
        result = _compute_lap_time(df)
        assert result["lap_time_s"].iloc[0] == 0.0
        assert result["lap_time_s"].iloc[-1] == 2.0


class TestResampleLap:
    def test_resamples_at_correct_step(self) -> None:
        n = 100
        df = pd.DataFrame(
            {
                "lap_distance_m": np.arange(n, dtype=float) * 5.0,
                "lap_time_s": np.arange(n, dtype=float) * 0.1,
                "speed_mps": np.ones(n) * 30.0,
                "heading_deg": np.linspace(0, 180, n),
                "lat": np.ones(n) * 33.5,
                "lon": np.ones(n) * -86.6,
                "lateral_g": np.zeros(n),
                "longitudinal_g": np.zeros(n),
                "yaw_rate_dps": np.zeros(n),
                "altitude_m": np.ones(n) * 200,
                "x_acc_g": np.zeros(n),
                "y_acc_g": np.zeros(n),
                "z_acc_g": np.ones(n),
            }
        )
        result = _resample_lap(df, step_m=0.7)
        assert not result.empty
        diffs = np.diff(result["lap_distance_m"].to_numpy())
        np.testing.assert_allclose(diffs, 0.7, atol=1e-10)

    def test_heading_wrap_handled(self) -> None:
        """Heading should interpolate correctly across 360/0 boundary."""
        n = 100
        heading = np.linspace(350, 370, n) % 360  # wraps from 350 through 0 to 10
        df = pd.DataFrame(
            {
                "lap_distance_m": np.arange(n, dtype=float) * 5.0,
                "lap_time_s": np.arange(n, dtype=float) * 0.1,
                "speed_mps": np.ones(n) * 30.0,
                "heading_deg": heading,
                "lat": np.ones(n) * 33.5,
                "lon": np.ones(n) * -86.6,
            }
        )
        result = _resample_lap(df)
        # The underlying interpolation should be smooth.
        # After % 360 there will be one wrap point; check angular diffs.
        h = result["heading_deg"].to_numpy()
        angular_diffs = (np.diff(h) + 180) % 360 - 180
        # All angular diffs should be small (no spurious jumps)
        assert np.max(np.abs(angular_diffs[5:-5])) < 5.0

    def test_empty_for_short_lap(self) -> None:
        df = pd.DataFrame(
            {
                "lap_distance_m": [0.0, 1.0, 2.0],
                "lap_time_s": [0.0, 0.1, 0.2],
                "speed_mps": [10.0, 10.0, 10.0],
            }
        )
        result = _resample_lap(df)
        assert result.empty


class TestFilterShortLaps:
    def test_removes_short_laps(self) -> None:
        lap1 = pd.DataFrame({"lap_distance_m": [0.0, 100.0, 500.0]})
        lap2 = pd.DataFrame({"lap_distance_m": [0.0, 50.0, 100.0]})  # too short
        lap3 = pd.DataFrame({"lap_distance_m": [0.0, 100.0, 480.0]})

        laps = {1: lap1, 2: lap2, 3: lap3}
        filtered = _filter_short_laps(laps)
        assert 2 not in filtered
        assert 1 in filtered
        assert 3 in filtered

    def test_single_lap_kept(self) -> None:
        lap = pd.DataFrame({"lap_distance_m": [0.0, 500.0]})
        laps = {1: lap}
        filtered = _filter_short_laps(laps)
        assert 1 in filtered


class TestProcessSession:
    def test_produces_processed_session(self, parsed_session: object) -> None:
        result = process_session(parsed_session.data)  # type: ignore[union-attr]
        assert isinstance(result, ProcessedSession)
        assert len(result.lap_summaries) > 0
        assert len(result.resampled_laps) > 0
        assert result.best_lap in result.resampled_laps

    def test_best_lap_is_fastest(self, parsed_session: object) -> None:
        result = process_session(parsed_session.data)  # type: ignore[union-attr]
        best = result.best_lap
        best_time = next(s.lap_time_s for s in result.lap_summaries if s.lap_number == best)
        for s in result.lap_summaries:
            assert s.lap_time_s >= best_time

    def test_summaries_sorted_by_time(self, parsed_session: object) -> None:
        result = process_session(parsed_session.data)  # type: ignore[union-attr]
        times = [s.lap_time_s for s in result.lap_summaries]
        assert times == sorted(times)

    def test_resampled_laps_uniform_distance(self, parsed_session: object) -> None:
        result = process_session(parsed_session.data)  # type: ignore[union-attr]
        for lap_df in result.resampled_laps.values():
            diffs = np.diff(lap_df["lap_distance_m"].to_numpy())
            np.testing.assert_allclose(diffs, RESAMPLE_STEP_M, atol=1e-10)

    def test_raises_on_empty_data(self) -> None:
        df = pd.DataFrame(
            {
                "lap_number": [np.nan] * 5,
                "elapsed_time": np.arange(5, dtype=float),
                "distance_m": np.arange(5, dtype=float),
                "speed_mps": np.ones(5),
                "lat": np.ones(5),
                "lon": np.ones(5),
            }
        )
        with pytest.raises(ValueError, match="No laps found"):
            process_session(df)


def _make_summary(lap: int, time: float) -> LapSummary:
    return LapSummary(lap_number=lap, lap_time_s=time, lap_distance_m=3669.0, max_speed_mps=45.0)


class TestFindAnomalousLaps:
    def test_flags_obvious_outlier(self) -> None:
        # L1–L6 tight cluster, L7 nearly double
        sums = [
            _make_summary(1, 109.57),
            _make_summary(2, 108.43),
            _make_summary(3, 110.24),
            _make_summary(4, 110.94),
            _make_summary(5, 113.12),
            _make_summary(6, 116.02),
            _make_summary(7, 208.79),
        ]
        assert find_anomalous_laps(sums) == {7}

    def test_no_anomalies_in_tight_session(self) -> None:
        sums = [
            _make_summary(1, 110.0),
            _make_summary(2, 108.5),
            _make_summary(3, 111.0),
            _make_summary(4, 109.5),
        ]
        assert find_anomalous_laps(sums) == set()

    def test_single_lap_returns_empty(self) -> None:
        sums = [_make_summary(1, 110.0)]
        assert find_anomalous_laps(sums) == set()

    def test_two_laps_no_outlier(self) -> None:
        # 200/155 median = 1.29x — below 1.5x ratio threshold
        sums = [_make_summary(1, 110.0), _make_summary(2, 200.0)]
        assert find_anomalous_laps(sums) == set()

    def test_two_laps_extreme_outlier_flagged_by_ratio(self) -> None:
        # median = 155, 350/155 = 2.26x — above 1.5x ratio threshold
        sums = [_make_summary(1, 110.0), _make_summary(2, 350.0)]
        assert find_anomalous_laps(sums) == {2}

    def test_multiple_outliers(self) -> None:
        sums = [
            _make_summary(1, 109.0),
            _make_summary(2, 108.5),
            _make_summary(3, 110.0),
            _make_summary(4, 111.0),
            _make_summary(5, 110.5),
            _make_summary(6, 109.5),
            _make_summary(7, 210.0),
            _make_summary(8, 250.0),
        ]
        anomalous = find_anomalous_laps(sums)
        assert 7 in anomalous
        assert 8 in anomalous
        assert 1 not in anomalous

    def test_ratio_catches_pit_stop_lap(self) -> None:
        # Real scenario: 12-minute red flag lap among normal ~109-113s laps
        sums = [
            _make_summary(1, 112.5),
            _make_summary(2, 109.3),
            _make_summary(3, 110.0),
            _make_summary(4, 111.6),
            _make_summary(5, 108.4),
            _make_summary(6, 110.6),
            _make_summary(7, 108.5),
            _make_summary(8, 113.3),
            _make_summary(9, 718.4),  # 12-minute red flag
        ]
        anomalous = find_anomalous_laps(sums)
        assert 9 in anomalous
        # Normal laps within the cluster should not be flagged
        for lap in [2, 3, 4, 5, 6, 7]:
            assert lap not in anomalous

    def test_high_variance_session_ratio_catches_extreme(self) -> None:
        # Pathological case: lots of variance makes IQR wide, but ratio still catches
        sums = [
            _make_summary(1, 100.0),
            _make_summary(2, 150.0),
            _make_summary(3, 200.0),
            _make_summary(4, 250.0),
            _make_summary(5, 300.0),
            _make_summary(6, 350.0),
            _make_summary(7, 800.0),  # extreme outlier
        ]
        anomalous = find_anomalous_laps(sums)
        assert 7 in anomalous

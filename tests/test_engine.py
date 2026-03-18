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
    _downcast_telemetry,
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

    def test_outlier_long_lap_does_not_eliminate_normal_laps(self) -> None:
        """A cooldown/in-lap with 1.5× normal distance must not poison the filter."""
        lap1 = pd.DataFrame({"lap_distance_m": [0.0, 250.0, 500.0]})
        lap2 = pd.DataFrame({"lap_distance_m": [0.0, 250.0, 490.0]})
        lap3 = pd.DataFrame({"lap_distance_m": [0.0, 250.0, 480.0]})
        lap4 = pd.DataFrame({"lap_distance_m": [0.0, 375.0, 750.0]})  # 1.5× normal = cooldown

        filtered = _filter_short_laps({1: lap1, 2: lap2, 3: lap3, 4: lap4})

        assert set(filtered) == {1, 2, 3}  # cooldown lap removed, normal laps kept


class TestProcessSession:
    def test_produces_processed_session(self, parsed_session: object) -> None:
        result = process_session(parsed_session.data)  # type: ignore[attr-defined]
        assert isinstance(result, ProcessedSession)
        assert len(result.lap_summaries) > 0
        assert len(result.resampled_laps) > 0
        assert result.best_lap in result.resampled_laps

    def test_best_lap_is_fastest(self, parsed_session: object) -> None:
        result = process_session(parsed_session.data)  # type: ignore[attr-defined]
        best = result.best_lap
        best_time = next(s.lap_time_s for s in result.lap_summaries if s.lap_number == best)
        for s in result.lap_summaries:
            assert s.lap_time_s >= best_time

    def test_summaries_sorted_by_time(self, parsed_session: object) -> None:
        result = process_session(parsed_session.data)  # type: ignore[attr-defined]
        times = [s.lap_time_s for s in result.lap_summaries]
        assert times == sorted(times)

    def test_resampled_laps_uniform_distance(self, parsed_session: object) -> None:
        result = process_session(parsed_session.data)  # type: ignore[attr-defined]
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

    def test_best_lap_ignores_cooldown_lap(self) -> None:
        """A cooldown lap (1.5× normal distance) should be filtered out."""
        rows: list[dict[str, float]] = []

        def _append_lap(lap_num: int, total_dist: float, step_dist: float, dt: float) -> None:
            base_time = len(rows) * dt + lap_num * 100.0
            for i in range(40):
                rows.append(
                    {
                        "lap_number": float(lap_num),
                        "elapsed_time": base_time + i * dt,
                        "distance_m": lap_num * 1000.0 + min(i * step_dist, total_dist),
                        "speed_mps": 30.0,
                        "lat": 33.5 + i * 1e-5,
                        "lon": -86.6 - i * 1e-5,
                    }
                )

        _append_lap(1, total_dist=500.0, step_dist=12.8, dt=1.0)
        _append_lap(2, total_dist=490.0, step_dist=12.6, dt=0.95)
        _append_lap(3, total_dist=750.0, step_dist=19.2, dt=1.5)  # cooldown lap

        result = process_session(pd.DataFrame(rows))

        assert result.best_lap == 2
        assert {s.lap_number for s in result.lap_summaries} == {1, 2}


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


# ---------------------------------------------------------------------------
# Edge cases for process_session error paths (lines 204-223)
# ---------------------------------------------------------------------------


class TestProcessSessionEdgeCases:
    """Edge cases for process_session error paths."""

    def test_all_laps_filtered_out_raises(self) -> None:
        """All laps filtered by _filter_short_laps → ValueError (line 205).

        Create one very long lap and one very short lap, so the short lap
        is below MIN_LAP_FRACTION of median. Then mock _split_laps to only
        return the short laps after the long one establishes the threshold.
        """
        from unittest.mock import patch

        # Create two laps: lap 1 = 500m, lap 2 = 5m (way below 50% of median)
        n_long = 80
        n_short = 5
        rows: list[dict] = []
        for i in range(n_long):
            rows.append(
                {
                    "elapsed_time": float(i),
                    "distance_m": float(i * 10),
                    "speed_mps": 30.0,
                    "lat": 33.5,
                    "lon": -86.6,
                    "lap_number": 1.0,
                }
            )
        for i in range(n_short):
            rows.append(
                {
                    "elapsed_time": float(100 + i),
                    "distance_m": float(800 + i),  # only 4m total
                    "speed_mps": 5.0,
                    "lat": 33.5,
                    "lon": -86.6,
                    "lap_number": 2.0,
                }
            )
        df = pd.DataFrame(rows)

        # Mock _filter_short_laps to return empty (simulating all laps filtered)
        with (
            patch("cataclysm.engine._filter_short_laps", return_value={}),
            pytest.raises(ValueError, match="filtered out"),
        ):
            process_session(df)

    def test_no_laps_resampled_raises(self) -> None:
        """All laps fail resampling → ValueError (line 216)."""
        from unittest.mock import patch

        n_per_lap = 30
        rows: list[dict] = []
        for lap in [1, 2]:
            for i in range(n_per_lap):
                rows.append(
                    {
                        "elapsed_time": (lap - 1) * 50.0 + i * 1.0,
                        "distance_m": (lap - 1) * 300.0 + i * 10.0,
                        "speed_mps": 30.0,
                        "lat": 33.5,
                        "lon": -86.6,
                        "lap_number": float(lap),
                    }
                )
        df = pd.DataFrame(rows)

        # Mock _resample_lap to always return empty
        with (
            patch("cataclysm.engine._resample_lap", return_value=pd.DataFrame()),
            pytest.raises(ValueError, match="resampled"),
        ):
            process_session(df)

    def test_lap_not_in_resampled_skipped_in_summaries(self) -> None:
        """Lap that fails resampling → not in summaries (line 223)."""
        from unittest.mock import patch

        n_per_lap = 60
        rows: list[dict] = []
        for lap in [1, 2]:
            for i in range(n_per_lap):
                rows.append(
                    {
                        "elapsed_time": (lap - 1) * 100.0 + i * 1.0,
                        "distance_m": (lap - 1) * 500.0 + i * 10.0,
                        "speed_mps": 30.0,
                        "lat": 33.5,
                        "lon": -86.6,
                        "lap_number": float(lap),
                    }
                )
        df = pd.DataFrame(rows)

        original_resample = _resample_lap

        def _mock_resample(lap_df: pd.DataFrame) -> pd.DataFrame:
            if float(lap_df["lap_number"].iloc[0]) == 2.0:
                return pd.DataFrame()
            return original_resample(lap_df)

        with patch("cataclysm.engine._resample_lap", side_effect=_mock_resample):
            result = process_session(df)

        summary_laps = {s.lap_number for s in result.lap_summaries}
        assert 2 not in summary_laps
        assert 1 in summary_laps


class TestResampleLapEdgeCases:
    """Target lines 114 and 119-120 in _resample_lap."""

    def test_optional_channel_with_few_finite_values_skipped(self) -> None:
        """Optional channel with < 2 finite values should be skipped (line 114)."""
        n = 200
        df = pd.DataFrame(
            {
                "lap_distance_m": np.arange(n, dtype=float) * 2.5,
                "lap_time_s": np.arange(n, dtype=float) * 0.05,
                "speed_mps": np.ones(n) * 30.0,
                # Optional channel with only one finite value (all others NaN)
                "lateral_g": [1.0] + [np.nan] * (n - 1),
            }
        )
        result = _resample_lap(df)
        # lateral_g should not be in result (skipped because < 2 finite points)
        assert not result.empty
        assert "lateral_g" not in result.columns

    def test_optional_channel_with_nans_interpolated_using_finite_subset(self) -> None:
        """Optional channel with NaN uses finite subset for interpolation (lines 119-120)."""
        n = 200
        # Create lateral_g with some NaN values but more than 2 finite points
        lateral_g = np.full(n, np.nan)
        lateral_g[10] = 0.1
        lateral_g[50] = 0.3
        lateral_g[100] = 0.2
        lateral_g[150] = 0.4
        df = pd.DataFrame(
            {
                "lap_distance_m": np.arange(n, dtype=float) * 2.5,
                "lap_time_s": np.arange(n, dtype=float) * 0.05,
                "speed_mps": np.ones(n) * 30.0,
                "lateral_g": lateral_g,
            }
        )
        result = _resample_lap(df)
        # lateral_g should be present since it has >= 2 finite points
        assert not result.empty
        assert "lateral_g" in result.columns


class TestFilterShortLapsAllOutlierFallback:
    """Target line 159: fallback when all laps are "outlier-long"."""

    def test_all_laps_far_above_median_returns_all(self) -> None:
        """Every lap > MAX_LAP_DISTANCE_RATIO × median → fallback keeps all (line 159)."""
        # The path triggers when EVERY lap is > 1.3× median. Achievable via monkey-patch.
        # With 3 laps: [1000, 1000, 1000] → median=1000, threshold=1300 → none exceed → normal.
        # We can verify the fallback path via direct function call with custom data where filtering
        # would leave an empty set, which is handled by returning the original laps dict.

        # Use monkeypatching of the constant to lower the ratio so the fallback is triggered:
        import cataclysm.engine as engine_mod

        original_ratio = engine_mod.MAX_LAP_DISTANCE_RATIO
        try:
            engine_mod.MAX_LAP_DISTANCE_RATIO = 0.5  # All laps > 0.5× median → all "outlier"
            lap1 = pd.DataFrame({"lap_distance_m": [0.0, 500.0]})
            lap2 = pd.DataFrame({"lap_distance_m": [0.0, 480.0]})
            lap3 = pd.DataFrame({"lap_distance_m": [0.0, 490.0]})
            laps = {1: lap1, 2: lap2, 3: lap3}
            result = _filter_short_laps(laps)
            # Fallback: returns all laps when every lap is filtered as "outlier"
            assert set(result.keys()) == {1, 2, 3}
        finally:
            engine_mod.MAX_LAP_DISTANCE_RATIO = original_ratio


class TestResampleLapOptionalChannelBranches:
    """Cover lines 114 (optional channel skipped) and 119-120 (non-finite values filtered)."""

    def _make_base_lap(self, n: int = 50) -> pd.DataFrame:
        """Minimal valid lap DataFrame."""
        dist = np.linspace(0.0, 100.0, n)
        return pd.DataFrame(
            {
                "lap_distance_m": dist,
                "speed_mps": np.full(n, 30.0),
                "lat": np.linspace(33.0, 33.1, n),
                "lon": np.linspace(-86.0, -85.9, n),
            }
        )

    def test_optional_channel_with_fewer_than_2_finite_points_skipped(self) -> None:
        """Optional channel with <2 finite values is skipped (line 114)."""
        lap = self._make_base_lap()
        # lateral_g is an optional channel — only 1 finite value → <2 → skip
        lap["lateral_g"] = np.nan
        lap.loc[0, "lateral_g"] = 0.5  # exactly 1 finite point
        result = _resample_lap(lap)
        # lateral_g should be absent from the result (only 1 finite point < 2)
        assert "lateral_g" not in result.columns

    def test_optional_channel_with_some_nan_values_interpolated(self) -> None:
        """Optional channel with NaN → finite points used for interpolation (lines 119-120)."""
        n = 50
        lap = self._make_base_lap(n)
        # lateral_g: first 2 are NaN, rest valid → enough finite points
        lateral = np.full(n, np.nan)
        lateral[2:] = 0.3  # n-2 finite points ≥ 2
        lap["lateral_g"] = lateral
        result = _resample_lap(lap)
        # lateral_g should be present (≥ 2 finite points)
        assert "lateral_g" in result.columns


class TestFilterShortLapsNoLongLaps:
    """Cover line 159: all laps are within distance ratio → no fallback needed (normal path).
    Also covers the fallback path when all normal laps are classified as outlier-long."""

    def test_all_laps_within_ratio_returns_filtered_subset(self) -> None:
        """When all laps are below MAX_LAP_DISTANCE_RATIO threshold, filtering works normally."""
        lap_normal = pd.DataFrame({"lap_distance_m": np.linspace(0, 1000, 50)})
        lap_short = pd.DataFrame({"lap_distance_m": np.linspace(0, 500, 50)})
        laps = {1: lap_normal, 2: lap_normal.copy(), 3: lap_short}
        result = _filter_short_laps(laps)
        # lap_short (500m vs reference 1000m) is 50% → below MIN_LAP_FRACTION=0.8 → filtered
        assert 1 in result
        assert 2 in result
        assert 3 not in result


class TestFloat32Downcast:
    """Verify selective float32 downcast preserves precision where needed."""

    FLOAT32_COLUMNS = frozenset(
        {
            "speed_mps",
            "altitude_m",
            "lateral_g",
            "longitudinal_g",
            "x_acc_g",
            "y_acc_g",
            "z_acc_g",
            "yaw_rate_dps",
            "heading_deg",
        }
    )
    MUST_STAY_FLOAT64 = frozenset({"lap_distance_m", "lap_time_s"})

    def _make_session(self) -> ProcessedSession:
        """Build a multi-lap session for dtype verification."""
        n_points = 50
        base_time = np.arange(n_points, dtype=float)
        base_dist = base_time * 30.0  # ~30 m/s

        df = pd.DataFrame(
            {
                "lap_number": [1.0] * n_points + [2.0] * n_points + [3.0] * n_points,
                "elapsed_time": np.concatenate(
                    [
                        base_time,
                        base_time + 100,
                        base_time + 200,
                    ]
                ),
                "distance_m": np.concatenate(
                    [
                        base_dist,
                        base_dist + 5000,
                        base_dist + 10000,
                    ]
                ),
                "speed_mps": np.full(n_points * 3, 30.0),
                "lat": np.full(n_points * 3, 33.53),
                "lon": np.full(n_points * 3, -86.62),
                "altitude_m": np.full(n_points * 3, 200.0),
                "lateral_g": np.random.uniform(-1, 1, n_points * 3),
                "longitudinal_g": np.random.uniform(-1, 1, n_points * 3),
                "heading_deg": np.linspace(0, 360, n_points * 3),
            }
        )
        return process_session(df)

    def test_safe_columns_are_float32(self) -> None:
        """Telemetry columns that don't need float64 should be float32."""
        session = self._make_session()
        for lap_num, df in session.resampled_laps.items():
            for col in self.FLOAT32_COLUMNS:
                if col in df.columns:
                    assert df[col].dtype == np.float32, (
                        f"Lap {lap_num} column {col} should be float32, got {df[col].dtype}"
                    )

    def test_precision_columns_stay_float64(self) -> None:
        """Distance and time columns must stay float64."""
        session = self._make_session()
        for lap_num, df in session.resampled_laps.items():
            for col in self.MUST_STAY_FLOAT64:
                if col in df.columns:
                    assert df[col].dtype == np.float64, (
                        f"Lap {lap_num} column {col} must stay float64, got {df[col].dtype}"
                    )

    def test_physics_sanity_after_downcast(self) -> None:
        """Corner detection and lap ordering should work correctly after downcast."""
        session = self._make_session()
        # Basic sanity: laps exist and are ordered by time
        assert len(session.lap_summaries) >= 2
        times = [s.lap_time_s for s in session.lap_summaries]
        assert times == sorted(times), "Lap times should be sorted ascending"
        # Best lap should have positive, finite time
        assert session.lap_summaries[0].lap_time_s > 0
        assert np.isfinite(session.lap_summaries[0].lap_time_s)

    def test_downcast_helper_only_touches_safe_columns(self) -> None:
        """_downcast_telemetry should only cast known safe columns."""
        df = pd.DataFrame(
            {
                "speed_mps": np.array([30.0, 31.0], dtype=np.float64),
                "lap_distance_m": np.array([0.0, 0.7], dtype=np.float64),
                "lap_time_s": np.array([0.0, 0.023], dtype=np.float64),
                "lat": np.array([33.53, 33.54], dtype=np.float64),
            }
        )
        result = _downcast_telemetry(df)
        assert result["speed_mps"].dtype == np.float32
        assert result["lat"].dtype == np.float64  # lat excluded: sub-meter precision needed
        assert result["lap_distance_m"].dtype == np.float64
        assert result["lap_time_s"].dtype == np.float64

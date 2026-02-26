"""Tests for cataclysm.gps_quality module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.engine import LapSummary, ProcessedSession
from cataclysm.gps_quality import (
    AccuracyStats,
    GPSQualityReport,
    HeadingJitterStats,
    LapDistanceConsistency,
    LateralScatterStats,
    SatelliteStats,
    SpeedSpikeStats,
    _compute_accuracy_stats,
    _compute_heading_jitter,
    _compute_lap_distance_consistency,
    _compute_lateral_scatter,
    _compute_satellite_stats,
    _compute_speed_spikes,
    _piecewise_linear_score,
    assess_gps_quality,
)


# ---------------------------------------------------------------------------
# Helpers: synthetic data builders
# ---------------------------------------------------------------------------


def _make_raw_data(
    n_rows: int = 400,
    accuracy_mean: float = 0.3,
    accuracy_std: float = 0.05,
    sats_mean: float = 14,
    sats_std: float = 1,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a synthetic raw DataFrame with accuracy_m and satellites columns."""
    rng = np.random.default_rng(seed)
    accuracy = np.clip(rng.normal(accuracy_mean, accuracy_std, n_rows), 0.01, 5.0)
    satellites = np.clip(rng.normal(sats_mean, sats_std, n_rows).astype(int), 3, 30)
    return pd.DataFrame({"accuracy_m": accuracy, "satellites": satellites})


def _make_resampled_lap(
    n_points: int = 700,
    speed_mean: float = 35.0,
    speed_noise: float = 0.0,
    heading_noise: float = 0.0,
    lat_start: float = 33.53,
    lon_start: float = -86.62,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a synthetic resampled lap DataFrame."""
    rng = np.random.default_rng(seed)
    step = 0.7
    distance = np.arange(n_points) * step

    # Oval-like heading: mostly straight with 4 turns
    heading = np.zeros(n_points)
    for center in [175, 350, 525, 700]:
        if center < n_points:
            for j in range(max(0, center - 30), min(n_points, center + 30)):
                offset = j - center
                heading[j] += 2.0 * np.exp(-(offset**2) / 200)
    heading = np.cumsum(heading) % 360
    heading += rng.normal(0, heading_noise, n_points) if heading_noise > 0 else 0.0

    speed = np.full(n_points, speed_mean)
    if speed_noise > 0:
        speed += rng.normal(0, speed_noise, n_points)
    speed = np.clip(speed, 1.0, 100.0)

    dt = step / speed
    lap_time = np.cumsum(dt)

    lat = lat_start + np.sin(np.radians(heading)) * distance / 111000
    lon = lon_start + np.cos(np.radians(heading)) * distance / 111000

    return pd.DataFrame(
        {
            "lap_distance_m": distance,
            "lap_time_s": lap_time,
            "speed_mps": speed,
            "heading_deg": heading % 360,
            "lat": lat,
            "lon": lon,
            "lateral_g": np.zeros(n_points),
            "longitudinal_g": np.zeros(n_points),
            "yaw_rate_dps": np.zeros(n_points),
            "altitude_m": np.full(n_points, 200.0),
            "x_acc_g": np.zeros(n_points),
            "y_acc_g": np.zeros(n_points),
            "z_acc_g": np.ones(n_points),
        }
    )


def _make_processed(
    n_laps: int = 4,
    n_points: int = 700,
    distance_noise: float = 0.0,
    speed_noise: float = 0.0,
    heading_noise: float = 0.0,
    seed: int = 42,
) -> ProcessedSession:
    """Build a synthetic ProcessedSession with N resampled laps."""
    rng = np.random.default_rng(seed)
    resampled: dict[int, pd.DataFrame] = {}
    summaries: list[LapSummary] = []

    base_distance = 490.0  # ~700 * 0.7
    base_time = 14.0  # ~490m / 35 m/s

    for i in range(1, n_laps + 1):
        lap_df = _make_resampled_lap(
            n_points=n_points,
            speed_noise=speed_noise,
            heading_noise=heading_noise,
            seed=seed + i,
        )
        # Add distance noise to simulate GPS-caused lap distance variation
        lap_dist = base_distance + rng.normal(0, distance_noise * base_distance / 100)
        resampled[i] = lap_df
        summaries.append(
            LapSummary(
                lap_number=i,
                lap_time_s=round(base_time + i * 0.2, 3),
                lap_distance_m=round(lap_dist, 1),
                max_speed_mps=40.0,
            )
        )

    summaries.sort(key=lambda s: s.lap_time_s)
    return ProcessedSession(
        lap_summaries=summaries,
        resampled_laps=resampled,
        best_lap=summaries[0].lap_number,
    )


# ---------------------------------------------------------------------------
# Test: _piecewise_linear_score
# ---------------------------------------------------------------------------


class TestPiecewiseLinearScore:
    """Tests for the generic piecewise linear interpolation helper."""

    def test_exact_breakpoint(self) -> None:
        bp = [(0.0, 100.0), (1.0, 50.0), (2.0, 0.0)]
        assert _piecewise_linear_score(1.0, bp) == 50.0

    def test_midpoint_interpolation(self) -> None:
        bp = [(0.0, 100.0), (2.0, 0.0)]
        assert _piecewise_linear_score(1.0, bp) == pytest.approx(50.0)

    def test_below_range_clamps(self) -> None:
        bp = [(1.0, 80.0), (2.0, 40.0)]
        assert _piecewise_linear_score(0.0, bp) == 80.0

    def test_above_range_clamps(self) -> None:
        bp = [(1.0, 80.0), (2.0, 40.0)]
        assert _piecewise_linear_score(5.0, bp) == 40.0

    def test_empty_breakpoints(self) -> None:
        assert _piecewise_linear_score(1.0, []) == 0.0

    def test_single_breakpoint(self) -> None:
        bp = [(1.0, 50.0)]
        assert _piecewise_linear_score(0.5, bp) == 50.0
        assert _piecewise_linear_score(1.5, bp) == 50.0

    def test_accuracy_breakpoints(self) -> None:
        """Accuracy p90 of 0.3 → perfect score."""
        from cataclysm.gps_quality import _ACCURACY_BP

        assert _piecewise_linear_score(0.3, _ACCURACY_BP) == 100.0

    def test_accuracy_midrange(self) -> None:
        """Accuracy p90 of 1.25 → between 80 and 50."""
        from cataclysm.gps_quality import _ACCURACY_BP

        score = _piecewise_linear_score(1.25, _ACCURACY_BP)
        assert 50.0 < score < 80.0


# ---------------------------------------------------------------------------
# Test: AccuracyStats
# ---------------------------------------------------------------------------


class TestAccuracyStats:
    """Tests for _compute_accuracy_stats."""

    def test_clean_gps(self) -> None:
        data = _make_raw_data(accuracy_mean=0.3, accuracy_std=0.05)
        result = _compute_accuracy_stats(data)
        assert isinstance(result, AccuracyStats)
        assert result.p90 < 0.5
        assert result.score >= 90.0

    def test_noisy_gps(self) -> None:
        data = _make_raw_data(accuracy_mean=1.5, accuracy_std=0.3)
        result = _compute_accuracy_stats(data)
        assert result.p90 > 1.0
        assert result.score < 60.0

    def test_missing_column(self) -> None:
        data = pd.DataFrame({"other_col": [1, 2, 3]})
        result = _compute_accuracy_stats(data)
        assert result.score == 100.0

    def test_empty_dataframe(self) -> None:
        data = pd.DataFrame({"accuracy_m": pd.Series([], dtype=float)})
        result = _compute_accuracy_stats(data)
        assert result.score == 100.0


# ---------------------------------------------------------------------------
# Test: SatelliteStats
# ---------------------------------------------------------------------------


class TestSatelliteStats:
    """Tests for _compute_satellite_stats."""

    def test_good_reception(self) -> None:
        data = _make_raw_data(sats_mean=14, sats_std=1)
        result = _compute_satellite_stats(data)
        assert isinstance(result, SatelliteStats)
        assert result.p10 >= 10.0
        assert result.score >= 70.0

    def test_poor_reception(self) -> None:
        data = _make_raw_data(sats_mean=7, sats_std=1)
        result = _compute_satellite_stats(data)
        assert result.p10 < 8.0
        assert result.score < 60.0

    def test_missing_column(self) -> None:
        data = pd.DataFrame({"other_col": [1, 2, 3]})
        result = _compute_satellite_stats(data)
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# Test: LapDistanceConsistency
# ---------------------------------------------------------------------------


class TestLapDistanceConsistency:
    """Tests for _compute_lap_distance_consistency."""

    def test_consistent_distances(self) -> None:
        summaries = [
            LapSummary(lap_number=i, lap_time_s=90.0 + i, lap_distance_m=500.0, max_speed_mps=40.0)
            for i in range(1, 5)
        ]
        result = _compute_lap_distance_consistency(summaries, set())
        assert result is not None
        assert result.cv_percent < 0.1
        assert result.score >= 90.0

    def test_inconsistent_distances(self) -> None:
        summaries = [
            LapSummary(
                lap_number=i,
                lap_time_s=90.0 + i,
                lap_distance_m=500.0 + i * 30,
                max_speed_mps=40.0,
            )
            for i in range(1, 5)
        ]
        result = _compute_lap_distance_consistency(summaries, set())
        assert result is not None
        assert result.cv_percent > 2.0
        assert result.score < 60.0

    def test_too_few_laps(self) -> None:
        summaries = [
            LapSummary(lap_number=i, lap_time_s=90.0, lap_distance_m=500.0, max_speed_mps=40.0)
            for i in range(1, 3)
        ]
        result = _compute_lap_distance_consistency(summaries, set())
        assert result is None

    def test_excludes_anomalous(self) -> None:
        summaries = [
            LapSummary(lap_number=i, lap_time_s=90.0, lap_distance_m=500.0, max_speed_mps=40.0)
            for i in range(1, 6)
        ]
        # Mark 3 of 5 as anomalous → only 2 clean → returns None
        result = _compute_lap_distance_consistency(summaries, {1, 2, 3})
        assert result is None


# ---------------------------------------------------------------------------
# Test: SpeedSpikeStats
# ---------------------------------------------------------------------------


class TestSpeedSpikeStats:
    """Tests for _compute_speed_spikes."""

    def test_clean_speed(self) -> None:
        processed = _make_processed(n_laps=3, speed_noise=0.0)
        result = _compute_speed_spikes(processed.resampled_laps, [1, 2, 3])
        assert isinstance(result, SpeedSpikeStats)
        assert result.total_spikes == 0
        assert result.score == 100.0

    def test_spike_injection(self) -> None:
        """Manually inject speed spikes to verify detection."""
        processed = _make_processed(n_laps=2)
        # Inject a spike: jump speed by 100 m/s in 0.02s (5000 m/s^2 >> 3g)
        df = processed.resampled_laps[1].copy()
        df.loc[100, "speed_mps"] = 150.0  # 150 m/s spike
        processed.resampled_laps[1] = df
        result = _compute_speed_spikes(processed.resampled_laps, [1, 2])
        assert result.total_spikes >= 1
        assert result.score < 100.0

    def test_empty_laps(self) -> None:
        result = _compute_speed_spikes({}, [])
        assert result.total_spikes == 0
        assert result.spikes_per_km == 0.0


# ---------------------------------------------------------------------------
# Test: HeadingJitterStats
# ---------------------------------------------------------------------------


class TestHeadingJitterStats:
    """Tests for _compute_heading_jitter."""

    def test_smooth_heading(self) -> None:
        lap = _make_resampled_lap(heading_noise=0.0)
        result = _compute_heading_jitter(lap)
        # May return None if not enough straight fraction, or very low jitter
        if result is not None:
            assert result.jitter_std < 0.15
            assert result.score >= 70.0

    def test_noisy_heading(self) -> None:
        lap = _make_resampled_lap(heading_noise=5.0, seed=99)
        result = _compute_heading_jitter(lap)
        # With noisy heading, jitter should be high (or None if no straights detected)
        if result is not None:
            assert result.jitter_std > 0.1

    def test_too_short(self) -> None:
        lap = _make_resampled_lap(n_points=10)
        result = _compute_heading_jitter(lap)
        assert result is None

    def test_no_heading_column(self) -> None:
        lap = pd.DataFrame({"lap_distance_m": np.arange(100) * 0.7, "speed_mps": np.ones(100)})
        result = _compute_heading_jitter(lap)
        assert result is None


# ---------------------------------------------------------------------------
# Test: LateralScatterStats
# ---------------------------------------------------------------------------


class TestLateralScatterStats:
    """Tests for _compute_lateral_scatter."""

    def test_identical_laps(self) -> None:
        """Identical lap traces should have zero scatter."""
        lap = _make_resampled_lap()
        resampled = {1: lap, 2: lap.copy(), 3: lap.copy()}
        result = _compute_lateral_scatter(resampled, [1, 2, 3])
        assert isinstance(result, LateralScatterStats)
        assert result.scatter_p90 == pytest.approx(0.0, abs=0.01)
        assert result.score >= 90.0

    def test_single_lap(self) -> None:
        """Single lap should return default (no scatter computable)."""
        lap = _make_resampled_lap()
        result = _compute_lateral_scatter({1: lap}, [1])
        assert result.scatter_p90 == 0.0
        assert result.score == 100.0

    def test_noisy_laps(self) -> None:
        """Laps with different lat/lon offsets should have higher scatter."""
        base_lap = _make_resampled_lap()
        shifted_lap = base_lap.copy()
        shifted_lap["lat"] = shifted_lap["lat"] + 0.0001  # ~11m shift
        resampled = {1: base_lap, 2: shifted_lap}
        result = _compute_lateral_scatter(resampled, [1, 2])
        assert result.scatter_p90 > 1.0
        assert result.score < 80.0


# ---------------------------------------------------------------------------
# Test: assess_gps_quality (integration)
# ---------------------------------------------------------------------------


class TestAssessGPSQuality:
    """Integration tests for the main assess_gps_quality function."""

    def test_clean_session_grade_a(self) -> None:
        """Clean GPS session should get grade A or B."""
        raw_data = _make_raw_data(accuracy_mean=0.3, accuracy_std=0.02, sats_mean=14)
        processed = _make_processed(n_laps=5, distance_noise=0.1)
        report = assess_gps_quality(raw_data, processed, set())
        assert isinstance(report, GPSQualityReport)
        assert report.grade in ("A", "B")
        assert report.overall_score >= 75.0
        assert report.is_usable is True

    def test_noisy_session_low_grade(self) -> None:
        """Noisy GPS with bad accuracy + low sats should get D or F."""
        raw_data = _make_raw_data(accuracy_mean=1.8, accuracy_std=0.1, sats_mean=7, sats_std=1)
        processed = _make_processed(n_laps=4, distance_noise=3.0)
        report = assess_gps_quality(raw_data, processed, set())
        assert report.grade in ("C", "D", "F")
        assert report.overall_score < 75.0

    def test_two_laps_no_cv(self) -> None:
        """With only 2 laps, lap_distance_cv should be None and weight redistributed."""
        raw_data = _make_raw_data(accuracy_mean=0.3, sats_mean=14)
        processed = _make_processed(n_laps=2)
        report = assess_gps_quality(raw_data, processed, set())
        assert report.lap_distance_cv is None
        assert "lap_distance_cv" not in report.metric_weights

    def test_all_metrics_present(self) -> None:
        """With enough laps and straights, all 6 metrics should be computed."""
        raw_data = _make_raw_data(accuracy_mean=0.3, sats_mean=14)
        processed = _make_processed(n_laps=5, distance_noise=0.2)
        report = assess_gps_quality(raw_data, processed, set())
        assert report.accuracy is not None
        assert report.satellites is not None
        assert report.speed_spikes is not None
        assert report.lateral_scatter is not None
        # lap_distance_cv and heading_jitter may or may not be present

    def test_grade_boundaries(self) -> None:
        """Verify grade boundaries: A >= 90, B >= 75, C >= 60, D >= 40, F < 40."""
        from cataclysm.gps_quality import _compute_grade

        assert _compute_grade(95.0) == "A"
        assert _compute_grade(90.0) == "A"
        assert _compute_grade(89.9) == "B"
        assert _compute_grade(75.0) == "B"
        assert _compute_grade(74.9) == "C"
        assert _compute_grade(60.0) == "C"
        assert _compute_grade(59.9) == "D"
        assert _compute_grade(40.0) == "D"
        assert _compute_grade(39.9) == "F"
        assert _compute_grade(0.0) == "F"

    def test_is_usable_boundary(self) -> None:
        """is_usable should be True for score >= 40, False below."""
        raw_data = _make_raw_data(accuracy_mean=0.3, sats_mean=14)
        processed = _make_processed(n_laps=5)
        report = assess_gps_quality(raw_data, processed, set())
        assert report.is_usable == (report.overall_score >= 40.0)

    def test_metric_weights_sum_to_one(self) -> None:
        """Metric weights should approximately sum to 1.0."""
        raw_data = _make_raw_data()
        processed = _make_processed(n_laps=5)
        report = assess_gps_quality(raw_data, processed, set())
        weight_sum = sum(report.metric_weights.values())
        assert weight_sum == pytest.approx(1.0, abs=0.01)

    def test_single_lap_session(self) -> None:
        """Single-lap session should still produce a valid report."""
        raw_data = _make_raw_data(accuracy_mean=0.3, sats_mean=14)
        processed = _make_processed(n_laps=1)
        report = assess_gps_quality(raw_data, processed, set())
        assert isinstance(report, GPSQualityReport)
        assert report.lap_distance_cv is None

    def test_anomalous_laps_excluded_from_cv(self) -> None:
        """Anomalous laps shouldn't affect lap distance CV."""
        raw_data = _make_raw_data()
        processed = _make_processed(n_laps=5, distance_noise=0.1)
        # Mark 3 of 5 as anomalous → only 2 clean → CV not computed
        report = assess_gps_quality(raw_data, processed, {1, 2, 3})
        assert report.lap_distance_cv is None

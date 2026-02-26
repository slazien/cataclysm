"""Tests for session consistency metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.consistency import (
    CornerConsistencyEntry,
    LapConsistency,
    SessionConsistency,
    TrackPositionConsistency,
    compute_corner_consistency,
    compute_lap_consistency,
    compute_session_consistency,
    compute_track_position_consistency,
)
from cataclysm.corners import Corner
from cataclysm.engine import LapSummary, ProcessedSession


def _make_summary(lap_number: int, lap_time_s: float) -> LapSummary:
    """Helper to build a LapSummary with sensible defaults."""
    return LapSummary(
        lap_number=lap_number,
        lap_time_s=lap_time_s,
        lap_distance_m=5000.0,
        max_speed_mps=60.0,
    )


def _make_corner(
    number: int,
    min_speed_mps: float = 20.0,
    brake_point_m: float | None = 80.0,
    throttle_commit_m: float | None = 170.0,
) -> Corner:
    """Helper to build a Corner with sensible defaults."""
    return Corner(
        number=number,
        entry_distance_m=100.0,
        exit_distance_m=200.0,
        apex_distance_m=150.0,
        min_speed_mps=min_speed_mps,
        brake_point_m=brake_point_m,
        peak_brake_g=-0.5,
        throttle_commit_m=throttle_commit_m,
        apex_type="mid",
    )


class TestLapConsistencyBasic:
    """Basic lap consistency tests using the processed_session fixture."""

    def test_lap_consistency_basic(self, processed_session: ProcessedSession) -> None:
        summaries = processed_session.lap_summaries
        result = compute_lap_consistency(summaries, anomalous_laps=set())

        assert isinstance(result, LapConsistency)
        assert 0.0 <= result.consistency_score <= 100.0
        assert 0.0 <= result.choppiness_score <= 100.0
        assert 0.0 <= result.spread_score <= 100.0
        assert 0.0 <= result.jump_score <= 100.0
        assert len(result.lap_numbers) == len(summaries)
        assert len(result.consecutive_deltas_s) == len(result.lap_numbers) - 1


class TestLapConsistencyTemporalOrdering:
    """The key test: choppy lap sequences must score lower than smooth ones."""

    def test_lap_consistency_temporal_ordering(self) -> None:
        # Choppy: big jump then back then same → 107, 112, 107, 107
        choppy_summaries = [
            _make_summary(1, 107.0),
            _make_summary(2, 112.0),
            _make_summary(3, 107.0),
            _make_summary(4, 107.0),
        ]
        # Smooth: three steady then one outlier → 107, 107, 107, 112
        smooth_summaries = [
            _make_summary(1, 107.0),
            _make_summary(2, 107.0),
            _make_summary(3, 107.0),
            _make_summary(4, 112.0),
        ]

        choppy = compute_lap_consistency(choppy_summaries, anomalous_laps=set())
        smooth = compute_lap_consistency(smooth_summaries, anomalous_laps=set())

        # Both have the same std dev and spread
        assert choppy.std_dev_s == pytest.approx(smooth.std_dev_s, abs=1e-9)
        assert choppy.spread_s == pytest.approx(smooth.spread_s, abs=1e-9)

        # But choppy has higher mean consecutive delta
        assert choppy.mean_abs_consecutive_delta_s > smooth.mean_abs_consecutive_delta_s

        # And therefore choppy scores LOWER (worse) than smooth
        assert choppy.consistency_score < smooth.consistency_score

        # Sub-scores should also be valid 0-100 ranges
        for result in (choppy, smooth):
            assert 0.0 <= result.choppiness_score <= 100.0
            assert 0.0 <= result.spread_score <= 100.0
            assert 0.0 <= result.jump_score <= 100.0

        # Choppiness sub-score specifically should be lower for the choppy sequence
        assert choppy.choppiness_score < smooth.choppiness_score
        # Spread sub-scores should be equal (same spread in both)
        assert choppy.spread_score == pytest.approx(smooth.spread_score, abs=1e-9)


class TestLapConsistencyEdgeCases:
    """Edge cases: single lap, anomalous filtering."""

    def test_lap_consistency_single_lap(self) -> None:
        summaries = [_make_summary(1, 107.0)]
        result = compute_lap_consistency(summaries, anomalous_laps=set())

        assert result.consistency_score == 100.0
        assert result.choppiness_score == 100.0
        assert result.spread_score == 100.0
        assert result.jump_score == 100.0
        assert result.std_dev_s == 0.0
        assert result.spread_s == 0.0
        assert result.mean_abs_consecutive_delta_s == 0.0
        assert result.max_consecutive_delta_s == 0.0
        assert result.consecutive_deltas_s == []

    def test_lap_consistency_excludes_anomalous(self) -> None:
        summaries = [
            _make_summary(1, 107.0),
            _make_summary(2, 108.0),
            _make_summary(3, 150.0),  # anomalous
            _make_summary(4, 107.5),
        ]
        anomalous = {3}
        result = compute_lap_consistency(summaries, anomalous_laps=anomalous)

        assert 3 not in result.lap_numbers
        assert len(result.lap_numbers) == 3
        assert all(n in [1, 2, 4] for n in result.lap_numbers)


class TestCornerConsistency:
    """Corner consistency metric tests."""

    def test_corner_consistency_basic(self) -> None:
        all_lap_corners: dict[int, list[Corner]] = {
            1: [_make_corner(1, 20.0, 80.0, 170.0), _make_corner(2, 25.0, 90.0, 180.0)],
            2: [_make_corner(1, 21.0, 82.0, 172.0), _make_corner(2, 24.0, 88.0, 178.0)],
            3: [_make_corner(1, 19.5, 79.0, 168.0), _make_corner(2, 26.0, 91.0, 182.0)],
        }
        result = compute_corner_consistency(all_lap_corners, anomalous_laps=set())

        assert len(result) == 2
        for entry in result:
            assert isinstance(entry, CornerConsistencyEntry)
            assert 0.0 <= entry.consistency_score <= 100.0
            assert entry.min_speed_std_mph >= 0.0
            assert entry.min_speed_range_mph >= 0.0

    def test_corner_consistency_none_safe(self) -> None:
        all_lap_corners: dict[int, list[Corner]] = {
            1: [_make_corner(1, 20.0, brake_point_m=None, throttle_commit_m=None)],
            2: [_make_corner(1, 21.0, brake_point_m=None, throttle_commit_m=None)],
        }
        result = compute_corner_consistency(all_lap_corners, anomalous_laps=set())

        assert len(result) == 1
        entry = result[0]
        assert entry.brake_point_std_m is None
        assert entry.throttle_commit_std_m is None
        assert 0.0 <= entry.consistency_score <= 100.0


class TestTrackPositionConsistency:
    """Track-position consistency tests."""

    def test_track_position_consistency_basic(self, sample_resampled_lap: pd.DataFrame) -> None:
        rng = np.random.default_rng(99)
        lap_a = sample_resampled_lap.copy()
        lap_b = sample_resampled_lap.copy()
        lap_b["speed_mps"] = lap_b["speed_mps"] + rng.normal(0, 0.5, len(lap_b))

        resampled_laps = {1: lap_a, 2: lap_b}
        result = compute_track_position_consistency(resampled_laps, ref_lap=1, anomalous_laps=set())

        assert isinstance(result, TrackPositionConsistency)
        assert result.n_laps == 2
        assert len(result.distance_m) == len(lap_a)
        assert len(result.speed_std_mph) == len(lap_a)
        assert len(result.speed_mean_mph) == len(lap_a)
        assert len(result.speed_median_mph) == len(lap_a)
        assert len(result.lat) == len(lap_a)
        assert len(result.lon) == len(lap_a)


class TestSessionConsistencyIntegration:
    """End-to-end integration test using the processed_session fixture."""

    def test_session_consistency_integration(self, processed_session: ProcessedSession) -> None:
        summaries = processed_session.lap_summaries
        resampled_laps = processed_session.resampled_laps
        best_lap = processed_session.best_lap

        # Detect corners from the best lap to build all_lap_corners
        from cataclysm.corners import detect_corners, extract_corner_kpis_for_lap

        ref_corners = detect_corners(resampled_laps[best_lap])
        all_lap_corners: dict[int, list[Corner]] = {}
        for lap_num, lap_df in resampled_laps.items():
            if lap_num == best_lap:
                all_lap_corners[lap_num] = ref_corners
            else:
                all_lap_corners[lap_num] = extract_corner_kpis_for_lap(lap_df, ref_corners)

        result = compute_session_consistency(
            summaries=summaries,
            all_lap_corners=all_lap_corners,
            resampled_laps=resampled_laps,
            ref_lap=best_lap,
            anomalous_laps=set(),
        )

        assert isinstance(result, SessionConsistency)
        assert isinstance(result.lap_consistency, LapConsistency)
        assert isinstance(result.corner_consistency, list)
        assert isinstance(result.track_position, TrackPositionConsistency)
        assert 0.0 <= result.lap_consistency.consistency_score <= 100.0
        assert result.track_position.n_laps == len(resampled_laps)

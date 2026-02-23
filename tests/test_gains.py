"""Tests for cataclysm.gains — deterministic time-gain estimation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.corners import Corner
from cataclysm.engine import LapSummary
from cataclysm.gains import (
    CompositeGainResult,
    ConsistencyGainResult,
    TheoreticalBestResult,
    build_segments,
    compute_composite_gain,
    compute_consistency_gain,
    compute_segment_times,
    compute_theoretical_best,
    estimate_gains,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lap(n_points: int, speed_mps: float, step: float = 0.7) -> pd.DataFrame:
    """Create a synthetic resampled lap at constant speed."""
    dist = np.arange(n_points) * step
    time = dist / speed_mps
    return pd.DataFrame(
        {
            "lap_distance_m": dist,
            "lap_time_s": time,
            "speed_mps": np.full(n_points, speed_mps),
        }
    )


def _make_corner(
    number: int,
    entry: float,
    exit: float,
    apex: float | None = None,
) -> Corner:
    """Create a minimal Corner for testing."""
    if apex is None:
        apex = (entry + exit) / 2
    return Corner(
        number=number,
        entry_distance_m=entry,
        exit_distance_m=exit,
        apex_distance_m=apex,
        min_speed_mps=20.0,
        brake_point_m=None,
        peak_brake_g=None,
        throttle_commit_m=None,
        apex_type="mid",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def two_laps() -> dict[int, pd.DataFrame]:
    """Two laps: lap 1 at 30 m/s, lap 2 at 28 m/s (1000 pts, 0.7m step)."""
    return {
        1: _make_lap(1000, 30.0),
        2: _make_lap(1000, 28.0),
    }


@pytest.fixture
def three_laps() -> dict[int, pd.DataFrame]:
    """Three laps at 30, 28, 26 m/s."""
    return {
        1: _make_lap(1000, 30.0),
        2: _make_lap(1000, 28.0),
        3: _make_lap(1000, 26.0),
    }


@pytest.fixture
def identical_laps() -> dict[int, pd.DataFrame]:
    """Two identical laps at 30 m/s."""
    return {
        1: _make_lap(1000, 30.0),
        2: _make_lap(1000, 30.0),
    }


@pytest.fixture
def two_corners() -> list[Corner]:
    """Two corners on a ~700m track."""
    return [
        _make_corner(1, entry=100.0, exit=200.0),
        _make_corner(2, entry=400.0, exit=500.0),
    ]


@pytest.fixture
def summaries_two() -> list[LapSummary]:
    """Summaries matching two_laps fixture."""
    return [
        LapSummary(lap_number=1, lap_time_s=23.31, lap_distance_m=699.3, max_speed_mps=30.0),
        LapSummary(lap_number=2, lap_time_s=24.975, lap_distance_m=699.3, max_speed_mps=28.0),
    ]


@pytest.fixture
def summaries_three() -> list[LapSummary]:
    """Summaries matching three_laps fixture."""
    return [
        LapSummary(lap_number=1, lap_time_s=23.31, lap_distance_m=699.3, max_speed_mps=30.0),
        LapSummary(lap_number=2, lap_time_s=24.975, lap_distance_m=699.3, max_speed_mps=28.0),
        LapSummary(lap_number=3, lap_time_s=26.896, lap_distance_m=699.3, max_speed_mps=26.0),
    ]


@pytest.fixture
def summaries_identical() -> list[LapSummary]:
    """Summaries matching identical_laps fixture."""
    return [
        LapSummary(lap_number=1, lap_time_s=23.31, lap_distance_m=699.3, max_speed_mps=30.0),
        LapSummary(lap_number=2, lap_time_s=23.31, lap_distance_m=699.3, max_speed_mps=30.0),
    ]


# ===========================================================================
# TestBuildSegments
# ===========================================================================


class TestBuildSegments:
    """Tests for build_segments."""

    def test_two_corners_five_segments(self, two_corners: list[Corner]) -> None:
        """2 corners produce 5 segments: S0-1, T1, S1-2, T2, S2-fin."""
        segs = build_segments(two_corners, 700.0)
        assert len(segs) == 5
        names = [s.name for s in segs]
        assert names == ["S0-1", "T1", "S1-2", "T2", "S2-fin"]

    def test_no_corners_single_straight(self) -> None:
        """No corners → one straight segment covering the full track."""
        segs = build_segments([], 500.0)
        assert len(segs) == 1
        assert segs[0].name == "S0-fin"
        assert segs[0].entry_distance_m == 0.0
        assert segs[0].exit_distance_m == 500.0
        assert segs[0].is_corner is False

    def test_segments_cover_full_track(self, two_corners: list[Corner]) -> None:
        """Segments must span from 0 to track_length without gaps."""
        segs = build_segments(two_corners, 700.0)
        assert segs[0].entry_distance_m == 0.0
        assert segs[-1].exit_distance_m == 700.0
        # Check no gaps between consecutive segments
        for i in range(len(segs) - 1):
            assert abs(segs[i].exit_distance_m - segs[i + 1].entry_distance_m) < 1e-6

    def test_adjacent_corners_no_zero_straight(self) -> None:
        """Adjacent corners (exit == entry) should not produce a zero-length straight."""
        corners = [
            _make_corner(1, entry=100.0, exit=200.0),
            _make_corner(2, entry=200.0, exit=300.0),
        ]
        segs = build_segments(corners, 500.0)
        for seg in segs:
            assert seg.exit_distance_m - seg.entry_distance_m > -1e-6
        # No zero-length straights
        straight_lengths = [s.exit_distance_m - s.entry_distance_m for s in segs if not s.is_corner]
        for length in straight_lengths:
            assert length > 1e-6

    def test_corner_segments_flagged(self, two_corners: list[Corner]) -> None:
        """Corner segments have is_corner=True, straights have is_corner=False."""
        segs = build_segments(two_corners, 700.0)
        for seg in segs:
            if seg.name.startswith("T"):
                assert seg.is_corner is True
            else:
                assert seg.is_corner is False


# ===========================================================================
# TestComputeSegmentTimes
# ===========================================================================


class TestComputeSegmentTimes:
    """Tests for compute_segment_times."""

    def test_constant_speed_proportional_times(
        self, two_laps: dict[int, pd.DataFrame], two_corners: list[Corner]
    ) -> None:
        """At constant speed, segment time = segment_length / speed."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(two_laps, segs, [1, 2])
        # T1 spans 100m-200m = 100m. Lap 1 at 30 m/s → ~3.33s
        t1_times = seg_times["T1"]
        assert abs(t1_times[1] - 100.0 / 30.0) < 0.1
        assert abs(t1_times[2] - 100.0 / 28.0) < 0.1

    def test_different_speeds_verified(
        self, two_laps: dict[int, pd.DataFrame], two_corners: list[Corner]
    ) -> None:
        """Slower lap should have larger segment times."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(two_laps, segs, [1, 2])
        for seg_name in seg_times:
            assert seg_times[seg_name][2] > seg_times[seg_name][1]

    def test_returns_correct_keys(
        self, two_laps: dict[int, pd.DataFrame], two_corners: list[Corner]
    ) -> None:
        """Returned dict has one key per segment."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(two_laps, segs, [1, 2])
        assert set(seg_times.keys()) == {s.name for s in segs}

    def test_only_clean_laps_included(
        self, two_laps: dict[int, pd.DataFrame], two_corners: list[Corner]
    ) -> None:
        """Only requested clean laps appear in segment times."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(two_laps, segs, [1])
        for seg_name in seg_times:
            assert 1 in seg_times[seg_name]
            assert 2 not in seg_times[seg_name]


# ===========================================================================
# TestConsistencyGain
# ===========================================================================


class TestConsistencyGain:
    """Tests for compute_consistency_gain (Layer 1)."""

    def test_identical_laps_zero_gain(
        self,
        identical_laps: dict[int, pd.DataFrame],
        summaries_identical: list[LapSummary],
        two_corners: list[Corner],
    ) -> None:
        """Identical laps should yield zero consistency gain."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(identical_laps, segs, [1, 2])
        result = compute_consistency_gain(seg_times, segs, summaries_identical, [1, 2])
        assert abs(result.total_gain_s) < 1e-6

    def test_one_slow_lap_positive_gain(
        self,
        two_laps: dict[int, pd.DataFrame],
        summaries_two: list[LapSummary],
        two_corners: list[Corner],
    ) -> None:
        """One slower lap should produce positive consistency gain."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(two_laps, segs, [1, 2])
        result = compute_consistency_gain(seg_times, segs, summaries_two, [1, 2])
        assert result.total_gain_s > 0

    def test_total_gain_nonnegative(
        self,
        three_laps: dict[int, pd.DataFrame],
        summaries_three: list[LapSummary],
        two_corners: list[Corner],
    ) -> None:
        """Total consistency gain should always be >= 0."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(three_laps, segs, [1, 2, 3])
        result = compute_consistency_gain(seg_times, segs, summaries_three, [1, 2, 3])
        assert result.total_gain_s >= 0

    def test_has_avg_and_best_lap_time(
        self,
        two_laps: dict[int, pd.DataFrame],
        summaries_two: list[LapSummary],
        two_corners: list[Corner],
    ) -> None:
        """Result should contain avg and best lap times from summaries."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(two_laps, segs, [1, 2])
        result = compute_consistency_gain(seg_times, segs, summaries_two, [1, 2])
        assert result.best_lap_time_s == min(s.lap_time_s for s in summaries_two)
        expected_avg = float(np.mean([s.lap_time_s for s in summaries_two]))
        assert abs(result.avg_lap_time_s - expected_avg) < 0.01


# ===========================================================================
# TestCompositeGain
# ===========================================================================


class TestCompositeGain:
    """Tests for compute_composite_gain (Layer 2)."""

    def test_identical_laps_zero_gain(
        self,
        identical_laps: dict[int, pd.DataFrame],
        two_corners: list[Corner],
    ) -> None:
        """Identical laps → composite == best → 0 gain."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(identical_laps, segs, [1, 2])
        result = compute_composite_gain(seg_times, segs, 23.31)
        assert abs(result.gain_s) < 0.1

    def test_complementary_laps_picks_best(self) -> None:
        """When different laps are faster in different segments, composite picks best."""
        # Lap 1: faster in first half (35 m/s), slower in second (25 m/s)
        # Lap 2: slower in first half (25 m/s), faster in second (35 m/s)
        n = 500
        step = 0.7
        dist = np.arange(n) * step  # 0 to 349.3m
        mid = n // 2

        time1 = np.empty(n)
        time1[:mid] = dist[:mid] / 35.0
        time1[mid:] = time1[mid - 1] + (dist[mid:] - dist[mid - 1]) / 25.0

        time2 = np.empty(n)
        time2[:mid] = dist[:mid] / 25.0
        time2[mid:] = time2[mid - 1] + (dist[mid:] - dist[mid - 1]) / 35.0

        laps = {
            1: pd.DataFrame(
                {"lap_distance_m": dist, "lap_time_s": time1, "speed_mps": np.full(n, 30.0)}
            ),
            2: pd.DataFrame(
                {"lap_distance_m": dist, "lap_time_s": time2, "speed_mps": np.full(n, 30.0)}
            ),
        }
        # Single corner in the middle
        corners = [_make_corner(1, entry=150.0, exit=200.0)]
        track_len = float(dist[-1])
        segs = build_segments(corners, track_len)
        seg_times = compute_segment_times(laps, segs, [1, 2])

        best_lap_time = min(float(time1[-1]), float(time2[-1]))
        result = compute_composite_gain(seg_times, segs, best_lap_time)
        # Composite should be faster than the best single lap
        assert result.composite_time_s < best_lap_time or abs(result.gain_s) < 0.01
        assert result.gain_s >= 0

    def test_gain_nonnegative(
        self,
        two_laps: dict[int, pd.DataFrame],
        two_corners: list[Corner],
    ) -> None:
        """Composite gain is always clamped to >= 0."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(two_laps, segs, [1, 2])
        result = compute_composite_gain(seg_times, segs, 23.31)
        assert result.gain_s >= 0


# ===========================================================================
# TestTheoreticalBest
# ===========================================================================


class TestTheoreticalBest:
    """Tests for compute_theoretical_best (Layer 3)."""

    def test_identical_laps_zero_gain(self, identical_laps: dict[int, pd.DataFrame]) -> None:
        """Identical laps → theoretical == best → 0 gain."""
        best_time = float(identical_laps[1]["lap_time_s"].iloc[-1])
        result = compute_theoretical_best(identical_laps, [1, 2], best_time)
        assert abs(result.gain_s) < 0.01

    def test_theoretical_lte_composite(
        self, two_laps: dict[int, pd.DataFrame], two_corners: list[Corner]
    ) -> None:
        """Theoretical time should be <= composite time (or very close)."""
        segs = build_segments(two_corners, 699.3)
        seg_times = compute_segment_times(two_laps, segs, [1, 2])
        best_time = float(two_laps[1]["lap_time_s"].iloc[-1])
        composite = compute_composite_gain(seg_times, segs, best_time)
        theoretical = compute_theoretical_best(two_laps, [1, 2], best_time)
        assert theoretical.theoretical_time_s <= composite.composite_time_s + 0.01

    def test_gain_nonnegative(self, two_laps: dict[int, pd.DataFrame]) -> None:
        """Theoretical gain is clamped to >= 0."""
        best_time = float(two_laps[1]["lap_time_s"].iloc[-1])
        result = compute_theoretical_best(two_laps, [1, 2], best_time)
        assert result.gain_s >= 0

    def test_sector_count(self, two_laps: dict[int, pd.DataFrame]) -> None:
        """Number of sectors = track_length / sector_size (approx)."""
        best_time = float(two_laps[1]["lap_time_s"].iloc[-1])
        result = compute_theoretical_best(two_laps, [1, 2], best_time, sector_size_m=50.0)
        expected_sectors = int(699.3 / 50.0)
        assert abs(result.n_sectors - expected_sectors) <= 1


# ===========================================================================
# TestEstimateGains
# ===========================================================================


class TestEstimateGains:
    """Tests for estimate_gains orchestrator."""

    def test_returns_all_three_layers(
        self,
        two_laps: dict[int, pd.DataFrame],
        summaries_two: list[LapSummary],
        two_corners: list[Corner],
    ) -> None:
        """estimate_gains returns consistency, composite, and theoretical."""
        result = estimate_gains(two_laps, two_corners, summaries_two, [1, 2], 1)
        assert isinstance(result.consistency, ConsistencyGainResult)
        assert isinstance(result.composite, CompositeGainResult)
        assert isinstance(result.theoretical, TheoreticalBestResult)

    def test_invariant_theoretical_lte_composite_lte_best(
        self,
        two_laps: dict[int, pd.DataFrame],
        summaries_two: list[LapSummary],
        two_corners: list[Corner],
    ) -> None:
        """Invariant: theoretical_time <= composite_time <= best_lap_time."""
        result = estimate_gains(two_laps, two_corners, summaries_two, [1, 2], 1)
        assert result.theoretical.theoretical_time_s <= result.composite.composite_time_s + 0.01
        assert result.composite.composite_time_s <= result.consistency.best_lap_time_s + 0.01

    def test_fewer_than_two_laps_raises(
        self,
        two_laps: dict[int, pd.DataFrame],
        summaries_two: list[LapSummary],
        two_corners: list[Corner],
    ) -> None:
        """< 2 clean laps should raise ValueError."""
        with pytest.raises(ValueError, match="At least 2 clean laps"):
            estimate_gains(two_laps, two_corners, summaries_two, [1], 1)

    def test_clean_lap_numbers_sorted(
        self,
        three_laps: dict[int, pd.DataFrame],
        summaries_three: list[LapSummary],
        two_corners: list[Corner],
    ) -> None:
        """clean_lap_numbers in result should be sorted."""
        result = estimate_gains(three_laps, two_corners, summaries_three, [3, 1, 2], 1)
        assert result.clean_lap_numbers == [1, 2, 3]

    def test_best_lap_number_stored(
        self,
        two_laps: dict[int, pd.DataFrame],
        summaries_two: list[LapSummary],
        two_corners: list[Corner],
    ) -> None:
        """best_lap_number should match what was passed in."""
        result = estimate_gains(two_laps, two_corners, summaries_two, [1, 2], 1)
        assert result.best_lap_number == 1

    def test_no_corners(
        self,
        two_laps: dict[int, pd.DataFrame],
        summaries_two: list[LapSummary],
    ) -> None:
        """No corners → single straight segment, still produces valid result."""
        result = estimate_gains(two_laps, [], summaries_two, [1, 2], 1)
        assert len(result.consistency.segment_gains) == 1
        assert result.consistency.segment_gains[0].segment.name == "S0-fin"


# ===========================================================================
# TestIntegration
# ===========================================================================


class TestIntegration:
    """Integration test with more realistic data."""

    def test_full_pipeline_realistic(self) -> None:
        """Full pipeline with varying speed profiles and multiple corners."""
        n = 2000
        step = 0.7
        dist = np.arange(n) * step  # ~1400m track

        # Lap 1: variable speed with dips at corners
        speed1 = np.full(n, 35.0)
        speed1[200:350] = 22.0  # T1 zone
        speed1[600:750] = 18.0  # T2 zone
        speed1[1100:1300] = 25.0  # T3 zone
        time1 = np.cumsum(step / speed1)

        # Lap 2: slightly different profile
        speed2 = np.full(n, 33.0)
        speed2[200:350] = 24.0  # T1 faster
        speed2[600:750] = 17.0  # T2 slower
        speed2[1100:1300] = 23.0  # T3 slower
        time2 = np.cumsum(step / speed2)

        # Lap 3: another variation
        speed3 = np.full(n, 34.0)
        speed3[200:350] = 21.0  # T1 slowest
        speed3[600:750] = 20.0  # T2 middle
        speed3[1100:1300] = 27.0  # T3 fastest
        time3 = np.cumsum(step / speed3)

        laps = {
            1: pd.DataFrame({"lap_distance_m": dist, "lap_time_s": time1, "speed_mps": speed1}),
            2: pd.DataFrame({"lap_distance_m": dist, "lap_time_s": time2, "speed_mps": speed2}),
            3: pd.DataFrame({"lap_distance_m": dist, "lap_time_s": time3, "speed_mps": speed3}),
        }

        corners = [
            _make_corner(1, entry=140.0, exit=245.0),
            _make_corner(2, entry=420.0, exit=525.0),
            _make_corner(3, entry=770.0, exit=910.0),
        ]

        summaries = [
            LapSummary(
                lap_number=i,
                lap_time_s=float(laps[i]["lap_time_s"].iloc[-1]),
                lap_distance_m=float(dist[-1]),
                max_speed_mps=float(np.max(laps[i]["speed_mps"])),
            )
            for i in [1, 2, 3]
        ]

        best_lap = min(summaries, key=lambda s: s.lap_time_s).lap_number
        result = estimate_gains(laps, corners, summaries, [1, 2, 3], best_lap)

        # Sanity checks
        assert result.consistency.total_gain_s > 0
        assert result.composite.gain_s >= 0
        assert result.theoretical.gain_s >= 0
        # Invariant (tolerance accounts for interpolation artifacts with step-function speed)
        assert result.theoretical.theoretical_time_s <= result.composite.composite_time_s + 0.05
        assert result.composite.composite_time_s <= result.consistency.best_lap_time_s + 0.01
        # All segments covered
        segs = build_segments(corners, float(dist[-1]))
        assert len(result.consistency.segment_gains) == len(segs)

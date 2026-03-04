"""Tests for cataclysm.flow_lap — flow lap detection."""

from __future__ import annotations

from cataclysm.flow_lap import (
    FlowLapResult,
    _score_balance,
    _score_proximity,
    _score_smoothness,
    _score_timing,
    detect_flow_laps,
)


class TestScoreProximity:
    def test_at_pb(self) -> None:
        assert _score_proximity(90.0, 90.0) == 1.0

    def test_faster_than_pb(self) -> None:
        assert _score_proximity(89.0, 90.0) == 1.0

    def test_decays_with_gap(self) -> None:
        score = _score_proximity(91.8, 90.0)  # 2% off
        assert 0.0 < score < 0.7

    def test_large_gap_near_zero(self) -> None:
        score = _score_proximity(100.0, 90.0)  # ~11% off
        assert score < 0.05

    def test_zero_best_time(self) -> None:
        assert _score_proximity(90.0, 0.0) == 0.0

    def test_negative_best_time(self) -> None:
        assert _score_proximity(90.0, -1.0) == 0.0


class TestScoreBalance:
    def test_perfect_balance(self) -> None:
        lap = [50.0, 60.0, 45.0]
        best = [50.0, 60.0, 45.0]
        assert _score_balance(lap, best) == 1.0

    def test_unbalanced(self) -> None:
        lap = [50.0, 60.0, 30.0]  # One corner way off
        best = [50.0, 60.0, 45.0]
        score = _score_balance(lap, best)
        assert score < 0.8

    def test_empty_lists(self) -> None:
        assert _score_balance([], []) == 0.5

    def test_mismatched_lengths(self) -> None:
        assert _score_balance([50.0], [50.0, 60.0]) == 0.5

    def test_zero_best_speed(self) -> None:
        score = _score_balance([50.0, 0.0], [50.0, 0.0])
        assert 0.0 <= score <= 1.0


class TestScoreSmoothness:
    def test_uniform_speeds(self) -> None:
        score = _score_smoothness([50.0, 50.0, 50.0, 50.0])
        assert score == 1.0

    def test_variable_speeds(self) -> None:
        score = _score_smoothness([30.0, 70.0, 25.0, 65.0])
        assert score < 0.5

    def test_single_corner(self) -> None:
        assert _score_smoothness([50.0]) == 0.5

    def test_near_zero_mean(self) -> None:
        assert _score_smoothness([0.1, 0.2]) == 0.5


class TestScoreTiming:
    def test_mid_session_peak(self) -> None:
        score_mid = _score_timing(5, 10)
        score_start = _score_timing(0, 10)
        score_end = _score_timing(9, 10)
        assert score_mid > score_start
        assert score_mid > score_end

    def test_single_lap(self) -> None:
        assert _score_timing(0, 1) == 0.5


class TestDetectFlowLaps:
    def _make_data(
        self,
        n_laps: int = 8,
        *,
        fast_laps: list[int] | None = None,
    ) -> tuple[list[float], dict[int, list[float]], list[float]]:
        """Create synthetic session data.

        fast_laps: 1-based lap numbers that should be near PB.
        """
        if fast_laps is None:
            fast_laps = [4, 5]
        base_time = 90.0
        lap_times: list[float] = []
        per_lap: dict[int, list[float]] = {}
        best_speeds = [50.0, 60.0, 45.0, 55.0]

        for lap in range(1, n_laps + 1):
            if lap in fast_laps:
                lap_times.append(base_time + 0.1)
                per_lap[lap] = [s - 0.2 for s in best_speeds]
            else:
                lap_times.append(base_time + 2.0 + lap * 0.1)
                per_lap[lap] = [s - 3.0 for s in best_speeds]

        # PB lap
        lap_times[fast_laps[0] - 1] = base_time
        per_lap[fast_laps[0]] = best_speeds

        return lap_times, per_lap, best_speeds

    def test_returns_none_for_few_laps(self) -> None:
        lap_times = [90.0, 91.0, 92.0]
        per_lap = {1: [50.0], 2: [48.0], 3: [49.0]}
        best = [50.0]
        assert detect_flow_laps(lap_times, per_lap, best) is None

    def test_returns_none_for_empty_corner_data(self) -> None:
        lap_times = [90.0] * 8
        assert detect_flow_laps(lap_times, {}, [50.0]) is None

    def test_identifies_fast_laps_as_flow(self) -> None:
        lap_times, per_lap, best = self._make_data(fast_laps=[4, 5])
        result = detect_flow_laps(lap_times, per_lap, best)
        assert result is not None
        assert isinstance(result, FlowLapResult)
        # The PB lap (4) should score highest and be a flow lap.
        assert 4 in result.flow_laps

    def test_best_flow_lap_set(self) -> None:
        lap_times, per_lap, best = self._make_data(fast_laps=[4, 5])
        result = detect_flow_laps(lap_times, per_lap, best)
        assert result is not None
        assert result.best_flow_lap is not None
        assert result.best_flow_lap in result.flow_laps

    def test_scores_populated(self) -> None:
        lap_times, per_lap, best = self._make_data()
        result = detect_flow_laps(lap_times, per_lap, best)
        assert result is not None
        assert len(result.scores) == len(per_lap)
        for score in result.scores.values():
            assert 0.0 <= score <= 1.0

    def test_flow_laps_sorted_by_score(self) -> None:
        lap_times, per_lap, best = self._make_data()
        result = detect_flow_laps(lap_times, per_lap, best)
        assert result is not None
        if len(result.flow_laps) >= 2:
            scores = [result.scores[lap] for lap in result.flow_laps]
            assert scores == sorted(scores, reverse=True)

    def test_high_threshold_reduces_flow_laps(self) -> None:
        lap_times, per_lap, best = self._make_data()
        result_low = detect_flow_laps(lap_times, per_lap, best, threshold=0.3)
        result_high = detect_flow_laps(lap_times, per_lap, best, threshold=0.9)
        assert result_low is not None and result_high is not None
        assert len(result_high.flow_laps) <= len(result_low.flow_laps)

    def test_all_identical_laps(self) -> None:
        n = 8
        lap_times = [90.0] * n
        per_lap = {i: [50.0, 60.0, 45.0] for i in range(1, n + 1)}
        best = [50.0, 60.0, 45.0]
        result = detect_flow_laps(lap_times, per_lap, best)
        assert result is not None
        # All laps identical → all should score similarly high
        scores = list(result.scores.values())
        assert max(scores) - min(scores) < 0.15

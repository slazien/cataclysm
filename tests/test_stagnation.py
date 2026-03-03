"""Tests for cataclysm.stagnation."""

from __future__ import annotations

import pytest

from cataclysm.stagnation import (
    StagnantCorner,
    StagnationAnalysis,
    _compute_improvement_rate,
    _find_stagnant_corners,
    build_stagnation_context,
    detect_stagnation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(
    best_lap_time_s: float,
    corner_times: dict[int, list[float]] | None = None,
) -> dict[str, object]:
    """Build a minimal session summary dict for testing."""
    result: dict[str, object] = {"best_lap_time_s": best_lap_time_s}
    if corner_times is not None:
        result["corner_times"] = corner_times
    return result


# ---------------------------------------------------------------------------
# TestComputeImprovementRate
# ---------------------------------------------------------------------------


class TestComputeImprovementRate:
    def test_empty_list(self) -> None:
        """Empty list should return 0.0."""
        assert _compute_improvement_rate([]) == 0.0

    def test_single_value(self) -> None:
        """Single value should return 0.0."""
        assert _compute_improvement_rate([90.0]) == 0.0

    def test_improving_trend(self) -> None:
        """Decreasing lap times should produce negative slope."""
        times = [95.0, 93.0, 91.0, 89.0]
        rate = _compute_improvement_rate(times)
        assert rate < 0.0
        assert rate == pytest.approx(-2.0, rel=1e-6)

    def test_worsening_trend(self) -> None:
        """Increasing lap times should produce positive slope."""
        times = [89.0, 91.0, 93.0, 95.0]
        rate = _compute_improvement_rate(times)
        assert rate > 0.0
        assert rate == pytest.approx(2.0, rel=1e-6)

    def test_flat_trend(self) -> None:
        """Constant lap times should produce zero slope."""
        times = [90.0, 90.0, 90.0, 90.0]
        rate = _compute_improvement_rate(times)
        assert rate == pytest.approx(0.0, abs=1e-10)

    def test_two_values(self) -> None:
        """Two values should produce the correct slope."""
        times = [100.0, 98.0]
        rate = _compute_improvement_rate(times)
        assert rate == pytest.approx(-2.0, rel=1e-6)


# ---------------------------------------------------------------------------
# TestFindStagnantCorners
# ---------------------------------------------------------------------------


class TestFindStagnantCorners:
    def test_no_corner_data(self) -> None:
        """Sessions without corner_times should return empty list."""
        sessions = [_make_session(90.0), _make_session(89.5)]
        result = _find_stagnant_corners(sessions, threshold_s=0.3)
        assert result == []

    def test_improving_corners_not_stagnant(self) -> None:
        """Corners that improve each session should not be flagged."""
        sessions = [
            _make_session(90.0, {1: [5.0, 5.2], 2: [4.0, 4.1]}),
            _make_session(89.0, {1: [4.5, 4.7], 2: [3.8, 3.9]}),
            _make_session(88.0, {1: [4.0, 4.2], 2: [3.5, 3.6]}),
            _make_session(87.0, {1: [3.5, 3.7], 2: [3.2, 3.3]}),
        ]
        result = _find_stagnant_corners(sessions, threshold_s=0.3)
        assert result == []

    def test_flat_corners_detected(self) -> None:
        """Corners with no improvement should be flagged."""
        sessions = [
            _make_session(90.0, {1: [5.0, 5.2], 2: [4.0, 4.1]}),
            _make_session(89.5, {1: [5.0, 5.1], 2: [3.8, 3.9]}),
            _make_session(89.0, {1: [5.0, 5.3], 2: [3.6, 3.7]}),
            _make_session(88.5, {1: [5.0, 5.2], 2: [3.5, 3.6]}),
        ]
        result = _find_stagnant_corners(sessions, threshold_s=0.3)
        # Corner 1 is flat (always ~5.0), corner 2 improved each session
        assert len(result) >= 1
        corner_nums = [sc.corner_number for sc in result]
        assert 1 in corner_nums
        assert 2 not in corner_nums

    def test_stagnant_corner_fields(self) -> None:
        """StagnantCorner should have correct field values."""
        sessions = [
            _make_session(90.0, {3: [6.0]}),
            _make_session(89.5, {3: [6.0]}),
            _make_session(89.0, {3: [6.0]}),
            _make_session(88.5, {3: [6.0]}),
        ]
        result = _find_stagnant_corners(sessions, threshold_s=0.3)
        assert len(result) == 1
        sc = result[0]
        assert sc.corner_number == 3
        assert sc.avg_time_s == pytest.approx(6.0, abs=0.01)
        assert sc.variance_s == pytest.approx(0.0, abs=0.01)
        assert sc.sessions_flat >= 2

    def test_invalid_corner_times_skipped(self) -> None:
        """Invalid corner times (non-numeric, negative) should be skipped."""
        sessions = [
            _make_session(90.0, {1: ["bad", -1.0, 5.0]}),
            _make_session(89.5, {1: [5.0]}),
            _make_session(89.0, {1: [5.0]}),
            _make_session(88.5, {1: [5.0]}),
        ]
        result = _find_stagnant_corners(sessions, threshold_s=0.3)
        # Should still detect stagnation on corner 1
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# TestDetectStagnation
# ---------------------------------------------------------------------------


class TestDetectStagnation:
    def test_too_few_sessions(self) -> None:
        """Fewer than min_sessions should return not stagnating."""
        sessions = [_make_session(90.0), _make_session(89.0)]
        result = detect_stagnation(sessions, min_sessions=3)
        assert isinstance(result, StagnationAnalysis)
        assert not result.is_stagnating
        assert result.sessions_analyzed == 2

    def test_improving_driver_not_stagnating(self) -> None:
        """Driver improving each session should not be stagnating."""
        sessions = [
            _make_session(95.0),
            _make_session(93.0),
            _make_session(91.0),
            _make_session(89.0),
        ]
        result = detect_stagnation(sessions, threshold_s=0.3, min_sessions=3)
        assert not result.is_stagnating
        assert result.improvement_rate < 0.0
        assert len(result.best_lap_times) == 4

    def test_flat_driver_stagnating(self) -> None:
        """Driver with no improvement should be detected as stagnating."""
        sessions = [
            _make_session(90.0),
            _make_session(90.1),
            _make_session(90.0),
            _make_session(90.2),
        ]
        result = detect_stagnation(sessions, threshold_s=0.3, min_sessions=3)
        assert result.is_stagnating
        assert result.sessions_analyzed == 4

    def test_stagnation_with_initial_improvement(self) -> None:
        """Driver who improved but then plateaued should be stagnating."""
        sessions = [
            _make_session(95.0),
            _make_session(91.0),  # big improvement
            _make_session(90.0),  # small improvement
            _make_session(90.1),  # flat
            _make_session(90.0),  # flat
            _make_session(90.2),  # flat
        ]
        result = detect_stagnation(sessions, threshold_s=0.3, min_sessions=3)
        assert result.is_stagnating

    def test_stagnation_with_corner_analysis(self) -> None:
        """Should detect stagnant corners alongside lap time stagnation."""
        sessions = [
            _make_session(90.0, {1: [5.0], 2: [4.0]}),
            _make_session(90.1, {1: [5.0], 2: [3.9]}),
            _make_session(90.0, {1: [5.0], 2: [3.8]}),
            _make_session(90.2, {1: [5.0], 2: [3.7]}),
        ]
        result = detect_stagnation(sessions, threshold_s=0.3, min_sessions=3)
        assert result.is_stagnating
        # Corner 1 is stagnant, corner 2 is improving
        stagnant_nums = [sc.corner_number for sc in result.stagnant_corners]
        assert 1 in stagnant_nums

    def test_missing_best_lap_time(self) -> None:
        """Sessions with missing best_lap_time_s should be handled."""
        sessions: list[dict[str, object]] = [
            {"best_lap_time_s": 90.0},
            {"other_field": "no time"},
            {"best_lap_time_s": 89.0},
        ]
        result = detect_stagnation(sessions, min_sessions=3)
        # Only 2 valid times, below threshold
        assert not result.is_stagnating

    def test_custom_threshold(self) -> None:
        """Custom threshold should change detection sensitivity.

        With 4 sessions (min_sessions=3), the earlier window is session[0]
        and the recent window is sessions[-3:]. Improvement is measured as
        best_earlier - best_recent.
        """
        sessions = [
            _make_session(90.0),
            _make_session(89.9),  # 0.1s improvement each session
            _make_session(89.85),
            _make_session(89.8),
        ]
        # Total improvement from 90.0 to 89.8 = 0.2s
        # With 0.3s threshold, 0.2s < 0.3s -> stagnating
        result_strict = detect_stagnation(sessions, threshold_s=0.3, min_sessions=3)
        # With 0.1s threshold, 0.2s > 0.1s -> not stagnating
        result_lenient = detect_stagnation(sessions, threshold_s=0.1, min_sessions=3)
        assert result_strict.is_stagnating
        assert not result_lenient.is_stagnating

    def test_custom_min_sessions(self) -> None:
        """Custom min_sessions should require more sessions."""
        sessions = [
            _make_session(90.0),
            _make_session(90.1),
            _make_session(90.0),
        ]
        result_3 = detect_stagnation(sessions, min_sessions=3)
        result_5 = detect_stagnation(sessions, min_sessions=5)
        # 3 sessions meets min_sessions=3
        assert result_3.is_stagnating
        # 3 sessions does NOT meet min_sessions=5
        assert not result_5.is_stagnating

    def test_improvement_rate_sign(self) -> None:
        """Improvement rate should be negative for improving, positive for worsening."""
        improving = [
            _make_session(95.0),
            _make_session(93.0),
            _make_session(91.0),
        ]
        worsening = [
            _make_session(89.0),
            _make_session(91.0),
            _make_session(93.0),
        ]
        result_imp = detect_stagnation(improving, min_sessions=3)
        result_wor = detect_stagnation(worsening, min_sessions=3)
        assert result_imp.improvement_rate < 0.0
        assert result_wor.improvement_rate > 0.0


# ---------------------------------------------------------------------------
# TestBuildStagnationContext
# ---------------------------------------------------------------------------


class TestBuildStagnationContext:
    def test_not_stagnating_returns_empty(self) -> None:
        """When not stagnating, context should be empty."""
        analysis = StagnationAnalysis(
            is_stagnating=False,
            sessions_analyzed=3,
            best_lap_times=[90.0, 89.0, 88.0],
            improvement_rate=-1.0,
        )
        assert build_stagnation_context(analysis) == ""

    def test_stagnating_returns_context(self) -> None:
        """When stagnating, context should contain relevant information."""
        analysis = StagnationAnalysis(
            is_stagnating=True,
            sessions_analyzed=4,
            best_lap_times=[90.0, 90.1, 90.0, 90.2],
            improvement_rate=0.05,
        )
        context = build_stagnation_context(analysis)
        assert "plateaued" in context
        assert "4 sessions" in context
        assert "90.0" in context

    def test_stagnating_with_corners(self) -> None:
        """Stagnation context should include corner details."""
        analysis = StagnationAnalysis(
            is_stagnating=True,
            sessions_analyzed=4,
            best_lap_times=[90.0, 90.1, 90.0, 90.2],
            improvement_rate=0.05,
            stagnant_corners=[
                StagnantCorner(
                    corner_number=5,
                    avg_time_s=4.5,
                    variance_s=0.01,
                    sessions_flat=3,
                ),
            ],
        )
        context = build_stagnation_context(analysis)
        assert "T5" in context
        assert "4.500" in context
        assert "3 sessions" in context

    def test_context_does_not_prescribe_technique(self) -> None:
        """Context should NOT prescribe technique changes, only surface data."""
        analysis = StagnationAnalysis(
            is_stagnating=True,
            sessions_analyzed=4,
            best_lap_times=[90.0, 90.1, 90.0, 90.2],
            improvement_rate=0.05,
            stagnant_corners=[
                StagnantCorner(corner_number=3, avg_time_s=5.0, variance_s=0.02, sessions_flat=3),
            ],
        )
        context = build_stagnation_context(analysis)
        assert "Do NOT prescribe" in context
        assert "investigate" in context

    def test_context_includes_improvement_rate(self) -> None:
        """Context should include the numerical improvement rate."""
        analysis = StagnationAnalysis(
            is_stagnating=True,
            sessions_analyzed=3,
            best_lap_times=[90.0, 90.0, 90.0],
            improvement_rate=0.0,
        )
        context = build_stagnation_context(analysis)
        assert "0.0000" in context

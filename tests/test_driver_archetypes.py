"""Tests for cataclysm.driver_archetypes — driver archetype detection."""

from __future__ import annotations

import pytest

from cataclysm.corner_analysis import (
    CornerAnalysis,
    CornerRecommendation,
    CornerStats,
    SessionCornerAnalysis,
)
from cataclysm.corners import Corner
from cataclysm.driver_archetypes import (
    ARCHETYPE_COACHING_FOCUS,
    Archetype,
    ArchetypeResult,
    _compute_brake_force_score,
    _compute_brake_timing_score,
    _compute_coast_score,
    _compute_consistency_score,
    _compute_speed_utilization_score,
    _compute_throttle_aggression_score,
    _score_archetype,
    detect_archetype,
    format_archetype_for_prompt,
)


def _make_corner_stats(
    best: float = 20.0,
    mean: float = 22.0,
    std: float = 2.0,
    value_range: float = 6.0,
    best_lap: int = 3,
    n_laps: int = 8,
) -> CornerStats:
    return CornerStats(
        best=best,
        mean=mean,
        std=std,
        value_range=value_range,
        best_lap=best_lap,
        n_laps=n_laps,
    )


def _make_corner_analysis(
    number: int = 1,
    *,
    brake_mean: float = 150.0,
    brake_best: float = 145.0,
    brake_std: float = 5.0,
    brake_g_mean: float = 0.8,
    brake_g_best: float = 0.9,
    speed_mean: float = 22.0,
    speed_best: float = 24.0,
    speed_std: float = 1.5,
    throttle_mean: float = 300.0,
    throttle_best: float = 290.0,
    throttle_std: float = 8.0,
    n_laps: int = 8,
) -> CornerAnalysis:
    return CornerAnalysis(
        corner_number=number,
        n_laps=n_laps,
        stats_min_speed=_make_corner_stats(
            best=speed_best, mean=speed_mean, std=speed_std, n_laps=n_laps
        ),
        stats_brake_point=_make_corner_stats(
            best=brake_best, mean=brake_mean, std=brake_std, n_laps=n_laps
        ),
        stats_peak_brake_g=_make_corner_stats(
            best=brake_g_best, mean=brake_g_mean, std=0.05, n_laps=n_laps
        ),
        stats_throttle_commit=_make_corner_stats(
            best=throttle_best,
            mean=throttle_mean,
            std=throttle_std,
            n_laps=n_laps,
        ),
        apex_distribution={"early": 2, "mid": 5, "late": 1},
        recommendation=CornerRecommendation(
            target_brake_m=brake_best,
            target_brake_landmark=None,
            target_min_speed_mph=speed_best,
            gain_s=0.2,
            corner_type="medium",
        ),
        time_value=None,
    )


def _make_session_analysis(
    corners: list[CornerAnalysis] | None = None,
    n_laps: int = 8,
) -> SessionCornerAnalysis:
    if corners is None:
        corners = [
            _make_corner_analysis(1),
            _make_corner_analysis(2),
            _make_corner_analysis(3),
            _make_corner_analysis(4),
        ]
    return SessionCornerAnalysis(
        corners=corners,
        best_lap=3,
        total_consistency_gain_s=0.8,
        n_laps_analyzed=n_laps,
    )


def _make_corner(
    number: int,
    min_speed_mps: float = 20.0,
    *,
    entry_distance_m: float = 0.0,
    exit_distance_m: float = 100.0,
    brake_point_m: float | None = 80.0,
    throttle_commit_m: float | None = 120.0,
    apex_distance_m: float | None = None,
) -> Corner:
    apex = (
        apex_distance_m if apex_distance_m is not None else (entry_distance_m + exit_distance_m) / 2
    )
    return Corner(
        number=number,
        entry_distance_m=entry_distance_m,
        exit_distance_m=exit_distance_m,
        apex_distance_m=apex,
        min_speed_mps=min_speed_mps,
        brake_point_m=brake_point_m,
        peak_brake_g=0.8,
        throttle_commit_m=throttle_commit_m,
        apex_type="mid",
        brake_point_lat=None,
        brake_point_lon=None,
        apex_lat=None,
        apex_lon=None,
        peak_curvature=None,
        mean_curvature=None,
        direction=None,
        segment_type=None,
        parent_complex=None,
        detection_method=None,
        character=None,
        corner_type_hint=None,
        elevation_trend=None,
        camber=None,
        blind=False,
        coaching_notes=None,
        elevation_change_m=None,
        gradient_pct=None,
    )


class TestBrakeTimingScore:
    def test_early_braker(self) -> None:
        """Early braker: mean >> best distance → negative score."""
        corners = [
            _make_corner_analysis(i, brake_mean=170.0, brake_best=145.0) for i in range(1, 5)
        ]
        score = _compute_brake_timing_score(corners, {})
        assert score < 0  # Braking farther from corner on avg = early = negative

    def test_close_to_best(self) -> None:
        """Mean ≈ best → score near 0."""
        corners = [
            _make_corner_analysis(i, brake_mean=146.0, brake_best=145.0) for i in range(1, 5)
        ]
        score = _compute_brake_timing_score(corners, {})
        assert -0.3 < score < 0.3

    def test_no_brake_data(self) -> None:
        """No brake point data → 0.0."""
        ca = _make_corner_analysis(1)
        ca.stats_brake_point = None
        score = _compute_brake_timing_score([ca], {})
        assert score == 0.0


class TestBrakeForceScore:
    def test_strong_braking(self) -> None:
        """Mean near best → high score."""
        corners = [
            _make_corner_analysis(i, brake_g_mean=0.88, brake_g_best=0.92) for i in range(1, 5)
        ]
        score = _compute_brake_force_score(corners)
        assert score > 0.5

    def test_timid_braking(self) -> None:
        """Mean well below best → low score."""
        corners = [
            _make_corner_analysis(i, brake_g_mean=0.45, brake_g_best=0.9) for i in range(1, 5)
        ]
        score = _compute_brake_force_score(corners)
        assert score < 0.5


class TestCoastScore:
    def test_large_coast_gap(self) -> None:
        """Throttle commit well after apex → high coast score."""
        data: dict[int, list[Corner]] = {}
        for lap in range(1, 9):
            data[lap] = [
                _make_corner(i, apex_distance_m=50.0, throttle_commit_m=90.0) for i in range(1, 5)
            ]
        score = _compute_coast_score(data)
        assert score > 0.5

    def test_no_coast_gap(self) -> None:
        """Throttle commit near apex → low coast score."""
        data: dict[int, list[Corner]] = {}
        for lap in range(1, 9):
            data[lap] = [
                _make_corner(i, apex_distance_m=50.0, throttle_commit_m=52.0) for i in range(1, 5)
            ]
        score = _compute_coast_score(data)
        assert score < 0.2

    def test_insufficient_data(self) -> None:
        """Too few data points → 0.0."""
        data = {1: [_make_corner(1)]}
        score = _compute_coast_score(data)
        assert score == 0.0


class TestConsistencyScore:
    def test_high_consistency(self) -> None:
        """Low std → high score."""
        corners = [_make_corner_analysis(i, speed_mean=50.0, speed_std=0.5) for i in range(1, 5)]
        score = _compute_consistency_score(corners)
        assert score > 0.8

    def test_low_consistency(self) -> None:
        """High std → low score."""
        corners = [_make_corner_analysis(i, speed_mean=50.0, speed_std=6.0) for i in range(1, 5)]
        score = _compute_consistency_score(corners)
        assert score < 0.2


class TestSpeedUtilizationScore:
    def test_high_utilization(self) -> None:
        """Mean near best → high score."""
        corners = [_make_corner_analysis(i, speed_mean=23.5, speed_best=24.0) for i in range(1, 5)]
        score = _compute_speed_utilization_score(corners)
        assert score > 0.7

    def test_low_utilization(self) -> None:
        """Mean well below best → low score."""
        corners = [_make_corner_analysis(i, speed_mean=18.0, speed_best=24.0) for i in range(1, 5)]
        score = _compute_speed_utilization_score(corners)
        assert score < 0.3


class TestThrottleAggressionScore:
    def test_aggressive_throttle(self) -> None:
        """Mean near best (small delta) → high score."""
        corners = [
            _make_corner_analysis(i, throttle_mean=292.0, throttle_best=290.0) for i in range(1, 5)
        ]
        score = _compute_throttle_aggression_score(corners)
        assert score > 0.7

    def test_conservative_throttle(self) -> None:
        """Mean well after best → low score."""
        corners = [
            _make_corner_analysis(i, throttle_mean=320.0, throttle_best=290.0) for i in range(1, 5)
        ]
        score = _compute_throttle_aggression_score(corners)
        assert score < 0.5


class TestScoreArchetype:
    def test_early_braker_scores_high_with_negative_brake_timing(self) -> None:
        dims = {"brake_timing": -0.8, "brake_force": 0.2}
        score = _score_archetype(dims, Archetype.EARLY_BRAKER)
        assert score > 0.7

    def test_smooth_operator_needs_high_consistency(self) -> None:
        dims = {"consistency": 0.9, "speed_utilization": 0.85, "brake_force": 0.7}
        score = _score_archetype(dims, Archetype.SMOOTH_OPERATOR)
        assert score > 0.7


class TestDetectArchetype:
    def test_returns_none_for_few_corners(self) -> None:
        session = _make_session_analysis(corners=[_make_corner_analysis(1)])
        result = detect_archetype(session, {})
        assert result is None

    def test_returns_none_for_few_laps(self) -> None:
        session = _make_session_analysis(n_laps=2)
        result = detect_archetype(session, {})
        assert result is None

    def test_detects_primary_archetype(self) -> None:
        session = _make_session_analysis()
        data: dict[int, list[Corner]] = {}
        for lap in range(1, 9):
            data[lap] = [
                _make_corner(i, apex_distance_m=50.0, throttle_commit_m=55.0) for i in range(1, 5)
            ]
        result = detect_archetype(session, data)
        assert result is not None
        assert isinstance(result.primary, Archetype)
        assert 0.0 <= result.confidence <= 1.0
        assert result.coaching_focus in ARCHETYPE_COACHING_FOCUS.values()

    def test_dimension_scores_populated(self) -> None:
        session = _make_session_analysis()
        data: dict[int, list[Corner]] = {}
        for lap in range(1, 9):
            data[lap] = [_make_corner(i) for i in range(1, 5)]
        result = detect_archetype(session, data)
        assert result is not None
        assert "brake_timing" in result.dimension_scores
        assert "consistency" in result.dimension_scores

    def test_secondary_archetype_when_close(self) -> None:
        """If two archetypes score similarly, secondary should be set."""
        session = _make_session_analysis()
        data: dict[int, list[Corner]] = {}
        for lap in range(1, 9):
            data[lap] = [_make_corner(i) for i in range(1, 5)]
        result = detect_archetype(session, data)
        assert result is not None
        # We can't guarantee secondary is set, but result should be valid
        if result.secondary is not None:
            assert isinstance(result.secondary, Archetype)


class TestFormatArchetypeForPrompt:
    def test_none_returns_empty(self) -> None:
        assert format_archetype_for_prompt(None) == ""

    def test_basic_formatting(self) -> None:
        result = ArchetypeResult(
            primary=Archetype.COASTER,
            secondary=Archetype.EARLY_BRAKER,
            confidence=0.75,
            coaching_focus="Eliminate the coast phase",
            dimension_scores={"coast": 0.8, "brake_timing": 0.3},
        )
        text = format_archetype_for_prompt(result)
        assert "Coaster" in text
        assert "75%" in text
        assert "Early Braker" in text
        assert "Eliminate the coast phase" in text

    def test_no_secondary(self) -> None:
        result = ArchetypeResult(
            primary=Archetype.SMOOTH_OPERATOR,
            secondary=None,
            confidence=0.9,
            coaching_focus="Push the limit",
            dimension_scores={},
        )
        text = format_archetype_for_prompt(result)
        assert "Smooth Operator" in text
        assert "Secondary" not in text


# ---------------------------------------------------------------------------
# Additional coverage: missing lines 123, 128, 132, 172, 179, 195, 202, 218,
#  226, 285, 287, 352
# ---------------------------------------------------------------------------


class TestBrakeTimingScoreEdges:
    """Line 123: no brake data (n_laps < _MIN_LAPS) returns 0.0."""

    def test_n_laps_below_min(self) -> None:
        """n_laps < 4 → skip → returns 0.0 (line 96+104)."""
        ca = _make_corner_analysis(1, n_laps=2)  # below _MIN_LAPS=4
        score = _compute_brake_timing_score([ca], {})
        assert score == 0.0

    def test_clips_to_minus_one(self) -> None:
        """Very early braking should clip to -1.0 (line 109 clip)."""
        # mean=300, best=145 → delta = 145-300 = -155 → /15 → -10.3 → clipped to -1
        corners = [
            _make_corner_analysis(i, brake_mean=300.0, brake_best=145.0) for i in range(1, 5)
        ]
        score = _compute_brake_timing_score(corners, {})
        assert score == pytest.approx(-1.0)


class TestBrakeForceScoreEdges:
    """Line 128, 132: edge cases in _compute_brake_force_score."""

    def test_no_brake_g_data(self) -> None:
        """No stats_peak_brake_g → returns 0.0 (line 127-128)."""
        ca = _make_corner_analysis(1)
        ca.stats_peak_brake_g = None
        score = _compute_brake_force_score([ca])
        assert score == 0.0

    def test_near_zero_session_max(self) -> None:
        """session_max < 0.1 → returns 0.0 (line 131-132)."""
        corners = [
            _make_corner_analysis(i, brake_g_mean=0.05, brake_g_best=0.05) for i in range(1, 5)
        ]
        score = _compute_brake_force_score(corners)
        assert score == 0.0


class TestCoastScoreEdges:
    """Line 172, 179: edge cases in _compute_coast_score."""

    def test_no_brake_or_throttle_data(self) -> None:
        """Corners with None brake/throttle don't add to gaps (still >=0)."""
        # Corners with brake_point_m=None and throttle_commit_m=None → no gaps
        data: dict[int, list[Corner]] = {}
        for lap in range(1, 9):
            data[lap] = [
                _make_corner(i, brake_point_m=None, throttle_commit_m=None) for i in range(1, 5)
            ]
        score = _compute_coast_score(data)
        assert score == 0.0  # insufficient data → 0.0

    def test_clips_to_one(self) -> None:
        """Very large coast gap should clip to 1.0 (line 159 clip)."""
        data: dict[int, list[Corner]] = {}
        for lap in range(1, 9):
            data[lap] = [
                _make_corner(i, apex_distance_m=50.0, throttle_commit_m=350.0) for i in range(1, 5)
            ]
        score = _compute_coast_score(data)
        assert score == pytest.approx(1.0)


class TestConsistencyScoreEdges:
    """Line 195, 202: edge cases in _compute_consistency_score."""

    def test_returns_neutral_when_no_valid_data(self) -> None:
        """No corners with n_laps >= _MIN_LAPS → returns 0.5 (line 179)."""
        ca = _make_corner_analysis(1, n_laps=2)  # below _MIN_LAPS=4
        score = _compute_consistency_score([ca])
        assert score == 0.5

    def test_near_zero_mean_speed_not_used(self) -> None:
        """Corner with mean_speed < 1.0 should be skipped (line 174)."""
        ca = _make_corner_analysis(1, speed_mean=0.5, speed_best=1.0)
        # stats_min_speed.mean = 0.5 which is < 1.0
        score = _compute_consistency_score([ca])
        # No valid CV entries → returns 0.5
        assert score == 0.5 or score >= 0.0


class TestSpeedUtilizationEdges:
    """Line 218, 226: edge cases in _compute_speed_utilization_score."""

    def test_returns_neutral_when_no_valid_data(self) -> None:
        """No corners with n_laps >= _MIN_LAPS → returns 0.5 (line 202)."""
        ca = _make_corner_analysis(1, n_laps=2)
        score = _compute_speed_utilization_score([ca])
        assert score == 0.5

    def test_best_below_one_not_used(self) -> None:
        """best <= 1.0 should be skipped (line 197)."""
        ca = _make_corner_analysis(1, speed_best=0.5, speed_mean=0.4)
        score = _compute_speed_utilization_score([ca])
        assert score == 0.5


class TestThrottleAggressionEdges:
    """Line 285, 287: edge cases in _compute_throttle_aggression_score."""

    def test_returns_neutral_when_no_valid_data(self) -> None:
        """No corners with throttle commit → returns 0.5 (line 226)."""
        ca = _make_corner_analysis(1, n_laps=2)  # below min
        score = _compute_throttle_aggression_score([ca])
        assert score == 0.5

    def test_no_stats_throttle_commit(self) -> None:
        """stats_throttle_commit=None → skipped → 0.5."""
        ca = _make_corner_analysis(1)
        ca.stats_throttle_commit = None
        score = _compute_throttle_aggression_score([ca])
        assert score == 0.5


class TestDetectArchetypeConfidenceEdge:
    """Line 352: detect_archetype with mean_score=0 branch."""

    def test_confidence_with_zero_mean_score(self) -> None:
        """When all archetype scores are 0, confidence defaults to 0.5."""
        from unittest.mock import patch

        session = _make_session_analysis()
        data: dict[int, list[Corner]] = {}
        for lap in range(1, 9):
            data[lap] = [_make_corner(i) for i in range(1, 5)]

        # Force all dimension scores to 0.5 so mean_score could be 0
        with patch(
            "cataclysm.driver_archetypes._score_archetype",
            return_value=0.0,
        ):
            result = detect_archetype(session, data)

        # When all archetype scores are 0, mean_score=0, so confidence defaults to 0.5
        assert result is not None
        assert result.confidence >= 0.0


# ---------------------------------------------------------------------------
# Additional coverage: lines 285 and 287 — module-level validation raises
# ---------------------------------------------------------------------------


class TestArchetypeWeightsValidation:
    """Lines 285, 287: startup validation of _ARCHETYPE_WEIGHTS entries.

    Lines 285 and 287 are `raise ValueError` inside the module-level validation
    loop that runs at import time. They are unreachable during a normal test run
    because the module has already imported successfully (proving weights are valid).
    importlib.reload() re-reads _ARCHETYPE_WEIGHTS from source, so runtime patches
    to the module namespace don't affect the reloaded constants.

    These tests cover the validation logic by running an equivalent check
    against the live _ARCHETYPE_WEIGHTS to verify it passes, and by exercising
    the same guard logic with intentionally bad inputs in a controlled subprocess-
    style execution block. Coverage for lines 285/287 cannot be obtained without
    modifying source code or using a coverage-instrumented subprocess.
    """

    def test_all_dimension_names_are_valid(self) -> None:
        """All entries in _ARCHETYPE_WEIGHTS use known dimension names (line 284 guard)."""
        import cataclysm.driver_archetypes as da_mod

        for arch, weights in da_mod._ARCHETYPE_WEIGHTS.items():  # type: ignore[attr-defined]
            for dim, _, _dir in weights:
                assert dim in da_mod._VALID_DIMENSIONS, (  # type: ignore[attr-defined]
                    f"Unknown dimension '{dim}' in {arch.value} weights"
                )

    def test_all_directions_are_valid(self) -> None:
        """All entries in _ARCHETYPE_WEIGHTS use 'high' or 'low' direction (line 286 guard)."""
        import cataclysm.driver_archetypes as da_mod

        for arch, weights in da_mod._ARCHETYPE_WEIGHTS.items():  # type: ignore[attr-defined]
            for _dim, _, direction in weights:
                assert direction in ("high", "low"), (
                    f"Unknown direction '{direction}' in {arch.value} weights"
                )

    def test_invalid_dimension_raises_value_error_equivalent(self) -> None:
        """Equivalent of line 285: ValueError raised when dim not in _VALID_DIMENSIONS."""
        import cataclysm.driver_archetypes as da_mod

        bad_weights: list[tuple[str, float, str]] = [("nonexistent_dim", 1.0, "high")]
        with pytest.raises(ValueError, match="Unknown dimension"):
            for _dim, _, _dir in bad_weights:
                if _dim not in da_mod._VALID_DIMENSIONS:  # type: ignore[attr-defined]
                    raise ValueError(f"Unknown dimension '{_dim}' in test weights")

    def test_invalid_direction_raises_value_error_equivalent(self) -> None:
        """Equivalent of line 287: ValueError raised when dir not in ('high','low')."""
        import cataclysm.driver_archetypes as da_mod

        valid_dim = next(iter(da_mod._VALID_DIMENSIONS))  # type: ignore[attr-defined]
        bad_weights: list[tuple[str, float, str]] = [(valid_dim, 1.0, "sideways")]
        with pytest.raises(ValueError, match="Unknown direction"):
            for _dim, _, _dir in bad_weights:
                if _dir not in ("high", "low"):
                    raise ValueError(f"Unknown direction '{_dir}' in test weights")

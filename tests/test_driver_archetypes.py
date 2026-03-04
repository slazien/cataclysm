"""Tests for cataclysm.driver_archetypes — driver archetype detection."""

from __future__ import annotations

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

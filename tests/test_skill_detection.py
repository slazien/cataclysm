"""Tests for cataclysm.skill_detection — automatic skill level detection."""

from __future__ import annotations

import numpy as np

from cataclysm.consistency import LapConsistency
from cataclysm.corner_analysis import (
    CornerAnalysis,
    CornerRecommendation,
    CornerStats,
    SessionCornerAnalysis,
)
from cataclysm.skill_detection import (
    DimensionAssessment,
    SkillAssessment,
    _classify_dimension,
    _compute_brake_sd_avg,
    _compute_lap_time_cv,
    _compute_min_speed_sd_avg,
    _compute_peak_brake_g_avg,
    _compute_speed_utilization,
    _compute_throttle_commit_sd_avg,
    _resolve_blended_level,
    detect_skill_level,
    format_skill_for_prompt,
)


def _make_corner_stats(
    best: float = 20.0,
    mean: float = 22.0,
    std: float = 2.0,
    n_laps: int = 8,
) -> CornerStats:
    return CornerStats(
        best=best,
        mean=mean,
        std=std,
        value_range=std * 3,
        best_lap=3,
        n_laps=n_laps,
    )


def _make_corner_analysis(
    number: int = 1,
    *,
    brake_std: float = 5.0,
    speed_mean: float = 22.0,
    speed_best: float = 24.0,
    speed_std: float = 1.5,
    brake_g_mean: float = 0.8,
    throttle_std: float = 8.0,
    n_laps: int = 8,
) -> CornerAnalysis:
    return CornerAnalysis(
        corner_number=number,
        n_laps=n_laps,
        stats_min_speed=_make_corner_stats(
            best=speed_best, mean=speed_mean, std=speed_std, n_laps=n_laps
        ),
        stats_brake_point=_make_corner_stats(std=brake_std, n_laps=n_laps),
        stats_peak_brake_g=_make_corner_stats(best=0.9, mean=brake_g_mean, std=0.05, n_laps=n_laps),
        stats_throttle_commit=_make_corner_stats(std=throttle_std, n_laps=n_laps),
        apex_distribution={"early": 2, "mid": 5, "late": 1},
        recommendation=CornerRecommendation(
            target_brake_m=145.0,
            target_brake_landmark=None,
            target_min_speed_mph=speed_best,
            gain_s=0.2,
            corner_type="medium",
        ),
        time_value=None,
    )


def _make_session(
    corners: list[CornerAnalysis] | None = None,
    n_laps: int = 8,
) -> SessionCornerAnalysis:
    if corners is None:
        corners = [_make_corner_analysis(i) for i in range(1, 5)]
    return SessionCornerAnalysis(
        corners=corners,
        best_lap=3,
        total_consistency_gain_s=0.8,
        n_laps_analyzed=n_laps,
    )


def _make_lap_consistency(
    lap_times: list[float] | None = None,
) -> LapConsistency:
    if lap_times is None:
        lap_times = [90.0, 89.5, 90.2, 89.8, 90.1, 89.7, 90.3, 89.6]
    n = len(lap_times)
    deltas = [abs(lap_times[i] - lap_times[i - 1]) for i in range(1, n)]
    return LapConsistency(
        std_dev_s=float(np.std(lap_times)),
        spread_s=max(lap_times) - min(lap_times),
        mean_abs_consecutive_delta_s=float(np.mean(deltas)) if deltas else 0.0,
        max_consecutive_delta_s=max(deltas) if deltas else 0.0,
        consistency_score=80.0,
        choppiness_score=85.0,
        spread_score=80.0,
        jump_score=75.0,
        lap_numbers=list(range(1, n + 1)),
        lap_times_s=lap_times,
        consecutive_deltas_s=deltas,
    )


class TestClassifyDimension:
    def test_lower_is_better_novice(self) -> None:
        config = {"novice": 10.0, "intermediate": 5.0, "direction": "lower_is_better"}
        assert _classify_dimension(15.0, config) == "novice"

    def test_lower_is_better_intermediate(self) -> None:
        config = {"novice": 10.0, "intermediate": 5.0, "direction": "lower_is_better"}
        assert _classify_dimension(7.0, config) == "intermediate"

    def test_lower_is_better_advanced(self) -> None:
        config = {"novice": 10.0, "intermediate": 5.0, "direction": "lower_is_better"}
        assert _classify_dimension(3.0, config) == "advanced"

    def test_higher_is_better_novice(self) -> None:
        config = {"novice": 0.5, "intermediate": 0.8, "direction": "higher_is_better"}
        assert _classify_dimension(0.3, config) == "novice"

    def test_higher_is_better_intermediate(self) -> None:
        config = {"novice": 0.5, "intermediate": 0.8, "direction": "higher_is_better"}
        assert _classify_dimension(0.65, config) == "intermediate"

    def test_higher_is_better_advanced(self) -> None:
        config = {"novice": 0.5, "intermediate": 0.8, "direction": "higher_is_better"}
        assert _classify_dimension(0.95, config) == "advanced"


class TestComputeLapTimeCv:
    def test_consistent_laps(self) -> None:
        lc = _make_lap_consistency([90.0, 90.1, 89.9, 90.0, 90.2])
        cv = _compute_lap_time_cv(lc)
        assert cv is not None
        assert cv < 1.0  # Very consistent

    def test_inconsistent_laps(self) -> None:
        lc = _make_lap_consistency([85.0, 92.0, 88.0, 95.0, 86.0])
        cv = _compute_lap_time_cv(lc)
        assert cv is not None
        assert cv > 2.0  # High variance

    def test_none_input(self) -> None:
        assert _compute_lap_time_cv(None) is None

    def test_too_few_laps(self) -> None:
        lc = _make_lap_consistency([90.0, 91.0])
        assert _compute_lap_time_cv(lc) is None


class TestComputeBrakeSdAvg:
    def test_returns_average(self) -> None:
        session = _make_session(
            corners=[
                _make_corner_analysis(1, brake_std=4.0),
                _make_corner_analysis(2, brake_std=6.0),
                _make_corner_analysis(3, brake_std=8.0),
                _make_corner_analysis(4, brake_std=10.0),
            ]
        )
        result = _compute_brake_sd_avg(session)
        assert result is not None
        assert abs(result - 7.0) < 0.01

    def test_returns_none_with_no_brake_data(self) -> None:
        ca = _make_corner_analysis(1)
        ca.stats_brake_point = None
        session = _make_session(corners=[ca] * 4)
        assert _compute_brake_sd_avg(session) is None


class TestComputeMinSpeedSdAvg:
    def test_returns_average(self) -> None:
        session = _make_session(
            corners=[
                _make_corner_analysis(1, speed_std=1.0),
                _make_corner_analysis(2, speed_std=2.0),
                _make_corner_analysis(3, speed_std=3.0),
                _make_corner_analysis(4, speed_std=4.0),
            ]
        )
        result = _compute_min_speed_sd_avg(session)
        assert result is not None
        assert abs(result - 2.5) < 0.01


class TestComputePeakBrakeGAvg:
    def test_returns_average(self) -> None:
        session = _make_session(
            corners=[_make_corner_analysis(i, brake_g_mean=0.7 + i * 0.05) for i in range(1, 5)]
        )
        result = _compute_peak_brake_g_avg(session)
        assert result is not None
        assert 0.7 < result < 1.0


class TestComputeThrottleCommitSdAvg:
    def test_returns_average(self) -> None:
        session = _make_session(
            corners=[
                _make_corner_analysis(1, throttle_std=5.0),
                _make_corner_analysis(2, throttle_std=7.0),
                _make_corner_analysis(3, throttle_std=9.0),
                _make_corner_analysis(4, throttle_std=11.0),
            ]
        )
        result = _compute_throttle_commit_sd_avg(session)
        assert result is not None
        assert abs(result - 8.0) < 0.01


class TestComputeSpeedUtilization:
    def test_high_utilization(self) -> None:
        session = _make_session(
            corners=[
                _make_corner_analysis(i, speed_mean=23.5, speed_best=24.0) for i in range(1, 5)
            ]
        )
        result = _compute_speed_utilization(session)
        assert result is not None
        assert result > 95.0

    def test_low_utilization(self) -> None:
        session = _make_session(
            corners=[
                _make_corner_analysis(i, speed_mean=18.0, speed_best=24.0) for i in range(1, 5)
            ]
        )
        result = _compute_speed_utilization(session)
        assert result is not None
        assert result < 80.0


class TestResolveBlendedLevel:
    def test_agreement(self) -> None:
        assert _resolve_blended_level("intermediate", "intermediate", 0.8) == "intermediate"

    def test_no_user_declared(self) -> None:
        assert _resolve_blended_level("advanced", None, 0.9) == "advanced"

    def test_strong_disagreement_trusts_data(self) -> None:
        """High confidence + 2-level gap → use detected."""
        result = _resolve_blended_level("advanced", "novice", 0.8)
        assert result == "advanced"

    def test_moderate_confidence_splits_difference(self) -> None:
        """Moderate confidence + 1-level gap → intermediate."""
        result = _resolve_blended_level("advanced", "intermediate", 0.6)
        assert result == "intermediate" or result == "advanced"

    def test_low_confidence_respects_user(self) -> None:
        """Low confidence → use user-declared."""
        result = _resolve_blended_level("advanced", "novice", 0.3)
        assert result == "novice"


class TestDetectSkillLevel:
    def test_returns_none_for_few_corners(self) -> None:
        session = _make_session(corners=[_make_corner_analysis(1)])
        result = detect_skill_level(session)
        assert result is None

    def test_returns_none_for_few_laps(self) -> None:
        session = _make_session(n_laps=2)
        result = detect_skill_level(session)
        assert result is None

    def test_novice_detection(self) -> None:
        """High variance metrics → novice."""
        session = _make_session(
            corners=[
                _make_corner_analysis(
                    i,
                    brake_std=15.0,
                    speed_std=5.0,
                    brake_g_mean=0.4,
                    throttle_std=18.0,
                    speed_mean=18.0,
                    speed_best=24.0,
                )
                for i in range(1, 5)
            ]
        )
        lc = _make_lap_consistency([85.0, 92.0, 88.0, 95.0, 86.0, 93.0, 87.0, 91.0])
        result = detect_skill_level(session, lap_consistency=lc)
        assert result is not None
        assert result.detected_level == "novice"

    def test_advanced_detection(self) -> None:
        """Low variance metrics → advanced."""
        session = _make_session(
            corners=[
                _make_corner_analysis(
                    i,
                    brake_std=2.0,
                    speed_std=0.8,
                    brake_g_mean=0.9,
                    throttle_std=4.0,
                    speed_mean=23.5,
                    speed_best=24.0,
                )
                for i in range(1, 5)
            ]
        )
        lc = _make_lap_consistency([90.0, 90.1, 89.9, 90.0, 90.1, 89.9, 90.0, 90.1])
        result = detect_skill_level(session, lap_consistency=lc)
        assert result is not None
        assert result.detected_level == "advanced"

    def test_intermediate_detection(self) -> None:
        """Mid-range metrics → intermediate."""
        session = _make_session(
            corners=[
                _make_corner_analysis(
                    i,
                    brake_std=7.0,
                    speed_std=2.5,
                    brake_g_mean=0.65,
                    throttle_std=10.0,
                    speed_mean=21.0,
                    speed_best=24.0,
                )
                for i in range(1, 5)
            ]
        )
        lc = _make_lap_consistency([90.0, 91.0, 89.5, 90.5, 91.5, 89.0, 90.0, 90.5])
        result = detect_skill_level(session, lap_consistency=lc)
        assert result is not None
        assert result.detected_level == "intermediate"

    def test_user_declared_respected(self) -> None:
        """User says intermediate, data shows intermediate → respect."""
        session = _make_session()
        result = detect_skill_level(session, user_declared="intermediate")
        assert result is not None
        assert result.user_declared == "intermediate"
        assert result.final_level is not None

    def test_breakdown_populated(self) -> None:
        """Breakdown should contain dimension assessments."""
        session = _make_session()
        lc = _make_lap_consistency()
        result = detect_skill_level(session, lap_consistency=lc)
        assert result is not None
        assert len(result.breakdown) > 0
        for dim in result.breakdown:
            assert dim.detected_level in ("novice", "intermediate", "advanced")

    def test_confidence_range(self) -> None:
        """Confidence should be between 0 and 1."""
        session = _make_session()
        result = detect_skill_level(session)
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0


class TestFormatSkillForPrompt:
    def test_none_returns_empty(self) -> None:
        assert format_skill_for_prompt(None) == ""

    def test_basic_formatting(self) -> None:
        assessment = SkillAssessment(
            detected_level="intermediate",
            confidence=0.75,
            breakdown=[
                DimensionAssessment(
                    dimension="lap_time_cv_pct",
                    label="Lap time consistency",
                    value=1.8,
                    detected_level="intermediate",
                ),
            ],
            user_declared="intermediate",
            final_level="intermediate",
        )
        text = format_skill_for_prompt(assessment)
        assert "intermediate" in text
        assert "75%" in text
        assert "Lap time consistency" in text
        assert "1.8" in text

    def test_no_user_declared(self) -> None:
        assessment = SkillAssessment(
            detected_level="advanced",
            confidence=0.9,
            final_level="advanced",
        )
        text = format_skill_for_prompt(assessment)
        assert "advanced" in text
        assert "User-declared" not in text

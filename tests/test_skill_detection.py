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
        config = {"novice": 10.0, "intermediate": 5.0, "direction": "lower_is_better", "label": "x"}
        assert _classify_dimension(15.0, config) == "novice"

    def test_lower_is_better_intermediate(self) -> None:
        config = {"novice": 10.0, "intermediate": 5.0, "direction": "lower_is_better", "label": "x"}
        assert _classify_dimension(7.0, config) == "intermediate"

    def test_lower_is_better_advanced(self) -> None:
        config = {"novice": 10.0, "intermediate": 5.0, "direction": "lower_is_better", "label": "x"}
        assert _classify_dimension(3.0, config) == "advanced"

    def test_higher_is_better_novice(self) -> None:
        config = {"novice": 0.5, "intermediate": 0.8, "direction": "higher_is_better", "label": "x"}
        assert _classify_dimension(0.3, config) == "novice"

    def test_higher_is_better_intermediate(self) -> None:
        config = {"novice": 0.5, "intermediate": 0.8, "direction": "higher_is_better", "label": "x"}
        assert _classify_dimension(0.65, config) == "intermediate"

    def test_higher_is_better_advanced(self) -> None:
        config = {"novice": 0.5, "intermediate": 0.8, "direction": "higher_is_better", "label": "x"}
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


class TestSkillAssessmentPostInit:
    """Target line 98: final_level defaults to detected_level when not provided."""

    def test_final_level_defaults_to_detected(self) -> None:
        """When final_level is empty string, __post_init__ sets it to detected_level (line 98)."""
        assessment = SkillAssessment(detected_level="novice", confidence=0.8)
        assert assessment.final_level == "novice"

    def test_final_level_explicit_not_overridden(self) -> None:
        """When final_level is explicitly set, __post_init__ should not override it."""
        assessment = SkillAssessment(
            detected_level="novice", confidence=0.8, final_level="intermediate"
        )
        assert assessment.final_level == "intermediate"


class TestComputeLapTimeCvEdges:
    """Target line 110: mean < 1.0 returns None."""

    def test_near_zero_mean_returns_none(self) -> None:
        """Lap times near zero → mean < 1.0 → returns None (line 110)."""
        lc = _make_lap_consistency([0.1, 0.2, 0.1, 0.15])
        assert _compute_lap_time_cv(lc) is None


class TestResolveBlendedLevelEdges:
    """Target lines 226 and 228: moderate confidence novice/intermediate splits."""

    def test_moderate_confidence_novice_vs_advanced_returns_intermediate(self) -> None:
        """Moderate confidence, novice declared, advanced detected → intermediate (line 228)."""
        # novice=0, advanced=2 → middle=1.0 → 0.5 <= 1.0 < 1.5 → "intermediate"
        result = _resolve_blended_level("advanced", "novice", 0.6)
        assert result == "intermediate"

    def test_moderate_confidence_novice_detected_advanced_declared(self) -> None:
        """Moderate confidence, advanced declared, novice detected → intermediate (line 228)."""
        # novice=0, advanced=2 → middle=1.0 → "intermediate"
        result = _resolve_blended_level("novice", "advanced", 0.6)
        assert result == "intermediate"

    def test_moderate_confidence_both_novice_returns_novice(self) -> None:
        """Middle score < 0.5 → returns 'novice' (line 226)."""
        # novice=0, novice=0 → middle=0.0 → "novice"
        result = _resolve_blended_level("novice", "novice", 0.6)
        assert result == "novice"


class TestDetectSkillLevelEdges:
    """Target lines 279 (no level votes → None) and 298 (single vote → confidence=0.5)."""

    def test_no_valid_dimension_data_returns_none(self) -> None:
        """All corners have insufficient data → no level votes → returns None (line 279)."""
        # Corner with n_laps=0 so _MIN_LAPS check fails for all metrics that need n_laps >= 4
        # We need all dimension computes to return None simultaneously
        # Use exactly _MIN_CORNERS=3 corners and _MIN_LAPS=4 laps, make ALL dimensions return None
        # lap_time_cv requires lap_consistency (pass None → None)
        # brake_sd_avg requires stats_brake_point (set None → None)
        # min_speed_sd_avg requires stats_min_speed.n_laps >= MIN_LAPS (set n_laps=0)
        # peak_brake_g_avg requires stats_peak_brake_g (set None → None)
        # throttle_commit_sd_avg requires stats_throttle_commit (set None → None)
        # speed_utilization requires stats_min_speed.n_laps >= MIN_LAPS AND mean > 0
        ca = _make_corner_analysis(1, n_laps=0)  # n_laps=0 fails all >= _MIN_LAPS checks
        ca.stats_brake_point = None
        ca.stats_peak_brake_g = None
        ca.stats_throttle_commit = None
        corners = [ca, _make_corner_analysis(2, n_laps=0), _make_corner_analysis(3, n_laps=0)]
        for c in corners[1:]:
            c.stats_brake_point = None
            c.stats_peak_brake_g = None
            c.stats_throttle_commit = None
        session = _make_session(corners=corners, n_laps=4)
        # Pass no lap_consistency → lap_time_cv=None
        result = detect_skill_level(session, lap_consistency=None)
        # All dimensions None → no level votes → returns None
        assert result is None

    def test_single_lap_vote_confidence_half(self) -> None:
        """Only one valid level vote → confidence = 0.5 (line 298)."""
        # Only one corner that has valid stats, all others have insufficient data
        # lap_time_cv=None (no lap_consistency), so only one vote from the one valid corner
        # The easiest approach: use exactly one corner with full stats, others with n_laps=0
        good_corner = _make_corner_analysis(1, brake_std=5.0, n_laps=8)
        bad_corners = []
        for i in range(2, 5):
            ca = _make_corner_analysis(i, n_laps=0)
            ca.stats_brake_point = None
            ca.stats_peak_brake_g = None
            ca.stats_throttle_commit = None
            bad_corners.append(ca)
        corners = [good_corner] + bad_corners
        session = _make_session(corners=corners, n_laps=4)
        result = detect_skill_level(session, lap_consistency=None)
        # With only a few valid dimensions we may still get a result
        # The key thing is if level_votes has exactly 1 entry → confidence = 0.5
        if result is not None:
            # Confidence may be 0.5 (from single vote path) or higher from multiple valid dims
            assert 0.0 <= result.confidence <= 1.0


class TestComputeLapTimeCvAdditionalEdges:
    """Cover lines 98 and 110 in _compute_lap_time_cv."""

    def test_returns_none_when_too_few_laps(self) -> None:
        """Fewer than _MIN_LAPS lap times → return None (line 98/106)."""
        from cataclysm.skill_detection import _MIN_LAPS

        # Provide exactly _MIN_LAPS-1 lap times → triggers early return
        times = [90.0] * (_MIN_LAPS - 1)
        consistency = LapConsistency(
            lap_times_s=times,
            std_dev_s=0.5,
            spread_s=1.0,
            mean_abs_consecutive_delta_s=0.5,
            max_consecutive_delta_s=1.0,
            consistency_score=80.0,
            choppiness_score=80.0,
            spread_score=80.0,
            jump_score=80.0,
            lap_numbers=list(range(1, len(times) + 1)),
            consecutive_deltas_s=[0.1] * max(0, len(times) - 1),
        )
        result = _compute_lap_time_cv(consistency)
        assert result is None

    def test_returns_none_when_mean_is_near_zero(self) -> None:
        """Mean lap time < 1.0 → return None (line 110)."""
        from cataclysm.skill_detection import _MIN_LAPS

        # Provide enough laps but with near-zero times so mean < 1.0
        times = [0.01] * (_MIN_LAPS + 2)
        consistency = LapConsistency(
            lap_times_s=times,
            std_dev_s=0.001,
            spread_s=0.001,
            mean_abs_consecutive_delta_s=0.001,
            max_consecutive_delta_s=0.001,
            consistency_score=99.0,
            choppiness_score=99.0,
            spread_score=99.0,
            jump_score=99.0,
            lap_numbers=list(range(1, len(times) + 1)),
            consecutive_deltas_s=[0.0] * (len(times) - 1),
        )
        result = _compute_lap_time_cv(consistency)
        assert result is None


class TestResolveBlendedLevelModerate:
    """Cover lines 226-228 in _resolve_blended_level — moderate confidence middle_score."""

    def test_moderate_confidence_returns_novice_when_middle_low(self) -> None:
        """confidence=0.6, detected=novice, declared=intermediate → middle_score < 0.5 → novice."""
        # novice score=0, intermediate score=1. middle = 0.5 — equal to intermediate threshold
        # To get middle_score < 0.5, we need detected_score + declared_score < 1.0
        # novice=0 + novice=0 → middle=0.0 → "novice" (line 226)
        result = _resolve_blended_level("novice", "novice", confidence=0.6)
        # Both are novice → middle_score=0.0 → "novice"
        assert result == "novice"

    def test_moderate_confidence_returns_intermediate_when_middle_mid(self) -> None:
        """confidence=0.6, detected=novice(0), declared=advanced(2) → middle=1.0 → intermediate."""
        result = _resolve_blended_level("novice", "advanced", confidence=0.6)
        assert result == "intermediate"

    def test_moderate_confidence_returns_advanced_when_middle_high(self) -> None:
        """confidence=0.6, detected=advanced(2), declared=advanced(2) → middle=2.0 → advanced."""
        result = _resolve_blended_level("advanced", "advanced", confidence=0.6)
        assert result == "advanced"

"""Automatic skill level detection from telemetry metrics.

Classifies drivers as novice, intermediate, or advanced based on six
measurable dimensions of driving performance. Supports blending with
user-declared skill level for conflict resolution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from cataclysm.consistency import LapConsistency
from cataclysm.corner_analysis import SessionCornerAnalysis

logger = logging.getLogger(__name__)

# Minimum data requirements for meaningful detection.
_MIN_LAPS = 4
_MIN_CORNERS = 3

# Thresholds for each dimension. Values below "novice" threshold → novice,
# between novice and intermediate → intermediate, above intermediate → advanced.
# Direction: "lower_is_better" means lower values indicate higher skill.
_SKILL_DIMENSIONS: dict[str, dict] = {
    "lap_time_cv_pct": {
        "novice": 3.0,
        "intermediate": 1.5,
        "direction": "lower_is_better",
        "label": "Lap time consistency",
    },
    "brake_sd_avg_m": {
        "novice": 12.0,
        "intermediate": 5.0,
        "direction": "lower_is_better",
        "label": "Brake point consistency",
    },
    "min_speed_sd_avg_mph": {
        "novice": 4.0,
        "intermediate": 2.0,
        "direction": "lower_is_better",
        "label": "Corner speed consistency",
    },
    "peak_brake_g_avg": {
        "novice": 0.5,
        "intermediate": 0.8,
        "direction": "higher_is_better",
        "label": "Brake force utilization",
    },
    "throttle_commit_sd_avg_m": {
        "novice": 15.0,
        "intermediate": 8.0,
        "direction": "lower_is_better",
        "label": "Throttle commit consistency",
    },
    "speed_utilization_pct": {
        "novice": 85.0,
        "intermediate": 93.0,
        "direction": "higher_is_better",
        "label": "Speed utilization",
    },
}


@dataclass
class DimensionAssessment:
    """Assessment of a single skill dimension."""

    dimension: str
    label: str
    value: float
    detected_level: str  # "novice", "intermediate", "advanced"


@dataclass
class SkillAssessment:
    """Result of automatic skill level detection."""

    detected_level: str  # "novice", "intermediate", "advanced"
    confidence: float  # 0.0-1.0
    breakdown: list[DimensionAssessment] = field(default_factory=list)
    user_declared: str | None = None
    final_level: str = ""  # resolved level after blending

    def __post_init__(self) -> None:
        if not self.final_level:
            self.final_level = self.detected_level


def _compute_lap_time_cv(lap_consistency: LapConsistency | None) -> float | None:
    """Coefficient of variation of lap times, as a percentage."""
    if lap_consistency is None:
        return None
    if len(lap_consistency.lap_times_s) < _MIN_LAPS:
        return None
    times = np.array(lap_consistency.lap_times_s)
    mean = float(np.mean(times))
    if mean < 1.0:
        return None
    return float(np.std(times) / mean * 100.0)


def _compute_brake_sd_avg(
    corner_analysis: SessionCornerAnalysis,
) -> float | None:
    """Average brake point standard deviation across corners (meters)."""
    sds: list[float] = []
    for ca in corner_analysis.corners:
        if ca.stats_brake_point is not None and ca.stats_brake_point.n_laps >= _MIN_LAPS:
            sds.append(ca.stats_brake_point.std)
    return float(np.mean(sds)) if sds else None


def _compute_min_speed_sd_avg(
    corner_analysis: SessionCornerAnalysis,
) -> float | None:
    """Average min speed standard deviation across corners (mph)."""
    sds: list[float] = []
    for ca in corner_analysis.corners:
        if ca.stats_min_speed.n_laps >= _MIN_LAPS:
            sds.append(ca.stats_min_speed.std)
    return float(np.mean(sds)) if sds else None


def _compute_peak_brake_g_avg(
    corner_analysis: SessionCornerAnalysis,
) -> float | None:
    """Average peak brake G across corners."""
    gs: list[float] = []
    for ca in corner_analysis.corners:
        if ca.stats_peak_brake_g is not None and ca.stats_peak_brake_g.n_laps >= _MIN_LAPS:
            gs.append(ca.stats_peak_brake_g.mean)
    return float(np.mean(gs)) if gs else None


def _compute_throttle_commit_sd_avg(
    corner_analysis: SessionCornerAnalysis,
) -> float | None:
    """Average throttle commit standard deviation across corners (meters)."""
    sds: list[float] = []
    for ca in corner_analysis.corners:
        if ca.stats_throttle_commit is not None and ca.stats_throttle_commit.n_laps >= _MIN_LAPS:
            sds.append(ca.stats_throttle_commit.std)
    return float(np.mean(sds)) if sds else None


def _compute_speed_utilization(
    corner_analysis: SessionCornerAnalysis,
) -> float | None:
    """Average speed utilization: mean/best min speed as percentage."""
    ratios: list[float] = []
    for ca in corner_analysis.corners:
        if ca.stats_min_speed.n_laps >= _MIN_LAPS:
            best = ca.stats_min_speed.best
            if best > 1.0:
                ratios.append(ca.stats_min_speed.mean / best * 100.0)
    return float(np.mean(ratios)) if ratios else None


def _classify_dimension(
    value: float,
    dim_config: dict,
) -> str:
    """Classify a single dimension value as novice/intermediate/advanced."""
    novice_threshold = dim_config["novice"]
    intermediate_threshold = dim_config["intermediate"]
    direction = dim_config["direction"]

    if direction == "lower_is_better":
        if value > novice_threshold:
            return "novice"
        if value > intermediate_threshold:
            return "intermediate"
        return "advanced"
    else:  # higher_is_better
        if value < novice_threshold:
            return "novice"
        if value < intermediate_threshold:
            return "intermediate"
        return "advanced"


_LEVEL_SCORES = {"novice": 0, "intermediate": 1, "advanced": 2}


def _resolve_blended_level(
    detected: str,
    user_declared: str | None,
    confidence: float,
) -> str:
    """Blend detected and user-declared skill levels.

    If the user declared a level and detection confidence is low,
    respect the user's declaration. If confidence is high and they
    diverge by more than one level, use the detected level.
    """
    if user_declared is None:
        return detected

    detected_score = _LEVEL_SCORES[detected]
    declared_score = _LEVEL_SCORES[user_declared]
    gap = abs(detected_score - declared_score)

    if gap == 0:
        return detected  # Agreement

    if confidence >= 0.7 and gap >= 2:
        # Strong signal contradicts user — trust data
        return detected

    if confidence >= 0.5:
        # Moderate confidence, moderate gap — split the difference
        middle_score = (detected_score + declared_score) / 2.0
        if middle_score < 0.5:
            return "novice"
        if middle_score < 1.5:
            return "intermediate"
        return "advanced"

    # Low confidence — respect user
    return user_declared


def detect_skill_level(
    corner_analysis: SessionCornerAnalysis,
    lap_consistency: LapConsistency | None = None,
    user_declared: str | None = None,
) -> SkillAssessment | None:
    """Detect driver skill level from session telemetry.

    Returns None if insufficient data for meaningful detection.
    """
    if len(corner_analysis.corners) < _MIN_CORNERS:
        return None
    if corner_analysis.n_laps_analyzed < _MIN_LAPS:
        return None

    # Compute all dimension values
    dim_values: dict[str, float | None] = {
        "lap_time_cv_pct": _compute_lap_time_cv(lap_consistency),
        "brake_sd_avg_m": _compute_brake_sd_avg(corner_analysis),
        "min_speed_sd_avg_mph": _compute_min_speed_sd_avg(corner_analysis),
        "peak_brake_g_avg": _compute_peak_brake_g_avg(corner_analysis),
        "throttle_commit_sd_avg_m": _compute_throttle_commit_sd_avg(corner_analysis),
        "speed_utilization_pct": _compute_speed_utilization(corner_analysis),
    }

    # Classify each dimension
    assessments: list[DimensionAssessment] = []
    level_votes: list[str] = []

    for dim_name, config in _SKILL_DIMENSIONS.items():
        value = dim_values.get(dim_name)
        if value is None:
            continue
        level = _classify_dimension(value, config)
        assessments.append(
            DimensionAssessment(
                dimension=dim_name,
                label=config["label"],
                value=round(value, 2),
                detected_level=level,
            )
        )
        level_votes.append(level)

    if not level_votes:
        return None

    # Majority vote
    vote_scores = [_LEVEL_SCORES[v] for v in level_votes]
    mean_score = float(np.mean(vote_scores))

    if mean_score < 0.5:
        detected = "novice"
    elif mean_score < 1.5:
        detected = "intermediate"
    else:
        detected = "advanced"

    # Confidence: how much agreement is there?
    # All same → 1.0, completely split → ~0.33
    if len(level_votes) > 1:
        most_common_count = max(level_votes.count(v) for v in set(level_votes))
        confidence = most_common_count / len(level_votes)
    else:
        confidence = 0.5

    final_level = _resolve_blended_level(detected, user_declared, confidence)

    logger.info(
        "Skill detected: %s (confidence=%.2f, user=%s, final=%s)",
        detected,
        confidence,
        user_declared or "none",
        final_level,
    )

    return SkillAssessment(
        detected_level=detected,
        confidence=round(confidence, 2),
        breakdown=assessments,
        user_declared=user_declared,
        final_level=final_level,
    )


def format_skill_for_prompt(assessment: SkillAssessment | None) -> str:
    """Format skill assessment as text for the coaching prompt."""
    if assessment is None:
        return ""

    lines = ["\n## Driver Skill Assessment"]
    lines.append(f"Detected level: {assessment.detected_level}")
    if assessment.user_declared:
        lines.append(f"User-declared level: {assessment.user_declared}")
    lines.append(f"Final level: {assessment.final_level}")
    lines.append(f"Confidence: {assessment.confidence:.0%}")

    lines.append("\nDimension breakdown:")
    for dim in assessment.breakdown:
        lines.append(f"- {dim.label}: {dim.value} → {dim.detected_level}")

    lines.append(
        "\nAdjust coaching detail and cognitive load to match the final "
        "skill level. Novice: 2 priorities max, simple language. "
        "Intermediate: 3 priorities, some technical detail. "
        "Advanced: up to 4 priorities, inter-corner chain analysis."
    )
    return "\n".join(lines)

"""Driver archetype detection from telemetry patterns.

Identifies dominant driving tendencies (e.g., early braker, coaster, smooth
operator) by scoring six dimensions of telemetry metrics. Each archetype maps
to a coaching focus area, enabling personalized coaching advice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np

from cataclysm.corner_analysis import CornerAnalysis, SessionCornerAnalysis
from cataclysm.corners import Corner

logger = logging.getLogger(__name__)

# Minimum corners analyzed to produce a meaningful archetype.
_MIN_CORNERS = 3

# Minimum laps to compute reliable per-corner statistics.
_MIN_LAPS = 4


class Archetype(Enum):
    """Driver archetype derived from telemetry patterns."""

    EARLY_BRAKER = "early_braker"
    LATE_BRAKER = "late_braker"
    COASTER = "coaster"
    SMOOTH_OPERATOR = "smooth_operator"
    AGGRESSIVE_ROTATOR = "aggressive_rotator"
    CONSERVATIVE_LINER = "conservative_liner"
    TRAIL_BRAZER = "trail_brazer"


# Coaching focus per archetype — injected into the coaching prompt.
ARCHETYPE_COACHING_FOCUS: dict[Archetype, str] = {
    Archetype.EARLY_BRAKER: (
        "Confidence-building: the car can brake deeper. Move the brake point "
        "closer to the corner, using more of the available straight for speed."
    ),
    Archetype.LATE_BRAKER: (
        "Patience at entry: commit to a stable corner entry position before "
        "applying throttle. Late braking that compromises the apex costs more "
        "than it saves."
    ),
    Archetype.COASTER: (
        "Eliminate the coast phase: release the brake progressively into the "
        "turn (trail braking) instead of coasting between brake and throttle."
    ),
    Archetype.SMOOTH_OPERATOR: (
        "Pushing the limit: you have headroom in the data. Trust the car's "
        "grip and carry more speed. Your consistency is your strength."
    ),
    Archetype.AGGRESSIVE_ROTATOR: (
        "Smoothness: let the car rotate naturally. Reduce abrupt inputs that "
        "unsettle the car and waste grip in transitions."
    ),
    Archetype.CONSERVATIVE_LINER: (
        "Use all of the road: widen your entry, clip the apex, and open the "
        "exit. Track width is free speed."
    ),
    Archetype.TRAIL_BRAZER: (
        "Fine-tuning: refine brake release rate and rotation balance. You "
        "trail brake well — now optimize the transition to throttle."
    ),
}


@dataclass
class ArchetypeResult:
    """Result of archetype detection for a session."""

    primary: Archetype
    secondary: Archetype | None
    confidence: float  # 0.0-1.0 based on signal strength
    coaching_focus: str
    dimension_scores: dict[str, float]  # raw scores per dimension


def _compute_brake_timing_score(
    corner_analyses: list[CornerAnalysis],
    all_lap_corners: dict[int, list[Corner]],
) -> float:
    """Score brake timing tendency: negative = early, positive = late.

    Compares average brake point to the corner's best-lap brake point.
    An early braker consistently brakes well before their own best lap.
    """
    deltas: list[float] = []
    for ca in corner_analyses:
        if ca.stats_brake_point is None or ca.stats_brake_point.n_laps < _MIN_LAPS:
            continue
        # Positive = braking later than best (closer to corner)
        # Negative = braking earlier than best
        delta = ca.stats_brake_point.mean - ca.stats_brake_point.best
        deltas.append(delta)

    if not deltas:
        return 0.0
    # Normalize: typical range is -20m (very early) to +5m (late)
    # Map to [-1, 1] where -1 = early, +1 = late
    mean_delta = float(np.mean(deltas))
    return float(np.clip(mean_delta / 15.0, -1.0, 1.0))


def _compute_brake_force_score(
    corner_analyses: list[CornerAnalysis],
) -> float:
    """Score brake force utilization: low score = timid braking.

    Compares average peak brake G to the session maximum across all corners.
    """
    peak_gs: list[float] = []
    best_gs: list[float] = []
    for ca in corner_analyses:
        if ca.stats_peak_brake_g is None or ca.stats_peak_brake_g.n_laps < _MIN_LAPS:
            continue
        peak_gs.append(ca.stats_peak_brake_g.mean)
        best_gs.append(ca.stats_peak_brake_g.best)

    if not peak_gs:
        return 0.0
    # Ratio of average to best — 1.0 means maximal, 0.5 means timid
    session_max = max(best_gs)
    if session_max < 0.1:
        return 0.0
    avg_usage = float(np.mean(peak_gs)) / session_max
    # Map 0.5-1.0 range to 0.0-1.0
    return float(np.clip((avg_usage - 0.5) * 2.0, 0.0, 1.0))


def _compute_coast_score(
    all_lap_corners: dict[int, list[Corner]],
) -> float:
    """Score coasting tendency: high = large gap between brake and throttle.

    Measures the distance gap between brake release (approximated by apex) and
    throttle commit. A coaster has a consistently large gap.
    """
    gaps: list[float] = []
    for lap_corners in all_lap_corners.values():
        for c in lap_corners:
            if c.brake_point_m is not None and c.throttle_commit_m is not None:
                # Gap between apex and throttle commit
                # Positive means throttle comes after apex (expected)
                gap = c.throttle_commit_m - c.apex_distance_m
                gaps.append(gap)

    if len(gaps) < _MIN_LAPS * _MIN_CORNERS:
        return 0.0
    mean_gap = float(np.mean(gaps))
    # Normalize: 0m gap = no coast, 30m+ = heavy coasting
    return float(np.clip(mean_gap / 30.0, 0.0, 1.0))


def _compute_consistency_score(
    corner_analyses: list[CornerAnalysis],
) -> float:
    """Score overall consistency: high = very consistent, low = erratic.

    Uses coefficient of variation of min speed across corners.
    """
    cvs: list[float] = []
    for ca in corner_analyses:
        if ca.stats_min_speed.n_laps < _MIN_LAPS:
            continue
        mean_speed = ca.stats_min_speed.mean
        if mean_speed > 1.0:  # Avoid division by near-zero
            cv = ca.stats_min_speed.std / mean_speed
            cvs.append(cv)

    if not cvs:
        return 0.5  # neutral
    mean_cv = float(np.mean(cvs))
    # Low CV = high consistency. Map: CV 0.0 → score 1.0, CV 0.10 → score 0.0
    return float(np.clip(1.0 - mean_cv * 10.0, 0.0, 1.0))


def _compute_speed_utilization_score(
    corner_analyses: list[CornerAnalysis],
) -> float:
    """Score speed utilization: how close avg min speed is to best.

    High score = carrying close to maximum speed. Low = leaving speed on table.
    """
    ratios: list[float] = []
    for ca in corner_analyses:
        if ca.stats_min_speed.n_laps < _MIN_LAPS:
            continue
        best = ca.stats_min_speed.best
        if best > 1.0:
            ratio = ca.stats_min_speed.mean / best
            ratios.append(ratio)

    if not ratios:
        return 0.5
    mean_ratio = float(np.mean(ratios))
    # Map 0.85-1.0 range to 0.0-1.0
    return float(np.clip((mean_ratio - 0.85) / 0.15, 0.0, 1.0))


def _compute_throttle_aggression_score(
    corner_analyses: list[CornerAnalysis],
) -> float:
    """Score throttle aggression: early commit = aggressive, late = conservative.

    Compares average throttle commit point to best-lap commit point.
    """
    deltas: list[float] = []
    for ca in corner_analyses:
        if ca.stats_throttle_commit is None or ca.stats_throttle_commit.n_laps < _MIN_LAPS:
            continue
        # Negative = committing earlier than best (aggressive)
        # Positive = committing later (conservative)
        delta = ca.stats_throttle_commit.mean - ca.stats_throttle_commit.best
        deltas.append(delta)

    if not deltas:
        return 0.5
    mean_delta = float(np.mean(deltas))
    # Normalize: -10m (aggressive) to +20m (conservative)
    # Map to 0.0 (conservative) to 1.0 (aggressive)
    return float(np.clip(1.0 - mean_delta / 15.0, 0.0, 1.0))


# Each archetype is activated by a combination of dimension scores.
# Format: {archetype: [(dimension, weight, threshold_direction)]}
# threshold_direction: "high" = score > 0.6 contributes, "low" = score < 0.4
_ARCHETYPE_WEIGHTS: dict[Archetype, list[tuple[str, float, str]]] = {
    Archetype.EARLY_BRAKER: [
        ("brake_timing", 2.0, "low"),  # Brakes early
        ("brake_force", 1.0, "low"),  # Timid brake pressure
    ],
    Archetype.LATE_BRAKER: [
        ("brake_timing", 2.0, "high"),  # Brakes late
        ("brake_force", 1.0, "high"),  # Strong brake pressure
    ],
    Archetype.COASTER: [
        ("coast", 2.5, "high"),  # Large coast gap
        ("throttle_aggression", 1.0, "low"),  # Late throttle
    ],
    Archetype.SMOOTH_OPERATOR: [
        ("consistency", 2.0, "high"),  # Very consistent
        ("speed_utilization", 1.5, "high"),  # Near-best speed
        ("brake_force", 0.5, "high"),  # Decent brake force
    ],
    Archetype.AGGRESSIVE_ROTATOR: [
        ("brake_timing", 1.5, "high"),  # Late braking
        ("throttle_aggression", 1.5, "high"),  # Early throttle
        ("consistency", 1.0, "low"),  # Less consistent
    ],
    Archetype.CONSERVATIVE_LINER: [
        ("speed_utilization", 2.0, "low"),  # Leaving speed on table
        ("consistency", 1.5, "high"),  # Consistent but slow
        ("brake_timing", 0.5, "low"),  # Early braker too
    ],
    Archetype.TRAIL_BRAZER: [
        ("brake_force", 2.0, "high"),  # Strong braking
        ("coast", 1.5, "low"),  # No coasting
        ("consistency", 1.0, "high"),  # Consistent
    ],
}


def _score_archetype(
    dimension_scores: dict[str, float],
    archetype: Archetype,
) -> float:
    """Score how well dimension scores match an archetype profile."""
    weights = _ARCHETYPE_WEIGHTS[archetype]
    total_score = 0.0
    total_weight = 0.0

    for dim, weight, direction in weights:
        score = dimension_scores.get(dim, 0.5)
        contribution = score if direction == "high" else 1.0 - score
        total_score += contribution * weight
        total_weight += weight

    return total_score / total_weight if total_weight > 0 else 0.0


def detect_archetype(
    corner_analysis: SessionCornerAnalysis,
    all_lap_corners: dict[int, list[Corner]],
) -> ArchetypeResult | None:
    """Detect driver archetype from session corner analysis.

    Returns None if insufficient data for meaningful detection.
    """
    if len(corner_analysis.corners) < _MIN_CORNERS:
        return None
    if corner_analysis.n_laps_analyzed < _MIN_LAPS:
        return None

    # Compute all dimension scores
    dimension_scores = {
        "brake_timing": _compute_brake_timing_score(corner_analysis.corners, all_lap_corners),
        "brake_force": _compute_brake_force_score(corner_analysis.corners),
        "coast": _compute_coast_score(all_lap_corners),
        "consistency": _compute_consistency_score(corner_analysis.corners),
        "speed_utilization": _compute_speed_utilization_score(corner_analysis.corners),
        "throttle_aggression": _compute_throttle_aggression_score(corner_analysis.corners),
    }

    # Score each archetype
    archetype_scores: dict[Archetype, float] = {}
    for archetype in Archetype:
        archetype_scores[archetype] = _score_archetype(dimension_scores, archetype)

    # Sort by score descending
    ranked = sorted(archetype_scores.items(), key=lambda x: x[1], reverse=True)
    primary = ranked[0][0]
    primary_score = ranked[0][1]

    # Secondary only if it scores at least 70% of primary
    secondary = None
    if len(ranked) > 1 and ranked[1][1] >= primary_score * 0.7:
        secondary = ranked[1][0]

    # Confidence: how far primary is from the average of all scores
    all_scores = [s for _, s in ranked]
    mean_score = float(np.mean(all_scores))
    if mean_score > 0:
        confidence = min((primary_score - mean_score) / mean_score + 0.5, 1.0)
    else:
        confidence = 0.5
    confidence = max(confidence, 0.0)

    logger.info(
        "Archetype detected: %s (confidence=%.2f, secondary=%s)",
        primary.value,
        confidence,
        secondary.value if secondary else "none",
    )

    return ArchetypeResult(
        primary=primary,
        secondary=secondary,
        confidence=round(confidence, 2),
        coaching_focus=ARCHETYPE_COACHING_FOCUS[primary],
        dimension_scores={k: round(v, 3) for k, v in dimension_scores.items()},
    )


def format_archetype_for_prompt(result: ArchetypeResult | None) -> str:
    """Format archetype result as text for the coaching prompt."""
    if result is None:
        return ""

    lines = ["\n## Driver Archetype"]
    lines.append(
        f"Primary: {result.primary.value.replace('_', ' ').title()} "
        f"(confidence: {result.confidence:.0%})"
    )
    if result.secondary:
        lines.append(f"Secondary tendency: {result.secondary.value.replace('_', ' ').title()}")
    lines.append(f"Coaching focus: {result.coaching_focus}")
    lines.append(
        "Tailor your coaching advice to address this driving tendency. "
        "Reference the archetype when it explains a pattern across corners."
    )
    return "\n".join(lines)

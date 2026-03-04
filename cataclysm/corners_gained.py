"""Corners Gained decomposition — gap to target broken down by corner.

Adapted from golf's "Strokes Gained" analytics.  Decomposes the difference
between the driver's current best lap and a target time into per-corner,
per-technique opportunities (braking, min speed, throttle, consistency).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from cataclysm.corner_analysis import CornerAnalysis, SessionCornerAnalysis

logger = logging.getLogger(__name__)

# Minimum data to produce a meaningful decomposition.
_MIN_CORNERS = 2
_MIN_LAPS = 4

# Conversion factor: mph speed deficit → approximate time cost per corner.
# Rough heuristic: 1 mph slower through a typical 50m corner ≈ 0.05s.
_MPH_TO_SEC_PER_CORNER = 0.05

# Brake point: 1m of brake point variance ≈ time cost at approach speed.
# Heuristic: at 100 mph (~44.7 m/s), 1m = 0.022s.
_BRAKE_M_TO_SEC = 0.022

# Throttle commit: 1m later commit ≈ cost at corner exit speed.
# Heuristic: at 60 mph (~26.8 m/s), 1m = 0.037s.
_THROTTLE_M_TO_SEC = 0.037


@dataclass
class CornerGainDetail:
    """Per-corner breakdown of time opportunity by technique category."""

    corner_number: int
    braking_gain_s: float
    min_speed_gain_s: float
    throttle_gain_s: float
    consistency_gain_s: float
    total_gain_s: float


@dataclass
class CornersGainedResult:
    """Full gap decomposition from current best to target."""

    target_lap_s: float
    current_best_s: float
    total_gap_s: float

    per_corner: list[CornerGainDetail]

    # Aggregated by category
    total_braking_s: float
    total_min_speed_s: float
    total_throttle_s: float
    total_consistency_s: float

    # Top opportunities for quick reference
    top_opportunities: list[tuple[int, str, float]] = field(default_factory=list)

    coaching_summary: str = ""


def _estimate_braking_gain(ca: CornerAnalysis) -> float:
    """Estimate braking-related time gain for one corner.

    Uses brake point std (meters) as the primary signal. Higher std =
    more inconsistency = more time left on the table.
    """
    if ca.stats_brake_point is None or ca.stats_brake_point.n_laps < _MIN_LAPS:
        return 0.0
    # Use time_value if available (more accurate).
    if ca.time_value is not None:
        return ca.time_value.brake_variance_time_cost_s
    # Fallback: heuristic from brake std.
    std = ca.stats_brake_point.std
    return std * _BRAKE_M_TO_SEC


def _estimate_min_speed_gain(ca: CornerAnalysis) -> float:
    """Estimate min-speed-related time gain for one corner.

    Gap between mean and best min speed across laps.
    """
    stats = ca.stats_min_speed
    if stats.n_laps < _MIN_LAPS:
        return 0.0
    # best = fastest min speed (highest value), so best > mean when driver
    # carried more speed on their best lap than average.
    speed_gap_mph = stats.best - stats.mean if stats.best > stats.mean else 0.0
    return speed_gap_mph * _MPH_TO_SEC_PER_CORNER


def _estimate_throttle_gain(ca: CornerAnalysis) -> float:
    """Estimate throttle-commit-related time gain for one corner."""
    if ca.stats_throttle_commit is None or ca.stats_throttle_commit.n_laps < _MIN_LAPS:
        return 0.0
    stats = ca.stats_throttle_commit
    # Gap between mean and best commit point (earlier is better).
    # best = min distance = earliest commit.
    gap_m = stats.mean - stats.best
    return max(gap_m, 0.0) * _THROTTLE_M_TO_SEC


def _estimate_consistency_gain(ca: CornerAnalysis) -> float:
    """Estimate consistency-related time gain for one corner.

    Uses the pre-computed recommendation gain which already accounts for
    variance-to-time conversion.
    """
    return max(ca.recommendation.gain_s, 0.0)


def compute_corners_gained(
    corner_analysis: SessionCornerAnalysis,
    target_lap_s: float,
    current_best_s: float,
) -> CornersGainedResult | None:
    """Decompose gap to target into per-corner, per-technique opportunities.

    Returns None if insufficient data.

    Parameters
    ----------
    corner_analysis : SessionCornerAnalysis
        Pre-computed corner analysis for the session.
    target_lap_s : float
        Target lap time in seconds (e.g., 100.0 for 1:40.0).
    current_best_s : float
        Driver's current best lap time in seconds.
    """
    if len(corner_analysis.corners) < _MIN_CORNERS:
        return None
    if corner_analysis.n_laps_analyzed < _MIN_LAPS:
        return None

    total_gap = current_best_s - target_lap_s
    if total_gap <= 0:
        # Already at or below target — no gap to decompose.
        return CornersGainedResult(
            target_lap_s=target_lap_s,
            current_best_s=current_best_s,
            total_gap_s=0.0,
            per_corner=[],
            total_braking_s=0.0,
            total_min_speed_s=0.0,
            total_throttle_s=0.0,
            total_consistency_s=0.0,
            top_opportunities=[],
            coaching_summary="You're already at or below target!",
        )

    # Compute raw per-corner gains.
    per_corner: list[CornerGainDetail] = []
    for ca in corner_analysis.corners:
        braking = _estimate_braking_gain(ca)
        speed = _estimate_min_speed_gain(ca)
        throttle = _estimate_throttle_gain(ca)
        consistency = _estimate_consistency_gain(ca)
        total = braking + speed + throttle + consistency
        per_corner.append(
            CornerGainDetail(
                corner_number=ca.corner_number,
                braking_gain_s=round(braking, 3),
                min_speed_gain_s=round(speed, 3),
                throttle_gain_s=round(throttle, 3),
                consistency_gain_s=round(consistency, 3),
                total_gain_s=round(total, 3),
            )
        )

    # Aggregate by category.
    raw_braking = sum(c.braking_gain_s for c in per_corner)
    raw_speed = sum(c.min_speed_gain_s for c in per_corner)
    raw_throttle = sum(c.throttle_gain_s for c in per_corner)
    raw_consistency = sum(c.consistency_gain_s for c in per_corner)
    raw_total = raw_braking + raw_speed + raw_throttle + raw_consistency

    # Scale gains proportionally so they sum to the actual gap.
    # Allows both upward and downward scaling to fully attribute the gap.
    scale = total_gap / raw_total if raw_total > 0 else 0.0

    total_braking = round(raw_braking * scale, 3)
    total_speed = round(raw_speed * scale, 3)
    total_throttle = round(raw_throttle * scale, 3)
    total_consistency = round(raw_consistency * scale, 3)

    # Scale per-corner values and recompute totals from rounded components.
    for c in per_corner:
        c.braking_gain_s = round(c.braking_gain_s * scale, 3)
        c.min_speed_gain_s = round(c.min_speed_gain_s * scale, 3)
        c.throttle_gain_s = round(c.throttle_gain_s * scale, 3)
        c.consistency_gain_s = round(c.consistency_gain_s * scale, 3)
        c.total_gain_s = round(
            c.braking_gain_s + c.min_speed_gain_s + c.throttle_gain_s + c.consistency_gain_s, 3
        )

    # Top opportunities: largest per-corner gains.
    sorted_corners = sorted(per_corner, key=lambda c: c.total_gain_s, reverse=True)
    top_ops: list[tuple[int, str, float]] = []
    for c in sorted_corners[:3]:
        if c.total_gain_s <= 0:
            break
        # Identify dominant technique category.
        cats = {
            "braking": c.braking_gain_s,
            "min speed": c.min_speed_gain_s,
            "throttle": c.throttle_gain_s,
            "consistency": c.consistency_gain_s,
        }
        dominant = max(cats, key=cats.get)  # type: ignore[arg-type]
        top_ops.append((c.corner_number, dominant, c.total_gain_s))

    # Coaching summary.
    if top_ops:
        parts = [f"T{cn} {cat} ({gain:.2f}s)" for cn, cat, gain in top_ops]
        target_min = int(target_lap_s // 60)
        target_sec = target_lap_s % 60
        summary = f"To break {target_min}:{target_sec:05.2f}: {', '.join(parts)}"
    else:
        summary = "Insufficient data to identify specific opportunities."

    logger.info(
        "Corners Gained: gap=%.2fs, top opportunity=T%d (%.2fs)",
        total_gap,
        top_ops[0][0] if top_ops else 0,
        top_ops[0][2] if top_ops else 0.0,
    )

    return CornersGainedResult(
        target_lap_s=target_lap_s,
        current_best_s=current_best_s,
        total_gap_s=round(total_gap, 3),
        per_corner=per_corner,
        total_braking_s=total_braking,
        total_min_speed_s=total_speed,
        total_throttle_s=total_throttle,
        total_consistency_s=total_consistency,
        top_opportunities=top_ops,
        coaching_summary=summary,
    )


def format_corners_gained_for_prompt(result: CornersGainedResult | None) -> str:
    """Format corners gained result for injection into the coaching prompt."""
    if result is None or result.total_gap_s <= 0:
        return ""

    lines = ["\n## Corners Gained Analysis"]
    lines.append(
        f"Target: {result.target_lap_s:.2f}s | Current best: "
        f"{result.current_best_s:.2f}s | Gap: {result.total_gap_s:.2f}s"
    )
    lines.append(
        f"Braking: {result.total_braking_s:.2f}s | "
        f"Min speed: {result.total_min_speed_s:.2f}s | "
        f"Throttle: {result.total_throttle_s:.2f}s | "
        f"Consistency: {result.total_consistency_s:.2f}s"
    )

    if result.top_opportunities:
        lines.append("Top opportunities:")
        for cn, cat, gain in result.top_opportunities:
            lines.append(f"  T{cn}: {cat} ({gain:.2f}s)")

    lines.append(
        "Use these Corners Gained breakdowns to prioritize coaching. "
        "Address the highest-gain corners first — they offer the fastest "
        "path to the target lap time."
    )
    return "\n".join(lines)

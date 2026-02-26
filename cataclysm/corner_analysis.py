"""Pre-computed per-corner statistical analysis for coaching prompts.

Aggregates data from corners, gains, consistency, and landmarks into
structured facts that the LLM can narrate without doing its own arithmetic.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from cataclysm.corners import Corner, classify_corner_type
from cataclysm.gains import GainEstimate
from cataclysm.landmarks import (
    Landmark,
    LandmarkReference,
    _BRAKE_PREFERRED_TYPES,
    find_nearest_landmark,
)

MPS_TO_MPH = 2.23694


@dataclass
class CornerStats:
    """Aggregated statistics for a single KPI across laps."""

    best: float
    mean: float
    std: float
    value_range: float  # max - min
    best_lap: int
    n_laps: int


@dataclass
class CornerCorrelation:
    """Pearson correlation between two KPI series for a corner."""

    kpi_x: str
    kpi_y: str
    r: float
    strength: str  # "strong", "moderate", "weak"
    n_points: int


@dataclass
class CornerRecommendation:
    """Actionable targets derived from best-lap data + landmarks."""

    target_brake_m: float | None
    target_brake_landmark: LandmarkReference | None
    target_min_speed_mph: float
    gain_s: float
    corner_type: str  # "slow", "medium", "fast"


@dataclass
class TimeValue:
    """Time-domain context for a corner: how much does variance cost?"""

    approach_speed_mph: float
    time_per_meter_ms: float  # milliseconds per meter at approach speed
    brake_variance_time_cost_s: float  # std_brake * time_per_meter


@dataclass
class CornerAnalysis:
    """Full pre-computed analysis for one corner."""

    corner_number: int
    n_laps: int
    stats_min_speed: CornerStats
    stats_brake_point: CornerStats | None
    stats_peak_brake_g: CornerStats | None
    stats_throttle_commit: CornerStats | None
    apex_distribution: dict[str, int]  # {"early": 2, "mid": 5, "late": 1}
    recommendation: CornerRecommendation
    time_value: TimeValue | None
    correlations: list[CornerCorrelation] = field(default_factory=list)


@dataclass
class SessionCornerAnalysis:
    """All corners sorted by gain opportunity, with session-level totals."""

    corners: list[CornerAnalysis]
    best_lap: int
    total_consistency_gain_s: float
    n_laps_analyzed: int


def _compute_kpi_stats(
    values: list[float],
    laps: list[int],
) -> CornerStats:
    """Compute aggregated statistics for a list of KPI values."""
    arr = np.array(values)
    best_val = float(np.min(arr))
    best_idx = int(np.argmin(arr))
    return CornerStats(
        best=best_val,
        mean=float(np.mean(arr)),
        std=float(np.std(arr)),
        value_range=float(np.max(arr) - np.min(arr)),
        best_lap=laps[best_idx],
        n_laps=len(values),
    )


def _compute_kpi_stats_max(
    values: list[float],
    laps: list[int],
) -> CornerStats:
    """Compute stats where 'best' = maximum (e.g., min_speed, peak brake g magnitude)."""
    arr = np.array(values)
    best_val = float(np.max(arr))
    best_idx = int(np.argmax(arr))
    return CornerStats(
        best=best_val,
        mean=float(np.mean(arr)),
        std=float(np.std(arr)),
        value_range=float(np.max(arr) - np.min(arr)),
        best_lap=laps[best_idx],
        n_laps=len(values),
    )


def _correlation_strength(r: float) -> str:
    """Classify Pearson r magnitude."""
    abs_r = abs(r)
    if abs_r >= 0.7:
        return "strong"
    if abs_r >= 0.4:
        return "moderate"
    return "weak"


def _compute_correlations(
    brake_points: list[float],
    min_speeds: list[float],
    brake_laps: list[int],
    speed_laps: list[int],
) -> list[CornerCorrelation]:
    """Compute Pearson correlations between paired KPI series (>=4 points)."""
    correlations: list[CornerCorrelation] = []

    # Build aligned arrays for brake_point vs min_speed
    bp_map = dict(zip(brake_laps, brake_points, strict=False))
    sp_map = dict(zip(speed_laps, min_speeds, strict=False))
    common_laps = sorted(set(bp_map) & set(sp_map))

    if len(common_laps) >= 4:
        bp_arr = np.array([bp_map[lap] for lap in common_laps])
        sp_arr = np.array([sp_map[lap] for lap in common_laps])

        # brake_point vs min_speed
        if np.std(bp_arr) > 1e-9 and np.std(sp_arr) > 1e-9:
            r = float(np.corrcoef(bp_arr, sp_arr)[0, 1])
            correlations.append(
                CornerCorrelation(
                    kpi_x="brake_point",
                    kpi_y="min_speed",
                    r=round(r, 3),
                    strength=_correlation_strength(r),
                    n_points=len(common_laps),
                )
            )

    return correlations


def _find_gain_for_corner(
    corner_number: int,
    gains: GainEstimate | None,
) -> float:
    """Look up consistency gain for a corner from the gains estimate."""
    if gains is None:
        return 0.0
    for sg in gains.consistency.segment_gains:
        if sg.segment.is_corner and sg.segment.name == f"T{corner_number}":
            return sg.gain_s
    return 0.0


def compute_corner_analysis(
    all_lap_corners: dict[int, list[Corner]],
    gains: GainEstimate | None,
    consistency_entries: list[object] | None,
    landmarks: list[Landmark] | None,
    best_lap: int,
) -> SessionCornerAnalysis:
    """Aggregate existing data into a structured per-corner analysis.

    Parameters
    ----------
    all_lap_corners:
        Per-lap corner KPIs from the processing pipeline.
    gains:
        Gain estimate (consistency/composite/theoretical) or None.
    consistency_entries:
        Corner consistency entries (unused directly — we recompute from
        raw corners for richer stats). Kept for future enrichment.
    landmarks:
        Track landmarks for resolving brake points to visual references.
    best_lap:
        The fastest lap number for target value extraction.

    Returns
    -------
    SessionCornerAnalysis with corners sorted by gain (descending).
    """
    if not all_lap_corners:
        return SessionCornerAnalysis(
            corners=[],
            best_lap=best_lap,
            total_consistency_gain_s=gains.consistency.total_gain_s if gains else 0.0,
            n_laps_analyzed=0,
        )

    # Determine corner numbers from all laps
    all_numbers: set[int] = set()
    for corners in all_lap_corners.values():
        for c in corners:
            all_numbers.add(c.number)

    lap_numbers = sorted(all_lap_corners.keys())
    n_laps = len(lap_numbers)

    analyses: list[CornerAnalysis] = []

    for cn in sorted(all_numbers):
        # Gather per-lap data for this corner
        min_speeds_mph: list[float] = []
        brake_points_m: list[float] = []
        peak_brake_gs: list[float] = []
        throttle_commits_m: list[float] = []
        apex_types: list[str] = []
        speed_laps: list[int] = []
        brake_laps: list[int] = []
        peak_g_laps: list[int] = []
        throttle_laps: list[int] = []

        best_lap_corner: Corner | None = None

        for lap_num in lap_numbers:
            corners = all_lap_corners[lap_num]
            match = [c for c in corners if c.number == cn]
            if not match:
                continue
            corner = match[0]

            min_speeds_mph.append(corner.min_speed_mps * MPS_TO_MPH)
            speed_laps.append(lap_num)
            apex_types.append(corner.apex_type)

            if corner.brake_point_m is not None:
                brake_points_m.append(corner.brake_point_m)
                brake_laps.append(lap_num)

            if corner.peak_brake_g is not None:
                peak_brake_gs.append(abs(corner.peak_brake_g))
                peak_g_laps.append(lap_num)

            if corner.throttle_commit_m is not None:
                throttle_commits_m.append(corner.throttle_commit_m)
                throttle_laps.append(lap_num)

            if lap_num == best_lap:
                best_lap_corner = corner

        if not min_speeds_mph:
            continue

        # If best lap didn't have this corner, use the first available
        if best_lap_corner is None:
            first_lap = speed_laps[0]
            for c in all_lap_corners[first_lap]:
                if c.number == cn:
                    best_lap_corner = c
                    break

        assert best_lap_corner is not None

        # Stats
        stats_min_speed = _compute_kpi_stats_max(min_speeds_mph, speed_laps)
        stats_brake = (
            _compute_kpi_stats(brake_points_m, brake_laps) if brake_points_m else None
        )
        stats_peak_g = (
            _compute_kpi_stats_max(peak_brake_gs, peak_g_laps) if peak_brake_gs else None
        )
        stats_throttle = (
            _compute_kpi_stats(throttle_commits_m, throttle_laps) if throttle_commits_m else None
        )

        # Apex distribution
        apex_dist = dict(Counter(apex_types))

        # Corner type from best lap
        corner_type = classify_corner_type(best_lap_corner)

        # Gain
        gain_s = _find_gain_for_corner(cn, gains)

        # Landmark resolution for brake target
        target_brake_landmark: LandmarkReference | None = None
        if best_lap_corner.brake_point_m is not None and landmarks:
            target_brake_landmark = find_nearest_landmark(
                best_lap_corner.brake_point_m,
                landmarks,
                preferred_types=_BRAKE_PREFERRED_TYPES,
            )

        # Recommendation
        recommendation = CornerRecommendation(
            target_brake_m=best_lap_corner.brake_point_m,
            target_brake_landmark=target_brake_landmark,
            target_min_speed_mph=round(best_lap_corner.min_speed_mps * MPS_TO_MPH, 1),
            gain_s=gain_s,
            corner_type=corner_type,
        )

        # Time value: estimate approach speed via kinematics
        time_value: TimeValue | None = None
        if (
            best_lap_corner.brake_point_m is not None
            and best_lap_corner.peak_brake_g is not None
            and best_lap_corner.entry_distance_m > best_lap_corner.brake_point_m
        ):
            brake_dist = best_lap_corner.entry_distance_m - best_lap_corner.brake_point_m
            decel_mps2 = abs(best_lap_corner.peak_brake_g) * 9.81
            v_apex = best_lap_corner.min_speed_mps
            approach_speed_mps = (v_apex**2 + 2 * decel_mps2 * max(brake_dist, 0)) ** 0.5
            approach_speed_mph = approach_speed_mps * MPS_TO_MPH

            if approach_speed_mps > 0.1:
                time_per_meter_s = 1.0 / approach_speed_mps
                time_per_meter_ms = time_per_meter_s * 1000.0

                brake_std = stats_brake.std if stats_brake is not None else 0.0
                brake_variance_cost = brake_std * time_per_meter_s

                time_value = TimeValue(
                    approach_speed_mph=round(approach_speed_mph, 1),
                    time_per_meter_ms=round(time_per_meter_ms, 1),
                    brake_variance_time_cost_s=round(brake_variance_cost, 3),
                )

        # Correlations (need >= 4 data points)
        correlations = _compute_correlations(
            brake_points_m, min_speeds_mph, brake_laps, speed_laps
        )

        analyses.append(
            CornerAnalysis(
                corner_number=cn,
                n_laps=len(speed_laps),
                stats_min_speed=stats_min_speed,
                stats_brake_point=stats_brake,
                stats_peak_brake_g=stats_peak_g,
                stats_throttle_commit=stats_throttle,
                apex_distribution=apex_dist,
                recommendation=recommendation,
                time_value=time_value,
                correlations=correlations,
            )
        )

    # Sort by gain descending; break ties by corner number
    analyses.sort(key=lambda a: (-a.recommendation.gain_s, a.corner_number))

    return SessionCornerAnalysis(
        corners=analyses,
        best_lap=best_lap,
        total_consistency_gain_s=gains.consistency.total_gain_s if gains else 0.0,
        n_laps_analyzed=n_laps,
    )

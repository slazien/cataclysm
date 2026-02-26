"""GPS quality assessment: session-level noise detection and quality grading.

Computes 6 metrics (accuracy p90, satellite p10, lap distance CV, speed spikes,
heading jitter, lateral scatter), scores each via piecewise linear interpolation,
and produces a weighted overall score with letter grade (A-F).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from cataclysm.engine import LapSummary, ProcessedSession

# ---------------------------------------------------------------------------
# Breakpoint tables (value, score) for piecewise linear interpolation.
# Each list is sorted by the value axis; the score axis can be non-monotonic.
# ---------------------------------------------------------------------------

# Metric 1: Accuracy p90 (lower is better)
_ACCURACY_BP: list[tuple[float, float]] = [
    (0.5, 100.0),
    (1.0, 80.0),
    (1.5, 50.0),
    (2.0, 10.0),
]

# Metric 2: Satellite p10 (higher is better)
_SATELLITE_BP: list[tuple[float, float]] = [
    (6.0, 20.0),
    (8.0, 60.0),
    (10.0, 80.0),
    (15.0, 100.0),
]

# Metric 3: Lap distance CV % (lower is better)
_LAP_DISTANCE_CV_BP: list[tuple[float, float]] = [
    (0.5, 100.0),
    (1.0, 80.0),
    (2.0, 50.0),
    (4.0, 10.0),
    (6.0, 0.0),
]

# Metric 4: Speed spikes per km (lower is better)
_SPEED_SPIKE_BP: list[tuple[float, float]] = [
    (0.0, 100.0),
    (1.0, 80.0),
    (5.0, 50.0),
    (20.0, 10.0),
    (50.0, 0.0),
]

# Metric 5: Heading jitter std on straights (lower is better)
_HEADING_JITTER_BP: list[tuple[float, float]] = [
    (0.05, 100.0),
    (0.15, 80.0),
    (0.30, 50.0),
    (0.60, 0.0),
]

# Metric 6: Lateral scatter p90 in meters (lower is better)
_LATERAL_SCATTER_BP: list[tuple[float, float]] = [
    (0.3, 100.0),
    (0.6, 80.0),
    (1.0, 50.0),
    (2.0, 0.0),
]

# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

_WEIGHT_ACCURACY = 0.30
_WEIGHT_SATELLITE = 0.15
_WEIGHT_LAP_DISTANCE_CV = 0.25
_WEIGHT_SPEED_SPIKES = 0.15
_WEIGHT_HEADING_JITTER = 0.10
_WEIGHT_LATERAL_SCATTER = 0.05

# ---------------------------------------------------------------------------
# Grade thresholds
# ---------------------------------------------------------------------------

_GRADE_A_MIN = 90.0
_GRADE_B_MIN = 75.0
_GRADE_C_MIN = 60.0
_GRADE_D_MIN = 40.0
_USABLE_THRESHOLD = 40.0

# Speed spike detection: 3g implied acceleration is physically implausible
_SPIKE_ACCEL_THRESHOLD_MPS2 = 3.0 * 9.81

# Heading rate below this threshold counts as "straight" (deg/m)
_STRAIGHT_HEADING_RATE = 0.5

# Minimum straight fraction to compute heading jitter
_MIN_STRAIGHT_FRACTION = 0.15


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AccuracyStats:
    """GPS accuracy statistics."""

    p50: float
    p90: float
    score: float


@dataclass
class SatelliteStats:
    """Satellite count statistics."""

    p10: float
    p50: float
    score: float


@dataclass
class LapDistanceConsistency:
    """Lap distance coefficient of variation."""

    cv_percent: float
    score: float
    n_laps: int


@dataclass
class SpeedSpikeStats:
    """Speed spike detection statistics."""

    spikes_per_km: float
    total_spikes: int
    total_distance_km: float
    score: float


@dataclass
class HeadingJitterStats:
    """Heading jitter on straights."""

    jitter_std: float
    straight_fraction: float
    score: float


@dataclass
class LateralScatterStats:
    """Lateral scatter from smoothed path."""

    scatter_p90: float
    score: float


@dataclass
class GPSQualityReport:
    """Complete GPS quality assessment for a session."""

    overall_score: float
    grade: str  # "A", "B", "C", "D", "F"
    is_usable: bool
    accuracy: AccuracyStats
    satellites: SatelliteStats
    lap_distance_cv: LapDistanceConsistency | None
    speed_spikes: SpeedSpikeStats
    heading_jitter: HeadingJitterStats | None
    lateral_scatter: LateralScatterStats
    metric_weights: dict[str, float]  # actual weights used (after redistribution)


# ---------------------------------------------------------------------------
# Piecewise linear scoring
# ---------------------------------------------------------------------------


def _piecewise_linear_score(
    value: float,
    breakpoints: list[tuple[float, float]],
) -> float:
    """Score a value via piecewise linear interpolation between breakpoints.

    Breakpoints are ``(value, score)`` pairs, sorted by value.
    Values outside the range are clamped to the nearest endpoint's score.
    """
    if not breakpoints:
        return 0.0

    bp = sorted(breakpoints, key=lambda x: x[0])

    if value <= bp[0][0]:
        return bp[0][1]
    if value >= bp[-1][0]:
        return bp[-1][1]

    for i in range(len(bp) - 1):
        v0, s0 = bp[i]
        v1, s1 = bp[i + 1]
        if v0 <= value <= v1:
            t = (value - v0) / (v1 - v0) if v1 != v0 else 0.0
            return s0 + t * (s1 - s0)

    return bp[-1][1]  # pragma: no cover


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def _compute_accuracy_stats(data: pd.DataFrame) -> AccuracyStats:
    """Compute GPS accuracy p50/p90 from the parsed DataFrame."""
    if "accuracy_m" not in data.columns or data["accuracy_m"].dropna().empty:
        return AccuracyStats(p50=0.0, p90=0.0, score=100.0)

    acc = data["accuracy_m"].dropna().to_numpy()
    p50 = float(np.percentile(acc, 50))
    p90 = float(np.percentile(acc, 90))
    score = _piecewise_linear_score(p90, _ACCURACY_BP)
    return AccuracyStats(p50=round(p50, 3), p90=round(p90, 3), score=round(score, 1))


def _compute_satellite_stats(data: pd.DataFrame) -> SatelliteStats:
    """Compute satellite count p10/p50 from the parsed DataFrame."""
    if "satellites" not in data.columns or data["satellites"].dropna().empty:
        return SatelliteStats(p10=0.0, p50=0.0, score=0.0)

    sats = data["satellites"].dropna().to_numpy()
    p10 = float(np.percentile(sats, 10))
    p50 = float(np.percentile(sats, 50))
    score = _piecewise_linear_score(p10, _SATELLITE_BP)
    return SatelliteStats(p10=round(p10, 1), p50=round(p50, 1), score=round(score, 1))


def _compute_lap_distance_consistency(
    summaries: list[LapSummary],
    anomalous_laps: set[int],
) -> LapDistanceConsistency | None:
    """Compute lap distance coefficient of variation.

    Returns None if fewer than 3 clean laps (weight gets redistributed).
    """
    clean = [s for s in summaries if s.lap_number not in anomalous_laps]
    if len(clean) < 3:
        return None

    distances = np.array([s.lap_distance_m for s in clean])
    mean_dist = float(np.mean(distances))
    if mean_dist <= 0:
        return None

    cv_pct = float(np.std(distances) / mean_dist * 100)
    score = _piecewise_linear_score(cv_pct, _LAP_DISTANCE_CV_BP)
    return LapDistanceConsistency(
        cv_percent=round(cv_pct, 3),
        score=round(score, 1),
        n_laps=len(clean),
    )


def _compute_speed_spikes(
    resampled_laps: dict[int, pd.DataFrame],
    coaching_laps: list[int],
) -> SpeedSpikeStats:
    """Detect speed spikes implying >3g acceleration (GPS noise artefact)."""
    total_spikes = 0
    total_distance_m = 0.0

    laps_to_check = coaching_laps if coaching_laps else list(resampled_laps.keys())

    for lap_num in laps_to_check:
        if lap_num not in resampled_laps:
            continue
        df = resampled_laps[lap_num]
        if len(df) < 2:
            continue

        speed = df["speed_mps"].to_numpy()
        distance = df["lap_distance_m"].to_numpy()
        time_arr = df["lap_time_s"].to_numpy()

        total_distance_m += float(distance[-1]) if len(distance) > 0 else 0.0

        dt = np.diff(time_arr)
        dv = np.diff(speed)
        valid = dt > 0
        accel = np.zeros_like(dv)
        accel[valid] = np.abs(dv[valid] / dt[valid])
        total_spikes += int(np.sum(accel > _SPIKE_ACCEL_THRESHOLD_MPS2))

    total_distance_km = total_distance_m / 1000.0
    spikes_per_km = total_spikes / total_distance_km if total_distance_km > 0 else 0.0
    score = _piecewise_linear_score(spikes_per_km, _SPEED_SPIKE_BP)

    return SpeedSpikeStats(
        spikes_per_km=round(spikes_per_km, 2),
        total_spikes=total_spikes,
        total_distance_km=round(total_distance_km, 3),
        score=round(score, 1),
    )


def _compute_heading_jitter(
    best_lap_df: pd.DataFrame,
) -> HeadingJitterStats | None:
    """Compute heading rate std on straights.

    Returns None if straight fraction is < 15% (weight gets redistributed).
    """
    if "heading_deg" not in best_lap_df.columns or len(best_lap_df) < 20:
        return None

    heading = best_lap_df["heading_deg"].to_numpy()
    distance = best_lap_df["lap_distance_m"].to_numpy()

    heading_rad = np.radians(heading)
    heading_unwrapped = np.unwrap(heading_rad)
    dd = np.diff(distance)
    dh = np.abs(np.diff(heading_unwrapped))

    valid = dd > 0
    heading_rate = np.zeros_like(dd)
    heading_rate[valid] = np.degrees(dh[valid]) / dd[valid]

    is_straight = heading_rate < _STRAIGHT_HEADING_RATE
    straight_fraction = float(np.mean(is_straight))

    if straight_fraction < _MIN_STRAIGHT_FRACTION:
        return None

    straight_rates = heading_rate[is_straight]
    if len(straight_rates) < 10:
        return None

    jitter = float(np.std(straight_rates))
    score = _piecewise_linear_score(jitter, _HEADING_JITTER_BP)

    return HeadingJitterStats(
        jitter_std=round(jitter, 4),
        straight_fraction=round(straight_fraction, 3),
        score=round(score, 1),
    )


def _compute_lateral_scatter(
    resampled_laps: dict[int, pd.DataFrame],
    coaching_laps: list[int],
) -> LateralScatterStats:
    """Compute perpendicular distance from the mean lap trace (smoothed path).

    Uses mean lat/lon across coaching laps, then measures how far individual
    lap traces deviate laterally.
    """
    laps_to_use = coaching_laps if coaching_laps else list(resampled_laps.keys())
    laps_to_use = [n for n in laps_to_use if n in resampled_laps]

    if len(laps_to_use) < 2:
        return LateralScatterStats(scatter_p90=0.0, score=100.0)

    min_len = min(len(resampled_laps[n]) for n in laps_to_use)
    if min_len < 10:
        return LateralScatterStats(scatter_p90=0.0, score=100.0)

    lats = np.array([resampled_laps[n]["lat"].to_numpy()[:min_len] for n in laps_to_use])
    lons = np.array([resampled_laps[n]["lon"].to_numpy()[:min_len] for n in laps_to_use])

    mean_lat = np.mean(lats, axis=0)
    mean_lon = np.mean(lons, axis=0)

    # Approximate lat/lon → meters conversion
    cos_lat = np.cos(np.radians(float(np.mean(mean_lat))))
    all_deviations: list[float] = []
    for i in range(len(laps_to_use)):
        dlat_m = (lats[i] - mean_lat) * 111000.0
        dlon_m = (lons[i] - mean_lon) * 111000.0 * cos_lat
        dist = np.sqrt(dlat_m**2 + dlon_m**2)
        all_deviations.extend(dist.tolist())

    if not all_deviations:
        return LateralScatterStats(scatter_p90=0.0, score=100.0)

    p90 = float(np.percentile(all_deviations, 90))
    score = _piecewise_linear_score(p90, _LATERAL_SCATTER_BP)

    return LateralScatterStats(scatter_p90=round(p90, 3), score=round(score, 1))


# ---------------------------------------------------------------------------
# Grade computation
# ---------------------------------------------------------------------------


def _compute_grade(score: float) -> str:
    """Convert a 0-100 score to a letter grade."""
    if score >= _GRADE_A_MIN:
        return "A"
    if score >= _GRADE_B_MIN:
        return "B"
    if score >= _GRADE_C_MIN:
        return "C"
    if score >= _GRADE_D_MIN:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def assess_gps_quality(
    parsed_data: pd.DataFrame,
    processed: ProcessedSession,
    anomalous_laps: set[int],
) -> GPSQualityReport:
    """Assess GPS quality for a session.

    Computes 6 metrics, applies weights (redistributing when metrics are
    unavailable), and produces a letter grade (A-F).

    Parameters
    ----------
    parsed_data:
        Raw DataFrame from ``ParsedSession.data``.
    processed:
        ``ProcessedSession`` with resampled laps and summaries.
    anomalous_laps:
        Set of lap numbers flagged as anomalous.

    Returns
    -------
    GPSQualityReport with overall score, grade, and per-metric details.
    """
    summaries = processed.lap_summaries
    resampled_laps = processed.resampled_laps
    best_lap_df = resampled_laps[processed.best_lap]

    # Derive coaching laps (non-anomalous, non-in/out)
    all_lap_nums = sorted(resampled_laps.keys())
    in_out: set[int] = set()
    if len(all_lap_nums) >= 2:
        in_out = {all_lap_nums[0], all_lap_nums[-1]}
    coaching_laps = [n for n in all_lap_nums if n not in anomalous_laps and n not in in_out]

    # Compute each metric
    accuracy = _compute_accuracy_stats(parsed_data)
    satellites = _compute_satellite_stats(parsed_data)
    lap_distance_cv = _compute_lap_distance_consistency(summaries, anomalous_laps)
    speed_spikes = _compute_speed_spikes(resampled_laps, coaching_laps)
    heading_jitter = _compute_heading_jitter(best_lap_df)
    lateral_scatter = _compute_lateral_scatter(resampled_laps, coaching_laps)

    # Build weight map and redistribute for unavailable metrics
    weights: dict[str, float] = {
        "accuracy": _WEIGHT_ACCURACY,
        "satellites": _WEIGHT_SATELLITE,
        "lap_distance_cv": _WEIGHT_LAP_DISTANCE_CV,
        "speed_spikes": _WEIGHT_SPEED_SPIKES,
        "heading_jitter": _WEIGHT_HEADING_JITTER,
        "lateral_scatter": _WEIGHT_LATERAL_SCATTER,
    }

    scores: dict[str, float] = {
        "accuracy": accuracy.score,
        "satellites": satellites.score,
        "speed_spikes": speed_spikes.score,
        "lateral_scatter": lateral_scatter.score,
    }

    # Redistribute lap_distance_cv weight if unavailable (< 3 laps)
    if lap_distance_cv is not None:
        scores["lap_distance_cv"] = lap_distance_cv.score
    else:
        redistribute = weights.pop("lap_distance_cv")
        weights["accuracy"] += redistribute * 0.67
        weights["satellites"] += redistribute * 0.33

    # Redistribute heading_jitter weight if unavailable (< 15% straights)
    if heading_jitter is not None:
        scores["heading_jitter"] = heading_jitter.score
    else:
        redistribute = weights.pop("heading_jitter")
        weights["accuracy"] += redistribute

    # Compute weighted overall score
    total_weight = sum(weights[k] for k in scores)
    if total_weight > 0:
        overall = sum(scores[k] * weights[k] for k in scores) / total_weight
    else:
        overall = 0.0

    overall = round(overall, 1)
    grade = _compute_grade(overall)

    return GPSQualityReport(
        overall_score=overall,
        grade=grade,
        is_usable=overall >= _USABLE_THRESHOLD,
        accuracy=accuracy,
        satellites=satellites,
        lap_distance_cv=lap_distance_cv,
        speed_spikes=speed_spikes,
        heading_jitter=heading_jitter,
        lateral_scatter=lateral_scatter,
        metric_weights={k: round(v, 3) for k, v in weights.items() if k in scores},
    )

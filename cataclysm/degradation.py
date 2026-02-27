"""Brake fade and tire degradation detection across a session.

Analyzes per-corner metrics (peak brake G, min speed) across laps to detect
systematic degradation trends using linear regression.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cataclysm.corners import Corner

# Minimum laps required for meaningful regression
MIN_LAPS = 4

# Slope thresholds (per lap, must be negative = degrading)
BRAKE_SLOPE_THRESHOLD = -0.01  # G per lap
TIRE_SPEED_SLOPE_THRESHOLD = -0.1  # m/s per lap

# Minimum R² for the trend to be considered real
R_SQUARED_MIN = 0.5


@dataclass
class DegradationEvent:
    """A detected degradation event for a specific corner and metric."""

    corner_number: int
    metric: str  # "brake_fade" | "tire_degradation"
    start_lap: int
    end_lap: int
    slope: float
    r_squared: float
    severity: str  # "mild" | "moderate" | "severe"
    description: str
    values: list[float]
    lap_numbers: list[int]


@dataclass
class DegradationAnalysis:
    """Results of degradation analysis across the session."""

    events: list[DegradationEvent] = field(default_factory=list)
    has_brake_fade: bool = False
    has_tire_degradation: bool = False


def _classify_severity(slope: float, threshold: float) -> str:
    """Classify severity based on how many times the slope exceeds the threshold.

    - mild: 1-2x threshold
    - moderate: 2-3x threshold
    - severe: 3x+ threshold
    """
    ratio = abs(slope) / abs(threshold)
    if ratio >= 3.0:
        return "severe"
    if ratio >= 2.0:
        return "moderate"
    return "mild"


def _compute_r_squared(y: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute R² (coefficient of determination) for a linear fit.

    Returns 0.0 if SS_tot is zero (all values identical).
    """
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    if ss_tot == 0.0:
        return 0.0
    return 1.0 - ss_res / ss_tot


def detect_degradation(
    all_lap_corners: dict[int, list[Corner]],
    anomalous_laps: set[int],
) -> DegradationAnalysis:
    """Detect brake fade and tire degradation across a session.

    For each corner, collects peak_brake_g and min_speed_mps across clean laps
    (excluding anomalous laps), fits a linear regression, and flags negative
    trends that exceed thresholds with sufficient R².

    Parameters
    ----------
    all_lap_corners:
        Corner KPIs per lap, keyed by lap number.
    anomalous_laps:
        Lap numbers to exclude (pit stops, red flags, etc.).

    Returns
    -------
    DegradationAnalysis with detected events and summary flags.
    """
    # Filter to clean laps only, sorted by lap number
    clean_laps = sorted(lap for lap in all_lap_corners if lap not in anomalous_laps)

    if len(clean_laps) < MIN_LAPS:
        return DegradationAnalysis()

    # Determine the set of corner numbers from the first clean lap
    first_corners = all_lap_corners[clean_laps[0]]
    corner_numbers = [c.number for c in first_corners]

    events: list[DegradationEvent] = []

    for corner_num in corner_numbers:
        # Collect per-lap values for this corner
        brake_values: list[float] = []
        speed_values: list[float] = []
        brake_laps: list[int] = []
        speed_laps: list[int] = []

        for lap_num in clean_laps:
            corners = all_lap_corners.get(lap_num, [])
            matching = [c for c in corners if c.number == corner_num]
            if not matching:
                continue
            corner = matching[0]

            # Brake data: only include if we have a real brake value (not None, not 0)
            if corner.peak_brake_g is not None and corner.peak_brake_g != 0.0:
                brake_values.append(corner.peak_brake_g)
                brake_laps.append(lap_num)

            # Speed data: always available
            speed_values.append(corner.min_speed_mps)
            speed_laps.append(lap_num)

        # Analyze brake fade
        if len(brake_values) >= MIN_LAPS:
            y = np.array(brake_values)
            x = np.arange(len(y), dtype=float)
            coeffs = np.polyfit(x, y, 1)
            slope = float(coeffs[0])
            y_pred = np.polyval(coeffs, x)
            r_sq = _compute_r_squared(y, y_pred)

            # peak_brake_g is negative (braking), so fade means values become
            # less negative (slope > 0 means fading brakes).  But the spec
            # defines BRAKE_SLOPE_THRESHOLD as -0.01, meaning we look for the
            # absolute magnitude dropping.  Since peak_brake_g is stored as a
            # negative number, fade = slope becoming more positive (less
            # negative).  We check slope > abs(threshold) after negating.
            # Actually, let's be precise: peak_brake_g is negative (e.g. -0.8).
            # Brake fade means it becomes less negative over laps (e.g. -0.8
            # -> -0.7).  That's a positive slope.  The threshold is -0.01
            # meaning a change of 0.01 G per lap.  So we check:
            # slope > 0 and slope > abs(BRAKE_SLOPE_THRESHOLD).
            if slope > abs(BRAKE_SLOPE_THRESHOLD) and r_sq >= R_SQUARED_MIN:
                severity = _classify_severity(slope, abs(BRAKE_SLOPE_THRESHOLD))
                events.append(
                    DegradationEvent(
                        corner_number=corner_num,
                        metric="brake_fade",
                        start_lap=brake_laps[0],
                        end_lap=brake_laps[-1],
                        slope=round(slope, 6),
                        r_squared=round(r_sq, 4),
                        severity=severity,
                        description=(
                            f"Corner {corner_num}: Brake fade detected "
                            f"({severity}). Peak brake G decreased by "
                            f"{abs(slope):.3f} G/lap over laps "
                            f"{brake_laps[0]}-{brake_laps[-1]} "
                            f"(R²={r_sq:.2f})."
                        ),
                        values=[round(v, 4) for v in brake_values],
                        lap_numbers=brake_laps,
                    )
                )

        # Analyze tire degradation (min speed decreasing)
        if len(speed_values) >= MIN_LAPS:
            y = np.array(speed_values)
            x = np.arange(len(y), dtype=float)
            coeffs = np.polyfit(x, y, 1)
            slope = float(coeffs[0])
            y_pred = np.polyval(coeffs, x)
            r_sq = _compute_r_squared(y, y_pred)

            # Tire degradation = speed dropping, so slope is negative
            if slope < TIRE_SPEED_SLOPE_THRESHOLD and r_sq >= R_SQUARED_MIN:
                severity = _classify_severity(slope, TIRE_SPEED_SLOPE_THRESHOLD)
                events.append(
                    DegradationEvent(
                        corner_number=corner_num,
                        metric="tire_degradation",
                        start_lap=speed_laps[0],
                        end_lap=speed_laps[-1],
                        slope=round(slope, 6),
                        r_squared=round(r_sq, 4),
                        severity=severity,
                        description=(
                            f"Corner {corner_num}: Tire degradation detected "
                            f"({severity}). Min speed decreased by "
                            f"{abs(slope):.2f} m/s per lap over laps "
                            f"{speed_laps[0]}-{speed_laps[-1]} "
                            f"(R²={r_sq:.2f})."
                        ),
                        values=[round(v, 4) for v in speed_values],
                        lap_numbers=speed_laps,
                    )
                )

    has_brake = any(e.metric == "brake_fade" for e in events)
    has_tire = any(e.metric == "tire_degradation" for e in events)

    return DegradationAnalysis(
        events=events,
        has_brake_fade=has_brake,
        has_tire_degradation=has_tire,
    )

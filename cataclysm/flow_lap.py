"""Flow lap detection — identifies peak-performance laps.

A "flow lap" is one where the driver performed near their personal best
across all corners with balanced technique.  Flow laps are the laps worth
studying for insight into what the driver does when everything clicks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# Minimum laps to run flow detection.
_MIN_LAPS = 5

# Default threshold for labeling a lap as "flow".
_DEFAULT_FLOW_THRESHOLD = 0.70

# Weights for the four scoring dimensions.
FLOW_LAP_WEIGHTS = {
    "proximity_to_pb": 0.45,
    "balance": 0.25,
    "smoothness": 0.20,
    "timing": 0.10,
}


@dataclass
class FlowLapResult:
    """Result of flow lap detection for a session."""

    flow_laps: list[int]
    scores: dict[int, float]
    threshold: float
    best_flow_lap: int | None = None


def _score_proximity(
    lap_time: float,
    best_time: float,
) -> float:
    """Score how close a lap is to the personal best.

    Returns 1.0 if at PB, decays toward 0 as the gap grows.
    A lap 2% slower than PB scores ~0.5.
    """
    if best_time <= 0:
        return 0.0
    pct_off = (lap_time - best_time) / best_time
    if pct_off <= 0:
        return 1.0
    # Exponential decay: 1% off → 0.75, 2% off → 0.56, 5% off → 0.22
    return float(np.exp(-pct_off * 30.0))


def _score_balance(
    lap_corner_speeds: list[float],
    best_corner_speeds: list[float],
) -> float:
    """Score how balanced the lap is across corners.

    A balanced lap has a similar gap to best across all corners,
    rather than one corner dominating the deficit.
    """
    if not lap_corner_speeds or not best_corner_speeds:
        return 0.5
    if len(lap_corner_speeds) != len(best_corner_speeds):
        return 0.5
    gaps = []
    for lap_speed, best_speed in zip(lap_corner_speeds, best_corner_speeds, strict=False):
        if best_speed > 0:
            gap_pct = abs(lap_speed - best_speed) / best_speed
            gaps.append(gap_pct)
    if not gaps:
        return 0.5
    # Low std of gaps = balanced. CV < 0.3 → score near 1.0.
    std_gap = float(np.std(gaps))
    mean_gap = float(np.mean(gaps))
    if mean_gap < 0.001:
        return 1.0  # All gaps near zero = perfectly balanced.
    cv = std_gap / mean_gap
    return float(np.clip(1.0 - cv, 0.0, 1.0))


def _score_smoothness(
    lap_corner_speeds: list[float],
) -> float:
    """Score smoothness based on speed consistency through corners.

    Low variance in min speeds = smoother driving.
    """
    if len(lap_corner_speeds) < 2:
        return 0.5
    # Coefficient of variation across corner speeds.
    mean = float(np.mean(lap_corner_speeds))
    if mean < 1.0:
        return 0.5
    cv = float(np.std(lap_corner_speeds)) / mean
    # CV < 0.05 → very smooth (score ~1.0). CV > 0.20 → rough (score ~0.0).
    return float(np.clip(1.0 - cv * 5.0, 0.0, 1.0))


def _score_timing(
    lap_index: int,
    total_laps: int,
) -> float:
    """Score based on lap position in the session.

    Mid-session laps are more likely to be genuine flow state
    (not early warm-up or late fatigue).
    """
    if total_laps <= 1:
        return 0.5
    fraction = lap_index / (total_laps - 1)
    # Peak at 40-60% of session (Gaussian centered at 0.5, σ=0.25).
    return float(np.exp(-((fraction - 0.5) ** 2) / (2 * 0.25**2)))


def detect_flow_laps(
    lap_times: list[float],
    per_lap_corner_speeds: dict[int, list[float]],
    best_corner_speeds: list[float],
    threshold: float = _DEFAULT_FLOW_THRESHOLD,
) -> FlowLapResult | None:
    """Identify peak-performance flow laps in a session.

    Parameters
    ----------
    lap_times : list[float]
        Lap times in seconds, ordered by lap number.
    per_lap_corner_speeds : dict[int, list[float]]
        Mapping from lap_number (1-based) to list of min corner speeds.
    best_corner_speeds : list[float]
        Best min speed at each corner across all laps.
    threshold : float
        Minimum composite score to qualify as a flow lap.

    Returns None if insufficient data.
    """
    if len(lap_times) < _MIN_LAPS:
        return None
    if not per_lap_corner_speeds:
        return None

    best_time = min(lap_times)
    total_laps = len(lap_times)

    scores: dict[int, float] = {}
    lap_numbers = sorted(per_lap_corner_speeds.keys())

    for i, lap_num in enumerate(lap_numbers):
        lap_time = lap_times[lap_num - 1] if lap_num <= len(lap_times) else lap_times[-1]
        corner_speeds = per_lap_corner_speeds[lap_num]

        prox = _score_proximity(lap_time, best_time)
        bal = _score_balance(corner_speeds, best_corner_speeds)
        smooth = _score_smoothness(corner_speeds)
        timing = _score_timing(i, total_laps)

        composite = (
            FLOW_LAP_WEIGHTS["proximity_to_pb"] * prox
            + FLOW_LAP_WEIGHTS["balance"] * bal
            + FLOW_LAP_WEIGHTS["smoothness"] * smooth
            + FLOW_LAP_WEIGHTS["timing"] * timing
        )
        scores[lap_num] = round(composite, 3)

    flow_laps = [lap for lap, score in scores.items() if score >= threshold]
    flow_laps.sort(key=lambda lap: scores[lap], reverse=True)

    best_flow = flow_laps[0] if flow_laps else None

    logger.info(
        "Flow laps: %d of %d (threshold=%.2f, best=L%s)",
        len(flow_laps),
        total_laps,
        threshold,
        best_flow or "none",
    )

    return FlowLapResult(
        flow_laps=flow_laps,
        scores=scores,
        threshold=threshold,
        best_flow_lap=best_flow,
    )

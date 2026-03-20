"""Phenomenological tire thermal/degradation model for multi-lap coaching.

NOT used in single-lap optimal prediction (minimal impact). Purpose is
coaching features:
  - "Your grip fell off after lap 8"
  - "You're overdriving in corners 5-8"
  - Cold tire warning on first hot lap

Model: simple per-compound degradation curve with warmup phase.
Grip fraction = warmup_ramp * degradation_decay.

Parameters are based on tire engineering literature and HPDE experience:
  - Street tires: warm up fast (0.5 laps), degrade slowly
  - R-compound: warm up slowly (1.5 laps), degrade faster under heat
  - Slicks: slowest warmup (2.5 laps), narrowest operating window

This is a phenomenological model (not physics-based thermal ODE) because
calibrating heat transfer coefficients requires measured tire temps that
we don't have. The % degradation approach is adequate for coaching.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cataclysm.equipment import TireCompoundCategory


@dataclass(frozen=True)
class TireThermalParams:
    """Per-compound thermal behavior parameters.

    warmup_laps: laps to reach 95% of peak grip (exponential ramp)
    optimal_window_laps: laps at peak grip before degradation starts
    degradation_per_lap: % grip loss per lap after optimal window
    min_grip_fraction: floor — grip never drops below this fraction of peak
    """

    warmup_laps: float
    optimal_window_laps: float
    degradation_per_lap: float  # fraction (0.01 = 1% per lap)
    min_grip_fraction: float


# Per-compound thermal parameters.
# Sources: Tire Rack tech articles, SAE tire engineering papers, HPDE coaching.
COMPOUND_THERMAL_PARAMS: dict[TireCompoundCategory, TireThermalParams] = {
    TireCompoundCategory.STREET: TireThermalParams(
        warmup_laps=0.5,
        optimal_window_laps=15.0,  # street tires are robust
        degradation_per_lap=0.003,  # 0.3% per lap
        min_grip_fraction=0.90,
    ),
    TireCompoundCategory.ENDURANCE_200TW: TireThermalParams(
        warmup_laps=1.0,
        optimal_window_laps=12.0,
        degradation_per_lap=0.005,  # 0.5% per lap
        min_grip_fraction=0.88,
    ),
    TireCompoundCategory.SUPER_200TW: TireThermalParams(
        warmup_laps=1.0,
        optimal_window_laps=10.0,
        degradation_per_lap=0.007,
        min_grip_fraction=0.85,
    ),
    TireCompoundCategory.TW_100: TireThermalParams(
        warmup_laps=1.2,
        optimal_window_laps=8.0,
        degradation_per_lap=0.010,  # 1% per lap
        min_grip_fraction=0.82,
    ),
    TireCompoundCategory.R_COMPOUND: TireThermalParams(
        warmup_laps=1.5,
        optimal_window_laps=6.0,
        degradation_per_lap=0.015,  # 1.5% per lap
        min_grip_fraction=0.78,
    ),
    TireCompoundCategory.SLICK: TireThermalParams(
        warmup_laps=2.5,
        optimal_window_laps=4.0,
        degradation_per_lap=0.020,  # 2% per lap — narrow operating window
        min_grip_fraction=0.75,
    ),
}


def grip_fraction_at_lap(
    lap_number: int,
    compound: TireCompoundCategory,
    *,
    params: TireThermalParams | None = None,
) -> float:
    """Compute the grip fraction (0-1) for a given lap number.

    Lap numbering is 1-based (lap 1 = first hot lap).

    Returns a value in [min_grip_fraction, 1.0] representing the fraction
    of peak grip available on this lap.

    The model has two phases:
    1. Warmup: grip ramps from ~0.60 to 1.0 over warmup_laps
    2. Degradation: after optimal_window_laps at peak, grip decays linearly
    """
    if params is None:
        params = COMPOUND_THERMAL_PARAMS.get(
            compound,
            COMPOUND_THERMAL_PARAMS[TireCompoundCategory.ENDURANCE_200TW],
        )

    # Warmup phase: exponential approach to 1.0
    # At lap=warmup_laps, grip = 1 - exp(-3) ≈ 0.95
    warmup_tau = params.warmup_laps / 3.0  # 3 time constants = 95%
    warmup_factor = 1.0 - math.exp(-lap_number / max(warmup_tau, 0.01))

    # Degradation phase: linear decay after optimal window
    laps_past_optimal = max(0.0, lap_number - params.optimal_window_laps)
    degrad_factor = max(
        params.min_grip_fraction,
        1.0 - laps_past_optimal * params.degradation_per_lap,
    )

    return max(params.min_grip_fraction, warmup_factor * degrad_factor)


def detect_grip_degradation(
    lap_times_s: list[float],
    compound: TireCompoundCategory,
    *,
    threshold_pct: float = 2.0,
) -> dict[str, object]:
    """Analyze lap times for signs of tire degradation.

    Compares the trend of lap times (fuel-corrected via median) against
    the expected degradation curve. Returns coaching insights.

    Parameters
    ----------
    lap_times_s:
        Chronological list of lap times in seconds (outlaps/cooldowns excluded).
    compound:
        Tire compound category for expected degradation rate.
    threshold_pct:
        Percentage above expected model to flag as "overdriving".

    Returns
    -------
    Dictionary with coaching-relevant fields:
        - degradation_detected: bool
        - onset_lap: lap number where degradation started (or None)
        - rate_pct_per_lap: observed degradation rate
        - expected_rate_pct: expected rate for compound
        - coaching_note: human-readable coaching insight
    """
    if len(lap_times_s) < 4:
        return {
            "degradation_detected": False,
            "onset_lap": None,
            "rate_pct_per_lap": 0.0,
            "expected_rate_pct": 0.0,
            "coaching_note": "Not enough laps to assess degradation.",
        }

    params = COMPOUND_THERMAL_PARAMS.get(
        compound,
        COMPOUND_THERMAL_PARAMS[TireCompoundCategory.ENDURANCE_200TW],
    )

    # Use the best lap (after warmup) as the reference
    warmup_end = max(1, int(math.ceil(params.warmup_laps)))
    if warmup_end >= len(lap_times_s):
        warmup_end = 0

    peak_laps = lap_times_s[warmup_end : warmup_end + max(3, int(params.optimal_window_laps))]
    if not peak_laps:
        peak_laps = lap_times_s[:3]
    reference_time = min(peak_laps)

    # Look for degradation in the second half of the session
    mid = len(lap_times_s) // 2
    late_laps = lap_times_s[mid:]
    if not late_laps:
        late_laps = lap_times_s[-3:]

    late_avg = sum(late_laps) / len(late_laps)
    degradation_pct = (late_avg / reference_time - 1.0) * 100.0

    # Find onset: first lap where time exceeds reference + threshold
    onset_lap = None
    for i, t in enumerate(lap_times_s):
        if i < warmup_end:
            continue
        if (t / reference_time - 1.0) * 100.0 > threshold_pct:
            onset_lap = i + 1  # 1-based
            break

    # Compute per-lap rate from onset to end
    if onset_lap is not None and onset_lap < len(lap_times_s):
        remaining = lap_times_s[onset_lap - 1 :]
        if len(remaining) >= 2:
            rate = (remaining[-1] / remaining[0] - 1.0) * 100.0 / max(len(remaining) - 1, 1)
        else:
            rate = 0.0
    else:
        rate = 0.0

    expected_rate = params.degradation_per_lap * 100.0
    degradation_detected = degradation_pct > threshold_pct

    # Generate coaching note
    if not degradation_detected:
        note = "Tire grip remained consistent throughout the session."
    elif onset_lap is not None and rate > expected_rate * 1.5:
        note = (
            f"Grip dropped ~{degradation_pct:.1f}% from lap {onset_lap}. "
            f"Rate ({rate:.2f}%/lap) exceeds expected ({expected_rate:.1f}%/lap) "
            f"for {compound.value} tires — consider managing tire load in corners."
        )
    elif onset_lap is not None:
        note = (
            f"Normal degradation (~{degradation_pct:.1f}%) starting around lap {onset_lap}. "
            f"Consistent with {compound.value} tire characteristics."
        )
    else:
        note = f"Mild grip reduction (~{degradation_pct:.1f}%) across the session."

    return {
        "degradation_detected": degradation_detected,
        "onset_lap": onset_lap,
        "rate_pct_per_lap": round(rate, 3),
        "expected_rate_pct": round(expected_rate, 1),
        "coaching_note": note,
    }

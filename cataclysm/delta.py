"""Delta-T calculation between two resampled laps."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from cataclysm.corners import Corner


@dataclass
class CornerDelta:
    """Time delta for a specific corner."""

    corner_number: int
    delta_s: float  # positive = comparison lap slower, negative = faster


@dataclass
class DeltaResult:
    """Full delta-T result between two laps."""

    distance_m: np.ndarray
    delta_time_s: np.ndarray  # positive = comparison lap slower
    corner_deltas: list[CornerDelta] = field(default_factory=list)
    total_delta_s: float = 0.0


def compute_delta(
    ref_lap: pd.DataFrame,
    comp_lap: pd.DataFrame,
    corners: list[Corner] | None = None,
) -> DeltaResult:
    """Compute delta-T between two resampled laps.

    Delta = comp_time - ref_time at each distance point.
    Positive values mean the comparison lap is slower (ref is ahead).

    Parameters
    ----------
    ref_lap:
        Reference (typically best) lap DataFrame with lap_distance_m, lap_time_s.
    comp_lap:
        Comparison lap DataFrame with the same columns.
    corners:
        Optional list of corners for per-corner delta calculation.

    Returns
    -------
    DeltaResult with distance array, delta-T array, and optional corner deltas.
    """
    ref_dist = ref_lap["lap_distance_m"].to_numpy()
    ref_time = ref_lap["lap_time_s"].to_numpy()
    comp_dist = comp_lap["lap_distance_m"].to_numpy()
    comp_time = comp_lap["lap_time_s"].to_numpy()

    # Truncate to common distance range
    max_common = min(ref_dist[-1], comp_dist[-1])
    ref_mask = ref_dist <= max_common
    common_dist = ref_dist[ref_mask]

    # Interpolate comparison time onto reference distance grid
    comp_time_interp = np.interp(common_dist, comp_dist, comp_time)
    ref_time_aligned = ref_time[ref_mask]

    delta = comp_time_interp - ref_time_aligned

    # Per-corner deltas
    corner_deltas: list[CornerDelta] = []
    if corners:
        for corner in corners:
            entry_idx = int(np.searchsorted(common_dist, corner.entry_distance_m))
            exit_idx = int(np.searchsorted(common_dist, corner.exit_distance_m))

            if entry_idx >= len(delta) or exit_idx >= len(delta):
                continue

            # Corner delta = delta at exit minus delta at entry
            corner_delta = float(
                delta[min(exit_idx, len(delta) - 1)] - delta[min(entry_idx, len(delta) - 1)]
            )
            corner_deltas.append(
                CornerDelta(
                    corner_number=corner.number,
                    delta_s=round(corner_delta, 3),
                )
            )

    total = float(delta[-1]) if len(delta) > 0 else 0.0

    return DeltaResult(
        distance_m=common_dist,
        delta_time_s=delta,
        corner_deltas=corner_deltas,
        total_delta_s=round(total, 3),
    )

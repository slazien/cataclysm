"""Compare a driver's actual speed profile against a physics-optimal profile.

Identifies per-corner speed gaps, braking point differences, and time costs
to quantify where the driver is leaving the most time on the table.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from cataclysm.constants import MPS_TO_MPH
from cataclysm.corners import Corner
from cataclysm.velocity_profile import OptimalProfile

# Search window before a corner entry for matching optimal brake points
_BRAKE_SEARCH_BEFORE_M = 200.0

# Floor speed (mps) to avoid division-by-zero in time computations
_MIN_SPEED_MPS = 1.0


@dataclass
class CornerOpportunity:
    """Speed and braking gap for a single corner vs the optimal profile."""

    corner_number: int
    actual_min_speed_mps: float
    optimal_min_speed_mps: float
    speed_gap_mps: float  # optimal - actual (positive = driver is slower)
    speed_gap_mph: float
    actual_brake_point_m: float | None
    optimal_brake_point_m: float | None
    brake_gap_m: float | None  # positive = driver brakes later (closer to corner) than optimal
    time_cost_s: float  # time lost vs optimal in this corner zone


@dataclass
class OptimalComparisonResult:
    """Full comparison of an actual lap against the optimal profile."""

    corner_opportunities: list[CornerOpportunity]
    actual_lap_time_s: float
    optimal_lap_time_s: float
    total_gap_s: float  # actual - optimal (positive = driver is slower)
    speed_delta_mps: np.ndarray  # per-point: optimal - actual
    distance_m: np.ndarray  # distance array for speed_delta


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _interpolate_speed_at_distance(
    distance: np.ndarray,
    speed: np.ndarray,
    target_distances: np.ndarray,
) -> np.ndarray:
    """Interpolate speed values onto *target_distances*, clamped to valid range.

    Simple wrapper around :func:`numpy.interp` that ensures target distances
    outside the source range are clamped to the boundary speed values.
    """
    result: np.ndarray = np.interp(target_distances, distance, speed)  # type: ignore[assignment]
    return result


def _find_optimal_brake_for_corner(
    corner: Corner,
    optimal: OptimalProfile,
) -> float | None:
    """Find the closest optimal brake point within [entry - 200m, apex].

    Returns the brake-point distance, or *None* if no optimal brake point
    falls inside the search window.
    """
    search_start = corner.entry_distance_m - _BRAKE_SEARCH_BEFORE_M
    search_end = corner.apex_distance_m

    best: float | None = None
    best_dist = float("inf")

    for bp in optimal.optimal_brake_points:
        if search_start <= bp <= search_end:
            # Prefer the brake point closest to the corner entry
            d = abs(bp - corner.entry_distance_m)
            if d < best_dist:
                best = bp
                best_dist = d

    return best


def _compute_time_cost(
    actual_speed: np.ndarray,
    optimal_speed: np.ndarray,
    step_m: float,
) -> float:
    """Compute time cost (seconds) of the actual vs optimal speed arrays.

    ``time_cost = sum(step / v_actual) - sum(step / v_optimal)``

    Speeds are floored at :data:`_MIN_SPEED_MPS` to prevent division by zero.
    """
    safe_actual = np.maximum(actual_speed, _MIN_SPEED_MPS)
    safe_optimal = np.maximum(optimal_speed, _MIN_SPEED_MPS)

    actual_time = np.sum(step_m / safe_actual)
    optimal_time = np.sum(step_m / safe_optimal)

    return float(actual_time - optimal_time)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compare_speed_profiles(
    lap_df: pd.DataFrame,
    optimal: OptimalProfile,
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate the actual speed onto the optimal distance grid and compute delta.

    Parameters
    ----------
    lap_df
        Must contain ``lap_distance_m`` and ``speed_mps`` columns.
    optimal
        The physics-optimal profile to compare against.

    Returns
    -------
    (distance_m, speed_delta_mps)
        *speed_delta_mps* = optimal - actual.  Positive values mean the driver
        is slower than optimal.
    """
    actual_distance = lap_df["lap_distance_m"].to_numpy()
    actual_speed = lap_df["speed_mps"].to_numpy()

    interpolated_actual = _interpolate_speed_at_distance(
        actual_distance,
        actual_speed,
        optimal.distance_m,
    )

    speed_delta = optimal.optimal_speed_mps - interpolated_actual
    return optimal.distance_m, speed_delta


def compute_corner_opportunities(
    corners: list[Corner],
    lap_df: pd.DataFrame,
    optimal: OptimalProfile,
) -> list[CornerOpportunity]:
    """Compute per-corner opportunity gaps vs the optimal profile.

    For each corner the function finds:
    - The optimal minimum speed within the corner zone [entry, exit].
    - The speed gap (optimal min - actual min).
    - The optimal brake point and braking gap.
    - The time cost for that corner zone.

    Returns a list sorted by *time_cost* descending (biggest opportunity first).
    """
    if not corners:
        return []

    actual_distance = lap_df["lap_distance_m"].to_numpy()
    actual_speed = lap_df["speed_mps"].to_numpy()

    # Pre-compute step size from the optimal profile
    if len(optimal.distance_m) >= 2:
        step_m = float(optimal.distance_m[1] - optimal.distance_m[0])
    else:
        step_m = 0.7

    opportunities: list[CornerOpportunity] = []

    for corner in corners:
        # --- optimal min speed in the corner zone --------------------------
        opt_mask = (optimal.distance_m >= corner.entry_distance_m) & (
            optimal.distance_m <= corner.exit_distance_m
        )
        if not opt_mask.any():
            continue
        optimal_zone_speed = optimal.optimal_speed_mps[opt_mask]
        optimal_min_speed = float(np.min(optimal_zone_speed))

        # --- actual speed interpolated onto the optimal grid ---------------
        interp_actual = _interpolate_speed_at_distance(
            actual_distance,
            actual_speed,
            optimal.distance_m[opt_mask],
        )

        # --- speed gap -----------------------------------------------------
        speed_gap = optimal_min_speed - corner.min_speed_mps
        speed_gap_mph = speed_gap * MPS_TO_MPH

        # --- brake gap -----------------------------------------------------
        opt_brake = _find_optimal_brake_for_corner(corner, optimal)
        if opt_brake is not None and corner.brake_point_m is not None:
            brake_gap: float | None = corner.brake_point_m - opt_brake
        else:
            brake_gap = None

        # --- time cost in this zone ----------------------------------------
        time_cost = _compute_time_cost(interp_actual, optimal_zone_speed, step_m)

        opportunities.append(
            CornerOpportunity(
                corner_number=corner.number,
                actual_min_speed_mps=corner.min_speed_mps,
                optimal_min_speed_mps=optimal_min_speed,
                speed_gap_mps=speed_gap,
                speed_gap_mph=speed_gap_mph,
                actual_brake_point_m=corner.brake_point_m,
                optimal_brake_point_m=opt_brake,
                brake_gap_m=brake_gap,
                time_cost_s=time_cost,
            )
        )

    # Sort by time cost descending (biggest opportunity first)
    opportunities.sort(key=lambda opp: opp.time_cost_s, reverse=True)
    return opportunities


def compare_with_optimal(
    lap_df: pd.DataFrame,
    corners: list[Corner],
    optimal: OptimalProfile,
) -> OptimalComparisonResult:
    """Orchestrate a full comparison of an actual lap vs the optimal profile.

    Parameters
    ----------
    lap_df
        Resampled lap with ``lap_distance_m``, ``speed_mps``, and
        ``lap_time_s`` columns.
    corners
        Detected corners for this lap.
    optimal
        Physics-optimal speed profile.

    Returns
    -------
    OptimalComparisonResult
    """
    distance_m, speed_delta = compare_speed_profiles(lap_df, optimal)
    corner_opportunities = compute_corner_opportunities(corners, lap_df, optimal)

    # Actual lap time from the DataFrame
    time_col = lap_df["lap_time_s"].to_numpy()
    actual_lap_time = float(time_col[-1] - time_col[0])

    total_gap = actual_lap_time - optimal.lap_time_s

    return OptimalComparisonResult(
        corner_opportunities=corner_opportunities,
        actual_lap_time_s=actual_lap_time,
        optimal_lap_time_s=optimal.lap_time_s,
        total_gap_s=total_gap,
        speed_delta_mps=speed_delta,
        distance_m=distance_m,
    )

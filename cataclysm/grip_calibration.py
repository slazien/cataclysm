"""Data-driven grip calibration from observed G-G telemetry data.

Extracts three semi-axis grip limits (lateral, braking, acceleration) from
a driver's actual telemetry rather than relying on equipment-based estimates.
This fixes "faster than optimal" problems where the constant mu=1.0 model
underestimates the car's actual capability at specific corners.

The approach:
1. Filter G-G data by cross-axis threshold to isolate pure-axis events.
2. Take the 99th percentile (not max) to reject sensor spikes.
3. Classify confidence based on available data point count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from cataclysm.velocity_profile import VehicleParams

if TYPE_CHECKING:
    from cataclysm.corners import Corner

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Confidence thresholds (minimum points across all axes)
_HIGH_CONFIDENCE_THRESHOLD = 500
_MEDIUM_CONFIDENCE_THRESHOLD = 100


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CalibratedGrip:
    """Observed vehicle capability extracted from G-G data."""

    max_lateral_g: float  # 99th percentile |ay| when |ax| < 0.2g
    max_brake_g: float  # 99th percentile |ax| when ax < -0.2g, |ay| < 0.2g
    max_accel_g: float  # 99th percentile |ax| when ax > 0.2g, |ay| < 0.2g
    point_count: int  # number of data points used (minimum across axes)
    confidence: str  # "high" (>500 pts per axis), "medium" (100-500), "low" (<100)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calibrate_grip_from_telemetry(
    lateral_g: np.ndarray,
    longitudinal_g: np.ndarray,
    *,
    percentile: float = 99.0,
    cross_axis_threshold: float = 0.2,
    min_points: int = 20,
) -> CalibratedGrip | None:
    """Extract 3-axis grip limits from observed G-G data.

    Filters telemetry into three regimes (pure lateral, pure braking, pure
    acceleration) using a cross-axis threshold, then computes the percentile
    of the absolute values in each regime.

    Parameters
    ----------
    lateral_g
        Array of lateral acceleration values (G).
    longitudinal_g
        Array of longitudinal acceleration values (G).  Negative = braking.
    percentile
        Percentile to use for extracting peak values (default 99.0).
    cross_axis_threshold
        Maximum allowed cross-axis G to consider a sample "pure" for that
        axis (default 0.2G).
    min_points
        Minimum number of data points required in each axis regime.
        Returns None if any axis has fewer points than this.

    Returns
    -------
    CalibratedGrip or None
        Extracted grip limits, or None if insufficient data in any axis.
    """
    if len(lateral_g) == 0 or len(longitudinal_g) == 0:
        return None

    # Lateral: points where |longitudinal_g| < threshold
    lat_mask = np.abs(longitudinal_g) < cross_axis_threshold
    if int(lat_mask.sum()) < min_points:
        return None
    max_lat = float(np.percentile(np.abs(lateral_g[lat_mask]), percentile))

    # Braking: ax < -threshold AND |ay| < threshold
    brake_mask = (longitudinal_g < -cross_axis_threshold) & (
        np.abs(lateral_g) < cross_axis_threshold
    )
    if int(brake_mask.sum()) < min_points:
        return None
    max_brake = float(np.percentile(np.abs(longitudinal_g[brake_mask]), percentile))

    # Acceleration: ax > threshold AND |ay| < threshold
    accel_mask = (longitudinal_g > cross_axis_threshold) & (
        np.abs(lateral_g) < cross_axis_threshold
    )
    if int(accel_mask.sum()) < min_points:
        return None
    max_accel = float(np.percentile(longitudinal_g[accel_mask], percentile))

    # Confidence classification based on minimum count across all axes
    point_count = int(min(lat_mask.sum(), brake_mask.sum(), accel_mask.sum()))
    if point_count > _HIGH_CONFIDENCE_THRESHOLD:
        confidence = "high"
    elif point_count > _MEDIUM_CONFIDENCE_THRESHOLD:
        confidence = "medium"
    else:
        confidence = "low"

    return CalibratedGrip(
        max_lateral_g=max_lat,
        max_brake_g=max_brake,
        max_accel_g=max_accel,
        point_count=point_count,
        confidence=confidence,
    )


def apply_calibration_to_params(
    base_params: VehicleParams,
    grip: CalibratedGrip,
) -> VehicleParams:
    """Override VehicleParams with calibrated grip values.

    Rules:
    - max_lateral_g = grip.max_lateral_g
    - max_decel_g = grip.max_brake_g
    - max_accel_g = grip.max_accel_g
    - mu = max(max_lateral_g, max_brake_g) (overall friction envelope)
    - Sets calibrated=True flag
    - Preserves equipment-derived top_speed, aero, drag coefficients

    Parameters
    ----------
    base_params
        Base VehicleParams (from equipment or defaults).
    grip
        Calibrated grip extracted from telemetry data.

    Returns
    -------
    VehicleParams
        New VehicleParams with grip values overridden.
    """
    return VehicleParams(
        mu=max(grip.max_lateral_g, grip.max_brake_g),
        max_accel_g=grip.max_accel_g,
        max_decel_g=grip.max_brake_g,
        max_lateral_g=grip.max_lateral_g,
        friction_circle_exponent=base_params.friction_circle_exponent,
        aero_coefficient=base_params.aero_coefficient,
        drag_coefficient=base_params.drag_coefficient,
        top_speed_mps=base_params.top_speed_mps,
        calibrated=True,
    )


def calibrate_per_corner_grip(
    lateral_g: np.ndarray,
    distance_m: np.ndarray,
    corners: list[Corner],
    *,
    percentile: float = 99.0,
    min_points: int = 10,
) -> dict[int, float]:
    """Extract per-corner effective mu from observed lateral G.

    For each corner zone (entry to exit distance), compute:
        mu_eff = percentile(|lateral_g|) / G_ACCEL

    where G_ACCEL = 9.81 m/s^2 (converting from G-force to friction coefficient).

    Since lateral_g is already in G units (multiples of 9.81), mu_eff is simply
    the percentile of |lateral_g| in the corner zone.

    Parameters
    ----------
    lateral_g
        Array of lateral acceleration values (in G).
    distance_m
        Array of distance values (m), same length as *lateral_g*.
    corners
        List of detected corners with entry/exit distances.
    percentile
        Percentile to extract from |lateral_g| in each zone (default 99.0).
    min_points
        Minimum data points in a corner zone to include it.
        Corners with fewer points are excluded from the result.

    Returns
    -------
    dict[int, float]
        Mapping of corner_number -> mu_effective.
        Corners with insufficient data are omitted.
    """
    if len(corners) == 0:
        return {}

    result: dict[int, float] = {}

    for corner in corners:
        # Build mask for points within this corner's distance zone
        mask = (distance_m >= corner.entry_distance_m) & (distance_m <= corner.exit_distance_m)
        n_points = int(mask.sum())

        if n_points < min_points:
            continue

        # mu_eff = percentile of |lateral_g| in the zone
        # lateral_g is already in G units, so this directly gives mu
        mu_eff = float(np.percentile(np.abs(lateral_g[mask]), percentile))
        result[corner.number] = mu_eff

    return result

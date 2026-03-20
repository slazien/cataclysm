"""Empirical GGV (g-g-speed) envelope extractor from telemetry data.

Builds speed-dependent performance envelopes from lateral and longitudinal
acceleration data, capturing real tire, suspension, and aerodynamic effects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# Minimum points required in a speed bin to compute percentile statistics.
_MIN_BIN_POINTS = 20


@dataclass
class GGVEnvelope:
    """Speed-dependent GG performance envelope built from telemetry."""

    speed_bins: np.ndarray  # center speed of each bin (m/s), sorted ascending
    max_lateral_g: np.ndarray  # peak |lateral| G per bin (p-th percentile)
    max_decel_g: np.ndarray  # peak braking G per bin (positive = decel, p-th percentile)
    max_accel_g: np.ndarray  # peak acceleration G per bin (positive, p-th percentile)
    point_counts: np.ndarray  # number of telemetry points per bin

    def max_lateral_at_speed(self, speed_mps: float) -> float:
        """Interpolate peak lateral G capability at a given speed."""
        return float(np.interp(speed_mps, self.speed_bins, self.max_lateral_g))

    def max_decel_at_speed(self, speed_mps: float) -> float:
        """Interpolate peak braking G capability at a given speed."""
        return float(np.interp(speed_mps, self.speed_bins, self.max_decel_g))

    def max_accel_at_speed(self, speed_mps: float) -> float:
        """Interpolate peak acceleration G capability at a given speed."""
        return float(np.interp(speed_mps, self.speed_bins, self.max_accel_g))


def build_ggv_from_telemetry(
    speed_mps: np.ndarray,
    lateral_g: np.ndarray,
    longitudinal_g: np.ndarray,
    *,
    n_speed_bins: int = 8,
    percentile: float = 95.0,
    min_total_points: int = 100,
) -> GGVEnvelope | None:
    """Build an empirical GGV envelope from telemetry acceleration data.

    Args:
        speed_mps: Vehicle speed in m/s for each sample.
        lateral_g: Lateral acceleration in G (positive = either direction).
        longitudinal_g: Longitudinal acceleration in G (positive = accel, negative = braking).
        n_speed_bins: Number of equal-width speed bins.
        percentile: Percentile for envelope boundary (e.g. 95 = p95).
        min_total_points: Minimum valid data points required; returns None otherwise.

    Returns:
        A GGVEnvelope capturing the speed-dependent performance envelope,
        or None if insufficient data.
    """
    # Validate inputs have matching lengths.
    if len(speed_mps) != len(lateral_g) or len(speed_mps) != len(longitudinal_g):
        logger.warning(
            "GGV input arrays have mismatched lengths: speed=%d, lat=%d, lon=%d",
            len(speed_mps),
            len(lateral_g),
            len(longitudinal_g),
        )
        return None

    # Filter out NaN / inf values.
    valid_mask = np.isfinite(speed_mps) & np.isfinite(lateral_g) & np.isfinite(longitudinal_g)
    speed = speed_mps[valid_mask]
    lat = lateral_g[valid_mask]
    lon = longitudinal_g[valid_mask]

    if len(speed) < min_total_points:
        logger.debug(
            "GGV: only %d valid points (need %d), returning None",
            len(speed),
            min_total_points,
        )
        return None

    # Build equal-width speed bins.
    speed_min = float(np.min(speed))
    speed_max = float(np.max(speed))
    if speed_max - speed_min < 1e-6:
        logger.debug("GGV: speed range too narrow (%.2f–%.2f m/s)", speed_min, speed_max)
        return None

    bin_edges = np.linspace(speed_min, speed_max, n_speed_bins + 1)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    # Digitize each sample into a bin (1-indexed, so subtract 1).
    bin_indices = np.digitize(speed, bin_edges) - 1
    # Clamp to valid range (last edge goes into last bin).
    bin_indices = np.clip(bin_indices, 0, n_speed_bins - 1)

    # Compute per-bin statistics.
    max_lat = np.full(n_speed_bins, np.nan)
    max_decel = np.full(n_speed_bins, np.nan)
    max_accel = np.full(n_speed_bins, np.nan)
    counts = np.zeros(n_speed_bins, dtype=np.int64)

    for i in range(n_speed_bins):
        mask = bin_indices == i
        n_pts = int(np.sum(mask))
        counts[i] = n_pts
        if n_pts < _MIN_BIN_POINTS:
            continue

        bin_lat = np.abs(lat[mask])
        bin_lon = lon[mask]

        max_lat[i] = float(np.percentile(bin_lat, percentile))

        # Braking: negative longitudinal → positive decel value.
        braking = -bin_lon[bin_lon < 0]
        if len(braking) >= 1:
            max_decel[i] = float(np.percentile(braking, percentile))
        else:
            max_decel[i] = 0.0

        # Acceleration: positive longitudinal.
        accel = bin_lon[bin_lon > 0]
        if len(accel) >= 1:
            max_accel[i] = float(np.percentile(accel, percentile))
        else:
            max_accel[i] = 0.0

    # Count populated bins (non-NaN lateral, which is the primary metric).
    populated_mask = ~np.isnan(max_lat)
    n_populated = int(np.sum(populated_mask))

    if n_populated < 2:
        logger.debug("GGV: only %d populated bins (need >= 2), returning None", n_populated)
        return None

    # Interpolate sparse bins from populated neighbors.
    populated_indices = np.where(populated_mask)[0]
    populated_centers = bin_centers[populated_indices]

    for arr in (max_lat, max_decel, max_accel):
        populated_vals = arr[populated_indices]
        for i in range(n_speed_bins):
            if np.isnan(arr[i]):
                arr[i] = float(np.interp(bin_centers[i], populated_centers, populated_vals))

    return GGVEnvelope(
        speed_bins=bin_centers,
        max_lateral_g=max_lat,
        max_decel_g=max_decel,
        max_accel_g=max_accel,
        point_counts=counts,
    )

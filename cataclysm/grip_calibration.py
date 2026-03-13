"""Data-driven grip calibration from observed G-G telemetry data.

Extracts three semi-axis grip limits (lateral, braking, acceleration) from
a driver's actual telemetry rather than relying on equipment-based estimates.
This fixes "faster than optimal" problems where the constant mu=1.0 model
underestimates the car's actual capability at specific corners.

The approach:
1. Filter G-G data by cross-axis threshold to isolate pure-axis events.
2. Take the 95th percentile (not max) to reject transient spikes from weight
   transfer, curb strikes, and sensor noise.  This better represents sustained
   near-limit cornering capability rather than momentary peaks.
3. Classify confidence based on available data point count.

Also provides a speed-bucketed GGV (G-G-Velocity) surface that captures how
the car's capability envelope changes with speed — power limitation at low
speed, aerodynamic grip boost at high speed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from cataclysm.velocity_profile import VehicleParams

if TYPE_CHECKING:
    from cataclysm.corners import Corner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Confidence thresholds (minimum points across all axes)
_HIGH_CONFIDENCE_THRESHOLD = 500
_MEDIUM_CONFIDENCE_THRESHOLD = 100

# GGV surface: minimum total data points to produce a meaningful surface
_MIN_GGV_TOTAL_POINTS = 50

# Full circle in radians
_TWO_PI = 2.0 * np.pi


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CalibratedGrip:
    """Observed vehicle capability extracted from G-G data."""

    max_lateral_g: float  # 95th percentile |ay| when |ax| < 0.2g and |ay| >= 0.3g
    max_brake_g: float  # 95th percentile |ax| when ax < -0.2g, |ay| < 0.2g
    max_accel_g: float  # 95th percentile |ax| when ax > 0.2g, |ay| < 0.2g
    point_count: int  # number of data points used (minimum across axes)
    confidence: str  # "high" (>500 pts per axis), "medium" (100-500), "low" (<100)


@dataclass
class GGVSurface:
    """Speed-bucketed G-G envelope surface.

    Captures how the vehicle's capability envelope changes with speed.
    At low speeds, power limits acceleration; at high speeds, aerodynamic
    downforce boosts cornering grip.

    Attributes
    ----------
    speed_bins
        Array of speed bin centers (m/s), shape ``(n_speed_bins,)``.
    envelopes
        For each speed bin, array of max combined-G per angular sector,
        each of shape ``(n_sectors,)``.
    n_sectors
        Number of angular sectors dividing the G-G plane (default 36,
        i.e. 10-degree resolution).
    """

    speed_bins: np.ndarray  # shape (n_speed_bins,)
    envelopes: list[np.ndarray]  # each shape (n_sectors,), one per speed bin
    n_sectors: int = 36


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calibrate_grip_from_telemetry(
    lateral_g: np.ndarray,
    longitudinal_g: np.ndarray,
    *,
    percentile: float = 95.0,
    cross_axis_threshold: float = 0.2,
    min_points: int = 20,
    min_lateral_g: float = 0.3,
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
        Percentile to use for extracting peak values (default 95.0).
        p95 captures near-limit cornering capability while rejecting sensor
        noise spikes.  Lower values (p90) under-estimate grip because the
        distribution includes below-limit moderate cornering; higher values
        (p99) over-index on transient spikes from weight transfer and curbs.
    cross_axis_threshold
        Maximum allowed cross-axis G to consider a sample "pure" for that
        axis (default 0.2G).
    min_points
        Minimum number of data points required in each axis regime.
        Returns None if any axis has fewer points than this.
    min_lateral_g
        Minimum |lateral_g| to include in the lateral regime (default 0.3G).
        Excludes gentle sweeping curves and highway-speed lane changes that
        dilute the distribution toward lower G values.  Only samples where
        the driver is genuinely cornering at ≥0.3G are used to estimate the
        tire's lateral grip limit.  Has no effect on braking or acceleration
        regimes.

    Returns
    -------
    CalibratedGrip or None
        Extracted grip limits, or None if insufficient data in any axis.
    """
    if len(lateral_g) == 0 or len(longitudinal_g) == 0:
        return None

    # Lateral: points where |longitudinal_g| < threshold AND driver is
    # genuinely cornering (|lateral_g| >= min_lateral_g).  The min_lateral_g
    # filter removes gentle sweeper data that dilutes the p-percentile toward
    # below-limit values, causing systematic under-estimation of tire mu.
    lat_mask = (np.abs(longitudinal_g) < cross_axis_threshold) & (
        np.abs(lateral_g) >= min_lateral_g
    )
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
    *,
    mu_cap: float | None = None,
) -> VehicleParams:
    """Merge calibrated grip with base VehicleParams, keeping the higher value.

    For each axis, uses max(base, observed) so that calibration can only raise
    the grip envelope above the base (equipment or defaults), never lower it.
    This prevents the solver from underestimating a car's capability when the
    driver hasn't fully explored the grip limit.

    When *mu_cap* is provided (typically from the tire compound category plus
    a margin), the calibrated values are clamped to prevent unrealistic grip
    inflation from transient G-spikes that exceed the tire's physical capability.

    Rules:
    - max_lateral_g = min(max(base, grip.max_lateral_g), mu_cap)
    - max_decel_g = min(max(base, grip.max_brake_g), mu_cap)
    - max_accel_g = min(max(base, grip.max_accel_g), mu_cap)
    - mu = max of the resolved lateral and brake values
    - Sets calibrated=True flag
    - Preserves equipment-derived top_speed, aero, drag coefficients

    Parameters
    ----------
    base_params
        Base VehicleParams (from equipment or defaults).
    grip
        Calibrated grip extracted from telemetry data.
    mu_cap
        Maximum allowed grip coefficient.  When set (e.g., from the tire
        compound category), prevents calibration from exceeding the tire's
        physical capability envelope.

    Returns
    -------
    VehicleParams
        New VehicleParams with grip values merged.
    """
    lat_g = max(base_params.max_lateral_g, grip.max_lateral_g)
    brake_g = max(base_params.max_decel_g, grip.max_brake_g)
    accel_g = max(base_params.max_accel_g, grip.max_accel_g)

    if mu_cap is not None:
        lat_g = min(lat_g, mu_cap)
        brake_g = min(brake_g, mu_cap)
        accel_g = min(accel_g, mu_cap)
    return VehicleParams(
        mu=max(lat_g, brake_g),
        max_accel_g=accel_g,
        max_decel_g=brake_g,
        max_lateral_g=lat_g,
        friction_circle_exponent=base_params.friction_circle_exponent,
        aero_coefficient=base_params.aero_coefficient,
        drag_coefficient=base_params.drag_coefficient,
        top_speed_mps=base_params.top_speed_mps,
        calibrated=True,
        load_sensitivity_exponent=base_params.load_sensitivity_exponent,
        cg_height_m=base_params.cg_height_m,
        track_width_m=base_params.track_width_m,
        wheel_power_w=base_params.wheel_power_w,
        mass_kg=base_params.mass_kg,
    )


def calibrate_per_corner_grip(
    lateral_g: np.ndarray,
    distance_m: np.ndarray,
    corners: list[Corner],
    *,
    percentile: float = 95.0,
    min_points: int = 10,
) -> dict[int, float]:
    """Extract per-corner effective mu from observed lateral G.

    For each corner zone (entry to exit distance), compute:
        mu_eff = percentile(|lateral_g|) / G_ACCEL

    where G_ACCEL = 9.81 m/s^2 (converting from G-force to friction coefficient).

    Since lateral_g is already in G units (multiples of 9.81), mu_eff is simply
    the percentile of |lateral_g| in the corner zone.  Unlike the global
    calibration, per-corner data is already concentrated on cornering events
    so no additional min_lateral_g filter is needed.

    Parameters
    ----------
    lateral_g
        Array of lateral acceleration values (in G).
    distance_m
        Array of distance values (m), same length as *lateral_g*.
    corners
        List of detected corners with entry/exit distances.
    percentile
        Percentile to extract from |lateral_g| in each zone (default 95.0).
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


def braking_zone_mask(
    distance_m: np.ndarray,
    zone_start_m: float,
    zone_end_m: float,
    *,
    local_zone_end_m: float | None = None,
) -> np.ndarray:
    """Return a boolean mask for a braking zone.

    True start/finish wrap is only inferred when the zone begins before 0 m.
    If ``zone_start_m > zone_end_m`` but the brake point still lies before the
    corner apex, treat it as an ordinary in-corner trail-braking interval that
    runs from brake onset through the local end (typically the apex).
    """
    finite_distance = distance_m[np.isfinite(distance_m)]
    if len(finite_distance) == 0:
        return np.zeros(len(distance_m), dtype=bool)

    if len(finite_distance) >= 2:
        unique_distance = np.unique(finite_distance)
        step_m = float(np.median(np.diff(unique_distance))) if len(unique_distance) >= 2 else 0.0
    else:
        step_m = 0.0

    track_length_m = float(np.max(finite_distance) + max(step_m, 0.0))
    if track_length_m <= 0.0:
        return (distance_m >= zone_start_m) & (distance_m <= zone_end_m)

    zone_span_m = zone_end_m - zone_start_m
    if zone_span_m >= track_length_m:
        return np.asarray(np.isfinite(distance_m), dtype=bool)

    # Most telemetry-derived "inverted" intervals are just trail braking that
    # begins slightly after the formal corner-entry boundary, not a start/finish
    # wrap. Only wrap if the zone actually extends before 0 m.
    if zone_start_m < 0.0:
        zone_start_wrapped = zone_start_m % track_length_m
        zone_end_wrapped = zone_end_m % track_length_m
        if zone_start_wrapped <= zone_end_wrapped:
            return (distance_m >= zone_start_wrapped) & (distance_m <= zone_end_wrapped)
        return (distance_m >= zone_start_wrapped) | (distance_m <= zone_end_wrapped)

    if zone_start_m > zone_end_m:
        if local_zone_end_m is not None and zone_start_m <= local_zone_end_m:
            return (distance_m >= zone_start_m) & (distance_m <= local_zone_end_m)
        zone_start_wrapped = zone_start_m % track_length_m
        zone_end_wrapped = zone_end_m % track_length_m
        if zone_start_wrapped <= zone_end_wrapped:
            return (distance_m >= zone_start_wrapped) & (distance_m <= zone_end_wrapped)
        return (distance_m >= zone_start_wrapped) | (distance_m <= zone_end_wrapped)

    return (distance_m >= zone_start_m) & (distance_m <= zone_end_m)


def calibrate_per_corner_braking_g(
    longitudinal_g: np.ndarray,
    distance_m: np.ndarray,
    corners: list[Corner],
    *,
    percentile: float = 95.0,
    min_points: int = 10,
    braking_zone_margin_m: float = 200.0,
) -> dict[int, float]:
    """Extract per-corner braking G from the braking zone preceding each corner.

    For each corner, the braking zone is defined as
    ``[brake_point_m, entry_distance_m]`` if ``brake_point_m`` is known,
    otherwise ``[entry_distance_m - braking_zone_margin_m, entry_distance_m]``.

    Only actual braking samples (``longitudinal_g < -0.2``) are included.
    """
    if len(corners) == 0:
        return {}

    result: dict[int, float] = {}

    for corner in corners:
        zone_end = corner.entry_distance_m
        zone_start = (
            corner.brake_point_m
            if corner.brake_point_m is not None
            else zone_end - braking_zone_margin_m
        )

        local_zone_end = (
            corner.apex_distance_m
            if corner.brake_point_m is not None and zone_start > zone_end
            else None
        )
        zone_mask = braking_zone_mask(
            distance_m,
            zone_start,
            zone_end,
            local_zone_end_m=local_zone_end,
        ) & (longitudinal_g < -0.2)
        n_points = int(zone_mask.sum())
        if n_points < min_points:
            continue

        braking_g = float(np.percentile(np.abs(longitudinal_g[zone_mask]), percentile))
        result[corner.number] = braking_g

    return result


# ---------------------------------------------------------------------------
# GGV Surface
# ---------------------------------------------------------------------------


def build_ggv_surface(
    speed_mps: np.ndarray,
    lateral_g: np.ndarray,
    longitudinal_g: np.ndarray,
    *,
    speed_bin_width: float = 5.0,
    n_sectors: int = 36,
    percentile: float = 99.0,
    min_points_per_sector: int = 3,
) -> GGVSurface | None:
    """Build a GGV surface from telemetry data.

    At each speed bucket, build a G-G envelope using angular sectors.
    Uses percentile (not max) for robustness against sensor spikes.

    Algorithm
    ---------
    1. Bin data by speed (e.g., 0-5, 5-10, 10-15, ... m/s).
    2. Within each speed bin, compute ``angle = atan2(lon_g, lat_g)``
       for each point.
    3. Bin by angle into *n_sectors* sectors (each ``360/n_sectors`` degrees).
    4. For each sector, take percentile of
       ``combined_g = sqrt(lat_g^2 + lon_g^2)``.
    5. Sectors with fewer than *min_points_per_sector* use the overall bin
       percentile as a fallback.

    Parameters
    ----------
    speed_mps
        Array of speed values (m/s).
    lateral_g
        Array of lateral acceleration values (G).
    longitudinal_g
        Array of longitudinal acceleration values (G).
    speed_bin_width
        Width of each speed bin in m/s (default 5.0, ~11 mph).
    n_sectors
        Number of angular sectors in the G-G plane (default 36).
    percentile
        Percentile to use for envelope extraction (default 99.0).
    min_points_per_sector
        Minimum data points in an angular sector to use its own percentile.
        Sectors below this threshold fall back to the bin-wide percentile.

    Returns
    -------
    GGVSurface or None
        The constructed surface, or None if insufficient data (fewer than
        ``_MIN_GGV_TOTAL_POINTS`` total points).
    """
    n = len(speed_mps)
    if n < _MIN_GGV_TOTAL_POINTS:
        return None

    # Pre-compute combined G and angle for all points
    combined_g = np.sqrt(lateral_g**2 + longitudinal_g**2)
    angles = np.arctan2(longitudinal_g, lateral_g)  # range [-pi, pi]

    # Determine speed bin edges
    speed_min = float(np.min(speed_mps))
    speed_max = float(np.max(speed_mps))

    # Align bin edges to multiples of speed_bin_width
    bin_start = (speed_min // speed_bin_width) * speed_bin_width
    bin_end = ((speed_max // speed_bin_width) + 1) * speed_bin_width
    bin_edges = np.arange(bin_start, bin_end + speed_bin_width * 0.5, speed_bin_width)

    # Angular sector edges: [-pi, -pi + 2*pi/n_sectors, ..., pi]
    sector_edges = np.linspace(-np.pi, np.pi, n_sectors + 1)

    # Digitize speeds into bins (1-indexed; 0 = below first edge, len = above last)
    speed_bin_idx = np.digitize(speed_mps, bin_edges)

    # Build envelopes for bins that have data
    valid_speed_bins: list[float] = []
    valid_envelopes: list[np.ndarray] = []

    for b in range(1, len(bin_edges)):
        bin_mask = speed_bin_idx == b
        n_in_bin = int(bin_mask.sum())
        if n_in_bin < min_points_per_sector:
            continue

        bin_combined = combined_g[bin_mask]
        bin_angles = angles[bin_mask]

        # Overall bin percentile as fallback for sparse sectors
        bin_overall_g = float(np.percentile(bin_combined, percentile))

        # Build per-sector envelope
        envelope = np.empty(n_sectors, dtype=np.float64)
        sector_idx = np.digitize(bin_angles, sector_edges) - 1
        # Clamp sector index: points exactly at pi map to n_sectors, wrap to 0
        sector_idx = np.clip(sector_idx, 0, n_sectors - 1)

        for s in range(n_sectors):
            s_mask = sector_idx == s
            n_in_sector = int(s_mask.sum())
            if n_in_sector >= min_points_per_sector:
                envelope[s] = float(np.percentile(bin_combined[s_mask], percentile))
            else:
                envelope[s] = bin_overall_g

        bin_center = float(bin_edges[b - 1]) + speed_bin_width / 2.0
        valid_speed_bins.append(bin_center)
        valid_envelopes.append(envelope)

    if len(valid_speed_bins) == 0:
        return None

    return GGVSurface(
        speed_bins=np.array(valid_speed_bins, dtype=np.float64),
        envelopes=valid_envelopes,
        n_sectors=n_sectors,
    )


def query_ggv_max_g(
    surface: GGVSurface,
    speed: float,
    angle_rad: float,
) -> float:
    """Query the GGV surface for max available G at a given speed and direction.

    Interpolates between speed bins.  Returns max combined G in the given
    direction.

    Parameters
    ----------
    surface
        A pre-built GGV surface from :func:`build_ggv_surface`.
    speed
        Vehicle speed in m/s.
    angle_rad
        Direction angle in radians where ``0 = pure lateral``,
        ``pi/2 = pure positive longitudinal`` (acceleration),
        ``-pi/2 = pure braking``.  Wraps to ``[-pi, pi]``.

    Returns
    -------
    float
        Maximum combined G available at the given speed and direction.
    """
    n_bins = len(surface.speed_bins)
    n_sectors = surface.n_sectors

    # Wrap angle to [-pi, pi]
    angle = float(np.arctan2(np.sin(angle_rad), np.cos(angle_rad)))

    # Map angle to sector index (fractional for interpolation)
    sector_width = _TWO_PI / n_sectors
    # Shift angle from [-pi, pi] to [0, 2*pi] for indexing
    shifted_angle = angle + np.pi
    sector_frac = shifted_angle / sector_width
    sector_lo = int(sector_frac) % n_sectors
    sector_hi = (sector_lo + 1) % n_sectors
    sector_t = sector_frac - int(sector_frac)

    # Clamp speed to the range of available bins
    if speed <= surface.speed_bins[0]:
        # Below min: use first bin
        env = surface.envelopes[0]
        return float(env[sector_lo] * (1.0 - sector_t) + env[sector_hi] * sector_t)

    if speed >= surface.speed_bins[-1]:
        # Above max: use last bin
        env = surface.envelopes[-1]
        return float(env[sector_lo] * (1.0 - sector_t) + env[sector_hi] * sector_t)

    # Find the two bracketing speed bins for interpolation
    bin_idx = int(np.searchsorted(surface.speed_bins, speed)) - 1
    bin_idx = max(0, min(bin_idx, n_bins - 2))

    speed_lo = float(surface.speed_bins[bin_idx])
    speed_hi = float(surface.speed_bins[bin_idx + 1])
    speed_t = (speed - speed_lo) / (speed_hi - speed_lo) if speed_hi > speed_lo else 0.0

    # Interpolate envelope values at both speed bins
    env_lo = surface.envelopes[bin_idx]
    env_hi = surface.envelopes[bin_idx + 1]

    g_lo = float(env_lo[sector_lo] * (1.0 - sector_t) + env_lo[sector_hi] * sector_t)
    g_hi = float(env_hi[sector_lo] * (1.0 - sector_t) + env_hi[sector_hi] * sector_t)

    # Linear interpolation between speed bins
    return g_lo + speed_t * (g_hi - g_lo)


# ---------------------------------------------------------------------------
# Tire thermal warmup model
# ---------------------------------------------------------------------------


def compute_warmup_factor(
    lap_number: int,
    *,
    cold_factor: float = 0.75,
    warmup_laps: float = 1.5,
) -> float:
    """Compute tire warmup multiplier for a given lap number.

    Lap 1: starts at cold_factor, ramps toward 1.0.
    After warmup_laps: returns 1.0 (tires warm).

    The warmup is modeled as:
        factor = min(1.0, cold_factor + (1 - cold_factor) * lap / warmup_laps)

    Parameters
    ----------
    lap_number
        1-based lap number.
    cold_factor
        Grip multiplier on completely cold tires (lap 0). Default 0.75.
    warmup_laps
        Number of laps to reach full grip. Default 1.5.
        Compound-specific: Street=0.5, 200TW=1.0, R-compound=1.5, Slick=2.5

    Returns
    -------
    float
        Grip multiplier in [cold_factor, 1.0].
    """
    lap = max(0, lap_number)
    return min(1.0, cold_factor + (1.0 - cold_factor) * lap / warmup_laps)


# ---------------------------------------------------------------------------
# Tire load sensitivity model
# ---------------------------------------------------------------------------


def load_sensitive_mu(
    mu_ref: float,
    fz_ref: float,
    fz_actual: float,
    *,
    sensitivity: float = -0.00005,
) -> float:
    """Compute load-sensitive friction coefficient.

    Uses a linear model: mu(Fz) = mu_ref + sensitivity * (Fz_actual - Fz_ref)

    Parameters
    ----------
    mu_ref
        Reference friction coefficient at Fz_ref.
    fz_ref
        Reference vertical load (N).
    fz_actual
        Actual vertical load (N).
    sensitivity
        Load sensitivity coefficient in 1/N, typically -0.00005 per N
        (equivalent to -0.05 per kN).
        mu decreases with more load (load sensitivity).

    Returns
    -------
    float
        Load-sensitive mu, clamped to >= 0.1.
    """
    mu = mu_ref + sensitivity * (fz_actual - fz_ref)
    return max(0.1, mu)

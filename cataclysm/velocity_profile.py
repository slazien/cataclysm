"""Forward-backward velocity solver for physics-optimal speed profiles.

Based on Kapania et al. (2016) — computes the maximum-speed velocity profile
for a given track curvature and vehicle friction model.  The solver:

1. Computes max cornering speed at every distance point from curvature + grip.
2. Forward pass: accelerates from each point subject to available traction.
3. Backward pass: decelerates from each point subject to available traction.
4. Takes the pointwise minimum of all three constraints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from cataclysm.curvature import CurvatureResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

G = 9.81  # m/s^2
MIN_SPEED_MPS = 5.0  # floor speed to avoid singularities


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class VehicleParams:
    """Vehicle grip and performance parameters for the velocity solver.

    When ``wheel_power_w`` and ``mass_kg`` are both > 0, the forward pass
    caps acceleration at ``P / (m * v * g)`` — modelling the power-limited
    regime where engine output, not tire grip, is the bottleneck.  In this
    mode ``max_accel_g`` acts as the low-speed (grip-limited) cap.

    Known simplifications (potential future improvements):
    - NOTE: No tire thermal model — grip doesn't degrade with sustained use or
      change with tire temperature.

    Tire load sensitivity is modelled via a power-law correction on total
    lateral force from an inner/outer tire pair under weight transfer:
        correction = 0.5 * ((1+dLT)^n + (1-dLT)^n)
    where *n* = ``load_sensitivity_exponent`` and dLT = 2 * mu * h_cg / track_w.
    For n < 1.0 the correction is < 1.0 (Jensen's inequality on concave x^n),
    meaning total grip drops under load transfer — always true for real tires.
    """

    mu: float  # overall friction coefficient (G)
    max_accel_g: float  # peak longitudinal accel (G)
    max_decel_g: float  # peak longitudinal decel (G, positive value)
    max_lateral_g: float  # peak lateral accel (G)
    friction_circle_exponent: float = 2.0  # 2.0 = circle, >2 = diamond
    aero_coefficient: float = 0.0  # k in mu_effective = mu + k*v^2
    drag_coefficient: float = 0.0  # k in drag_g = k * v^2 / G (absorbs Cd*A*rho/2m)
    top_speed_mps: float = 80.0  # absolute speed cap
    calibrated: bool = False  # True when params came from observed G-G data
    load_sensitivity_exponent: float = 1.0  # tire load sensitivity (n<1 = mu drops with load)
    cg_height_m: float = 0.0  # CG height for weight transfer estimation
    track_width_m: float = 0.0  # average track width for weight transfer estimation
    wheel_power_w: float = 0.0  # Wheel power in Watts (after drivetrain loss); 0 = disabled
    mass_kg: float = 0.0  # Vehicle mass in kg; 0 = use max_accel_g only
    braking_mu_ratio: float = 1.0  # ratio of peak braking mu to peak lateral mu (>1.0 = ellipse)
    cornering_drag_factor: float = 0.0  # sin(peak_slip_angle) — induced drag from tire slip


@dataclass
class OptimalProfile:
    """Result of the forward-backward velocity solver."""

    distance_m: np.ndarray
    optimal_speed_mps: np.ndarray
    curvature: np.ndarray
    max_cornering_speed_mps: np.ndarray
    optimal_brake_points: list[float]  # distances where braking begins
    optimal_throttle_points: list[float]  # distances where accel begins
    lap_time_s: float
    vehicle_params: VehicleParams


# ---------------------------------------------------------------------------
# Default parameters
# ---------------------------------------------------------------------------


def default_vehicle_params() -> VehicleParams:
    """Return reasonable defaults for a high-performance street car on R-compound tires."""
    return VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.0,
        max_lateral_g=1.0,
        top_speed_mps=80.0,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_max_cornering_speed(
    abs_curvature: np.ndarray,
    params: VehicleParams,
    gradient_sin: np.ndarray | None = None,
    mu_array: np.ndarray | None = None,
    vertical_curvature: np.ndarray | None = None,
) -> np.ndarray:
    """Compute the maximum speed at each point from curvature and grip.

    Base formula (flat, no aero):
        v = sqrt(mu * g / |kappa_lat|)

    With vertical curvature (compression/crest correction):
        N_eff = m·(g·cos(θ) + v²·κ_v)
        v²·|κ_lat| = mu · (g·cos(θ) + v²·κ_v)
        v² = mu·g·cos(θ) / (|κ_lat| - mu·κ_v)

    Compressions (κ_v > 0) shrink the denominator → higher max speed.
    Crests (κ_v < 0) grow the denominator → lower max speed.

    With aero downforce (downforce increases normal force, grip = mu * N):
        v² = mu·g·cos(θ) / (|κ_lat| - mu·κ_v - mu·aero_coeff·G)
    """
    n = len(abs_curvature)
    max_speed = np.full(n, params.top_speed_mps, dtype=np.float64)

    effective_mu_scalar = min(params.mu, params.max_lateral_g)

    if mu_array is not None:
        effective_mu = mu_array.astype(np.float64)
    else:
        effective_mu = np.full(n, effective_mu_scalar, dtype=np.float64)

    # Load sensitivity: total lateral force drops under lateral weight transfer.
    # Tire force model: F_y = mu_ref * Fz_ref * (Fz / Fz_ref)^n, where n < 1.
    # At cornering limit, lateral G ~ mu*g, so lateral load transfer ratio:
    #   dLT = lat_G * h_cg / (0.5 * track_w) = 2 * mu * h_cg / track_w
    # Total force from inner + outer tire pair, normalised by static force:
    #   correction = 0.5 * ((1+dLT)^n + (1-dLT)^n)
    # For n < 1, x^n is concave → correction < 1.0 (Jensen's inequality).
    #
    # For calibrated params (from telemetry), the observed p95 already includes
    # real load-transfer effects.  Applying the full correction would double-count.
    # Instead we apply a RELATIVE correction: how much does load sensitivity vary
    # from the calibration reference condition.  At the reference, the ratio is 1.0;
    # at higher load transfer (fast corners) it drops below 1.0; at lower load
    # transfer (slow corners) it rises above 1.0.
    n_exp = params.load_sensitivity_exponent
    if n_exp < 1.0 and params.track_width_m > 0 and params.cg_height_m > 0:
        dlt = 2.0 * effective_mu * params.cg_height_m / params.track_width_m
        dlt_clamp = np.clip(dlt, 0.0, 0.95)
        correction = 0.5 * (
            np.power(1.0 + dlt_clamp, n_exp) + np.power(np.maximum(1.0 - dlt_clamp, 0.05), n_exp)
        )
        if params.calibrated:
            # Relative correction: normalise by the correction at the calibration
            # condition (where mu = effective_mu_scalar, i.e. the global p95 value).
            dlt_ref = 2.0 * effective_mu_scalar * params.cg_height_m / params.track_width_m
            dlt_ref = min(dlt_ref, 0.95)
            correction_ref = 0.5 * ((1.0 + dlt_ref) ** n_exp + max(1.0 - dlt_ref, 0.05) ** n_exp)
            correction = correction / correction_ref
        effective_mu = effective_mu * correction

    if gradient_sin is not None:
        cos_theta = np.sqrt(np.maximum(1.0 - gradient_sin**2, 0.0))
    else:
        cos_theta = np.ones(n, dtype=np.float64)

    kappa_v = (
        vertical_curvature if vertical_curvature is not None else np.zeros(n, dtype=np.float64)
    )

    curved_mask = abs_curvature > 1e-6

    if params.aero_coefficient > 0:
        curved_indices = np.where(curved_mask)[0]
        # effective denominator = |kappa_lat| - mu*kappa_v - mu*aero*G
        # The mu factor on the aero term is required because downforce
        # increases normal force N, and additional grip = mu * delta_N.
        denom = (
            abs_curvature[curved_indices]
            - effective_mu[curved_indices] * kappa_v[curved_indices]
            - effective_mu[curved_indices] * params.aero_coefficient * G
        )
        # Numerical guard (not a physics limit): vertical curvature must not
        # reduce effective curvature below 50% of lateral curvature.  Prevents
        # LIDAR/GPS altitude noise from dominating the denominator at gentle
        # curves.  Caps aero/compression speed benefit to ~√2 factor.
        denom_floor = 0.5 * abs_curvature[curved_indices]
        denom = np.maximum(denom, denom_floor)
        bounded_mask = denom > 1e-9
        bounded_indices = curved_indices[bounded_mask]
        effective_denom = denom[bounded_mask]
        mu_at_pts = effective_mu[bounded_indices] * cos_theta[bounded_indices]
        max_speed[bounded_indices] = np.sqrt(mu_at_pts * G / effective_denom)
    else:
        curved_indices = np.where(curved_mask)[0]
        # effective denominator = |kappa_lat| - mu*kappa_v
        denom = (
            abs_curvature[curved_indices] - effective_mu[curved_indices] * kappa_v[curved_indices]
        )
        # Floor: same 50% clamp as above
        denom_floor = 0.5 * abs_curvature[curved_indices]
        denom = np.maximum(denom, denom_floor)
        bounded_mask = denom > 1e-9
        bounded_indices = curved_indices[bounded_mask]
        effective_denom = denom[bounded_mask]
        mu_at_pts = effective_mu[bounded_indices] * cos_theta[bounded_indices]
        max_speed[bounded_indices] = np.sqrt(mu_at_pts * G / effective_denom)

    bad_mask = ~np.isfinite(max_speed)
    max_speed[bad_mask] = params.top_speed_mps

    np.clip(max_speed, MIN_SPEED_MPS, params.top_speed_mps, out=max_speed)

    return max_speed


def _available_accel(
    speed: float,
    lateral_g_used: float,
    params: VehicleParams,
    direction: str,
) -> float:
    """Compute available longitudinal G from the friction circle.

    Given current speed and lateral G being used, the remaining longitudinal
    budget follows from the generalised friction circle:

        (lat/max_lat)^p + (lon/max_lon)^p <= 1

    Solving for lon:
        lon = max_lon * (1 - (lat/max_lat)^p) ^ (1/p)
    """
    max_lon_g = params.max_accel_g if direction == "accel" else params.max_decel_g
    exp = params.friction_circle_exponent

    lateral_fraction = (abs(lateral_g_used) / params.max_lateral_g) ** exp
    # Clamp to [0, 1] — if lateral exceeds max, no longitudinal budget remains
    lateral_fraction = min(lateral_fraction, 1.0)

    available: float = max_lon_g * (1.0 - lateral_fraction) ** (1.0 / exp)
    return max(available, 0.0)


def _forward_pass(
    max_speed: np.ndarray,
    step_m: float,
    params: VehicleParams,
    abs_curvature: np.ndarray,
    gradient_sin: np.ndarray | None = None,
    vertical_curvature: np.ndarray | None = None,
) -> np.ndarray:
    """Forward integration: accelerate from each point respecting traction limits.

    If *gradient_sin* is provided, uphill grades (positive) reduce net
    acceleration and downhill grades (negative) assist it.

    If *vertical_curvature* is provided, compressions (positive) increase the
    normal force → more traction budget, crests (negative) decrease it.
    """
    n = len(max_speed)
    v = np.empty(n, dtype=np.float64)
    v[0] = max_speed[0]

    for i in range(1, n):
        v_prev = v[i - 1]
        avg_k = 0.5 * (abs_curvature[i - 1] + abs_curvature[i])
        lateral_g = v_prev**2 * avg_k / G
        accel_g = _available_accel(v_prev, lateral_g, params, "accel")
        # Vertical curvature scales grip-limited traction via normal force:
        # N_eff/N_static = 1 + v²·κ_v/g.  Only affects tire-force budget,
        # not power-limited acceleration (engine doesn't care about normal force).
        if vertical_curvature is not None:
            kv = float(vertical_curvature[i])
            normal_scale = max(1.0 + v_prev**2 * kv / G, 0.1)
            accel_g *= normal_scale
        # Power-limited regime: a = P/(m*v) at high speed
        if params.wheel_power_w > 0 and params.mass_kg > 0 and v_prev > MIN_SPEED_MPS:
            power_accel_g = params.wheel_power_w / (params.mass_kg * v_prev * G)
            accel_g = min(accel_g, power_accel_g)
        drag_g = params.drag_coefficient * v_prev**2 / G
        # Cornering drag: tires at slip angle create induced drag proportional
        # to lateral force used.  F_drag = F_lat * sin(alpha_peak).
        cornering_drag_g = params.cornering_drag_factor * lateral_g
        gradient_g = float(gradient_sin[i]) if gradient_sin is not None else 0.0
        net_accel_g = max(accel_g - drag_g - cornering_drag_g - gradient_g, 0.0)
        v_next_sq = v_prev**2 + 2.0 * net_accel_g * G * step_m
        v_next = np.sqrt(max(v_next_sq, 0.0))
        v[i] = min(v_next, max_speed[i])

    return v


def _backward_pass(
    max_speed: np.ndarray,
    step_m: float,
    params: VehicleParams,
    abs_curvature: np.ndarray,
    gradient_sin: np.ndarray | None = None,
    vertical_curvature: np.ndarray | None = None,
) -> np.ndarray:
    """Backward integration: decelerate from each point respecting traction limits.

    If *gradient_sin* is provided, uphill grades (positive) assist braking
    (going backwards in distance, an uphill is a downhill) and downhill grades
    reduce the effective deceleration budget.

    If *vertical_curvature* is provided, compressions (positive) increase
    the normal force → more braking budget, crests (negative) decrease it.
    """
    n = len(max_speed)
    v = np.empty(n, dtype=np.float64)
    v[-1] = max_speed[-1]

    for i in range(n - 2, -1, -1):
        v_next = v[i + 1]
        avg_k = 0.5 * (abs_curvature[i + 1] + abs_curvature[i])
        lateral_g = v_next**2 * avg_k / G
        decel_g = _available_accel(v_next, lateral_g, params, "decel")
        # Vertical curvature scales traction via normal force
        if vertical_curvature is not None:
            kv = float(vertical_curvature[i])
            normal_scale = max(1.0 + v_next**2 * kv / G, 0.1)
            decel_g *= normal_scale
        drag_g = params.drag_coefficient * v_next**2 / G
        cornering_drag_g = params.cornering_drag_factor * lateral_g
        gradient_g = float(gradient_sin[i]) if gradient_sin is not None else 0.0
        effective_decel_g = decel_g + drag_g + cornering_drag_g + gradient_g
        v_prev_sq = v_next**2 + 2.0 * effective_decel_g * G * step_m
        v_prev = np.sqrt(max(v_prev_sq, 0.0))
        v[i] = min(v_prev, max_speed[i])

    return v


def _find_transitions(
    speed: np.ndarray,
    distance: np.ndarray,
) -> tuple[list[float], list[float]]:
    """Detect braking and throttle transition points in the optimal profile.

    Uses a cumulative speed-change threshold of 0.5 m/s with hysteresis
    to suppress noise from per-sample jitter while detecting sustained
    acceleration or deceleration trends.

    Returns
    -------
    (brake_distances, throttle_distances)
        Lists of distances where braking begins and where acceleration begins.
    """
    threshold = 0.5  # m/s cumulative change to trigger a transition
    brake_points: list[float] = []
    throttle_points: list[float] = []

    if len(speed) < 2:
        return brake_points, throttle_points

    # States: "cruise", "accel", "decel"
    state = "cruise"
    anchor_speed = speed[0]  # speed at the start of the current segment
    anchor_idx = 0

    for i in range(1, len(speed)):
        cumulative_dv = speed[i] - anchor_speed

        if state != "decel" and cumulative_dv < -threshold:
            # Transition into braking
            state = "decel"
            brake_points.append(float(distance[anchor_idx]))
            anchor_speed = speed[i]
            anchor_idx = i
        elif state != "accel" and cumulative_dv > threshold:
            # Transition into acceleration
            state = "accel"
            throttle_points.append(float(distance[anchor_idx]))
            anchor_speed = speed[i]
            anchor_idx = i
        # Note: decel→accel reversal is already handled by the
        # `state != "accel"` branch above (covers both cruise and decel).
        # Similarly, accel→decel reversal is handled by the
        # `state != "decel"` branch (covers both cruise and accel).

        # While in a state, keep updating the anchor to track the extremum
        if state == "decel":
            if speed[i] < anchor_speed:
                anchor_speed = speed[i]
                anchor_idx = i
        elif state == "accel" and speed[i] > anchor_speed:
            anchor_speed = speed[i]
            anchor_idx = i

    return brake_points, throttle_points


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_optimal_profile(
    curvature_result: CurvatureResult,
    params: VehicleParams | None = None,
    *,
    closed_circuit: bool = True,
    gradient_sin: np.ndarray | None = None,
    mu_array: np.ndarray | None = None,
    vertical_curvature: np.ndarray | None = None,
) -> OptimalProfile:
    """Compute the physics-optimal velocity profile for a track.

    Parameters
    ----------
    curvature_result
        Curvature data from :func:`cataclysm.curvature.compute_curvature`.
    params
        Vehicle parameters.  If *None*, :func:`default_vehicle_params` is used.
    closed_circuit
        If *True* (default), treat the track as a closed loop so the solver
        accounts for braking into the start/finish from the end of the lap.
        Uses track tripling: tiles curvature 3x, solves on the tripled
        track, then extracts the middle copy.  If *False*, the track is
        treated as an open circuit (no wrap-around).
    gradient_sin
        Array of sin(theta) values from
        :func:`cataclysm.elevation_profile.compute_gradient_array`.
        Positive = uphill, negative = downhill.  If *None* (default), the
        track is treated as flat (backward compatible).
    mu_array
        Per-point friction coefficient override.  If provided, overrides the
        scalar ``min(params.mu, params.max_lateral_g)`` at each point.
        Points outside corner zones typically keep the global mu.
        If *None* (default), the global scalar mu is used (backward compatible).
    vertical_curvature
        Array of d²z/ds² values from
        :func:`cataclysm.elevation_profile.compute_vertical_curvature`.
        Positive = compression (more grip), negative = crest (less grip).
        If *None* (default), vertical curvature effects are ignored
        (backward compatible).

    Returns
    -------
    OptimalProfile
        Optimal speed at every distance point, transition points, and lap time.
    """
    if params is None:
        params = default_vehicle_params()

    distance = curvature_result.distance_m
    n = len(distance)

    # Compute uniform step size from the distance array
    step_m = float(distance[1] - distance[0]) if n >= 2 else 0.7

    abs_k = curvature_result.abs_curvature

    # Step 1: cornering speed limit at every point
    max_corner_speed = _compute_max_cornering_speed(
        abs_k, params, gradient_sin, mu_array, vertical_curvature
    )

    if closed_circuit and n >= 4:
        # Track tripling: tile curvature and max_speed 3x, solve on the
        # tripled track, then extract the middle copy.  This ensures both
        # the forward pass (correct entry speed) and the backward pass
        # (correct braking into the next lap's first corner) see the
        # wrap-around boundary correctly.
        abs_k_3x = np.tile(abs_k, 3)
        max_speed_3x = np.tile(max_corner_speed, 3)
        gradient_3x = np.tile(gradient_sin, 3) if gradient_sin is not None else None
        kv_3x = np.tile(vertical_curvature, 3) if vertical_curvature is not None else None

        forward_3x = _forward_pass(max_speed_3x, step_m, params, abs_k_3x, gradient_3x, kv_3x)
        backward_3x = _backward_pass(max_speed_3x, step_m, params, abs_k_3x, gradient_3x, kv_3x)

        optimal_3x = np.minimum(np.minimum(forward_3x, backward_3x), max_speed_3x)
        # Extract the middle copy (fully warmed-up from both directions)
        optimal = optimal_3x[n : 2 * n]
    else:
        # Open circuit or too short — no doubling
        forward = _forward_pass(
            max_corner_speed, step_m, params, abs_k, gradient_sin, vertical_curvature
        )
        backward = _backward_pass(
            max_corner_speed, step_m, params, abs_k, gradient_sin, vertical_curvature
        )
        optimal = np.minimum(np.minimum(forward, backward), max_corner_speed)

    # Clamp final result
    np.clip(optimal, MIN_SPEED_MPS, params.top_speed_mps, out=optimal)

    # Step 5: find brake/throttle transition points
    brake_pts, throttle_pts = _find_transitions(optimal, distance)

    # Step 6: estimate lap time via trapezoidal integration of dt = ds / v
    # Uses harmonic mean of endpoint speeds: dt_i = 2*ds / (v_i + v_{i+1})
    lap_time = float(np.sum(2.0 * step_m / (optimal[:-1] + optimal[1:]))) if n >= 2 else 0.0

    return OptimalProfile(
        distance_m=distance,
        optimal_speed_mps=optimal,
        curvature=curvature_result.curvature,
        max_cornering_speed_mps=max_corner_speed,
        optimal_brake_points=brake_pts,
        optimal_throttle_points=throttle_pts,
        lap_time_s=lap_time,
        vehicle_params=params,
    )


# ---------------------------------------------------------------------------
# Speed sensitivity
# ---------------------------------------------------------------------------

# 1 mph in m/s
_ONE_MPH_MPS = 0.44704
# Minimum number of integration points for a meaningful segment
_MIN_SEGMENT_POINTS = 4


def _segment_time(
    entry_speed: float,
    exit_speed: float,
    min_speed: float,
    arc_length: float,
    vehicle: VehicleParams,
    n_points: int = 200,
) -> float:
    """Estimate time through a corner segment using a simplified speed profile.

    Models the corner as three phases:
    1. Deceleration from entry speed to min speed (braking)
    2. Constant speed at min speed through the apex
    3. Acceleration from min speed to exit speed

    The braking and acceleration distances are computed from vehicle
    capabilities.  The remaining distance is traversed at min speed.

    Parameters
    ----------
    entry_speed
        Speed at corner entry (m/s).
    exit_speed
        Speed at corner exit (m/s).
    min_speed
        Minimum speed through the corner apex (m/s).
    arc_length
        Total corner arc length (m).
    vehicle
        Vehicle parameters for accel/decel limits.
    n_points
        Number of integration points for the trapezoidal rule.

    Returns
    -------
    float
        Estimated time through the segment in seconds.
    """
    if arc_length <= 0 or n_points < _MIN_SEGMENT_POINTS:
        return 0.0

    # Clamp min_speed to be no greater than entry/exit
    min_speed = max(min_speed, MIN_SPEED_MPS)
    entry_speed = max(entry_speed, min_speed)
    exit_speed = max(exit_speed, min_speed)

    # Braking distance: v_entry^2 - v_min^2 = 2 * a_brake * d_brake
    # a_brake = max_decel_g * G
    a_brake = vehicle.max_decel_g * G
    if a_brake > 0 and entry_speed > min_speed:
        d_brake = (entry_speed**2 - min_speed**2) / (2.0 * a_brake)
    else:
        d_brake = 0.0

    # Acceleration distance: v_exit^2 - v_min^2 = 2 * a_accel * d_accel
    a_accel = vehicle.max_accel_g * G
    if a_accel > 0 and exit_speed > min_speed:
        d_accel = (exit_speed**2 - min_speed**2) / (2.0 * a_accel)
    else:
        d_accel = 0.0

    # If the braking + accel distance exceeds the arc, scale them down
    total_transition = d_brake + d_accel
    if total_transition > arc_length:
        scale = arc_length / total_transition
        d_brake *= scale
        d_accel *= scale

    d_apex = arc_length - d_brake - d_accel

    # Build a piecewise speed profile over n_points
    ds = arc_length / (n_points - 1)
    speeds = np.empty(n_points, dtype=np.float64)

    for i in range(n_points):
        d = i * ds
        if d <= d_brake and d_brake > 0:
            # Braking phase: v^2 = v_entry^2 - 2*a_brake*d
            v_sq = entry_speed**2 - 2.0 * a_brake * d
            speeds[i] = np.sqrt(max(v_sq, min_speed**2))
        elif d <= d_brake + d_apex:
            # Apex phase: constant min speed
            speeds[i] = min_speed
        else:
            # Acceleration phase: v^2 = v_min^2 + 2*a_accel*(d - d_brake - d_apex)
            d_into_accel = d - d_brake - d_apex
            v_sq = min_speed**2 + 2.0 * a_accel * d_into_accel
            speeds[i] = np.sqrt(max(v_sq, min_speed**2))

    # Trapezoidal integration: dt = ds / v
    # t = sum(2*ds / (v_i + v_{i+1}))
    pair_sums = speeds[:-1] + speeds[1:]
    # Guard against division by zero (should not happen with min_speed clamp)
    pair_sums = np.maximum(pair_sums, 1e-6)
    t = float(np.sum(2.0 * ds / pair_sums))
    return t


def compute_speed_sensitivity(
    corner_entry_speed_mps: float,
    corner_exit_speed_mps: float,
    corner_min_speed_mps: float,
    corner_arc_length_m: float,
    vehicle: VehicleParams,
) -> float:
    """Estimate time saved if minimum corner speed increases by 1 mph.

    Simulates the corner with min_speed and min_speed + 1 mph by building a
    simplified three-phase speed profile (brake -> apex -> accelerate) and
    computing segment time via trapezoidal integration.

    This replaces the generic Bentley approximation (1 mph ~ 0.5 s) with
    a data-grounded, car+track-specific number.

    Parameters
    ----------
    corner_entry_speed_mps
        Speed at corner entry (m/s).
    corner_exit_speed_mps
        Speed at corner exit (m/s).
    corner_min_speed_mps
        Current minimum speed through the corner apex (m/s).
    corner_arc_length_m
        Total arc length of the corner (m).
    vehicle
        Vehicle parameters (accel, decel capabilities).

    Returns
    -------
    float
        Time saved in seconds if min speed increases by 1 mph.
        Always non-negative; returns 0.0 for degenerate inputs.
    """
    if corner_arc_length_m <= 0 or corner_min_speed_mps <= 0:
        return 0.0

    t_current = _segment_time(
        corner_entry_speed_mps,
        corner_exit_speed_mps,
        corner_min_speed_mps,
        corner_arc_length_m,
        vehicle,
    )

    # Increase min speed by 1 mph, but cap at entry/exit speed
    faster_min = corner_min_speed_mps + _ONE_MPH_MPS
    t_faster = _segment_time(
        corner_entry_speed_mps,
        corner_exit_speed_mps,
        faster_min,
        corner_arc_length_m,
        vehicle,
    )

    return max(0.0, t_current - t_faster)

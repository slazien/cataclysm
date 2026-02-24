"""Forward-backward velocity solver for physics-optimal speed profiles.

Based on Kapania et al. (2016) — computes the maximum-speed velocity profile
for a given track curvature and vehicle friction model.  The solver:

1. Computes max cornering speed at every distance point from curvature + grip.
2. Forward pass: accelerates from each point subject to available traction.
3. Backward pass: decelerates from each point subject to available traction.
4. Takes the pointwise minimum of all three constraints.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cataclysm.curvature import CurvatureResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

G = 9.81  # m/s^2
MIN_SPEED_MPS = 5.0  # floor speed to avoid singularities
MPS_TO_MPH = 2.23694


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class VehicleParams:
    """Vehicle grip and performance parameters for the velocity solver."""

    mu: float  # overall friction coefficient (G)
    max_accel_g: float  # peak longitudinal accel (G)
    max_decel_g: float  # peak longitudinal decel (G, positive value)
    max_lateral_g: float  # peak lateral accel (G)
    friction_circle_exponent: float = 2.0  # 2.0 = circle, >2 = diamond
    aero_coefficient: float = 0.0  # k in mu_effective = mu + k*v^2
    top_speed_mps: float = 80.0  # absolute speed cap


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
) -> np.ndarray:
    """Compute the maximum speed at each point from curvature and grip.

    For aero_coefficient == 0:
        v = sqrt(mu * G / |kappa|)

    For aero_coefficient > 0:
        v^2 * (|kappa| - aero_coefficient * G) = mu * G
        v = sqrt(mu * G / (|kappa| - aero_coefficient * G))
        only valid when |kappa| > aero_coefficient * G.
    """
    n = len(abs_curvature)
    max_speed = np.full(n, params.top_speed_mps, dtype=np.float64)

    # Only compute for points with meaningful curvature
    curved_mask = abs_curvature > 1e-6

    if params.aero_coefficient > 0:
        effective_curvature = abs_curvature[curved_mask] - params.aero_coefficient * G
        # Where effective curvature is positive, speed is bounded
        bounded_mask = effective_curvature > 1e-9
        # Build indices: curved points that are also bounded
        curved_indices = np.where(curved_mask)[0]
        bounded_indices = curved_indices[bounded_mask]
        effective_k = effective_curvature[bounded_mask]
        max_speed[bounded_indices] = np.sqrt(params.mu * G / effective_k)
    else:
        max_speed[curved_mask] = np.sqrt(params.mu * G / abs_curvature[curved_mask])

    # Replace any NaN or inf with top_speed
    bad_mask = ~np.isfinite(max_speed)
    max_speed[bad_mask] = params.top_speed_mps

    # Clamp to [MIN_SPEED_MPS, top_speed_mps]
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
) -> np.ndarray:
    """Forward integration: accelerate from each point respecting traction limits."""
    n = len(max_speed)
    v = np.empty(n, dtype=np.float64)
    v[0] = max_speed[0]

    for i in range(1, n):
        v_prev = v[i - 1]
        lateral_g = v_prev**2 * abs_curvature[i - 1] / G
        accel_g = _available_accel(v_prev, lateral_g, params, "accel")
        v_next_sq = v_prev**2 + 2.0 * accel_g * G * step_m
        v_next = np.sqrt(max(v_next_sq, 0.0))
        v[i] = min(v_next, max_speed[i])

    return v


def _backward_pass(
    max_speed: np.ndarray,
    step_m: float,
    params: VehicleParams,
    abs_curvature: np.ndarray,
) -> np.ndarray:
    """Backward integration: decelerate from each point respecting traction limits."""
    n = len(max_speed)
    v = np.empty(n, dtype=np.float64)
    v[-1] = max_speed[-1]

    for i in range(n - 2, -1, -1):
        v_next = v[i + 1]
        lateral_g = v_next**2 * abs_curvature[i + 1] / G
        decel_g = _available_accel(v_next, lateral_g, params, "decel")
        v_prev_sq = v_next**2 + 2.0 * decel_g * G * step_m
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
        elif state == "decel" and cumulative_dv > threshold:
            # Reversed direction while decelerating — now accelerating
            state = "accel"
            throttle_points.append(float(distance[anchor_idx]))
            anchor_speed = speed[i]
            anchor_idx = i
        elif state == "accel" and cumulative_dv < -threshold:
            # Reversed direction while accelerating — now braking
            state = "decel"
            brake_points.append(float(distance[anchor_idx]))
            anchor_speed = speed[i]
            anchor_idx = i

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
) -> OptimalProfile:
    """Compute the physics-optimal velocity profile for a track.

    Parameters
    ----------
    curvature_result
        Curvature data from :func:`cataclysm.curvature.compute_curvature`.
    params
        Vehicle parameters.  If *None*, :func:`default_vehicle_params` is used.

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
    max_corner_speed = _compute_max_cornering_speed(abs_k, params)

    # Step 2: forward pass (acceleration-limited)
    forward = _forward_pass(max_corner_speed, step_m, params, abs_k)

    # Step 3: backward pass (deceleration-limited)
    backward = _backward_pass(max_corner_speed, step_m, params, abs_k)

    # Step 4: pointwise minimum of all three constraints
    optimal = np.minimum(np.minimum(forward, backward), max_corner_speed)

    # Clamp final result
    np.clip(optimal, MIN_SPEED_MPS, params.top_speed_mps, out=optimal)

    # Step 5: find brake/throttle transition points
    brake_pts, throttle_pts = _find_transitions(optimal, distance)

    # Step 6: estimate lap time via trapezoidal integration of dt = ds / v
    lap_time = float(np.sum(step_m / optimal[:-1])) if n >= 2 else 0.0

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

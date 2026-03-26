"""Grip factor sweep: calibration of mu to match actual corner speeds.

Two approaches:
  1. ``sweep_grip_factor`` — fast analytical V = sqrt(F * mu * g / kappa).
  2. ``solver_based_sweep`` — full forward-backward solver binary search.
"""

from __future__ import annotations

from dataclasses import replace as dc_replace

import numpy as np

from cataclysm.curvature import CurvatureResult
from cataclysm.velocity_profile import VehicleParams, compute_optimal_profile

G = 9.81
_F_MIN = 0.80
_F_MAX = 1.25
_F_STEP = 0.005
_OVERSHOOT_PENALTY_WEIGHT = 5.0  # penalize model > actual heavily


def sweep_grip_factor(
    corner_kappa: np.ndarray,
    actual_min_speed_mps: np.ndarray,
    base_mu: float,
    *,
    f_min: float = _F_MIN,
    f_max: float = _F_MAX,
    f_step: float = _F_STEP,
) -> tuple[float, float]:
    """Find the grip factor F that best matches predicted to actual corner speeds.

    Uses analytical approximation: V_max = sqrt(F * mu * g / kappa) per corner.
    This runs in <1ms for any number of candidates (no full solver needed).

    Returns (best_F, best_rmse_mps).
    """
    if len(corner_kappa) == 0:
        return 1.0, 0.0

    # Filter out zero/near-zero curvature (straights)
    valid = corner_kappa > 0.001
    if not valid.any():
        return 1.0, 0.0

    kappa = corner_kappa[valid]
    actual = actual_min_speed_mps[valid]

    candidates = np.arange(f_min, f_max + f_step / 2, f_step)
    best_f = 1.0
    best_score = float("inf")

    for f in candidates:
        predicted = np.sqrt(f * base_mu * G / kappa)
        residuals = predicted - actual
        # RMSE with asymmetric penalty: overshoot (model > actual) is worse
        penalties = np.where(
            residuals > 0,
            residuals * _OVERSHOOT_PENALTY_WEIGHT,
            np.abs(residuals),
        )
        score = float(np.sqrt(np.mean(penalties**2)))
        if score < best_score:
            best_score = score
            best_f = float(f)

    # Compute the unweighted RMSE at best F for reporting
    predicted_best = np.sqrt(best_f * base_mu * G / kappa)
    rmse = float(np.sqrt(np.mean((predicted_best - actual) ** 2)))

    return best_f, rmse


# ---------------------------------------------------------------------------
# Solver-based sweep (binary search on the full velocity solver)
# ---------------------------------------------------------------------------

_OVERSHOOT_WEIGHT = 3.0
_MIN_CURVATURE_THRESHOLD = 0.008


def _solver_corner_rmse(
    curv: CurvatureResult,
    params: VehicleParams,
    corner_apex_distances: np.ndarray,
    actual_min_speeds: np.ndarray,
    mu: float,
    *,
    gradient_sin: np.ndarray | None = None,
    vertical_curvature: np.ndarray | None = None,
) -> float:
    """Run solver at *mu* and return weighted RMSE against actual corner speeds.

    Overshoot (predicted > actual) is penalised 3x to prevent the model
    from claiming the driver can go faster than they actually did.
    """
    adjusted = dc_replace(params, mu=mu, max_lateral_g=mu)
    profile = compute_optimal_profile(
        curv,
        adjusted,
        gradient_sin=gradient_sin,
        vertical_curvature=vertical_curvature,
    )

    errors: list[float] = []
    for apex_d, actual_v in zip(corner_apex_distances, actual_min_speeds, strict=True):
        idx = int(np.searchsorted(curv.distance_m, apex_d))
        idx = min(idx, len(profile.optimal_speed_mps) - 1)
        predicted = float(profile.optimal_speed_mps[idx])
        residual = predicted - actual_v
        if residual > 0:
            errors.append(residual * _OVERSHOOT_WEIGHT)
        else:
            errors.append(abs(residual))

    if not errors:
        return 0.0
    return float(np.sqrt(np.mean(np.array(errors) ** 2)))


def solver_based_sweep(
    curv: CurvatureResult,
    params: VehicleParams,
    corner_apex_distances: np.ndarray,
    actual_min_speeds: np.ndarray,
    *,
    mu_lo: float = 0.7,
    mu_hi: float = 1.5,
    max_iters: int = 2,
    gradient_sin: np.ndarray | None = None,
    vertical_curvature: np.ndarray | None = None,
) -> tuple[float, int]:
    """Find optimal mu via binary search on the full velocity solver.

    Each iteration evaluates 3 candidates (lo, mid, hi) and narrows the
    range around the best.  Converges in 2 iterations (6 solver runs,
    ~48 s).  Results are cached at track level by the caller.

    Returns ``(best_mu, n_iterations)``.
    """
    if len(corner_apex_distances) == 0:
        return params.mu, 0

    # Filter to grip-limited corners (kappa > threshold)
    valid: list[int] = []
    for i, apex_d in enumerate(corner_apex_distances):
        idx = int(np.searchsorted(curv.distance_m, apex_d))
        idx = min(idx, len(curv.abs_curvature) - 1)
        if curv.abs_curvature[idx] > _MIN_CURVATURE_THRESHOLD:
            valid.append(i)

    if not valid:
        return params.mu, 0

    valid_idx = np.array(valid)
    apex_d = corner_apex_distances[valid_idx]
    actual_v = actual_min_speeds[valid_idx]

    lo = max(mu_lo, params.mu * 0.6)
    hi = min(mu_hi, params.mu * 1.3)

    best_mu = params.mu
    best_score = float("inf")
    n_iters = 0

    for _ in range(max_iters):
        n_iters += 1
        mid = (lo + hi) / 2.0
        candidates = [lo, mid, hi]
        scores: list[float] = []
        for mu_c in candidates:
            score = _solver_corner_rmse(
                curv,
                params,
                apex_d,
                actual_v,
                mu_c,
                gradient_sin=gradient_sin,
                vertical_curvature=vertical_curvature,
            )
            scores.append(score)

        best_idx = int(np.argmin(scores))
        if scores[best_idx] < best_score:
            best_score = scores[best_idx]
            best_mu = candidates[best_idx]

        # Narrow search range around best candidate
        if best_idx == 0:
            hi = mid
        elif best_idx == 2:
            lo = mid
        else:
            lo = (lo + mid) / 2
            hi = (mid + hi) / 2

        if hi - lo < 0.02:
            break

    return best_mu, n_iters

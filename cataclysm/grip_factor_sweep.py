"""Grip factor sweep: Michelin-style calibration using analytical corner-limit approximation.

Instead of running the full forward-backward solver (~8s) per candidate,
we use V_max = sqrt(F * mu * g / kappa) per corner to evaluate candidates
in <1ms.  An asymmetric penalty penalises overshoot (model > actual) more
heavily than undershoot, preventing 'impossible' optimal targets.
"""

from __future__ import annotations

import numpy as np

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

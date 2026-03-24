"""Bayesian per-corner capability factor — learns track properties from prediction errors.

The capability factor C adjusts the physics model's cornering speed prediction
per-corner. A value of C > 1 means the corner is faster than the basic model
predicts (e.g., banked turn, favorable camber). C < 1 means slower (e.g.,
off-camber, bumpy surface, poor visibility reducing driver confidence).

This module is pure computation — no database or pipeline dependencies.
"""

from __future__ import annotations

_C_MIN = 0.7
_C_MAX = 1.5
_G = 9.81


def bayesian_update_capability(
    mu_prior: float,
    sigma_prior: float,
    c_obs: float,
    sigma_obs: float,
) -> tuple[float, float]:
    """Normal-Normal conjugate Bayesian update for capability factor C.

    Parameters
    ----------
    mu_prior : float
        Prior mean of the capability factor.
    sigma_prior : float
        Prior standard deviation (uncertainty).
    c_obs : float
        Observed capability factor from telemetry.
    sigma_obs : float
        Observation noise standard deviation.

    Returns
    -------
    tuple[float, float]
        (mu_posterior, sigma_posterior)
    """
    # Clamp observation to physical bounds before update
    c_obs = max(_C_MIN, min(_C_MAX, c_obs))

    # Conjugate normal update: combine prior and observation via precision weighting
    precision_prior = 1.0 / (sigma_prior**2)
    precision_obs = 1.0 / (sigma_obs**2)
    precision_post = precision_prior + precision_obs

    sigma_post = 1.0 / (precision_post**0.5)
    mu_post = (mu_prior * precision_prior + c_obs * precision_obs) / precision_post

    # Clamp posterior mean to physical bounds
    mu_post = max(_C_MIN, min(_C_MAX, mu_post))

    return mu_post, sigma_post


def compute_c_obs(
    actual_speed_mps: float,
    kappa: float,
    mu: float,
) -> float:
    """Compute observed capability factor from actual corner speed.

    Derived from the lateral force balance at the apex:
        v² · κ = C · μ · g
    Solving for C:
        C_obs = (v² · κ) / (μ · g)

    Parameters
    ----------
    actual_speed_mps : float
        Measured apex speed in m/s.
    kappa : float
        Path curvature at the apex in 1/m (must be positive for a real corner).
    mu : float
        Tire friction coefficient (must be positive).

    Returns
    -------
    float
        Observed capability factor. Returns 1.0 for degenerate inputs.
    """
    if kappa <= 0 or mu <= 0:
        return 1.0
    return (actual_speed_mps**2 * kappa) / (mu * _G)

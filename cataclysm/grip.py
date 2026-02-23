"""Robust grip limit estimation from multi-lap telemetry data.

Combines four estimation approaches with accuracy-weighted blending:
1. Multi-lap envelope (99th percentile of total G across all laps)
2. Directional peaks with ellipse fit (captures braking/lateral asymmetry)
3. Speed-dependent grip model (for aero cars)
4. Convex hull envelope (data-driven boundary)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull, QhullError

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MultiLapEnvelopeResult:
    """Result from multi-lap envelope estimation."""

    max_g: float
    n_points: int
    n_laps: int
    percentile: float


@dataclass
class EllipseParams:
    """Fitted ellipse parameters."""

    semi_major: float
    semi_minor: float
    rotation_rad: float
    center_lat_g: float
    center_lon_g: float


@dataclass
class DirectionalPeaksResult:
    """Result from directional peak analysis with ellipse fit."""

    ellipse: EllipseParams
    n_bins: int
    bin_angles: list[float]
    bin_peaks: list[float]
    fit_residual: float
    equivalent_radius: float


@dataclass
class SpeedGripModel:
    """Speed-dependent grip model: max_g(v) = base_grip + k * v^2."""

    base_grip_g: float
    aero_coefficient_k: float
    r_squared: float
    speed_bins: list[float]
    peak_g_per_bin: list[float]
    reference_speed_mps: float
    equivalent_g: float


@dataclass
class ConvexHullResult:
    """Result from convex hull envelope estimation."""

    hull_vertices_lat_g: list[float]
    hull_vertices_lon_g: list[float]
    hull_area: float
    equivalent_radius: float
    n_vertices: int


@dataclass
class GripEstimate:
    """Composite grip estimate from all approaches."""

    multi_lap: MultiLapEnvelopeResult
    directional: DirectionalPeaksResult
    speed_model: SpeedGripModel
    convex_hull: ConvexHullResult
    composite_max_g: float
    envelope_lat_g: list[float]
    envelope_lon_g: list[float]
    weights: dict[str, float]
    metadata: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_BIN_POINTS = 5
DEFAULT_N_BINS = 36
DEFAULT_PERCENTILE = 99.0
DEFAULT_BIN_WIDTH_MPS = 8.94  # ~20 mph
MIN_COMPOSITE_G = 0.3
ENVELOPE_N_POINTS = 360

DEFAULT_WEIGHTS: dict[str, float] = {
    "multi_lap": 0.35,
    "directional": 0.30,
    "speed_model": 0.10,
    "convex_hull": 0.25,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _concat_g_data(
    resampled_laps: dict[int, pd.DataFrame],
    clean_laps: list[int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Concatenate lateral_g, longitudinal_g, and speed_mps from clean laps."""
    lat_parts: list[np.ndarray] = []
    lon_parts: list[np.ndarray] = []
    spd_parts: list[np.ndarray] = []
    for lap_num in clean_laps:
        if lap_num not in resampled_laps:
            continue
        df = resampled_laps[lap_num]
        lat_parts.append(df["lateral_g"].to_numpy())
        lon_parts.append(df["longitudinal_g"].to_numpy())
        spd_parts.append(df["speed_mps"].to_numpy())
    if not lat_parts:
        msg = "No clean laps found in resampled data"
        raise ValueError(msg)
    return (
        np.concatenate(lat_parts),
        np.concatenate(lon_parts),
        np.concatenate(spd_parts),
    )


def _polar_ellipse_radius(
    theta: np.ndarray,
    a: float,
    b: float,
    phi: float,
) -> np.ndarray:
    """Compute polar radius of ellipse at angles theta.

    r(θ) = (a·b) / sqrt((b·cos(θ-φ))² + (a·sin(θ-φ))²)
    """
    cos_term = b * np.cos(theta - phi)
    sin_term = a * np.sin(theta - phi)
    denom = np.sqrt(cos_term**2 + sin_term**2)
    denom = np.maximum(denom, 1e-10)  # avoid division by zero
    return (a * b) / denom


# ---------------------------------------------------------------------------
# Approach 1: Multi-Lap Envelope
# ---------------------------------------------------------------------------


def compute_multi_lap_envelope(
    resampled_laps: dict[int, pd.DataFrame],
    clean_laps: list[int],
    percentile: float = DEFAULT_PERCENTILE,
) -> MultiLapEnvelopeResult:
    """Compute grip limit as Nth percentile of total G across all clean laps."""
    lat_g, lon_g, _ = _concat_g_data(resampled_laps, clean_laps)
    total_g = np.sqrt(lat_g**2 + lon_g**2)
    max_g = float(np.percentile(total_g, percentile))
    n_laps_used = sum(1 for n in clean_laps if n in resampled_laps)
    return MultiLapEnvelopeResult(
        max_g=max_g,
        n_points=len(total_g),
        n_laps=n_laps_used,
        percentile=percentile,
    )


# ---------------------------------------------------------------------------
# Approach 2: Directional Peaks (Ellipse Fit)
# ---------------------------------------------------------------------------


def _fit_ellipse_to_peaks(
    angles: np.ndarray,
    peaks: np.ndarray,
) -> tuple[EllipseParams, float]:
    """Fit polar ellipse to (angle, peak_radius) pairs.

    Returns (EllipseParams, residual).
    """
    # Initial guess: a=median, b=median, phi=0
    median_r = float(np.median(peaks))
    x0 = np.array([median_r, median_r, 0.0])

    def residual_fn(params: np.ndarray) -> np.ndarray:
        a, b, phi = params
        a, b = abs(a), abs(b)
        predicted = _polar_ellipse_radius(angles, a, b, phi)
        return np.asarray(predicted - peaks)

    result = least_squares(
        residual_fn,
        x0,
        bounds=([0.01, 0.01, -np.pi], [10.0, 10.0, np.pi]),
    )
    a, b, phi = float(abs(result.x[0])), float(abs(result.x[1])), float(result.x[2])

    # Convention: semi_major >= semi_minor
    if b > a:
        a, b = b, a
        phi += np.pi / 2

    fit_residual = float(np.sqrt(np.mean(result.fun**2)))

    return (
        EllipseParams(
            semi_major=a,
            semi_minor=b,
            rotation_rad=phi,
            center_lat_g=0.0,
            center_lon_g=0.0,
        ),
        fit_residual,
    )


def compute_directional_peaks(
    resampled_laps: dict[int, pd.DataFrame],
    clean_laps: list[int],
    n_bins: int = DEFAULT_N_BINS,
) -> DirectionalPeaksResult:
    """Compute directional peak G in angular bins and fit an ellipse."""
    lat_g, lon_g, _ = _concat_g_data(resampled_laps, clean_laps)
    total_g = np.sqrt(lat_g**2 + lon_g**2)
    angles_rad = np.arctan2(lon_g, lat_g)  # angle from lateral axis

    bin_edges = np.linspace(-np.pi, np.pi, n_bins + 1)
    bin_centers: list[float] = []
    bin_peaks: list[float] = []

    for i in range(n_bins):
        mask = (angles_rad >= bin_edges[i]) & (angles_rad < bin_edges[i + 1])
        if np.sum(mask) < MIN_BIN_POINTS:
            continue
        bin_centers.append(float((bin_edges[i] + bin_edges[i + 1]) / 2))
        bin_peaks.append(float(np.max(total_g[mask])))

    if len(bin_centers) < 4:
        # Not enough bins — fall back to circle
        overall_max = float(np.percentile(total_g, 99))
        ellipse = EllipseParams(
            semi_major=overall_max,
            semi_minor=overall_max,
            rotation_rad=0.0,
            center_lat_g=0.0,
            center_lon_g=0.0,
        )
        return DirectionalPeaksResult(
            ellipse=ellipse,
            n_bins=len(bin_centers),
            bin_angles=bin_centers,
            bin_peaks=bin_peaks,
            fit_residual=0.0,
            equivalent_radius=overall_max,
        )

    angles_arr = np.array(bin_centers)
    peaks_arr = np.array(bin_peaks)
    ellipse, fit_residual = _fit_ellipse_to_peaks(angles_arr, peaks_arr)
    equivalent_radius = float(np.sqrt(ellipse.semi_major * ellipse.semi_minor))

    return DirectionalPeaksResult(
        ellipse=ellipse,
        n_bins=len(bin_centers),
        bin_angles=bin_centers,
        bin_peaks=bin_peaks,
        fit_residual=fit_residual,
        equivalent_radius=equivalent_radius,
    )


# ---------------------------------------------------------------------------
# Approach 3: Speed-Dependent Grip Model
# ---------------------------------------------------------------------------


def compute_speed_grip_model(
    resampled_laps: dict[int, pd.DataFrame],
    clean_laps: list[int],
    bin_width_mps: float = DEFAULT_BIN_WIDTH_MPS,
) -> SpeedGripModel:
    """Fit max_g(v) = base_grip + k * v² to speed-binned peak G data."""
    lat_g, lon_g, speed = _concat_g_data(resampled_laps, clean_laps)
    total_g = np.sqrt(lat_g**2 + lon_g**2)

    # Bin by speed
    min_speed = float(np.min(speed))
    max_speed = float(np.max(speed))
    bins = np.arange(min_speed, max_speed + bin_width_mps, bin_width_mps)

    speed_centers: list[float] = []
    peak_g_values: list[float] = []

    for i in range(len(bins) - 1):
        mask = (speed >= bins[i]) & (speed < bins[i + 1])
        if np.sum(mask) < MIN_BIN_POINTS:
            continue
        speed_centers.append(float((bins[i] + bins[i + 1]) / 2))
        peak_g_values.append(float(np.percentile(total_g[mask], 99)))

    if len(speed_centers) < 2:
        # Not enough bins for a fit — return flat model
        flat_g = float(np.percentile(total_g, 99))
        median_speed = float(np.median(speed))
        return SpeedGripModel(
            base_grip_g=flat_g,
            aero_coefficient_k=0.0,
            r_squared=0.0,
            speed_bins=speed_centers,
            peak_g_per_bin=peak_g_values,
            reference_speed_mps=median_speed,
            equivalent_g=flat_g,
        )

    speeds_arr = np.array(speed_centers)
    peaks_arr = np.array(peak_g_values)

    # Fit: peak_g = base + k * speed²
    speed_sq = speeds_arr**2
    coeffs = np.polyfit(speed_sq, peaks_arr, 1)
    k = float(coeffs[0])
    base = float(coeffs[1])

    # Clamp k >= 0 (negative is unphysical for aero)
    if k < 0:
        k = 0.0
        base = float(np.mean(peaks_arr))

    # R² calculation
    predicted = base + k * speed_sq
    ss_res = float(np.sum((peaks_arr - predicted) ** 2))
    ss_tot = float(np.sum((peaks_arr - np.mean(peaks_arr)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    median_speed = float(np.median(speed))
    equivalent_g = base + k * median_speed**2

    return SpeedGripModel(
        base_grip_g=base,
        aero_coefficient_k=k,
        r_squared=r_squared,
        speed_bins=speed_centers,
        peak_g_per_bin=peak_g_values,
        reference_speed_mps=median_speed,
        equivalent_g=equivalent_g,
    )


# ---------------------------------------------------------------------------
# Approach 4: Convex Hull Envelope
# ---------------------------------------------------------------------------


def compute_convex_hull(
    resampled_laps: dict[int, pd.DataFrame],
    clean_laps: list[int],
) -> ConvexHullResult:
    """Compute convex hull of G-G data from all clean laps."""
    lat_g, lon_g, _ = _concat_g_data(resampled_laps, clean_laps)

    points = np.column_stack([lat_g, lon_g])

    try:
        hull = ConvexHull(points)
    except QhullError:
        # Degenerate data — fall back to circle based on max total G
        total_g = np.sqrt(lat_g**2 + lon_g**2)
        radius = float(np.max(total_g))
        theta = np.linspace(0, 2 * np.pi, ENVELOPE_N_POINTS, endpoint=False)
        return ConvexHullResult(
            hull_vertices_lat_g=(radius * np.cos(theta)).tolist(),
            hull_vertices_lon_g=(radius * np.sin(theta)).tolist(),
            hull_area=np.pi * radius**2,
            equivalent_radius=radius,
            n_vertices=ENVELOPE_N_POINTS,
        )

    hull_area = float(hull.volume)  # 2D: volume = area
    equivalent_radius = float(np.sqrt(hull_area / np.pi))

    vertices = hull.vertices
    verts_lat = points[vertices, 0].tolist()
    verts_lon = points[vertices, 1].tolist()

    return ConvexHullResult(
        hull_vertices_lat_g=verts_lat,
        hull_vertices_lon_g=verts_lon,
        hull_area=hull_area,
        equivalent_radius=equivalent_radius,
        n_vertices=len(vertices),
    )


# ---------------------------------------------------------------------------
# Weighted Composite
# ---------------------------------------------------------------------------


def _build_composite_envelope(
    directional: DirectionalPeaksResult,
    composite_max_g: float,
    n_points: int = ENVELOPE_N_POINTS,
) -> tuple[list[float], list[float]]:
    """Build envelope from actual directional peaks, scaled to composite magnitude.

    Instead of fitting an ellipse and scaling it (which smooths away real
    directional peaks), this interpolates the measured peak-G at each angle
    and uniformly scales so the mean radius matches ``composite_max_g``.
    This preserves the true shape—including braking peaks that exceed the
    lateral grip—while anchoring the overall magnitude to the consensus.
    """
    if len(directional.bin_angles) < 4:
        # Not enough directional data — fall back to circle
        theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
        lat_g = (composite_max_g * np.cos(theta)).tolist()
        lon_g = (composite_max_g * np.sin(theta)).tolist()
        return lat_g, lon_g

    bin_angles = np.array(directional.bin_angles)
    bin_peaks = np.array(directional.bin_peaks)

    # Sort by angle for interpolation
    order = np.argsort(bin_angles)
    sorted_angles = bin_angles[order]
    sorted_peaks = bin_peaks[order]

    # Interpolate peaks onto a fine uniform grid
    theta = np.linspace(-np.pi, np.pi, n_points, endpoint=False)
    r = np.interp(theta, sorted_angles, sorted_peaks, period=2 * np.pi)

    # Scale so the mean radius matches the composite scalar
    mean_r = float(np.mean(r))
    if mean_r < 1e-6:
        mean_r = 1.0
    r = r * (composite_max_g / mean_r)

    lat_g = (r * np.cos(theta)).tolist()
    lon_g = (r * np.sin(theta)).tolist()
    return lat_g, lon_g


def estimate_grip_limit(
    resampled_laps: dict[int, pd.DataFrame],
    clean_laps: list[int],
    weights: dict[str, float] | None = None,
) -> GripEstimate:
    """Estimate grip limit using all four approaches with weighted blending.

    Parameters
    ----------
    resampled_laps
        Mapping of lap number → resampled DataFrame (from engine.process_session).
    clean_laps
        List of lap numbers to include (typically non-anomalous laps).
    weights
        Optional custom weights dict with keys: multi_lap, directional,
        speed_model, convex_hull. Normalized to sum 1.0.

    Returns
    -------
    GripEstimate with composite result and individual approach results.

    Raises
    ------
    ValueError
        If no clean laps are found in resampled data.
    """
    if weights is None:
        weights = dict(DEFAULT_WEIGHTS)

    # Normalize weights
    total_w = sum(weights.values())
    if total_w > 0:
        weights = {k: v / total_w for k, v in weights.items()}

    # Run all four approaches
    multi_lap = compute_multi_lap_envelope(resampled_laps, clean_laps)
    directional = compute_directional_peaks(resampled_laps, clean_laps)
    speed_model = compute_speed_grip_model(resampled_laps, clean_laps)
    convex_hull = compute_convex_hull(resampled_laps, clean_laps)

    # Weighted composite scalar
    scalars = {
        "multi_lap": multi_lap.max_g,
        "directional": directional.equivalent_radius,
        "speed_model": speed_model.equivalent_g,
        "convex_hull": convex_hull.equivalent_radius,
    }
    composite_max_g = sum(weights[k] * scalars[k] for k in weights)
    composite_max_g = max(composite_max_g, MIN_COMPOSITE_G)

    # Build composite envelope shape from directional peaks
    envelope_lat, envelope_lon = _build_composite_envelope(directional, composite_max_g)

    return GripEstimate(
        multi_lap=multi_lap,
        directional=directional,
        speed_model=speed_model,
        convex_hull=convex_hull,
        composite_max_g=composite_max_g,
        envelope_lat_g=envelope_lat,
        envelope_lon_g=envelope_lon,
        weights=weights,
        metadata={
            "individual_scalars": scalars,
        },
    )

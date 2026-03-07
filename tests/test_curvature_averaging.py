"""Tests for cataclysm.curvature_averaging -- multi-lap curvature averaging."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.curvature import CurvatureResult, _latlon_to_local_xy
from cataclysm.curvature_averaging import (
    average_lap_coordinates,
    compute_averaged_curvature,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CENTER_LAT: float = 33.53
CENTER_LON: float = -86.62


def _circle_lap_df(
    radius_m: float = 100.0,
    n: int = 500,
    fraction: float = 0.8,
    noise_m: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a lap DataFrame tracing a circular arc, optionally with noise.

    Each call with a different *seed* produces independent noise.
    """
    theta = np.linspace(0, 2 * np.pi * fraction, n)
    x = radius_m * np.cos(theta)
    y = radius_m * np.sin(theta)

    if noise_m > 0.0:
        rng = np.random.default_rng(seed)
        x = x + rng.normal(0, noise_m, n)
        y = y + rng.normal(0, noise_m, n)

    cos_lat = np.cos(np.radians(CENTER_LAT))
    lat = CENTER_LAT + y / 111320.0
    lon = CENTER_LON + x / (111320.0 * cos_lat)
    distance = radius_m * theta  # arc length

    return pd.DataFrame(
        {
            "lat": lat,
            "lon": lon,
            "lap_distance_m": distance,
        }
    )


def _reference_xy_on_grid(
    df: pd.DataFrame,
    step_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute the reference XY on the same distance grid that averaging uses.

    Returns (distance_grid, x_interp, y_interp).
    """
    lat = df["lat"].to_numpy(dtype=np.float64)
    lon = df["lon"].to_numpy(dtype=np.float64)
    dist = df["lap_distance_m"].to_numpy(dtype=np.float64)
    x, y = _latlon_to_local_xy(lat, lon)
    grid = np.arange(0.0, dist[-1], step_m)
    return grid, np.interp(grid, dist, x), np.interp(grid, dist, y)


def _xy_from_latlon_with_ref(
    df: pd.DataFrame,
    ref_lat: float,
    ref_lon: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert lat/lon to XY using a specific reference origin."""
    lat = df["lat"].to_numpy(dtype=np.float64)
    lon = df["lon"].to_numpy(dtype=np.float64)
    mean_lat_rad = np.radians(np.mean(lat))
    x = (lon - ref_lon) * np.cos(mean_lat_rad) * 111320.0
    y = (lat - ref_lat) * 111320.0
    return x, y


# ---------------------------------------------------------------------------
# TestAverageLapCoordinates
# ---------------------------------------------------------------------------


class TestAverageLapCoordinates:
    """Tests for the average_lap_coordinates function."""

    def test_single_lap_identical(self) -> None:
        """One lap -> averaged coords should match direct interpolation."""
        df = _circle_lap_df(radius_m=100.0, n=500, fraction=0.8)
        laps = {1: df}

        dist, avg_x, avg_y = average_lap_coordinates(laps, step_m=0.7)

        # Compute the expected result by manual interpolation
        ref_dist, ref_x, ref_y = _reference_xy_on_grid(df, step_m=0.7)

        # Distance grids should match
        np.testing.assert_allclose(dist, ref_dist, atol=1e-10)
        # XY coordinates should match (single lap = no averaging, just interp)
        np.testing.assert_allclose(avg_x, ref_x, atol=1e-6)
        np.testing.assert_allclose(avg_y, ref_y, atol=1e-6)

    def test_multi_lap_reduces_noise(self) -> None:
        """N noisy laps averaged -> coordinates closer to the clean track."""
        n_laps = 10
        radius = 100.0
        noise_m = 0.5
        step_m = 0.7

        # Noisy laps with independent seeds
        laps: dict[int, pd.DataFrame] = {}
        for i in range(n_laps):
            laps[i] = _circle_lap_df(
                radius_m=radius,
                n=500,
                fraction=0.8,
                noise_m=noise_m,
                seed=1000 + i,
            )

        # Clean reference track — use the same reference origin as the
        # implementation will (first lap's first point)
        clean_df = _circle_lap_df(radius_m=radius, n=500, fraction=0.8, noise_m=0.0)
        ref_lat = float(laps[0]["lat"].iloc[0])
        ref_lon = float(laps[0]["lon"].iloc[0])
        ref_x, ref_y = _xy_from_latlon_with_ref(clean_df, ref_lat, ref_lon)
        ref_dist = clean_df["lap_distance_m"].to_numpy()
        ref_grid = np.arange(0.0, ref_dist[-1], step_m)
        ref_x_grid = np.interp(ref_grid, ref_dist, ref_x)
        ref_y_grid = np.interp(ref_grid, ref_dist, ref_y)

        # Single noisy lap deviation from clean track
        _, single_x, single_y = average_lap_coordinates({0: laps[0]}, step_m=step_m)
        n_pts = min(len(ref_x_grid), len(single_x))
        single_err = np.sqrt(
            (single_x[:n_pts] - ref_x_grid[:n_pts]) ** 2
            + (single_y[:n_pts] - ref_y_grid[:n_pts]) ** 2
        )
        single_rmse = float(np.sqrt(np.mean(single_err**2)))

        # Multi-lap averaged deviation from clean track
        _, avg_x, avg_y = average_lap_coordinates(laps, step_m=step_m)
        n_pts = min(len(ref_x_grid), len(avg_x))
        avg_err = np.sqrt(
            (avg_x[:n_pts] - ref_x_grid[:n_pts]) ** 2 + (avg_y[:n_pts] - ref_y_grid[:n_pts]) ** 2
        )
        avg_rmse = float(np.sqrt(np.mean(avg_err**2)))

        # Averaging 10 laps should reduce noise meaningfully (> 1.5x)
        assert avg_rmse < single_rmse / 1.5, (
            f"Multi-lap averaging didn't reduce noise enough: "
            f"single RMSE={single_rmse:.4f} m, avg RMSE={avg_rmse:.4f} m"
        )

    def test_empty_laps_raises(self) -> None:
        """Empty lap dict should raise ValueError."""
        with pytest.raises(ValueError, match="at least one lap"):
            average_lap_coordinates({}, step_m=0.7)

    def test_common_distance_uses_shortest_lap(self) -> None:
        """When laps have different lengths, use the shortest for the grid."""
        short = _circle_lap_df(radius_m=100.0, n=250, fraction=0.4)
        long = _circle_lap_df(radius_m=100.0, n=500, fraction=0.8)

        dist, _, _ = average_lap_coordinates({0: short, 1: long}, step_m=0.7)

        short_max = short["lap_distance_m"].iloc[-1]
        assert dist[-1] < short_max + 0.7


# ---------------------------------------------------------------------------
# TestComputeAveragedCurvature
# ---------------------------------------------------------------------------


class TestComputeAveragedCurvature:
    """Tests for the compute_averaged_curvature function."""

    def test_curvature_preserves_shape(self) -> None:
        """Circular arc + noise -> curvature ~ 1/R after averaging."""
        n_laps = 10
        radius = 100.0
        expected_kappa = 1.0 / radius

        laps: dict[int, pd.DataFrame] = {}
        for i in range(n_laps):
            laps[i] = _circle_lap_df(
                radius_m=radius,
                n=500,
                fraction=0.8,
                noise_m=0.5,
                seed=2000 + i,
            )

        result = compute_averaged_curvature(laps, step_m=0.7)

        assert isinstance(result, CurvatureResult)
        interior = result.curvature[50:-50]
        np.testing.assert_allclose(
            np.abs(interior),
            expected_kappa,
            atol=0.005,
            err_msg=(
                f"Averaged curvature not close to 1/R: "
                f"mean |k|={np.mean(np.abs(interior)):.5f}, "
                f"expected={expected_kappa:.5f}"
            ),
        )

    def test_single_lap_fallback(self) -> None:
        """Single-lap input should still produce a valid CurvatureResult."""
        df = _circle_lap_df(radius_m=100.0, n=500, fraction=0.8)
        result = compute_averaged_curvature({1: df}, step_m=0.7)

        assert isinstance(result, CurvatureResult)
        assert len(result.distance_m) > 0
        assert len(result.curvature) == len(result.distance_m)

    def test_averaged_less_noisy_than_single(self) -> None:
        """Curvature from 10 averaged laps should be smoother than from 1 noisy lap.

        Uses low smoothing (s=0.1) to preserve noise differences that would
        otherwise be masked by heavy spline smoothing.
        """
        n_laps = 10
        radius = 100.0
        expected_kappa = 1.0 / radius

        laps: dict[int, pd.DataFrame] = {}
        for i in range(n_laps):
            laps[i] = _circle_lap_df(
                radius_m=radius,
                n=500,
                fraction=0.8,
                noise_m=0.5,
                seed=3000 + i,
            )

        # Use low smoothing so spline doesn't mask noise differences
        low_s = 0.1

        # Single-lap curvature variance (deviation from expected)
        single_result = compute_averaged_curvature({0: laps[0]}, step_m=0.7, smoothing=low_s)
        single_interior = single_result.curvature[50:-50]
        single_var = float(np.var(np.abs(single_interior) - expected_kappa))

        # Multi-lap averaged curvature variance
        avg_result = compute_averaged_curvature(laps, step_m=0.7, smoothing=low_s)
        avg_interior = avg_result.curvature[50:-50]
        avg_var = float(np.var(np.abs(avg_interior) - expected_kappa))

        assert avg_var < single_var, (
            f"Averaged curvature not smoother: single var={single_var:.8f}, avg var={avg_var:.8f}"
        )

    def test_result_fields_valid(self) -> None:
        """All CurvatureResult fields should be populated with consistent lengths."""
        df = _circle_lap_df(radius_m=80.0, n=400, fraction=0.7)
        result = compute_averaged_curvature({0: df, 1: df}, step_m=0.7)

        n = len(result.distance_m)
        assert n > 0
        assert len(result.curvature) == n
        assert len(result.abs_curvature) == n
        assert len(result.heading_rad) == n
        assert len(result.x_smooth) == n
        assert len(result.y_smooth) == n
        np.testing.assert_array_equal(result.abs_curvature, np.abs(result.curvature))


class TestAverageLapCoordinatesShortTrack:
    """Cover line 91: linspace fallback when distance_grid < MIN_SAMPLES."""

    def test_very_short_lap_uses_linspace_fallback(self) -> None:
        """When the common distance is very short (< MIN_SAMPLES * step_m),
        the code falls back to np.linspace to ensure MIN_SAMPLES points (line 91)."""
        from cataclysm.curvature_averaging import MIN_SAMPLES

        step_m = 0.7
        # Need common_max < MIN_SAMPLES * step_m to trigger linspace fallback
        # MIN_SAMPLES = 20, so common_max < 14.0 m
        # Build a lap of just 8 m arc length
        radius = 20.0
        n = 15
        fraction = 8.0 / (2 * np.pi * radius)  # ~8 m arc
        df = _circle_lap_df(radius_m=radius, n=n, fraction=fraction)

        dist, avg_x, avg_y = average_lap_coordinates({0: df, 1: df}, step_m=step_m)

        # Should have exactly MIN_SAMPLES points due to linspace fallback
        assert len(dist) == MIN_SAMPLES
        assert len(avg_x) == MIN_SAMPLES
        assert len(avg_y) == MIN_SAMPLES

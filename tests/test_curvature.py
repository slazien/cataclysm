"""Tests for cataclysm.curvature."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.curvature import (
    CurvatureResult,
    _latlon_to_local_xy,
    compute_curvature,
    compute_curvature_from_heading,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _circle_lap_df(
    radius_m: float = 100.0,
    n: int = 500,
    fraction: float = 0.8,
    center_lat: float = 33.53,
    center_lon: float = -86.62,
) -> pd.DataFrame:
    """Build a DataFrame whose lat/lon trace a circular arc."""
    theta = np.linspace(0, 2 * np.pi * fraction, n)
    x = radius_m * np.cos(theta)
    y = radius_m * np.sin(theta)

    lat = center_lat + y / 111320.0
    lon = center_lon + x / (111320.0 * np.cos(np.radians(center_lat)))
    distance = radius_m * theta  # arc length

    return pd.DataFrame(
        {
            "lat": lat,
            "lon": lon,
            "lap_distance_m": distance,
        }
    )


def _straight_line_df(
    n: int = 400,
    step_m: float = 0.7,
    bearing_deg: float = 45.0,
) -> pd.DataFrame:
    """Build a DataFrame with lat/lon along a straight line."""
    distance = np.arange(n) * step_m
    bearing_rad = np.radians(bearing_deg)

    # GPS convention: bearing 0=N, 90=E
    dlat_per_m = np.cos(bearing_rad) / 111320.0
    dlon_per_m = np.sin(bearing_rad) / (111320.0 * np.cos(np.radians(33.53)))

    lat = 33.53 + distance * dlat_per_m
    lon = -86.62 + distance * dlon_per_m

    return pd.DataFrame(
        {
            "lat": lat,
            "lon": lon,
            "lap_distance_m": distance,
        }
    )


# ---------------------------------------------------------------------------
# TestLatLonToLocalXY
# ---------------------------------------------------------------------------


class TestLatLonToLocalXY:
    def test_origin_is_zero(self) -> None:
        lat = np.array([33.53, 33.531, 33.532])
        lon = np.array([-86.62, -86.619, -86.618])
        x, y = _latlon_to_local_xy(lat, lon)
        assert x[0] == pytest.approx(0.0)
        assert y[0] == pytest.approx(0.0)

    def test_east_displacement(self) -> None:
        """Moving 1 degree east at the equator should be ~111320 m."""
        lat = np.array([0.0, 0.0])
        lon = np.array([0.0, 1.0])
        x, _y = _latlon_to_local_xy(lat, lon)
        # cos(0) = 1, so x[1] should be ~111320
        assert x[1] == pytest.approx(111320.0, rel=0.01)

    def test_north_displacement(self) -> None:
        """Moving 1 degree north should be ~111320 m."""
        lat = np.array([0.0, 1.0])
        lon = np.array([0.0, 0.0])
        _x, y = _latlon_to_local_xy(lat, lon)
        assert y[1] == pytest.approx(111320.0, rel=0.01)


# ---------------------------------------------------------------------------
# TestComputeCurvature
# ---------------------------------------------------------------------------


class TestComputeCurvature:
    def test_straight_line_zero_curvature(self) -> None:
        """A straight-line track should have curvature very close to zero."""
        df = _straight_line_df(n=400, step_m=0.7)
        result = compute_curvature(df, step_m=0.7)

        assert isinstance(result, CurvatureResult)
        # Trim edges (spline boundary effects)
        interior = result.curvature[20:-20]
        np.testing.assert_allclose(interior, 0.0, atol=0.001)

    def test_circle_curvature(self) -> None:
        """A circular arc of radius R should have curvature ~ 1/R."""
        radius = 100.0
        df = _circle_lap_df(radius_m=radius, n=500, fraction=0.8)
        result = compute_curvature(df, step_m=0.7, smoothing=0.1)

        expected_kappa = 1.0 / radius  # 0.01
        # Trim edges where spline end effects dominate
        interior = result.curvature[50:-50]
        np.testing.assert_allclose(np.abs(interior), expected_kappa, atol=0.005)

    def test_s_curve_sign_changes(self) -> None:
        """An S-curve should produce curvature that changes sign."""
        radius = 100.0
        n_per_arc = 300

        # First arc: left turn (CCW, positive curvature)
        theta1 = np.linspace(0, np.pi * 0.6, n_per_arc)
        x1 = radius * np.sin(theta1)
        y1 = radius * (1 - np.cos(theta1))

        # Second arc: right turn (CW, negative curvature)
        # Start from the end of the first arc, curve the other way
        theta2 = np.linspace(0, np.pi * 0.6, n_per_arc)
        # Center of second circle is offset to produce opposite curvature
        cx2 = x1[-1] + radius * np.sin(theta1[-1])
        cy2 = y1[-1] - radius * (1 - np.cos(theta1[-1]))
        x2 = cx2 - radius * np.sin(theta1[-1] - theta2)
        y2 = cy2 + radius * np.cos(theta1[-1] - theta2)

        x = np.concatenate([x1, x2[1:]])
        y = np.concatenate([y1, y2[1:]])

        # Compute cumulative arc length as the distance array
        dx = np.diff(x)
        dy = np.diff(y)
        seg_len = np.sqrt(dx**2 + dy**2)
        distance = np.concatenate([[0.0], np.cumsum(seg_len)])

        center_lat = 33.53
        lat = center_lat + y / 111320.0
        lon = -86.62 + x / (111320.0 * np.cos(np.radians(center_lat)))

        df = pd.DataFrame(
            {
                "lat": lat,
                "lon": lon,
                "lap_distance_m": distance,
            }
        )

        result = compute_curvature(df, step_m=0.7, smoothing=1.0)

        total = len(result.curvature)
        margin = total // 6
        mid = total // 2

        # First arc interior and second arc interior
        first_section = result.curvature[margin : mid - margin]
        second_section = result.curvature[mid + margin : total - margin]

        mean_first = np.mean(first_section)
        mean_second = np.mean(second_section)
        # They should have opposite signs
        assert mean_first * mean_second < 0, (
            f"Expected opposite signs: first={mean_first:.6f}, second={mean_second:.6f}"
        )

    def test_missing_latlon_raises(self) -> None:
        """DataFrame missing lat/lon should raise ValueError."""
        df = pd.DataFrame(
            {
                "speed_mps": [10.0, 20.0, 30.0],
                "lap_distance_m": [0.0, 0.7, 1.4],
            }
        )
        with pytest.raises(ValueError, match="lat"):
            compute_curvature(df)

    def test_missing_distance_raises(self) -> None:
        """DataFrame missing lap_distance_m should raise ValueError."""
        df = pd.DataFrame(
            {
                "lat": [33.53, 33.531],
                "lon": [-86.62, -86.621],
            }
        )
        with pytest.raises(ValueError, match="lap_distance_m"):
            compute_curvature(df)

    def test_savgol_filter_applied(self) -> None:
        """Result with savgol_window should differ from result without."""
        df = _circle_lap_df(radius_m=100.0, n=500, fraction=0.8)
        result_plain = compute_curvature(df, step_m=0.7, smoothing=0.1)
        result_savgol = compute_curvature(df, step_m=0.7, smoothing=0.1, savgol_window=15)

        # The savgol filter should change the curvature values
        assert not np.allclose(result_plain.curvature, result_savgol.curvature), (
            "Savitzky-Golay filter had no effect on the curvature"
        )

    def test_result_array_lengths(self) -> None:
        """All output arrays should have the same length as the input."""
        n = 300
        df = _circle_lap_df(radius_m=100.0, n=n, fraction=0.5)
        result = compute_curvature(df, step_m=0.7)

        assert len(result.distance_m) == n
        assert len(result.curvature) == n
        assert len(result.abs_curvature) == n
        assert len(result.heading_rad) == n
        assert len(result.x_smooth) == n
        assert len(result.y_smooth) == n

    def test_abs_curvature_is_absolute(self) -> None:
        """abs_curvature should equal |curvature| everywhere."""
        df = _circle_lap_df(radius_m=100.0, n=500, fraction=0.8)
        result = compute_curvature(df, step_m=0.7)
        np.testing.assert_array_equal(result.abs_curvature, np.abs(result.curvature))


# ---------------------------------------------------------------------------
# TestComputeCurvatureFromHeading
# ---------------------------------------------------------------------------


class TestComputeCurvatureFromHeading:
    def test_constant_heading_zero_curvature(self) -> None:
        """Constant heading should produce zero curvature."""
        n = 200
        step_m = 0.7
        distance = np.arange(n) * step_m
        heading = np.full(n, 90.0)  # due east

        result = compute_curvature_from_heading(heading, distance, step_m=step_m)

        np.testing.assert_allclose(result.curvature, 0.0, atol=1e-10)

    def test_turning_heading_nonzero_curvature(self) -> None:
        """Linearly increasing heading should produce nonzero curvature."""
        n = 200
        step_m = 0.7
        distance = np.arange(n) * step_m
        # 0.5 deg/sample = 0.5 / 0.7 deg/m
        heading = np.linspace(0, 100, n)

        result = compute_curvature_from_heading(heading, distance, step_m=step_m)

        # Curvature is d(heading_rad)/d(distance), should be roughly constant
        interior = result.curvature[5:-5]
        expected_rate = np.radians(100.0 / (n * step_m))  # rad/m
        np.testing.assert_allclose(interior, expected_rate, rtol=0.05)

    def test_result_has_reconstructed_xy(self) -> None:
        """Reconstructed x_smooth and y_smooth should have correct length."""
        n = 150
        distance = np.arange(n) * 0.7
        heading = np.full(n, 0.0)

        result = compute_curvature_from_heading(heading, distance)

        assert len(result.x_smooth) == n
        assert len(result.y_smooth) == n
        # Heading 0 = North -> y should increase, x should be ~0
        assert result.y_smooth[-1] > result.y_smooth[0]

    def test_heading_wrap_does_not_spike(self) -> None:
        """Heading wrapping from 359 to 1 should not create curvature spikes."""
        n = 100
        step_m = 0.7
        distance = np.arange(n) * step_m
        # Smooth rotation across the 360/0 boundary
        heading = np.linspace(350, 370, n) % 360

        result = compute_curvature_from_heading(heading, distance, step_m=step_m)

        # Should be smooth, no huge spikes from the wrap
        assert np.max(np.abs(result.curvature)) < 1.0, (
            "Curvature spike detected at heading wrap boundary"
        )

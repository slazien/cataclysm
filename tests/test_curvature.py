"""Tests for cataclysm.curvature."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.curvature import (
    MAX_CURVATURE_RATE,
    MAX_PHYSICAL_CURVATURE,
    CurvatureResult,
    _latlon_to_local_xy,
    _limit_curvature_rate,
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


# ---------------------------------------------------------------------------
# TestPhysicsConstraints — clamp + rate limiter
# ---------------------------------------------------------------------------


class TestCurvatureClamped:
    """Verify that curvature is clamped to the physical maximum."""

    def test_curvature_clamped_to_physical_max(self) -> None:
        """Inject GPS data producing extreme curvature; verify it is clamped."""
        # Build a trace with an artificially tight kink: straight → 1 m
        # radius hairpin → straight.  Curvature of a 1 m radius circle
        # is 1.0 1/m, far above MAX_PHYSICAL_CURVATURE (0.33).
        radius = 1.0  # extremely tight — impossible for a car
        n = 400
        step_m = 0.3  # finer spacing to capture the kink

        # Build: straight 20 m → 180° arc of radius 1 m → straight 20 m
        n_straight = 60
        n_arc = n - 2 * n_straight

        # Straight segment 1 (heading east)
        d1 = np.arange(n_straight) * step_m
        x1 = d1
        y1 = np.zeros(n_straight)

        # Arc segment (semicircle, center at (d1[-1], radius))
        arc_length = np.pi * radius
        theta = np.linspace(0, np.pi, n_arc)
        cx = x1[-1]
        cy = radius
        x_arc = cx + radius * np.sin(theta)
        y_arc = cy - radius * np.cos(theta)
        d_arc = d1[-1] + np.linspace(0, arc_length, n_arc)

        # Straight segment 2 (heading west)
        d2_start = d_arc[-1]
        d2 = d2_start + np.arange(1, n_straight + 1) * step_m
        x2 = x_arc[-1] - np.arange(1, n_straight + 1) * step_m
        y2 = np.full(n_straight, y_arc[-1])

        x = np.concatenate([x1, x_arc, x2])
        y = np.concatenate([y1, y_arc, y2])
        distance = np.concatenate([d1, d_arc, d2])

        center_lat = 33.53
        lat = center_lat + y / 111320.0
        lon = -86.62 + x / (111320.0 * np.cos(np.radians(center_lat)))

        df = pd.DataFrame({"lat": lat, "lon": lon, "lap_distance_m": distance})

        result = compute_curvature(df, step_m=step_m, smoothing=0.01)

        # Every curvature value must be within the physical clamp
        assert np.all(np.abs(result.curvature) <= MAX_PHYSICAL_CURVATURE + 1e-9), (
            f"Curvature exceeded physical max: "
            f"max |k| = {np.max(np.abs(result.curvature)):.4f}, "
            f"limit = {MAX_PHYSICAL_CURVATURE}"
        )

    def test_clamp_does_not_affect_normal_curvature(self) -> None:
        """Normal 100 m radius curvature (0.01) should pass through untouched."""
        df = _circle_lap_df(radius_m=100.0, n=500, fraction=0.8)
        result = compute_curvature(df, step_m=0.7, smoothing=0.1)

        interior = result.curvature[50:-50]
        expected = 1.0 / 100.0
        # Should still be close to the true value — clamp is far above 0.01
        np.testing.assert_allclose(np.abs(interior), expected, atol=0.005)


class TestCurvatureRateLimited:
    """Verify the curvature rate limiter constrains transitions."""

    def test_rate_limiter_unit(self) -> None:
        """Direct test of _limit_curvature_rate on a synthetic spike."""
        n = 100
        step_m = 0.7
        kappa = np.zeros(n, dtype=np.float64)
        # Inject a single massive spike at the midpoint
        kappa[50] = 1.0  # physically impossible jump

        limited = _limit_curvature_rate(kappa, step_m=step_m)

        # No adjacent pair should differ by more than max_rate * step_m
        max_delta = MAX_CURVATURE_RATE * step_m
        diffs = np.abs(np.diff(limited))
        assert np.all(diffs <= max_delta + 1e-12), (
            f"Rate limit violated: max diff = {np.max(diffs):.6f}, allowed = {max_delta:.6f}"
        )

    def test_rate_limited_in_compute_curvature(self) -> None:
        """Full pipeline: verify no adjacent curvature pair exceeds rate limit."""
        df = _circle_lap_df(radius_m=50.0, n=500, fraction=0.8)
        step_m = 0.7
        result = compute_curvature(df, step_m=step_m, smoothing=0.1)

        max_delta = MAX_CURVATURE_RATE * step_m
        diffs = np.abs(np.diff(result.curvature))
        assert np.all(diffs <= max_delta + 1e-12), (
            f"Rate limit violated in full pipeline: "
            f"max diff = {np.max(diffs):.6f}, allowed = {max_delta:.6f}"
        )

    def test_rate_limiter_preserves_sign(self) -> None:
        """Rate limiter should preserve the sign of curvature transitions."""
        n = 100
        step_m = 0.7
        # Smooth positive-then-negative curvature
        kappa = np.concatenate(
            [
                np.linspace(0, 0.05, n // 2),
                np.linspace(0.05, -0.05, n // 2),
            ]
        )

        limited = _limit_curvature_rate(kappa, step_m=step_m)

        # The transition from positive to negative should still happen
        assert np.any(limited > 0) and np.any(limited < 0), (
            "Rate limiter eliminated the sign change entirely"
        )


class TestKnownRadiusAccuracy:
    """Ensure post-processing does not degrade accuracy on clean data."""

    def test_known_radius_accuracy(self) -> None:
        """Circular arc of known radius: curvature should still be close to 1/R."""
        for radius in [30.0, 50.0, 100.0, 200.0]:
            df = _circle_lap_df(radius_m=radius, n=500, fraction=0.8)
            result = compute_curvature(df, step_m=0.7, smoothing=0.1)

            expected = 1.0 / radius
            # Trim edges
            interior = result.curvature[50:-50]
            np.testing.assert_allclose(
                np.abs(interior),
                expected,
                atol=0.005,
                err_msg=(
                    f"Accuracy degraded for R={radius}m: "
                    f"mean |k|={np.mean(np.abs(interior)):.5f}, "
                    f"expected={expected:.5f}"
                ),
            )


# ---------------------------------------------------------------------------
# TestComputeCurvatureFromHeading
# ---------------------------------------------------------------------------


class TestSavgolWindowClampToTraceLength:
    """Cover line 192: win adjusted when win >= len(curvature)."""

    def test_even_length_trace_with_large_savgol_window(self) -> None:
        """When savgol_window >= trace length and trace has even length,
        win should be decremented by 1 (line 192 even branch)."""
        # Build a trace with exactly 10 points (even length)
        radius = 100.0
        n = 10  # even
        df = _circle_lap_df(radius_m=radius, n=n, fraction=0.2)

        # Use a savgol_window much larger than the trace (20 > 10)
        # This triggers: win >= len(curvature) → win = len(curvature) - 1 (since even → subtract 1)
        result = compute_curvature(df, step_m=0.7, smoothing=0.1, savgol_window=20)

        # Should not crash and produce valid output of same length as input
        assert len(result.curvature) == n

    def test_odd_length_trace_with_large_savgol_window(self) -> None:
        """When savgol_window >= trace length and trace has odd length,
        win should stay at len(curvature) (line 192 odd branch)."""
        n = 11  # odd
        df = _circle_lap_df(radius_m=100.0, n=n, fraction=0.2)

        result = compute_curvature(df, step_m=0.7, smoothing=0.1, savgol_window=20)

        assert len(result.curvature) == n


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


# ---------------------------------------------------------------------------
# TestYawRateCurvature
# ---------------------------------------------------------------------------


class TestYawRateCurvature:
    """Tests for compute_yaw_rate_curvature()."""

    def test_basic_constant_radius_turn(self) -> None:
        """Constant yaw rate + constant speed = constant curvature."""
        from cataclysm.curvature import compute_yaw_rate_curvature

        n = 200
        # 50m radius turn at 20 m/s → κ = 1/50 = 0.02 m⁻¹
        # yaw_rate = v * κ = 20 * 0.02 = 0.4 rad/s = 22.92 deg/s
        speed_mps = np.full(n, 20.0)
        yaw_rate_dps = np.full(n, 22.92)
        distance_m = np.linspace(0, 200, n)

        result = compute_yaw_rate_curvature(yaw_rate_dps, speed_mps, distance_m)
        assert result is not None
        # Should be ~0.02 m⁻¹ everywhere (allow 5% tolerance for filtering)
        assert np.abs(np.median(result) - 0.02) < 0.002

    def test_returns_none_when_mostly_nan(self) -> None:
        """Should return None if >80% of yaw_rate values are NaN."""
        from cataclysm.curvature import compute_yaw_rate_curvature

        n = 100
        yaw_rate_dps = np.full(n, np.nan)
        yaw_rate_dps[:10] = 15.0  # only 10% valid
        speed_mps = np.full(n, 25.0)
        distance_m = np.linspace(0, 100, n)

        result = compute_yaw_rate_curvature(yaw_rate_dps, speed_mps, distance_m)
        assert result is None

    def test_low_speed_returns_zero_curvature(self) -> None:
        """At very low speeds, curvature should be zeroed to avoid singularity."""
        from cataclysm.curvature import compute_yaw_rate_curvature

        n = 50
        speed_mps = np.full(n, 2.0)  # 2 m/s = ~7 km/h (pit lane)
        yaw_rate_dps = np.full(n, 10.0)
        distance_m = np.linspace(0, 50, n)

        result = compute_yaw_rate_curvature(yaw_rate_dps, speed_mps, distance_m)
        assert result is not None
        # Should be zero or near-zero at low speed
        assert np.max(np.abs(result)) < 0.005

    def test_returns_none_for_all_nan(self) -> None:
        """Completely NaN yaw_rate array should return None."""
        from cataclysm.curvature import compute_yaw_rate_curvature

        n = 100
        yaw_rate_dps = np.full(n, np.nan)
        speed_mps = np.full(n, 25.0)
        distance_m = np.linspace(0, 100, n)

        result = compute_yaw_rate_curvature(yaw_rate_dps, speed_mps, distance_m)
        assert result is None

    def test_output_length_matches_input(self) -> None:
        """Output array must have the same length as input arrays."""
        from cataclysm.curvature import compute_yaw_rate_curvature

        n = 150
        speed_mps = np.full(n, 30.0)
        yaw_rate_dps = np.full(n, 10.0)
        distance_m = np.linspace(0, 150, n)

        result = compute_yaw_rate_curvature(yaw_rate_dps, speed_mps, distance_m)
        assert result is not None
        assert len(result) == n

    def test_curvature_clamped_to_physical_max(self) -> None:
        """Extreme yaw rate should still be clamped to MAX_PHYSICAL_CURVATURE."""
        from cataclysm.curvature import compute_yaw_rate_curvature

        n = 100
        # 500 deg/s at 10 m/s → raw κ = 8.73/10 = 0.87 — above 0.33 max
        speed_mps = np.full(n, 10.0)
        yaw_rate_dps = np.full(n, 500.0)
        distance_m = np.linspace(0, 100, n)

        result = compute_yaw_rate_curvature(yaw_rate_dps, speed_mps, distance_m)
        assert result is not None
        assert np.all(np.abs(result) <= MAX_PHYSICAL_CURVATURE + 1e-9)

    def test_negative_yaw_rate_produces_negative_curvature(self) -> None:
        """Negative yaw rate (right turn) should produce negative curvature."""
        from cataclysm.curvature import compute_yaw_rate_curvature

        n = 200
        speed_mps = np.full(n, 20.0)
        yaw_rate_dps = np.full(n, -22.92)  # right turn
        distance_m = np.linspace(0, 200, n)

        result = compute_yaw_rate_curvature(yaw_rate_dps, speed_mps, distance_m)
        assert result is not None
        assert np.median(result) < -0.01


# ---------------------------------------------------------------------------
# TestFuseCurvatureSources
# ---------------------------------------------------------------------------


class TestFuseCurvatureSources:
    """Tests for fuse_curvature_sources()."""

    def test_fuse_curvature_prefers_yaw_at_apex(self) -> None:
        """When both sources available, fusion should weight yaw-rate at high-curvature zones."""
        from cataclysm.curvature import fuse_curvature_sources

        n = 100
        distance_m = np.linspace(0, 500, n)
        # GPS curvature: underestimates apex (0.015 instead of 0.02)
        kappa_gps = np.full(n, 0.005)
        kappa_gps[40:60] = 0.015  # GPS apex estimate (too low)
        # Yaw-rate curvature: correct apex (0.02)
        kappa_yaw = np.full(n, 0.005)
        kappa_yaw[40:60] = 0.020  # yaw-rate apex estimate (correct)

        fused = fuse_curvature_sources(kappa_gps, kappa_yaw, distance_m)
        # At apex (indices 40-60), fused should be closer to yaw-rate than GPS
        apex_fused = np.mean(fused[40:60])
        assert apex_fused > 0.017  # closer to 0.02 than 0.015

    def test_fuse_returns_gps_when_yaw_is_none(self) -> None:
        """When yaw-rate is None, should return GPS curvature unchanged."""
        from cataclysm.curvature import fuse_curvature_sources

        n = 50
        kappa_gps = np.random.rand(n) * 0.01
        distance_m = np.linspace(0, 200, n)
        fused = fuse_curvature_sources(kappa_gps, None, distance_m)
        np.testing.assert_array_equal(fused, kappa_gps)

    def test_fuse_output_length_matches_input(self) -> None:
        """Output array length should match input."""
        from cataclysm.curvature import fuse_curvature_sources

        n = 80
        kappa_gps = np.full(n, 0.01)
        kappa_yaw = np.full(n, 0.012)
        distance_m = np.linspace(0, 300, n)
        fused = fuse_curvature_sources(kappa_gps, kappa_yaw, distance_m)
        assert len(fused) == n

    def test_smooth_transition_at_threshold(self) -> None:
        """Weights should transition smoothly, not step, around the threshold.

        A hard step creates a spike in the second derivative of fused curvature
        that is >>10x the background level.  A sigmoid blend keeps the ratio low.
        """
        from cataclysm.curvature import fuse_curvature_sources

        n = 200
        distance_m = np.linspace(0, 500, n)
        # Linearly increasing curvature that sweeps through the threshold
        kappa_gps = np.linspace(0.0, 0.02, n)
        kappa_yaw = np.linspace(0.001, 0.021, n)

        fused = fuse_curvature_sources(kappa_gps, kappa_yaw, distance_m)

        # Second derivative of fused curvature
        dd_fused = np.abs(np.diff(fused, n=2))
        max_dd = float(np.max(dd_fused))
        median_dd = float(np.median(dd_fused[dd_fused > 0]))
        # With a hard step, max_dd / median_dd >> 10.  With sigmoid, ratio < 5.
        ratio = max_dd / median_dd if median_dd > 0 else max_dd
        assert ratio < 5.0, (
            f"Curvature has discontinuity: max_dd={max_dd:.6f}, "
            f"median_dd={median_dd:.6f}, ratio={ratio:.1f}"
        )

"""Tests for cataclysm.elevation_profile."""

from __future__ import annotations

import numpy as np

from cataclysm.elevation_profile import compute_gradient_array

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_distance(n: int, step_m: float = 0.7) -> np.ndarray:
    """Create an evenly spaced distance array."""
    return np.arange(n, dtype=np.float64) * step_m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComputeGradientArray:
    def test_flat_track_zero_gradient(self) -> None:
        """Constant altitude should produce all-zero sin(theta)."""
        n = 500
        distance = _make_distance(n)
        altitude = np.full(n, 100.0)

        gradient_sin = compute_gradient_array(altitude, distance)

        assert gradient_sin.shape == (n,)
        np.testing.assert_allclose(gradient_sin, 0.0, atol=1e-12)

    def test_uphill_positive_gradient(self) -> None:
        """Linearly increasing altitude should produce positive sin(theta)."""
        n = 500
        step_m = 0.7
        distance = _make_distance(n, step_m)
        # 5% grade: rise 0.05 m per 1 m horizontal
        grade = 0.05
        altitude = 100.0 + grade * distance

        gradient_sin = compute_gradient_array(altitude, distance)

        # Interior points (away from boundary effects) should be positive
        interior = gradient_sin[100:-100]
        assert np.all(interior > 0.0)

        # sin(theta) for 5% grade: 0.05 / sqrt(1 + 0.05^2) ~ 0.04994
        expected_sin = grade / np.sqrt(1.0 + grade**2)
        np.testing.assert_allclose(interior, expected_sin, rtol=0.02)

    def test_downhill_negative_gradient(self) -> None:
        """Linearly decreasing altitude should produce negative sin(theta)."""
        n = 500
        step_m = 0.7
        distance = _make_distance(n, step_m)
        grade = -0.05
        altitude = 200.0 + grade * distance

        gradient_sin = compute_gradient_array(altitude, distance)

        interior = gradient_sin[100:-100]
        assert np.all(interior < 0.0)

        expected_sin = grade / np.sqrt(1.0 + grade**2)
        np.testing.assert_allclose(interior, expected_sin, rtol=0.02)

    def test_smoothing_reduces_noise(self) -> None:
        """Noisy altitude data should produce a smooth gradient with low variance."""
        n = 3000
        step_m = 0.7
        distance = _make_distance(n, step_m)

        # Flat track with aggressive noise
        rng = np.random.default_rng(42)
        altitude = 100.0 + rng.normal(0, 3.0, n)

        gradient_sin = compute_gradient_array(altitude, distance)

        # The smoothed gradient should have much lower variance than raw noise
        # Raw gradient std ~ noise_std / (step * sqrt(window_pts)) ~ small
        # With 50m smoothing window, residual should be modest
        interior = gradient_sin[200:-200]
        assert np.std(interior) < 0.10

        # Mean should be near zero (no net elevation change)
        assert abs(np.mean(interior)) < 0.02

    def test_steep_grade_values(self) -> None:
        """10% grade should produce sin(theta) ~ 0.0995."""
        n = 500
        step_m = 0.7
        distance = _make_distance(n, step_m)
        grade = 0.10
        altitude = 50.0 + grade * distance

        gradient_sin = compute_gradient_array(altitude, distance)

        expected_sin = grade / np.sqrt(1.0 + grade**2)  # ~ 0.09950
        interior = gradient_sin[100:-100]
        np.testing.assert_allclose(interior, expected_sin, rtol=0.02)

    def test_empty_array_returns_empty(self) -> None:
        """Empty input arrays should return an empty gradient array."""
        altitude = np.array([], dtype=np.float64)
        distance = np.array([], dtype=np.float64)

        gradient_sin = compute_gradient_array(altitude, distance)

        assert len(gradient_sin) == 0

    def test_single_point_returns_zero(self) -> None:
        """Single-point input should return a single zero."""
        altitude = np.array([100.0])
        distance = np.array([0.0])

        gradient_sin = compute_gradient_array(altitude, distance)

        assert len(gradient_sin) == 1
        assert gradient_sin[0] == 0.0

    def test_all_nan_returns_zero(self) -> None:
        """All-NaN altitude should return all-zero gradient."""
        n = 100
        distance = _make_distance(n)
        altitude = np.full(n, np.nan)

        gradient_sin = compute_gradient_array(altitude, distance)

        np.testing.assert_array_equal(gradient_sin, 0.0)

    def test_partial_nan_handled(self) -> None:
        """NaN values in altitude should be filled without crashing."""
        n = 200
        step_m = 0.7
        distance = _make_distance(n, step_m)
        altitude = np.full(n, 100.0)
        # Inject some NaNs
        altitude[10:20] = np.nan
        altitude[50] = np.nan

        gradient_sin = compute_gradient_array(altitude, distance)

        assert gradient_sin.shape == (n,)
        assert np.all(np.isfinite(gradient_sin))

    def test_custom_smooth_window(self) -> None:
        """Custom smooth_window_m should be respected."""
        # Use a long track so even a 200m window doesn't dominate boundary effects
        n = 2000
        step_m = 0.7
        distance = _make_distance(n, step_m)
        grade = 0.05
        altitude = 100.0 + grade * distance

        # Very large smoothing window
        gradient_sin_smooth = compute_gradient_array(altitude, distance, smooth_window_m=200.0)
        # Very small smoothing window
        gradient_sin_raw = compute_gradient_array(altitude, distance, smooth_window_m=1.0)

        # Both should produce valid results for a linear profile
        # Use generous interior margin (half of total) to avoid boundary effects
        interior_smooth = gradient_sin_smooth[500:-500]
        interior_raw = gradient_sin_raw[100:-100]
        expected = grade / np.sqrt(1.0 + grade**2)

        # Linear profile: both should converge to the same value
        np.testing.assert_allclose(interior_smooth, expected, rtol=0.05)
        np.testing.assert_allclose(interior_raw, expected, rtol=0.05)

    def test_undulating_profile(self) -> None:
        """Sinusoidal altitude should produce sinusoidal gradient."""
        n = 2000
        step_m = 0.7
        distance = _make_distance(n, step_m)
        # Sine wave: 5m amplitude, 200m wavelength
        wavelength = 200.0
        amplitude = 5.0
        altitude = amplitude * np.sin(2 * np.pi * distance / wavelength)

        gradient_sin = compute_gradient_array(altitude, distance)

        # Should alternate between positive and negative
        assert np.any(gradient_sin > 0.01)
        assert np.any(gradient_sin < -0.01)

    def test_output_bounded(self) -> None:
        """sin(theta) should always be in [-1, 1]."""
        n = 500
        step_m = 0.7
        distance = _make_distance(n, step_m)
        # Extreme grade: 100% (45 degrees)
        altitude = distance.copy()  # 1:1 rise over run

        gradient_sin = compute_gradient_array(altitude, distance)

        assert np.all(gradient_sin >= -1.0)
        assert np.all(gradient_sin <= 1.0)

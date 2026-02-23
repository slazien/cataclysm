"""Tests for cataclysm.grip — robust grip limit estimation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.grip import (
    ConvexHullResult,
    DirectionalPeaksResult,
    GripEstimate,
    MultiLapEnvelopeResult,
    SpeedGripModel,
    compute_convex_hull,
    compute_directional_peaks,
    compute_multi_lap_envelope,
    compute_speed_grip_model,
    estimate_grip_limit,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_lap_df(
    n: int = 500,
    lat_g_scale: float = 1.0,
    lon_g_scale: float = 0.8,
    speed_mean: float = 30.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Create a synthetic resampled lap DataFrame with controllable G ranges."""
    rng = np.random.default_rng(seed)
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return pd.DataFrame(
        {
            "lap_distance_m": np.arange(n) * 0.7,
            "lap_time_s": np.arange(n) * 0.025,
            "speed_mps": speed_mean + 5.0 * np.sin(theta) + rng.normal(0, 0.5, n),
            "heading_deg": np.degrees(theta) % 360,
            "lat": 33.53 + np.sin(theta) * 0.001,
            "lon": -86.62 + np.cos(theta) * 0.001,
            "lateral_g": lat_g_scale * np.sin(theta) + rng.normal(0, 0.05, n),
            "longitudinal_g": lon_g_scale * np.cos(theta) + rng.normal(0, 0.05, n),
            "yaw_rate_dps": np.zeros(n),
            "altitude_m": np.full(n, 200.0),
            "x_acc_g": np.zeros(n),
            "y_acc_g": np.zeros(n),
            "z_acc_g": np.ones(n),
        }
    )


@pytest.fixture
def single_lap() -> tuple[dict[int, pd.DataFrame], list[int]]:
    return {1: _make_lap_df(seed=10)}, [1]


@pytest.fixture
def multi_lap() -> tuple[dict[int, pd.DataFrame], list[int]]:
    laps = {
        1: _make_lap_df(seed=10),
        2: _make_lap_df(seed=20),
        3: _make_lap_df(seed=30),
    }
    return laps, [1, 2, 3]


@pytest.fixture
def circular_lap() -> tuple[dict[int, pd.DataFrame], list[int]]:
    """Lap with perfectly circular G-G distribution (equal lat/lon scale)."""
    return {1: _make_lap_df(lat_g_scale=1.0, lon_g_scale=1.0, seed=42)}, [1]


@pytest.fixture
def elliptical_lap() -> tuple[dict[int, pd.DataFrame], list[int]]:
    """Lap with clearly elliptical G-G distribution."""
    return {1: _make_lap_df(lat_g_scale=1.2, lon_g_scale=0.6, seed=42)}, [1]


# ---------------------------------------------------------------------------
# TestMultiLapEnvelope
# ---------------------------------------------------------------------------


class TestMultiLapEnvelope:
    def test_single_lap(self, single_lap: tuple[dict[int, pd.DataFrame], list[int]]) -> None:
        laps, clean = single_lap
        result = compute_multi_lap_envelope(laps, clean)
        assert isinstance(result, MultiLapEnvelopeResult)
        assert result.max_g > 0
        assert result.n_laps == 1
        assert result.n_points == 500

    def test_multi_lap_more_data(
        self, multi_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        laps, clean = multi_lap
        result = compute_multi_lap_envelope(laps, clean)
        assert result.n_laps == 3
        assert result.n_points == 1500

    def test_percentile_affects_result(
        self, single_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        laps, clean = single_lap
        r95 = compute_multi_lap_envelope(laps, clean, percentile=95.0)
        r99 = compute_multi_lap_envelope(laps, clean, percentile=99.0)
        assert r99.max_g >= r95.max_g

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="No clean laps"):
            compute_multi_lap_envelope({}, [1])


# ---------------------------------------------------------------------------
# TestDirectionalPeaks
# ---------------------------------------------------------------------------


class TestDirectionalPeaks:
    def test_circular_data_equal_axes(
        self, circular_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        laps, clean = circular_lap
        result = compute_directional_peaks(laps, clean)
        assert isinstance(result, DirectionalPeaksResult)
        ratio = result.ellipse.semi_major / result.ellipse.semi_minor
        # For nearly circular data, semi-axes should be close (within 50%)
        assert ratio < 1.5

    def test_elliptical_data_asymmetric(
        self, elliptical_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        laps, clean = elliptical_lap
        result = compute_directional_peaks(laps, clean)
        ratio = result.ellipse.semi_major / result.ellipse.semi_minor
        # Elliptical data should show clear asymmetry
        assert ratio > 1.2

    def test_equivalent_radius_positive(
        self, single_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        laps, clean = single_lap
        result = compute_directional_peaks(laps, clean)
        assert result.equivalent_radius > 0


# ---------------------------------------------------------------------------
# TestEllipseFit
# ---------------------------------------------------------------------------


class TestEllipseFit:
    def test_unit_circle_recovery(self) -> None:
        """Fit to unit-circle peaks should recover a ≈ b ≈ 1."""
        from cataclysm.grip import _fit_ellipse_to_peaks

        angles = np.linspace(-np.pi, np.pi, 36, endpoint=False)
        peaks = np.ones(36)  # unit circle
        params, residual = _fit_ellipse_to_peaks(angles, peaks)
        assert abs(params.semi_major - 1.0) < 0.1
        assert abs(params.semi_minor - 1.0) < 0.1
        assert residual < 0.05

    def test_known_ellipse_recovery(self) -> None:
        """Fit to known ellipse should recover correct semi-axes."""
        from cataclysm.grip import _fit_ellipse_to_peaks, _polar_ellipse_radius

        angles = np.linspace(-np.pi, np.pi, 72, endpoint=False)
        true_a, true_b, true_phi = 1.5, 0.8, 0.0
        peaks = _polar_ellipse_radius(angles, true_a, true_b, true_phi)
        params, residual = _fit_ellipse_to_peaks(angles, peaks)
        assert abs(params.semi_major - true_a) < 0.15
        assert abs(params.semi_minor - true_b) < 0.15
        assert residual < 0.1


# ---------------------------------------------------------------------------
# TestSpeedGripModel
# ---------------------------------------------------------------------------


class TestSpeedGripModel:
    def test_constant_speed_k_near_zero(
        self, single_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        """With roughly constant speed, aero coefficient should be ~0."""
        laps, clean = single_lap
        result = compute_speed_grip_model(laps, clean)
        assert isinstance(result, SpeedGripModel)
        assert result.aero_coefficient_k >= 0  # clamped
        assert result.equivalent_g > 0

    def test_increasing_grip_with_speed(self) -> None:
        """Synthetic data where peak G increases with speed² should give k > 0."""
        rng = np.random.default_rng(99)
        n = 2000
        speed = np.linspace(10, 50, n)
        base, k = 0.8, 0.0003
        total_g_target = base + k * speed**2
        # Generate lat/lon G on a circle of that radius
        theta = rng.uniform(-np.pi, np.pi, n)
        lat_g = total_g_target * np.cos(theta) + rng.normal(0, 0.02, n)
        lon_g = total_g_target * np.sin(theta) + rng.normal(0, 0.02, n)
        df = pd.DataFrame(
            {
                "lateral_g": lat_g,
                "longitudinal_g": lon_g,
                "speed_mps": speed,
                "lap_distance_m": np.arange(n) * 0.7,
                "lap_time_s": np.arange(n) * 0.025,
                "heading_deg": np.zeros(n),
                "lat": np.zeros(n),
                "lon": np.zeros(n),
                "yaw_rate_dps": np.zeros(n),
                "altitude_m": np.full(n, 200.0),
                "x_acc_g": np.zeros(n),
                "y_acc_g": np.zeros(n),
                "z_acc_g": np.ones(n),
            }
        )
        result = compute_speed_grip_model({1: df}, [1], bin_width_mps=10.0)
        assert result.aero_coefficient_k > 0
        assert result.r_squared > 0.5


# ---------------------------------------------------------------------------
# TestConvexHull
# ---------------------------------------------------------------------------


class TestConvexHull:
    def test_known_area(self) -> None:
        """Square data should have area ≈ 4 (±hull edge effects)."""
        n = 400
        rng = np.random.default_rng(7)
        lat_g = rng.uniform(-1, 1, n)
        lon_g = rng.uniform(-1, 1, n)
        df = pd.DataFrame(
            {
                "lateral_g": lat_g,
                "longitudinal_g": lon_g,
                "speed_mps": np.full(n, 30.0),
                "lap_distance_m": np.arange(n) * 0.7,
                "lap_time_s": np.arange(n) * 0.025,
                "heading_deg": np.zeros(n),
                "lat": np.zeros(n),
                "lon": np.zeros(n),
                "yaw_rate_dps": np.zeros(n),
                "altitude_m": np.full(n, 200.0),
                "x_acc_g": np.zeros(n),
                "y_acc_g": np.zeros(n),
                "z_acc_g": np.ones(n),
            }
        )
        result = compute_convex_hull({1: df}, [1])
        assert isinstance(result, ConvexHullResult)
        # Square [-1,1]x[-1,1] has area 4
        assert abs(result.hull_area - 4.0) < 0.2
        # equivalent_radius = sqrt(area / pi)
        expected_r = np.sqrt(4.0 / np.pi)
        assert abs(result.equivalent_radius - expected_r) < 0.1

    def test_degenerate_collinear_data(self) -> None:
        """Collinear data should be handled gracefully (QhullError fallback)."""
        n = 50
        df = pd.DataFrame(
            {
                "lateral_g": np.linspace(-1, 1, n),
                "longitudinal_g": np.zeros(n),
                "speed_mps": np.full(n, 30.0),
                "lap_distance_m": np.arange(n) * 0.7,
                "lap_time_s": np.arange(n) * 0.025,
                "heading_deg": np.zeros(n),
                "lat": np.zeros(n),
                "lon": np.zeros(n),
                "yaw_rate_dps": np.zeros(n),
                "altitude_m": np.full(n, 200.0),
                "x_acc_g": np.zeros(n),
                "y_acc_g": np.zeros(n),
                "z_acc_g": np.ones(n),
            }
        )
        result = compute_convex_hull({1: df}, [1])
        assert result.equivalent_radius > 0
        assert result.n_vertices > 0


# ---------------------------------------------------------------------------
# TestCompositeEstimate
# ---------------------------------------------------------------------------


class TestCompositeEstimate:
    def test_composite_within_range(
        self, multi_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        laps, clean = multi_lap
        result = estimate_grip_limit(laps, clean)
        scalars = [
            result.multi_lap.max_g,
            result.directional.equivalent_radius,
            result.speed_model.equivalent_g,
            result.convex_hull.equivalent_radius,
        ]
        assert result.composite_max_g >= min(scalars) * 0.95  # small tolerance
        assert result.composite_max_g <= max(scalars) * 1.05

    def test_custom_weights_respected(
        self, single_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        laps, clean = single_lap
        # 100% weight on multi_lap
        w1 = {"multi_lap": 1.0, "directional": 0.0, "speed_model": 0.0, "convex_hull": 0.0}
        r1 = estimate_grip_limit(laps, clean, weights=w1)
        # 100% weight on directional
        w2 = {"multi_lap": 0.0, "directional": 1.0, "speed_model": 0.0, "convex_hull": 0.0}
        r2 = estimate_grip_limit(laps, clean, weights=w2)
        assert abs(r1.composite_max_g - r1.multi_lap.max_g) < 0.01
        assert abs(r2.composite_max_g - r2.directional.equivalent_radius) < 0.01

    def test_envelope_arrays_same_length(
        self, single_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        laps, clean = single_lap
        result = estimate_grip_limit(laps, clean)
        assert len(result.envelope_lat_g) == len(result.envelope_lon_g)
        assert len(result.envelope_lat_g) == 360


# ---------------------------------------------------------------------------
# TestEstimateGripLimit
# ---------------------------------------------------------------------------


class TestEstimateGripLimit:
    def test_returns_complete_estimate(
        self, multi_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        laps, clean = multi_lap
        result = estimate_grip_limit(laps, clean)
        assert isinstance(result, GripEstimate)
        assert isinstance(result.multi_lap, MultiLapEnvelopeResult)
        assert isinstance(result.directional, DirectionalPeaksResult)
        assert isinstance(result.speed_model, SpeedGripModel)
        assert isinstance(result.convex_hull, ConvexHullResult)
        assert result.composite_max_g > 0

    def test_no_clean_laps_raises(self) -> None:
        with pytest.raises(ValueError, match="No clean laps"):
            estimate_grip_limit({1: _make_lap_df()}, [99])

    def test_single_lap_works(self, single_lap: tuple[dict[int, pd.DataFrame], list[int]]) -> None:
        laps, clean = single_lap
        result = estimate_grip_limit(laps, clean)
        assert result.composite_max_g > 0
        assert result.multi_lap.n_laps == 1

    def test_all_scalars_positive(
        self, multi_lap: tuple[dict[int, pd.DataFrame], list[int]]
    ) -> None:
        laps, clean = multi_lap
        result = estimate_grip_limit(laps, clean)
        assert result.multi_lap.max_g > 0
        assert result.directional.equivalent_radius > 0
        assert result.speed_model.equivalent_g > 0
        assert result.convex_hull.equivalent_radius > 0


# ---------------------------------------------------------------------------
# TestIntegration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_realistic_multi_lap_range(self) -> None:
        """Multi-lap data with realistic G levels should give 0.5-2.5G composite."""
        laps = {i: _make_lap_df(lat_g_scale=1.0, lon_g_scale=0.9, seed=i) for i in range(1, 6)}
        clean = list(range(1, 6))
        result = estimate_grip_limit(laps, clean)
        # Synthetic data peaks around ~1.0-1.3G
        assert 0.5 < result.composite_max_g < 2.5

    def test_weights_sum_to_one(self) -> None:
        laps = {1: _make_lap_df(seed=1)}
        result = estimate_grip_limit(laps, [1])
        assert abs(sum(result.weights.values()) - 1.0) < 1e-6

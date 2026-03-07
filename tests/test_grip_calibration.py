"""Tests for cataclysm.grip_calibration — data-driven grip extraction from G-G data."""

from __future__ import annotations

import numpy as np
import pytest

from cataclysm.corners import Corner
from cataclysm.grip_calibration import (
    CalibratedGrip,
    GGVSurface,
    apply_calibration_to_params,
    build_ggv_surface,
    calibrate_grip_from_telemetry,
    calibrate_per_corner_grip,
    compute_warmup_factor,
    load_sensitive_mu,
    query_ggv_max_g,
)
from cataclysm.velocity_profile import VehicleParams, default_vehicle_params


class TestCalibrateGripFromTelemetry:
    """Tests for calibrate_grip_from_telemetry()."""

    def test_calibrate_from_clean_data(self) -> None:
        """Synthetic G-G data with known max values produces correct calibration."""
        rng = np.random.default_rng(42)
        n = 2000

        # Generate G-G data with known envelopes:
        # lateral ~ uniform(-1.2, 1.2), longitudinal ~ uniform(-1.0, 0.6)
        lateral_g = rng.uniform(-1.2, 1.2, size=n)
        longitudinal_g = rng.uniform(-1.0, 0.6, size=n)

        result = calibrate_grip_from_telemetry(lateral_g, longitudinal_g)

        assert result is not None
        # 99th percentile of |uniform(-1.2, 1.2)| ~ 1.2 * 0.99 = ~1.188
        assert result.max_lateral_g == pytest.approx(1.2, abs=0.05)
        # 99th percentile of |ax| where ax < -0.2 and |ay| < 0.2
        assert result.max_brake_g > 0.5
        assert result.max_accel_g > 0.2
        assert result.confidence in ("high", "medium", "low")

    def test_calibrate_filters_cross_axis(self) -> None:
        """Verifies cross-axis threshold filtering works correctly.

        When measuring braking, only samples with |ay| < threshold should be
        included. Points with high lateral G should be excluded.
        """
        rng = np.random.default_rng(99)

        lateral_g = np.zeros(800)
        longitudinal_g = np.zeros(800)

        # Block 1 (200 pts): coasting — low G on both axes (feeds lateral filter)
        lateral_g[:200] = rng.uniform(-0.8, 0.8, size=200)
        longitudinal_g[:200] = rng.uniform(-0.15, 0.15, size=200)

        # Block 2 (200 pts): straight-line gentle braking (ax ~ -0.3...-0.5, |ay| < 0.1)
        lateral_g[200:400] = rng.uniform(-0.1, 0.1, size=200)
        longitudinal_g[200:400] = rng.uniform(-0.5, -0.3, size=200)

        # Block 3 (200 pts): straight-line acceleration (ax ~ 0.3...0.5, |ay| < 0.1)
        lateral_g[400:600] = rng.uniform(-0.1, 0.1, size=200)
        longitudinal_g[400:600] = rng.uniform(0.3, 0.5, size=200)

        # Block 4 (200 pts): trail-braking with heavy lateral + heavy braking
        lateral_g[600:] = rng.uniform(0.8, 1.2, size=200)
        longitudinal_g[600:] = rng.uniform(-1.5, -1.0, size=200)

        result = calibrate_grip_from_telemetry(lateral_g, longitudinal_g)
        assert result is not None

        # Braking should only reflect the straight-line values (~0.3-0.5G),
        # NOT the trail-braking values (~1.0-1.5G) since those have |ay| > 0.2
        assert result.max_brake_g < 0.6
        assert result.max_brake_g > 0.25

    def test_calibrate_returns_none_insufficient_data(self) -> None:
        """Too few data points returns None."""
        # Only 10 points — below default min_points=20
        lateral_g = np.array([0.5, -0.3, 0.2, -0.1, 0.4, 0.6, -0.5, 0.3, -0.2, 0.1])
        longitudinal_g = np.array([-0.3, -0.5, 0.2, 0.1, -0.4, 0.3, -0.2, 0.4, -0.1, 0.5])

        result = calibrate_grip_from_telemetry(lateral_g, longitudinal_g)
        assert result is None

    def test_calibrate_returns_none_insufficient_braking_data(self) -> None:
        """Returns None when there's enough lateral data but not enough braking data."""
        rng = np.random.default_rng(7)
        n = 200

        # All longitudinal values near zero — no braking or accel events
        lateral_g = rng.uniform(-1.0, 1.0, size=n)
        longitudinal_g = rng.uniform(-0.1, 0.1, size=n)

        result = calibrate_grip_from_telemetry(lateral_g, longitudinal_g)
        assert result is None

    def test_calibrate_uses_percentile_not_max(self) -> None:
        """An outlier spike should be ignored by percentile-based extraction."""
        rng = np.random.default_rng(42)
        n = 2000

        # Normal driving: lateral peaks ~1.0G
        lateral_g = rng.uniform(-1.0, 1.0, size=n)
        longitudinal_g = rng.uniform(-0.8, 0.5, size=n)

        # Inject a massive outlier spike (sensor glitch)
        lateral_g[0] = 5.0
        lateral_g[1] = -5.0

        result = calibrate_grip_from_telemetry(lateral_g, longitudinal_g)
        assert result is not None

        # The 99th percentile should still be near 1.0, not 5.0
        assert result.max_lateral_g < 1.5
        assert result.max_lateral_g > 0.8

    def test_calibrate_custom_percentile(self) -> None:
        """Custom percentile parameter is respected."""
        rng = np.random.default_rng(42)
        n = 2000

        lateral_g = rng.uniform(-1.2, 1.2, size=n)
        longitudinal_g = rng.uniform(-1.0, 0.6, size=n)

        result_99 = calibrate_grip_from_telemetry(lateral_g, longitudinal_g, percentile=99.0)
        result_90 = calibrate_grip_from_telemetry(lateral_g, longitudinal_g, percentile=90.0)

        assert result_99 is not None
        assert result_90 is not None
        # 99th percentile should be higher than 90th
        assert result_99.max_lateral_g > result_90.max_lateral_g

    def test_calibrate_custom_cross_axis_threshold(self) -> None:
        """Custom cross_axis_threshold parameter is respected."""
        rng = np.random.default_rng(42)
        n = 2000

        lateral_g = rng.uniform(-1.2, 1.2, size=n)
        longitudinal_g = rng.uniform(-1.0, 0.6, size=n)

        # Tight threshold: only nearly-straight-line data
        result_tight = calibrate_grip_from_telemetry(
            lateral_g, longitudinal_g, cross_axis_threshold=0.05
        )
        # Loose threshold: more data included
        result_loose = calibrate_grip_from_telemetry(
            lateral_g, longitudinal_g, cross_axis_threshold=0.5
        )

        assert result_tight is not None
        assert result_loose is not None
        # With looser threshold, more data points qualify
        assert result_loose.point_count >= result_tight.point_count

    def test_calibrate_empty_arrays(self) -> None:
        """Empty input arrays return None."""
        result = calibrate_grip_from_telemetry(np.array([]), np.array([]))
        assert result is None

    def test_calibrate_min_points_parameter(self) -> None:
        """Custom min_points threshold is respected."""
        rng = np.random.default_rng(42)

        # Build data with guaranteed points in each regime
        lateral_g = np.zeros(150)
        longitudinal_g = np.zeros(150)

        # 50 pts: coasting (feeds lateral filter: |lon_g| < 0.2)
        lateral_g[:50] = rng.uniform(-0.8, 0.8, size=50)
        longitudinal_g[:50] = rng.uniform(-0.1, 0.1, size=50)

        # 50 pts: straight-line braking (feeds brake filter)
        lateral_g[50:100] = rng.uniform(-0.1, 0.1, size=50)
        longitudinal_g[50:100] = rng.uniform(-0.8, -0.3, size=50)

        # 50 pts: straight-line acceleration (feeds accel filter)
        lateral_g[100:150] = rng.uniform(-0.1, 0.1, size=50)
        longitudinal_g[100:150] = rng.uniform(0.3, 0.6, size=50)

        # With min_points=100, ~50 points per axis bucket should fail
        result_strict = calibrate_grip_from_telemetry(lateral_g, longitudinal_g, min_points=100)
        # With min_points=5, should succeed
        result_lenient = calibrate_grip_from_telemetry(lateral_g, longitudinal_g, min_points=5)

        assert result_strict is None
        assert result_lenient is not None


class TestCalibrateGripInsufficientAccelData:
    """Cover line 147: return None when accel data is insufficient."""

    def test_returns_none_when_only_accel_data_missing(self) -> None:
        """Sufficient lateral and braking data, but no acceleration events → None."""
        rng = np.random.default_rng(999)
        n = 300

        # Block 1: coasting — sufficient lateral data (feeds lat_mask)
        lateral_g = np.zeros(n)
        longitudinal_g = np.zeros(n)

        # 150 pts: coasting with lateral variation, |lon_g| < 0.2
        lateral_g[:150] = rng.uniform(-1.0, 1.0, size=150)
        longitudinal_g[:150] = rng.uniform(-0.1, 0.1, size=150)

        # 150 pts: straight-line braking, |lat_g| < 0.2 AND lon_g < -0.2
        lateral_g[150:] = rng.uniform(-0.1, 0.1, size=150)
        longitudinal_g[150:] = rng.uniform(-1.0, -0.3, size=150)

        # No acceleration events at all — accel_mask will be empty → line 147
        result = calibrate_grip_from_telemetry(lateral_g, longitudinal_g)

        assert result is None


class TestBuildGGVSurfaceEmptyBins:
    """Cover line 392: return None when no valid speed bins exist."""

    def test_returns_none_when_all_bins_have_too_few_points(self) -> None:
        """With enough total points but min_points_per_sector exceeds total data,
        every speed bin is skipped and valid_speed_bins is empty (line 392)."""
        rng = np.random.default_rng(42)
        # 100 total points (>= _MIN_GGV_TOTAL_POINTS=50), passes the early guard.
        # Set min_points_per_sector=101 so no single bin can ever reach the threshold
        # (we only have 100 points total across all bins).
        n = 100
        speed_mps = rng.uniform(10.0, 30.0, size=n)  # default 5 m/s bins → ~4 bins
        lat_g = rng.uniform(-1.0, 1.0, size=n)
        lon_g = rng.uniform(-0.8, 0.5, size=n)

        result = build_ggv_surface(speed_mps, lat_g, lon_g, min_points_per_sector=101)

        assert result is None


class TestConfidenceLevels:
    """Tests for confidence classification in CalibratedGrip."""

    @staticmethod
    def _make_regime_data(
        n_per_regime: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate G-G data with exactly n_per_regime points per axis bucket.

        Creates three blocks: coasting (lateral), braking, acceleration,
        each designed to pass the cross-axis filter cleanly.
        """
        rng = np.random.default_rng(42)
        n = n_per_regime * 3

        lateral_g = np.zeros(n)
        longitudinal_g = np.zeros(n)

        # Block 1: coasting — |lon_g| < 0.2 (feeds lateral filter)
        lateral_g[:n_per_regime] = rng.uniform(-1.0, 1.0, size=n_per_regime)
        longitudinal_g[:n_per_regime] = rng.uniform(-0.1, 0.1, size=n_per_regime)

        # Block 2: straight-line braking — ax < -0.2, |ay| < 0.2
        lateral_g[n_per_regime : 2 * n_per_regime] = rng.uniform(-0.1, 0.1, size=n_per_regime)
        longitudinal_g[n_per_regime : 2 * n_per_regime] = rng.uniform(-1.0, -0.3, size=n_per_regime)

        # Block 3: straight-line accel — ax > 0.2, |ay| < 0.2
        lateral_g[2 * n_per_regime :] = rng.uniform(-0.1, 0.1, size=n_per_regime)
        longitudinal_g[2 * n_per_regime :] = rng.uniform(0.3, 0.6, size=n_per_regime)

        return lateral_g, longitudinal_g

    def test_high_confidence(self) -> None:
        """High confidence when >500 points per axis."""
        lat_g, lon_g = self._make_regime_data(600)
        result = calibrate_grip_from_telemetry(lat_g, lon_g)
        assert result is not None
        assert result.confidence == "high"
        assert result.point_count > 500

    def test_medium_confidence(self) -> None:
        """Medium confidence when 100-500 points per axis."""
        lat_g, lon_g = self._make_regime_data(200)
        result = calibrate_grip_from_telemetry(lat_g, lon_g)
        assert result is not None
        assert result.confidence == "medium"
        assert 100 < result.point_count <= 500

    def test_low_confidence(self) -> None:
        """Low confidence when <=100 points per axis."""
        lat_g, lon_g = self._make_regime_data(50)
        result = calibrate_grip_from_telemetry(lat_g, lon_g)
        assert result is not None
        assert result.confidence == "low"
        assert result.point_count <= 100


class TestApplyCalibrationToParams:
    """Tests for apply_calibration_to_params()."""

    def test_apply_calibration_overrides_params(self) -> None:
        """Verify that VehicleParams fields are updated from CalibratedGrip."""
        base = default_vehicle_params()
        grip = CalibratedGrip(
            max_lateral_g=1.3,
            max_brake_g=1.1,
            max_accel_g=0.7,
            point_count=1000,
            confidence="high",
        )

        result = apply_calibration_to_params(base, grip)

        assert result.max_lateral_g == 1.3
        assert result.max_decel_g == 1.1
        assert result.max_accel_g == 0.7
        assert result.mu == max(1.3, 1.1)  # max of lateral and brake
        assert result.calibrated is True

    def test_apply_calibration_preserves_equipment_fields(self) -> None:
        """Aero, drag, top_speed, and friction_circle_exponent are preserved."""
        base = VehicleParams(
            mu=0.9,
            max_accel_g=0.4,
            max_decel_g=0.85,
            max_lateral_g=0.9,
            aero_coefficient=0.002,
            drag_coefficient=0.001,
            top_speed_mps=70.0,
            friction_circle_exponent=2.5,
            load_sensitivity_exponent=0.92,
            cg_height_m=0.48,
            track_width_m=1.62,
            wheel_power_w=180_000.0,
            mass_kg=1_420.0,
        )
        grip = CalibratedGrip(
            max_lateral_g=1.1,
            max_brake_g=0.95,
            max_accel_g=0.55,
            point_count=800,
            confidence="high",
        )

        result = apply_calibration_to_params(base, grip)

        # Grip fields overridden
        assert result.max_lateral_g == 1.1
        assert result.max_decel_g == 0.95
        assert result.max_accel_g == 0.55
        assert result.mu == max(1.1, 0.95)
        assert result.calibrated is True

        # Equipment-derived fields preserved
        assert result.aero_coefficient == 0.002
        assert result.drag_coefficient == 0.001
        assert result.top_speed_mps == 70.0
        assert result.friction_circle_exponent == 2.5
        assert result.load_sensitivity_exponent == 0.92
        assert result.cg_height_m == 0.48
        assert result.track_width_m == 1.62
        assert result.wheel_power_w == 180_000.0
        assert result.mass_kg == 1_420.0

    def test_apply_calibration_mu_from_max_of_lateral_and_brake(self) -> None:
        """mu should be max(max_lateral_g, max_brake_g)."""
        base = default_vehicle_params()

        # Case 1: brake > lateral
        grip1 = CalibratedGrip(
            max_lateral_g=0.8,
            max_brake_g=1.2,
            max_accel_g=0.5,
            point_count=1000,
            confidence="high",
        )
        result1 = apply_calibration_to_params(base, grip1)
        assert result1.mu == 1.2

        # Case 2: lateral > brake
        grip2 = CalibratedGrip(
            max_lateral_g=1.4,
            max_brake_g=1.0,
            max_accel_g=0.5,
            point_count=1000,
            confidence="high",
        )
        result2 = apply_calibration_to_params(base, grip2)
        assert result2.mu == 1.4

    def test_calibration_never_lowers_below_base(self) -> None:
        """Observed grip below base params should not reduce the solver's limits."""
        base = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
        )
        grip = CalibratedGrip(
            max_lateral_g=0.85,  # driver below car's capability
            max_brake_g=0.9,
            max_accel_g=0.4,
            point_count=500,
            confidence="medium",
        )

        result = apply_calibration_to_params(base, grip)

        # Should keep base values since they're higher
        assert result.max_lateral_g == 1.0
        assert result.max_decel_g == 1.0
        assert result.max_accel_g == 0.5
        assert result.mu == 1.0
        assert result.calibrated is True


class TestVehicleParamsCalibratedField:
    """Test that VehicleParams has the calibrated field."""

    def test_default_calibrated_false(self) -> None:
        """Default VehicleParams should have calibrated=False."""
        params = default_vehicle_params()
        assert params.calibrated is False

    def test_calibrated_field_in_dataclass(self) -> None:
        """VehicleParams can be created with calibrated=True."""
        params = VehicleParams(
            mu=1.0,
            max_accel_g=0.5,
            max_decel_g=1.0,
            max_lateral_g=1.0,
            calibrated=True,
        )
        assert params.calibrated is True


# ---------------------------------------------------------------------------
# Helpers for per-corner tests
# ---------------------------------------------------------------------------


def _make_corner(
    number: int,
    entry_m: float,
    exit_m: float,
    apex_m: float | None = None,
) -> Corner:
    """Create a minimal Corner for testing per-corner grip."""
    if apex_m is None:
        apex_m = (entry_m + exit_m) / 2
    return Corner(
        number=number,
        entry_distance_m=entry_m,
        exit_distance_m=exit_m,
        apex_distance_m=apex_m,
        min_speed_mps=20.0,
        brake_point_m=None,
        peak_brake_g=None,
        throttle_commit_m=None,
        apex_type="mid",
    )


# ---------------------------------------------------------------------------
# TestCalibratePerCornerGrip
# ---------------------------------------------------------------------------


class TestCalibratePerCornerGrip:
    """Tests for calibrate_per_corner_grip()."""

    def test_per_corner_grip_extraction(self) -> None:
        """Synthetic data with different lat-G per corner zone gives per-corner mu."""
        # Track: 0 to 1000m.  Two corners:
        #   Corner 1: 100-300m  (high grip zone, |lat_g| ~ 1.2)
        #   Corner 2: 600-800m  (low grip zone, |lat_g| ~ 0.6)
        n = 1500  # points at 0.7m spacing → ~1050m
        step_m = 0.7
        distance_m = np.arange(n) * step_m

        # Background lateral G is ~0.3 everywhere
        rng = np.random.default_rng(42)
        lateral_g = rng.uniform(-0.3, 0.3, size=n)

        # Corner 1 zone: indices for distance 100-300m → indices ~143-429
        c1_mask = (distance_m >= 100.0) & (distance_m <= 300.0)
        lateral_g[c1_mask] = rng.choice([-1, 1], size=int(c1_mask.sum())) * rng.uniform(
            1.0, 1.3, size=int(c1_mask.sum())
        )

        # Corner 2 zone: indices for distance 600-800m → indices ~857-1143
        c2_mask = (distance_m >= 600.0) & (distance_m <= 800.0)
        lateral_g[c2_mask] = rng.choice([-1, 1], size=int(c2_mask.sum())) * rng.uniform(
            0.4, 0.7, size=int(c2_mask.sum())
        )

        corners = [
            _make_corner(1, 100.0, 300.0),
            _make_corner(2, 600.0, 800.0),
        ]

        result = calibrate_per_corner_grip(lateral_g, distance_m, corners)

        # Both corners should be present
        assert 1 in result
        assert 2 in result

        # Corner 1 should have higher mu than corner 2
        assert result[1] > result[2]

        # Corner 1: 99th percentile of |lat_g| in [1.0, 1.3] → should be ~1.2+
        assert result[1] > 0.9

        # Corner 2: 99th percentile of |lat_g| in [0.4, 0.7] → should be ~0.65
        assert result[2] < 0.8
        assert result[2] > 0.3

    def test_per_corner_grip_min_points_filter(self) -> None:
        """Corners with too few points are excluded from the result."""
        n = 200
        step_m = 0.7
        distance_m = np.arange(n) * step_m
        # Total distance ~ 140m

        rng = np.random.default_rng(99)
        lateral_g = rng.uniform(-1.0, 1.0, size=n)

        # Corner 1: 10-100m → has many points (~129 at 0.7m step)
        # Corner 2: 120-125m → only ~7 points (too few for default min_points=10)
        corners = [
            _make_corner(1, 10.0, 100.0),
            _make_corner(2, 120.0, 125.0),
        ]

        result = calibrate_per_corner_grip(lateral_g, distance_m, corners, min_points=10)

        # Corner 1 should be present (many points)
        assert 1 in result
        # Corner 2 should be excluded (too few points)
        assert 2 not in result

    def test_per_corner_grip_empty_corners(self) -> None:
        """Empty corners list returns empty dict."""
        distance_m = np.arange(100) * 0.7
        lateral_g = np.ones(100) * 0.5

        result = calibrate_per_corner_grip(lateral_g, distance_m, [])
        assert result == {}

    def test_per_corner_grip_custom_percentile(self) -> None:
        """Custom percentile parameter is respected."""
        n = 500
        step_m = 0.7
        distance_m = np.arange(n) * step_m

        rng = np.random.default_rng(42)
        lateral_g = rng.uniform(-1.0, 1.0, size=n)

        corners = [_make_corner(1, 10.0, 300.0)]

        result_99 = calibrate_per_corner_grip(lateral_g, distance_m, corners, percentile=99.0)
        result_50 = calibrate_per_corner_grip(lateral_g, distance_m, corners, percentile=50.0)

        assert 1 in result_99
        assert 1 in result_50
        # 99th percentile should be higher than 50th
        assert result_99[1] > result_50[1]


# ---------------------------------------------------------------------------
# GGV Surface Tests
# ---------------------------------------------------------------------------


class TestBuildGGVSurface:
    """Tests for build_ggv_surface()."""

    def test_ggv_surface_from_synthetic_data(self) -> None:
        """Constant capability across all speeds produces a uniform surface.

        Generates G-G data at uniform random speeds with constant combined-G
        magnitude ~1.0G in all directions.  The surface should show roughly
        equal envelope values across all speed bins.
        """
        rng = np.random.default_rng(42)
        n = 20_000

        # Uniform speed spread from 5 to 60 m/s
        speed_mps = rng.uniform(5.0, 60.0, size=n)

        # Random angles, constant combined-G magnitude ~1.0
        angles = rng.uniform(-np.pi, np.pi, size=n)
        combined_g = rng.uniform(0.8, 1.0, size=n)
        lateral_g = combined_g * np.cos(angles)
        longitudinal_g = combined_g * np.sin(angles)

        surface = build_ggv_surface(speed_mps, lateral_g, longitudinal_g)

        assert surface is not None
        assert isinstance(surface, GGVSurface)
        assert len(surface.speed_bins) > 0
        assert len(surface.envelopes) == len(surface.speed_bins)
        assert surface.n_sectors == 36

        # All speed bins should have envelope values near 1.0G
        for envelope in surface.envelopes:
            mean_g = float(np.mean(envelope))
            assert mean_g > 0.7, f"Mean envelope G too low: {mean_g}"
            assert mean_g < 1.1, f"Mean envelope G too high: {mean_g}"

    def test_ggv_query_interpolates_between_bins(self) -> None:
        """Speed between two bin centers produces interpolated value.

        Creates data at two distinct speed ranges with different G limits.
        Querying at the midpoint should give an interpolated value.
        """
        rng = np.random.default_rng(42)
        n_per_bin = 5000

        # Low-speed bin (~7.5 m/s center with 5.0 width): combined-G ~0.6
        speed_low = rng.uniform(5.0, 10.0, size=n_per_bin)
        angles_low = rng.uniform(-np.pi, np.pi, size=n_per_bin)
        g_low = rng.uniform(0.5, 0.6, size=n_per_bin)

        # High-speed bin (~12.5 m/s center): combined-G ~1.0
        speed_high = rng.uniform(10.0, 15.0, size=n_per_bin)
        angles_high = rng.uniform(-np.pi, np.pi, size=n_per_bin)
        g_high = rng.uniform(0.9, 1.0, size=n_per_bin)

        speed = np.concatenate([speed_low, speed_high])
        lat_g = np.concatenate(
            [
                g_low * np.cos(angles_low),
                g_high * np.cos(angles_high),
            ]
        )
        lon_g = np.concatenate(
            [
                g_low * np.sin(angles_low),
                g_high * np.sin(angles_high),
            ]
        )

        surface = build_ggv_surface(speed, lat_g, lon_g, speed_bin_width=5.0)
        assert surface is not None

        # Query at pure lateral direction (angle=0)
        g_at_7_5 = query_ggv_max_g(surface, 7.5, 0.0)
        g_at_12_5 = query_ggv_max_g(surface, 12.5, 0.0)
        g_at_10 = query_ggv_max_g(surface, 10.0, 0.0)

        # Low speed should have lower G than high speed
        assert g_at_7_5 < g_at_12_5

        # Midpoint should be between the two bin values
        assert g_at_10 > g_at_7_5 - 0.05
        assert g_at_10 < g_at_12_5 + 0.05

    def test_ggv_power_limited_at_low_speed(self) -> None:
        """Synthetic data where low speed has lower acceleration G.

        Simulates power limitation: at low speed, traction-limited acceleration
        is lower because the engine has less torque multiplication through gears.
        """
        rng = np.random.default_rng(42)
        n_per_bin = 3000

        # Low speed (5-15 m/s): limited acceleration (max ~0.3G forward)
        speed_low = rng.uniform(5.0, 15.0, size=n_per_bin)
        lat_low = rng.uniform(-0.8, 0.8, size=n_per_bin)
        # Acceleration direction is positive longitudinal G
        lon_low = rng.uniform(-0.8, 0.3, size=n_per_bin)

        # High speed (25-35 m/s): stronger acceleration available (~0.6G)
        speed_high = rng.uniform(25.0, 35.0, size=n_per_bin)
        lat_high = rng.uniform(-0.8, 0.8, size=n_per_bin)
        lon_high = rng.uniform(-0.8, 0.6, size=n_per_bin)

        speed = np.concatenate([speed_low, speed_high])
        lat_g = np.concatenate([lat_low, lat_high])
        lon_g = np.concatenate([lon_low, lon_high])

        surface = build_ggv_surface(speed, lat_g, lon_g, speed_bin_width=10.0)
        assert surface is not None

        # Query pure acceleration direction: angle = pi/2
        # (atan2(lon_g, lat_g) = pi/2 for pure positive longitudinal)
        accel_angle = np.pi / 2

        # Find bins near low-speed and high-speed centers
        g_low_val = query_ggv_max_g(surface, 10.0, accel_angle)
        g_high_val = query_ggv_max_g(surface, 30.0, accel_angle)

        # High speed should have more available accel G
        assert g_high_val > g_low_val, (
            f"Expected more accel G at high speed ({g_high_val}) than low speed ({g_low_val})"
        )

    def test_ggv_aero_boost_at_high_speed(self) -> None:
        """Synthetic data where high speed has higher lateral G (downforce).

        At high speed, aerodynamic downforce increases tire normal force,
        enabling higher cornering G.  This should show up as larger lateral
        envelope at high speed bins.
        """
        rng = np.random.default_rng(42)
        n_per_bin = 3000

        # Low speed (5-15 m/s): baseline lateral G ~0.8
        speed_low = rng.uniform(5.0, 15.0, size=n_per_bin)
        lat_low = rng.choice([-1, 1], size=n_per_bin) * rng.uniform(0.6, 0.8, size=n_per_bin)
        lon_low = rng.uniform(-0.3, 0.3, size=n_per_bin)

        # High speed (35-50 m/s): boosted lateral G ~1.3 (aero downforce)
        speed_high = rng.uniform(35.0, 50.0, size=n_per_bin)
        lat_high = rng.choice([-1, 1], size=n_per_bin) * rng.uniform(1.0, 1.3, size=n_per_bin)
        lon_high = rng.uniform(-0.3, 0.3, size=n_per_bin)

        speed = np.concatenate([speed_low, speed_high])
        lat_g = np.concatenate([lat_low, lat_high])
        lon_g = np.concatenate([lon_low, lon_high])

        surface = build_ggv_surface(speed, lat_g, lon_g, speed_bin_width=10.0)
        assert surface is not None

        # Query pure lateral direction: angle = 0
        g_low_speed = query_ggv_max_g(surface, 10.0, 0.0)
        g_high_speed = query_ggv_max_g(surface, 42.5, 0.0)

        # High speed should have more lateral G from aero
        assert g_high_speed > g_low_speed, (
            f"Expected more lateral G at high speed ({g_high_speed}) than low speed ({g_low_speed})"
        )
        # The difference should be meaningful (at least 0.1G)
        assert g_high_speed - g_low_speed > 0.1

    def test_ggv_returns_none_insufficient_data(self) -> None:
        """Too few data points returns None."""
        speed = np.array([10.0, 20.0, 30.0])
        lat_g = np.array([0.5, 0.3, 0.8])
        lon_g = np.array([-0.2, 0.1, -0.5])

        result = build_ggv_surface(speed, lat_g, lon_g)
        assert result is None

    def test_ggv_surface_sectors_count(self) -> None:
        """Custom n_sectors parameter is respected."""
        rng = np.random.default_rng(42)
        n = 10_000

        speed = rng.uniform(5.0, 50.0, size=n)
        angles = rng.uniform(-np.pi, np.pi, size=n)
        combined_g = rng.uniform(0.5, 1.0, size=n)
        lat_g = combined_g * np.cos(angles)
        lon_g = combined_g * np.sin(angles)

        surface = build_ggv_surface(speed, lat_g, lon_g, n_sectors=18)
        assert surface is not None
        assert surface.n_sectors == 18
        for envelope in surface.envelopes:
            assert len(envelope) == 18

    def test_ggv_empty_speed_bins_handled(self) -> None:
        """Speed bins with no data are handled gracefully.

        When data only covers a narrow speed range, the surface should only
        contain bins that have data, not crash on empty bins.
        """
        rng = np.random.default_rng(42)
        n = 5000

        # All data concentrated in 20-30 m/s range
        speed = rng.uniform(20.0, 30.0, size=n)
        angles = rng.uniform(-np.pi, np.pi, size=n)
        combined_g = rng.uniform(0.5, 1.0, size=n)
        lat_g = combined_g * np.cos(angles)
        lon_g = combined_g * np.sin(angles)

        surface = build_ggv_surface(speed, lat_g, lon_g, speed_bin_width=5.0)
        assert surface is not None

        # Should have bins covering the 20-30 m/s range (2 bins)
        assert len(surface.speed_bins) >= 2
        # All bin centers should be in or near the 20-30 m/s range
        for center in surface.speed_bins:
            assert 17.5 <= center <= 32.5


class TestQueryGGVMaxG:
    """Tests for query_ggv_max_g()."""

    def test_query_clamps_below_min_speed(self) -> None:
        """Querying below the minimum speed bin returns the lowest bin value."""
        rng = np.random.default_rng(42)
        n = 10_000

        speed = rng.uniform(10.0, 50.0, size=n)
        angles = rng.uniform(-np.pi, np.pi, size=n)
        combined_g = rng.uniform(0.5, 1.0, size=n)
        lat_g = combined_g * np.cos(angles)
        lon_g = combined_g * np.sin(angles)

        surface = build_ggv_surface(speed, lat_g, lon_g, speed_bin_width=5.0)
        assert surface is not None

        # Query well below data range
        g_low = query_ggv_max_g(surface, 1.0, 0.0)
        # Should return the first bin's value (clamped, not crash)
        g_first_bin = query_ggv_max_g(surface, float(surface.speed_bins[0]), 0.0)
        assert g_low == pytest.approx(g_first_bin, abs=0.01)

    def test_query_clamps_above_max_speed(self) -> None:
        """Querying above the maximum speed bin returns the highest bin value."""
        rng = np.random.default_rng(42)
        n = 10_000

        speed = rng.uniform(10.0, 50.0, size=n)
        angles = rng.uniform(-np.pi, np.pi, size=n)
        combined_g = rng.uniform(0.5, 1.0, size=n)
        lat_g = combined_g * np.cos(angles)
        lon_g = combined_g * np.sin(angles)

        surface = build_ggv_surface(speed, lat_g, lon_g, speed_bin_width=5.0)
        assert surface is not None

        # Query well above data range
        g_high = query_ggv_max_g(surface, 100.0, 0.0)
        # Should return the last bin's value
        g_last_bin = query_ggv_max_g(surface, float(surface.speed_bins[-1]), 0.0)
        assert g_high == pytest.approx(g_last_bin, abs=0.01)

    def test_query_angle_wrapping(self) -> None:
        """Angles outside [-pi, pi] wrap correctly."""
        rng = np.random.default_rng(42)
        n = 10_000

        speed = rng.uniform(10.0, 50.0, size=n)
        angles = rng.uniform(-np.pi, np.pi, size=n)
        combined_g = rng.uniform(0.5, 1.0, size=n)
        lat_g = combined_g * np.cos(angles)
        lon_g = combined_g * np.sin(angles)

        surface = build_ggv_surface(speed, lat_g, lon_g)
        assert surface is not None

        # Query at equivalent angles: 0 and 2*pi should give same result
        g_at_0 = query_ggv_max_g(surface, 30.0, 0.0)
        g_at_2pi = query_ggv_max_g(surface, 30.0, 2.0 * np.pi)
        assert g_at_0 == pytest.approx(g_at_2pi, abs=0.01)


# ---------------------------------------------------------------------------
# Tire thermal warmup model tests
# ---------------------------------------------------------------------------


class TestComputeWarmupFactor:
    """Tests for compute_warmup_factor()."""

    def test_warmup_first_lap_midpoint(self) -> None:
        """Lap 1 with default warmup_laps=1.5 should be ~0.917."""
        factor = compute_warmup_factor(1)
        expected = 0.75 + (1.0 - 0.75) * 1.0 / 1.5  # 0.9167
        assert factor == pytest.approx(expected, rel=1e-6)

    def test_warmup_second_lap_full_grip(self) -> None:
        """After warmup_laps, should be 1.0."""
        assert compute_warmup_factor(2) == pytest.approx(1.0, rel=1e-6)

    def test_warmup_custom_cold_factor(self) -> None:
        """Custom cold_factor should be used."""
        factor = compute_warmup_factor(1, cold_factor=0.5, warmup_laps=2.0)
        expected = 0.5 + (1.0 - 0.5) * 1.0 / 2.0  # 0.75
        assert factor == pytest.approx(expected, rel=1e-6)

    def test_warmup_compound_street_fast(self) -> None:
        """Street tires (warmup_laps=0.5) should be warm mid-lap 1."""
        factor = compute_warmup_factor(1, warmup_laps=0.5)
        assert factor == pytest.approx(1.0, rel=1e-6)

    def test_warmup_compound_slick_slow(self) -> None:
        """Slick tires (warmup_laps=2.5) should still be warming on lap 2."""
        factor = compute_warmup_factor(2, warmup_laps=2.5)
        expected = 0.75 + (1.0 - 0.75) * 2.0 / 2.5  # 0.95
        assert factor == pytest.approx(expected, rel=1e-6)

    def test_warmup_lap_zero_returns_cold(self) -> None:
        """Lap 0 (or negative) should return cold_factor."""
        assert compute_warmup_factor(0) == pytest.approx(0.75, rel=1e-6)


# ---------------------------------------------------------------------------
# Tire load sensitivity model tests
# ---------------------------------------------------------------------------


class TestLoadSensitiveMu:
    """Tests for load_sensitive_mu()."""

    def test_at_reference_load_unchanged(self) -> None:
        """At reference load, mu should equal mu_ref."""
        result = load_sensitive_mu(1.2, 4000.0, 4000.0)
        assert result == pytest.approx(1.2, rel=1e-10)

    def test_higher_load_lower_mu(self) -> None:
        """More load should decrease mu (negative sensitivity)."""
        result = load_sensitive_mu(1.2, 4000.0, 5000.0, sensitivity=-0.00005)
        # mu = 1.2 + (-0.00005) * (5000 - 4000) = 1.2 - 0.05 = 1.15
        expected = 1.2 + (-0.00005) * (5000.0 - 4000.0)
        assert result == pytest.approx(expected, rel=1e-10)
        assert result < 1.2

    def test_mu_clamped_at_minimum(self) -> None:
        """Extremely high load should not produce negative mu."""
        result = load_sensitive_mu(1.0, 4000.0, 100000.0, sensitivity=-0.001)
        assert result >= 0.1

    def test_lower_load_higher_mu(self) -> None:
        """Less load should increase mu (load sensitivity works both ways)."""
        result = load_sensitive_mu(1.0, 4000.0, 2000.0, sensitivity=-0.00005)
        # mu = 1.0 + (-0.00005) * (2000 - 4000) = 1.0 + 0.1 = 1.1
        assert result > 1.0
        expected = 1.0 + (-0.00005) * (2000.0 - 4000.0)
        assert result == pytest.approx(expected, rel=1e-10)

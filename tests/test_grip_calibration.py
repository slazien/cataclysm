"""Tests for cataclysm.grip_calibration — data-driven grip extraction from G-G data."""

from __future__ import annotations

import numpy as np
import pytest

from cataclysm.grip_calibration import (
    CalibratedGrip,
    apply_calibration_to_params,
    calibrate_grip_from_telemetry,
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

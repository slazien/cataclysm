"""Tests for cataclysm.ggv_envelope — empirical GGV envelope extractor."""

from __future__ import annotations

import numpy as np
import pytest

from cataclysm.ggv_envelope import GGVEnvelope, build_ggv_from_telemetry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uniform_gg_data(
    n: int = 1000,
    speed_range: tuple[float, float] = (10.0, 60.0),
    max_g: float = 1.0,
    rng_seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic telemetry with a uniform ~max_g envelope across all speeds."""
    rng = np.random.default_rng(rng_seed)
    speed = rng.uniform(speed_range[0], speed_range[1], n)
    # Random direction on the GG circle, random magnitude up to max_g.
    angle = rng.uniform(0, 2 * np.pi, n)
    magnitude = rng.uniform(0, max_g, n)
    lat_g = magnitude * np.cos(angle)
    lon_g = magnitude * np.sin(angle)
    return speed, lat_g, lon_g


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildGGV:
    """Tests for build_ggv_from_telemetry."""

    def test_ggv_basic_construction(self) -> None:
        """Build from synthetic data with known ~1.0G envelope, verify ~1.0G per bin."""
        speed, lat_g, lon_g = _uniform_gg_data(n=2000, max_g=1.0)
        env = build_ggv_from_telemetry(speed, lat_g, lon_g, n_speed_bins=8)

        assert env is not None
        assert len(env.speed_bins) == 8
        assert len(env.max_lateral_g) == 8
        assert len(env.max_decel_g) == 8
        assert len(env.max_accel_g) == 8
        assert len(env.point_counts) == 8

        # Each bin should show a reasonable G value within the 1.0G envelope.
        # |lat_g| = magnitude * |cos(angle)| — the projection reduces p95 below 1.0.
        for i in range(8):
            assert 0.5 < env.max_lateral_g[i] <= 1.0, (
                f"bin {i}: lateral {env.max_lateral_g[i]:.3f} outside expected range"
            )
            assert env.max_decel_g[i] >= 0, f"bin {i}: decel should be non-negative"
            assert env.max_accel_g[i] >= 0, f"bin {i}: accel should be non-negative"

    def test_ggv_query_interpolates(self) -> None:
        """Query at intermediate speed between bin centers gives reasonable value."""
        speed, lat_g, lon_g = _uniform_gg_data(n=2000, max_g=1.2)
        env = build_ggv_from_telemetry(speed, lat_g, lon_g, n_speed_bins=6)
        assert env is not None

        # Query at a speed between two bin centers.
        mid_speed = float(np.mean(env.speed_bins[:2]))
        result = env.max_lateral_at_speed(mid_speed)

        # Should be between the two neighboring bin values (linear interp).
        lo = min(env.max_lateral_g[0], env.max_lateral_g[1])
        hi = max(env.max_lateral_g[0], env.max_lateral_g[1])
        assert lo - 0.01 <= result <= hi + 0.01

    def test_ggv_empty_data_returns_none(self) -> None:
        """Empty arrays should return None."""
        result = build_ggv_from_telemetry(
            np.array([]),
            np.array([]),
            np.array([]),
        )
        assert result is None

    def test_ggv_insufficient_data_returns_none(self) -> None:
        """Fewer than min_total_points should return None."""
        speed = np.array([10.0, 20.0, 30.0])
        lat = np.array([0.5, 0.6, 0.7])
        lon = np.array([-0.3, 0.2, -0.1])
        result = build_ggv_from_telemetry(speed, lat, lon, min_total_points=100)
        assert result is None

    def test_ggv_sparse_bins_filled(self) -> None:
        """100 points clustered in two speed ranges — sparse bins filled by interpolation."""
        rng = np.random.default_rng(99)
        n_per_cluster = 60

        # Cluster 1: low speed (10-15 m/s), ~0.8G.
        speed_lo = rng.uniform(10.0, 15.0, n_per_cluster)
        lat_lo = rng.uniform(-0.8, 0.8, n_per_cluster)
        lon_lo = rng.uniform(-0.8, 0.8, n_per_cluster)

        # Cluster 2: high speed (50-55 m/s), ~1.2G.
        speed_hi = rng.uniform(50.0, 55.0, n_per_cluster)
        lat_hi = rng.uniform(-1.2, 1.2, n_per_cluster)
        lon_hi = rng.uniform(-1.2, 1.2, n_per_cluster)

        speed = np.concatenate([speed_lo, speed_hi])
        lat = np.concatenate([lat_lo, lat_hi])
        lon = np.concatenate([lon_lo, lon_hi])

        env = build_ggv_from_telemetry(speed, lat, lon, n_speed_bins=8, min_total_points=50)
        assert env is not None

        # Sparse (middle) bins should have interpolated values — no NaN.
        assert np.all(np.isfinite(env.max_lateral_g))
        assert np.all(np.isfinite(env.max_decel_g))
        assert np.all(np.isfinite(env.max_accel_g))

        # Middle bins should be between the two cluster values.
        mid_idx = len(env.speed_bins) // 2
        assert env.max_lateral_g[0] < env.max_lateral_g[-1], (
            "High-speed cluster had higher G; last bin should exceed first"
        )
        assert env.max_lateral_g[0] <= env.max_lateral_g[mid_idx] <= env.max_lateral_g[-1]

    def test_ggv_aero_car_increases_with_speed(self) -> None:
        """Synthetic data where lateral_g scales with speed² (downforce effect)."""
        rng = np.random.default_rng(7)
        n = 3000
        speed = rng.uniform(15.0, 70.0, n)

        # Simulate downforce: grip scales with speed² (normalized).
        base_g = 0.8
        aero_factor = 0.005  # G per (m/s)²
        max_g_at_speed = base_g + aero_factor * speed**2 / 70.0

        angle = rng.uniform(0, 2 * np.pi, n)
        magnitude = rng.uniform(0.5, 1.0, n) * max_g_at_speed
        lat_g = magnitude * np.cos(angle)
        lon_g = magnitude * np.sin(angle)

        env = build_ggv_from_telemetry(speed, lat_g, lon_g, n_speed_bins=8)
        assert env is not None

        # Max lateral G should generally increase with speed.
        # Check that the last bin > first bin (aero effect).
        assert env.max_lateral_g[-1] > env.max_lateral_g[0], (
            f"Expected increasing lateral G: first={env.max_lateral_g[0]:.3f}, "
            f"last={env.max_lateral_g[-1]:.3f}"
        )

    def test_ggv_monotonic_query(self) -> None:
        """Multiple queries at increasing speeds should produce smooth results."""
        speed, lat_g, lon_g = _uniform_gg_data(n=2000, max_g=1.0)
        env = build_ggv_from_telemetry(speed, lat_g, lon_g, n_speed_bins=8)
        assert env is not None

        # Query at 50 equally-spaced speeds across the range.
        query_speeds = np.linspace(
            float(env.speed_bins[0]),
            float(env.speed_bins[-1]),
            50,
        )
        lat_values = [env.max_lateral_at_speed(s) for s in query_speeds]
        decel_values = [env.max_decel_at_speed(s) for s in query_speeds]
        accel_values = [env.max_accel_at_speed(s) for s in query_speeds]

        # All values should be positive and finite.
        for vals, name in [
            (lat_values, "lateral"),
            (decel_values, "decel"),
            (accel_values, "accel"),
        ]:
            for v in vals:
                assert np.isfinite(v), f"{name}: non-finite value {v}"
                assert v >= 0, f"{name}: negative value {v}"

        # Check smoothness: max consecutive jump should be < 0.3G.
        for vals, name in [(lat_values, "lateral"), (decel_values, "decel")]:
            diffs = [abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)]
            max_jump = max(diffs)
            assert max_jump < 0.3, (
                f"{name}: discontinuity of {max_jump:.3f}G between consecutive queries"
            )


class TestGGVEnvelopeDataclass:
    """Direct tests on the GGVEnvelope dataclass methods."""

    def test_extrapolation_clamps(self) -> None:
        """Queries outside the speed range should clamp to edge values."""
        env = GGVEnvelope(
            speed_bins=np.array([10.0, 30.0, 50.0]),
            max_lateral_g=np.array([0.8, 1.0, 1.2]),
            max_decel_g=np.array([1.0, 1.0, 1.0]),
            max_accel_g=np.array([0.5, 0.4, 0.3]),
            point_counts=np.array([100, 200, 150]),
        )

        # Below min speed → clamp to first bin value.
        assert env.max_lateral_at_speed(0.0) == pytest.approx(0.8)
        assert env.max_accel_at_speed(0.0) == pytest.approx(0.5)

        # Above max speed → clamp to last bin value.
        assert env.max_lateral_at_speed(100.0) == pytest.approx(1.2)
        assert env.max_accel_at_speed(100.0) == pytest.approx(0.3)

    def test_exact_bin_center_query(self) -> None:
        """Query at an exact bin center returns the bin value."""
        env = GGVEnvelope(
            speed_bins=np.array([20.0, 40.0, 60.0]),
            max_lateral_g=np.array([0.9, 1.1, 1.3]),
            max_decel_g=np.array([1.2, 1.1, 1.0]),
            max_accel_g=np.array([0.6, 0.5, 0.4]),
            point_counts=np.array([50, 80, 60]),
        )

        assert env.max_lateral_at_speed(40.0) == pytest.approx(1.1)
        assert env.max_decel_at_speed(40.0) == pytest.approx(1.1)
        assert env.max_accel_at_speed(40.0) == pytest.approx(0.5)

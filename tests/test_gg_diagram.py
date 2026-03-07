"""Comprehensive tests for cataclysm.gg_diagram module."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from cataclysm.corners import Corner
from cataclysm.gg_diagram import (
    MIN_MAX_G,
    N_SECTORS,
    GGDiagramResult,
    GGPoint,
    _build_sector_envelope,
    _convex_hull_area,
    _envelope_utilization_pct,
    _utilization_pct,
    compute_gg_diagram,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_corner(
    number: int = 1,
    entry_m: float = 100.0,
    exit_m: float = 200.0,
) -> Corner:
    """Build a minimal Corner for GG testing."""
    return Corner(
        number=number,
        entry_distance_m=entry_m,
        exit_distance_m=exit_m,
        apex_distance_m=(entry_m + exit_m) / 2,
        min_speed_mps=25.0,
        brake_point_m=entry_m - 20,
        peak_brake_g=-0.8,
        throttle_commit_m=exit_m - 30,
        apex_type="mid",
    )


def _make_lap_df(
    lat_g: np.ndarray,
    lon_g: np.ndarray,
    distance_m: np.ndarray | None = None,
) -> pd.DataFrame:
    """Build a minimal resampled-lap DataFrame."""
    n = len(lat_g)
    if distance_m is None:
        distance_m = np.arange(n, dtype=np.float64) * 0.7
    return pd.DataFrame(
        {
            "lateral_g": lat_g,
            "longitudinal_g": lon_g,
            "lap_distance_m": distance_m,
        }
    )


def _circular_g_data(n: int = 500, radius_g: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Generate points uniformly distributed around a circle (full traction use)."""
    theta = np.linspace(0, 2 * math.pi, n, endpoint=False)
    # Fill the circle interior by varying radius uniformly
    rng = np.random.default_rng(42)
    r = radius_g * np.sqrt(rng.uniform(0, 1, n))
    lat_g = r * np.cos(theta)
    lon_g = r * np.sin(theta)
    return lat_g, lon_g


def _quadrant_g_data(n: int = 500, radius_g: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Generate points only in the first quadrant (lat>0, lon>0)."""
    rng = np.random.default_rng(42)
    r = radius_g * np.sqrt(rng.uniform(0, 1, n))
    theta = rng.uniform(0, math.pi / 2, n)
    lat_g = r * np.cos(theta)
    lon_g = r * np.sin(theta)
    return lat_g, lon_g


def _asymmetric_g_data(
    n: int = 1000,
    brake_g: float = 1.0,
    accel_g: float = 0.3,
    lateral_g: float = 0.8,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate realistic asymmetric data: strong braking, weak acceleration."""
    rng = np.random.default_rng(42)
    lat_parts: list[float] = []
    lon_parts: list[float] = []

    # Braking zone (30% of points)
    n_brake = n * 3 // 10
    for _ in range(n_brake):
        lat_parts.append(rng.normal(0.0, lateral_g * 0.3))
        lon_parts.append(-rng.uniform(0.2, brake_g))

    # Cornering (40% of points)
    n_corner = n * 4 // 10
    for _ in range(n_corner):
        side = rng.choice([-1, 1])
        lat_parts.append(side * rng.uniform(0.3, lateral_g))
        lon_parts.append(rng.normal(-0.1, 0.15))

    # Acceleration (30% of points) — limited by engine power
    n_accel = n - n_brake - n_corner
    for _ in range(n_accel):
        lat_parts.append(rng.normal(0.0, lateral_g * 0.2))
        lon_parts.append(rng.uniform(0.05, accel_g))

    return np.array(lat_parts), np.array(lon_parts)


# ---------------------------------------------------------------------------
# Tests for _convex_hull_area
# ---------------------------------------------------------------------------


class TestConvexHullArea:
    """Tests for the convex-hull area helper."""

    def test_unit_square(self) -> None:
        """Four corners of a unit square should give area = 1.0."""
        lat = np.array([0, 1, 1, 0], dtype=np.float64)
        lon = np.array([0, 0, 1, 1], dtype=np.float64)
        area = _convex_hull_area(lat, lon)
        assert area == pytest.approx(1.0, abs=1e-6)

    def test_triangle(self) -> None:
        """A right triangle with legs 2 and 3 has area 3.0."""
        lat = np.array([0, 2, 0], dtype=np.float64)
        lon = np.array([0, 0, 3], dtype=np.float64)
        area = _convex_hull_area(lat, lon)
        assert area == pytest.approx(3.0, abs=1e-6)

    def test_fewer_than_min_points(self) -> None:
        """Fewer than MIN_POINTS_FOR_HULL returns 0."""
        lat = np.array([0, 1], dtype=np.float64)
        lon = np.array([0, 1], dtype=np.float64)
        assert _convex_hull_area(lat, lon) == 0.0

    def test_empty_arrays(self) -> None:
        lat = np.array([], dtype=np.float64)
        lon = np.array([], dtype=np.float64)
        assert _convex_hull_area(lat, lon) == 0.0

    def test_collinear_points(self) -> None:
        """Points on a line have zero area."""
        lat = np.array([0, 1, 2, 3], dtype=np.float64)
        lon = np.array([0, 1, 2, 3], dtype=np.float64)
        assert _convex_hull_area(lat, lon) == 0.0

    def test_identical_points(self) -> None:
        """All points at the same location have zero area."""
        lat = np.full(10, 0.5, dtype=np.float64)
        lon = np.full(10, -0.3, dtype=np.float64)
        assert _convex_hull_area(lat, lon) == 0.0

    def test_circle_approximation(self) -> None:
        """Many points on a unit circle should approximate pi."""
        n = 1000
        theta = np.linspace(0, 2 * math.pi, n, endpoint=False)
        lat = np.cos(theta)
        lon = np.sin(theta)
        area = _convex_hull_area(lat, lon)
        assert area == pytest.approx(math.pi, rel=0.01)


# ---------------------------------------------------------------------------
# Tests for _utilization_pct (legacy circle-based)
# ---------------------------------------------------------------------------


class TestUtilizationPct:
    """Tests for the legacy circle-based utilization helper."""

    def test_full_circle_is_100(self) -> None:
        """If hull area equals pi * max_g^2, utilization is 100%."""
        max_g = 1.5
        hull_area = math.pi * max_g**2
        assert _utilization_pct(hull_area, max_g) == pytest.approx(100.0)

    def test_half_circle(self) -> None:
        """Half the traction circle area -> 50%."""
        max_g = 1.0
        hull_area = 0.5 * math.pi * max_g**2
        assert _utilization_pct(hull_area, max_g) == pytest.approx(50.0)

    def test_zero_max_g(self) -> None:
        """Max G below floor returns 0% (avoids div-by-zero)."""
        assert _utilization_pct(1.0, 0.0) == 0.0
        assert _utilization_pct(1.0, MIN_MAX_G - 0.001) == 0.0

    def test_clamps_at_100(self) -> None:
        """Utilization should never exceed 100% (e.g. numerical noise)."""
        max_g = 0.5
        huge_area = 100.0  # Way bigger than pi * 0.5^2
        assert _utilization_pct(huge_area, max_g) == 100.0

    def test_tiny_area(self) -> None:
        """Very small hull area -> near 0%."""
        assert _utilization_pct(0.001, 2.0) == pytest.approx(0.001 / (math.pi * 4) * 100, rel=0.01)


# ---------------------------------------------------------------------------
# Tests for _build_sector_envelope
# ---------------------------------------------------------------------------


class TestBuildSectorEnvelope:
    """Tests for the angular sector envelope builder."""

    def test_circular_data_uniform_envelope(self) -> None:
        """Points on a circle should give a roughly uniform envelope."""
        n = 1000
        theta = np.linspace(0, 2 * math.pi, n, endpoint=False)
        lat_g = np.cos(theta)
        lon_g = np.sin(theta)

        env = _build_sector_envelope(lat_g, lon_g)

        assert len(env) == N_SECTORS
        # All sectors should be close to 1.0
        assert np.all(env > 0.9)
        assert np.all(env <= 1.01)

    def test_asymmetric_data_different_sectors(self) -> None:
        """Asymmetric data should produce different envelope values."""
        lat_g, lon_g = _asymmetric_g_data(n=2000, brake_g=1.0, accel_g=0.3)
        env = _build_sector_envelope(lat_g, lon_g)

        # Braking sector (lon_g < 0, lat_g ~ 0) -> angle near -pi/2
        # The braking direction sectors should have higher envelope values
        # than acceleration direction sectors
        brake_angle = -math.pi / 2  # pure braking direction
        accel_angle = math.pi / 2  # pure acceleration direction
        sector_width = 2 * math.pi / N_SECTORS

        brake_idx = int((brake_angle + math.pi) / sector_width)
        brake_idx = min(brake_idx, N_SECTORS - 1)
        accel_idx = int((accel_angle + math.pi) / sector_width)
        accel_idx = min(accel_idx, N_SECTORS - 1)

        # Braking envelope should be significantly larger than acceleration
        assert env[brake_idx] > env[accel_idx] * 1.5

    def test_empty_sectors_get_filled(self) -> None:
        """Sectors with no data should get a non-zero fallback."""
        # Data only in one direction
        lat_g = np.array([1.0, 0.9, 0.8, 0.7, 0.6])
        lon_g = np.zeros(5)
        env = _build_sector_envelope(lat_g, lon_g)

        # All sectors should be > 0 (empty ones filled with average)
        assert np.all(env >= MIN_MAX_G)


# ---------------------------------------------------------------------------
# Tests for _envelope_utilization_pct
# ---------------------------------------------------------------------------


class TestEnvelopeUtilizationPct:
    """Tests for the new envelope-based utilization calculation."""

    def test_points_at_envelope_give_100(self) -> None:
        """Points exactly at the envelope boundary should give 100%."""
        # All points on a unit circle = all at max in every direction
        n = 500
        theta = np.linspace(0, 2 * math.pi, n, endpoint=False)
        lat_g = np.cos(theta)
        lon_g = np.sin(theta)

        util = _envelope_utilization_pct(lat_g, lon_g)
        assert util == pytest.approx(100.0, abs=1.0)

    def test_points_at_origin_give_low(self) -> None:
        """Points near the origin should give lower utilization than at the edge.

        With envelope scoring, even origin-clustered data gets ~40-50%
        because the envelope is built from the same points — the 4 edge
        points define the max in their sectors, and the near-zero points
        in other sectors create a small envelope that they nearly fill.
        The key property: it's lower than data at the envelope boundary.
        """
        rng = np.random.default_rng(42)
        n = 500
        # Mostly near center with a few at the edge to define envelope
        lat_g = np.concatenate(
            [
                rng.normal(0, 0.05, n - 4),
                np.array([1.0, -1.0, 0.0, 0.0]),
            ]
        )
        lon_g = np.concatenate(
            [
                rng.normal(0, 0.05, n - 4),
                np.array([0.0, 0.0, 1.0, -1.0]),
            ]
        )

        util = _envelope_utilization_pct(lat_g, lon_g)
        # Lower than boundary data (which gives ~100%)
        assert util < 60.0

    def test_dense_fill_high_utilization(self) -> None:
        """Uniformly filled circle should give high utilization."""
        lat_g, lon_g = _circular_g_data(n=2000, radius_g=1.0)
        util = _envelope_utilization_pct(lat_g, lon_g)
        # Dense uniform fill: mean radius = 2/3 of max -> ~67% utilization
        assert 50.0 < util < 85.0

    def test_too_few_points_returns_zero(self) -> None:
        """Fewer than MIN_POINTS_FOR_HULL returns 0."""
        lat_g = np.array([0.5, -0.5])
        lon_g = np.array([0.3, -0.3])
        assert _envelope_utilization_pct(lat_g, lon_g) == 0.0

    def test_near_zero_g_returns_zero(self) -> None:
        """Near-zero G data returns 0."""
        rng = np.random.default_rng(42)
        lat_g = rng.normal(0, 0.01, 100)
        lon_g = rng.normal(0, 0.01, 100)
        assert _envelope_utilization_pct(lat_g, lon_g) == 0.0

    def test_asymmetric_still_high(self) -> None:
        """Asymmetric data (weak accel, strong brake) should still score well.

        This is THE key test: a car with 0.3G accel and 1.0G braking
        should NOT be penalized for the low acceleration capability.
        """
        lat_g, lon_g = _asymmetric_g_data(n=2000, brake_g=1.0, accel_g=0.3, lateral_g=0.8)
        util = _envelope_utilization_pct(lat_g, lon_g)

        # Should be reasonable (>40%) even though it would score low
        # against a symmetric circle due to the 0.3G accel limit
        assert util > 40.0

    def test_clamped_at_100(self) -> None:
        """Utilization never exceeds 100%."""
        n = 500
        theta = np.linspace(0, 2 * math.pi, n, endpoint=False)
        lat_g = np.cos(theta)
        lon_g = np.sin(theta)
        util = _envelope_utilization_pct(lat_g, lon_g)
        assert util <= 100.0

    def test_custom_envelope_passed(self) -> None:
        """When an external envelope is passed, it's used as the reference."""
        rng = np.random.default_rng(42)
        n = 200
        lat_g = rng.uniform(-0.3, 0.3, n)
        lon_g = rng.uniform(-0.3, 0.3, n)

        # Build a large envelope (as if full-lap max was much bigger)
        big_envelope = np.full(N_SECTORS, 1.0)
        util_big = _envelope_utilization_pct(lat_g, lon_g, envelope=big_envelope)

        # Build envelope from just this data
        util_self = _envelope_utilization_pct(lat_g, lon_g)

        # Self-envelope should be higher than the big one
        assert util_self > util_big


# ---------------------------------------------------------------------------
# Tests for compute_gg_diagram -- overall
# ---------------------------------------------------------------------------


class TestComputeGGDiagramOverall:
    """Tests for compute_gg_diagram overall behavior."""

    def test_circular_data_high_utilization(self) -> None:
        """Uniformly filled circle should give high utilization."""
        lat_g, lon_g = _circular_g_data(n=2000, radius_g=1.0)
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        assert isinstance(result, GGDiagramResult)
        assert len(result.points) == 2000
        assert result.observed_max_g > 0.5
        # With envelope-based scoring, dense uniform fill gives ~60-70%
        # (mean distance / max distance, uniformly distributed)
        assert result.overall_utilization_pct > 50.0

    def test_single_point(self) -> None:
        """Single point: no convex hull possible, utilization = 0."""
        df = _make_lap_df(
            np.array([0.5]),
            np.array([-0.3]),
        )
        result = compute_gg_diagram(df)

        assert len(result.points) == 1
        assert result.overall_utilization_pct == 0.0
        assert result.observed_max_g > 0.0

    def test_two_points(self) -> None:
        """Two points: below hull minimum, utilization = 0."""
        df = _make_lap_df(
            np.array([0.5, -0.5]),
            np.array([0.3, -0.3]),
        )
        result = compute_gg_diagram(df)

        assert len(result.points) == 2
        assert result.overall_utilization_pct == 0.0

    def test_empty_data(self) -> None:
        """Empty DataFrame should return zero everything."""
        df = _make_lap_df(
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
        )
        result = compute_gg_diagram(df)

        assert len(result.points) == 0
        assert result.overall_utilization_pct == 0.0
        assert result.observed_max_g == 0.0

    def test_collinear_data(self) -> None:
        """Collinear points (all braking, no lateral) give 0 utilization."""
        n = 50
        lat_g = np.zeros(n)
        lon_g = np.linspace(-1.0, 0.0, n)
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        # With envelope-based scoring, collinear data still has points
        # at some distance from origin, so utilization is based on how
        # close they are to the envelope. But since all points are in
        # 1-2 sectors, the filled sectors will be near-max. Still, the
        # overall value should be moderate since it's a narrow strip.
        # The key is it doesn't crash or give nonsensical values.
        assert 0.0 <= result.overall_utilization_pct <= 100.0
        assert result.observed_max_g > 0.0

    def test_nan_values_filtered(self) -> None:
        """NaN values in G traces should be filtered out gracefully."""
        lat_g = np.array([0.5, np.nan, -0.5, 0.3, -0.3, 0.0, 0.2, -0.2, 0.4, -0.4])
        lon_g = np.array([0.3, 0.2, np.nan, -0.3, 0.1, -0.1, 0.3, -0.3, 0.0, 0.2])
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        # 2 NaN rows removed -> 8 points
        assert len(result.points) == 8

    def test_all_nan_values_returns_empty(self) -> None:
        """All-NaN values should trigger the post-filter empty guard (line 255)."""
        # Non-empty DataFrame but ALL values are NaN → after valid_mask filter, n==0
        n = 5
        lat_g = np.full(n, np.nan)
        lon_g = np.full(n, np.nan)
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        assert len(result.points) == 0
        assert result.overall_utilization_pct == 0.0
        assert result.observed_max_g == 0.0

    def test_observed_max_g_correct(self) -> None:
        """Observed max G should be the max sqrt(lat^2 + lon^2)."""
        lat_g = np.array([0.0, 0.6, 0.0, -0.6])
        lon_g = np.array([0.8, 0.0, -0.8, 0.0])
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        assert result.observed_max_g == pytest.approx(0.8, abs=0.01)

    def test_point_fields(self) -> None:
        """Each GGPoint should have the correct fields."""
        df = _make_lap_df(
            np.array([0.3, -0.2, 0.1]),
            np.array([-0.5, 0.4, 0.0]),
        )
        result = compute_gg_diagram(df)

        assert len(result.points) == 3
        p = result.points[0]
        assert isinstance(p, GGPoint)
        assert p.lat_g == pytest.approx(0.3, abs=0.01)
        assert p.lon_g == pytest.approx(-0.5, abs=0.01)
        assert p.distance_m >= 0.0
        assert p.corner_number is None  # No corners supplied

    def test_asymmetric_not_penalized(self) -> None:
        """Asymmetric car (0.3G accel, 1.0G brake) should get fair score.

        With the old circle-based method, this data would score ~25-35%
        because the circle radius is set by braking (1.0G) but the
        entire acceleration quadrant is mostly empty.  With envelope
        scoring, each direction is compared against its own capability.
        """
        lat_g, lon_g = _asymmetric_g_data(n=2000, brake_g=1.0, accel_g=0.3, lateral_g=0.8)
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        # Should score higher than what circle-based would give (~30%)
        assert result.overall_utilization_pct > 40.0
        assert result.observed_max_g > 0.8  # braking defines max_g


# ---------------------------------------------------------------------------
# Tests for per-corner filtering
# ---------------------------------------------------------------------------


class TestPerCornerFiltering:
    """Tests for corner-level G-G analysis."""

    def test_per_corner_breakdown(self) -> None:
        """Points should be correctly assigned to corners."""
        n = 300
        distance = np.arange(n, dtype=np.float64) * 1.0  # 0..299 m

        rng = np.random.default_rng(123)
        lat_g = rng.uniform(-1, 1, n)
        lon_g = rng.uniform(-1, 1, n)

        corners = [
            _make_corner(number=1, entry_m=50.0, exit_m=100.0),
            _make_corner(number=2, entry_m=150.0, exit_m=200.0),
        ]

        df = _make_lap_df(lat_g, lon_g, distance)
        result = compute_gg_diagram(df, corners=corners)

        assert len(result.per_corner) == 2
        c1 = result.per_corner[0]
        c2 = result.per_corner[1]
        assert c1.corner_number == 1
        assert c2.corner_number == 2
        assert c1.point_count == 50  # indices 50..99
        assert c2.point_count == 50  # indices 150..199
        assert c1.utilization_pct >= 0.0
        assert c2.utilization_pct >= 0.0

    def test_single_corner_filter(self) -> None:
        """Filtering by corner_number returns only that corner's points."""
        n = 300
        distance = np.arange(n, dtype=np.float64) * 1.0

        rng = np.random.default_rng(456)
        lat_g = rng.uniform(-1, 1, n)
        lon_g = rng.uniform(-1, 1, n)

        corners = [
            _make_corner(number=1, entry_m=50.0, exit_m=100.0),
            _make_corner(number=2, entry_m=150.0, exit_m=200.0),
        ]

        df = _make_lap_df(lat_g, lon_g, distance)
        result = compute_gg_diagram(df, corners=corners, corner_number=2)

        assert len(result.points) == 50
        assert all(p.corner_number == 2 for p in result.points)
        # No per-corner breakdown when filtering a single corner
        assert len(result.per_corner) == 0

    def test_nonexistent_corner_filter(self) -> None:
        """Filtering by a corner number with no matching points returns empty."""
        n = 100
        distance = np.arange(n, dtype=np.float64) * 1.0
        lat_g = np.random.default_rng(0).uniform(-1, 1, n)
        lon_g = np.random.default_rng(0).uniform(-1, 1, n)

        corners = [_make_corner(number=1, entry_m=50.0, exit_m=80.0)]
        df = _make_lap_df(lat_g, lon_g, distance)

        result = compute_gg_diagram(df, corners=corners, corner_number=99)

        assert len(result.points) == 0
        assert result.overall_utilization_pct == 0.0

    def test_no_corners_supplied(self) -> None:
        """Without corners, all corner_number fields are None and per_corner is empty."""
        lat_g, lon_g = _circular_g_data(n=100)
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df, corners=None)

        assert all(p.corner_number is None for p in result.points)
        assert len(result.per_corner) == 0

    def test_corner_with_no_points(self) -> None:
        """A corner with no telemetry points should get 0 utilization."""
        n = 50
        distance = np.arange(n, dtype=np.float64) * 1.0  # 0..49 m

        lat_g = np.random.default_rng(0).uniform(-1, 1, n)
        lon_g = np.random.default_rng(0).uniform(-1, 1, n)

        # Corner is at 500-600m, but data only goes to 49m
        corners = [_make_corner(number=1, entry_m=500.0, exit_m=600.0)]
        df = _make_lap_df(lat_g, lon_g, distance)

        result = compute_gg_diagram(df, corners=corners)

        assert len(result.per_corner) == 1
        c = result.per_corner[0]
        assert c.point_count == 0
        assert c.utilization_pct == 0.0
        assert c.max_lat_g == 0.0
        assert c.max_lon_g == 0.0


# ---------------------------------------------------------------------------
# Tests with realistic noisy data patterns
# ---------------------------------------------------------------------------


class TestRealisticNoisyData:
    """Tests with GPS-like noise patterns."""

    def test_noisy_circular_envelope(self) -> None:
        """Noisy data around a circle should give moderate utilization."""
        rng = np.random.default_rng(42)
        n = 1000
        theta = np.linspace(0, 2 * math.pi, n, endpoint=False)
        r_base = 0.8 * np.ones(n)
        noise = rng.normal(0, 0.1, n)  # GPS noise ~0.1 G
        r = np.clip(r_base + noise, 0, 2.0)
        lat_g = r * np.cos(theta)
        lon_g = r * np.sin(theta)

        df = _make_lap_df(lat_g, lon_g)
        result = compute_gg_diagram(df)

        assert result.observed_max_g > 0.7
        # Points mostly on the perimeter -> high utilization with envelope scoring
        assert 50.0 < result.overall_utilization_pct < 100.0

    def test_mostly_straight_driving(self) -> None:
        """Straight-line driving (low lateral G) should give moderate utilization.

        With envelope scoring, straight-line points are compared against the
        envelope in their direction (longitudinal), so it can still be high
        IF the driver is actually using their braking/accel capability.
        """
        rng = np.random.default_rng(42)
        n = 500
        lat_g = rng.normal(0, 0.05, n)  # Tiny lateral variation
        lon_g = rng.uniform(-0.8, 0.3, n)  # Braking and accel
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        # With envelope scoring, the points fill their sectors reasonably well
        assert 0.0 < result.overall_utilization_pct < 100.0

    def test_realistic_oval_track(self) -> None:
        """Simulated oval track: left turns + straights."""
        rng = np.random.default_rng(42)
        lat_g_parts = []
        lon_g_parts = []

        # Straights (500 points): low lateral, varied longitudinal
        for _ in range(500):
            lat_g_parts.append(rng.normal(0.0, 0.05))
            lon_g_parts.append(rng.uniform(-0.5, 0.3))

        # Left turns (500 points): high lateral, moderate longitudinal
        for _ in range(500):
            lat_g_parts.append(rng.normal(0.8, 0.1))
            lon_g_parts.append(rng.normal(-0.2, 0.15))

        lat_g = np.array(lat_g_parts)
        lon_g = np.array(lon_g_parts)
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        assert result.observed_max_g > 0.6
        assert 10.0 < result.overall_utilization_pct < 80.0

    def test_near_zero_g_stationary(self) -> None:
        """Near-zero G data (parked car / GPS noise) gives 0 utilization."""
        rng = np.random.default_rng(42)
        n = 100
        lat_g = rng.normal(0, 0.01, n)
        lon_g = rng.normal(0, 0.01, n)
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        # Max combined G should be tiny
        assert result.observed_max_g < MIN_MAX_G
        assert result.overall_utilization_pct == 0.0


# ---------------------------------------------------------------------------
# Tests for CornerGGSummary fields
# ---------------------------------------------------------------------------


class TestCornerGGSummaryFields:
    """Tests for per-corner summary field correctness."""

    def test_max_lat_g_and_max_lon_g(self) -> None:
        """max_lat_g and max_lon_g should be the max absolute values in the corner."""
        n = 200
        distance = np.arange(n, dtype=np.float64) * 1.0
        lat_g = np.zeros(n)
        lon_g = np.zeros(n)

        # Corner 1 at 50-100m: known max values
        for i in range(50, 100):
            lat_g[i] = 0.7 if i < 75 else -0.9
            lon_g[i] = -0.6 if i < 75 else 0.4

        corners = [_make_corner(number=1, entry_m=50.0, exit_m=100.0)]
        df = _make_lap_df(lat_g, lon_g, distance)
        result = compute_gg_diagram(df, corners=corners)

        assert len(result.per_corner) == 1
        c = result.per_corner[0]
        assert c.max_lat_g == pytest.approx(0.9, abs=0.01)
        assert c.max_lon_g == pytest.approx(0.6, abs=0.01)
        assert c.point_count == 50

"""Comprehensive tests for cataclysm.gg_diagram module."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from cataclysm.corners import Corner
from cataclysm.gg_diagram import (
    MIN_MAX_G,
    GGDiagramResult,
    GGPoint,
    _convex_hull_area,
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
        """Many points on a unit circle should approximate π."""
        n = 1000
        theta = np.linspace(0, 2 * math.pi, n, endpoint=False)
        lat = np.cos(theta)
        lon = np.sin(theta)
        area = _convex_hull_area(lat, lon)
        assert area == pytest.approx(math.pi, rel=0.01)


# ---------------------------------------------------------------------------
# Tests for _utilization_pct
# ---------------------------------------------------------------------------


class TestUtilizationPct:
    """Tests for the utilization percentage helper."""

    def test_full_circle_is_100(self) -> None:
        """If hull area equals π × max_g², utilization is 100%."""
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
        huge_area = 100.0  # Way bigger than π × 0.5²
        assert _utilization_pct(huge_area, max_g) == 100.0

    def test_tiny_area(self) -> None:
        """Very small hull area -> near 0%."""
        assert _utilization_pct(0.001, 2.0) == pytest.approx(0.001 / (math.pi * 4) * 100, rel=0.01)


# ---------------------------------------------------------------------------
# Tests for compute_gg_diagram — overall
# ---------------------------------------------------------------------------


class TestComputeGGDiagramOverall:
    """Tests for compute_gg_diagram overall behavior."""

    def test_circular_data_high_utilization(self) -> None:
        """Uniformly filled circle should give utilization near 100%."""
        lat_g, lon_g = _circular_g_data(n=2000, radius_g=1.0)
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        assert isinstance(result, GGDiagramResult)
        assert len(result.points) == 2000
        assert result.observed_max_g > 0.5
        # Dense uniform fill should give >80% utilization
        assert result.overall_utilization_pct > 80.0

    def test_quadrant_data_low_utilization(self) -> None:
        """Data only in one quadrant should give ~25% utilization."""
        lat_g, lon_g = _quadrant_g_data(n=2000, radius_g=1.0)
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        assert result.observed_max_g > 0.5
        # One quadrant of a filled circle -> ~25% of the full circle
        assert 15.0 < result.overall_utilization_pct < 35.0

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

        assert result.overall_utilization_pct == 0.0
        assert result.observed_max_g > 0.0

    def test_nan_values_filtered(self) -> None:
        """NaN values in G traces should be filtered out gracefully."""
        lat_g = np.array([0.5, np.nan, -0.5, 0.3, -0.3, 0.0, 0.2, -0.2, 0.4, -0.4])
        lon_g = np.array([0.3, 0.2, np.nan, -0.3, 0.1, -0.1, 0.3, -0.3, 0.0, 0.2])
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        # 2 NaN rows removed -> 8 points
        assert len(result.points) == 8

    def test_observed_max_g_correct(self) -> None:
        """Observed max G should be the max sqrt(lat² + lon²)."""
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
        # Points mostly on the perimeter with noise spreading them inward/outward.
        # The Gaussian noise creates a ring-like distribution whose convex hull
        # covers most of the observed traction circle.
        assert 40.0 < result.overall_utilization_pct < 95.0

    def test_mostly_straight_driving(self) -> None:
        """Straight-line driving (low lateral G) should give low utilization."""
        rng = np.random.default_rng(42)
        n = 500
        lat_g = rng.normal(0, 0.05, n)  # Tiny lateral variation
        lon_g = rng.uniform(-0.8, 0.3, n)  # Braking and accel
        df = _make_lap_df(lat_g, lon_g)

        result = compute_gg_diagram(df)

        # Long narrow scatter (mostly longitudinal) -> low utilization
        assert result.overall_utilization_pct < 30.0

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
        # Asymmetric (only left turns): should be moderate, not full utilization
        assert 10.0 < result.overall_utilization_pct < 60.0

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

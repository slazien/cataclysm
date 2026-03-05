"""Tests for cataclysm.clothoid_fitting — piecewise clothoid curvature."""

from __future__ import annotations

import numpy as np

from cataclysm.clothoid_fitting import (
    compute_clothoid_curvature,
    fit_clothoid_segment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _straight_line_xy(
    n: int = 500,
    step_m: float = 0.7,
    bearing_rad: float = 0.3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate XY points along a straight line and their distance array."""
    distance = np.arange(n, dtype=np.float64) * step_m
    x = distance * np.cos(bearing_rad)
    y = distance * np.sin(bearing_rad)
    return x, y, distance


def _circular_arc_xy(
    radius_m: float = 100.0,
    n: int = 500,
    arc_fraction: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate XY points along a circular arc and their distance array.

    Arc sweeps ``arc_fraction * 2*pi`` radians, starting at angle 0.
    """
    total_arc = 2 * np.pi * arc_fraction * radius_m
    distance = np.linspace(0, total_arc, n, dtype=np.float64)
    theta = distance / radius_m  # angle in radians
    x = radius_m * np.cos(theta)
    y = radius_m * np.sin(theta)
    return x, y, distance


def _clothoid_transition_xy(
    n_straight: int = 200,
    n_transition: int = 200,
    n_arc: int = 200,
    step_m: float = 0.5,
    target_curvature: float = 0.01,  # 1/R = 1/100 m
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate a track: straight -> clothoid transition -> constant-radius arc.

    In the straight section, curvature = 0.
    In the transition, curvature linearly increases from 0 to target_curvature.
    In the arc section, curvature stays constant at target_curvature.

    The track is built by integrating curvature -> heading -> XY.
    """
    n_total = n_straight + n_transition + n_arc
    distance = np.arange(n_total, dtype=np.float64) * step_m

    # Build curvature profile
    kappa = np.zeros(n_total, dtype=np.float64)
    # Transition: linearly from 0 to target_curvature
    kappa[n_straight : n_straight + n_transition] = np.linspace(0, target_curvature, n_transition)
    # Arc: constant
    kappa[n_straight + n_transition :] = target_curvature

    # Integrate curvature to get heading
    heading = np.cumsum(kappa) * step_m  # theta(s) = integral of kappa ds

    # Integrate heading to get XY
    x = np.cumsum(np.cos(heading)) * step_m
    y = np.cumsum(np.sin(heading)) * step_m

    return x, y, distance


def _s_curve_xy(
    n_per_section: int = 200,
    step_m: float = 0.5,
    curvature_magnitude: float = 0.01,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate an S-curve: left turn -> transition -> right turn.

    Curvature goes +kappa -> linearly through 0 -> -kappa.
    """
    n_total = n_per_section * 3
    distance = np.arange(n_total, dtype=np.float64) * step_m

    kappa = np.zeros(n_total, dtype=np.float64)
    # Left turn (positive curvature)
    kappa[:n_per_section] = curvature_magnitude
    # Transition through zero
    kappa[n_per_section : 2 * n_per_section] = np.linspace(
        curvature_magnitude, -curvature_magnitude, n_per_section
    )
    # Right turn (negative curvature)
    kappa[2 * n_per_section :] = -curvature_magnitude

    # Integrate to get heading and XY
    heading = np.cumsum(kappa) * step_m
    x = np.cumsum(np.cos(heading)) * step_m
    y = np.cumsum(np.sin(heading)) * step_m

    return x, y, distance


# ---------------------------------------------------------------------------
# Tests for fit_clothoid_segment
# ---------------------------------------------------------------------------


class TestFitClothoidSegment:
    """Tests for the single-segment clothoid fitting."""

    def test_straight_segment_zero_curvature(self) -> None:
        """Straight segment: both kappa0 and kappa1 should be ~0."""
        # Two points on a straight line with same heading
        kappa0, kappa1, arc_len = fit_clothoid_segment(
            x0=0.0,
            y0=0.0,
            theta0=0.3,
            x1=100 * np.cos(0.3),
            y1=100 * np.sin(0.3),
            theta1=0.3,
        )
        assert abs(kappa0) < 1e-6, f"kappa0 should be ~0 for straight, got {kappa0}"
        assert abs(kappa1) < 1e-6, f"kappa1 should be ~0 for straight, got {kappa1}"
        assert arc_len > 0, "arc length must be positive"

    def test_circular_arc_constant_curvature(self) -> None:
        """Circular arc: kappa0 and kappa1 should both be ~1/R."""
        radius = 100.0
        # Start and end of a 90-degree arc
        theta_start = 0.0
        theta_end = np.pi / 2
        x0, y0 = radius * np.cos(theta_start), radius * np.sin(theta_start)
        x1, y1 = radius * np.cos(theta_end), radius * np.sin(theta_end)
        # Heading is tangent to circle: perpendicular to radius
        heading0 = theta_start + np.pi / 2
        heading1 = theta_end + np.pi / 2

        kappa0, kappa1, arc_len = fit_clothoid_segment(
            x0=x0,
            y0=y0,
            theta0=heading0,
            x1=x1,
            y1=y1,
            theta1=heading1,
        )
        expected_kappa = 1.0 / radius
        assert abs(kappa0 - expected_kappa) < 0.005, (
            f"kappa0 should be ~{expected_kappa}, got {kappa0}"
        )
        assert abs(kappa1 - expected_kappa) < 0.005, (
            f"kappa1 should be ~{expected_kappa}, got {kappa1}"
        )

    def test_clothoid_curvatures_differ(self) -> None:
        """A true clothoid segment should have kappa0 != kappa1."""
        # Transition from straight (heading 0) to curved
        # Use heading change that implies increasing curvature
        kappa0, kappa1, arc_len = fit_clothoid_segment(
            x0=0.0,
            y0=0.0,
            theta0=0.0,
            x1=50.0,
            y1=10.0,
            theta1=0.4,
        )
        assert abs(kappa1 - kappa0) > 1e-4, (
            f"For a clothoid, kappa0={kappa0} and kappa1={kappa1} should differ"
        )


# ---------------------------------------------------------------------------
# Tests for compute_clothoid_curvature
# ---------------------------------------------------------------------------


class TestComputeClothoidCurvature:
    """Tests for the full piecewise-clothoid curvature computation."""

    def test_straight_line_zero_curvature(self) -> None:
        """A perfectly straight track should have near-zero curvature everywhere."""
        x, y, dist = _straight_line_xy(n=500, step_m=0.7)
        kappa = compute_clothoid_curvature(x, y, dist)

        assert kappa.shape == dist.shape
        assert np.max(np.abs(kappa)) < 1e-4, (
            f"Straight line curvature should be ~0, got max |kappa|={np.max(np.abs(kappa))}"
        )

    def test_circular_arc_constant_curvature(self) -> None:
        """A circular arc should produce roughly constant curvature ~ 1/R."""
        radius = 100.0
        x, y, dist = _circular_arc_xy(radius_m=radius, n=500, arc_fraction=0.5)
        kappa = compute_clothoid_curvature(x, y, dist)

        assert kappa.shape == dist.shape
        expected = 1.0 / radius  # 0.01

        # Check interior points (skip first/last 10% for boundary effects)
        interior = kappa[50:-50]
        median_kappa = np.median(interior)
        assert abs(median_kappa - expected) < 0.003, (
            f"Circular arc median curvature should be ~{expected}, got {median_kappa}"
        )

    def test_clothoid_transition_linearly_increasing(self) -> None:
        """Track with straight->clothoid->arc should show linearly increasing
        curvature in the transition zone."""
        target_kappa = 0.01
        x, y, dist = _clothoid_transition_xy(
            n_straight=200,
            n_transition=200,
            n_arc=200,
            step_m=0.5,
            target_curvature=target_kappa,
        )
        kappa = compute_clothoid_curvature(x, y, dist)

        assert kappa.shape == dist.shape

        # In the straight section (skip first few points), curvature ~ 0
        straight_kappa = kappa[20:180]
        assert np.max(np.abs(straight_kappa)) < 0.003, (
            f"Straight section max |kappa| = {np.max(np.abs(straight_kappa))}, expected < 0.003"
        )

        # In the arc section, curvature ~ target_kappa
        arc_kappa = kappa[420:580]
        arc_median = np.median(arc_kappa)
        assert abs(arc_median - target_kappa) < 0.003, (
            f"Arc section median kappa = {arc_median}, expected ~{target_kappa}"
        )

        # In the transition zone, curvature should be monotonically increasing
        # (approximately — allow some noise)
        transition_kappa = kappa[210:390]
        # Check that the first quarter is lower than the last quarter
        q1 = np.median(transition_kappa[: len(transition_kappa) // 4])
        q4 = np.median(transition_kappa[3 * len(transition_kappa) // 4 :])
        assert q4 > q1, f"Transition curvature should increase: q1={q1}, q4={q4}"

    def test_s_curve_sign_change(self) -> None:
        """S-curve should show curvature changing sign from positive to negative."""
        kappa_mag = 0.01
        x, y, dist = _s_curve_xy(
            n_per_section=200,
            step_m=0.5,
            curvature_magnitude=kappa_mag,
        )
        kappa = compute_clothoid_curvature(x, y, dist)

        assert kappa.shape == dist.shape

        # First section (left turn): predominantly positive curvature
        left_section = kappa[20:180]
        assert np.median(left_section) > 0, (
            f"Left-turn section should have positive curvature, "
            f"got median={np.median(left_section)}"
        )

        # Last section (right turn): predominantly negative curvature
        right_section = kappa[420:580]
        assert np.median(right_section) < 0, (
            f"Right-turn section should have negative curvature, "
            f"got median={np.median(right_section)}"
        )

    def test_output_length_matches_input(self) -> None:
        """Output curvature array must have same length as input arrays."""
        x, y, dist = _straight_line_xy(n=123, step_m=1.0)
        kappa = compute_clothoid_curvature(x, y, dist)
        assert len(kappa) == 123

    def test_short_input_handled(self) -> None:
        """Very short input (< 5 points) should not crash."""
        x = np.array([0.0, 1.0, 2.0])
        y = np.array([0.0, 0.0, 0.0])
        dist = np.array([0.0, 1.0, 2.0])
        kappa = compute_clothoid_curvature(x, y, dist)
        assert len(kappa) == 3

    def test_minimum_two_points(self) -> None:
        """With fewer than 2 points, should return zeros or handle gracefully."""
        x = np.array([0.0])
        y = np.array([0.0])
        dist = np.array([0.0])
        kappa = compute_clothoid_curvature(x, y, dist)
        assert len(kappa) == 1
        assert kappa[0] == 0.0

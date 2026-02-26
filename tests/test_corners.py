"""Tests for cataclysm.corners."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cataclysm.corners import (
    CORNER_TYPE_TIPS,
    Corner,
    _classify_apex,
    _compute_heading_rate,
    _find_brake_point,
    _find_contiguous_regions,
    _find_throttle_commit,
    _merge_regions,
    _smooth,
    classify_corner_type,
    detect_corners,
    extract_corner_kpis_for_lap,
)


class TestComputeHeadingRate:
    def test_constant_heading(self) -> None:
        heading = np.full(100, 90.0)
        rate = _compute_heading_rate(heading, step_m=0.7)
        np.testing.assert_allclose(rate, 0.0, atol=1e-10)

    def test_linear_heading(self) -> None:
        heading = np.linspace(0, 70, 100)  # 70 degrees over 100 points
        rate = _compute_heading_rate(heading, step_m=1.0)
        # Should be approximately constant (~0.707 deg/m)
        expected = 70.0 / 99.0
        np.testing.assert_allclose(rate[:-1], expected, atol=0.01)

    def test_wrap_around(self) -> None:
        """Heading crossing 360/0 boundary should not create a spike."""
        heading = np.array([350.0, 355.0, 0.0, 5.0, 10.0])
        rate = _compute_heading_rate(heading, step_m=1.0)
        # All changes are +5 degrees
        np.testing.assert_allclose(rate[:4], 5.0, atol=0.01)

    def test_reverse_wrap(self) -> None:
        heading = np.array([10.0, 5.0, 0.0, 355.0, 350.0])
        rate = _compute_heading_rate(heading, step_m=1.0)
        np.testing.assert_allclose(rate[:4], -5.0, atol=0.01)


class TestSmooth:
    def test_preserves_constant(self) -> None:
        values = np.full(50, 5.0)
        smoothed = _smooth(values, 10)
        # Edge effects from convolution are expected; check the middle
        np.testing.assert_allclose(smoothed[10:-10], 5.0, atol=0.01)

    def test_reduces_noise(self) -> None:
        rng = np.random.default_rng(42)
        values = np.full(200, 10.0) + rng.normal(0, 1, 200)
        smoothed = _smooth(values, 20)
        assert np.std(smoothed[20:-20]) < np.std(values[20:-20])

    def test_small_window(self) -> None:
        values = np.array([1.0, 2.0, 3.0])
        result = _smooth(values, 1)
        np.testing.assert_allclose(result, values)


class TestFindContiguousRegions:
    def test_single_region(self) -> None:
        mask = np.array([False, True, True, True, False])
        regions = _find_contiguous_regions(mask)
        assert regions == [(1, 4)]

    def test_multiple_regions(self) -> None:
        mask = np.array([True, True, False, True, True, True, False])
        regions = _find_contiguous_regions(mask)
        assert regions == [(0, 2), (3, 6)]

    def test_empty(self) -> None:
        mask = np.array([False, False, False])
        regions = _find_contiguous_regions(mask)
        assert regions == []

    def test_all_true(self) -> None:
        mask = np.array([True, True, True])
        regions = _find_contiguous_regions(mask)
        assert regions == [(0, 3)]

    def test_starts_true(self) -> None:
        mask = np.array([True, True, False, False])
        regions = _find_contiguous_regions(mask)
        assert regions == [(0, 2)]

    def test_ends_true(self) -> None:
        mask = np.array([False, False, True, True])
        regions = _find_contiguous_regions(mask)
        assert regions == [(2, 4)]


class TestMergeRegions:
    def test_merges_close_regions(self) -> None:
        regions = [(0, 10), (12, 20)]
        merged = _merge_regions(regions, gap_points=5)
        assert merged == [(0, 20)]

    def test_keeps_distant_regions(self) -> None:
        regions = [(0, 10), (30, 40)]
        merged = _merge_regions(regions, gap_points=5)
        assert merged == [(0, 10), (30, 40)]

    def test_single_region(self) -> None:
        regions = [(5, 15)]
        merged = _merge_regions(regions, gap_points=5)
        assert merged == [(5, 15)]

    def test_empty(self) -> None:
        assert _merge_regions([], gap_points=5) == []


class TestFindBrakePoint:
    def test_detects_braking(self) -> None:
        lon_g = np.zeros(200)
        # Braking starts at index 80
        lon_g[80:100] = -0.5
        brake_idx, peak_g = _find_brake_point(lon_g, entry_idx=100, apex_idx=130, step_m=0.7)
        assert brake_idx is not None
        assert brake_idx == 80
        assert peak_g is not None
        assert peak_g < -0.1

    def test_braking_inside_corner(self) -> None:
        """Braking that starts inside the corner zone should still be detected."""
        lon_g = np.zeros(200)
        # Braking starts at index 105, inside the corner (entry=100, apex=130)
        lon_g[105:125] = -0.4
        brake_idx, peak_g = _find_brake_point(lon_g, entry_idx=100, apex_idx=130, step_m=0.7)
        assert brake_idx is not None
        assert brake_idx == 105
        assert peak_g is not None

    def test_no_braking(self) -> None:
        lon_g = np.zeros(200)
        brake_idx, peak_g = _find_brake_point(lon_g, entry_idx=100, apex_idx=130, step_m=0.7)
        assert brake_idx is None
        assert peak_g is None

    def test_brake_point_clamped_to_prev_exit(self) -> None:
        """Braking before prev_exit_idx should be ignored (belongs to previous corner)."""
        lon_g = np.zeros(300)
        # Braking at index 60–80, which is before prev corner's exit at 90
        lon_g[60:80] = -0.6
        brake_idx, peak_g = _find_brake_point(
            lon_g, entry_idx=150, apex_idx=180, step_m=0.7, prev_exit_idx=90
        )
        # The braking at 60-80 should be excluded (before prev_exit=90)
        assert brake_idx is None
        assert peak_g is None

    def test_brake_point_no_clamp_without_prev(self) -> None:
        """Without prev_exit_idx, braking before entry should still be detected."""
        lon_g = np.zeros(300)
        # Same braking at index 60–80
        lon_g[60:80] = -0.6
        brake_idx, peak_g = _find_brake_point(lon_g, entry_idx=150, apex_idx=180, step_m=0.7)
        # Without clamping, the search window extends back and finds it
        assert brake_idx is not None
        assert brake_idx == 60
        assert peak_g is not None

    def test_brake_after_prev_exit_still_detected(self) -> None:
        """Braking between prev_exit and entry should be detected."""
        lon_g = np.zeros(300)
        # Braking at index 120–140, after prev exit at 90 and before entry at 150
        lon_g[120:140] = -0.5
        brake_idx, peak_g = _find_brake_point(
            lon_g, entry_idx=150, apex_idx=180, step_m=0.7, prev_exit_idx=90
        )
        assert brake_idx is not None
        assert brake_idx == 120
        assert peak_g is not None


class TestFindThrottleCommit:
    def test_detects_throttle(self) -> None:
        lon_g = np.zeros(200)
        # Sustained throttle starting at index 120
        lon_g[120:150] = 0.3
        idx = _find_throttle_commit(lon_g, apex_idx=100, exit_idx=180, step_m=0.7)
        assert idx is not None
        assert 120 <= idx <= 130

    def test_no_throttle(self) -> None:
        lon_g = np.zeros(200)
        idx = _find_throttle_commit(lon_g, apex_idx=100, exit_idx=180, step_m=0.7)
        assert idx is None

    def test_unsustained_throttle(self) -> None:
        """Short throttle blip should not count."""
        lon_g = np.zeros(200)
        lon_g[120:123] = 0.3  # only 3 points, not sustained
        idx = _find_throttle_commit(lon_g, apex_idx=100, exit_idx=180, step_m=0.7)
        assert idx is None


class TestClassifyApex:
    """Apex classification is now relative to the geometric apex (peak curvature).

    geo_apex_idx=50 in all tests means peak curvature is at the midpoint.
    The speed apex is compared against that reference.
    """

    def test_early(self) -> None:
        # Speed apex at 20, geometric apex at 50 → offset = -0.30 → early
        assert (
            _classify_apex(speed_apex_idx=20, geo_apex_idx=50, entry_idx=0, exit_idx=100) == "early"
        )

    def test_mid(self) -> None:
        # Speed apex at 50, geometric apex at 50 → offset = 0 → mid
        assert (
            _classify_apex(speed_apex_idx=50, geo_apex_idx=50, entry_idx=0, exit_idx=100) == "mid"
        )

    def test_late(self) -> None:
        # Speed apex at 70, geometric apex at 50 → offset = 0.20 → late
        assert (
            _classify_apex(speed_apex_idx=70, geo_apex_idx=50, entry_idx=0, exit_idx=100) == "late"
        )

    def test_zero_span(self) -> None:
        assert (
            _classify_apex(speed_apex_idx=50, geo_apex_idx=50, entry_idx=50, exit_idx=50) == "mid"
        )

    def test_within_tolerance_is_mid(self) -> None:
        # Speed apex at 55, geometric apex at 50 → offset = 0.05 → within ±0.10 → mid
        assert (
            _classify_apex(speed_apex_idx=55, geo_apex_idx=50, entry_idx=0, exit_idx=100) == "mid"
        )


class TestDetectCorners:
    def test_detects_corners_in_synthetic_data(self, sample_resampled_lap: pd.DataFrame) -> None:
        corners = detect_corners(sample_resampled_lap)
        assert len(corners) > 0
        for c in corners:
            assert isinstance(c, Corner)
            assert c.entry_distance_m < c.exit_distance_m
            assert c.min_speed_mps > 0

    def test_corner_numbers_sequential(self, sample_resampled_lap: pd.DataFrame) -> None:
        corners = detect_corners(sample_resampled_lap)
        for i, c in enumerate(corners, start=1):
            assert c.number == i

    def test_no_corners_on_straight(self) -> None:
        n = 500
        df = pd.DataFrame(
            {
                "lap_distance_m": np.arange(n) * 0.7,
                "speed_mps": np.ones(n) * 40.0,
                "heading_deg": np.full(n, 90.0),  # constant heading = straight
                "longitudinal_g": np.zeros(n),
                "lateral_g": np.zeros(n),
            }
        )
        corners = detect_corners(df)
        assert len(corners) == 0


class TestExtractCornerKpis:
    def test_uses_reference_boundaries(self, sample_resampled_lap: pd.DataFrame) -> None:
        ref_corners = detect_corners(sample_resampled_lap)
        if not ref_corners:
            pytest.skip("No corners detected in synthetic data")

        # Use same lap as comparison (KPIs should match)
        comp_corners = extract_corner_kpis_for_lap(sample_resampled_lap, ref_corners)
        assert len(comp_corners) == len(ref_corners)
        for rc, cc in zip(ref_corners, comp_corners, strict=True):
            assert rc.number == cc.number
            assert rc.entry_distance_m == cc.entry_distance_m
            # Min speed should be the same since same lap
            assert abs(rc.min_speed_mps - cc.min_speed_mps) < 0.1


class TestClassifyCornerType:
    def test_slow_corner(self) -> None:
        """Corner with <40 mph apex should be classified as slow."""
        c = Corner(
            number=1,
            entry_distance_m=0,
            exit_distance_m=100,
            apex_distance_m=50,
            min_speed_mps=15.0,  # ~33.6 mph
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        assert classify_corner_type(c) == "slow"

    def test_medium_corner(self) -> None:
        """Corner with 40-80 mph apex should be classified as medium."""
        c = Corner(
            number=1,
            entry_distance_m=0,
            exit_distance_m=100,
            apex_distance_m=50,
            min_speed_mps=25.0,  # ~55.9 mph
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        assert classify_corner_type(c) == "medium"

    def test_fast_corner(self) -> None:
        """Corner with >80 mph apex should be classified as fast."""
        c = Corner(
            number=1,
            entry_distance_m=0,
            exit_distance_m=100,
            apex_distance_m=50,
            min_speed_mps=40.0,  # ~89.5 mph
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        assert classify_corner_type(c) == "fast"

    def test_boundary_slow_medium(self) -> None:
        """Exactly 40 mph should be medium (not slow)."""
        speed_mps = 40.0 / 2.23694
        c = Corner(
            number=1,
            entry_distance_m=0,
            exit_distance_m=100,
            apex_distance_m=50,
            min_speed_mps=speed_mps,
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        assert classify_corner_type(c) == "medium"

    def test_boundary_medium_fast(self) -> None:
        """Exactly 80 mph should be fast (not medium)."""
        speed_mps = 80.0 / 2.23694
        c = Corner(
            number=1,
            entry_distance_m=0,
            exit_distance_m=100,
            apex_distance_m=50,
            min_speed_mps=speed_mps,
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        assert classify_corner_type(c) == "fast"


class TestGPSFields:
    """Corner GPS coordinate fields (brake_point_lat/lon, apex_lat/lon)."""

    def test_gps_fields_default_none(self) -> None:
        """GPS fields should default to None when not provided."""
        c = Corner(
            number=1,
            entry_distance_m=0,
            exit_distance_m=100,
            apex_distance_m=50,
            min_speed_mps=20.0,
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        assert c.brake_point_lat is None
        assert c.brake_point_lon is None
        assert c.apex_lat is None
        assert c.apex_lon is None

    def test_gps_fields_populated(self) -> None:
        c = Corner(
            number=1,
            entry_distance_m=0,
            exit_distance_m=100,
            apex_distance_m=50,
            min_speed_mps=20.0,
            brake_point_m=30.0,
            peak_brake_g=-0.5,
            throttle_commit_m=70.0,
            apex_type="mid",
            brake_point_lat=33.53,
            brake_point_lon=-86.62,
            apex_lat=33.531,
            apex_lon=-86.621,
        )
        assert c.brake_point_lat == 33.53
        assert c.brake_point_lon == -86.62
        assert c.apex_lat == 33.531
        assert c.apex_lon == -86.621

    def test_detect_corners_populates_gps(self, sample_resampled_lap: pd.DataFrame) -> None:
        """detect_corners should populate GPS fields when lat/lon exist."""
        assert "lat" in sample_resampled_lap.columns
        assert "lon" in sample_resampled_lap.columns
        corners = detect_corners(sample_resampled_lap)
        if not corners:
            pytest.skip("No corners detected in synthetic data")
        for c in corners:
            # Apex GPS should always be populated when lat/lon exist
            assert c.apex_lat is not None
            assert c.apex_lon is not None

    def test_detect_corners_no_gps(self) -> None:
        """detect_corners without lat/lon columns should leave GPS fields None."""
        n = 1000
        step = 0.7
        distance = np.arange(n) * step
        heading = np.zeros(n)
        speed = np.ones(n) * 40.0
        for center in [250, 750]:
            for j in range(max(0, center - 40), min(n, center + 40)):
                offset = j - center
                heading[j] = heading[max(0, j - 1)] + 3.0 * np.exp(-(offset**2) / 200)
                speed[j] = 40.0 - 15.0 * np.exp(-(offset**2) / 200)
        heading = np.cumsum(np.concatenate([[0], np.diff(heading)])) % 360
        lon_g = np.gradient(speed) / 9.81 * 10
        df = pd.DataFrame(
            {
                "lap_distance_m": distance,
                "speed_mps": speed,
                "heading_deg": heading % 360,
                "longitudinal_g": lon_g,
                "lateral_g": np.zeros(n),
            }
        )
        corners = detect_corners(df)
        for c in corners:
            assert c.brake_point_lat is None
            assert c.brake_point_lon is None
            assert c.apex_lat is None
            assert c.apex_lon is None

    def test_extract_kpis_populates_gps(self, sample_resampled_lap: pd.DataFrame) -> None:
        """extract_corner_kpis_for_lap should populate GPS when lat/lon exist."""
        ref_corners = detect_corners(sample_resampled_lap)
        if not ref_corners:
            pytest.skip("No corners detected")
        result = extract_corner_kpis_for_lap(sample_resampled_lap, ref_corners)
        for c in result:
            assert c.apex_lat is not None
            assert c.apex_lon is not None


class TestCornerTypeTips:
    def test_all_types_have_tips(self) -> None:
        """Every corner type should have a technique tip."""
        for ctype in ["slow", "medium", "fast"]:
            assert ctype in CORNER_TYPE_TIPS
            assert len(CORNER_TYPE_TIPS[ctype]) > 0


class TestDetectCornersAdvanced:
    """Tests for advanced detection methods (spline, pelt, css, asc)."""

    @pytest.mark.parametrize("method", ["spline", "pelt", "css", "asc"])
    def test_advanced_method_detects_corners(
        self, sample_resampled_lap: pd.DataFrame, method: str
    ) -> None:
        corners = detect_corners(sample_resampled_lap, method=method)
        assert len(corners) > 0
        for c in corners:
            assert isinstance(c, Corner)
            assert c.entry_distance_m < c.exit_distance_m
            assert c.min_speed_mps > 0
            assert c.detection_method == method

    @pytest.mark.parametrize("method", ["spline", "pelt", "css", "asc"])
    def test_advanced_has_curvature_fields(
        self, sample_resampled_lap: pd.DataFrame, method: str
    ) -> None:
        corners = detect_corners(sample_resampled_lap, method=method)
        if not corners:
            pytest.skip("No corners detected")
        for c in corners:
            assert c.peak_curvature is not None
            assert c.mean_curvature is not None
            assert c.direction in ("left", "right")
            assert c.segment_type == "corner"

    def test_unknown_method_raises(self, sample_resampled_lap: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="Unknown detection method"):
            detect_corners(sample_resampled_lap, method="invalid")


class TestBackwardCompatibility:
    """Ensure default method produces identical results."""

    def test_default_method_is_heading_rate(self, sample_resampled_lap: pd.DataFrame) -> None:
        default = detect_corners(sample_resampled_lap)
        explicit = detect_corners(sample_resampled_lap, method="heading_rate")
        assert len(default) == len(explicit)
        for d, e in zip(default, explicit, strict=True):
            assert d.number == e.number
            assert d.entry_distance_m == e.entry_distance_m
            assert d.exit_distance_m == e.exit_distance_m
            assert d.min_speed_mps == e.min_speed_mps

    def test_new_fields_default_none(self) -> None:
        c = Corner(
            number=1,
            entry_distance_m=0,
            exit_distance_m=100,
            apex_distance_m=50,
            min_speed_mps=20.0,
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        assert c.peak_curvature is None
        assert c.mean_curvature is None
        assert c.direction is None
        assert c.segment_type is None
        assert c.parent_complex is None
        assert c.detection_method is None
        assert c.character is None

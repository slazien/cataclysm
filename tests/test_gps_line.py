"""Tests for cataclysm.gps_line — GPS trace processing and reference centerline."""

from __future__ import annotations

import numpy as np

from cataclysm.gps_line import (
    GPSTrace,
    compute_lateral_offsets,
    compute_reference_centerline,
    gps_to_enu,
    should_enable_line_analysis,
    smooth_gps_trace,
)
from cataclysm.gps_quality import GPSQualityReport


class TestGPSToENU:
    def test_origin_maps_to_zero(self) -> None:
        lat = np.array([33.5])
        lon = np.array([-86.6])
        e, n = gps_to_enu(lat, lon, 33.5, -86.6)
        assert abs(e[0]) < 1e-6
        assert abs(n[0]) < 1e-6

    def test_east_is_positive_longitude(self) -> None:
        """Moving east (higher longitude) should produce positive E."""
        lat = np.array([33.5, 33.5])
        lon = np.array([-86.6, -86.5999])  # Small east offset
        e, n = gps_to_enu(lat, lon, 33.5, -86.6)
        assert e[1] > 0  # East of origin
        assert abs(n[1]) < 1.0  # Same latitude, near-zero north

    def test_north_is_positive_latitude(self) -> None:
        """Moving north (higher latitude) should produce positive N."""
        lat = np.array([33.5, 33.5001])
        lon = np.array([-86.6, -86.6])
        e, n = gps_to_enu(lat, lon, 33.5, -86.6)
        assert abs(e[1]) < 1.0
        assert n[1] > 0

    def test_roundtrip_submeter_accuracy(self) -> None:
        """Convert to ENU and compute distance; compare to known geo distance."""
        # Two points ~111m apart (1/1000 degree at equator latitude)
        lat = np.array([33.5, 33.501])
        lon = np.array([-86.6, -86.6])
        e, n = gps_to_enu(lat, lon, 33.5, -86.6)
        dist = np.sqrt(e[1] ** 2 + n[1] ** 2)
        # 0.001 degree latitude ~ 111m
        assert 100 < dist < 120


class TestSmoothGPSTrace:
    def test_preserves_shape_on_straight(self) -> None:
        """Smoothed straight line should stay close to original."""
        n = 100
        e = np.linspace(0, 100, n)
        north = np.zeros(n)
        e_s, n_s = smooth_gps_trace(e, north)
        assert np.allclose(e_s, e, atol=0.5)
        assert np.allclose(n_s, north, atol=0.5)

    def test_reduces_noise(self) -> None:
        """Adding noise then smoothing should produce lower variance."""
        n = 200
        rng = np.random.default_rng(42)
        e_true = np.linspace(0, 200, n)
        n_true = np.sin(np.linspace(0, 2 * np.pi, n)) * 20
        e_noisy = e_true + rng.normal(0, 0.5, n)
        n_noisy = n_true + rng.normal(0, 0.5, n)
        e_s, n_s = smooth_gps_trace(e_noisy, n_noisy)
        # Smoothed should be closer to true than noisy
        noisy_err = np.mean(np.sqrt((e_noisy - e_true) ** 2 + (n_noisy - n_true) ** 2))
        smooth_err = np.mean(np.sqrt((e_s - e_true) ** 2 + (n_s - n_true) ** 2))
        assert smooth_err < noisy_err

    def test_short_trace_returns_copy(self) -> None:
        """Trace shorter than window should return a copy, not crash."""
        e = np.array([0.0, 1.0, 2.0])
        n = np.array([0.0, 0.0, 0.0])
        e_s, n_s = smooth_gps_trace(e, n)
        np.testing.assert_array_equal(e_s, e)


class TestReferenceCenterline:
    def _make_traces(self, n_laps: int = 5, n_points: int = 200) -> list[GPSTrace]:
        rng = np.random.default_rng(42)
        traces = []
        distance = np.linspace(0, 140, n_points)
        for i in range(n_laps):
            # Circle with some noise
            theta = np.linspace(0, 2 * np.pi, n_points)
            e = 50 * np.cos(theta) + rng.normal(0, 0.3, n_points)
            n = 50 * np.sin(theta) + rng.normal(0, 0.3, n_points)
            traces.append(GPSTrace(e=e, n=n, distance_m=distance, lap_number=i + 1))
        return traces

    def test_needs_minimum_laps(self) -> None:
        traces = self._make_traces(n_laps=2)
        ref = compute_reference_centerline(traces, min_laps=3)
        assert ref is None

    def test_builds_from_enough_laps(self) -> None:
        traces = self._make_traces(n_laps=5)
        ref = compute_reference_centerline(traces)
        assert ref is not None
        assert ref.n_laps_used == 5
        assert len(ref.e) == len(ref.n)

    def test_median_robustness_to_outlier(self) -> None:
        """An outlier lap should not distort the reference."""
        traces = self._make_traces(n_laps=5)
        # Add an outlier lap with huge offset
        outlier = GPSTrace(
            e=traces[0].e + 100,  # 100m off
            n=traces[0].n,
            distance_m=traces[0].distance_m,
            lap_number=99,
        )
        traces_with_outlier = traces + [outlier]
        ref_clean = compute_reference_centerline(traces)
        ref_outlier = compute_reference_centerline(traces_with_outlier)
        assert ref_clean is not None
        assert ref_outlier is not None
        # Median should keep the reference close despite the outlier
        assert np.mean(np.abs(ref_clean.e - ref_outlier.e)) < 5.0

    def test_track_edges_computed(self) -> None:
        traces = self._make_traces()
        ref = compute_reference_centerline(traces)
        assert ref is not None
        assert len(ref.left_edge) == len(ref.e)
        assert len(ref.right_edge) == len(ref.e)
        # Left edge should generally be <= right edge
        assert np.mean(ref.left_edge < ref.right_edge) > 0.9


class TestLateralOffsets:
    def test_zero_offset_on_reference(self) -> None:
        """A trace identical to the reference should have ~zero offsets."""
        e = np.linspace(0, 100, 200)
        n = np.zeros(200)
        distance = np.linspace(0, 140, 200)
        trace = GPSTrace(e=e, n=n, distance_m=distance, lap_number=1)
        # Build a fake reference from the same trace
        traces = [
            GPSTrace(e=e.copy(), n=n.copy(), distance_m=distance, lap_number=i) for i in range(3)
        ]
        ref = compute_reference_centerline(traces)
        assert ref is not None
        offsets = compute_lateral_offsets(trace, ref)
        assert np.max(np.abs(offsets)) < 0.01

    def test_known_offset_sign(self) -> None:
        """Point right of reference -> positive offset."""
        n_pts = 100
        e_ref = np.linspace(0, 100, n_pts)
        n_ref = np.zeros(n_pts)
        distance = np.linspace(0, 70, n_pts)

        # Trace 1m to the right (positive N for east-going reference)
        e_trace = e_ref.copy()
        n_trace = np.full(n_pts, -1.0)  # Below the reference
        trace = GPSTrace(e=e_trace, n=n_trace, distance_m=distance, lap_number=1)

        traces_for_ref = [
            GPSTrace(e=e_ref.copy(), n=n_ref.copy(), distance_m=distance, lap_number=i)
            for i in range(3)
        ]
        ref = compute_reference_centerline(traces_for_ref)
        assert ref is not None
        offsets = compute_lateral_offsets(trace, ref)
        # All offsets should be consistently signed (either all positive or all negative)
        mid_offsets = offsets[10:-10]  # Skip edges
        assert np.std(np.sign(mid_offsets)) < 0.5  # Consistent sign


class TestShouldEnableLineAnalysis:
    def test_grade_a_enabled(self) -> None:
        report = _make_gps_report("A")
        assert should_enable_line_analysis(report) is True

    def test_grade_b_enabled(self) -> None:
        report = _make_gps_report("B")
        assert should_enable_line_analysis(report) is True

    def test_grade_c_disabled(self) -> None:
        report = _make_gps_report("C")
        assert should_enable_line_analysis(report) is False

    def test_grade_d_disabled(self) -> None:
        report = _make_gps_report("D")
        assert should_enable_line_analysis(report) is False


def _make_gps_report(grade: str) -> GPSQualityReport:
    """Create a minimal GPSQualityReport for testing."""
    from cataclysm.gps_quality import (
        AccuracyStats,
        HeadingJitterStats,
        LateralScatterStats,
        SatelliteStats,
        SpeedSpikeStats,
    )

    return GPSQualityReport(
        overall_score=80.0,
        grade=grade,
        is_usable=True,
        accuracy=AccuracyStats(p50=0.5, p90=1.0, score=80.0),
        satellites=SatelliteStats(p10=10.0, p50=12.0, score=80.0),
        lap_distance_cv=None,
        speed_spikes=SpeedSpikeStats(
            spikes_per_km=0.0, total_spikes=0, total_distance_km=5.0, score=100.0
        ),
        heading_jitter=HeadingJitterStats(jitter_std=0.1, straight_fraction=0.5, score=80.0),
        lateral_scatter=LateralScatterStats(scatter_p90=0.3, score=80.0),
        metric_weights={"accuracy_p90": 0.3},
    )

"""Tests for cataclysm.charts."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from cataclysm.charts import (
    brake_consistency_chart,
    brake_throttle_chart,
    consistency_trend_chart,
    corner_detail_chart,
    corner_heatmap_chart,
    corner_kpi_table,
    corner_mini_map,
    corner_trend_chart,
    delta_t_chart,
    g_force_chart,
    gain_per_corner_chart,
    ideal_lap_delta_chart,
    ideal_lap_overlay_chart,
    lap_time_trend_chart,
    lap_times_chart,
    milestone_summary,
    session_comparison_box_chart,
    speed_trace_chart,
    track_map_chart,
    track_median_speed_map,
    traction_utilization_chart,
)
from cataclysm.consistency import TrackPositionConsistency
from cataclysm.corners import Corner
from cataclysm.delta import DeltaResult
from cataclysm.engine import LapSummary
from cataclysm.gains import (
    CompositeGainResult,
    ConsistencyGainResult,
    GainEstimate,
    SegmentDefinition,
    SegmentGain,
    TheoreticalBestResult,
)
from cataclysm.trends import SessionSnapshot, TrendAnalysis, compute_trend_analysis


@pytest.fixture
def lap_summaries() -> list[LapSummary]:
    return [
        LapSummary(1, 92.5, 3800.0, 45.0),
        LapSummary(2, 94.2, 3810.0, 44.0),
        LapSummary(3, 93.1, 3805.0, 44.5),
    ]


@pytest.fixture
def sample_laps() -> dict[int, pd.DataFrame]:
    laps: dict[int, pd.DataFrame] = {}
    for lap_num in (1, 2, 3):
        n = 500
        speed_offset = (lap_num - 1) * 2
        laps[lap_num] = pd.DataFrame(
            {
                "lap_distance_m": np.arange(n) * 0.7,
                "speed_mps": np.full(n, 30.0 - speed_offset) + np.sin(np.arange(n) * 0.1) * 5,
                "lat": 33.53 + np.sin(np.arange(n) * 0.01) * 0.001,
                "lon": -86.62 + np.cos(np.arange(n) * 0.01) * 0.002,
                "heading_deg": np.linspace(0, 360, n) % 360,
                "lateral_g": np.sin(np.arange(n) * 0.05) * 0.5,
                "longitudinal_g": np.cos(np.arange(n) * 0.05) * 0.3,
                "lap_time_s": np.arange(n) * 0.023,
            }
        )
    return laps


@pytest.fixture
def sample_corners() -> list[Corner]:
    return [
        Corner(1, 50.0, 120.0, 85.0, 22.0, 30.0, -0.8, 130.0, "mid"),
        Corner(2, 200.0, 280.0, 240.0, 18.0, 180.0, -1.0, 290.0, "late"),
    ]


@pytest.fixture
def sample_delta() -> DeltaResult:
    n = 500
    return DeltaResult(
        distance_m=np.arange(n) * 0.7,
        delta_time_s=np.linspace(-0.5, 0.3, n),
        corner_deltas=[],
        total_delta_s=0.3,
    )


class TestLapTimesChart:
    def test_returns_figure(self, lap_summaries: list[LapSummary]) -> None:
        fig = lap_times_chart(lap_summaries)
        assert isinstance(fig, go.Figure)

    def test_has_bars(self, lap_summaries: list[LapSummary]) -> None:
        fig = lap_times_chart(lap_summaries)
        assert len(fig.data) == 1
        assert isinstance(fig.data[0], go.Bar)

    def test_correct_number_of_bars(self, lap_summaries: list[LapSummary]) -> None:
        fig = lap_times_chart(lap_summaries)
        assert len(fig.data[0].x) == 3


class TestSpeedTraceChart:
    def test_returns_figure(
        self, sample_laps: dict[int, pd.DataFrame], sample_corners: list[Corner]
    ) -> None:
        fig = speed_trace_chart(sample_laps, corners=sample_corners)
        assert isinstance(fig, go.Figure)

    def test_has_traces_for_selected_laps(self, sample_laps: dict[int, pd.DataFrame]) -> None:
        fig = speed_trace_chart(sample_laps, selected_laps=[1, 2])
        trace_names = [t.name for t in fig.data]
        assert "Lap 1" in trace_names
        assert "Lap 2" in trace_names
        assert "Lap 3" not in trace_names

    def test_default_shows_all(self, sample_laps: dict[int, pd.DataFrame]) -> None:
        fig = speed_trace_chart(sample_laps)
        assert len(fig.data) == 3


class TestDeltaTChart:
    def test_returns_figure(self, sample_delta: DeltaResult) -> None:
        fig = delta_t_chart(sample_delta, ref_lap=1, comp_lap=2)
        assert isinstance(fig, go.Figure)

    def test_has_traces(self, sample_delta: DeltaResult) -> None:
        fig = delta_t_chart(sample_delta, ref_lap=1, comp_lap=2)
        assert len(fig.data) >= 2  # positive fill, negative fill, main line

    def test_title_includes_laps(self, sample_delta: DeltaResult) -> None:
        fig = delta_t_chart(sample_delta, ref_lap=1, comp_lap=3)
        assert "L3" in fig.layout.title.text
        assert "L1" in fig.layout.title.text


class TestTrackMapChart:
    def test_returns_figure(
        self, sample_laps: dict[int, pd.DataFrame], sample_corners: list[Corner]
    ) -> None:
        fig = track_map_chart(sample_laps[1], lap_number=1, corners=sample_corners)
        assert isinstance(fig, go.Figure)

    def test_no_corners(self, sample_laps: dict[int, pd.DataFrame]) -> None:
        fig = track_map_chart(sample_laps[1], lap_number=1)
        assert isinstance(fig, go.Figure)


class TestCornerMiniMap:
    def test_returns_figure(
        self, sample_laps: dict[int, pd.DataFrame], sample_corners: list[Corner]
    ) -> None:
        fig = corner_mini_map(sample_laps[1], sample_corners[0], sample_corners)
        assert isinstance(fig, go.Figure)

    def test_has_full_track_and_highlight(
        self, sample_laps: dict[int, pd.DataFrame], sample_corners: list[Corner]
    ) -> None:
        fig = corner_mini_map(sample_laps[1], sample_corners[0], sample_corners)
        # At least 2 traces: full track (gray) + highlighted section (colored)
        assert len(fig.data) >= 2

    def test_zoomed_to_corner(
        self, sample_laps: dict[int, pd.DataFrame], sample_corners: list[Corner]
    ) -> None:
        fig = corner_mini_map(sample_laps[1], sample_corners[0], sample_corners)
        # x-axis should have explicit range (zoomed in), not autorange
        assert fig.layout.xaxis.range is not None

    def test_labels_target_corner(
        self, sample_laps: dict[int, pd.DataFrame], sample_corners: list[Corner]
    ) -> None:
        fig = corner_mini_map(sample_laps[1], sample_corners[0], sample_corners)
        annotations = fig.layout.annotations
        target_label = [a for a in annotations if "<b>T1</b>" in a.text]
        assert len(target_label) == 1


class TestCornerKpiTable:
    def test_returns_figure(self, sample_corners: list[Corner]) -> None:
        fig = corner_kpi_table(sample_corners)
        assert isinstance(fig, go.Figure)

    def test_with_comparison(self, sample_corners: list[Corner]) -> None:
        fig = corner_kpi_table(sample_corners, sample_corners)
        assert isinstance(fig, go.Figure)

    def test_with_deltas(self, sample_corners: list[Corner]) -> None:
        deltas = [
            {"corner_number": 1, "delta_s": 0.15},
            {"corner_number": 2, "delta_s": -0.08},
        ]
        fig = corner_kpi_table(sample_corners, sample_corners, deltas)
        assert isinstance(fig, go.Figure)


class TestGForceChart:
    def test_returns_figure(self, sample_laps: dict[int, pd.DataFrame]) -> None:
        fig = g_force_chart(sample_laps[1], lap_number=1)
        assert isinstance(fig, go.Figure)

    def test_has_scatter(self, sample_laps: dict[int, pd.DataFrame]) -> None:
        fig = g_force_chart(sample_laps[1], lap_number=1)
        assert len(fig.data) == 1


def _make_segment(name: str, entry: float, exit_m: float, *, is_corner: bool) -> SegmentDefinition:
    return SegmentDefinition(
        name=name, entry_distance_m=entry, exit_distance_m=exit_m, is_corner=is_corner
    )


def _make_segment_gain(
    seg: SegmentDefinition,
    best_time: float,
    avg_time: float,
    gain: float,
    best_lap: int = 1,
) -> SegmentGain:
    return SegmentGain(
        segment=seg,
        best_time_s=best_time,
        avg_time_s=avg_time,
        gain_s=gain,
        best_lap=best_lap,
        lap_times_s={1: best_time, 2: avg_time},
    )


@pytest.fixture
def sample_gains() -> GainEstimate:
    t1 = _make_segment("T1", 50.0, 120.0, is_corner=True)
    t2 = _make_segment("T2", 200.0, 280.0, is_corner=True)
    s1 = _make_segment("S1", 120.0, 200.0, is_corner=False)

    cons_segments = [
        _make_segment_gain(t1, 3.0, 3.5, 0.50),
        _make_segment_gain(s1, 2.0, 2.1, 0.10),
        _make_segment_gain(t2, 4.0, 4.8, 0.80),
    ]
    comp_segments = [
        _make_segment_gain(t1, 3.0, 3.5, 0.20),
        _make_segment_gain(s1, 2.0, 2.1, 0.05),
        _make_segment_gain(t2, 4.0, 4.8, 0.30),
    ]

    consistency = ConsistencyGainResult(
        segment_gains=cons_segments,
        total_gain_s=1.40,
        avg_lap_time_s=94.0,
        best_lap_time_s=92.5,
    )
    composite = CompositeGainResult(
        segment_gains=comp_segments,
        composite_time_s=92.0,
        best_lap_time_s=92.5,
        gain_s=0.50,
    )
    theoretical = TheoreticalBestResult(
        sector_size_m=100.0,
        n_sectors=38,
        theoretical_time_s=91.7,
        best_lap_time_s=92.5,
        gain_s=0.30,
    )

    return GainEstimate(
        consistency=consistency,
        composite=composite,
        theoretical=theoretical,
        clean_lap_numbers=[1, 2, 3],
        best_lap_number=1,
    )


class TestGainPerCornerChart:
    def test_returns_figure(self, sample_gains: GainEstimate) -> None:
        fig = gain_per_corner_chart(sample_gains.consistency, sample_gains.composite)
        assert isinstance(fig, go.Figure)

    def test_filters_straights(self, sample_gains: GainEstimate) -> None:
        fig = gain_per_corner_chart(sample_gains.consistency, sample_gains.composite)
        # Only corner names should appear, not straight S1
        for trace in fig.data:
            y_vals = list(trace.y)
            assert "S1" not in y_vals

    def test_has_two_trace_groups(self, sample_gains: GainEstimate) -> None:
        fig = gain_per_corner_chart(sample_gains.consistency, sample_gains.composite)
        assert len(fig.data) == 2  # consistency + composite bars

    def test_sorted_by_consistency_descending(self, sample_gains: GainEstimate) -> None:
        fig = gain_per_corner_chart(sample_gains.consistency, sample_gains.composite)
        cons_trace = fig.data[0]
        vals = list(cons_trace.x)
        assert vals == sorted(vals, reverse=True)

    def test_dark_theme(self, sample_gains: GainEstimate) -> None:
        fig = gain_per_corner_chart(sample_gains.consistency, sample_gains.composite)
        assert fig.layout.plot_bgcolor == "#0e1117"


@pytest.fixture
def sample_track_position() -> TrackPositionConsistency:
    n = 500
    return TrackPositionConsistency(
        distance_m=np.arange(n) * 0.7,
        speed_std_mph=np.random.default_rng(42).uniform(0.5, 3.0, n),
        speed_mean_mph=np.full(n, 60.0) + np.sin(np.arange(n) * 0.05) * 10,
        speed_median_mph=np.full(n, 59.0) + np.sin(np.arange(n) * 0.05) * 10,
        n_laps=5,
        lat=33.53 + np.sin(np.arange(n) * 0.01) * 0.001,
        lon=-86.62 + np.cos(np.arange(n) * 0.01) * 0.002,
    )


class TestTrackMedianSpeedMap:
    def test_returns_figure(
        self, sample_track_position: TrackPositionConsistency, sample_corners: list[Corner]
    ) -> None:
        fig = track_median_speed_map(sample_track_position, sample_corners)
        assert isinstance(fig, go.Figure)

    def test_no_corners(self, sample_track_position: TrackPositionConsistency) -> None:
        fig = track_median_speed_map(sample_track_position)
        assert isinstance(fig, go.Figure)

    def test_dark_theme(self, sample_track_position: TrackPositionConsistency) -> None:
        fig = track_median_speed_map(sample_track_position)
        assert fig.layout.plot_bgcolor == "#0e1117"

    def test_uses_rdylgn_colorscale(self, sample_track_position: TrackPositionConsistency) -> None:
        fig = track_median_speed_map(sample_track_position)
        # Plotly expands named colorscales to tuples; check first color matches RdYlGn
        cs = fig.data[0].marker.colorscale
        assert cs[0][0] == 0.0
        assert "165" in cs[0][1]  # rgb(165,0,38) is RdYlGn start


class TestBrakeThrottleChart:
    def test_returns_figure(self, sample_resampled_lap: pd.DataFrame) -> None:
        laps = {1: sample_resampled_lap}
        fig = brake_throttle_chart(laps, [1])
        assert isinstance(fig, go.Figure)

    def test_has_traces(self, sample_resampled_lap: pd.DataFrame) -> None:
        laps = {1: sample_resampled_lap, 2: sample_resampled_lap}
        fig = brake_throttle_chart(laps, [1, 2])
        assert len(fig.data) == 2

    def test_with_corners(self, sample_resampled_lap: pd.DataFrame) -> None:
        corners = [
            Corner(
                number=1,
                entry_distance_m=80.0,
                exit_distance_m=120.0,
                apex_distance_m=100.0,
                min_speed_mps=25.0,
                brake_point_m=70.0,
                peak_brake_g=-0.5,
                throttle_commit_m=110.0,
                apex_type="mid",
            )
        ]
        laps = {1: sample_resampled_lap}
        fig = brake_throttle_chart(laps, [1], corners)
        assert isinstance(fig, go.Figure)


class TestCornerDetailChart:
    def test_returns_figure(self, sample_resampled_lap: pd.DataFrame) -> None:
        corner = Corner(
            number=1,
            entry_distance_m=80.0,
            exit_distance_m=120.0,
            apex_distance_m=100.0,
            min_speed_mps=25.0,
            brake_point_m=70.0,
            peak_brake_g=-0.5,
            throttle_commit_m=110.0,
            apex_type="mid",
        )
        laps = {1: sample_resampled_lap}
        fig = corner_detail_chart(laps, [1], corner)
        assert isinstance(fig, go.Figure)

    def test_multiple_laps(self, sample_resampled_lap: pd.DataFrame) -> None:
        corner = Corner(
            number=1,
            entry_distance_m=80.0,
            exit_distance_m=120.0,
            apex_distance_m=100.0,
            min_speed_mps=25.0,
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="late",
        )
        laps = {1: sample_resampled_lap, 2: sample_resampled_lap}
        fig = corner_detail_chart(laps, [1, 2], corner)
        # 2 laps * 2 subplots = 4 traces
        assert len(fig.data) == 4

    def test_title_includes_corner(self, sample_resampled_lap: pd.DataFrame) -> None:
        corner = Corner(
            number=5,
            entry_distance_m=80.0,
            exit_distance_m=120.0,
            apex_distance_m=100.0,
            min_speed_mps=25.0,
            brake_point_m=None,
            peak_brake_g=None,
            throttle_commit_m=None,
            apex_type="mid",
        )
        laps = {1: sample_resampled_lap}
        fig = corner_detail_chart(laps, [1], corner)
        assert "T5" in fig.layout.title.text


class TestIdealLapOverlayChart:
    def test_returns_figure(self, sample_resampled_lap: pd.DataFrame) -> None:
        dist = sample_resampled_lap["lap_distance_m"].to_numpy()
        speed = sample_resampled_lap["speed_mps"].to_numpy()
        fig = ideal_lap_overlay_chart({1: sample_resampled_lap}, 1, dist, speed)
        assert isinstance(fig, go.Figure)

    def test_has_two_main_traces(self, sample_resampled_lap: pd.DataFrame) -> None:
        dist = sample_resampled_lap["lap_distance_m"].to_numpy()
        speed = sample_resampled_lap["speed_mps"].to_numpy()
        fig = ideal_lap_overlay_chart({1: sample_resampled_lap}, 1, dist, speed)
        # At least best lap + ideal lap traces
        assert len(fig.data) >= 2

    def test_title_mentions_ideal(self, sample_resampled_lap: pd.DataFrame) -> None:
        dist = sample_resampled_lap["lap_distance_m"].to_numpy()
        speed = sample_resampled_lap["speed_mps"].to_numpy()
        fig = ideal_lap_overlay_chart({1: sample_resampled_lap}, 1, dist, speed)
        assert "ideal" in fig.layout.title.text.lower()


class TestIdealLapDeltaChart:
    def test_returns_figure(self, sample_resampled_lap: pd.DataFrame) -> None:
        dist = sample_resampled_lap["lap_distance_m"].to_numpy()
        speed = sample_resampled_lap["speed_mps"].to_numpy()
        fig = ideal_lap_delta_chart(sample_resampled_lap, 1, dist, speed)
        assert isinstance(fig, go.Figure)

    def test_has_delta_traces(self, sample_resampled_lap: pd.DataFrame) -> None:
        dist = sample_resampled_lap["lap_distance_m"].to_numpy()
        speed = sample_resampled_lap["speed_mps"].to_numpy()
        fig = ideal_lap_delta_chart(sample_resampled_lap, 1, dist, speed)
        # positive fill + negative fill + main delta line = 3
        assert len(fig.data) >= 3

    def test_title_mentions_delta(self, sample_resampled_lap: pd.DataFrame) -> None:
        dist = sample_resampled_lap["lap_distance_m"].to_numpy()
        speed = sample_resampled_lap["speed_mps"].to_numpy()
        fig = ideal_lap_delta_chart(sample_resampled_lap, 1, dist, speed)
        assert "delta" in fig.layout.title.text.lower()

    def test_with_corners(self, sample_resampled_lap: pd.DataFrame) -> None:
        dist = sample_resampled_lap["lap_distance_m"].to_numpy()
        speed = sample_resampled_lap["speed_mps"].to_numpy()
        corners = [
            Corner(
                number=1,
                entry_distance_m=80.0,
                exit_distance_m=120.0,
                apex_distance_m=100.0,
                min_speed_mps=25.0,
                brake_point_m=70.0,
                peak_brake_g=-0.5,
                throttle_commit_m=110.0,
                apex_type="mid",
            )
        ]
        fig = ideal_lap_delta_chart(sample_resampled_lap, 1, dist, speed, corners)
        assert isinstance(fig, go.Figure)

    def test_identical_speed_zero_delta(self, sample_resampled_lap: pd.DataFrame) -> None:
        """When ideal speed equals best lap speed, delta should be near zero."""
        dist = sample_resampled_lap["lap_distance_m"].to_numpy()
        speed = sample_resampled_lap["speed_mps"].to_numpy()
        fig = ideal_lap_delta_chart(sample_resampled_lap, 1, dist, speed)
        # The delta-T trace (3rd trace) should be near zero
        delta_y = fig.data[2].y
        assert max(abs(v) for v in delta_y) < 0.1


class TestBrakeConsistencyChart:
    def test_returns_figure(self) -> None:
        corners = [
            Corner(
                number=1,
                entry_distance_m=80.0,
                exit_distance_m=120.0,
                apex_distance_m=100.0,
                min_speed_mps=25.0,
                brake_point_m=70.0,
                peak_brake_g=-0.5,
                throttle_commit_m=110.0,
                apex_type="mid",
            )
        ]
        all_laps = {
            1: [
                Corner(
                    number=1,
                    entry_distance_m=80.0,
                    exit_distance_m=120.0,
                    apex_distance_m=100.0,
                    min_speed_mps=25.0,
                    brake_point_m=70.0,
                    peak_brake_g=-0.5,
                    throttle_commit_m=110.0,
                    apex_type="mid",
                )
            ],
            2: [
                Corner(
                    number=1,
                    entry_distance_m=80.0,
                    exit_distance_m=120.0,
                    apex_distance_m=100.0,
                    min_speed_mps=26.0,
                    brake_point_m=72.0,
                    peak_brake_g=-0.4,
                    throttle_commit_m=112.0,
                    apex_type="mid",
                )
            ],
        }
        fig = brake_consistency_chart(all_laps, corners)
        assert isinstance(fig, go.Figure)

    def test_empty_corners(self) -> None:
        fig = brake_consistency_chart({}, [])
        assert isinstance(fig, go.Figure)


class TestTractionUtilizationChart:
    def test_returns_figure(self, sample_resampled_lap: pd.DataFrame) -> None:
        fig = traction_utilization_chart(sample_resampled_lap, 1)
        assert isinstance(fig, go.Figure)

    def test_title_includes_utilization(self, sample_resampled_lap: pd.DataFrame) -> None:
        fig = traction_utilization_chart(sample_resampled_lap, 1)
        assert "utilization" in fig.layout.title.text.lower()

    def test_has_circle_and_data_traces(self, sample_resampled_lap: pd.DataFrame) -> None:
        fig = traction_utilization_chart(sample_resampled_lap, 1)
        # Should have grip limit circle, 80% circle, and data points
        assert len(fig.data) >= 3

    def test_dark_theme(self, sample_resampled_lap: pd.DataFrame) -> None:
        fig = traction_utilization_chart(sample_resampled_lap, 1)
        assert fig.layout.plot_bgcolor == "#0e1117"

    def test_with_grip_estimate(self, sample_resampled_lap: pd.DataFrame) -> None:
        from cataclysm.grip import estimate_grip_limit

        grip = estimate_grip_limit({1: sample_resampled_lap}, [1])
        fig = traction_utilization_chart(sample_resampled_lap, 1, grip=grip)
        assert isinstance(fig, go.Figure)
        # With grip: hull + envelope + 80% threshold + data = 4 traces
        assert len(fig.data) >= 4
        assert "grip" in fig.layout.title.text.lower()

    def test_with_grip_estimate_title_format(self, sample_resampled_lap: pd.DataFrame) -> None:
        from cataclysm.grip import estimate_grip_limit

        grip = estimate_grip_limit({1: sample_resampled_lap}, [1])
        fig = traction_utilization_chart(sample_resampled_lap, 1, grip=grip)
        title = fig.layout.title.text
        assert "Grip:" in title
        assert "Utilization:" in title

    def test_without_grip_backward_compatible(self, sample_resampled_lap: pd.DataFrame) -> None:
        fig = traction_utilization_chart(sample_resampled_lap, 1, grip=None)
        assert isinstance(fig, go.Figure)
        # Without grip, title should NOT mention "Grip:"
        assert "Grip:" not in fig.layout.title.text


# ---------------------------------------------------------------------------
# Trend chart tests
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_trend(
    three_session_snapshots: list[SessionSnapshot],
) -> TrendAnalysis:
    """TrendAnalysis built from the three-session improvement fixture."""
    return compute_trend_analysis(three_session_snapshots)


class TestLapTimeTrendChart:
    def test_returns_figure(self, sample_trend: TrendAnalysis) -> None:
        fig = lap_time_trend_chart(sample_trend)
        assert isinstance(fig, go.Figure)

    def test_has_multiple_traces(self, sample_trend: TrendAnalysis) -> None:
        fig = lap_time_trend_chart(sample_trend)
        # At least: best, top3, avg, theoretical
        assert len(fig.data) >= 4

    def test_dark_theme(self, sample_trend: TrendAnalysis) -> None:
        fig = lap_time_trend_chart(sample_trend)
        assert fig.layout.plot_bgcolor == "#0e1117"

    def test_title_mentions_lap_time(self, sample_trend: TrendAnalysis) -> None:
        fig = lap_time_trend_chart(sample_trend)
        assert "lap" in fig.layout.title.text.lower() or "time" in fig.layout.title.text.lower()


class TestConsistencyTrendChart:
    def test_returns_figure(self, sample_trend: TrendAnalysis) -> None:
        fig = consistency_trend_chart(sample_trend)
        assert isinstance(fig, go.Figure)

    def test_has_background_shapes(self, sample_trend: TrendAnalysis) -> None:
        fig = consistency_trend_chart(sample_trend)
        # Should have at least 3 rectangular shapes for score bands
        shapes = fig.layout.shapes
        assert shapes is not None
        assert len(shapes) >= 3

    def test_dark_theme(self, sample_trend: TrendAnalysis) -> None:
        fig = consistency_trend_chart(sample_trend)
        assert fig.layout.plot_bgcolor == "#0e1117"


class TestCornerHeatmapChart:
    def test_returns_figure_min_speed(self, sample_trend: TrendAnalysis) -> None:
        fig = corner_heatmap_chart(sample_trend, metric="min_speed")
        assert isinstance(fig, go.Figure)

    def test_returns_figure_brake_std(self, sample_trend: TrendAnalysis) -> None:
        fig = corner_heatmap_chart(sample_trend, metric="brake_std")
        assert isinstance(fig, go.Figure)

    def test_returns_figure_consistency(self, sample_trend: TrendAnalysis) -> None:
        fig = corner_heatmap_chart(sample_trend, metric="consistency")
        assert isinstance(fig, go.Figure)

    def test_has_heatmap_trace(self, sample_trend: TrendAnalysis) -> None:
        fig = corner_heatmap_chart(sample_trend)
        assert any(isinstance(t, go.Heatmap) for t in fig.data)

    def test_dark_theme(self, sample_trend: TrendAnalysis) -> None:
        fig = corner_heatmap_chart(sample_trend)
        assert fig.layout.plot_bgcolor == "#0e1117"


class TestSessionComparisonBoxChart:
    def test_returns_figure(self, sample_trend: TrendAnalysis) -> None:
        fig = session_comparison_box_chart(sample_trend)
        assert isinstance(fig, go.Figure)

    def test_has_traces_per_session(self, sample_trend: TrendAnalysis) -> None:
        fig = session_comparison_box_chart(sample_trend)
        # At least one trace per session (box) + possibly diamond markers
        assert len(fig.data) >= sample_trend.n_sessions

    def test_dark_theme(self, sample_trend: TrendAnalysis) -> None:
        fig = session_comparison_box_chart(sample_trend)
        assert fig.layout.plot_bgcolor == "#0e1117"


class TestCornerTrendChart:
    def test_returns_figure(self, sample_trend: TrendAnalysis) -> None:
        fig = corner_trend_chart(sample_trend)
        assert isinstance(fig, go.Figure)

    def test_dark_theme(self, sample_trend: TrendAnalysis) -> None:
        fig = corner_trend_chart(sample_trend)
        assert fig.layout.plot_bgcolor == "#0e1117"

    def test_has_subplots(self, sample_trend: TrendAnalysis) -> None:
        fig = corner_trend_chart(sample_trend)
        # Should have traces for common corners
        n_corners = len(sample_trend.corner_min_speed_trends)
        if n_corners > 0:
            assert len(fig.data) >= n_corners

    def test_has_trendlines(self, sample_trend: TrendAnalysis) -> None:
        fig = corner_trend_chart(sample_trend)
        n_corners = len(sample_trend.corner_min_speed_trends)
        if n_corners > 0:
            # Each corner with ≥2 data points gets a data trace + a dashed trendline
            dashed = [t for t in fig.data if getattr(t.line, "dash", None) == "dash"]
            assert len(dashed) >= 1

    def test_trendline_slope_annotation(self, sample_trend: TrendAnalysis) -> None:
        fig = corner_trend_chart(sample_trend)
        annotations = [a for a in fig.layout.annotations if "mph/sess" in (a.text or "")]
        n_corners = len(sample_trend.corner_min_speed_trends)
        if n_corners > 0:
            assert len(annotations) >= 1


class TestMilestoneSummary:
    def test_returns_list(self, sample_trend: TrendAnalysis) -> None:
        result = milestone_summary(sample_trend)
        assert isinstance(result, list)

    def test_dict_keys(self, sample_trend: TrendAnalysis) -> None:
        result = milestone_summary(sample_trend)
        for m in result:
            assert "category" in m
            assert "description" in m
            assert "date" in m
            assert "icon" in m

    def test_icon_mapping(self, sample_trend: TrendAnalysis) -> None:
        result = milestone_summary(sample_trend)
        valid_icons = {"trophy", "chart", "stopwatch"}
        for m in result:
            assert m["icon"] in valid_icons

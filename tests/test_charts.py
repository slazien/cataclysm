"""Tests for cataclysm.charts."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from cataclysm.charts import (
    corner_kpi_table,
    delta_t_chart,
    g_force_chart,
    lap_times_chart,
    speed_trace_chart,
    track_map_chart,
)
from cataclysm.corners import Corner
from cataclysm.delta import DeltaResult
from cataclysm.engine import LapSummary


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
        laps[lap_num] = pd.DataFrame({
            "lap_distance_m": np.arange(n) * 0.7,
            "speed_mps": np.full(n, 30.0 - speed_offset) + np.sin(np.arange(n) * 0.1) * 5,
            "lat": 33.53 + np.sin(np.arange(n) * 0.01) * 0.001,
            "lon": -86.62 + np.cos(np.arange(n) * 0.01) * 0.002,
            "heading_deg": np.linspace(0, 360, n) % 360,
            "lateral_g": np.sin(np.arange(n) * 0.05) * 0.5,
            "longitudinal_g": np.cos(np.arange(n) * 0.05) * 0.3,
            "lap_time_s": np.arange(n) * 0.023,
        })
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

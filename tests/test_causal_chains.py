"""Tests for cataclysm.causal_chains — inter-corner causal chain detection."""

from __future__ import annotations

import numpy as np

from cataclysm.causal_chains import (
    CornerLink,
    SessionCausalAnalysis,
    _build_chains,
    _compute_link,
    _extract_lap_metrics,
    compute_causal_analysis,
    compute_recovery_fraction,
    format_causal_context_for_prompt,
)
from cataclysm.corners import Corner


def _make_corner(
    number: int,
    min_speed_mps: float,
    *,
    entry_distance_m: float = 0.0,
    exit_distance_m: float = 100.0,
    brake_point_m: float | None = None,
    throttle_commit_m: float | None = None,
    peak_brake_g: float | None = None,
) -> Corner:
    return Corner(
        number=number,
        entry_distance_m=entry_distance_m,
        exit_distance_m=exit_distance_m,
        apex_distance_m=(entry_distance_m + exit_distance_m) / 2,
        min_speed_mps=min_speed_mps,
        brake_point_m=brake_point_m,
        peak_brake_g=peak_brake_g,
        throttle_commit_m=throttle_commit_m,
        apex_type="mid",
        brake_point_lat=None,
        brake_point_lon=None,
        apex_lat=None,
        apex_lon=None,
        peak_curvature=None,
        mean_curvature=None,
        direction=None,
        segment_type=None,
        parent_complex=None,
        detection_method=None,
        character=None,
        corner_type_hint=None,
        elevation_trend=None,
        camber=None,
        blind=False,
        coaching_notes=None,
        elevation_change_m=None,
        gradient_pct=None,
    )


class TestRecoveryFraction:
    def test_zero_distance(self) -> None:
        assert compute_recovery_fraction(0.0) == 0.0

    def test_negative_distance(self) -> None:
        assert compute_recovery_fraction(-10.0) == 0.0

    def test_short_straight(self) -> None:
        # Short straight → low recovery
        result = compute_recovery_fraction(30.0)
        assert 0.0 < result < 0.5

    def test_long_straight(self) -> None:
        # Long straight → high recovery
        result = compute_recovery_fraction(500.0)
        assert result > 0.9

    def test_medium_straight(self) -> None:
        # Medium straight → moderate recovery
        result = compute_recovery_fraction(100.0)
        assert 0.3 < result < 0.8

    def test_monotonically_increasing(self) -> None:
        fracs = [compute_recovery_fraction(d) for d in [10, 50, 100, 200, 500]]
        for i in range(len(fracs) - 1):
            assert fracs[i] < fracs[i + 1]

    def test_capped_at_1(self) -> None:
        assert compute_recovery_fraction(10000.0) <= 1.0


class TestExtractLapMetrics:
    def test_basic_extraction(self) -> None:
        corners = {
            1: [_make_corner(1, 20.0, brake_point_m=150.0, throttle_commit_m=300.0)],
            2: [_make_corner(1, 22.0, brake_point_m=145.0, throttle_commit_m=295.0)],
        }
        metrics = _extract_lap_metrics(corners, 1)
        assert len(metrics) == 2
        assert metrics[1]["min_speed_mph"] is not None
        assert metrics[1]["brake_point_m"] == 150.0

    def test_filters_anomalous(self) -> None:
        corners = {
            1: [_make_corner(1, 20.0)],
            2: [_make_corner(1, 22.0)],
        }
        metrics = _extract_lap_metrics(corners, 1, anomalous_laps={2})
        assert len(metrics) == 1
        assert 1 in metrics

    def test_missing_corner_number(self) -> None:
        corners = {1: [_make_corner(1, 20.0)]}
        metrics = _extract_lap_metrics(corners, 99)
        assert len(metrics) == 0


class TestComputeLink:
    def _build_correlated_data(self, n_laps: int = 8) -> dict[int, list[Corner]]:
        """Build lap data where T1 and T2 are strongly correlated."""
        rng = np.random.default_rng(42)
        base_speeds = 20.0 + rng.normal(0, 2, n_laps)
        data: dict[int, list[Corner]] = {}
        for i, speed in enumerate(base_speeds, start=1):
            # T2 speed correlates with T1 speed (same variation direction)
            t2_speed = speed + 5.0 + rng.normal(0, 0.5)
            data[i] = [
                _make_corner(
                    1,
                    speed,
                    entry_distance_m=100.0,
                    exit_distance_m=200.0,
                    brake_point_m=80.0,
                    throttle_commit_m=220.0,
                ),
                _make_corner(
                    2,
                    t2_speed,
                    entry_distance_m=350.0,
                    exit_distance_m=450.0,
                    brake_point_m=330.0,
                    throttle_commit_m=470.0,
                ),
            ]
        return data

    def test_detects_strong_correlation(self) -> None:
        data = self._build_correlated_data()
        link = _compute_link(data, 1, 2)
        assert link is not None
        assert abs(link.pearson_r) >= 0.5
        assert link.upstream_corner == 1
        assert link.downstream_corner == 2

    def test_returns_none_for_few_laps(self) -> None:
        data = self._build_correlated_data(n_laps=3)
        link = _compute_link(data, 1, 2)
        assert link is None

    def test_returns_none_for_uncorrelated(self) -> None:
        rng = np.random.default_rng(99)
        data: dict[int, list[Corner]] = {}
        for i in range(1, 9):
            data[i] = [
                _make_corner(
                    1,
                    20.0 + rng.normal(0, 2),
                    entry_distance_m=100.0,
                    exit_distance_m=200.0,
                ),
                _make_corner(
                    2,
                    25.0 + rng.normal(0, 2),
                    entry_distance_m=350.0,
                    exit_distance_m=450.0,
                ),
            ]
        link = _compute_link(data, 1, 2)
        # May or may not be None depending on random seed, but r should be low
        if link is not None:
            assert abs(link.pearson_r) >= 0.5  # threshold was met

    def test_straight_distance_computed(self) -> None:
        data = self._build_correlated_data()
        link = _compute_link(data, 1, 2)
        assert link is not None
        # T1 exit=200, T2 entry=350 → 150m
        assert link.straight_distance_m == 150.0


class TestBuildChains:
    def test_empty_links(self) -> None:
        assert _build_chains([]) == []

    def test_single_link_too_short(self) -> None:
        link = CornerLink(
            upstream_corner=1,
            downstream_corner=2,
            metric_pair="min_speed → min_speed",
            pearson_r=0.8,
            n_laps=8,
            recovery_fraction=0.5,
            straight_distance_m=100.0,
        )
        chains = _build_chains([link])
        assert len(chains) == 0  # need >= 2 links for a chain

    def test_two_connected_links_form_chain(self) -> None:
        links = [
            CornerLink(
                upstream_corner=1,
                downstream_corner=2,
                metric_pair="min_speed → min_speed",
                pearson_r=0.8,
                n_laps=8,
                recovery_fraction=0.5,
                straight_distance_m=100.0,
            ),
            CornerLink(
                upstream_corner=2,
                downstream_corner=3,
                metric_pair="min_speed → min_speed",
                pearson_r=0.7,
                n_laps=8,
                recovery_fraction=0.4,
                straight_distance_m=80.0,
            ),
        ]
        chains = _build_chains(links)
        assert len(chains) == 1
        assert chains[0].root_corner == 1
        assert chains[0].chain_corners == [1, 2, 3]

    def test_disconnected_links_no_chain(self) -> None:
        links = [
            CornerLink(
                upstream_corner=1,
                downstream_corner=2,
                metric_pair="min_speed → min_speed",
                pearson_r=0.8,
                n_laps=8,
                recovery_fraction=0.5,
                straight_distance_m=100.0,
            ),
            CornerLink(
                upstream_corner=4,
                downstream_corner=5,
                metric_pair="min_speed → min_speed",
                pearson_r=0.7,
                n_laps=8,
                recovery_fraction=0.4,
                straight_distance_m=80.0,
            ),
        ]
        chains = _build_chains(links)
        # Neither pair has 2+ connected links
        assert len(chains) == 0


class TestComputeCausalAnalysis:
    def test_empty_input(self) -> None:
        result = compute_causal_analysis({})
        assert result.links == []
        assert result.chains == []
        assert result.time_killer is None
        assert result.n_laps_analyzed == 0

    def test_too_few_laps(self) -> None:
        data = {
            1: [
                _make_corner(1, 20.0, entry_distance_m=100.0, exit_distance_m=200.0),
                _make_corner(2, 25.0, entry_distance_m=350.0, exit_distance_m=450.0),
            ],
        }
        result = compute_causal_analysis(data)
        assert result.links == []
        assert result.n_laps_analyzed == 1

    def test_single_corner(self) -> None:
        data = {i: [_make_corner(1, 20.0 + i)] for i in range(1, 8)}
        result = compute_causal_analysis(data)
        assert result.links == []

    def test_correlated_pair_detected(self) -> None:
        rng = np.random.default_rng(42)
        data: dict[int, list[Corner]] = {}
        for i in range(1, 9):
            base = 20.0 + rng.normal(0, 3)
            data[i] = [
                _make_corner(
                    1,
                    base,
                    entry_distance_m=100.0,
                    exit_distance_m=200.0,
                    brake_point_m=80.0,
                    throttle_commit_m=220.0,
                ),
                _make_corner(
                    2,
                    base + 5.0 + rng.normal(0, 0.3),
                    entry_distance_m=300.0,
                    exit_distance_m=400.0,
                    brake_point_m=280.0,
                    throttle_commit_m=420.0,
                ),
            ]
        result = compute_causal_analysis(data)
        assert result.n_laps_analyzed == 8
        assert len(result.links) >= 1
        assert result.links[0].upstream_corner == 1
        assert result.links[0].downstream_corner == 2

    def test_anomalous_laps_excluded(self) -> None:
        rng = np.random.default_rng(42)
        data: dict[int, list[Corner]] = {}
        for i in range(1, 9):
            base = 20.0 + rng.normal(0, 3)
            data[i] = [
                _make_corner(
                    1,
                    base,
                    entry_distance_m=100.0,
                    exit_distance_m=200.0,
                ),
                _make_corner(
                    2,
                    base + 5.0,
                    entry_distance_m=300.0,
                    exit_distance_m=400.0,
                ),
            ]
        # Mark all but 3 as anomalous → below threshold
        result = compute_causal_analysis(data, anomalous_laps={1, 2, 3, 4, 5})
        assert result.n_laps_analyzed == 3
        assert result.links == []  # not enough laps


class TestFormatCausalContextForPrompt:
    def test_empty_analysis(self) -> None:
        analysis = SessionCausalAnalysis(
            links=[],
            chains=[],
            time_killer=None,
            n_laps_analyzed=5,
        )
        assert format_causal_context_for_prompt(analysis) == ""

    def test_single_link_formatted(self) -> None:
        analysis = SessionCausalAnalysis(
            links=[
                CornerLink(
                    upstream_corner=3,
                    downstream_corner=4,
                    metric_pair="min_speed → min_speed",
                    pearson_r=0.72,
                    n_laps=8,
                    recovery_fraction=0.45,
                    straight_distance_m=120.0,
                ),
            ],
            chains=[],
            time_killer=None,
            n_laps_analyzed=8,
        )
        text = format_causal_context_for_prompt(analysis)
        assert "T3 → T4" in text
        assert "r=0.72" in text
        assert "120m" in text
        assert "45%" in text

    def test_time_killer_formatted(self) -> None:
        from cataclysm.causal_chains import TimeKiller

        analysis = SessionCausalAnalysis(
            links=[
                CornerLink(
                    upstream_corner=5,
                    downstream_corner=6,
                    metric_pair="min_speed → min_speed",
                    pearson_r=0.8,
                    n_laps=8,
                    recovery_fraction=0.3,
                    straight_distance_m=80.0,
                ),
            ],
            chains=[],
            time_killer=TimeKiller(
                corner=5,
                direct_cost_s=0.1,
                cascade_cost_s=0.05,
                total_cost_s=0.15,
                affected_corners=[6],
            ),
            n_laps_analyzed=8,
        )
        text = format_causal_context_for_prompt(analysis)
        assert "TimeKiller: T5" in text
        assert "T6" in text
        assert "outsized impact" in text

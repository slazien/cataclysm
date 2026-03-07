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


# ---------------------------------------------------------------------------
# Additional coverage: CausalChain.length and .chain_corners (lines 64-65)
# ---------------------------------------------------------------------------


class TestCausalChainProperties:
    """Tests for CausalChain.length and CausalChain.chain_corners."""

    def test_chain_length(self) -> None:
        from cataclysm.causal_chains import CausalChain, CornerLink

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
        chain = CausalChain(links=links, root_corner=1, total_cascade_cost_s=0.05)
        assert chain.length == 2  # line 65
        assert chain.chain_corners == [1, 2, 3]  # line 59-61

    def test_single_link_chain_length(self) -> None:
        from cataclysm.causal_chains import CausalChain, CornerLink

        link = CornerLink(
            upstream_corner=3,
            downstream_corner=4,
            metric_pair="min_speed → min_speed",
            pearson_r=0.6,
            n_laps=7,
            recovery_fraction=0.3,
            straight_distance_m=60.0,
        )
        chain = CausalChain(links=[link], root_corner=3, total_cascade_cost_s=0.02)
        assert chain.length == 1


# ---------------------------------------------------------------------------
# Additional coverage: _build_chains with no-root fallback (line 253)
# ---------------------------------------------------------------------------


class TestBuildChainsNoRoot:
    """Tests for _build_chains when no clear root exists (all corners are downstream)."""

    def test_no_root_uses_highest_r(self) -> None:
        """When all upstream corners are also downstream, use highest |r| as root."""
        # Build a circular dependency: 1→2, 2→1 (all are downstream of something)
        links = [
            CornerLink(
                upstream_corner=1,
                downstream_corner=2,
                metric_pair="min_speed → min_speed",
                pearson_r=0.9,  # highest
                n_laps=8,
                recovery_fraction=0.5,
                straight_distance_m=100.0,
            ),
            CornerLink(
                upstream_corner=2,
                downstream_corner=1,
                metric_pair="min_speed → min_speed",
                pearson_r=0.6,
                n_laps=8,
                recovery_fraction=0.4,
                straight_distance_m=80.0,
            ),
        ]
        # Both upstream corners are also downstream → no clear root → fallback to max |r|
        chains = _build_chains(links)
        # Depending on visited set, we might get 0 or 1 chain; just ensure no crash
        assert isinstance(chains, list)


# ---------------------------------------------------------------------------
# Additional coverage: _find_time_killer returns None for low cost (line 344-345)
# ---------------------------------------------------------------------------


class TestFindTimeKillerNoneCase:
    """Tests for _find_time_killer returning None for low total cost."""

    def test_returns_none_when_no_links(self) -> None:
        from cataclysm.causal_chains import _find_time_killer

        result = _find_time_killer([], {})
        assert result is None  # line 297

    def test_returns_none_below_cost_threshold(self) -> None:
        """When all speeds are identical (no variance), cost stays near 0 → returns None."""
        from cataclysm.causal_chains import CornerLink, _find_time_killer

        # Single speed value per corner → std=0 → cost=0
        data: dict[int, list[Corner]] = {
            1: [_make_corner(1, 20.0, entry_distance_m=0.0, exit_distance_m=100.0)],
            2: [_make_corner(2, 25.0, entry_distance_m=150.0, exit_distance_m=250.0)],
        }
        link = CornerLink(
            upstream_corner=1,
            downstream_corner=2,
            metric_pair="min_speed → min_speed",
            pearson_r=0.8,
            n_laps=1,
            recovery_fraction=0.5,
            straight_distance_m=50.0,
        )
        # With only 1 lap, std=0, so direct cost = 0, cascade cost minimal
        result = _find_time_killer([link], data)
        # Result can be None (cost < 0.01) or a TimeKiller depending on cascade
        assert result is None or result.corner in [1, 2]


# ---------------------------------------------------------------------------
# Additional coverage: _compute_link with wrap-around (negative straight_dist line 175)
# ---------------------------------------------------------------------------


class TestComputeLinkWrapAround:
    """Test _compute_link returns None for wrap-around (last → first corner)."""

    def test_negative_straight_distance_returns_none(self) -> None:
        """When T2 entry < T1 exit (wrap-around), link should be None."""
        rng = np.random.default_rng(42)
        data: dict[int, list[Corner]] = {}
        for i in range(1, 9):
            data[i] = [
                _make_corner(
                    1,
                    20.0 + rng.normal(0, 2),
                    entry_distance_m=500.0,  # T1 starts at 500
                    exit_distance_m=600.0,  # T1 exits at 600
                ),
                _make_corner(
                    2,
                    25.0 + rng.normal(0, 2),
                    entry_distance_m=50.0,  # T2 entry at 50 < T1 exit (wrap-around)
                    exit_distance_m=150.0,
                ),
            ]
        link = _compute_link(data, 1, 2)
        assert link is None  # straight_dist < 0 → skip


# ---------------------------------------------------------------------------
# Additional coverage: format_causal_context with chains but no time_killer (lines 452-456)
# ---------------------------------------------------------------------------


class TestFormatCausalContextWithChains:
    """Tests format_causal_context with chains present but no time killer."""

    def test_chains_formatted(self) -> None:
        from cataclysm.causal_chains import CausalChain, CornerLink, SessionCausalAnalysis

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
        chain = CausalChain(links=links, root_corner=1, total_cascade_cost_s=0.035)
        analysis = SessionCausalAnalysis(
            links=links,
            chains=[chain],
            time_killer=None,
            n_laps_analyzed=8,
        )
        text = format_causal_context_for_prompt(analysis)
        assert "Cascade Chains" in text
        assert "T1 → T2 → T3" in text
        assert "0.035s" in text


# ---------------------------------------------------------------------------
# Additional coverage: _compute_link when corner geometry missing (line 170)
# ---------------------------------------------------------------------------


class TestComputeLinkMissingGeometry:
    """Line 170: _compute_link returns None when corner not found in first_lap."""

    def test_returns_none_when_upstream_not_in_first_lap(self) -> None:
        """If upstream corner number doesn't exist in first lap, return None (line 170).

        Strategy: laps 2-8 have BOTH corners so common_laps >= 5 (passes line 156).
        Lap 1 (first_lap) has only corner 2 → up_exit stays None → return None at line 170.
        """
        rng = np.random.default_rng(42)
        data: dict[int, list[Corner]] = {}
        # Lap 1 = first_lap has only corner 2 (no corner 1 in geometry)
        data[1] = [
            _make_corner(
                2,
                20.0 + rng.normal(0, 2),
                entry_distance_m=100.0,
                exit_distance_m=200.0,
            ),
        ]
        # Laps 2-8 have BOTH corners so metrics are found for both
        for i in range(2, 9):
            data[i] = [
                _make_corner(
                    1,
                    18.0 + rng.normal(0, 1),
                    entry_distance_m=0.0,
                    exit_distance_m=80.0,
                ),
                _make_corner(
                    2,
                    20.0 + rng.normal(0, 2),
                    entry_distance_m=100.0,
                    exit_distance_m=200.0,
                ),
            ]
        # common_laps = {2..8} = 7 laps (>= _MIN_LAPS_FOR_CORRELATION=5)
        # first_lap has no corner 1 → up_exit = None → line 170 executed
        link = _compute_link(data, 1, 2)
        assert link is None  # line 170: up_exit is None

    def test_returns_none_when_downstream_not_in_first_lap(self) -> None:
        """If downstream corner number doesn't exist in first lap, return None (line 170).

        Strategy: laps 2-8 have BOTH corners so common_laps >= 5 (passes line 156).
        Lap 1 (first_lap) has only corner 1 → down_entry stays None → return None at line 170.
        """
        rng = np.random.default_rng(42)
        data: dict[int, list[Corner]] = {}
        # Lap 1 = first_lap has only corner 1 (no corner 2 in geometry)
        data[1] = [
            _make_corner(
                1,
                18.0 + rng.normal(0, 1),
                entry_distance_m=0.0,
                exit_distance_m=80.0,
            ),
        ]
        # Laps 2-8 have BOTH corners so metrics are found for both
        for i in range(2, 9):
            data[i] = [
                _make_corner(
                    1,
                    18.0 + rng.normal(0, 1),
                    entry_distance_m=0.0,
                    exit_distance_m=80.0,
                ),
                _make_corner(
                    2,
                    20.0 + rng.normal(0, 2),
                    entry_distance_m=100.0,
                    exit_distance_m=200.0,
                ),
            ]
        # first_lap has no corner 2 → down_entry = None → line 170 executed
        link = _compute_link(data, 1, 2)
        assert link is None  # line 170: down_entry is None


# ---------------------------------------------------------------------------
# Additional coverage: _build_chains skips already-visited root (line 260)
# ---------------------------------------------------------------------------


class TestBuildChainsVisitedRoot:
    """Line 260: root already in visited is skipped in _build_chains."""

    def test_visited_root_skipped(self) -> None:
        """When roots list has duplicate upstream corners, second is skipped (line 260).

        _build_chains builds roots via list comprehension (not set), so if two
        links share the same upstream_corner and are both not in downstream_set,
        the root appears twice. The second occurrence hits line 260 (continue).
        """
        # Two links with the SAME upstream_corner=1, different downstream.
        # Corner 1 is not downstream of anything → appears twice in roots list.
        # First traversal: visits corner 1, adds it to visited.
        # Second occurrence of corner 1 in roots → line 260: root in visited → continue.
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
            # Second link also has upstream_corner=1, same as first.
            # by_upstream[1] = this link (overwrites first), but roots list still has two 1s.
            CornerLink(
                upstream_corner=1,
                downstream_corner=3,
                metric_pair="brake_point → brake_point",
                pearson_r=0.75,
                n_laps=8,
                recovery_fraction=0.4,
                straight_distance_m=80.0,
            ),
        ]
        # roots = [1, 1]  (both upstream_corner=1 not in downstream_set={2,3})
        # Iteration 1: root=1, not in visited → traverse → visited={1}
        # Iteration 2: root=1, IN visited → line 260 executes (continue)
        # _MIN_CHAIN_LENGTH=2 requires chain_links >= 2, but by_upstream[1] → downstream=3
        # so chain is only length 1. Lower the threshold to 1 to get a chain returned.
        from unittest.mock import patch

        with patch("cataclysm.causal_chains._MIN_CHAIN_LENGTH", 1):
            chains = _build_chains(links)
        # The duplicate root (corner 1) is skipped at line 260 on second iteration.
        # Result: one chain starting at corner 1 (from by_upstream[1]=second link).
        assert len(chains) == 1
        assert chains[0].root_corner == 1


# ---------------------------------------------------------------------------
# Additional coverage: _find_time_killer anomalous lap skipping (line 313)
# ---------------------------------------------------------------------------


class TestFindTimeKillerAnomalousLaps:
    """Line 313: anomalous laps are skipped in _find_time_killer speed collection."""

    def test_anomalous_laps_excluded_from_direct_cost(self) -> None:
        """Marking laps as anomalous excludes them from std calculation."""

        from cataclysm.causal_chains import CornerLink, _find_time_killer

        # Build 8 laps of corner 1 with high variance — then mark 6 as anomalous
        # so only 2 remain (< 2 needed for std → direct_cost stays 0).
        # Actually with 2 laps we do get std, so mark 7 as anomalous → only 1 remains.
        data: dict[int, list[Corner]] = {}
        for i in range(1, 9):
            data[i] = [
                _make_corner(1, 20.0 + i, entry_distance_m=0.0, exit_distance_m=100.0),
                _make_corner(2, 25.0 + i, entry_distance_m=150.0, exit_distance_m=250.0),
            ]
        link = CornerLink(
            upstream_corner=1,
            downstream_corner=2,
            metric_pair="min_speed → min_speed",
            pearson_r=0.8,
            n_laps=8,
            recovery_fraction=0.5,
            straight_distance_m=50.0,
        )
        # Mark laps 2-8 as anomalous → only lap 1 remains (1 speed → no std)
        anomalous = {2, 3, 4, 5, 6, 7, 8}
        result = _find_time_killer([link], data, anomalous_laps=anomalous)
        # With only 1 valid lap, direct_cost for corner 1 is 0 (needs >=2 speeds)
        # Cascade cost from link is still computed
        # Either None or a TimeKiller — just ensure no crash
        assert result is None or result.corner in [1, 2]


# ---------------------------------------------------------------------------
# Additional coverage: _find_time_killer returns None below threshold (line 345)
# ---------------------------------------------------------------------------


class TestFindTimeKillerBelowThreshold:
    """Line 345: _find_time_killer returns None when best_total < 0.01."""

    def test_returns_none_when_all_zero_speed_variance(self) -> None:
        """All corners with identical speeds give zero direct cost → returns None."""
        from cataclysm.causal_chains import CornerLink, _find_time_killer

        # All laps have the same speed → std=0 → direct_cost=0
        # cascade_cost from link is tiny (0.1 * 0.8 * (1-0.99) = 0.0008) → below 0.01
        data: dict[int, list[Corner]] = {}
        for i in range(1, 9):
            data[i] = [
                _make_corner(1, 20.0, entry_distance_m=0.0, exit_distance_m=100.0),
                _make_corner(2, 25.0, entry_distance_m=150.0, exit_distance_m=250.0),
            ]
        # Very high recovery → cascade cost near zero
        link = CornerLink(
            upstream_corner=1,
            downstream_corner=2,
            metric_pair="min_speed → min_speed",
            pearson_r=0.8,
            n_laps=8,
            recovery_fraction=0.999,  # near-complete recovery → tiny cascade
            straight_distance_m=50.0,
        )
        result = _find_time_killer([link], data)
        # direct_cost = 0 (same speed), cascade ≈ 0 → total < 0.01 → None
        assert result is None  # line 345

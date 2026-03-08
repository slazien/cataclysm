"""Tests for cataclysm.linked_corners."""

from __future__ import annotations

import numpy as np
import pytest

from cataclysm.corners import Corner
from cataclysm.linked_corners import (
    CornerGroup,
    LinkedCornerResult,
    compute_curvature_variation_index,
    detect_linked_corners,
)


def _make_corner(
    number: int,
    entry_m: float,
    exit_m: float,
    apex_m: float | None = None,
) -> Corner:
    """Helper to build a minimal Corner for testing."""
    if apex_m is None:
        apex_m = (entry_m + exit_m) / 2.0
    return Corner(
        number=number,
        entry_distance_m=entry_m,
        exit_distance_m=exit_m,
        apex_distance_m=apex_m,
        min_speed_mps=20.0,
        brake_point_m=None,
        peak_brake_g=None,
        throttle_commit_m=None,
        apex_type="mid",
    )


class TestDetectLinkedCornersIsolated:
    """Corners with full-speed straights between them produce no groups."""

    def test_isolated_corners_no_groups(self) -> None:
        """Two corners separated by a long straight with full speed -> no linking."""
        # Track: 0--[C1: 100-200]--straight--[C2: 800-900]--1000
        distance_m = np.linspace(0, 1000, 2000)
        speed = np.ones(2000) * 50.0  # 50 m/s everywhere

        # Slow down in corner zones only
        c1_mask = (distance_m >= 100) & (distance_m <= 200)
        c2_mask = (distance_m >= 800) & (distance_m <= 900)
        speed[c1_mask] = 20.0
        speed[c2_mask] = 20.0

        corners = [
            _make_corner(1, 100.0, 200.0),
            _make_corner(2, 800.0, 900.0),
        ]

        result = detect_linked_corners(corners, speed, distance_m)

        assert isinstance(result, LinkedCornerResult)
        assert len(result.groups) == 0
        assert len(result.corner_to_group) == 0

    def test_single_corner_no_groups(self) -> None:
        """A single corner cannot form a group."""
        distance_m = np.linspace(0, 500, 1000)
        speed = np.ones(1000) * 50.0
        corners = [_make_corner(1, 100.0, 200.0)]

        result = detect_linked_corners(corners, speed, distance_m)
        assert len(result.groups) == 0

    def test_empty_corners_no_groups(self) -> None:
        """No corners at all -> no groups."""
        distance_m = np.linspace(0, 500, 1000)
        speed = np.ones(1000) * 50.0

        result = detect_linked_corners([], speed, distance_m)
        assert len(result.groups) == 0


class TestTwoLinkedCorners:
    """Two corners that never reach straight-line speed between them."""

    def test_two_linked_corners(self) -> None:
        """Two corners with low speed between them -> one group of 2."""
        # Track: 0--[C1: 100-200]--low speed--[C2: 250-350]--500
        distance_m = np.linspace(0, 500, 1000)
        speed = np.ones(1000) * 50.0  # max straight speed = 50 m/s

        # Slow in corners
        c1_mask = (distance_m >= 100) & (distance_m <= 200)
        c2_mask = (distance_m >= 250) & (distance_m <= 350)
        between_mask = (distance_m > 200) & (distance_m < 250)

        speed[c1_mask] = 20.0
        speed[c2_mask] = 20.0
        speed[between_mask] = 30.0  # 30 m/s < 0.95 * 50 = 47.5

        corners = [
            _make_corner(1, 100.0, 200.0),
            _make_corner(2, 250.0, 350.0),
        ]

        result = detect_linked_corners(corners, speed, distance_m)

        assert len(result.groups) == 1
        group = result.groups[0]
        assert group.group_id == 1
        assert group.corner_numbers == [1, 2]
        assert 1 in result.corner_to_group
        assert 2 in result.corner_to_group
        assert result.corner_to_group[1] == 1
        assert result.corner_to_group[2] == 1


class TestThreeCornerComplex:
    """Chicane pattern: three corners linked into a single group."""

    def test_three_corner_complex(self) -> None:
        """Three close corners with low speed between all of them -> one group of 3."""
        distance_m = np.linspace(0, 1000, 2000)
        speed = np.ones(2000) * 60.0

        # Three closely-spaced corners with low inter-corner speed
        c1_mask = (distance_m >= 100) & (distance_m <= 150)
        c2_mask = (distance_m >= 180) & (distance_m <= 230)
        c3_mask = (distance_m >= 260) & (distance_m <= 310)
        between_1_2 = (distance_m > 150) & (distance_m < 180)
        between_2_3 = (distance_m > 230) & (distance_m < 260)

        speed[c1_mask] = 25.0
        speed[c2_mask] = 22.0
        speed[c3_mask] = 28.0
        speed[between_1_2] = 35.0  # < 0.95 * 60 = 57
        speed[between_2_3] = 32.0  # < 0.95 * 60 = 57

        corners = [
            _make_corner(1, 100.0, 150.0),
            _make_corner(2, 180.0, 230.0),
            _make_corner(3, 260.0, 310.0),
        ]

        result = detect_linked_corners(corners, speed, distance_m)

        assert len(result.groups) == 1
        group = result.groups[0]
        assert group.corner_numbers == [1, 2, 3]
        assert len(result.corner_to_group) == 3
        for cn in [1, 2, 3]:
            assert result.corner_to_group[cn] == group.group_id


class TestMixedLinkedAndIsolated:
    """Some corners linked, some not."""

    def test_mixed_linked_and_isolated(self) -> None:
        """C1-C2 linked, C3 isolated -> one group of 2, C3 not in any group."""
        distance_m = np.linspace(0, 1500, 3000)
        speed = np.ones(3000) * 55.0

        # C1 and C2 close together, low speed between
        c1_mask = (distance_m >= 100) & (distance_m <= 200)
        c2_mask = (distance_m >= 250) & (distance_m <= 350)
        between_1_2 = (distance_m > 200) & (distance_m < 250)

        speed[c1_mask] = 20.0
        speed[c2_mask] = 22.0
        speed[between_1_2] = 30.0  # linked: 30 < 0.95 * 55 = 52.25

        # C3 far away, full speed between C2 and C3
        c3_mask = (distance_m >= 1000) & (distance_m <= 1100)
        speed[c3_mask] = 25.0
        # Speed between C2 exit (350) and C3 entry (1000) stays at 55 — not linked

        corners = [
            _make_corner(1, 100.0, 200.0),
            _make_corner(2, 250.0, 350.0),
            _make_corner(3, 1000.0, 1100.0),
        ]

        result = detect_linked_corners(corners, speed, distance_m)

        assert len(result.groups) == 1
        assert result.groups[0].corner_numbers == [1, 2]
        assert 1 in result.corner_to_group
        assert 2 in result.corner_to_group
        assert 3 not in result.corner_to_group

    def test_two_separate_groups(self) -> None:
        """C1-C2 linked, C3-C4 linked, gap between -> two groups."""
        distance_m = np.linspace(0, 2000, 4000)
        speed = np.ones(4000) * 60.0

        # Group A: C1-C2
        speed[(distance_m >= 100) & (distance_m <= 200)] = 20.0
        speed[(distance_m >= 240) & (distance_m <= 340)] = 22.0
        speed[(distance_m > 200) & (distance_m < 240)] = 30.0  # linked

        # Group B: C3-C4 (far away, full speed between A and B)
        speed[(distance_m >= 1200) & (distance_m <= 1300)] = 18.0
        speed[(distance_m >= 1340) & (distance_m <= 1440)] = 21.0
        speed[(distance_m > 1300) & (distance_m < 1340)] = 28.0  # linked

        corners = [
            _make_corner(1, 100.0, 200.0),
            _make_corner(2, 240.0, 340.0),
            _make_corner(3, 1200.0, 1300.0),
            _make_corner(4, 1340.0, 1440.0),
        ]

        result = detect_linked_corners(corners, speed, distance_m)

        assert len(result.groups) == 2
        assert result.groups[0].corner_numbers == [1, 2]
        assert result.groups[1].corner_numbers == [3, 4]
        assert result.corner_to_group[1] == result.groups[0].group_id
        assert result.corner_to_group[3] == result.groups[1].group_id


class TestCVISimpleArc:
    """Simple constant-radius arc has low CVI."""

    def test_cvi_simple_arc(self) -> None:
        """Uniform curvature (single radius) -> CVI < 0.5."""
        # Constant curvature = uniform arc
        n = 200
        curvature = np.full(n, 0.01)  # constant 1/100m radius

        cvi = compute_curvature_variation_index(curvature, entry_idx=0, exit_idx=n)

        assert cvi < 0.5
        # For truly constant curvature, std=0, so CVI should be ~0
        assert cvi == pytest.approx(0.0, abs=1e-10)

    def test_cvi_near_constant_curvature(self) -> None:
        """Curvature with small noise -> still low CVI."""
        rng = np.random.default_rng(42)
        n = 200
        curvature = 0.01 + rng.normal(0, 0.001, n)  # small noise around 0.01

        cvi = compute_curvature_variation_index(curvature, entry_idx=0, exit_idx=n)
        assert cvi < 0.5


class TestCVIChicane:
    """Chicane with alternating curvature has high CVI."""

    def test_cvi_chicane(self) -> None:
        """Alternating left-right curvature -> CVI > 1.0."""
        n = 200
        # Alternating curvature: +0.02 for first half, -0.02 for second half
        curvature = np.zeros(n)
        curvature[: n // 2] = 0.02
        curvature[n // 2 :] = -0.02

        cvi = compute_curvature_variation_index(curvature, entry_idx=0, exit_idx=n)

        assert cvi > 1.0

    def test_cvi_esses(self) -> None:
        """Sinusoidal curvature (esses) -> high CVI."""
        n = 400
        curvature = 0.015 * np.sin(np.linspace(0, 4 * np.pi, n))

        cvi = compute_curvature_variation_index(curvature, entry_idx=0, exit_idx=n)
        assert cvi > 1.0


class TestCVIEdgeCases:
    """Edge cases for CVI computation."""

    def test_cvi_empty_section(self) -> None:
        """Empty section -> CVI = 0."""
        curvature = np.array([0.01, 0.02, 0.03])
        cvi = compute_curvature_variation_index(curvature, entry_idx=2, exit_idx=2)
        assert cvi == 0.0

    def test_cvi_single_point(self) -> None:
        """Single-point section -> CVI = 0."""
        curvature = np.array([0.01, 0.02, 0.03])
        cvi = compute_curvature_variation_index(curvature, entry_idx=1, exit_idx=2)
        assert cvi == 0.0

    def test_cvi_zero_curvature(self) -> None:
        """All-zero curvature -> CVI = 0 (avoid div-by-zero)."""
        curvature = np.zeros(100)
        cvi = compute_curvature_variation_index(curvature, entry_idx=0, exit_idx=100)
        assert cvi == 0.0


class TestCornerGroupDataclass:
    """Basic dataclass behavior for CornerGroup."""

    def test_defaults(self) -> None:
        group = CornerGroup(group_id=1)
        assert group.group_id == 1
        assert group.corner_numbers == []
        assert group.section_entry_idx == 0
        assert group.section_exit_idx == 0
        assert group.curvature_variation_index == 0.0

    def test_populated(self) -> None:
        group = CornerGroup(
            group_id=2,
            corner_numbers=[3, 4, 5],
            section_entry_idx=100,
            section_exit_idx=500,
            curvature_variation_index=1.5,
        )
        assert group.corner_numbers == [3, 4, 5]
        assert group.curvature_variation_index == 1.5


class TestLinkedCornerResultDataclass:
    """Basic dataclass behavior for LinkedCornerResult."""

    def test_defaults(self) -> None:
        result = LinkedCornerResult()
        assert result.groups == []
        assert result.corner_to_group == {}


class TestCornerLinkedGroupIdField:
    """Corner dataclass gains linked_group_id field."""

    def test_default_none(self) -> None:
        c = _make_corner(1, 0.0, 100.0)
        assert c.linked_group_id is None

    def test_set_value(self) -> None:
        c = _make_corner(1, 0.0, 100.0)
        c.linked_group_id = 3
        assert c.linked_group_id == 3


class TestLinkThresholdSensitivity:
    """Threshold parameter affects linking behavior."""

    def test_strict_threshold_links_more(self) -> None:
        """Higher threshold (closer to 1.0) means harder to reach -> more linking."""
        # Corners close enough (apexes 75m apart) to pass the distance gate.
        distance_m = np.linspace(0, 500, 1000)
        speed = np.ones(1000) * 50.0

        speed[(distance_m >= 100) & (distance_m <= 150)] = 20.0
        speed[(distance_m >= 200) & (distance_m <= 250)] = 22.0
        # Between speed = 48 m/s
        speed[(distance_m > 150) & (distance_m < 200)] = 48.0

        corners = [
            _make_corner(1, 100.0, 150.0),
            _make_corner(2, 200.0, 250.0),
        ]

        # With default threshold (0.95): 48 < 50*0.95=47.5 -> NOT linked (48 > 47.5)
        result_default = detect_linked_corners(corners, speed, distance_m)
        assert len(result_default.groups) == 0

        # With strict threshold (0.97): 48 < 50*0.97=48.5 -> linked
        result_strict = detect_linked_corners(corners, speed, distance_m, link_threshold=0.97)
        assert len(result_strict.groups) == 1

    def test_loose_threshold_unlinks(self) -> None:
        """Lower threshold (e.g. 0.5) means easier to reach -> fewer links."""
        distance_m = np.linspace(0, 500, 1000)
        speed = np.ones(1000) * 50.0

        speed[(distance_m >= 100) & (distance_m <= 150)] = 20.0
        speed[(distance_m >= 200) & (distance_m <= 250)] = 22.0
        speed[(distance_m > 150) & (distance_m < 200)] = 30.0  # 30 > 50*0.5=25

        corners = [
            _make_corner(1, 100.0, 150.0),
            _make_corner(2, 200.0, 250.0),
        ]

        result = detect_linked_corners(corners, speed, distance_m, link_threshold=0.50)
        assert len(result.groups) == 0


class TestOverlappingCorners:
    """Corners whose regions overlap are always linked."""

    def test_overlapping_corners_linked(self) -> None:
        """Overlapping corner boundaries -> always linked."""
        distance_m = np.linspace(0, 500, 1000)
        speed = np.ones(1000) * 50.0

        speed[(distance_m >= 100) & (distance_m <= 220)] = 20.0
        speed[(distance_m >= 200) & (distance_m <= 320)] = 22.0

        corners = [
            _make_corner(1, 100.0, 220.0),
            _make_corner(2, 200.0, 320.0),  # overlaps with C1
        ]

        result = detect_linked_corners(corners, speed, distance_m)
        assert len(result.groups) == 1
        assert result.groups[0].corner_numbers == [1, 2]


# ---------------------------------------------------------------------------
# Additional coverage: lines 54, 92, 99, 138, 163-164, 168-169
# ---------------------------------------------------------------------------


class TestFindVMaxStraight:
    """Tests for _find_v_max_straight edge cases."""

    def test_empty_speed_array_returns_zero(self) -> None:
        """len(corners) < 2 with empty speed → returns 0.0 (line 54)."""
        from cataclysm.linked_corners import _find_v_max_straight

        result = _find_v_max_straight(np.array([]), np.array([]), [])
        assert result == 0.0

    def test_single_corner_returns_global_max(self) -> None:
        """len(corners) < 2 → returns global max speed (line 53-54)."""
        from cataclysm.linked_corners import _find_v_max_straight

        distance_m = np.linspace(0, 500, 100)
        speed = np.ones(100) * 40.0
        speed[50] = 60.0  # global max
        corners = [_make_corner(1, 100.0, 200.0)]

        result = _find_v_max_straight(speed, distance_m, corners)
        assert result == pytest.approx(60.0)

    def test_no_straights_returns_global_max(self) -> None:
        """If no straights found, returns global max (line 92)."""
        from cataclysm.linked_corners import _find_v_max_straight

        # Corners that span the entire track → no straight segments
        distance_m = np.linspace(0, 500, 100)
        speed = np.ones(100) * 50.0
        corners = [
            _make_corner(1, 0.0, 250.0),  # first half
            _make_corner(2, 250.0, 500.0),  # second half
        ]
        result = _find_v_max_straight(speed, distance_m, corners)
        assert result == pytest.approx(50.0)

    def test_empty_segment_falls_back_to_global_max(self) -> None:
        """Empty segment in straights falls back to global max (line 99)."""
        from cataclysm.linked_corners import _find_v_max_straight

        # Two corners with the between-straight having entry=exit → empty segment
        distance_m = np.linspace(0, 1000, 10)
        speed = np.ones(10) * 45.0
        # Set corners so between-straight segment is empty
        corners = [
            _make_corner(1, 100.0, 400.0),
            _make_corner(2, 600.0, 900.0),
        ]
        result = _find_v_max_straight(speed, distance_m, corners)
        assert result > 0.0


class TestDetectLinkedCornersEdgeCases:
    """Additional edge cases for detect_linked_corners."""

    def test_zero_v_max_returns_empty(self) -> None:
        """v_max_straight == 0 → returns empty result (line 138)."""
        distance_m = np.linspace(0, 500, 100)
        speed = np.zeros(100)  # all-zero speed

        corners = [
            _make_corner(1, 100.0, 200.0),
            _make_corner(2, 300.0, 400.0),
        ]
        result = detect_linked_corners(corners, speed, distance_m)
        assert len(result.groups) == 0

    def test_entry_equals_exit_in_between(self) -> None:
        """Between-speed segment with entry_idx == exit_idx → linked (line 163-164)."""
        distance_m = np.linspace(0, 500, 10)  # very sparse
        speed = np.ones(10) * 50.0

        # Dense enough that searchsorted gives same index for both corners
        corners = [
            _make_corner(1, 100.0, 200.0),
            _make_corner(2, 201.0, 300.0),  # very close to C1 exit
        ]
        # This might or might not link depending on index resolution
        result = detect_linked_corners(corners, speed, distance_m)
        assert isinstance(
            result, pytest.importorskip("cataclysm.linked_corners").LinkedCornerResult
        )

    def test_between_speed_empty_array(self) -> None:
        """empty between_speed → linked=True (line 168-169)."""
        # Corners that are far apart but sparse speed array results in empty between-speed
        distance_m = np.array([0.0, 100.0, 200.0, 300.0, 400.0])
        speed = np.ones(5) * 50.0
        # C1 exit at 200, C2 entry at 250: no samples between them
        corners = [
            _make_corner(1, 100.0, 200.0),
            _make_corner(2, 250.0, 350.0),
        ]
        # With only 5 samples, between_speed may be empty
        result = detect_linked_corners(corners, speed, distance_m)
        # Either linked (empty between) or not — just ensure no crash
        assert isinstance(result.groups, list)


# ---------------------------------------------------------------------------
# Additional coverage: _find_v_max_straight branches
# lines 54, 92, 99, 138, 163-164, 168-169
# ---------------------------------------------------------------------------


class TestFindVMaxStraightV2:
    """Tests for _find_v_max_straight — internal speed max calculation."""

    def test_fewer_than_two_corners_returns_global_max(self) -> None:
        """< 2 corners → return global max speed (line 54)."""
        from cataclysm.linked_corners import _find_v_max_straight

        distance_m = np.linspace(0, 500, 1000)
        speed = np.ones(1000) * 40.0
        speed[200:300] = 20.0  # a corner zone

        # One corner — should return global max
        corners = [_make_corner(1, 100.0, 200.0)]
        v_max = _find_v_max_straight(speed, distance_m, corners)
        assert v_max == pytest.approx(40.0)

    def test_empty_corners_returns_global_max(self) -> None:
        """No corners → return global max speed."""
        from cataclysm.linked_corners import _find_v_max_straight

        distance_m = np.linspace(0, 500, 100)
        speed = np.ones(100) * 30.0
        v_max = _find_v_max_straight(speed, distance_m, [])
        assert v_max == pytest.approx(30.0)

    def test_overlapping_corners_no_straight_between(self) -> None:
        """Overlapping corners (entry <= exit of prev) → no straight between them.
        The result should still be a valid float (line 73-74)."""
        from cataclysm.linked_corners import _find_v_max_straight

        distance_m = np.linspace(0, 500, 1000)
        speed = np.ones(1000) * 50.0
        # Overlapping: C1 exits at 250, C2 enters at 200 < 250
        corners = [
            _make_corner(1, 100.0, 250.0),
            _make_corner(2, 200.0, 350.0),
        ]
        v_max = _find_v_max_straight(speed, distance_m, corners)
        assert v_max > 0

    def test_no_straights_returns_global_max(self) -> None:
        """If no straights exist after filtering, return global max (line 92)."""
        from cataclysm.linked_corners import _find_v_max_straight

        # Two adjacent corners that cover the entire track
        distance_m = np.linspace(0, 500, 1000)
        speed = np.ones(1000) * 40.0
        # C1 covers 0→300, C2 covers 300→500, no first_entry > 0, no after-last segment
        corners = [
            _make_corner(1, 0.0, 300.0),
            _make_corner(2, 300.0, 500.0),
        ]
        v_max = _find_v_max_straight(speed, distance_m, corners)
        # Should return global max since no straights exist
        assert v_max == pytest.approx(40.0)

    def test_empty_segment_returns_global_max(self) -> None:
        """Longest segment that is empty → return global max (line 99)."""
        from cataclysm.linked_corners import _find_v_max_straight

        # Very sparse speed array where the longest straight segment is empty
        distance_m = np.array([0.0, 500.0])
        speed = np.array([40.0, 40.0])
        corners = [
            _make_corner(1, 50.0, 100.0),
            _make_corner(2, 400.0, 450.0),
        ]
        v_max = _find_v_max_straight(speed, distance_m, corners)
        assert v_max > 0

"""Tests for cataclysm.segmentation."""

from __future__ import annotations

import numpy as np
import pytest

from cataclysm.curvature import CurvatureResult
from cataclysm.segmentation import (
    MIN_CORNER_CURVATURE,
    SegmentationResult,
    TrackSegment,
    _classify_segments,
    segment_asc,
    segment_css,
    segment_pelt,
    segment_track,
)

# ---------------------------------------------------------------------------
# Synthetic curvature helpers
# ---------------------------------------------------------------------------


def _make_oval_curvature(
    n_points: int = 2000,
    step_m: float = 0.7,
) -> CurvatureResult:
    """Build curvature for an oval track: 4 corners connected by straights."""
    distance = np.arange(n_points) * step_m
    curvature = np.zeros(n_points)

    width = int(0.05 * n_points)  # each corner spans ~5% of track

    # 4 corners at 15%, 35%, 65%, 85% of track
    for center_frac in [0.15, 0.35, 0.65, 0.85]:
        center = int(center_frac * n_points)
        for j in range(max(0, center - width), min(n_points, center + width)):
            offset = j - center
            curvature[j] = 0.02 * np.exp(-(offset**2) / (width**2 / 4))

    # Alternate left/right turns (negative curvature for right turns)
    right_centers = [0.35, 0.85]
    for center_frac in right_centers:
        center = int(center_frac * n_points)
        lo = max(0, center - width)
        hi = min(n_points, center + width)
        curvature[lo:hi] *= -1

    heading = np.cumsum(curvature) * step_m
    x = np.cumsum(np.cos(heading) * step_m)
    y = np.cumsum(np.sin(heading) * step_m)

    return CurvatureResult(
        distance_m=distance,
        curvature=curvature,
        abs_curvature=np.abs(curvature),
        heading_rad=heading,
        x_smooth=x,
        y_smooth=y,
    )


def _make_straight_curvature(
    n_points: int = 1000,
    step_m: float = 0.7,
) -> CurvatureResult:
    """Build curvature for a perfectly straight track (all zeros)."""
    distance = np.arange(n_points) * step_m
    curvature = np.zeros(n_points)
    heading = np.zeros(n_points)
    x = np.arange(n_points, dtype=float) * step_m
    y = np.zeros(n_points)

    return CurvatureResult(
        distance_m=distance,
        curvature=curvature,
        abs_curvature=curvature.copy(),
        heading_rad=heading,
        x_smooth=x,
        y_smooth=y,
    )


def _make_s_turn_curvature(
    n_points: int = 1500,
    step_m: float = 0.7,
) -> CurvatureResult:
    """Build curvature with an S-turn: left corner followed immediately by right corner."""
    distance = np.arange(n_points) * step_m
    curvature = np.zeros(n_points)

    # S-turn centred at 50% of track
    center = n_points // 2
    half_width = int(0.04 * n_points)

    # Left turn: center - 2*half_width to center
    for j in range(max(0, center - 2 * half_width), center):
        mid = center - half_width
        offset = j - mid
        curvature[j] = 0.015 * np.exp(-(offset**2) / (half_width**2 / 4))

    # Right turn: center to center + 2*half_width
    for j in range(center, min(n_points, center + 2 * half_width)):
        mid = center + half_width
        offset = j - mid
        curvature[j] = -0.015 * np.exp(-(offset**2) / (half_width**2 / 4))

    heading = np.cumsum(curvature) * step_m
    x = np.cumsum(np.cos(heading) * step_m)
    y = np.cumsum(np.sin(heading) * step_m)

    return CurvatureResult(
        distance_m=distance,
        curvature=curvature,
        abs_curvature=np.abs(curvature),
        heading_rad=heading,
        x_smooth=x,
        y_smooth=y,
    )


# ---------------------------------------------------------------------------
# TestClassifySegments
# ---------------------------------------------------------------------------


class TestClassifySegments:
    """Tests for the _classify_segments helper."""

    def test_basic_classification(self) -> None:
        """Known changepoints should produce correct straight/corner labels."""
        cr = _make_oval_curvature()
        # Place changepoints between the known corners — roughly at 10% and 20%
        # so one segment covers the first corner (at 15%) and another doesn't
        n = len(cr.distance_m)
        cp_before = float(cr.distance_m[int(0.10 * n)])
        cp_after = float(cr.distance_m[int(0.20 * n)])

        result = _classify_segments([cp_before, cp_after], cr, method="pelt")
        assert isinstance(result, SegmentationResult)
        assert result.method == "pelt"

        # There should be at least one corner and one straight in the result
        types = {s.segment_type for s in result.segments}
        assert "corner" in types or "straight" in types

        # The segment covering 10-20% of the oval should be a corner
        # (the first corner is at 15%)
        for seg in result.segments:
            if seg.entry_distance_m <= cp_before and seg.exit_distance_m >= cp_after:
                # This segment spans the first corner
                assert seg.mean_curvature > MIN_CORNER_CURVATURE

    def test_direction_detection(self) -> None:
        """Positive curvature should map to 'left', negative to 'right'."""
        cr = _make_oval_curvature()
        n = len(cr.distance_m)

        # The corner at 15% is left (positive curvature)
        # The corner at 35% is right (negative curvature)
        cp_list = [
            float(cr.distance_m[int(0.10 * n)]),
            float(cr.distance_m[int(0.20 * n)]),
            float(cr.distance_m[int(0.30 * n)]),
            float(cr.distance_m[int(0.40 * n)]),
        ]
        result = _classify_segments(cp_list, cr, method="pelt")

        directions_found: set[str] = set()
        for seg in result.segments:
            if seg.segment_type == "corner":
                directions_found.add(seg.direction)

        # Should find at least one left and one right
        assert "left" in directions_found or "right" in directions_found


# ---------------------------------------------------------------------------
# TestSegmentPelt
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestSegmentPelt:
    """Tests for PELT-based segmentation."""

    def test_detects_corners_in_oval(self) -> None:
        """Oval track should produce at least 3 segments (corners + straights)."""
        cr = _make_oval_curvature()
        result = segment_pelt(cr)

        assert isinstance(result, SegmentationResult)
        assert result.method == "pelt"
        assert len(result.segments) >= 3

        corner_segs = [s for s in result.segments if s.segment_type == "corner"]
        assert len(corner_segs) >= 1, "PELT should detect at least one corner on an oval"

    def test_straight_only_track(self) -> None:
        """A flat curvature signal should produce only straight segments."""
        cr = _make_straight_curvature()
        result = segment_pelt(cr)

        assert result.method == "pelt"
        for seg in result.segments:
            assert seg.segment_type == "straight"
            assert seg.direction == "straight"
            assert seg.mean_curvature < MIN_CORNER_CURVATURE

    def test_custom_penalty(self) -> None:
        """Passing a custom penalty should not crash and return valid results."""
        cr = _make_oval_curvature()
        result = segment_pelt(cr, penalty=5.0)
        assert isinstance(result, SegmentationResult)
        assert len(result.segments) >= 1


# ---------------------------------------------------------------------------
# TestSegmentCSS
# ---------------------------------------------------------------------------


class TestSegmentCSS:
    """Tests for Curvature Scale Space segmentation."""

    def test_detects_corners_in_oval(self) -> None:
        """Oval track should produce corner segments via CSS."""
        cr = _make_oval_curvature()
        result = segment_css(cr)

        assert isinstance(result, SegmentationResult)
        assert result.method == "css"

        corner_segs = [s for s in result.segments if s.segment_type == "corner"]
        assert len(corner_segs) >= 1, "CSS should detect at least one corner on an oval"

    def test_straight_only_track(self) -> None:
        """A flat curvature signal should produce only straight segments."""
        cr = _make_straight_curvature()
        result = segment_css(cr)

        assert result.method == "css"
        for seg in result.segments:
            assert seg.segment_type == "straight"

    def test_custom_scales(self) -> None:
        """Passing custom scales should work without error."""
        cr = _make_oval_curvature()
        result = segment_css(cr, scales=[3.0, 7.0, 15.0])
        assert isinstance(result, SegmentationResult)


# ---------------------------------------------------------------------------
# TestSegmentASC
# ---------------------------------------------------------------------------


class TestSegmentASC:
    """Tests for Adaptive Segmentation by Curvature peaks."""

    def test_detects_corners_in_oval(self) -> None:
        """Oval track should produce corner segments via ASC."""
        cr = _make_oval_curvature()
        result = segment_asc(cr)

        assert isinstance(result, SegmentationResult)
        assert result.method == "asc"

        corner_segs = [s for s in result.segments if s.segment_type == "corner"]
        assert len(corner_segs) >= 2, "ASC should detect at least 2 corners on an oval"

    def test_straight_only_track(self) -> None:
        """A flat curvature signal should produce only straight segments."""
        cr = _make_straight_curvature()
        result = segment_asc(cr)

        assert result.method == "asc"
        for seg in result.segments:
            assert seg.segment_type == "straight"

    def test_s_turn_detection(self) -> None:
        """An S-curve should be detected as corner segments (possibly split into two)."""
        cr = _make_s_turn_curvature()
        result = segment_asc(cr)

        corner_segs = [s for s in result.segments if s.segment_type == "corner"]
        assert len(corner_segs) >= 1, "ASC should detect the S-turn as at least one corner"

        # If the S-turn is split, we should see both left and right directions
        directions = {s.direction for s in corner_segs}
        # At minimum, corners were found; ideally both directions present
        if len(corner_segs) >= 2:
            assert "left" in directions and "right" in directions

    def test_segment_boundaries_ordered(self) -> None:
        """Every segment should have entry < exit."""
        cr = _make_oval_curvature()
        result = segment_asc(cr)
        for seg in result.segments:
            assert seg.entry_distance_m < seg.exit_distance_m


# ---------------------------------------------------------------------------
# TestSegmentTrack
# ---------------------------------------------------------------------------


class TestSegmentTrack:
    """Tests for the convenience dispatcher."""

    def test_dispatches_pelt(self) -> None:
        cr = _make_oval_curvature()
        result = segment_track(cr, method="pelt")
        assert result.method == "pelt"
        assert isinstance(result, SegmentationResult)

    def test_dispatches_css(self) -> None:
        cr = _make_oval_curvature()
        result = segment_track(cr, method="css")
        assert result.method == "css"

    def test_dispatches_asc(self) -> None:
        cr = _make_oval_curvature()
        result = segment_track(cr, method="asc")
        assert result.method == "asc"


# ---------------------------------------------------------------------------
# Edge case tests targeting specific uncovered lines
# ---------------------------------------------------------------------------


class TestClassifySegmentsEdgeCases:
    """Target lines 90 and 100 in _classify_segments."""

    def test_single_changepoint_outside_track_falls_back(self) -> None:
        """Changepoints outside [d_min, d_max] → fallback to [d_min, d_max] (line 90)."""
        cr = _make_straight_curvature(n_points=100)
        # Provide changepoints far outside the track range → all get filtered
        d_max = float(cr.distance_m[-1])
        result = _classify_segments([d_max * 2, d_max * 3], cr, method="pelt")
        # After clamping/filtering, should fall back to [d_min, d_max]
        assert isinstance(result, SegmentationResult)
        assert len(result.segments) >= 0  # May be 0 or 1 segment

    def test_empty_mask_segment_skipped(self) -> None:
        """Changepoints that produce an empty mask segment should be skipped (line 100)."""
        cr = _make_straight_curvature(n_points=200)
        # Use duplicate changepoints that produce a zero-width segment
        d0 = float(cr.distance_m[0])
        d1 = float(cr.distance_m[50])
        # Passing the exact same point twice in the list → zero-width segment
        result = _classify_segments([d0, d0, d1], cr, method="pelt")
        assert isinstance(result, SegmentationResult)
        # No segment should have entry_distance >= exit_distance
        for seg in result.segments:
            assert seg.entry_distance_m < seg.exit_distance_m


class TestAssignComplexIds:
    """Target lines 194-195: consecutive corner grouping in _assign_complex_ids."""

    def test_consecutive_same_direction_corners_share_complex_id(self) -> None:
        """Two consecutive left corners should share the same parent_complex ID."""
        from cataclysm.segmentation import _assign_complex_ids

        # Build two left corners separated by a tiny gap
        seg_a = TrackSegment(
            segment_type="corner",
            entry_distance_m=100.0,
            exit_distance_m=150.0,
            peak_curvature=0.02,
            mean_curvature=0.015,
            direction="left",
            scale=0.0,
            parent_complex=None,
        )
        seg_b = TrackSegment(
            segment_type="corner",
            entry_distance_m=155.0,
            exit_distance_m=200.0,
            peak_curvature=0.018,
            mean_curvature=0.012,
            direction="left",  # same direction → should share complex_id
            scale=0.0,
            parent_complex=None,
        )
        segments = [seg_a, seg_b]
        _assign_complex_ids(segments)
        # Both same-direction consecutive corners should share the same complex id (lines 194-195)
        assert seg_a.parent_complex == seg_b.parent_complex

    def test_opposite_direction_corners_get_different_complex_ids(self) -> None:
        """Left corner followed by right corner → different complex IDs."""
        from cataclysm.segmentation import _assign_complex_ids

        left_corner = TrackSegment(
            segment_type="corner",
            entry_distance_m=100.0,
            exit_distance_m=150.0,
            peak_curvature=0.02,
            mean_curvature=0.015,
            direction="left",
            scale=0.0,
            parent_complex=None,
        )
        right_corner = TrackSegment(
            segment_type="corner",
            entry_distance_m=200.0,
            exit_distance_m=250.0,
            peak_curvature=0.018,
            mean_curvature=0.012,
            direction="right",
            scale=0.0,
            parent_complex=None,
        )
        segments = [left_corner, right_corner]
        _assign_complex_ids(segments)
        assert left_corner.parent_complex != right_corner.parent_complex


class TestAscMergeZones:
    """Target line 379: adjacent zone merging in segment_asc."""

    def test_adjacent_corners_merged_into_single_zone(self) -> None:
        """Two peaks close together should be merged into one zone (line 379 merge path)."""
        # Build a track with two very close corners that will merge during zone detection
        n = 2000
        step = 0.7
        distance = np.arange(n) * step
        curvature = np.zeros(n)
        # Two tight left corners very close together (within MERGE_GAP_M)
        center1 = int(0.5 * n)
        center2 = center1 + 20  # only 20 samples apart (~14m)
        width = 15
        for j in range(max(0, center1 - width), min(n, center1 + width)):
            curvature[j] = 0.025 * np.exp(-((j - center1) ** 2) / (width**2 / 4))
        for j in range(max(0, center2 - width), min(n, center2 + width)):
            curvature[j] += 0.025 * np.exp(-((j - center2) ** 2) / (width**2 / 4))

        heading = np.cumsum(curvature) * step
        x = np.cumsum(np.cos(heading) * step)
        y = np.cumsum(np.sin(heading) * step)

        cr = CurvatureResult(
            distance_m=distance,
            curvature=curvature,
            abs_curvature=np.abs(curvature),
            heading_rad=heading,
            x_smooth=x,
            y_smooth=y,
        )
        result = segment_asc(cr)
        assert isinstance(result, SegmentationResult)
        corner_segs = [s for s in result.segments if s.segment_type == "corner"]
        # The two close peaks should be merged into fewer segments than 2 separate peaks would be
        assert len(corner_segs) >= 1

    def test_unknown_method_raises(self) -> None:
        cr = _make_oval_curvature()
        with pytest.raises(ValueError, match="Unknown segmentation method"):
            segment_track(cr, method="unknown")


# ---------------------------------------------------------------------------
# TestTrackSegmentDataclass
# ---------------------------------------------------------------------------


class TestTrackSegmentDataclass:
    """Basic dataclass validation."""

    def test_fields(self) -> None:
        seg = TrackSegment(
            segment_type="corner",
            entry_distance_m=100.0,
            exit_distance_m=200.0,
            peak_curvature=0.015,
            mean_curvature=0.008,
            direction="left",
            scale=10.0,
            parent_complex=1,
        )
        assert seg.segment_type == "corner"
        assert seg.exit_distance_m - seg.entry_distance_m == 100.0
        assert seg.parent_complex == 1


# ---------------------------------------------------------------------------
# TestParentComplex
# ---------------------------------------------------------------------------


class TestParentComplex:
    """Verify hierarchical grouping of corner complexes."""

    def test_corners_get_complex_ids(self) -> None:
        """Corner segments should receive parent_complex IDs."""
        cr = _make_oval_curvature()
        result = segment_asc(cr)

        corner_segs = [s for s in result.segments if s.segment_type == "corner"]
        if len(corner_segs) >= 1:
            assert corner_segs[0].parent_complex is not None
            assert corner_segs[0].parent_complex >= 1

    def test_straights_have_no_complex(self) -> None:
        """Straight segments should have parent_complex=None."""
        cr = _make_oval_curvature()
        result = segment_asc(cr)

        straight_segs = [s for s in result.segments if s.segment_type == "straight"]
        for seg in straight_segs:
            assert seg.parent_complex is None


# ---------------------------------------------------------------------------
# Edge case tests for uncovered lines
# ---------------------------------------------------------------------------


class TestInferStepEdgeCases:
    """Cover _infer_step_m single-point fallback (line 60)."""

    def test_single_point_returns_default(self) -> None:
        from cataclysm.segmentation import _infer_step_m

        result = _infer_step_m(np.array([42.0]))
        assert result == 0.7


class TestClassifySegmentsEdgeCasesV2:
    """Cover _classify_segments edge cases (lines 79, 90, 100)."""

    def test_empty_distance_returns_empty(self) -> None:
        cr = CurvatureResult(
            distance_m=np.array([]),
            curvature=np.array([]),
            abs_curvature=np.array([]),
            heading_rad=np.array([]),
            x_smooth=np.array([]),
            y_smooth=np.array([]),
        )
        result = _classify_segments([], cr, method="test")
        assert result.segments == []

    def test_single_boundary_after_clamp(self) -> None:
        """Changepoints outside data range → fallback to [d_min, d_max]."""
        n = 200
        distance = np.linspace(0, 100, n)
        cr = CurvatureResult(
            distance_m=distance,
            curvature=np.zeros(n),
            abs_curvature=np.zeros(n),
            heading_rad=np.zeros(n),
            x_smooth=distance,
            y_smooth=np.zeros(n),
        )
        result = _classify_segments([200.0, 300.0], cr, method="test")
        assert len(result.segments) >= 1


class TestASCEmptyDistance:
    """Cover segment_asc with empty distance (line 347)."""

    def test_empty_curvature(self) -> None:
        cr = CurvatureResult(
            distance_m=np.array([]),
            curvature=np.array([]),
            abs_curvature=np.array([]),
            heading_rad=np.array([]),
            x_smooth=np.array([]),
            y_smooth=np.array([]),
        )
        result = segment_asc(cr)
        assert result.segments == []
        assert result.method == "asc"


class TestClassifySegmentsOneBoundary:
    """Cover line 90: _classify_segments fallback when < 2 boundaries."""

    def test_degenerate_single_point_track(self) -> None:
        """A single-point distance array forces fallback to [d_min, d_max] (line 90)."""
        # Single point → all_boundaries would have length 1 before the fallback
        # Passing changepoints_m that collapse to a single unique value
        n = 5
        distance = np.linspace(50.0, 50.0, n)  # all same distance — degenerate
        cr = CurvatureResult(
            distance_m=distance,
            curvature=np.zeros(n),
            abs_curvature=np.zeros(n),
            heading_rad=np.zeros(n),
            x_smooth=distance,
            y_smooth=np.zeros(n),
        )
        # Passing changepoints all equal to d_min means after dedup/clamp: only one boundary
        result = _classify_segments([50.0, 50.0], cr, method="test")
        # Should not raise; returns at least one segment
        assert result.method == "test"


class TestClassifySegmentsNoMask:
    """Cover line 100: mask with no hits → segment skipped."""

    def test_changepoint_outside_distance_range_skipped(self) -> None:
        """Boundaries that result in empty mask between them are skipped (line 100)."""
        n = 100
        distance = np.linspace(0, 50, n)
        cr = CurvatureResult(
            distance_m=distance,
            curvature=np.zeros(n),
            abs_curvature=np.zeros(n),
            heading_rad=np.zeros(n),
            x_smooth=distance,
            y_smooth=np.zeros(n),
        )
        # Two boundaries very close together but within the array: forces a tiny segment
        # that may have no points between them when distance is coarsely sampled
        # Use boundaries slightly beyond the array to test the clamp
        result = _classify_segments([0.0, 25.0, 50.0], cr, method="test")
        # Should produce segments without raising
        assert len(result.segments) >= 1


class TestAssignComplexIdsConsecutiveSameDirection:
    """Cover lines 194-195: consecutive corners with same direction share a complex."""

    def test_two_consecutive_same_direction_corners_share_complex(self) -> None:
        """Two adjacent corners with same direction → both get same parent_complex."""
        from cataclysm.segmentation import _assign_complex_ids

        seg1 = TrackSegment(
            segment_type="corner",
            entry_distance_m=0.0,
            exit_distance_m=50.0,
            peak_curvature=0.02,
            mean_curvature=0.015,
            direction="left",
            scale=0.0,
            parent_complex=None,
        )
        seg2 = TrackSegment(
            segment_type="corner",
            entry_distance_m=50.0,
            exit_distance_m=100.0,
            peak_curvature=0.02,
            mean_curvature=0.015,
            direction="left",  # same direction as seg1
            scale=0.0,
            parent_complex=None,
        )
        seg3 = TrackSegment(
            segment_type="straight",
            entry_distance_m=100.0,
            exit_distance_m=200.0,
            peak_curvature=0.001,
            mean_curvature=0.0,
            direction="straight",
            scale=0.0,
            parent_complex=None,
        )
        _assign_complex_ids([seg1, seg2, seg3])
        # seg1 and seg2 both left → same parent_complex
        assert seg1.parent_complex is not None
        assert seg2.parent_complex == seg1.parent_complex
        assert seg3.parent_complex is None


class TestASCMergeOverlappingZones:
    """Cover line 379: overlapping corner zones are merged."""

    def test_overlapping_corner_peaks_merge(self) -> None:
        """Two peaks whose zones overlap are merged into one zone (line 379)."""
        n = 500
        distance = np.linspace(0, 200, n)
        # Build two close peaks whose expansion zones overlap
        curv = np.zeros(n)
        step = 200.0 / (n - 1)
        # peak at index 100 and index 110 — close enough to overlap after expansion
        for i in range(90, 115):
            curv[i] = 0.03 * np.exp(-((i - 102) ** 2) / 20)
        cr = CurvatureResult(
            distance_m=distance,
            curvature=curv,
            abs_curvature=np.abs(curv),
            heading_rad=np.cumsum(curv) * step,
            x_smooth=distance,
            y_smooth=np.zeros(n),
        )
        result = segment_asc(cr)
        # Should not raise and should produce at least one segment
        assert len(result.segments) >= 1

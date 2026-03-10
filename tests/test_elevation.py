"""Tests for cataclysm.elevation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cataclysm.corners import Corner
from cataclysm.elevation import (
    CornerElevation,
    compute_corner_elevation,
    enrich_corners_with_elevation,
)


def _make_corner(number: int, entry_m: float, exit_m: float, apex_m: float) -> Corner:
    return Corner(
        number=number,
        entry_distance_m=entry_m,
        exit_distance_m=exit_m,
        apex_distance_m=(entry_m + exit_m) / 2 if apex_m == 0 else apex_m,
        min_speed_mps=20.0,
        brake_point_m=None,
        peak_brake_g=None,
        throttle_commit_m=None,
        apex_type="mid",
    )


def _make_lap_df(
    n: int = 1000,
    step_m: float = 0.7,
    altitude_fn: object | None = None,
) -> pd.DataFrame:
    """Build a lap DataFrame with optional altitude profile."""
    distance = np.arange(n) * step_m
    data: dict[str, np.ndarray] = {"lap_distance_m": distance}
    if altitude_fn is not None:
        data["altitude_m"] = np.array([altitude_fn(d) for d in distance])  # type: ignore[operator]
    return pd.DataFrame(data)


class TestFlatTrack:
    def test_all_flat(self) -> None:
        """Constant altitude → 'flat' trend, ~0% gradient."""
        df = _make_lap_df(altitude_fn=lambda _d: 200.0)
        corners = [_make_corner(1, 100.0, 300.0, 200.0)]
        result = compute_corner_elevation(df, corners)
        assert len(result) == 1
        assert result[0].trend == "flat"
        assert abs(result[0].gradient_pct) < 1.0
        assert abs(result[0].elevation_change_m) < 1.0


class TestUphillCorner:
    def test_uphill(self) -> None:
        """Rising altitude → 'uphill' trend, positive gradient."""
        df = _make_lap_df(altitude_fn=lambda d: 200.0 + d * 0.05)
        corners = [_make_corner(1, 100.0, 400.0, 250.0)]
        result = compute_corner_elevation(df, corners)
        assert len(result) == 1
        assert result[0].trend == "uphill"
        assert result[0].gradient_pct > 0
        assert result[0].elevation_change_m > 0


class TestDownhillCorner:
    def test_downhill(self) -> None:
        """Falling altitude → 'downhill' trend, negative gradient."""
        df = _make_lap_df(altitude_fn=lambda d: 300.0 - d * 0.05)
        corners = [_make_corner(1, 100.0, 400.0, 250.0)]
        result = compute_corner_elevation(df, corners)
        assert len(result) == 1
        assert result[0].trend == "downhill"
        assert result[0].gradient_pct < 0
        assert result[0].elevation_change_m < 0


class TestCrestClassification:
    def test_crest(self) -> None:
        """Peak-then-drop altitude → 'crest' trend."""

        def alt_fn(d: float) -> float:
            # Strong V-shaped peak: rises 10m to midpoint, then drops 10m
            if d < 350.0:
                return 200.0 + (d - 100.0) * 0.04  # +10m over 250m
            return 210.0 - (d - 350.0) * 0.04  # -10m over 250m

        df = _make_lap_df(n=1500, altitude_fn=alt_fn)
        corners = [_make_corner(1, 100.0, 600.0, 350.0)]
        result = compute_corner_elevation(df, corners)
        assert len(result) == 1
        assert result[0].trend == "crest"

    def test_crest_apex_aware_when_apex_is_early(self) -> None:
        """Early apex peak should still classify as crest via apex-aware sign change."""

        def alt_fn(d: float) -> float:
            if d <= 180.0:
                return 200.0 + (d - 100.0) * 0.12
            return 209.6 - (d - 180.0) * 0.09

        df = _make_lap_df(n=1600, altitude_fn=alt_fn)
        corners = [_make_corner(1, 100.0, 600.0, 180.0)]
        result = compute_corner_elevation(df, corners)
        assert len(result) == 1
        assert result[0].trend == "crest"


class TestCompressionClassification:
    def test_compression(self) -> None:
        """Dip-then-rise altitude → 'compression' trend."""

        def alt_fn(d: float) -> float:
            # Strong V-shaped dip: drops 10m to midpoint, then rises 10m
            if d < 350.0:
                return 200.0 - (d - 100.0) * 0.04  # -10m over 250m
            return 190.0 + (d - 350.0) * 0.04  # +10m over 250m

        df = _make_lap_df(n=1500, altitude_fn=alt_fn)
        corners = [_make_corner(1, 100.0, 600.0, 350.0)]
        result = compute_corner_elevation(df, corners)
        assert len(result) == 1
        assert result[0].trend == "compression"

    def test_compression_apex_aware_when_apex_is_early(self) -> None:
        """Early apex dip should still classify as compression via apex-aware sign change."""

        def alt_fn(d: float) -> float:
            if d <= 180.0:
                return 200.0 - (d - 100.0) * 0.12
            return 190.4 + (d - 180.0) * 0.09

        df = _make_lap_df(n=1600, altitude_fn=alt_fn)
        corners = [_make_corner(1, 100.0, 600.0, 180.0)]
        result = compute_corner_elevation(df, corners)
        assert len(result) == 1
        assert result[0].trend == "compression"


class TestMissingAltitude:
    def test_no_altitude_column(self) -> None:
        """No altitude_m column → empty list."""
        df = _make_lap_df(altitude_fn=None)
        corners = [_make_corner(1, 100.0, 300.0, 200.0)]
        result = compute_corner_elevation(df, corners)
        assert result == []


class TestSmoothingHandlesNoise:
    def test_noisy_data(self) -> None:
        """Noisy altitude data should still produce reasonable results."""
        rng = np.random.default_rng(42)

        def noisy_uphill(d: float) -> float:
            return 200.0 + d * 0.03 + rng.normal(0, 3.0)

        df = _make_lap_df(n=2000, altitude_fn=noisy_uphill)
        corners = [_make_corner(1, 200.0, 800.0, 500.0)]
        result = compute_corner_elevation(df, corners)
        assert len(result) == 1
        # Should classify as uphill despite noise
        assert result[0].trend == "uphill"
        assert result[0].gradient_pct > 0


class TestMultipleCorners:
    def test_multiple_corners(self) -> None:
        """Multiple corners should each get their own elevation data."""
        df = _make_lap_df(altitude_fn=lambda d: 200.0 + d * 0.02)
        corners = [
            _make_corner(1, 50.0, 200.0, 125.0),
            _make_corner(2, 300.0, 500.0, 400.0),
        ]
        result = compute_corner_elevation(df, corners)
        assert len(result) == 2
        assert result[0].corner_number == 1
        assert result[1].corner_number == 2


class TestEnrichCornersWithElevation:
    def test_enriches_corners_in_place(self) -> None:
        """enrich_corners_with_elevation should set elevation fields on corners."""
        corner = _make_corner(1, 100.0, 300.0, 200.0)
        all_lap_corners = {1: [corner]}
        elevations = [CornerElevation(1, 5.0, 2.5, "uphill")]
        enrich_corners_with_elevation(all_lap_corners, elevations)
        assert corner.elevation_change_m == 5.0
        assert corner.gradient_pct == 2.5
        assert corner.elevation_trend == "uphill"

    def test_curated_trend_takes_precedence(self) -> None:
        """If corner already has elevation_trend, computed trend should not overwrite."""
        corner = _make_corner(1, 100.0, 300.0, 200.0)
        corner.elevation_trend = "crest"  # curated from track_db
        all_lap_corners = {1: [corner]}
        elevations = [CornerElevation(1, 5.0, 2.5, "uphill")]
        enrich_corners_with_elevation(all_lap_corners, elevations)
        assert corner.elevation_change_m == 5.0  # still set
        assert corner.gradient_pct == 2.5  # still set
        assert corner.elevation_trend == "crest"  # NOT overwritten

    def test_no_matching_elevation(self) -> None:
        """Corners without matching elevation data should be unchanged."""
        corner = _make_corner(5, 100.0, 300.0, 200.0)
        all_lap_corners = {1: [corner]}
        elevations = [CornerElevation(1, 5.0, 2.5, "uphill")]  # corner 1, not 5
        enrich_corners_with_elevation(all_lap_corners, elevations)
        assert corner.elevation_change_m is None
        assert corner.gradient_pct is None


# ---------------------------------------------------------------------------
# TestClassifyTrendEdgeCases (lines 56-58: short segment fallback)
# ---------------------------------------------------------------------------


class TestClassifyTrendEdgeCases:
    """Edge cases for _classify_trend (lines 56-58 and 69-73)."""

    def test_short_segment_flat_gradient(self) -> None:
        """Segment with fewer than 3 points and small gradient returns 'flat'."""
        from cataclysm.elevation import _classify_trend

        alt = np.array([200.0, 200.1])
        result = _classify_trend(alt, entry_idx=0, exit_idx=1, gradient_pct=0.5)
        assert result == "flat"

    def test_short_segment_uphill_gradient(self) -> None:
        """Segment with fewer than 3 points and significant positive gradient returns 'uphill'."""
        from cataclysm.elevation import _classify_trend

        alt = np.array([200.0, 205.0])
        result = _classify_trend(alt, entry_idx=0, exit_idx=1, gradient_pct=5.0)
        assert result == "uphill"

    def test_short_segment_downhill_gradient(self) -> None:
        """Segment with fewer than 3 points and significant negative gradient returns 'downhill'."""
        from cataclysm.elevation import _classify_trend

        alt = np.array([205.0, 200.0])
        result = _classify_trend(alt, entry_idx=0, exit_idx=1, gradient_pct=-5.0)
        assert result == "downhill"

    def test_short_segment_preserves_existing_sign_behavior(self) -> None:
        """Short segments keep legacy sign-based fallback for >=1% gradient."""
        from cataclysm.elevation import _classify_trend

        alt = np.array([200.0, 200.05])
        result = _classify_trend(alt, entry_idx=0, exit_idx=1, gradient_pct=1.2)
        assert result == "uphill"

    def test_crest_detected_when_halves_exceed_threshold(self) -> None:
        """Segment that rises then falls by more than 0.5m each returns 'crest'."""
        from cataclysm.elevation import _classify_trend

        # 7-point crest: 200 → 201 → 202 → 203 → 202 → 201 → 200
        alt = np.array([200.0, 201.0, 202.0, 203.0, 202.0, 201.0, 200.0])
        result = _classify_trend(alt, entry_idx=0, exit_idx=6, gradient_pct=0.0)
        assert result == "crest"

    def test_compression_detected_when_halves_exceed_threshold(self) -> None:
        """Segment that falls then rises by more than 0.5m each returns 'compression'."""
        from cataclysm.elevation import _classify_trend

        # 7-point compression: 200 → 199 → 198 → 197 → 198 → 199 → 200
        alt = np.array([200.0, 199.0, 198.0, 197.0, 198.0, 199.0, 200.0])
        result = _classify_trend(alt, entry_idx=0, exit_idx=6, gradient_pct=0.0)
        assert result == "compression"

    def test_insignificant_shape_falls_through_to_flat(self) -> None:
        """Half-deltas below 0.5m threshold and low overall gradient returns 'flat'."""
        from cataclysm.elevation import _classify_trend

        # Very minor hill shape — each half changes by well under 0.5m threshold
        alt = np.array([200.0, 200.01, 200.02, 200.03, 200.02, 200.01, 200.0])
        result = _classify_trend(alt, entry_idx=0, exit_idx=6, gradient_pct=0.0)
        assert result == "flat"

    def test_apex_aware_detects_early_crest(self) -> None:
        """Apex-aware sign-change logic should detect crest even when midpoint would miss."""
        from cataclysm.elevation import _classify_trend

        alt = np.array([200.0, 203.0, 202.0, 201.0, 200.0, 199.0, 198.0, 197.0, 196.0])
        result = _classify_trend(alt, entry_idx=0, exit_idx=8, gradient_pct=-4.0, apex_idx=1)
        assert result == "crest"

    def test_apex_aware_detects_early_compression(self) -> None:
        """Apex-aware sign-change logic should detect compression with an early dip."""
        from cataclysm.elevation import _classify_trend

        alt = np.array([200.0, 197.0, 198.0, 199.0, 200.0, 201.0, 202.0, 203.0, 204.0])
        result = _classify_trend(alt, entry_idx=0, exit_idx=8, gradient_pct=4.0, apex_idx=1)
        assert result == "compression"

    def test_invalid_apex_falls_back_to_midpoint_shape(self) -> None:
        """Out-of-range apex index should not break shape detection."""
        from cataclysm.elevation import _classify_trend

        alt = np.array([200.0, 201.0, 202.0, 203.0, 202.0, 201.0, 200.0])
        result = _classify_trend(alt, entry_idx=0, exit_idx=6, gradient_pct=0.0, apex_idx=99)
        assert result == "crest"

    def test_deadband_between_flat_and_uphill_is_flat(self) -> None:
        """Gradients between 1.0% and 1.5% should classify as flat when no shape exists."""
        from cataclysm.elevation import _classify_trend

        alt = np.array([200.0, 201.0, 202.0, 203.0])
        result = _classify_trend(alt, entry_idx=0, exit_idx=3, gradient_pct=1.2)
        assert result == "flat"

    def test_threshold_boundaries_are_not_uphill_or_downhill(self) -> None:
        """Exactly +/-1.5% should not classify as uphill/downhill."""
        from cataclysm.elevation import _classify_trend

        alt = np.array([200.0, 201.0, 202.0, 203.0])
        assert _classify_trend(alt, entry_idx=0, exit_idx=3, gradient_pct=1.5) == "flat"
        assert _classify_trend(alt, entry_idx=0, exit_idx=3, gradient_pct=-1.5) == "flat"


# ---------------------------------------------------------------------------
# TestComputeCornerElevationEdgeCases (lines 107, 120)
# ---------------------------------------------------------------------------


class TestComputeCornerElevationEdgeCases:
    """Extra edge cases for compute_corner_elevation (lines 107, 120)."""

    def test_all_nan_altitude_returns_empty(self) -> None:
        """When all altitude values are NaN, returns empty list (line 107)."""
        n = 200
        df = _make_lap_df(n=n, altitude_fn=lambda _d: float("nan"))
        corners = [_make_corner(1, 10.0, 80.0, 45.0)]
        result = compute_corner_elevation(df, corners)
        assert result == []

    def test_exit_idx_equal_entry_idx_corner_skipped(self) -> None:
        """When exit_idx collapses to entry_idx after clamping, corner is skipped (line 120)."""
        df = pd.DataFrame(
            {
                "lap_distance_m": np.array([0.0, 0.7]),
                "altitude_m": np.array([200.0, 200.5]),
            }
        )
        # entry=0.3 and exit=0.4: both searchsorted to index 1, then clamped to 1 → skip
        corners = [_make_corner(1, 0.3, 0.4, 0.35)]
        result = compute_corner_elevation(df, corners)
        assert result == []

    def test_gradient_computed_correctly(self) -> None:
        """Gradient percentage should be (elevation_change / horiz_dist) * 100."""
        n = 500
        step_m = 1.0

        def alt_fn(d: float) -> float:
            return 200.0 + d * 0.05  # 5% uphill

        df = _make_lap_df(n=n, step_m=step_m, altitude_fn=alt_fn)
        corners = [_make_corner(1, 50.0, 200.0, 125.0)]
        result = compute_corner_elevation(df, corners, step_m=step_m)
        assert len(result) == 1
        # Should be close to 5%
        assert abs(result[0].gradient_pct - 5.0) < 1.5

    def test_apex_outside_corner_range_still_classifies(self) -> None:
        """Apex before entry should not fail trend classification."""
        df = _make_lap_df(n=700, altitude_fn=lambda d: 200.0 + d * 0.03)
        corners = [_make_corner(1, 100.0, 300.0, 50.0)]
        result = compute_corner_elevation(df, corners)
        assert len(result) == 1
        assert result[0].trend == "uphill"

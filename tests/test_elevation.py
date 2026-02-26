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

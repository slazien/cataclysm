"""Tests for track data quality confidence scoring."""

from __future__ import annotations

import pytest

from cataclysm.track_db import OfficialCorner
from cataclysm.track_quality import (
    QualityScore,
    _assign_tier,
    _compute_field_completeness,
    compute_quality_score,
)


def _make_corner(
    number: int = 1,
    name: str = "T1",
    fraction: float = 0.1,
    *,
    direction: str | None = None,
    corner_type: str | None = None,
    elevation_trend: str | None = None,
    camber: str | None = None,
    coaching_notes: str | None = None,
    character: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    blind: bool = False,
) -> OfficialCorner:
    return OfficialCorner(
        number=number,
        name=name,
        fraction=fraction,
        direction=direction,
        corner_type=corner_type,
        elevation_trend=elevation_trend,
        camber=camber,
        coaching_notes=coaching_notes,
        character=character,
        lat=lat,
        lon=lon,
        blind=blind,
    )


def _fully_populated_corner(number: int = 1) -> OfficialCorner:
    """A corner with every optional field filled."""
    return _make_corner(
        number=number,
        name=f"Turn {number}",
        fraction=number * 0.05,
        direction="left",
        corner_type="hairpin",
        elevation_trend="uphill",
        camber="positive",
        coaching_notes="Trail brake deep into apex",
        character="brake",
        lat=33.45,
        lon=-86.78,
    )


def _minimal_corner(number: int = 1) -> OfficialCorner:
    """A corner with only required fields -- all optional fields None/default."""
    return _make_corner(number=number, name=f"T{number}", fraction=number * 0.05)


# ─── Test 1: Fully populated + LIDAR + manual → score > 0.8, tier 3 ───


class TestFullyPopulated:
    def test_high_score(self) -> None:
        corners = [_fully_populated_corner(i) for i in range(1, 6)]
        result = compute_quality_score(
            corners,
            elevation_source="usgs_3dep",
            corner_source="manual",
            has_centerline=True,
            has_elevation_profile=True,
            has_landmarks=True,
            track_length_m=3500.0,
        )
        assert result.overall > 0.8
        assert result.suggested_tier == 3
        assert result.field_completeness == pytest.approx(1.0)
        assert result.elevation_quality == pytest.approx(1.0)
        assert result.corner_verification == pytest.approx(1.0)
        assert result.source_count == pytest.approx(1.0)

    def test_returns_quality_score_dataclass(self) -> None:
        corners = [_fully_populated_corner()]
        result = compute_quality_score(corners, elevation_source="usgs_3dep")
        assert isinstance(result, QualityScore)


# ─── Test 2: Minimal auto-detected, no elevation → score < 0.3, tier 1 ───


class TestMinimalAutoDetected:
    def test_low_score(self) -> None:
        corners = [_minimal_corner(i) for i in range(1, 4)]
        result = compute_quality_score(
            corners,
            elevation_source=None,
            corner_source="auto",
        )
        assert result.overall < 0.3
        assert result.suggested_tier == 1
        assert result.field_completeness == pytest.approx(0.0)
        assert result.elevation_quality == pytest.approx(0.0)

    def test_corner_verification_auto(self) -> None:
        corners = [_minimal_corner()]
        result = compute_quality_score(corners, corner_source="auto")
        assert result.corner_verification == pytest.approx(0.3)


# ─── Test 3: Partially filled + Copernicus + admin → tier 2 ───


class TestPartiallyFilled:
    def test_tier_2(self) -> None:
        corners = [
            _make_corner(
                number=1,
                direction="left",
                corner_type="sweeper",
                lat=33.45,
                lon=-86.78,
            ),
            _make_corner(number=2, direction="right"),
            _make_corner(number=3),
        ]
        result = compute_quality_score(
            corners,
            elevation_source="copernicus_dem",
            corner_source="admin",
            has_centerline=True,
            track_length_m=2400.0,
        )
        assert result.suggested_tier == 2
        assert 0.3 <= result.overall < 0.7


# ─── Test 4: Empty corner list → score near 0, tier 1 ───


class TestEmptyCorners:
    def test_empty_list(self) -> None:
        result = compute_quality_score([])
        # With default corner_source="auto" (0.3), overall = 0.25*0.3 = 0.075
        assert result.overall == pytest.approx(0.075)
        assert result.suggested_tier == 1
        assert result.field_completeness == pytest.approx(0.0)

    def test_source_count_no_corners(self) -> None:
        result = compute_quality_score([])
        # has_corners = False since len([]) == 0
        assert result.source_count == pytest.approx(0.0)


# ─── Test 5: Field completeness — all fields vs none ───


class TestFieldCompleteness:
    def test_all_fields_filled(self) -> None:
        corners = [_fully_populated_corner()]
        assert _compute_field_completeness(corners) == pytest.approx(1.0)

    def test_no_fields_filled(self) -> None:
        corners = [_minimal_corner()]
        assert _compute_field_completeness(corners) == pytest.approx(0.0)

    def test_partial_fields(self) -> None:
        corner = _make_corner(direction="left", camber="positive", character="brake")
        # 3 out of 7 fields filled
        assert _compute_field_completeness([corner]) == pytest.approx(3.0 / 7.0)

    def test_lat_lon_both_required(self) -> None:
        # Only lat set, lon is None -> lat/lon pair not counted
        corner = _make_corner(lat=33.45)
        assert _compute_field_completeness([corner]) == pytest.approx(0.0)

        # Both set -> counted
        corner = _make_corner(lat=33.45, lon=-86.78)
        assert _compute_field_completeness([corner]) == pytest.approx(1.0 / 7.0)

    def test_multiple_corners_averaged(self) -> None:
        full = _fully_populated_corner(1)
        empty = _minimal_corner(2)
        result = _compute_field_completeness([full, empty])
        assert result == pytest.approx(0.5)

    def test_empty_list_returns_zero(self) -> None:
        assert _compute_field_completeness([]) == pytest.approx(0.0)


# ─── Test 6: Tier boundary values ───


class TestTierBoundaries:
    def test_exactly_0_3_is_tier_2(self) -> None:
        assert _assign_tier(0.3) == 2

    def test_just_below_0_3_is_tier_1(self) -> None:
        assert _assign_tier(0.2999) == 1

    def test_exactly_0_7_is_tier_3(self) -> None:
        assert _assign_tier(0.7) == 3

    def test_just_below_0_7_is_tier_2(self) -> None:
        assert _assign_tier(0.6999) == 2

    def test_zero_is_tier_1(self) -> None:
        assert _assign_tier(0.0) == 1

    def test_one_is_tier_3(self) -> None:
        assert _assign_tier(1.0) == 3


# ─── Elevation source mapping ───


class TestElevationSource:
    def test_usgs_3dep(self) -> None:
        result = compute_quality_score([], elevation_source="usgs_3dep")
        assert result.elevation_quality == pytest.approx(1.0)

    def test_copernicus(self) -> None:
        result = compute_quality_score([], elevation_source="copernicus_dem")
        assert result.elevation_quality == pytest.approx(0.6)

    def test_gps_fallback(self) -> None:
        result = compute_quality_score([], elevation_source="gps_fallback")
        assert result.elevation_quality == pytest.approx(0.3)

    def test_none(self) -> None:
        result = compute_quality_score([], elevation_source=None)
        assert result.elevation_quality == pytest.approx(0.0)

    def test_unknown_source(self) -> None:
        result = compute_quality_score([], elevation_source="unknown_thing")
        assert result.elevation_quality == pytest.approx(0.0)


# ─── Corner verification source mapping ───


class TestCornerSource:
    def test_manual(self) -> None:
        result = compute_quality_score([], corner_source="manual")
        assert result.corner_verification == pytest.approx(1.0)

    def test_admin(self) -> None:
        result = compute_quality_score([], corner_source="admin")
        assert result.corner_verification == pytest.approx(0.8)

    def test_auto(self) -> None:
        result = compute_quality_score([], corner_source="auto")
        assert result.corner_verification == pytest.approx(0.3)

    def test_unknown_source(self) -> None:
        result = compute_quality_score([], corner_source="unknown")
        assert result.corner_verification == pytest.approx(0.0)


# ─── Source count normalization ───


class TestSourceCount:
    def test_all_sources(self) -> None:
        corners = [_minimal_corner()]
        result = compute_quality_score(
            corners,
            has_centerline=True,
            has_elevation_profile=True,
            has_landmarks=True,
            track_length_m=3500.0,
        )
        assert result.source_count == pytest.approx(1.0)

    def test_no_sources(self) -> None:
        result = compute_quality_score([])
        assert result.source_count == pytest.approx(0.0)

    def test_partial_sources(self) -> None:
        result = compute_quality_score(
            [],
            has_centerline=True,
            has_landmarks=True,
        )
        # has_centerline + has_landmarks = 2/5
        assert result.source_count == pytest.approx(0.4)


# ─── Overall score weighting ───


class TestWeightedScore:
    def test_weights_sum_to_one(self) -> None:
        """Sanity check: all component weights add up to 1.0."""
        from cataclysm.track_quality import (
            _W_CORNER_VERIFICATION,
            _W_ELEVATION,
            _W_FIELD_COMPLETENESS,
            _W_SOURCE_COUNT,
        )

        total = _W_FIELD_COMPLETENESS + _W_ELEVATION + _W_CORNER_VERIFICATION + _W_SOURCE_COUNT
        assert total == pytest.approx(1.0)

    def test_overall_is_weighted_average(self) -> None:
        """Verify overall = weighted sum of components."""
        corners = [_make_corner(direction="left", corner_type="hairpin")]
        result = compute_quality_score(
            corners,
            elevation_source="copernicus_dem",
            corner_source="admin",
            has_centerline=True,
            track_length_m=1000.0,
        )
        expected = (
            0.40 * result.field_completeness
            + 0.20 * result.elevation_quality
            + 0.25 * result.corner_verification
            + 0.15 * result.source_count
        )
        assert result.overall == pytest.approx(expected)

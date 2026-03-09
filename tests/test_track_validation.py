"""Tests for automated track data validation."""

from __future__ import annotations

import math

from cataclysm.track_db import OfficialCorner
from cataclysm.track_validation import ValidationResult, validate_track


class TestValidateTrack:
    def test_fractions_monotonic_pass(self) -> None:
        corners = [
            OfficialCorner(1, "T1", 0.10),
            OfficialCorner(2, "T2", 0.50),
        ]
        result = validate_track(corners, length_m=1000.0)
        assert result.fraction_monotonic is True

    def test_fractions_non_monotonic_fail(self) -> None:
        corners = [
            OfficialCorner(1, "T1", 0.50),
            OfficialCorner(2, "T2", 0.10),
        ]
        result = validate_track(corners, length_m=1000.0)
        assert result.fraction_monotonic is False
        assert result.is_valid is False
        assert any("<= previous" in i.message for i in result.issues)

    def test_fraction_spacing_too_close(self) -> None:
        corners = [
            OfficialCorner(1, "T1", 0.10),
            OfficialCorner(2, "T2", 0.105),
        ]
        result = validate_track(corners, length_m=1000.0)
        assert result.fraction_spacing is False
        assert result.is_valid is False

    def test_fraction_spacing_exactly_at_threshold(self) -> None:
        corners = [
            OfficialCorner(1, "T1", 0.10),
            OfficialCorner(2, "T2", 0.11),
        ]
        result = validate_track(corners, length_m=1000.0)
        assert result.fraction_spacing is True

    def test_direction_consistency(self) -> None:
        corners = [
            OfficialCorner(1, "T1", 0.10, direction="left"),
            OfficialCorner(2, "T2", 0.50, direction="right"),
        ]
        result = validate_track(corners, length_m=1000.0)
        assert result.all_directions_set is True

    def test_missing_directions_flagged(self) -> None:
        corners = [OfficialCorner(1, "T1", 0.10)]
        result = validate_track(corners, length_m=1000.0)
        assert result.all_directions_set is False

    def test_quality_score_fully_populated(self) -> None:
        corners = [
            OfficialCorner(
                1,
                "T1",
                0.10,
                direction="left",
                corner_type="hairpin",
                coaching_notes="Brake hard.",
                elevation_trend="downhill",
                camber="positive",
                lat=33.5,
                lon=-86.6,
            ),
        ]
        result = validate_track(corners, length_m=1000.0)
        assert result.quality_score == 1.0

    def test_quality_score_partial(self) -> None:
        corners = [
            OfficialCorner(
                1,
                "T1",
                0.10,
                direction="left",
                corner_type="hairpin",
                coaching_notes="Brake hard.",
                elevation_trend="downhill",
            ),
        ]
        result = validate_track(corners, length_m=1000.0)
        assert result.quality_score > 0.5
        assert result.quality_score < 1.0

    def test_overall_valid(self) -> None:
        corners = [
            OfficialCorner(1, "T1", 0.10, direction="left"),
            OfficialCorner(2, "T2", 0.50, direction="right"),
        ]
        result = validate_track(corners, length_m=1000.0)
        assert result.is_valid is True

    def test_overall_invalid_when_non_monotonic(self) -> None:
        corners = [
            OfficialCorner(1, "T1", 0.50),
            OfficialCorner(2, "T2", 0.10),
        ]
        result = validate_track(corners, length_m=1000.0)
        assert result.is_valid is False

    def test_zero_corners_invalid(self) -> None:
        """Zero-corner tracks are invalid — physics solver needs corners."""
        result = validate_track([], length_m=1000.0)
        assert result.is_valid is False
        assert result.quality_score == 0.0
        assert any("zero corners" in i.message.lower() for i in result.issues)

    def test_empty_corners_directions_and_notes_false(self) -> None:
        result = validate_track([], length_m=1000.0)
        assert result.all_directions_set is False
        assert result.all_coaching_notes is False

    def test_quality_score_no_length(self) -> None:
        """length_m=None should reduce quality score."""
        corners = [
            OfficialCorner(
                1,
                "T1",
                0.10,
                direction="left",
                corner_type="hairpin",
                coaching_notes="Brake hard.",
                elevation_trend="downhill",
                camber="positive",
                lat=33.5,
                lon=-86.6,
            ),
        ]
        result = validate_track(corners)
        # Missing length_m -> should lose 0.10 weight
        assert result.quality_score < 1.0
        assert abs(result.quality_score - 0.9) < 0.01

    def test_validation_result_is_valid_property(self) -> None:
        r = ValidationResult(
            fraction_monotonic=True,
            fraction_spacing=True,
            all_directions_set=False,
            all_coaching_notes=False,
            quality_score=0.3,
        )
        assert r.is_valid is True

        r2 = ValidationResult(
            fraction_monotonic=True,
            fraction_spacing=False,
            all_directions_set=True,
            all_coaching_notes=True,
            quality_score=0.9,
        )
        # No issues in the issues list, so still valid despite fraction_spacing=False
        # (is_valid now depends on issues, not booleans)
        assert r2.is_valid is True

    def test_fraction_out_of_range(self) -> None:
        """Fractions must be in [0.0, 1.0)."""
        # Fraction >= 1.0
        corners = [OfficialCorner(1, "T1", 1.0)]
        result = validate_track(corners, length_m=1000.0)
        assert result.is_valid is False
        assert any("outside [0.0, 1.0)" in i.message for i in result.issues)

        # Negative fraction
        corners = [OfficialCorner(1, "T1", -0.05)]
        result = validate_track(corners, length_m=1000.0)
        assert result.is_valid is False
        assert any("outside [0.0, 1.0)" in i.message for i in result.issues)

    def test_fraction_at_upper_bound_invalid(self) -> None:
        """Fraction of exactly 1.0 is out of range (upper bound exclusive)."""
        corners = [OfficialCorner(1, "T1", 1.0)]
        result = validate_track(corners, length_m=1000.0)
        assert result.is_valid is False

    def test_wrap_around_spacing_too_close(self) -> None:
        """Last corner near 1.0 and first corner near 0.0 must have enough gap."""
        corners = [
            OfficialCorner(1, "T1", 0.002),
            OfficialCorner(2, "T2", 0.50),
            OfficialCorner(3, "T3", 0.997),
        ]
        # Wrap-around gap = (1.0 - 0.997) + 0.002 = 0.005 < 0.01
        result = validate_track(corners, length_m=1000.0)
        assert result.is_valid is False
        assert any("wrap-around" in i.message for i in result.issues)

    def test_wrap_around_spacing_ok(self) -> None:
        """Wrap-around with sufficient gap is valid."""
        corners = [
            OfficialCorner(1, "T1", 0.05),
            OfficialCorner(2, "T2", 0.50),
            OfficialCorner(3, "T3", 0.90),
        ]
        # Wrap-around gap = (1.0 - 0.90) + 0.05 = 0.15 >= 0.01
        result = validate_track(corners, length_m=1000.0)
        assert result.is_valid is True
        assert not any("wrap-around" in i.message for i in result.issues)

    def test_length_m_negative_invalid(self) -> None:
        """Track length must be positive when provided."""
        corners = [OfficialCorner(1, "T1", 0.10)]
        result = validate_track(corners, length_m=-100.0)
        assert result.is_valid is False
        assert any("positive" in i.message for i in result.issues)

    def test_length_m_zero_invalid(self) -> None:
        """Zero-length track is invalid."""
        corners = [OfficialCorner(1, "T1", 0.10)]
        result = validate_track(corners, length_m=0.0)
        assert result.is_valid is False

    def test_length_m_none_ok(self) -> None:
        """length_m=None is allowed (just reduces quality score)."""
        corners = [OfficialCorner(1, "T1", 0.10)]
        result = validate_track(corners)
        assert result.is_valid is True

    def test_elevation_length_mismatch(self) -> None:
        """distances_m and elevations_m must have the same length."""
        corners = [OfficialCorner(1, "T1", 0.10)]
        result = validate_track(
            corners,
            length_m=1000.0,
            elevation_distances=[0.0, 100.0, 200.0],
            elevation_values=[10.0, 12.0],
        )
        assert result.is_valid is False
        assert any("length mismatch" in i.message.lower() for i in result.issues)

    def test_elevation_not_increasing(self) -> None:
        """Elevation distances must be strictly increasing."""
        corners = [OfficialCorner(1, "T1", 0.10)]
        result = validate_track(
            corners,
            length_m=1000.0,
            elevation_distances=[0.0, 100.0, 50.0],
            elevation_values=[10.0, 12.0, 11.0],
        )
        assert result.is_valid is False
        assert any("not strictly increasing" in i.message for i in result.issues)

    def test_elevation_nan_invalid(self) -> None:
        """NaN in elevation data is invalid."""
        corners = [OfficialCorner(1, "T1", 0.10)]

        # NaN in distances
        result = validate_track(
            corners,
            length_m=1000.0,
            elevation_distances=[0.0, float("nan"), 200.0],
            elevation_values=[10.0, 12.0, 14.0],
        )
        assert result.is_valid is False
        assert any("nan" in i.message.lower() for i in result.issues)

        # NaN in values
        result = validate_track(
            corners,
            length_m=1000.0,
            elevation_distances=[0.0, 100.0, 200.0],
            elevation_values=[10.0, float("nan"), 14.0],
        )
        assert result.is_valid is False

        # Inf in values
        result = validate_track(
            corners,
            length_m=1000.0,
            elevation_distances=[0.0, 100.0, 200.0],
            elevation_values=[10.0, math.inf, 14.0],
        )
        assert result.is_valid is False

    def test_elevation_grade_spike(self) -> None:
        """Grade > 40% between consecutive points is invalid."""
        corners = [OfficialCorner(1, "T1", 0.10)]
        # 50m rise over 100m run = 50% grade
        result = validate_track(
            corners,
            length_m=1000.0,
            elevation_distances=[0.0, 100.0, 200.0],
            elevation_values=[10.0, 60.0, 65.0],
        )
        assert result.is_valid is False
        assert any("grade spike" in i.message.lower() for i in result.issues)

    def test_elevation_grade_at_limit_ok(self) -> None:
        """Grade of exactly 40% should pass."""
        corners = [OfficialCorner(1, "T1", 0.10)]
        # 40m rise over 100m run = exactly 40%
        result = validate_track(
            corners,
            length_m=1000.0,
            elevation_distances=[0.0, 100.0, 200.0],
            elevation_values=[10.0, 50.0, 55.0],
        )
        # Should not have grade spike issues
        assert not any("grade spike" in i.message.lower() for i in result.issues)

    def test_valid_with_elevation(self) -> None:
        """Valid track with proper elevation data passes all checks."""
        corners = [
            OfficialCorner(1, "T1", 0.10, direction="left"),
            OfficialCorner(2, "T2", 0.50, direction="right"),
        ]
        result = validate_track(
            corners,
            length_m=3000.0,
            elevation_distances=[0.0, 500.0, 1000.0, 1500.0, 2000.0, 2500.0, 3000.0],
            elevation_values=[100.0, 105.0, 110.0, 108.0, 103.0, 100.0, 101.0],
        )
        assert result.is_valid is True
        assert len(result.issues) == 0

    def test_elevation_only_distances_provided(self) -> None:
        """Providing distances without values is an error."""
        corners = [OfficialCorner(1, "T1", 0.10)]
        result = validate_track(
            corners,
            length_m=1000.0,
            elevation_distances=[0.0, 100.0],
        )
        assert result.is_valid is False
        assert any("incomplete" in i.message.lower() for i in result.issues)

    def test_elevation_only_values_provided(self) -> None:
        """Providing values without distances is an error."""
        corners = [OfficialCorner(1, "T1", 0.10)]
        result = validate_track(
            corners,
            length_m=1000.0,
            elevation_values=[10.0, 12.0],
        )
        assert result.is_valid is False
        assert any("incomplete" in i.message.lower() for i in result.issues)

    def test_multiple_errors_accumulated(self) -> None:
        """Multiple correctness issues are all reported."""
        corners = [
            OfficialCorner(1, "T1", -0.05),  # Out of range
            OfficialCorner(2, "T2", 1.5),  # Out of range
        ]
        result = validate_track(corners, length_m=-100.0)
        assert result.is_valid is False
        # Should have fraction domain errors + non-monotonic + length error
        error_issues = [i for i in result.issues if i.severity == "error"]
        assert len(error_issues) >= 3

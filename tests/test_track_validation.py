"""Tests for automated track data validation."""

from __future__ import annotations

from cataclysm.track_db import OfficialCorner, TrackLayout
from cataclysm.track_validation import ValidationResult, validate_track


class TestValidateTrack:
    def test_fractions_monotonic_pass(self) -> None:
        layout = TrackLayout(
            name="Good",
            corners=[
                OfficialCorner(1, "T1", 0.10),
                OfficialCorner(2, "T2", 0.50),
            ],
            length_m=1000.0,
        )
        result = validate_track(layout)
        assert result.fraction_monotonic is True

    def test_fractions_non_monotonic_fail(self) -> None:
        layout = TrackLayout(
            name="Bad",
            corners=[
                OfficialCorner(1, "T1", 0.50),
                OfficialCorner(2, "T2", 0.10),
            ],
            length_m=1000.0,
        )
        result = validate_track(layout)
        assert result.fraction_monotonic is False
        assert len(result.errors) >= 1

    def test_fraction_spacing_too_close(self) -> None:
        layout = TrackLayout(
            name="Close",
            corners=[
                OfficialCorner(1, "T1", 0.10),
                OfficialCorner(2, "T2", 0.105),
            ],
            length_m=1000.0,
        )
        result = validate_track(layout)
        assert result.fraction_spacing is False

    def test_fraction_spacing_exactly_at_threshold(self) -> None:
        layout = TrackLayout(
            name="Threshold",
            corners=[
                OfficialCorner(1, "T1", 0.10),
                OfficialCorner(2, "T2", 0.11),
            ],
            length_m=1000.0,
        )
        result = validate_track(layout)
        assert result.fraction_spacing is True

    def test_direction_consistency(self) -> None:
        layout = TrackLayout(
            name="Consistent",
            corners=[
                OfficialCorner(1, "T1", 0.10, direction="left"),
                OfficialCorner(2, "T2", 0.50, direction="right"),
            ],
            length_m=1000.0,
        )
        result = validate_track(layout)
        assert result.all_directions_set is True

    def test_missing_directions_flagged(self) -> None:
        layout = TrackLayout(
            name="Missing",
            corners=[
                OfficialCorner(1, "T1", 0.10),
            ],
            length_m=1000.0,
        )
        result = validate_track(layout)
        assert result.all_directions_set is False

    def test_quality_score_fully_populated(self) -> None:
        layout = TrackLayout(
            name="Full",
            corners=[
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
            ],
            length_m=1000.0,
        )
        result = validate_track(layout)
        assert result.quality_score == 1.0

    def test_quality_score_partial(self) -> None:
        layout = TrackLayout(
            name="Partial",
            corners=[
                OfficialCorner(
                    1,
                    "T1",
                    0.10,
                    direction="left",
                    corner_type="hairpin",
                    coaching_notes="Brake hard.",
                    elevation_trend="downhill",
                ),
            ],
            length_m=1000.0,
        )
        result = validate_track(layout)
        assert result.quality_score > 0.5
        assert result.quality_score < 1.0

    def test_overall_valid(self) -> None:
        layout = TrackLayout(
            name="Good",
            corners=[
                OfficialCorner(1, "T1", 0.10, direction="left"),
                OfficialCorner(2, "T2", 0.50, direction="right"),
            ],
            length_m=1000.0,
        )
        result = validate_track(layout)
        assert result.is_valid is True

    def test_overall_invalid_when_non_monotonic(self) -> None:
        layout = TrackLayout(
            name="Bad",
            corners=[
                OfficialCorner(1, "T1", 0.50),
                OfficialCorner(2, "T2", 0.10),
            ],
            length_m=1000.0,
        )
        result = validate_track(layout)
        assert result.is_valid is False

    def test_empty_corners_valid(self) -> None:
        layout = TrackLayout(name="Empty", corners=[], length_m=1000.0)
        result = validate_track(layout)
        assert result.is_valid is True
        assert result.quality_score == 0.0

    def test_empty_corners_directions_and_notes_false(self) -> None:
        layout = TrackLayout(name="Empty", corners=[], length_m=1000.0)
        result = validate_track(layout)
        assert result.all_directions_set is False
        assert result.all_coaching_notes is False

    def test_quality_score_no_length(self) -> None:
        """length_m=None should reduce quality score."""
        layout = TrackLayout(
            name="NoLen",
            corners=[
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
            ],
        )
        result = validate_track(layout)
        # Missing length_m → should lose 0.10 weight
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
        assert r2.is_valid is False

"""Tests for corner type auto-classification from curvature metrics."""

from __future__ import annotations

from typing import Any

import pytest

from cataclysm.corner_classifier import (
    CornerClassification,
    classify_corner,
    classify_sequence,
)

# =====================================================================
# Single-corner classification
# =====================================================================


class TestClassifyCornerHairpin:
    """High curvature + large heading + short arc -> hairpin."""

    def test_classic_hairpin(self) -> None:
        result = classify_corner(
            peak_curvature=0.04,
            heading_change_deg=130.0,
            arc_length_m=30.0,
        )
        assert result.corner_type == "hairpin"
        assert result.confidence > 0.7

    def test_threshold_hairpin(self) -> None:
        """Exactly at hairpin curvature and heading thresholds."""
        result = classify_corner(
            peak_curvature=0.02,
            heading_change_deg=120.0,
            arc_length_m=40.0,
        )
        assert result.corner_type == "hairpin"
        assert result.confidence >= 0.5

    def test_high_curvature_short_arc_hairpin_even_without_120_deg_heading(self) -> None:
        result = classify_corner(
            peak_curvature=0.03,
            heading_change_deg=80.0,
            arc_length_m=35.0,
        )
        assert result.corner_type == "hairpin"

    def test_below_heading_threshold_not_hairpin(self) -> None:
        result = classify_corner(
            peak_curvature=0.01,
            heading_change_deg=119.9,
            arc_length_m=40.0,
        )
        assert result.corner_type != "hairpin"

    def test_hairpin_long_arc_becomes_sweeper(self) -> None:
        """Long arc should fail hairpin gating and resolve to sweeper geometry."""
        short = classify_corner(
            peak_curvature=0.035,
            heading_change_deg=130.0,
            arc_length_m=25.0,
        )
        long = classify_corner(
            peak_curvature=0.035,
            heading_change_deg=130.0,
            arc_length_m=120.0,
        )
        assert short.corner_type == "hairpin"
        assert long.corner_type == "sweeper"

    def test_barber_t5_wide_hairpin(self) -> None:
        """Barber T5-like geometry (wide but tight) should still be hairpin."""
        result = classify_corner(
            peak_curvature=0.030,
            heading_change_deg=100.0,
            arc_length_m=90.0,
        )
        assert result.corner_type == "hairpin"


class TestClassifyCornerSweeper:
    """Medium curvature + medium heading + medium arc -> sweeper."""

    def test_classic_sweeper(self) -> None:
        result = classify_corner(
            peak_curvature=0.012,
            heading_change_deg=45.0,
            arc_length_m=170.0,
        )
        assert result.corner_type == "sweeper"
        assert result.confidence > 0.5

    def test_sweeper_short_arc_fallback(self) -> None:
        """Near-threshold arc should use low-confidence sweeper fallback."""
        result = classify_corner(
            peak_curvature=0.010,
            heading_change_deg=40.0,
            arc_length_m=70.0,
        )
        assert result.corner_type == "sweeper"
        assert result.confidence < 0.6

    def test_sweeper_long_arc(self) -> None:
        """Very long arc still classified as sweeper."""
        result = classify_corner(
            peak_curvature=0.008,
            heading_change_deg=50.0,
            arc_length_m=250.0,
        )
        assert result.corner_type == "sweeper"

    def test_barber_t3_shorter_sweeper(self) -> None:
        """Barber T3-like geometry should classify as sweeper, not complex."""
        result = classify_corner(
            peak_curvature=0.009,
            heading_change_deg=45.0,
            arc_length_m=140.0,
        )
        assert result.corner_type == "sweeper"


class TestClassifyCornerKink:
    """Low curvature + small heading + short arc -> kink."""

    def test_classic_kink(self) -> None:
        result = classify_corner(
            peak_curvature=0.003,
            heading_change_deg=15.0,
            arc_length_m=20.0,
        )
        assert result.corner_type == "kink"
        assert result.confidence > 0.5

    def test_near_straight_kink(self) -> None:
        """Very slight curvature -> kink with high confidence."""
        result = classify_corner(
            peak_curvature=0.001,
            heading_change_deg=5.0,
            arc_length_m=15.0,
        )
        assert result.corner_type == "kink"
        assert result.confidence > 0.7

    def test_kink_speed_loss_below_threshold(self) -> None:
        result = classify_corner(
            peak_curvature=0.003,
            heading_change_deg=20.0,
            arc_length_m=20.0,
            speed_loss_pct=4.9,
        )
        assert result.corner_type == "kink"

    def test_kink_speed_loss_at_threshold_not_kink(self) -> None:
        result = classify_corner(
            peak_curvature=0.003,
            heading_change_deg=20.0,
            arc_length_m=20.0,
            speed_loss_pct=5.0,
        )
        assert result.corner_type != "kink"


class TestClassifyCornerCarousel:
    """Long, high-curvature arc with large heading -> carousel."""

    def test_classic_carousel(self) -> None:
        result = classify_corner(
            peak_curvature=0.025,
            heading_change_deg=180.0,
            arc_length_m=150.0,
        )
        assert result.corner_type == "carousel"
        assert result.confidence > 0.6

    def test_nurburgring_style_carousel(self) -> None:
        """Long sweeping corner like the Nurburgring Karussell."""
        result = classify_corner(
            peak_curvature=0.020,
            heading_change_deg=210.0,
            arc_length_m=200.0,
        )
        assert result.corner_type == "carousel"

    def test_carousel_beats_hairpin(self) -> None:
        """When arc length is long enough, carousel takes priority over hairpin."""
        result = classify_corner(
            peak_curvature=0.025,
            heading_change_deg=180.0,
            arc_length_m=120.0,
        )
        assert result.corner_type == "carousel"


class TestClassifyCornerComplex:
    """Mixed geometry that doesn't fit standard categories -> complex."""

    def test_high_curvature_low_heading_long_arc(self) -> None:
        """High curvature with low heading but long arc -> complex."""
        result = classify_corner(
            peak_curvature=0.025,
            heading_change_deg=20.0,
            arc_length_m=80.0,
        )
        assert result.corner_type == "complex"

    def test_low_curvature_high_heading(self) -> None:
        """Low curvature but high heading change -> complex."""
        result = classify_corner(
            peak_curvature=0.003,
            heading_change_deg=80.0,
            arc_length_m=40.0,
        )
        assert result.corner_type == "complex"


class TestClassifyCornerEdgeCases:
    """Edge cases: zero values, negative values, extreme values."""

    def test_zero_curvature_zero_heading(self) -> None:
        result = classify_corner(
            peak_curvature=0.0,
            heading_change_deg=0.0,
            arc_length_m=10.0,
        )
        assert result.corner_type == "kink"
        assert result.confidence <= 0.5

    def test_negative_curvature(self) -> None:
        """Negative curvature is treated as absolute value."""
        pos = classify_corner(
            peak_curvature=0.03,
            heading_change_deg=130.0,
            arc_length_m=30.0,
        )
        neg = classify_corner(
            peak_curvature=-0.03,
            heading_change_deg=130.0,
            arc_length_m=30.0,
        )
        assert pos.corner_type == neg.corner_type
        assert pos.confidence == pytest.approx(neg.confidence, abs=0.01)

    def test_negative_heading(self) -> None:
        """Negative heading change is treated as absolute value."""
        result = classify_corner(
            peak_curvature=0.03,
            heading_change_deg=-130.0,
            arc_length_m=30.0,
        )
        assert result.corner_type == "hairpin"

    def test_negative_arc_length(self) -> None:
        """Negative arc length is treated as absolute value."""
        result = classify_corner(
            peak_curvature=0.03,
            heading_change_deg=130.0,
            arc_length_m=-30.0,
        )
        assert result.corner_type == "hairpin"

    def test_very_large_curvature(self) -> None:
        """Extremely tight corner."""
        result = classify_corner(
            peak_curvature=0.1,
            heading_change_deg=180.0,
            arc_length_m=20.0,
        )
        assert result.corner_type == "hairpin"
        assert result.confidence > 0.7

    def test_very_large_arc(self) -> None:
        """Very long corner arc."""
        result = classify_corner(
            peak_curvature=0.018,
            heading_change_deg=200.0,
            arc_length_m=500.0,
        )
        assert result.corner_type == "carousel"


class TestConfidenceBounds:
    """All confidence values must be in [0.0, 1.0]."""

    @pytest.mark.parametrize(
        ("curv", "heading", "arc"),
        [
            (0.0, 0.0, 0.0),
            (0.001, 5.0, 10.0),
            (0.01, 45.0, 100.0),
            (0.04, 120.0, 30.0),
            (0.025, 200.0, 300.0),
            (0.1, 360.0, 10.0),
        ],
    )
    def test_confidence_clamped(self, curv: float, heading: float, arc: float) -> None:
        result = classify_corner(
            peak_curvature=curv,
            heading_change_deg=heading,
            arc_length_m=arc,
        )
        assert 0.0 <= result.confidence <= 1.0


# =====================================================================
# Sequence classification (chicane, esses)
# =====================================================================


def _make_corner(
    *,
    peak_curvature: float = 0.01,
    heading_change_deg: float = 45.0,
    arc_length_m: float = 40.0,
    direction: str = "left",
    apex_distance_m: float = 100.0,
    entry_distance_m: float = 80.0,
    exit_distance_m: float = 120.0,
) -> dict[str, Any]:
    return {
        "peak_curvature": peak_curvature,
        "heading_change_deg": heading_change_deg,
        "arc_length_m": arc_length_m,
        "direction": direction,
        "apex_distance_m": apex_distance_m,
        "entry_distance_m": entry_distance_m,
        "exit_distance_m": exit_distance_m,
    }


class TestChicaneDetection:
    """Two close opposite-direction corners -> chicane."""

    def test_classic_chicane(self) -> None:
        corners = [
            _make_corner(
                direction="left",
                entry_distance_m=100.0,
                exit_distance_m=140.0,
            ),
            _make_corner(
                direction="right",
                entry_distance_m=170.0,
                exit_distance_m=210.0,
            ),
        ]
        results = classify_sequence(corners)
        assert len(results) == 2
        assert results[0].corner_type == "chicane"
        assert results[1].corner_type == "chicane"

    def test_chicane_closer_gap_higher_confidence(self) -> None:
        close = classify_sequence(
            [
                _make_corner(direction="left", exit_distance_m=100.0),
                _make_corner(direction="right", entry_distance_m=110.0),
            ]
        )
        far = classify_sequence(
            [
                _make_corner(direction="left", exit_distance_m=100.0),
                _make_corner(direction="right", entry_distance_m=170.0),
            ]
        )
        assert close[0].confidence > far[0].confidence

    def test_same_direction_not_chicane(self) -> None:
        """Two corners in the same direction -> not a chicane."""
        corners = [
            _make_corner(direction="left", exit_distance_m=100.0),
            _make_corner(direction="left", entry_distance_m=130.0),
        ]
        results = classify_sequence(corners)
        assert results[0].corner_type != "chicane"
        assert results[1].corner_type != "chicane"

    def test_too_far_apart_not_chicane(self) -> None:
        """Opposite direction but gap > 80m -> not a chicane."""
        corners = [
            _make_corner(direction="left", exit_distance_m=100.0),
            _make_corner(direction="right", entry_distance_m=200.0),
        ]
        results = classify_sequence(corners)
        assert results[0].corner_type != "chicane"
        assert results[1].corner_type != "chicane"


class TestEssesDetection:
    """3+ alternating close corners -> esses."""

    def test_three_corner_esses(self) -> None:
        corners = [
            _make_corner(direction="left", exit_distance_m=100.0),
            _make_corner(direction="right", entry_distance_m=130.0, exit_distance_m=170.0),
            _make_corner(direction="left", entry_distance_m=200.0),
        ]
        results = classify_sequence(corners)
        assert all(r.corner_type == "esses" for r in results)

    def test_four_corner_esses(self) -> None:
        corners = [
            _make_corner(direction="left", exit_distance_m=100.0),
            _make_corner(direction="right", entry_distance_m=120.0, exit_distance_m=160.0),
            _make_corner(direction="left", entry_distance_m=180.0, exit_distance_m=220.0),
            _make_corner(direction="right", entry_distance_m=240.0),
        ]
        results = classify_sequence(corners)
        assert all(r.corner_type == "esses" for r in results)

    def test_esses_confidence_increases_with_length(self) -> None:
        three = classify_sequence(
            [
                _make_corner(direction="left", exit_distance_m=100.0),
                _make_corner(direction="right", entry_distance_m=120.0, exit_distance_m=160.0),
                _make_corner(direction="left", entry_distance_m=180.0),
            ]
        )
        five = classify_sequence(
            [
                _make_corner(direction="left", exit_distance_m=100.0),
                _make_corner(direction="right", entry_distance_m=120.0, exit_distance_m=160.0),
                _make_corner(direction="left", entry_distance_m=180.0, exit_distance_m=220.0),
                _make_corner(direction="right", entry_distance_m=240.0, exit_distance_m=280.0),
                _make_corner(direction="left", entry_distance_m=300.0),
            ]
        )
        assert five[0].confidence > three[0].confidence

    def test_broken_alternation_not_esses(self) -> None:
        """Same direction in the middle breaks the esses pattern."""
        corners = [
            _make_corner(direction="left", exit_distance_m=100.0),
            _make_corner(direction="right", entry_distance_m=120.0, exit_distance_m=160.0),
            _make_corner(direction="right", entry_distance_m=180.0, exit_distance_m=220.0),
            _make_corner(direction="left", entry_distance_m=240.0),
        ]
        results = classify_sequence(corners)
        # First two are chicane (opposite + close), 3rd and 4th are chicane too
        assert results[0].corner_type != "esses"


class TestSequenceEdgeCases:
    """Edge cases for sequence classification."""

    def test_empty_list(self) -> None:
        assert classify_sequence([]) == []

    def test_single_corner(self) -> None:
        results = classify_sequence(
            [
                _make_corner(peak_curvature=0.03, heading_change_deg=120.0),
            ]
        )
        assert len(results) == 1
        assert results[0].corner_type == "hairpin"

    def test_none_direction_not_sequence(self) -> None:
        """Corners with None direction cannot form chicane/esses."""
        corners = [
            _make_corner(direction="left", exit_distance_m=100.0),
            {
                "peak_curvature": 0.01,
                "heading_change_deg": 45.0,
                "arc_length_m": 40.0,
                "direction": None,
                "apex_distance_m": 160.0,
                "entry_distance_m": 130.0,
                "exit_distance_m": 170.0,
            },
        ]
        results = classify_sequence(corners)
        assert results[0].corner_type != "chicane"
        assert results[1].corner_type != "chicane"

    def test_mixed_isolated_and_sequence(self) -> None:
        """Some corners form a chicane, others are isolated."""
        corners = [
            _make_corner(
                peak_curvature=0.003,
                heading_change_deg=10.0,
                direction="left",
                entry_distance_m=50.0,
                exit_distance_m=70.0,
            ),
            # Gap > 80m -> isolated
            _make_corner(
                direction="left",
                entry_distance_m=200.0,
                exit_distance_m=240.0,
            ),
            _make_corner(
                direction="right",
                entry_distance_m=270.0,
                exit_distance_m=310.0,
            ),
        ]
        results = classify_sequence(corners)
        assert results[0].corner_type == "kink"  # isolated
        assert results[1].corner_type == "chicane"
        assert results[2].corner_type == "chicane"

    def test_classification_dataclass_fields(self) -> None:
        """Verify CornerClassification has the expected fields."""
        c = CornerClassification(corner_type="hairpin", confidence=0.9, reasoning="test")
        assert c.corner_type == "hairpin"
        assert c.confidence == 0.9
        assert c.reasoning == "test"

    def test_missing_keys_default_to_zero(self) -> None:
        """Missing dict keys should not crash, defaulting to 0."""
        results = classify_sequence(
            [
                {"direction": "left", "exit_distance_m": 100.0},
                {"direction": "right", "entry_distance_m": 120.0},
            ]
        )
        assert len(results) == 2
        # Both have zero curvature/heading -> kink-like, but close+opposite -> chicane
        assert results[0].corner_type == "chicane"

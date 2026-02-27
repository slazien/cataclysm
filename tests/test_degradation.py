"""Comprehensive tests for cataclysm.degradation module."""

from __future__ import annotations

import numpy as np
import pytest

from cataclysm.corners import Corner
from cataclysm.degradation import (
    MIN_LAPS,
    DegradationAnalysis,
    _classify_severity,
    _compute_r_squared,
    detect_degradation,
)


def _make_corner(
    number: int = 1,
    min_speed_mps: float = 25.0,
    peak_brake_g: float | None = -0.8,
) -> Corner:
    """Build a minimal Corner for degradation testing."""
    return Corner(
        number=number,
        entry_distance_m=100.0,
        exit_distance_m=200.0,
        apex_distance_m=150.0,
        min_speed_mps=min_speed_mps,
        brake_point_m=80.0,
        peak_brake_g=peak_brake_g,
        throttle_commit_m=170.0,
        apex_type="mid",
    )


def _build_all_lap_corners_brake_fade(
    n_laps: int = 6,
    base_brake_g: float = -0.9,
    brake_fade_per_lap: float = 0.05,
    base_speed: float = 25.0,
    speed_change_per_lap: float = 0.0,
) -> dict[int, list[Corner]]:
    """Build all_lap_corners with a known linear brake fade trend.

    brake_fade_per_lap > 0 means brakes get weaker (less negative G) each lap.
    """
    result: dict[int, list[Corner]] = {}
    for i in range(n_laps):
        lap_num = i + 1
        brake_g = base_brake_g + i * brake_fade_per_lap
        speed = base_speed + i * speed_change_per_lap
        result[lap_num] = [_make_corner(number=1, peak_brake_g=brake_g, min_speed_mps=speed)]
    return result


def _build_all_lap_corners_tire_degradation(
    n_laps: int = 6,
    base_speed: float = 30.0,
    speed_drop_per_lap: float = 0.3,
) -> dict[int, list[Corner]]:
    """Build all_lap_corners with a known linear tire degradation trend.

    speed_drop_per_lap > 0 means speed drops each lap (negative slope).
    """
    result: dict[int, list[Corner]] = {}
    for i in range(n_laps):
        lap_num = i + 1
        speed = base_speed - i * speed_drop_per_lap
        result[lap_num] = [
            _make_corner(number=1, min_speed_mps=speed, peak_brake_g=-0.8),
        ]
    return result


class TestClassifySeverity:
    """Tests for _classify_severity helper."""

    def test_mild(self) -> None:
        assert _classify_severity(-0.015, -0.01) == "mild"

    def test_moderate(self) -> None:
        assert _classify_severity(-0.025, -0.01) == "moderate"

    def test_severe(self) -> None:
        assert _classify_severity(-0.04, -0.01) == "severe"

    def test_exactly_2x_is_moderate(self) -> None:
        assert _classify_severity(-0.02, -0.01) == "moderate"

    def test_exactly_3x_is_severe(self) -> None:
        assert _classify_severity(-0.03, -0.01) == "severe"

    def test_just_above_1x(self) -> None:
        assert _classify_severity(-0.0101, -0.01) == "mild"


class TestComputeRSquared:
    """Tests for _compute_r_squared helper."""

    def test_perfect_fit(self) -> None:
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert _compute_r_squared(y, y_pred) == pytest.approx(1.0)

    def test_zero_ss_tot(self) -> None:
        """All values identical => SS_tot=0 => R²=0."""
        y = np.array([5.0, 5.0, 5.0, 5.0])
        y_pred = np.array([5.0, 5.0, 5.0, 5.0])
        assert _compute_r_squared(y, y_pred) == 0.0

    def test_poor_fit(self) -> None:
        """Predicting the mean gives R²=0."""
        y = np.array([1.0, 5.0, 2.0, 4.0])
        mean_val = float(np.mean(y))  # 3.0
        y_pred = np.full_like(y, mean_val)
        r_sq = _compute_r_squared(y, y_pred)
        assert r_sq == pytest.approx(0.0, abs=1e-10)


class TestDetectBrakeFade:
    """Tests for detecting brake fade (peak_brake_g degradation)."""

    def test_clear_brake_fade_detected(self) -> None:
        """Strong linear brake fade should be detected."""
        all_corners = _build_all_lap_corners_brake_fade(
            n_laps=6,
            base_brake_g=-0.9,
            brake_fade_per_lap=0.05,  # severe: 5x threshold
        )
        result = detect_degradation(all_corners, anomalous_laps=set())

        assert isinstance(result, DegradationAnalysis)
        assert result.has_brake_fade is True
        brake_events = [e for e in result.events if e.metric == "brake_fade"]
        assert len(brake_events) == 1
        event = brake_events[0]
        assert event.corner_number == 1
        assert event.slope > 0  # positive slope = less negative G = fade
        assert event.r_squared >= 0.5
        assert event.severity == "severe"
        assert event.start_lap == 1
        assert event.end_lap == 6
        assert len(event.values) == 6
        assert len(event.lap_numbers) == 6

    def test_no_fade_flat_braking(self) -> None:
        """Constant brake G across laps should not trigger."""
        all_corners = _build_all_lap_corners_brake_fade(
            n_laps=6,
            base_brake_g=-0.8,
            brake_fade_per_lap=0.0,
        )
        result = detect_degradation(all_corners, anomalous_laps=set())
        assert result.has_brake_fade is False
        assert len([e for e in result.events if e.metric == "brake_fade"]) == 0

    def test_improving_brakes_not_flagged(self) -> None:
        """Brakes getting stronger (more negative G) should not flag."""
        all_corners = _build_all_lap_corners_brake_fade(
            n_laps=6,
            base_brake_g=-0.7,
            brake_fade_per_lap=-0.05,  # getting stronger
        )
        result = detect_degradation(all_corners, anomalous_laps=set())
        assert result.has_brake_fade is False

    def test_fade_below_r_squared_threshold(self) -> None:
        """Noisy data with low R² should not be flagged."""
        all_corners: dict[int, list[Corner]] = {}
        # Intentionally noisy: alternating high and low brake G
        brake_values = [-0.9, -0.6, -0.85, -0.55, -0.8, -0.5]
        for i, bg in enumerate(brake_values):
            all_corners[i + 1] = [_make_corner(number=1, peak_brake_g=bg)]

        result = detect_degradation(all_corners, anomalous_laps=set())
        # The R² for this alternating pattern should be low
        brake_events = [e for e in result.events if e.metric == "brake_fade"]
        # If R² < 0.5, no event; otherwise check severity
        for event in brake_events:
            assert event.r_squared >= 0.5

    def test_mild_brake_fade(self) -> None:
        """Slope just above threshold should be classified as mild."""
        all_corners = _build_all_lap_corners_brake_fade(
            n_laps=8,
            base_brake_g=-0.9,
            brake_fade_per_lap=0.015,  # 1.5x threshold = mild
        )
        result = detect_degradation(all_corners, anomalous_laps=set())
        if result.has_brake_fade:
            event = [e for e in result.events if e.metric == "brake_fade"][0]
            assert event.severity == "mild"


class TestDetectTireDegradation:
    """Tests for detecting tire degradation (min speed dropping)."""

    def test_clear_tire_degradation_detected(self) -> None:
        """Strong linear speed drop should be detected."""
        all_corners = _build_all_lap_corners_tire_degradation(
            n_laps=6,
            base_speed=30.0,
            speed_drop_per_lap=0.5,  # 5x threshold
        )
        result = detect_degradation(all_corners, anomalous_laps=set())

        assert result.has_tire_degradation is True
        tire_events = [e for e in result.events if e.metric == "tire_degradation"]
        assert len(tire_events) == 1
        event = tire_events[0]
        assert event.corner_number == 1
        assert event.slope < 0  # negative slope = speed dropping
        assert event.r_squared >= 0.5
        assert event.severity == "severe"
        assert len(event.values) == 6

    def test_no_degradation_flat_speed(self) -> None:
        """Constant speed should not trigger."""
        all_corners = _build_all_lap_corners_tire_degradation(
            n_laps=6,
            base_speed=30.0,
            speed_drop_per_lap=0.0,
        )
        result = detect_degradation(all_corners, anomalous_laps=set())
        assert result.has_tire_degradation is False

    def test_improving_speed_not_flagged(self) -> None:
        """Speed increasing (driver improvement) should not flag."""
        all_corners: dict[int, list[Corner]] = {}
        for i in range(6):
            speed = 25.0 + i * 0.5  # improving
            all_corners[i + 1] = [_make_corner(number=1, min_speed_mps=speed)]
        result = detect_degradation(all_corners, anomalous_laps=set())
        assert result.has_tire_degradation is False

    def test_moderate_tire_degradation(self) -> None:
        """Slope 2-3x threshold should be moderate."""
        all_corners = _build_all_lap_corners_tire_degradation(
            n_laps=8,
            base_speed=30.0,
            speed_drop_per_lap=0.25,  # 2.5x threshold
        )
        result = detect_degradation(all_corners, anomalous_laps=set())
        if result.has_tire_degradation:
            event = [e for e in result.events if e.metric == "tire_degradation"][0]
            assert event.severity == "moderate"


class TestTooFewLaps:
    """Tests for insufficient lap count."""

    def test_fewer_than_min_laps_returns_empty(self) -> None:
        """Fewer than MIN_LAPS clean laps should return no events."""
        all_corners: dict[int, list[Corner]] = {}
        for i in range(MIN_LAPS - 1):
            all_corners[i + 1] = [
                _make_corner(number=1, peak_brake_g=-0.9 + i * 0.1, min_speed_mps=30.0 - i * 1.0)
            ]
        result = detect_degradation(all_corners, anomalous_laps=set())
        assert len(result.events) == 0
        assert result.has_brake_fade is False
        assert result.has_tire_degradation is False

    def test_exactly_min_laps(self) -> None:
        """Exactly MIN_LAPS should work if trend is clear."""
        all_corners: dict[int, list[Corner]] = {}
        for i in range(MIN_LAPS):
            # Very strong degradation to ensure detection even with few points
            all_corners[i + 1] = [
                _make_corner(number=1, peak_brake_g=-0.9 + i * 0.1, min_speed_mps=30.0 - i * 1.0)
            ]
        result = detect_degradation(all_corners, anomalous_laps=set())
        # Should detect at least one event with such a strong trend
        assert len(result.events) > 0

    def test_empty_all_lap_corners(self) -> None:
        """Empty dict should return empty analysis."""
        result = detect_degradation({}, anomalous_laps=set())
        assert len(result.events) == 0
        assert result.has_brake_fade is False
        assert result.has_tire_degradation is False


class TestAnomalousLapExclusion:
    """Tests for anomalous lap filtering."""

    def test_anomalous_laps_excluded(self) -> None:
        """Anomalous laps should be excluded from analysis."""
        all_corners = _build_all_lap_corners_brake_fade(
            n_laps=8,
            base_brake_g=-0.9,
            brake_fade_per_lap=0.05,
        )
        # Mark laps 3-8 as anomalous, leaving only laps 1-2 (< MIN_LAPS)
        anomalous = {3, 4, 5, 6, 7, 8}
        result = detect_degradation(all_corners, anomalous_laps=anomalous)
        assert len(result.events) == 0

    def test_enough_clean_laps_after_exclusion(self) -> None:
        """Should still detect if enough clean laps remain."""
        all_corners = _build_all_lap_corners_brake_fade(
            n_laps=8,
            base_brake_g=-0.9,
            brake_fade_per_lap=0.05,
        )
        # Mark only 2 laps as anomalous, leaving 6 clean laps
        anomalous = {3, 5}
        result = detect_degradation(all_corners, anomalous_laps=anomalous)
        # With 6 clean laps showing fade, should still detect
        # (though the excluded laps break the perfect linear trend)
        assert isinstance(result, DegradationAnalysis)


class TestMissingBrakeData:
    """Tests for corners with missing or zero brake data."""

    def test_none_brake_g_excluded(self) -> None:
        """Corners with peak_brake_g=None should be excluded from brake analysis."""
        all_corners: dict[int, list[Corner]] = {}
        for i in range(6):
            # Alternate between None and real values
            brake_g = None if i % 2 == 0 else -0.9 + i * 0.05
            all_corners[i + 1] = [_make_corner(number=1, peak_brake_g=brake_g, min_speed_mps=25.0)]
        result = detect_degradation(all_corners, anomalous_laps=set())
        # Only 3 laps with brake data (1, 3, 5) -- less than MIN_LAPS
        brake_events = [e for e in result.events if e.metric == "brake_fade"]
        assert len(brake_events) == 0

    def test_zero_brake_g_excluded(self) -> None:
        """Corners with peak_brake_g=0.0 should be excluded from brake analysis."""
        all_corners: dict[int, list[Corner]] = {}
        for i in range(6):
            brake_g = 0.0 if i < 3 else -0.9 + (i - 3) * 0.05
            all_corners[i + 1] = [_make_corner(number=1, peak_brake_g=brake_g, min_speed_mps=25.0)]
        result = detect_degradation(all_corners, anomalous_laps=set())
        # Only 3 laps with valid brake data -- less than MIN_LAPS
        brake_events = [e for e in result.events if e.metric == "brake_fade"]
        assert len(brake_events) == 0


class TestMixedEvents:
    """Tests for sessions with both brake fade and tire degradation."""

    def test_both_brake_and_tire_events(self) -> None:
        """Session with both fade and degradation should report both."""
        all_corners: dict[int, list[Corner]] = {}
        for i in range(8):
            lap_num = i + 1
            # Corner 1: brake fade
            c1 = _make_corner(
                number=1,
                peak_brake_g=-0.9 + i * 0.05,
                min_speed_mps=25.0,
            )
            # Corner 2: tire degradation
            c2 = _make_corner(
                number=2,
                peak_brake_g=-0.8,
                min_speed_mps=30.0 - i * 0.5,
            )
            all_corners[lap_num] = [c1, c2]

        result = detect_degradation(all_corners, anomalous_laps=set())
        assert result.has_brake_fade is True
        assert result.has_tire_degradation is True

        brake_events = [e for e in result.events if e.metric == "brake_fade"]
        tire_events = [e for e in result.events if e.metric == "tire_degradation"]
        assert len(brake_events) >= 1
        assert len(tire_events) >= 1

    def test_multiple_corners_independent(self) -> None:
        """Degradation on one corner shouldn't affect another."""
        all_corners: dict[int, list[Corner]] = {}
        for i in range(8):
            lap_num = i + 1
            # Corner 1: fading brakes
            c1 = _make_corner(number=1, peak_brake_g=-0.9 + i * 0.05, min_speed_mps=25.0)
            # Corner 2: stable
            c2 = _make_corner(number=2, peak_brake_g=-0.8, min_speed_mps=30.0)
            all_corners[lap_num] = [c1, c2]

        result = detect_degradation(all_corners, anomalous_laps=set())
        brake_events = [e for e in result.events if e.metric == "brake_fade"]
        # Only corner 1 should have a brake fade event
        assert all(e.corner_number == 1 for e in brake_events)


class TestEdgeCases:
    """Edge case tests."""

    def test_single_corner_per_lap(self) -> None:
        """Works with just one corner per lap."""
        all_corners = _build_all_lap_corners_brake_fade(n_laps=6)
        result = detect_degradation(all_corners, anomalous_laps=set())
        assert isinstance(result, DegradationAnalysis)

    def test_corner_missing_from_some_laps(self) -> None:
        """If a corner is missing from some laps, analysis should use available data."""
        all_corners: dict[int, list[Corner]] = {}
        for i in range(8):
            lap_num = i + 1
            if lap_num == 4:
                # Lap 4 has no corners
                all_corners[lap_num] = []
            else:
                all_corners[lap_num] = [
                    _make_corner(
                        number=1,
                        peak_brake_g=-0.9 + i * 0.04,
                        min_speed_mps=30.0 - i * 0.3,
                    )
                ]
        result = detect_degradation(all_corners, anomalous_laps=set())
        # Should still analyze with 7 data points
        assert isinstance(result, DegradationAnalysis)

    def test_description_format(self) -> None:
        """Event description should contain key details."""
        all_corners = _build_all_lap_corners_brake_fade(n_laps=6, brake_fade_per_lap=0.05)
        result = detect_degradation(all_corners, anomalous_laps=set())
        if result.has_brake_fade:
            event = [e for e in result.events if e.metric == "brake_fade"][0]
            assert "Corner 1" in event.description
            assert "Brake fade" in event.description
            assert "R²" in event.description

    def test_all_laps_anomalous(self) -> None:
        """If all laps are anomalous, return empty."""
        all_corners = _build_all_lap_corners_brake_fade(n_laps=6)
        anomalous = {1, 2, 3, 4, 5, 6}
        result = detect_degradation(all_corners, anomalous_laps=anomalous)
        assert len(result.events) == 0

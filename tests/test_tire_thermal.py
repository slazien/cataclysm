"""Tests for cataclysm.tire_thermal."""

from __future__ import annotations

import pytest

from cataclysm.equipment import TireCompoundCategory
from cataclysm.tire_thermal import (
    COMPOUND_THERMAL_PARAMS,
    TireThermalParams,
    detect_grip_degradation,
    grip_fraction_at_lap,
)


class TestGripFractionAtLap:
    """Tests for the grip fraction model."""

    def test_first_lap_below_peak(self) -> None:
        """First lap should have reduced grip (cold tires)."""
        for compound in TireCompoundCategory:
            grip = grip_fraction_at_lap(1, compound)
            assert grip < 1.0, f"{compound}: first lap should be below peak"
            assert grip > 0.5, f"{compound}: first lap shouldn't be below 0.5"

    def test_peak_grip_near_one(self) -> None:
        """After warmup, grip should be near 1.0."""
        for compound in TireCompoundCategory:
            params = COMPOUND_THERMAL_PARAMS[compound]
            peak_lap = int(params.warmup_laps * 3) + 1  # well past warmup
            if peak_lap > params.optimal_window_laps:
                peak_lap = max(2, int(params.optimal_window_laps))
            grip = grip_fraction_at_lap(peak_lap, compound)
            assert grip > 0.95, f"{compound} at lap {peak_lap}: expected >0.95, got {grip:.3f}"

    def test_late_lap_degradation(self) -> None:
        """Very late laps should show reduced grip for aggressive compounds."""
        # Slick tires after 20 laps should be well past optimal
        grip = grip_fraction_at_lap(20, TireCompoundCategory.SLICK)
        assert grip < 0.90, f"Slick at lap 20 should be degraded, got {grip:.3f}"

    def test_grip_never_below_minimum(self) -> None:
        """Grip should never drop below min_grip_fraction."""
        for compound in TireCompoundCategory:
            params = COMPOUND_THERMAL_PARAMS[compound]
            grip = grip_fraction_at_lap(100, compound)
            assert grip >= params.min_grip_fraction - 0.001

    def test_street_more_durable_than_slick(self) -> None:
        """Street tires should maintain grip longer than slicks."""
        street_20 = grip_fraction_at_lap(20, TireCompoundCategory.STREET)
        slick_20 = grip_fraction_at_lap(20, TireCompoundCategory.SLICK)
        assert street_20 > slick_20

    def test_monotonic_during_warmup(self) -> None:
        """Grip should increase during warmup phase."""
        compound = TireCompoundCategory.R_COMPOUND
        prev = 0.0
        for lap in range(1, 5):
            grip = grip_fraction_at_lap(lap, compound)
            assert grip >= prev, f"Grip should increase during warmup: lap {lap}"
            prev = grip

    def test_custom_params(self) -> None:
        """Custom params should override compound defaults."""
        custom = TireThermalParams(
            warmup_laps=0.1,
            optimal_window_laps=2.0,
            degradation_per_lap=0.10,
            min_grip_fraction=0.50,
        )
        # After warmup, lap 1 should be near peak
        grip_1 = grip_fraction_at_lap(1, TireCompoundCategory.STREET, params=custom)
        assert grip_1 > 0.95

        # At lap 12 (10 laps past optimal), should be at floor
        grip_12 = grip_fraction_at_lap(12, TireCompoundCategory.STREET, params=custom)
        assert grip_12 == pytest.approx(0.50, abs=0.01)


class TestDetectGripDegradation:
    """Tests for the degradation detection coaching feature."""

    def test_not_enough_laps(self) -> None:
        """Fewer than 4 laps should return no degradation."""
        result = detect_grip_degradation([90, 89, 88], TireCompoundCategory.STREET)
        assert result["degradation_detected"] is False
        assert "Not enough" in result["coaching_note"]

    def test_consistent_laps_no_degradation(self) -> None:
        """Consistent lap times should show no degradation."""
        laps = [90.0, 89.5, 89.2, 89.3, 89.4, 89.2, 89.5, 89.3]
        result = detect_grip_degradation(laps, TireCompoundCategory.ENDURANCE_200TW)
        assert result["degradation_detected"] is False

    def test_obvious_degradation_detected(self) -> None:
        """Clear degradation pattern should be detected."""
        # Fast early, then increasingly slow
        laps = [89.0, 88.5, 88.2, 88.3, 89.0, 90.0, 91.5, 93.0, 95.0]
        result = detect_grip_degradation(laps, TireCompoundCategory.SLICK)
        assert result["degradation_detected"] is True
        assert result["onset_lap"] is not None

    def test_returns_expected_rate(self) -> None:
        """Expected rate should match compound parameters."""
        result = detect_grip_degradation(
            [90, 89, 89, 89, 90],
            TireCompoundCategory.R_COMPOUND,
        )
        assert result["expected_rate_pct"] == 1.5  # 0.015 * 100

    def test_coaching_note_present(self) -> None:
        """Should always return a coaching note."""
        result = detect_grip_degradation(
            [90, 89, 89, 89, 90, 91, 92, 93],
            TireCompoundCategory.ENDURANCE_200TW,
        )
        assert isinstance(result["coaching_note"], str)
        assert len(result["coaching_note"]) > 10

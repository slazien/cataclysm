"""Tests for session-level grip evolution model."""

from __future__ import annotations

import pytest

from cataclysm.grip_evolution import compute_grip_factor


class TestComputeGripFactor:
    def test_lap1_below_one_endurance(self) -> None:
        """Lap 1 grip should be below 1.0 for endurance_200tw."""
        factor = compute_grip_factor(1, "endurance_200tw")
        assert factor < 1.0

    def test_saturation_returns_one(self) -> None:
        """After enough laps, grip saturates to 1.0."""
        assert compute_grip_factor(20, "endurance_200tw") == 1.0

    def test_lap_zero_raises(self) -> None:
        """Lap 0 is invalid and should raise ValueError."""
        with pytest.raises(ValueError, match="lap_number must be >= 1"):
            compute_grip_factor(0, "street")

    def test_street_starts_lower_than_slick(self) -> None:
        """Street tires deposit more rubber, so lap 1 deficit is larger."""
        street_1 = compute_grip_factor(1, "street")
        slick_1 = compute_grip_factor(1, "slick")
        assert street_1 < slick_1

    def test_monotonic_increase(self) -> None:
        """Grip factor must be non-decreasing across laps."""
        for compound in ("street", "endurance_200tw", "100tw", "slick"):
            prev = 0.0
            for lap in range(1, 25):
                current = compute_grip_factor(lap, compound)
                assert current >= prev, f"{compound} lap {lap}: {current} < {prev}"
                prev = current

    def test_unknown_compound_uses_default(self) -> None:
        """Unknown compound should fall back to default parameters."""
        factor = compute_grip_factor(1, "unknown_compound")
        # Default is (0.05, 4), same as endurance_200tw
        expected = compute_grip_factor(1, "endurance_200tw")
        assert factor == expected

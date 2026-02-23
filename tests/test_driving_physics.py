"""Tests for cataclysm.driving_physics constants."""

from __future__ import annotations

from cataclysm.driving_physics import (
    COACHING_SYSTEM_PROMPT,
    DRIVING_PHYSICS_REFERENCE,
    PHYSICS_GUARDRAILS,
)


class TestDrivingPhysicsReference:
    def test_contains_traction_circle(self) -> None:
        assert "traction circle" in DRIVING_PHYSICS_REFERENCE.lower()

    def test_contains_trail_braking(self) -> None:
        assert "trail braking" in DRIVING_PHYSICS_REFERENCE.lower()

    def test_contains_weight_transfer(self) -> None:
        assert "weight" in DRIVING_PHYSICS_REFERENCE.lower()
        assert "load transfer" in DRIVING_PHYSICS_REFERENCE.lower()


class TestPhysicsGuardrails:
    def test_early_turnin_late_apex_rule(self) -> None:
        assert "early turn-in" in PHYSICS_GUARDRAILS.lower()
        assert "late apex" in PHYSICS_GUARDRAILS.lower()

    def test_liftoff_oversteer_warning(self) -> None:
        assert "snap oversteer" in PHYSICS_GUARDRAILS.lower()


class TestCoachingSystemPrompt:
    def test_combines_reference_and_guardrails(self) -> None:
        assert DRIVING_PHYSICS_REFERENCE in COACHING_SYSTEM_PROMPT
        assert PHYSICS_GUARDRAILS in COACHING_SYSTEM_PROMPT

    def test_includes_role_preamble(self) -> None:
        assert "expert motorsport driving coach" in COACHING_SYSTEM_PROMPT

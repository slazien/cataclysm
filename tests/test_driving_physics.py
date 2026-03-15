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

    def test_data_honesty_forbidden_composites(self) -> None:
        lower = PHYSICS_GUARDRAILS.lower()
        assert "x mph of grip" in lower
        assert "x g of speed" in lower


class TestCoachingSystemPrompt:
    def test_combines_reference_and_guardrails(self) -> None:
        assert DRIVING_PHYSICS_REFERENCE in COACHING_SYSTEM_PROMPT
        assert PHYSICS_GUARDRAILS in COACHING_SYSTEM_PROMPT

    def test_includes_role_preamble(self) -> None:
        assert "elite motorsport driving coach" in COACHING_SYSTEM_PROMPT

    def test_five_step_pattern_reasoning(self) -> None:
        prompt_lower = COACHING_SYSTEM_PROMPT.lower()
        assert "observation" in prompt_lower
        assert "mechanism" in prompt_lower
        assert "root cause" in prompt_lower
        assert "time impact" in prompt_lower
        assert "fix" in prompt_lower
        assert "five-step" in prompt_lower

    def test_ois_format_required(self) -> None:
        assert "OIS Format" in COACHING_SYSTEM_PROMPT
        assert "Observation" in COACHING_SYSTEM_PROMPT

    def test_because_clause_required(self) -> None:
        assert '"Because" Clause' in COACHING_SYSTEM_PROMPT

    def test_external_focus_required(self) -> None:
        assert "external focus" in COACHING_SYSTEM_PROMPT.lower()

    def test_golden_example_present(self) -> None:
        assert "Golden Example" in COACHING_SYSTEM_PROMPT
        assert "primary_focus" in COACHING_SYSTEM_PROMPT

    def test_anti_example_present(self) -> None:
        assert "Anti-Example" in COACHING_SYSTEM_PROMPT
        assert "_WRONG" in COACHING_SYSTEM_PROMPT

    def test_line_analysis_integration_instructions(self) -> None:
        assert "Line Analysis Integration" in COACHING_SYSTEM_PROMPT
        assert "early_apex" in COACHING_SYSTEM_PROMPT
        assert "consistency_tier" in COACHING_SYSTEM_PROMPT

    def test_metric_allow_list_present(self) -> None:
        assert "Permitted Metrics — Data Honesty" in COACHING_SYSTEM_PROMPT
        assert "Corner min speed" in COACHING_SYSTEM_PROMPT
        assert "Speed gap optimal" in COACHING_SYSTEM_PROMPT

    def test_hallucination_example_present(self) -> None:
        assert "Hallucination Example" in COACHING_SYSTEM_PROMPT
        assert "mph of available grip" in COACHING_SYSTEM_PROMPT

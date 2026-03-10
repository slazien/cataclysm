"""Coaching quality regression tests for golden eval scenarios."""

from __future__ import annotations

import json
from typing import Protocol

import pytest

from cataclysm.coaching_content_validator import find_forbidden_composites
from cataclysm.coaching_judge import parse_judge_response


class _Scenario(Protocol):
    name: str
    skill_level: str
    sample_report: str
    judge_response: dict[str, object]
    min_scores: dict[str, int]
    must_mention: list[str]
    must_not_say: list[str]


@pytest.mark.eval
def test_coaching_quality_regression(eval_scenarios: list[_Scenario]) -> None:
    """Golden-scenario regression checks for grounding + rubric quality."""
    assert eval_scenarios

    for scenario in eval_scenarios:
        scenario_name = scenario.name
        sample_report = scenario.sample_report
        skill_level = scenario.skill_level
        must_mention = scenario.must_mention
        must_not_say = scenario.must_not_say
        min_scores = scenario.min_scores
        judge_response = scenario.judge_response

        report_lower = sample_report.lower()
        for token in must_mention:
            assert token.lower() in report_lower, (
                f"{scenario_name}: missing required token '{token}'"
            )
        for token in must_not_say:
            assert token.lower() not in report_lower, f"{scenario_name}: forbidden token '{token}'"

        assert not find_forbidden_composites(sample_report), (
            f"{scenario_name}: deterministic forbidden composite detected"
        )

        judge = parse_judge_response(json.dumps(judge_response), skill_level)
        for dimension, min_score in min_scores.items():
            actual = getattr(judge, dimension)
            assert actual >= min_score, (
                f"{scenario_name}: {dimension} score regression ({actual} < {min_score})"
            )
        assert judge.overall_pass is True, f"{scenario_name}: judge failed overall pass"

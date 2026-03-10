"""Tests for rubric-based coaching judge helpers."""

from __future__ import annotations

from cataclysm.coaching_judge import build_judge_prompt, parse_judge_response


def test_build_prompt_includes_skill_level_and_report() -> None:
    prompt = build_judge_prompt("Report body", "novice")
    assert "Skill level under evaluation: novice" in prompt
    assert "Report body" in prompt
    assert "trail braking" in prompt.lower()


def test_parse_judge_response_parses_valid_json() -> None:
    raw = (
        '{"topic_gating": 4, "communication_fit": 5, "data_relevance": 4, '
        '"causal_reasoning": 4, "actionability": 5, '
        '"forbidden_pattern_violations": [], "skill_level_checked": "intermediate", '
        '"overall_pass": true}'
    )
    result = parse_judge_response(raw, "intermediate")
    assert result.overall_pass is True
    assert result.data_relevance == 4
    assert result.skill_level_checked == "intermediate"


def test_parse_judge_response_hard_fails_low_score() -> None:
    raw = (
        '{"topic_gating": 2, "communication_fit": 5, "data_relevance": 5, '
        '"causal_reasoning": 5, "actionability": 5, '
        '"forbidden_pattern_violations": [], "skill_level_checked": "advanced", '
        '"overall_pass": true}'
    )
    result = parse_judge_response(raw, "advanced")
    assert result.overall_pass is False
    assert result.topic_gating == 2


def test_parse_judge_response_hard_fails_forbidden_violations() -> None:
    raw = (
        '{"topic_gating": 5, "communication_fit": 5, "data_relevance": 5, '
        '"causal_reasoning": 5, "actionability": 5, '
        '"forbidden_pattern_violations": ["trail braking for novice"], '
        '"skill_level_checked": "novice", "overall_pass": true}'
    )
    result = parse_judge_response(raw, "novice")
    assert result.overall_pass is False
    assert result.forbidden_pattern_violations == ["trail braking for novice"]

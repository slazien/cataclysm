"""Rubric-based judge prompt and parser for coaching quality evaluation."""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass, field

SkillLevel = str

_FORBIDDEN_PATTERNS_BY_SKILL: dict[str, list[str]] = {
    "novice": [
        "trail braking",
        "threshold braking",
        "friction circle",
        "slip angle",
        "rotation",
        "std dev",
        "release rate",
        "micro-sector",
        "more than 2 priorities",
        "more than 2 data citations",
    ],
    "intermediate": [
        "pure prescriptive commands without reasoning",
        "advice without self-comparison",
        "excessive advanced signal processing details",
    ],
    "advanced": [
        "oversimplified beginner language",
        "no quantitative references",
        "marker-only coaching without tradeoff reasoning",
        "ignores consistency or variance",
    ],
}


@dataclass(slots=True)
class CoachingJudgeResult:
    """Structured rubric output from the coaching judge."""

    topic_gating: int = 5
    communication_fit: int = 5
    data_relevance: int = 5
    causal_reasoning: int = 5
    actionability: int = 5
    forbidden_pattern_violations: list[str] = field(default_factory=list)
    skill_level_checked: str = "intermediate"
    overall_pass: bool = True


def build_judge_prompt(report_text: str, skill_level: SkillLevel) -> str:
    """Build a strict JSON-only scoring prompt for the coaching report judge."""
    forbidden = _FORBIDDEN_PATTERNS_BY_SKILL.get(
        skill_level,
        _FORBIDDEN_PATTERNS_BY_SKILL["intermediate"],
    )
    forbidden_lines = "\n".join(f"- {item}" for item in forbidden)

    return (
        "You are evaluating a motorsport coaching report produced by another model.\n"
        "Score only what is present in the report text.\n\n"
        f"Skill level under evaluation: {skill_level}\n\n"
        "Score each dimension from 1 to 5:\n"
        "- topic_gating (25%): advice complexity matches driver skill level\n"
        "- communication_fit (20%): language style matches the skill level\n"
        "- data_relevance (20%): uses relevant telemetry-backed evidence\n"
        "- causal_reasoning (20%): explains mechanism/root-cause, not symptoms only\n"
        "- actionability (15%): gives bounded, testable next steps\n\n"
        "Hard-fail skill-level forbidden patterns:\n"
        f"{forbidden_lines}\n\n"
        "Passing rule:\n"
        "- overall_pass=false if any dimension < 3\n"
        "- overall_pass=false if forbidden_pattern_violations is non-empty\n"
        "- overall_pass=true only when both conditions above pass\n\n"
        "Respond ONLY with strict JSON (no markdown):\n"
        '{"topic_gating": 1, "communication_fit": 1, "data_relevance": 1, '
        '"causal_reasoning": 1, "actionability": 1, '
        '"forbidden_pattern_violations": [], '
        '"skill_level_checked": "' + skill_level + '", "overall_pass": false}\n\n'
        "Coaching report to evaluate:\n"
        f"{report_text}"
    )


def parse_judge_response(raw_text: str, skill_level: SkillLevel) -> CoachingJudgeResult:
    """Parse judge response JSON into a normalized typed result."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    data: dict[str, object] | None = None
    with contextlib.suppress(json.JSONDecodeError):
        data = json.loads(text)

    if data is None:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            with contextlib.suppress(json.JSONDecodeError):
                data = json.loads(text[start : end + 1])

    if data is None:
        return CoachingJudgeResult(skill_level_checked=skill_level)

    result = CoachingJudgeResult(
        topic_gating=_coerce_score(data.get("topic_gating"), default=5),
        communication_fit=_coerce_score(data.get("communication_fit"), default=5),
        data_relevance=_coerce_score(data.get("data_relevance"), default=5),
        causal_reasoning=_coerce_score(data.get("causal_reasoning"), default=5),
        actionability=_coerce_score(data.get("actionability"), default=5),
        forbidden_pattern_violations=_coerce_violations(data.get("forbidden_pattern_violations")),
        skill_level_checked=str(data.get("skill_level_checked", skill_level)),
        overall_pass=bool(data.get("overall_pass", True)),
    )
    if (
        result.topic_gating < 3
        or result.communication_fit < 3
        or result.data_relevance < 3
        or result.causal_reasoning < 3
        or result.actionability < 3
        or result.forbidden_pattern_violations
    ):
        result.overall_pass = False
    return result


def _coerce_score(value: object, *, default: int) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(5, parsed))


def _coerce_violations(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    violations: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            violations.append(item.strip())
    return violations

"""LLM-as-judge for subjective coaching dimensions.

Uses DeepEval G-Eval for structured rubric scoring.
Run with: pytest evaluation/ --run-assessment
Requires: OPENAI_API_KEY or ANTHROPIC_API_KEY for the judge model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from evaluation.types import DimensionResult, Verdict

JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-5-mini")


@dataclass(slots=True)
class JudgeConfig:
    """Configuration for an LLM judge dimension."""

    name: str
    scoring_steps: list[str]
    threshold: float


PHYSICS_JUDGE = JudgeConfig(
    name="physics_accuracy",
    scoring_steps=[
        "Check that causal chains are physically correct "
        "(e.g., early braking -> slow entry -> lost time, NOT early braking -> oversteer).",
        "Check that weight transfer descriptions match the driving phase "
        "(braking -> front load, acceleration -> rear load).",
        "Check that trail braking advice correctly describes partial brake release "
        "through the turn, not full braking into the apex.",
        "Check that throttle advice is consistent with corner phase "
        "(no 'full throttle at apex' for slow corners).",
    ],
    threshold=0.7,
)

VOICE_JUDGE = JudgeConfig(
    name="voice_quality",
    scoring_steps=[
        "Check that tips use external focus -- describe what the CAR does "
        "(e.g., 'the car rotates', 'weight shifts forward'), "
        "NOT what the BODY does (e.g., 'push your left foot').",
        "Check that sentence structure varies -- not every paragraph starts with "
        "'At Turn N...' or follows the same template.",
        "Check that tone is conversational and encouraging, not robotic or report-like.",
        "Check that physical sensations are described where relevant "
        "(weight transfer feel, rotation, grip buildup).",
    ],
    threshold=0.7,
)

COHERENCE_JUDGE = JudgeConfig(
    name="coherence",
    scoring_steps=[
        "Check that the summary accurately reflects the priority corners and grades.",
        "Check that priority ordering makes sense -- biggest time loss or "
        "safety concern comes first.",
        "Check that corner grades are consistent with the tips "
        "(a 'C' grade corner should have improvement tips, not praise).",
        "Check that the report reads as a coherent coaching debrief, "
        "not a disconnected list of observations.",
    ],
    threshold=0.7,
)

ACTIONABILITY_JUDGE = JudgeConfig(
    name="actionability",
    scoring_steps=[
        "Rate each tip on a 3-point scale: "
        "1=Vague ('brake better'), "
        "2=Directional ('brake later'), "
        "3=Specific ('brake 3m later, at the 2-board').",
        "Check that at least 50% of tips are level 3 (Specific).",
        "Check that drills are concrete enough to execute "
        "(e.g., 'On your next session, focus on Turn 5 entry speed' "
        "is better than 'work on braking').",
    ],
    threshold=0.6,
)

ALL_JUDGES = [PHYSICS_JUDGE, VOICE_JUDGE, COHERENCE_JUDGE, ACTIONABILITY_JUDGE]


def run_llm_judge(
    config: JudgeConfig,
    coaching_output: str,
    telemetry_context: str = "",
) -> DimensionResult:
    """Run a single LLM judge dimension using DeepEval G-Eval."""
    try:
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    except ImportError:
        return DimensionResult(
            name=config.name,
            score=0.0,
            verdict=Verdict.WARN,
            details="deepeval not installed -- skipping LLM judge",
        )

    metric = GEval(
        name=config.name,
        evaluation_steps=config.scoring_steps,
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        model=JUDGE_MODEL,
        threshold=config.threshold,
    )

    test_case = LLMTestCase(
        input=telemetry_context or "Motorsport coaching telemetry session",
        actual_output=coaching_output,
    )

    metric.measure(test_case)
    score = metric.score or 0.0
    passed = score >= config.threshold
    return DimensionResult(
        name=config.name,
        score=score,
        verdict=Verdict.PASS if passed else Verdict.FAIL,
        details=metric.reason or "",
    )


def run_all_judges(
    coaching_output: str,
    telemetry_context: str = "",
    judges: list[JudgeConfig] | None = None,
) -> list[DimensionResult]:
    """Run all configured LLM judges."""
    configs = judges or ALL_JUDGES
    return [run_llm_judge(c, coaching_output, telemetry_context) for c in configs]

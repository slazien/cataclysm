"""Weighted score aggregation for assessment results."""

from __future__ import annotations

from evaluation.types import AssessmentResult, DimensionResult, Verdict

DEFAULT_WEIGHTS: dict[str, float] = {
    "citation_grounding": 0.25,
    "physics_accuracy": 0.25,
    "voice_quality": 0.15,
    "coherence": 0.15,
    "actionability": 0.10,
    "because_clauses": 0.05,
    "corner_first": 0.05,
}

DEFAULT_MINIMUMS: dict[str, float] = {
    "citation_grounding": 0.45,
    "physics_accuracy": 0.5,
}


def aggregate(
    case_id: str,
    hard_gate_results: list[DimensionResult],
    soft_results: list[DimensionResult],
    judge_results: list[DimensionResult],
    *,
    weights: dict[str, float] | None = None,
    minimums: dict[str, float] | None = None,
    pass_threshold: float = 0.70,
) -> AssessmentResult:
    """Aggregate all dimensions into a final verdict."""
    w = weights or DEFAULT_WEIGHTS
    mins = minimums or DEFAULT_MINIMUMS
    all_dims = hard_gate_results + soft_results + judge_results

    hard_gate_passed = all(r.verdict != Verdict.FAIL for r in hard_gate_results)
    if not hard_gate_passed:
        failed = [r for r in hard_gate_results if r.verdict == Verdict.FAIL]
        return AssessmentResult(
            case_id=case_id,
            hard_gate_passed=False,
            dimensions=all_dims,
            weighted_score=0.0,
            verdict=Verdict.FAIL,
            error=f"Hard gate failed: {[r.name for r in failed]}",
        )

    scored = [
        r
        for r in soft_results + judge_results
        if not (r.verdict == Verdict.WARN and r.score == 0.0)  # exclude skipped dims
    ]
    total_weight = sum(w.get(r.name, 0.0) for r in scored)
    if total_weight == 0:
        weighted = 0.0
    else:
        weighted = sum(r.score * w.get(r.name, 0.0) for r in scored) / total_weight

    min_violations = []
    for r in scored:
        min_score = mins.get(r.name)
        if min_score is not None and r.score < min_score:
            min_violations.append(f"{r.name}={r.score:.2f}<{min_score}")

    if min_violations:
        return AssessmentResult(
            case_id=case_id,
            hard_gate_passed=True,
            dimensions=all_dims,
            weighted_score=weighted,
            verdict=Verdict.FAIL,
            error=f"Below minimums: {min_violations}",
        )

    verdict = Verdict.PASS if weighted >= pass_threshold else Verdict.FAIL
    return AssessmentResult(
        case_id=case_id,
        hard_gate_passed=True,
        dimensions=all_dims,
        weighted_score=weighted,
        verdict=verdict,
    )

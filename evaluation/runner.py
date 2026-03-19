"""Assessment runner -- orchestrates all checks on a golden dataset.

Usage:
    pytest evaluation/ --run-assessment               # Full suite
    python -m evaluation.runner                       # Standalone CLI
    python -m evaluation.runner --no-llm-judge        # Skip LLM judges (free)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evaluation.aggregate import aggregate
from evaluation.citation_checks import check_citation_grounding
from evaluation.constraint_checks import run_constraint_checks
from evaluation.schema_checks import run_schema_checks
from evaluation.types import AssessmentResult, Verdict


def _extract_coaching_text(report: dict) -> str:
    """Extract human-readable coaching prose from a parsed report dict.

    Avoids feeding raw JSON to citation grounding / LLM judges, which would
    pick up structural numbers like ``"corner": 5`` as coaching claims.
    """
    def _str(val: object) -> str:
        return val if isinstance(val, str) else ""

    parts: list[str] = [_str(report.get("summary", ""))]
    for pc in report.get("priority_corners", []):
        parts.append(_str(pc.get("tip", "")))
        parts.append(_str(pc.get("feedback", "")))
    for cg in report.get("corner_grades", []):
        parts.append(_str(cg.get("notes", "")))
    for p in report.get("patterns", []):
        parts.append(_str(p))
    parts.append(_str(report.get("primary_focus", "")))
    for d in report.get("drills", []):
        parts.append(_str(d))
    return " ".join(p for p in parts if p)


def assess_single(
    case: dict,
    *,
    use_llm_judge: bool = True,
) -> AssessmentResult:
    """Assess a single coaching output against its telemetry input."""
    case_id = case.get("case_id", "unknown")
    raw_output = case.get("coaching_output", "")
    telemetry = case.get("telemetry", {})

    # Stage 1: Hard gates
    hard_gates = run_schema_checks(raw_output)
    any_hard_fail = any(r.verdict == Verdict.FAIL for r in hard_gates)
    if any_hard_fail:
        return aggregate(case_id, hard_gates, [], [])

    # Stage 2: Soft checks
    report_dict = json.loads(raw_output)
    soft = run_constraint_checks(report_dict)

    # Extract coaching prose (not raw JSON) for text-quality checks
    coaching_text = _extract_coaching_text(report_dict)
    soft.append(check_citation_grounding(coaching_text, telemetry))

    # Stage 3: LLM judge
    judge_results = []
    if use_llm_judge:
        from evaluation.llm_judges import run_all_judges

        telemetry_context = json.dumps(telemetry, indent=2)[:4000]
        judge_results = run_all_judges(coaching_text, telemetry_context)

    # Stage 4: Aggregation
    return aggregate(case_id, hard_gates, soft, judge_results)


def run_assessment(
    golden_path: str = "evaluation/golden_set.jsonl",
    *,
    use_llm_judge: bool = True,
) -> list[AssessmentResult]:
    """Run assessment on entire golden dataset."""
    path = Path(golden_path)
    if not path.exists():
        print(f"Golden set not found: {path}")
        return []

    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    print(f"Assessing {len(cases)} cases (LLM judge: {'ON' if use_llm_judge else 'OFF'})")

    results = [assess_single(c, use_llm_judge=use_llm_judge) for c in cases]

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    avg_score = sum(r.weighted_score for r in results) / len(results) if results else 0

    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{len(results)} PASSED ({failed} failed)")
    print(f"Average weighted score: {avg_score:.2f}")

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.case_id}: score={r.weighted_score:.2f} {r.error}")

    return results


if __name__ == "__main__":
    use_judge = "--no-llm-judge" not in sys.argv
    golden = "evaluation/golden_set.jsonl"
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            golden = arg
    run_assessment(golden, use_llm_judge=use_judge)

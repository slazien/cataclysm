"""Pytest-integrated assessment suite.

Run: pytest evaluation/test_suite.py --run-assessment --no-llm-judge -v
"""

from __future__ import annotations

import pytest

from evaluation.runner import assess_single


@pytest.mark.parametrize("case_idx", range(100))
def test_golden_case(golden_set: list[dict], case_idx: int, use_llm_judge: bool) -> None:
    """Assess a single golden case."""
    if case_idx >= len(golden_set):
        pytest.skip(f"Only {len(golden_set)} cases in golden set")

    case = golden_set[case_idx]
    result = assess_single(case, use_llm_judge=use_llm_judge)

    expected = case.get("expected_verdict")
    if expected == "fail":
        assert not result.passed, f"Expected FAIL but got PASS for {result.case_id}"
    elif expected == "pass":
        assert result.passed, (
            f"Expected PASS but got FAIL for {result.case_id}: "
            f"score={result.weighted_score:.2f} error={result.error}"
        )

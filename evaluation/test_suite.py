"""Pytest-integrated assessment suite.

Run: pytest evaluation/test_suite.py --run-assessment --no-llm-judge -v
"""

from __future__ import annotations

import pytest

from evaluation.runner import assess_single


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Dynamically parametrize golden cases based on actual dataset size."""
    if "case_idx" in metafunc.fixturenames:
        golden = metafunc.config.getoption("--golden-set", "evaluation/golden_set.jsonl")
        from pathlib import Path

        path = Path(golden)
        count = (
            sum(1 for line in path.read_text().splitlines() if line.strip()) if path.exists() else 0
        )
        metafunc.parametrize("case_idx", range(count), ids=[f"case-{i}" for i in range(count)])


@pytest.mark.eval
def test_golden_case(
    request: pytest.FixtureRequest,
    golden_set: list[dict],
    case_idx: int,
    use_llm_judge: bool,
) -> None:
    """Assess a single golden case."""
    if not request.config.getoption("--run-assessment", default=False):
        pytest.skip("assessment suite requires --run-assessment")

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

"""Shared fixtures for coaching eval regression tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(slots=True)
class EvalScenario:
    """Single evaluation scenario loaded from fixture + baseline files."""

    name: str
    skill_level: str
    sample_report: str
    judge_response: dict[str, object]
    min_scores: dict[str, int]
    must_mention: list[str]
    must_not_say: list[str]


@pytest.fixture
def eval_scenarios() -> list[EvalScenario]:
    """Load all eval scenarios from tests/eval fixtures + baselines."""
    root = Path(__file__).parent
    fixtures_dir = root / "fixtures"
    baselines_dir = root / "baselines"

    scenarios: list[EvalScenario] = []
    for fixture_path in sorted(fixtures_dir.glob("*.json")):
        fixture_data = json.loads(fixture_path.read_text())
        stem = fixture_path.stem
        baseline_path = baselines_dir / f"{stem}_baseline.json"
        baseline_data = json.loads(baseline_path.read_text())
        scenarios.append(
            EvalScenario(
                name=stem,
                skill_level=str(fixture_data["skill_level"]),
                sample_report=str(fixture_data["sample_report"]),
                judge_response=dict(fixture_data["judge_response"]),
                min_scores={k: int(v) for k, v in dict(baseline_data["min_scores"]).items()},
                must_mention=[str(x) for x in list(baseline_data.get("must_mention", []))],
                must_not_say=[str(x) for x in list(baseline_data.get("must_not_say", []))],
            )
        )

    return scenarios

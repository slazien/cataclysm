"""Pytest configuration for assessment tests."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    with contextlib.suppress(ValueError):
        parser.addoption("--run-assessment", action="store_true", help="Run LLM assessment suite")
    with contextlib.suppress(ValueError):
        parser.addoption(
            "--golden-set",
            default="evaluation/golden_set.jsonl",
            help="Path to golden dataset JSONL",
        )
    with contextlib.suppress(ValueError):
        parser.addoption("--no-llm-judge", action="store_true", default=False)


@pytest.fixture(scope="session")
def golden_set(request: pytest.FixtureRequest) -> list[dict]:
    """Load the golden dataset from JSONL."""
    path = Path(request.config.getoption("--golden-set"))
    if not path.exists():
        pytest.skip(f"Golden set not found: {path}")
    cases: list[dict] = []
    for line in path.read_text().splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


@pytest.fixture(scope="session")
def use_llm_judge(request: pytest.FixtureRequest) -> bool:
    return not request.config.getoption("--no-llm-judge", default=False)

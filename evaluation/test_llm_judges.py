"""Tests for LLM judge dimensions (mocked -- no actual API calls)."""

from __future__ import annotations

from typing import Any

from evaluation.llm_judges import (
    ALL_JUDGES,
    JudgeConfig,
)
from evaluation.types import Verdict


def test_missing_deepeval_returns_warn(monkeypatch: object) -> None:
    """If deepeval is not installed, return WARN not crash."""
    import builtins
    import importlib
    import sys

    # Temporarily hide deepeval
    saved = {}
    for mod_name in list(sys.modules):
        if mod_name.startswith("deepeval"):
            saved[mod_name] = sys.modules.pop(mod_name)

    import evaluation.llm_judges as mod

    importlib.reload(mod)

    # Now patch the import inside run_llm_judge to fail
    original_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("deepeval"):
            raise ImportError("mocked")
        return original_import(name, *args, **kwargs)

    old = builtins.__import__
    builtins.__import__ = fake_import  # type: ignore[assignment]
    try:
        importlib.reload(mod)
        config = JudgeConfig(name="test", scoring_steps=["Step 1", "Step 2"], threshold=0.5)
        result = mod.run_llm_judge(config, "some output")
        assert result.verdict == Verdict.WARN
        assert "not installed" in result.details
    finally:
        builtins.__import__ = old
        sys.modules.update(saved)
        importlib.reload(mod)


def test_judge_config_structure() -> None:
    """All judge configs have required fields."""
    for j in ALL_JUDGES:
        assert j.name
        assert len(j.scoring_steps) >= 2
        assert 0.0 <= j.threshold <= 1.0


def test_custom_judge_config() -> None:
    """Can create custom judge configs."""
    config = JudgeConfig(
        name="test",
        scoring_steps=["Step 1", "Step 2"],
        threshold=0.5,
    )
    assert config.name == "test"
    assert config.threshold == 0.5

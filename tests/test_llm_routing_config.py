"""Tests for DB-backed per-task routing config."""

from __future__ import annotations

import pytest

from cataclysm.llm_gateway import (
    _route_for_task,
    get_task_route_chain,
    set_task_route_cache,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure routing env vars don't leak into tests."""
    for var in (
        "LLM_ROUTING_ENABLED",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


def test_empty_cache_returns_defaults() -> None:
    set_task_route_cache({})
    provider, model = _route_for_task("coaching_report", "anthropic", "claude-haiku-4-5-20251001")
    assert provider == "anthropic"
    assert model == "claude-haiku-4-5-20251001"


def test_cache_overrides_primary() -> None:
    set_task_route_cache(
        {
            "coaching_report": [
                {"provider": "openai", "model": "gpt-5-mini"},
                {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
            ],
        }
    )
    provider, model = _route_for_task("coaching_report", "anthropic", "claude-haiku-4-5-20251001")
    assert provider == "openai"
    assert model == "gpt-5-mini"


def test_fallback_from_cache_chain() -> None:
    set_task_route_cache(
        {
            "coaching_report": [
                {"provider": "openai", "model": "gpt-5-mini"},
                {"provider": "google", "model": "gemini-2.5-flash"},
            ],
        }
    )
    chain = get_task_route_chain("coaching_report", "anthropic", "claude-haiku-4-5-20251001")
    assert len(chain) == 2
    assert chain[0] == ("openai", "gpt-5-mini")
    assert chain[1] == ("google", "gemini-2.5-flash")


def test_unconfigured_task_uses_caller_defaults() -> None:
    set_task_route_cache(
        {
            "coaching_report": [{"provider": "openai", "model": "gpt-5-mini"}],
        }
    )
    # topic_classifier not configured -> uses defaults
    provider, model = _route_for_task("topic_classifier", "anthropic", "claude-haiku-4-5-20251001")
    assert provider == "anthropic"
    assert model == "claude-haiku-4-5-20251001"


def test_get_chain_returns_default_when_no_cache() -> None:
    set_task_route_cache({})
    chain = get_task_route_chain("coaching_report", "anthropic", "claude-haiku-4-5-20251001")
    assert chain == [("anthropic", "claude-haiku-4-5-20251001")]

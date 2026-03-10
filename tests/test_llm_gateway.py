"""Tests for cataclysm.llm_gateway."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from cataclysm import llm_gateway
from cataclysm.llm_gateway import (
    LLMUsage,
    call_text_completion,
    get_recent_usage_events,
    get_usage_summary,
    set_task_route_cache,
)


@pytest.fixture(autouse=True)
def _clean_task_route_cache() -> Iterator[None]:
    """Ensure task route cache doesn't leak between tests."""
    set_task_route_cache({})
    yield
    set_task_route_cache({})


def _clear_events() -> None:
    with llm_gateway._EVENTS_LOCK:  # noqa: SLF001
        llm_gateway._EVENTS.clear()  # noqa: SLF001


def test_call_text_completion_uses_default_provider_when_routing_disabled(
    monkeypatch,
) -> None:
    _clear_events()
    monkeypatch.setenv("LLM_ROUTING_ENABLED", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    def _fake_call_anthropic(*_args, **_kwargs):
        return "ok", LLMUsage(input_tokens=100, output_tokens=20)

    monkeypatch.setattr(llm_gateway, "_call_anthropic", _fake_call_anthropic)

    result = call_text_completion(
        task="coaching_report",
        user_content="hello",
        system=None,
        max_tokens=128,
        temperature=0.3,
        default_provider="anthropic",
        default_model="claude-haiku-4-5-20251001",
    )

    assert result.provider == "anthropic"
    assert result.text == "ok"
    summary = get_usage_summary()
    assert summary["total_calls"] == 1.0
    assert summary["total_errors"] == 0.0


def test_route_prefers_openai_for_lightweight_tasks_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("LLM_ROUTING_ENABLED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    provider, model = llm_gateway._route_for_task(  # noqa: SLF001
        "topic_classifier",
        "anthropic",
        "claude-haiku-4-5-20251001",
    )
    assert provider == "openai"
    assert model == "gpt-5-nano"


def test_recent_usage_events_returns_newest_first(monkeypatch) -> None:
    _clear_events()
    monkeypatch.setenv("LLM_ROUTING_ENABLED", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    def _fake_call_anthropic(*_args, **_kwargs):
        return "ok", LLMUsage(input_tokens=10, output_tokens=5)

    monkeypatch.setattr(llm_gateway, "_call_anthropic", _fake_call_anthropic)

    call_text_completion(
        task="t1",
        user_content="a",
        system=None,
        max_tokens=64,
        temperature=0.0,
        default_provider="anthropic",
        default_model="claude-haiku-4-5-20251001",
    )
    call_text_completion(
        task="t2",
        user_content="b",
        system=None,
        max_tokens=64,
        temperature=0.0,
        default_provider="anthropic",
        default_model="claude-haiku-4-5-20251001",
    )

    events = get_recent_usage_events(limit=2)
    assert len(events) == 2
    assert events[0]["task"] == "t2"
    assert events[1]["task"] == "t1"

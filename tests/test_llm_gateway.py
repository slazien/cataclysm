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


# ---------------------------------------------------------------------------
# Provider-specific parameter handling
# ---------------------------------------------------------------------------


def test_openai_reasoning_model_strips_temperature(monkeypatch) -> None:
    """GPT-5 Nano/Mini are reasoning models that reject temperature."""
    _clear_events()
    monkeypatch.setenv("LLM_ROUTING_ENABLED", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")

    captured_kwargs: dict = {}

    def _fake_call_openai(
        model,
        user_content,
        *,
        system,
        max_tokens,
        temperature,
        timeout_s,
        max_retries,
        json_mode=False,
    ):
        captured_kwargs["temperature"] = temperature
        captured_kwargs["model"] = model
        return "ok", LLMUsage(input_tokens=10, output_tokens=5)

    monkeypatch.setattr(llm_gateway, "_call_openai", _fake_call_openai)

    result = call_text_completion(
        task="coaching_report",
        user_content="test",
        system=None,
        max_tokens=128,
        temperature=0.3,
        default_provider="openai",
        default_model="gpt-5-nano",
    )
    assert result.provider == "openai"
    assert result.text == "ok"


def _make_fake_openai_client(captured: dict):
    """Create a fake OpenAI client that captures kwargs passed to responses.create."""

    class _Usage:
        input_tokens = 10
        output_tokens = 5
        input_tokens_details = None

    class _FakeResponse:
        usage = _Usage
        output = [
            type(
                "Block",
                (),
                {
                    "type": "message",
                    "content": [type("T", (), {"type": "output_text", "text": "ok"})()],
                },
            )()
        ]

    class _FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse()

    class _FakeClient:
        responses = _FakeResponses()

        def __init__(self, **kw):
            pass

    return _FakeClient


def test_openai_reasoning_model_kwargs_no_temperature(monkeypatch) -> None:
    """Verify _call_openai actually strips temperature from kwargs for reasoning models."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")

    captured: dict = {}
    fake_client = _make_fake_openai_client(captured)
    monkeypatch.setattr("openai.OpenAI", fake_client)

    from cataclysm.llm_gateway import _call_openai

    _call_openai(
        "gpt-5-nano",
        "test prompt",
        system="sys",
        max_tokens=128,
        temperature=0.3,
        timeout_s=30,
        max_retries=1,
    )
    assert "temperature" not in captured, (
        f"temperature should be stripped for reasoning model, got {captured}"
    )

    # Non-reasoning model should keep temperature
    captured.clear()
    _call_openai(
        "gpt-4o",
        "test prompt",
        system="sys",
        max_tokens=128,
        temperature=0.3,
        timeout_s=30,
        max_retries=1,
    )
    assert captured.get("temperature") == 0.3, "Non-reasoning model should pass temperature"


def test_openai_gpt5_mini_also_strips_temperature(monkeypatch) -> None:
    """GPT-5 Mini is also a reasoning model."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")

    captured: dict = {}
    fake_client = _make_fake_openai_client(captured)
    monkeypatch.setattr("openai.OpenAI", fake_client)

    from cataclysm.llm_gateway import _call_openai

    _call_openai(
        "gpt-5-mini",
        "test",
        system=None,
        max_tokens=64,
        temperature=0.5,
        timeout_s=30,
        max_retries=1,
    )
    assert "temperature" not in captured


def test_google_model_passes_temperature(monkeypatch) -> None:
    """Gemini models should receive temperature normally."""
    _clear_events()
    monkeypatch.setenv("LLM_ROUTING_ENABLED", "0")
    monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")

    def _fake_call_google(
        model, user_content, *, system, max_tokens, temperature, timeout_s, json_mode=False
    ):
        assert temperature == 0.3, "Google models should receive temperature"
        return "gemini ok", LLMUsage(input_tokens=10, output_tokens=5)

    monkeypatch.setattr(llm_gateway, "_call_google", _fake_call_google)

    result = call_text_completion(
        task="coaching_report",
        user_content="test",
        system=None,
        max_tokens=128,
        temperature=0.3,
        default_provider="google",
        default_model="gemini-2.5-flash",
    )
    assert result.provider == "google"
    assert result.text == "gemini ok"


def test_openai_json_mode_sets_text_format(monkeypatch) -> None:
    """json_mode=True should set text.format.type=json_object on OpenAI calls."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")

    captured: dict = {}
    fake_client = _make_fake_openai_client(captured)
    monkeypatch.setattr("openai.OpenAI", fake_client)

    from cataclysm.llm_gateway import _call_openai

    _call_openai(
        "gpt-5-mini",
        "return JSON",
        system=None,
        max_tokens=128,
        temperature=0.3,
        timeout_s=30,
        max_retries=1,
        json_mode=True,
    )
    assert captured.get("text") == {"format": {"type": "json_object"}}

    # Without json_mode, no text format
    captured.clear()
    _call_openai(
        "gpt-5-mini",
        "test",
        system=None,
        max_tokens=64,
        temperature=None,
        timeout_s=30,
        max_retries=1,
    )
    assert "text" not in captured

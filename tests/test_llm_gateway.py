"""Tests for cataclysm.llm_gateway."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from cataclysm import llm_gateway
from cataclysm.llm_gateway import (
    LLMUsage,
    _estimate_cost_usd,
    call_text_completion,
    get_recent_usage_events,
    get_usage_summary,
    set_routing_enabled_override,
    set_task_route_cache,
)


@pytest.fixture(autouse=True)
def _clean_llm_gateway_state() -> Iterator[None]:
    """Ensure task route cache and routing override don't leak between tests."""
    set_task_route_cache({})
    set_routing_enabled_override(None, source="test-reset")
    yield
    set_task_route_cache({})
    set_routing_enabled_override(None, source="test-reset")


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


def test_openai_reasoning_model_triples_max_tokens(monkeypatch) -> None:
    """Reasoning models get 3x max_output_tokens to account for internal chain-of-thought."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")

    captured: dict = {}
    fake_client = _make_fake_openai_client(captured)
    monkeypatch.setattr("openai.OpenAI", fake_client)

    from cataclysm.llm_gateway import _call_openai

    _call_openai(
        "gpt-5-mini",
        "test",
        system=None,
        max_tokens=8192,
        temperature=0.3,
        timeout_s=30,
        max_retries=1,
    )
    assert captured["max_output_tokens"] == 8192 * 3, (
        f"Reasoning model should get 3x tokens, got {captured['max_output_tokens']}"
    )

    # Non-reasoning model should pass max_tokens unchanged
    captured.clear()
    _call_openai(
        "gpt-4o",
        "test",
        system=None,
        max_tokens=8192,
        temperature=0.3,
        timeout_s=30,
        max_retries=1,
    )
    assert captured["max_output_tokens"] == 8192, (
        f"Non-reasoning model should get exact max_tokens, got {captured['max_output_tokens']}"
    )


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


# ---------------------------------------------------------------------------
# Prompt caching: _call_anthropic cache_control
# ---------------------------------------------------------------------------


def test_call_anthropic_sends_cache_control(monkeypatch) -> None:
    """Verify _call_anthropic sends system as content block list with cache_control."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    captured_kwargs: dict = {}

    class _FakeUsage:
        input_tokens = 100
        output_tokens = 50
        cache_read_input_tokens = 0
        cache_creation_input_tokens = 0

    class _FakeBlock:
        text = "response text"

    class _FakeMessage:
        content = [_FakeBlock()]
        usage = _FakeUsage()

    class _FakeMessages:
        def create(self, **kwargs: object) -> _FakeMessage:
            captured_kwargs.update(kwargs)
            return _FakeMessage()

    class _FakeClient:
        messages = _FakeMessages()

        def __init__(self, **_kw: object) -> None:
            pass

    monkeypatch.setattr("anthropic.Anthropic", _FakeClient)

    from cataclysm.llm_gateway import _call_anthropic

    _call_anthropic(
        "claude-haiku-4-5-20251001",
        "hello",
        system="You are a motorsport coach.",
        max_tokens=256,
        temperature=0.3,
        timeout_s=30,
        max_retries=1,
    )

    system_val = captured_kwargs["system"]
    assert isinstance(system_val, list), f"Expected list, got {type(system_val)}"
    assert len(system_val) == 1
    block = system_val[0]
    assert block["type"] == "text"
    assert block["text"] == "You are a motorsport coach."
    assert block["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_call_anthropic_no_system_omits_key(monkeypatch) -> None:
    """When system is None, kwargs should not contain 'system' key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    captured_kwargs: dict = {}

    class _FakeUsage:
        input_tokens = 10
        output_tokens = 5
        cache_read_input_tokens = 0
        cache_creation_input_tokens = 0

    class _FakeBlock:
        text = "ok"

    class _FakeMessage:
        content = [_FakeBlock()]
        usage = _FakeUsage()

    class _FakeMessages:
        def create(self, **kwargs: object) -> _FakeMessage:
            captured_kwargs.update(kwargs)
            return _FakeMessage()

    class _FakeClient:
        messages = _FakeMessages()

        def __init__(self, **_kw: object) -> None:
            pass

    monkeypatch.setattr("anthropic.Anthropic", _FakeClient)

    from cataclysm.llm_gateway import _call_anthropic

    _call_anthropic(
        "claude-haiku-4-5-20251001",
        "hello",
        system=None,
        max_tokens=64,
        temperature=None,
        timeout_s=30,
        max_retries=1,
    )

    assert "system" not in captured_kwargs


# ---------------------------------------------------------------------------
# Cost estimation with caching
# ---------------------------------------------------------------------------


def test_estimate_cost_usd_with_caching() -> None:
    """Cached input tokens cost 0.1x — 8000/10000 cached on Haiku."""
    usage = LLMUsage(
        input_tokens=10000,
        output_tokens=5000,
        cached_input_tokens=8000,
        cache_creation_input_tokens=0,
    )
    cost = _estimate_cost_usd("anthropic", "claude-haiku-4-5-20251001", usage)
    # normal: 2000 * 1.0 = 2000, cached: 8000 * 0.1 = 800, out: 5000 * 5.0 = 25000
    # total = (2000 + 800 + 25000) / 1e6 = 0.0278
    assert cost == pytest.approx(0.0278, abs=1e-6)


def test_estimate_cost_usd_with_cache_write() -> None:
    """Cache creation tokens cost 2.0x — 8000/10000 are cache writes on Haiku."""
    usage = LLMUsage(
        input_tokens=10000,
        output_tokens=5000,
        cached_input_tokens=0,
        cache_creation_input_tokens=8000,
    )
    cost = _estimate_cost_usd("anthropic", "claude-haiku-4-5-20251001", usage)
    # normal: 2000 * 1.0 = 2000, write: 8000 * 2.0 = 16000, out: 5000 * 5.0 = 25000
    # total = (2000 + 16000 + 25000) / 1e6 = 0.043
    assert cost == pytest.approx(0.043, abs=1e-6)


def test_estimate_cost_usd_no_caching() -> None:
    """With zero cached tokens, cost calculation matches the original formula."""
    usage = LLMUsage(
        input_tokens=10000,
        output_tokens=5000,
        cached_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    cost = _estimate_cost_usd("anthropic", "claude-haiku-4-5-20251001", usage)
    # normal: 10000 * 1.0 = 10000, out: 5000 * 5.0 = 25000
    # total = 35000 / 1e6 = 0.035
    assert cost == pytest.approx(0.035, abs=1e-6)

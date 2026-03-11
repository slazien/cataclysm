"""Provider-agnostic LLM gateway with lightweight usage telemetry."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

logger = logging.getLogger(__name__)

Provider = Literal["anthropic", "openai", "google"]

_LIGHTWEIGHT_TASKS = {
    "topic_classifier",
    "coaching_validator",
    "share_comparison",
    "track_draft",
}


@dataclass(slots=True)
class LLMUsage:
    """Token usage for a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass(slots=True)
class LLMResult:
    """Normalized LLM result payload."""

    text: str
    provider: Provider
    model: str
    usage: LLMUsage
    latency_ms: float
    cost_usd: float


@dataclass(slots=True)
class UsageEvent:
    """In-memory telemetry event."""

    timestamp: str
    task: str
    provider: str
    model: str
    success: bool
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cache_creation_input_tokens: int
    latency_ms: float
    cost_usd: float
    error: str | None = None


_EVENTS_LOCK = threading.Lock()
_EVENTS: deque[UsageEvent] = deque(maxlen=5000)
_EVENT_SINK_LOCK = threading.Lock()
_EVENT_SINK: Callable[[dict[str, Any]], None] | None = None
_ROUTING_LOCK = threading.Lock()
_ROUTING_ENABLED_OVERRIDE: bool | None = None
_ROUTING_SOURCE: str = "default"
_ROUTING_UPDATED_AT: str | None = None

# ── Per-task route cache (synced from DB) ────────────────────────────
_TASK_ROUTE_LOCK = threading.Lock()
_TASK_ROUTE_CACHE: dict[str, list[dict[str, str]]] = {}


def set_task_route_cache(routes: dict[str, list[dict[str, str]]]) -> None:
    """Replace the in-memory per-task route cache (called by sync worker)."""
    global _TASK_ROUTE_CACHE
    with _TASK_ROUTE_LOCK:
        _TASK_ROUTE_CACHE = dict(routes)


def get_task_route_chain(
    task: str, default_provider: Provider, default_model: str
) -> list[tuple[Provider, str]]:
    """Return the full provider/model chain for a task (primary + fallbacks)."""
    with _TASK_ROUTE_LOCK:
        chain_raw = _TASK_ROUTE_CACHE.get(task)
    if not chain_raw:
        return [(default_provider, default_model)]
    return [
        (
            _normalize_provider(entry.get("provider"), default_provider),
            entry.get("model", default_model),
        )
        for entry in chain_raw
    ]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _normalize_provider(raw: str | None, default: Provider) -> Provider:
    if raw is None:
        return default
    val = raw.strip().lower()
    if val in {"anthropic", "openai", "google"}:
        return val  # type: ignore[return-value]
    return default


def _task_env_key(prefix: str, task: str) -> str:
    return f"{prefix}_{task.upper()}"


def set_routing_enabled_override(enabled: bool | None, *, source: str = "db") -> None:
    """Set an optional runtime override for global LLM routing."""
    global _ROUTING_ENABLED_OVERRIDE, _ROUTING_SOURCE, _ROUTING_UPDATED_AT
    with _ROUTING_LOCK:
        _ROUTING_ENABLED_OVERRIDE = enabled
        _ROUTING_SOURCE = source
        _ROUTING_UPDATED_AT = datetime.now(UTC).isoformat()


def routing_enabled(default: bool = False) -> bool:
    """Return whether global LLM routing is enabled."""
    with _ROUTING_LOCK:
        override = _ROUTING_ENABLED_OVERRIDE
    if override is not None:
        return override
    return _env_bool("LLM_ROUTING_ENABLED", default)


def get_routing_status(default: bool = False) -> dict[str, str | bool | None]:
    """Return routing status metadata for admin dashboards."""
    with _ROUTING_LOCK:
        override = _ROUTING_ENABLED_OVERRIDE
        source = _ROUTING_SOURCE
        updated_at = _ROUTING_UPDATED_AT

    if override is not None:
        return {
            "enabled": override,
            "source": source,
            "updated_at": updated_at,
        }

    raw = os.environ.get("LLM_ROUTING_ENABLED")
    return {
        "enabled": _env_bool("LLM_ROUTING_ENABLED", default),
        "source": "env" if raw is not None else "default",
        "updated_at": None,
    }


def _route_for_task(
    task: str, default_provider: Provider, default_model: str
) -> tuple[Provider, str]:
    """Resolve provider/model route for a task.

    Priority: DB config > env vars > caller defaults.
    """
    # 1. DB-backed per-task config (highest priority)
    with _TASK_ROUTE_LOCK:
        chain_raw = _TASK_ROUTE_CACHE.get(task)
    if chain_raw:
        entry = chain_raw[0]
        return (
            _normalize_provider(entry.get("provider"), default_provider),
            entry.get("model", default_model),
        )

    # 2. Legacy env-var routing (only when routing enabled)
    if not routing_enabled(False):
        return default_provider, default_model

    provider_override = os.environ.get(_task_env_key("LLM_PROVIDER", task))
    model_override = os.environ.get(_task_env_key("LLM_MODEL", task))
    if provider_override and model_override:
        provider = _normalize_provider(provider_override, default_provider)
        return provider, model_override

    # Auto route to cheaper tiers when explicit overrides are not set.
    if task in _LIGHTWEIGHT_TASKS:
        if os.environ.get("OPENAI_API_KEY"):
            return "openai", "gpt-5-nano"
        if os.environ.get("GOOGLE_API_KEY"):
            return "google", "gemini-2.5-flash-lite"
    else:
        if os.environ.get("OPENAI_API_KEY"):
            return "openai", "gpt-5-mini"
        if os.environ.get("GOOGLE_API_KEY"):
            return "google", "gemini-2.5-flash"

    return default_provider, default_model


def _fallback_for_task(
    task: str, default_provider: Provider, default_model: str
) -> tuple[Provider, str]:
    provider = _normalize_provider(
        os.environ.get(_task_env_key("LLM_FALLBACK_PROVIDER", task)),
        default_provider,
    )
    model = os.environ.get(_task_env_key("LLM_FALLBACK_MODEL", task), default_model)
    return provider, model


def _provider_api_key(provider: Provider) -> str:
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY", "")
    if provider == "openai":
        return os.environ.get("OPENAI_API_KEY", "")
    return os.environ.get("GOOGLE_API_KEY", "")


def is_task_available(task: str, default_provider: Provider = "anthropic") -> bool:
    """Return True if a routed provider has an API key configured."""
    with _TASK_ROUTE_LOCK:
        has_db_config = task in _TASK_ROUTE_CACHE
    if has_db_config:
        chain = get_task_route_chain(task, default_provider, "")
        return any(_provider_api_key(p) for p, _m in chain)
    # Legacy: use env-var routing (primary + fallback)
    provider, _ = _route_for_task(task, default_provider, "")
    if _provider_api_key(provider):
        return True
    fb_provider, _ = _fallback_for_task(task, default_provider, "")
    return bool(_provider_api_key(fb_provider))


def _extract_text_from_openai(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text:
        return text
    output = getattr(response, "output", None)
    if output is None:
        return ""
    chunks: list[str] = []
    for item in output:
        content = getattr(item, "content", None)
        if content is None:
            continue
        for part in content:
            value = getattr(part, "text", None)
            if isinstance(value, str):
                chunks.append(value)
    return "".join(chunks)


def _estimate_cost_usd(provider: Provider, model: str, usage: LLMUsage) -> float:
    """Estimate request cost from public token pricing snapshots."""
    in_rate = 0.0
    out_rate = 0.0
    m = model.lower()
    if provider == "anthropic":
        if "sonnet-4-6" in m:
            in_rate, out_rate = 3.0, 15.0
        elif "haiku-4-5" in m:
            in_rate, out_rate = 1.0, 5.0
    elif provider == "openai":
        if "gpt-5-nano" in m:
            in_rate, out_rate = 0.05, 0.4
        elif "gpt-5-mini" in m:
            in_rate, out_rate = 0.25, 2.0
    elif provider == "google":
        if "flash-lite" in m:
            in_rate, out_rate = 0.10, 0.40
        elif "gemini-2.5-flash" in m:
            in_rate, out_rate = 0.30, 2.50
    return (usage.input_tokens * in_rate + usage.output_tokens * out_rate) / 1_000_000


def _record_event(event: UsageEvent) -> None:
    payload = asdict(event)
    with _EVENTS_LOCK:
        _EVENTS.append(event)
    sink: Callable[[dict[str, Any]], None] | None
    with _EVENT_SINK_LOCK:
        sink = _EVENT_SINK
    if sink is not None:
        try:
            sink(payload)
        except Exception:  # noqa: BLE001
            logger.warning("LLM usage event sink failed", exc_info=True)


def set_usage_event_sink(sink: Callable[[dict[str, Any]], None] | None) -> None:
    """Register an optional sink for persisted usage telemetry."""
    global _EVENT_SINK
    with _EVENT_SINK_LOCK:
        _EVENT_SINK = sink


def get_usage_summary() -> dict[str, Any]:
    """Return aggregate usage summary over in-memory telemetry events."""
    with _EVENTS_LOCK:
        events = list(_EVENTS)

    by_task: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "calls": 0.0,
            "errors": 0.0,
            "input_tokens": 0.0,
            "output_tokens": 0.0,
            "cost_usd": 0.0,
            "latency_ms_sum": 0.0,
        }
    )

    for event in events:
        slot = by_task[event.task]
        slot["calls"] += 1.0
        slot["input_tokens"] += float(event.input_tokens)
        slot["output_tokens"] += float(event.output_tokens)
        slot["cost_usd"] += event.cost_usd
        slot["latency_ms_sum"] += event.latency_ms
        if not event.success:
            slot["errors"] += 1.0

    tasks: dict[str, dict[str, float]] = {}
    for task, agg in by_task.items():
        calls = max(1.0, agg["calls"])
        tasks[task] = {
            "calls": agg["calls"],
            "errors": agg["errors"],
            "input_tokens": agg["input_tokens"],
            "output_tokens": agg["output_tokens"],
            "cost_usd": round(agg["cost_usd"], 6),
            "avg_latency_ms": round(agg["latency_ms_sum"] / calls, 2),
        }

    total_calls = float(len(events))
    total_errors = float(sum(1 for e in events if not e.success))
    total_cost = float(sum(e.cost_usd for e in events))
    return {
        "total_calls": total_calls,
        "total_errors": total_errors,
        "total_cost_usd": round(total_cost, 6),
        "tasks": tasks,
    }


def get_recent_usage_events(limit: int = 100) -> list[dict[str, Any]]:
    """Return recent telemetry events (newest-first)."""
    with _EVENTS_LOCK:
        items = list(_EVENTS)[-max(1, limit) :]
    items.reverse()
    return [asdict(item) for item in items]


def _call_anthropic(
    model: str,
    user_content: str,
    *,
    system: str | None,
    max_tokens: int,
    temperature: float | None,
    timeout_s: float,
    max_retries: int,
) -> tuple[str, LLMUsage]:
    import anthropic

    client = anthropic.Anthropic(
        api_key=_provider_api_key("anthropic"),
        max_retries=max_retries,
        timeout=timeout_s,
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user_content}],
    }
    if system:
        kwargs["system"] = system
    if temperature is not None:
        kwargs["temperature"] = temperature
    message = client.messages.create(**kwargs)
    block = message.content[0]
    text = block.text if hasattr(block, "text") else str(block)
    usage_obj = getattr(message, "usage", None)
    usage = LLMUsage(
        input_tokens=int(getattr(usage_obj, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage_obj, "output_tokens", 0) or 0),
        cached_input_tokens=int(getattr(usage_obj, "cache_read_input_tokens", 0) or 0),
        cache_creation_input_tokens=int(getattr(usage_obj, "cache_creation_input_tokens", 0) or 0),
    )
    return text, usage


# OpenAI reasoning models (o-series, GPT-5 Nano/Mini) reject temperature.
_OPENAI_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5-nano", "gpt-5-mini")


def _call_openai(
    model: str,
    user_content: str,
    *,
    system: str | None,
    max_tokens: int,
    temperature: float | None,
    timeout_s: float,
    max_retries: int,
) -> tuple[str, LLMUsage]:
    from openai import OpenAI

    client = OpenAI(
        api_key=_provider_api_key("openai"),
        max_retries=max_retries,
        timeout=timeout_s,
    )
    is_reasoning = any(model.startswith(p) for p in _OPENAI_REASONING_PREFIXES)

    kwargs: dict[str, Any] = {
        "model": model,
        "input": user_content,
        "max_output_tokens": max_tokens,
    }
    if system:
        kwargs["instructions"] = system
    if temperature is not None and not is_reasoning:
        kwargs["temperature"] = temperature

    response = client.responses.create(**kwargs)
    text = _extract_text_from_openai(response)

    usage_obj = getattr(response, "usage", None)
    input_tokens = int(getattr(usage_obj, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage_obj, "output_tokens", 0) or 0)
    cached = 0
    details = getattr(usage_obj, "input_tokens_details", None)
    if details is not None:
        cached = int(getattr(details, "cached_tokens", 0) or 0)
    usage = LLMUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached,
    )
    return text, usage


def _call_google(
    model: str,
    user_content: str,
    *,
    system: str | None,
    max_tokens: int,
    temperature: float | None,
    timeout_s: float,
) -> tuple[str, LLMUsage]:
    import google.generativeai as genai

    genai.configure(api_key=_provider_api_key("google"))
    model_obj = genai.GenerativeModel(model_name=model, system_instruction=system)
    generation_config = genai.types.GenerationConfig(
        max_output_tokens=max_tokens,
        temperature=temperature if temperature is not None else 0.3,
    )
    try:
        response = model_obj.generate_content(
            user_content,
            generation_config=generation_config,
            request_options={"timeout": timeout_s},
        )
    except TypeError:
        # Older google-generativeai versions may not support request_options.
        response = model_obj.generate_content(
            user_content,
            generation_config=generation_config,
        )
    text = getattr(response, "text", "") or ""
    usage_obj = getattr(response, "usage_metadata", None)
    usage = LLMUsage(
        input_tokens=int(getattr(usage_obj, "prompt_token_count", 0) or 0),
        output_tokens=int(getattr(usage_obj, "candidates_token_count", 0) or 0),
        cached_input_tokens=int(getattr(usage_obj, "cached_content_token_count", 0) or 0),
    )
    return text, usage


def call_text_completion(
    *,
    task: str,
    user_content: str,
    system: str | None,
    max_tokens: int,
    temperature: float | None,
    default_provider: Provider,
    default_model: str,
    timeout_s: float | None = None,
    max_retries: int | None = None,
) -> LLMResult:
    """Execute a text completion with routing + fallback + telemetry."""
    resolved_timeout_s = (
        timeout_s if timeout_s is not None else float(os.environ.get("LLM_TIMEOUT_S", "120"))
    )
    resolved_max_retries = (
        max_retries if max_retries is not None else _env_int("LLM_MAX_RETRIES", 3)
    )
    # Build attempt chain: DB config (full chain) or legacy (primary+fallback)
    with _TASK_ROUTE_LOCK:
        chain_raw = _TASK_ROUTE_CACHE.get(task)
    if chain_raw:
        attempts = [
            (
                _normalize_provider(e.get("provider"), default_provider),
                e.get("model", default_model),
            )
            for e in chain_raw
        ]
    else:
        primary_provider, primary_model = _route_for_task(task, default_provider, default_model)
        fallback_provider, fallback_model = _fallback_for_task(
            task, default_provider, default_model
        )
        attempts = [(primary_provider, primary_model)]
        if (fallback_provider, fallback_model) != (primary_provider, primary_model):
            attempts.append((fallback_provider, fallback_model))

    last_error: Exception | None = None
    for provider, model in attempts:
        api_key = _provider_api_key(provider)
        if not api_key:
            continue
        start = time.perf_counter()
        try:
            if provider == "anthropic":
                text, usage = _call_anthropic(
                    model,
                    user_content,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout_s=resolved_timeout_s,
                    max_retries=resolved_max_retries,
                )
            elif provider == "openai":
                text, usage = _call_openai(
                    model,
                    user_content,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout_s=resolved_timeout_s,
                    max_retries=resolved_max_retries,
                )
            else:
                text, usage = _call_google(
                    model,
                    user_content,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout_s=resolved_timeout_s,
                )
            latency_ms = (time.perf_counter() - start) * 1000.0
            cost_usd = _estimate_cost_usd(provider, model, usage)
            _record_event(
                UsageEvent(
                    timestamp=datetime.now(UTC).isoformat(),
                    task=task,
                    provider=provider,
                    model=model,
                    success=True,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cached_input_tokens=usage.cached_input_tokens,
                    cache_creation_input_tokens=usage.cache_creation_input_tokens,
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                )
            )
            return LLMResult(
                text=text,
                provider=provider,
                model=model,
                usage=usage,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            latency_ms = (time.perf_counter() - start) * 1000.0
            _record_event(
                UsageEvent(
                    timestamp=datetime.now(UTC).isoformat(),
                    task=task,
                    provider=provider,
                    model=model,
                    success=False,
                    input_tokens=0,
                    output_tokens=0,
                    cached_input_tokens=0,
                    cache_creation_input_tokens=0,
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    error=type(exc).__name__,
                )
            )
            logger.warning(
                "LLM call failed (%s/%s task=%s), trying fallback if available",
                provider,
                model,
                task,
                exc_info=True,
            )

    if last_error is not None:
        raise last_error
    raise RuntimeError("No configured LLM API key available for task")

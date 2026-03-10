"""Persistent storage and aggregation for LLM usage telemetry."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import async_session_factory
from backend.api.db.models import LLMUsageEvent

logger = logging.getLogger(__name__)

_QUEUE_MAX_SIZE = 10_000
_PERSIST_BATCH_SIZE = 100
_MAX_PERSIST_ATTEMPTS = 5
_RETRY_BACKOFF_S = 1.0

_queue: asyncio.Queue[dict[str, Any]] | None = None
_queue_loop: asyncio.AbstractEventLoop | None = None
_worker_task: asyncio.Task[None] | None = None


def _parse_timestamp(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=UTC)
        return raw.astimezone(UTC)
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def _event_to_model(event: dict[str, Any]) -> LLMUsageEvent:
    return LLMUsageEvent(
        event_timestamp=_parse_timestamp(event.get("timestamp")),
        task=str(event.get("task", "")),
        provider=str(event.get("provider", "")),
        model=str(event.get("model", "")),
        success=bool(event.get("success", False)),
        input_tokens=int(event.get("input_tokens", 0) or 0),
        output_tokens=int(event.get("output_tokens", 0) or 0),
        cached_input_tokens=int(event.get("cached_input_tokens", 0) or 0),
        cache_creation_input_tokens=int(event.get("cache_creation_input_tokens", 0) or 0),
        latency_ms=float(event.get("latency_ms", 0.0) or 0.0),
        cost_usd=float(event.get("cost_usd", 0.0) or 0.0),
        error=str(event.get("error")) if event.get("error") else None,
    )


async def _persist_batch(events: list[dict[str, Any]]) -> None:
    if not events:
        return
    async with async_session_factory() as db:
        for event in events:
            db.add(_event_to_model(event))
        await db.commit()


async def _worker() -> None:
    assert _queue is not None
    while True:
        first = await _queue.get()
        batch = [first]
        while len(batch) < _PERSIST_BATCH_SIZE:
            try:
                batch.append(_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        try:
            await _persist_batch(batch)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to persist LLM usage batch", exc_info=True)
            await asyncio.sleep(_RETRY_BACKOFF_S)
            for event in batch:
                attempts = int(event.get("_persist_attempt", 0) or 0) + 1
                if attempts > _MAX_PERSIST_ATTEMPTS:
                    logger.error("Dropping LLM usage event after %d failed attempts", attempts - 1)
                    continue
                event["_persist_attempt"] = attempts
                try:
                    _queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.error("LLM usage queue full while retrying event")
        finally:
            for _ in batch:
                _queue.task_done()


async def start_llm_usage_persistence_worker() -> None:
    """Start background worker for persisting usage events."""
    global _queue, _queue_loop, _worker_task
    if _worker_task is not None:
        return
    _queue_loop = asyncio.get_running_loop()
    _queue = asyncio.Queue(maxsize=_QUEUE_MAX_SIZE)
    _worker_task = asyncio.create_task(_worker(), name="llm-usage-persist-worker")


async def stop_llm_usage_persistence_worker() -> None:
    """Flush and stop usage persistence worker."""
    global _queue, _queue_loop, _worker_task
    if _worker_task is None:
        return
    assert _queue is not None
    await _queue.join()
    _worker_task.cancel()
    with suppress(asyncio.CancelledError):
        await _worker_task
    _worker_task = None
    _queue = None
    _queue_loop = None


def enqueue_llm_usage_event(event: dict[str, Any]) -> None:
    """Enqueue usage event from any thread."""
    if _queue is None or _queue_loop is None:
        return

    def _enqueue() -> None:
        assert _queue is not None
        try:
            _queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("LLM usage queue full; dropping event")

    _queue_loop.call_soon_threadsafe(_enqueue)


async def prune_old_llm_usage_events(db: AsyncSession, *, retention_days: int) -> int:
    """Delete old persisted LLM usage events and return deleted row count."""
    if retention_days <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    result = await db.execute(delete(LLMUsageEvent).where(LLMUsageEvent.event_timestamp < cutoff))
    await db.commit()
    rowcount = getattr(result, "rowcount", 0)
    return int(rowcount or 0)


async def get_llm_usage_summary_db(db: AsyncSession, *, days: int = 30) -> dict[str, Any]:
    """Return aggregate usage summary from persisted telemetry."""
    stmt = select(
        LLMUsageEvent.task.label("task"),
        func.count(LLMUsageEvent.id).label("calls"),
        func.sum(case((LLMUsageEvent.success.is_(False), 1), else_=0)).label("errors"),
        func.sum(LLMUsageEvent.input_tokens).label("input_tokens"),
        func.sum(LLMUsageEvent.output_tokens).label("output_tokens"),
        func.sum(LLMUsageEvent.cost_usd).label("cost_usd"),
        func.avg(LLMUsageEvent.latency_ms).label("avg_latency_ms"),
    )
    if days > 0:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = stmt.where(LLMUsageEvent.event_timestamp >= cutoff)
    stmt = stmt.group_by(LLMUsageEvent.task).order_by(LLMUsageEvent.task)
    rows = (await db.execute(stmt)).all()

    tasks: dict[str, dict[str, float]] = {}
    total_calls = 0.0
    total_errors = 0.0
    total_cost = 0.0
    for row in rows:
        calls = float(row.calls or 0)
        errors = float(row.errors or 0)
        cost = float(row.cost_usd or 0.0)
        tasks[str(row.task)] = {
            "calls": calls,
            "errors": errors,
            "input_tokens": float(row.input_tokens or 0),
            "output_tokens": float(row.output_tokens or 0),
            "cost_usd": round(cost, 6),
            "avg_latency_ms": round(float(row.avg_latency_ms or 0.0), 2),
        }
        total_calls += calls
        total_errors += errors
        total_cost += cost

    return {
        "total_calls": total_calls,
        "total_errors": total_errors,
        "total_cost_usd": round(total_cost, 6),
        "tasks": tasks,
    }


async def get_recent_llm_usage_events_db(
    db: AsyncSession, *, limit: int = 100
) -> list[dict[str, Any]]:
    """Return persisted usage events (newest-first)."""
    clamped = max(1, min(limit, 500))
    rows = (
        await db.execute(select(LLMUsageEvent).order_by(desc(LLMUsageEvent.id)).limit(clamped))
    ).scalars()

    events: list[dict[str, Any]] = []
    for row in rows:
        events.append(
            {
                "timestamp": row.event_timestamp.isoformat(),
                "task": row.task,
                "provider": row.provider,
                "model": row.model,
                "success": row.success,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "cached_input_tokens": row.cached_input_tokens,
                "cache_creation_input_tokens": row.cache_creation_input_tokens,
                "latency_ms": row.latency_ms,
                "cost_usd": row.cost_usd,
                "error": row.error,
            }
        )
    return events


async def get_llm_usage_dashboard_db(db: AsyncSession, *, days: int = 30) -> dict[str, Any]:
    """Return dashboard-shaped usage aggregates for admin analytics views."""
    clamped_days = max(0, min(days, 365))
    stmt = select(LLMUsageEvent).order_by(LLMUsageEvent.event_timestamp.asc())
    if clamped_days > 0:
        cutoff = datetime.now(UTC) - timedelta(days=clamped_days)
        stmt = stmt.where(LLMUsageEvent.event_timestamp >= cutoff)
    rows = (await db.execute(stmt)).scalars().all()

    total_calls = float(len(rows))
    total_errors = float(sum(1 for row in rows if not row.success))
    total_cost = float(sum(float(row.cost_usd or 0.0) for row in rows))
    avg_latency = (
        float(sum(float(row.latency_ms or 0.0) for row in rows)) / total_calls
        if total_calls
        else 0.0
    )

    cost_timeseries: dict[str, dict[str, float]] = defaultdict(
        lambda: {"cost_usd": 0.0, "calls": 0.0}
    )
    by_model: dict[tuple[str, str], dict[str, float | str]] = defaultdict(
        lambda: {"provider": "", "model": "", "calls": 0.0, "cost_usd": 0.0}
    )
    by_task: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "calls": 0.0,
            "errors": 0.0,
            "cost_usd": 0.0,
            "latency_ms_sum": 0.0,
        }
    )
    task_model: dict[tuple[str, str, str], dict[str, float | str]] = defaultdict(
        lambda: {"task": "", "model": "", "provider": "", "calls": 0.0, "cost_usd": 0.0}
    )
    task_top_models: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for row in rows:
        date_key = row.event_timestamp.astimezone(UTC).date().isoformat()
        cost = float(row.cost_usd or 0.0)

        ts_slot = cost_timeseries[date_key]
        ts_slot["cost_usd"] += cost
        ts_slot["calls"] += 1.0

        mk = (row.provider, row.model)
        m_slot = by_model[mk]
        m_slot["provider"] = row.provider
        m_slot["model"] = row.model
        m_slot["calls"] = float(m_slot["calls"]) + 1.0
        m_slot["cost_usd"] = float(m_slot["cost_usd"]) + cost

        t_slot = by_task[row.task]
        t_slot["calls"] += 1.0
        t_slot["cost_usd"] += cost
        t_slot["latency_ms_sum"] += float(row.latency_ms or 0.0)
        if not row.success:
            t_slot["errors"] += 1.0

        tm_key = (row.task, row.provider, row.model)
        tm_slot = task_model[tm_key]
        tm_slot["task"] = row.task
        tm_slot["model"] = row.model
        tm_slot["provider"] = row.provider
        tm_slot["calls"] = float(tm_slot["calls"]) + 1.0
        tm_slot["cost_usd"] = float(tm_slot["cost_usd"]) + cost
        task_top_models[row.task][f"{row.provider}/{row.model}"] += cost

    timeseries_rows = [
        {
            "date": date_key,
            "calls": values["calls"],
            "cost_usd": round(values["cost_usd"], 6),
        }
        for date_key, values in sorted(cost_timeseries.items(), key=lambda item: item[0])
    ]

    model_rows: list[dict[str, float | str]] = [
        {
            "provider": str(values["provider"]),
            "model": str(values["model"]),
            "calls": float(values["calls"]),
            "cost_usd": round(float(values["cost_usd"]), 6),
        }
        for values in by_model.values()
    ]
    model_rows.sort(key=lambda item: float(item["calls"]), reverse=True)

    task_rows: list[dict[str, float | str]] = []
    for task, values in by_task.items():
        calls = float(values["calls"])
        errors = float(values["errors"])
        top_models = sorted(
            task_top_models[task].items(),
            key=lambda item: item[1],
            reverse=True,
        )[:2]
        task_rows.append(
            {
                "task": task,
                "calls": calls,
                "errors": errors,
                "error_rate": round((errors / calls) if calls else 0.0, 4),
                "cost_usd": round(float(values["cost_usd"]), 6),
                "avg_latency_ms": round(
                    (float(values["latency_ms_sum"]) / calls) if calls else 0.0,
                    2,
                ),
                "top_models": ", ".join(label for label, _ in top_models),
            }
        )

    task_rows.sort(key=lambda item: float(item["cost_usd"]), reverse=True)

    matrix_rows = sorted(
        [
            {
                "task": str(values["task"]),
                "provider": str(values["provider"]),
                "model": str(values["model"]),
                "calls": float(values["calls"]),
                "cost_usd": round(float(values["cost_usd"]), 6),
            }
            for values in task_model.values()
        ],
        key=lambda item: (item["task"], item["model"]),
    )

    return {
        "window_days": clamped_days,
        "kpis": {
            "total_calls": total_calls,
            "total_errors": total_errors,
            "error_rate": round((total_errors / total_calls) if total_calls else 0.0, 4),
            "total_cost_usd": round(total_cost, 6),
            "avg_latency_ms": round(avg_latency, 2),
        },
        "cost_timeseries": timeseries_rows,
        "calls_by_model": model_rows,
        "cost_by_task": task_rows,
        "task_model_cost_matrix": matrix_rows,
    }

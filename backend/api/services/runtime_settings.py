"""Persistent runtime settings and synchronization helpers."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime

from cataclysm.llm_gateway import set_routing_enabled_override, set_task_route_cache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import async_session_factory
from backend.api.db.models import LlmTaskRoute, RuntimeSetting

logger = logging.getLogger(__name__)

LLM_ROUTING_SETTING_KEY = "llm_routing_enabled"
_TRUE_VALUES = {"1", "true", "yes", "on"}

_worker_task: asyncio.Task[None] | None = None
_stop_event: asyncio.Event | None = None


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def _bool_to_str(value: bool) -> str:
    return "true" if value else "false"


def _apply_routing_state(enabled: bool, *, source: str) -> None:
    # Keep legacy env-based checks consistent with the runtime override.
    os.environ["LLM_ROUTING_ENABLED"] = "1" if enabled else "0"
    set_routing_enabled_override(enabled, source=source)


async def get_runtime_setting(db: AsyncSession, key: str) -> RuntimeSetting | None:
    """Fetch a runtime setting row by key."""
    return await db.get(RuntimeSetting, key)


async def get_runtime_setting_bool(db: AsyncSession, key: str, *, default: bool) -> bool:
    """Read a boolean runtime setting from string storage."""
    row = await get_runtime_setting(db, key)
    if row is None:
        return default
    return _parse_bool(row.value, default=default)


async def set_runtime_setting_bool(
    db: AsyncSession,
    key: str,
    enabled: bool,
    *,
    updated_by: str | None,
) -> RuntimeSetting:
    """Upsert a boolean runtime setting row."""
    row = await get_runtime_setting(db, key)
    if row is None:
        row = RuntimeSetting(key=key, value=_bool_to_str(enabled), updated_by=updated_by)
        db.add(row)
    else:
        row.value = _bool_to_str(enabled)
        row.updated_by = updated_by
    await db.flush()
    await db.refresh(row)
    return row


async def sync_llm_routing_setting_once(*, default_enabled: bool) -> dict[str, object]:
    """Load routing state from DB and apply it to process runtime state."""
    async with async_session_factory() as db:
        row = await db.get(RuntimeSetting, LLM_ROUTING_SETTING_KEY)

    if row is None:
        _apply_routing_state(default_enabled, source="default")
        return {
            "enabled": default_enabled,
            "source": "default",
            "updated_at": None,
        }

    enabled = _parse_bool(row.value, default=default_enabled)
    _apply_routing_state(enabled, source="db")
    return {
        "enabled": enabled,
        "source": "db",
        "updated_at": row.updated_at.isoformat() if isinstance(row.updated_at, datetime) else None,
    }


async def sync_task_routes_once() -> dict[str, list[dict[str, str]]]:
    """Load all per-task route configs from DB and apply to gateway cache."""
    async with async_session_factory() as db:
        result = await db.execute(select(LlmTaskRoute))
        rows = result.scalars().all()

    routes: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        try:
            config = json.loads(row.config_json)
            chain = config.get("chain", [])
            if isinstance(chain, list) and chain:
                routes[row.task] = chain
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Invalid route config for task %s", row.task)

    set_task_route_cache(routes)
    return routes


async def start_runtime_settings_sync(
    *,
    default_routing_enabled: bool,
    interval_s: float = 15.0,
) -> None:
    """Start periodic synchronization of runtime settings from DB."""
    global _worker_task, _stop_event

    if _worker_task is not None and not _worker_task.done():
        return

    _stop_event = asyncio.Event()

    async def _runner() -> None:
        while True:
            try:
                await sync_llm_routing_setting_once(default_enabled=default_routing_enabled)
            except Exception:
                logger.warning("Failed to sync runtime settings", exc_info=True)
            try:
                await sync_task_routes_once()
            except Exception:
                logger.warning("Failed to sync task routes", exc_info=True)
            assert _stop_event is not None
            try:
                await asyncio.wait_for(_stop_event.wait(), timeout=interval_s)
                break
            except TimeoutError:
                continue

    # Apply immediately before background loop settles.
    try:
        await sync_llm_routing_setting_once(default_enabled=default_routing_enabled)
    except Exception:
        logger.warning("Failed initial runtime settings sync; using defaults", exc_info=True)
        _apply_routing_state(default_routing_enabled, source="default")

    try:
        await sync_task_routes_once()
    except Exception:
        logger.warning("Failed initial task routes sync; using defaults", exc_info=True)

    _worker_task = asyncio.create_task(_runner(), name="runtime-settings-sync")


async def stop_runtime_settings_sync() -> None:
    """Stop periodic runtime settings synchronization."""
    global _worker_task, _stop_event

    if _worker_task is None:
        return

    if _stop_event is not None:
        _stop_event.set()

    try:
        await _worker_task
    finally:
        _worker_task = None
        _stop_event = None

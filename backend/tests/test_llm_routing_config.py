"""Tests for per-task LLM routing CRUD endpoints."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _mock_sync_task_routes() -> Generator[None, None, None]:
    """Mock sync_task_routes_once since it uses async_session_factory directly."""
    with patch(
        "backend.api.routers.admin.sync_task_routes_once",
        new_callable=AsyncMock,
    ):
        yield


@pytest.mark.asyncio
async def test_list_models_returns_registry(client: AsyncClient) -> None:
    resp = await client.get("/api/admin/llm-routing/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "tasks" in data
    assert "available_providers" in data
    assert len(data["models"]) >= 6
    assert "coaching_report" in data["tasks"]


@pytest.mark.asyncio
async def test_upsert_and_list_task_route(client: AsyncClient) -> None:
    chain = [
        {"provider": "openai", "model": "gpt-5-mini"},
        {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    ]
    resp = await client.put(
        "/api/admin/llm-routing/tasks/coaching_report",
        json={"chain": chain},
    )
    assert resp.status_code == 200
    assert resp.json()["task"] == "coaching_report"

    resp = await client.get("/api/admin/llm-routing/tasks")
    assert resp.status_code == 200
    configs = resp.json()["task_routes"]
    assert "coaching_report" in configs
    assert configs["coaching_report"]["chain"] == chain


@pytest.mark.asyncio
async def test_delete_task_route(client: AsyncClient) -> None:
    # Upsert first
    await client.put(
        "/api/admin/llm-routing/tasks/coaching_report",
        json={"chain": [{"provider": "openai", "model": "gpt-5-mini"}]},
    )
    # Delete
    resp = await client.delete("/api/admin/llm-routing/tasks/coaching_report")
    assert resp.status_code == 200

    # Verify gone
    resp = await client.get("/api/admin/llm-routing/tasks")
    assert "coaching_report" not in resp.json()["task_routes"]


@pytest.mark.asyncio
async def test_unknown_task_rejected(client: AsyncClient) -> None:
    resp = await client.put(
        "/api/admin/llm-routing/tasks/nonexistent_task",
        json={"chain": [{"provider": "anthropic", "model": "claude-haiku-4-5-20251001"}]},
    )
    assert resp.status_code == 400

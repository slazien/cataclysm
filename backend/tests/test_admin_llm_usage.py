"""Tests for persisted admin LLM usage endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.config import Settings
from backend.api.db.models import LLMUsageEvent
from backend.api.dependencies import AuthenticatedUser
from backend.api.routers.admin import require_admin


@pytest_asyncio.fixture
async def _seed_llm_usage_events(client: AsyncClient) -> None:
    from backend.api.db.database import get_db
    from backend.api.main import app

    db_gen = app.dependency_overrides[get_db]()
    db: AsyncSession = await db_gen.__anext__()

    base = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    db.add_all(
        [
            LLMUsageEvent(
                event_timestamp=base,
                task="coaching_report",
                provider="openai",
                model="gpt-5-mini",
                success=True,
                input_tokens=1200,
                output_tokens=300,
                cached_input_tokens=0,
                cache_creation_input_tokens=0,
                latency_ms=420.0,
                cost_usd=0.003,
                error=None,
            ),
            LLMUsageEvent(
                event_timestamp=base + timedelta(seconds=1),
                task="coaching_report",
                provider="openai",
                model="gpt-5-mini",
                success=False,
                input_tokens=0,
                output_tokens=0,
                cached_input_tokens=0,
                cache_creation_input_tokens=0,
                latency_ms=510.0,
                cost_usd=0.0,
                error="TimeoutError",
            ),
            LLMUsageEvent(
                event_timestamp=base + timedelta(seconds=2),
                task="topic_classifier",
                provider="google",
                model="gemini-2.5-flash-lite",
                success=True,
                input_tokens=40,
                output_tokens=10,
                cached_input_tokens=0,
                cache_creation_input_tokens=0,
                latency_ms=95.0,
                cost_usd=0.00001,
                error=None,
            ),
        ]
    )
    await db.commit()


@pytest.mark.asyncio
async def test_admin_llm_usage_summary_reads_persisted_data(
    client: AsyncClient,
    _seed_llm_usage_events: None,
) -> None:
    response = await client.get("/api/admin/llm-usage/summary", params={"days": 0})
    assert response.status_code == 200
    payload = response.json()

    assert payload["total_calls"] == 3.0
    assert payload["total_errors"] == 1.0
    assert payload["tasks"]["coaching_report"]["calls"] == 2.0
    assert payload["tasks"]["coaching_report"]["errors"] == 1.0
    assert payload["tasks"]["topic_classifier"]["calls"] == 1.0


@pytest.mark.asyncio
async def test_admin_llm_usage_events_reads_persisted_data_newest_first(
    client: AsyncClient,
    _seed_llm_usage_events: None,
) -> None:
    response = await client.get("/api/admin/llm-usage/events", params={"limit": 2})
    assert response.status_code == 200
    payload = response.json()

    events = payload["events"]
    assert len(events) == 2
    assert events[0]["task"] == "topic_classifier"
    assert events[1]["task"] == "coaching_report"


@pytest.mark.asyncio
async def test_admin_llm_usage_dashboard_returns_aggregates(
    client: AsyncClient,
    _seed_llm_usage_events: None,
) -> None:
    response = await client.get("/api/admin/llm-usage/dashboard", params={"days": 0})
    assert response.status_code == 200
    payload = response.json()

    assert payload["window_days"] == 0
    assert payload["kpis"]["total_calls"] == 3.0
    assert payload["kpis"]["total_errors"] == 1.0
    assert payload["kpis"]["total_cost_usd"] > 0.0
    assert len(payload["cost_timeseries"]) == 1
    assert len(payload["calls_by_model"]) == 2
    assert len(payload["cost_by_task"]) == 2
    assert len(payload["task_model_cost_matrix"]) == 2


@pytest.mark.asyncio
async def test_admin_llm_usage_dashboard_empty_window_is_safe(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/admin/llm-usage/dashboard", params={"days": 30})
    assert response.status_code == 200
    payload = response.json()

    assert payload["kpis"]["total_calls"] == 0.0
    assert payload["kpis"]["avg_latency_ms"] == 0.0
    assert payload["cost_timeseries"] == []
    assert payload["calls_by_model"] == []
    assert payload["cost_by_task"] == []
    assert payload["task_model_cost_matrix"] == []


@pytest.mark.asyncio
async def test_admin_llm_routing_status_toggle_persists_and_reads_back(
    client: AsyncClient,
) -> None:
    put_response = await client.put("/api/admin/llm-routing/status", json={"enabled": True})
    assert put_response.status_code == 200
    put_payload = put_response.json()
    assert put_payload["enabled"] is True
    assert put_payload["source"] == "db"
    assert put_payload["updated_by"] == "test@example.com"

    get_response = await client.get("/api/admin/llm-routing/status")
    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload["enabled"] is True
    assert get_payload["source"] == "db"
    assert get_payload["updated_by"] == "test@example.com"


@pytest.mark.asyncio
async def test_admin_me_returns_authenticated_admin_identity(client: AsyncClient) -> None:
    response = await client.get("/api/admin/me")
    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "test@example.com"
    assert payload["name"] == "Test Driver"


def test_require_admin_uses_configurable_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.api.routers import admin as admin_router

    monkeypatch.setattr(
        admin_router,
        "_SETTINGS",
        Settings(admin_allowlist_emails_raw="first@example.com,second@example.com"),
    )

    allowed = AuthenticatedUser(user_id="u1", email="second@example.com", name="Allowed")
    assert require_admin(allowed) == allowed

    blocked = AuthenticatedUser(user_id="u2", email="blocked@example.com", name="Blocked")
    with pytest.raises(HTTPException) as exc:
        require_admin(blocked)
    assert exc.value.status_code == 403

# LLM Per-Task Routing Config UI — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a UI section to `/admin/llm-dashboard` that lets the admin configure per-task primary model, ordered fallback chain, and see cost estimates — persisted to DB, applied at runtime.

**Architecture:** New `LlmTaskRoute` DB model stores per-task routing rules as JSON rows (one row per task). The gateway's `_route_for_task()` and `_fallback_for_task()` read from an in-memory cache that syncs from DB every 15s (same pattern as `runtime_settings`). Backend CRUD endpoints under `/api/admin/llm-routing/tasks`. Frontend adds a "Routing Config" card to the existing `LlmCostDashboard` component with per-task dropdowns and a drag-to-reorder fallback list.

**Tech Stack:** SQLAlchemy 2.0 (async), Alembic migration, FastAPI router, React + TanStack Query, `@dnd-kit/sortable` for drag-reorder.

---

## Available Models Registry

The gateway already knows these provider/model pairs (from `_estimate_cost_usd` and `_route_for_task`):

| Provider | Model ID | Display Name | Cost (in/out per 1M tokens) |
|----------|----------|--------------|---------------------------|
| anthropic | claude-haiku-4-5-20251001 | Haiku 4.5 | $1.00 / $5.00 |
| anthropic | claude-sonnet-4-6 | Sonnet 4.6 | $3.00 / $15.00 |
| openai | gpt-5-nano | GPT-5 Nano | $0.05 / $0.40 |
| openai | gpt-5-mini | GPT-5 Mini | $0.25 / $2.00 |
| google | gemini-2.5-flash-lite | Flash Lite | $0.10 / $0.40 |
| google | gemini-2.5-flash | Flash 2.5 | $0.30 / $2.50 |

Known task names: `coaching_report`, `coaching_chat`, `topic_classifier`, `coaching_validator`, `track_draft`, `share_comparison`.

---

## Task 1: DB Model + Migration

**Files:**
- Modify: `backend/api/db/models.py` — add `LlmTaskRoute`
- Create: `backend/api/db/migrations/versions/l2b3c4d5e6f7_add_llm_task_routes_table.py`

**Step 1: Add ORM model**

In `backend/api/db/models.py`, after the `RuntimeSetting` class:

```python
class LlmTaskRoute(Base):
    """Per-task LLM routing configuration persisted in Postgres."""

    __tablename__ = "llm_task_routes"

    task: Mapped[str] = mapped_column(String(100), primary_key=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`config_json` stores a JSON object:
```json
{
  "chain": [
    {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    {"provider": "openai", "model": "gpt-5-mini"},
    {"provider": "google", "model": "gemini-2.5-flash"}
  ]
}
```

First entry = primary, rest = ordered fallbacks. Empty chain = use caller defaults.

**Step 2: Create Alembic migration**

```python
"""Add llm_task_routes table.

Revision ID: l2b3c4d5e6f7
Revises: k1a2b3c4d5e6
"""
from alembic import op
import sqlalchemy as sa

revision = "l2b3c4d5e6f7"
down_revision = "k1a2b3c4d5e6"

def upgrade() -> None:
    op.create_table(
        "llm_task_routes",
        sa.Column("task", sa.String(100), primary_key=True),
        sa.Column("config_json", sa.Text, nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table("llm_task_routes")
```

**Step 3: Run migration locally, verify**

```bash
cd backend && alembic upgrade head
```

**Step 4: Commit**

```
feat(db): add llm_task_routes table for per-task routing config
```

---

## Task 2: Gateway Route Cache + Reader

**Files:**
- Modify: `cataclysm/llm_gateway.py` — add in-memory route cache, modify `_route_for_task` + `_fallback_for_task`
- Create: `tests/test_llm_routing_config.py`

**Step 1: Write failing tests**

```python
"""Tests for DB-backed per-task routing config."""
from __future__ import annotations

from cataclysm.llm_gateway import (
    get_task_route_chain,
    set_task_route_cache,
    _route_for_task,
    _fallback_for_task,
)


def test_empty_cache_returns_defaults() -> None:
    set_task_route_cache({})
    provider, model = _route_for_task("coaching_report", "anthropic", "claude-haiku-4-5-20251001")
    assert provider == "anthropic"
    assert model == "claude-haiku-4-5-20251001"


def test_cache_overrides_primary() -> None:
    set_task_route_cache({
        "coaching_report": [
            {"provider": "openai", "model": "gpt-5-mini"},
            {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
        ],
    })
    provider, model = _route_for_task("coaching_report", "anthropic", "claude-haiku-4-5-20251001")
    assert provider == "openai"
    assert model == "gpt-5-mini"


def test_fallback_from_cache_chain() -> None:
    set_task_route_cache({
        "coaching_report": [
            {"provider": "openai", "model": "gpt-5-mini"},
            {"provider": "google", "model": "gemini-2.5-flash"},
        ],
    })
    chain = get_task_route_chain("coaching_report", "anthropic", "claude-haiku-4-5-20251001")
    assert len(chain) == 2
    assert chain[0] == ("openai", "gpt-5-mini")
    assert chain[1] == ("google", "gemini-2.5-flash")


def test_unconfigured_task_uses_caller_defaults() -> None:
    set_task_route_cache({
        "coaching_report": [{"provider": "openai", "model": "gpt-5-mini"}],
    })
    # topic_classifier not configured → uses defaults
    provider, model = _route_for_task("topic_classifier", "anthropic", "claude-haiku-4-5-20251001")
    assert provider == "anthropic"
    assert model == "claude-haiku-4-5-20251001"


def test_get_chain_returns_default_when_no_cache() -> None:
    set_task_route_cache({})
    chain = get_task_route_chain("coaching_report", "anthropic", "claude-haiku-4-5-20251001")
    assert chain == [("anthropic", "claude-haiku-4-5-20251001")]
```

**Step 2: Implement gateway changes**

In `llm_gateway.py`, add:

```python
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
        (_normalize_provider(entry.get("provider"), default_provider), entry.get("model", default_model))
        for entry in chain_raw
    ]
```

Modify `_route_for_task()`:

```python
def _route_for_task(
    task: str, default_provider: Provider, default_model: str
) -> tuple[Provider, str]:
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
```

Modify `call_text_completion()` to use the full chain instead of just primary+fallback:

```python
# Replace the two-entry attempts list with:
chain = get_task_route_chain(task, default_provider, default_model)
if not chain:
    chain = [(default_provider, default_model)]
# If chain came from cache, use it. Otherwise, keep legacy env-var behavior.
with _TASK_ROUTE_LOCK:
    has_db_config = task in _TASK_ROUTE_CACHE
if has_db_config:
    attempts = chain
else:
    primary_provider, primary_model = _route_for_task(task, default_provider, default_model)
    fallback_provider, fallback_model = _fallback_for_task(task, default_provider, default_model)
    attempts = [(primary_provider, primary_model)]
    if (fallback_provider, fallback_model) != (primary_provider, primary_model):
        attempts.append((fallback_provider, fallback_model))
```

**Step 3: Run tests, verify pass**

```bash
pytest tests/test_llm_routing_config.py -v
```

**Step 4: Commit**

```
feat(gateway): add DB-backed per-task route cache with ordered fallback chain
```

---

## Task 3: Backend CRUD Endpoints

**Files:**
- Modify: `backend/api/routers/admin.py` — add GET/PUT/DELETE for task routes
- Modify: `backend/api/services/runtime_settings.py` — add route sync logic
- Create: `backend/tests/test_llm_routing_config.py`

**Step 1: Add route sync to `runtime_settings.py`**

```python
import json
from backend.api.db.models import LlmTaskRoute
from cataclysm.llm_gateway import set_task_route_cache
from sqlalchemy import select


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
```

Add `sync_task_routes_once()` call to the existing `_runner()` loop alongside `sync_llm_routing_setting_once()`.

**Step 2: Add admin endpoints to `admin.py`**

```python
from backend.api.db.models import LlmTaskRoute
from backend.api.services.runtime_settings import sync_task_routes_once

KNOWN_TASKS = [
    "coaching_report", "coaching_chat", "topic_classifier",
    "coaching_validator", "track_draft", "share_comparison",
]

MODEL_REGISTRY = [
    {"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "display": "Haiku 4.5", "cost_in": 1.0, "cost_out": 5.0},
    {"provider": "anthropic", "model": "claude-sonnet-4-6", "display": "Sonnet 4.6", "cost_in": 3.0, "cost_out": 15.0},
    {"provider": "openai", "model": "gpt-5-nano", "display": "GPT-5 Nano", "cost_in": 0.05, "cost_out": 0.4},
    {"provider": "openai", "model": "gpt-5-mini", "display": "GPT-5 Mini", "cost_in": 0.25, "cost_out": 2.0},
    {"provider": "google", "model": "gemini-2.5-flash-lite", "display": "Flash Lite", "cost_in": 0.10, "cost_out": 0.40},
    {"provider": "google", "model": "gemini-2.5-flash", "display": "Flash 2.5", "cost_in": 0.30, "cost_out": 2.50},
]


class TaskRoutePayload(BaseModel):
    chain: list[dict[str, str]]  # [{"provider": "...", "model": "..."}]


@router.get("/llm-routing/models")
async def list_available_models(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
) -> dict[str, Any]:
    """Return known models, tasks, and which providers have API keys configured."""
    available_providers = []
    for p in ["anthropic", "openai", "google"]:
        key_var = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY"}[p]
        if os.environ.get(key_var):
            available_providers.append(p)
    return {
        "models": MODEL_REGISTRY,
        "tasks": KNOWN_TASKS,
        "available_providers": available_providers,
    }


@router.get("/llm-routing/tasks")
async def list_task_routes(
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Return all per-task routing configurations."""
    result = await db.execute(select(LlmTaskRoute))
    rows = result.scalars().all()
    configs = {}
    for row in rows:
        try:
            configs[row.task] = json.loads(row.config_json)
        except json.JSONDecodeError:
            configs[row.task] = {"chain": []}
    return {"task_routes": configs, "tasks": KNOWN_TASKS}


@router.put("/llm-routing/tasks/{task}")
async def upsert_task_route(
    task: str,
    payload: TaskRoutePayload,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Create or update routing config for a specific task."""
    if task not in KNOWN_TASKS:
        raise HTTPException(400, f"Unknown task: {task}")

    config_json = json.dumps({"chain": payload.chain})
    row = await db.get(LlmTaskRoute, task)
    if row is None:
        row = LlmTaskRoute(task=task, config_json=config_json, updated_by=user.email)
        db.add(row)
    else:
        row.config_json = config_json
        row.updated_by = user.email
    await db.commit()

    # Immediately apply to gateway cache
    await sync_task_routes_once()
    return {"task": task, "config": {"chain": payload.chain}}


@router.delete("/llm-routing/tasks/{task}")
async def delete_task_route(
    task: str,
    _user: Annotated[AuthenticatedUser, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Remove per-task routing config (revert to caller defaults)."""
    row = await db.get(LlmTaskRoute, task)
    if row is not None:
        await db.delete(row)
        await db.commit()
    await sync_task_routes_once()
    return {"status": "deleted", "task": task}
```

**Step 3: Write backend tests**

```python
"""Tests for per-task routing CRUD endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_models_returns_registry(admin_client: AsyncClient) -> None:
    resp = await admin_client.get("/api/admin/llm-routing/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "tasks" in data
    assert "available_providers" in data
    assert len(data["models"]) >= 6
    assert "coaching_report" in data["tasks"]


@pytest.mark.anyio
async def test_upsert_and_list_task_route(admin_client: AsyncClient) -> None:
    chain = [
        {"provider": "openai", "model": "gpt-5-mini"},
        {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    ]
    resp = await admin_client.put(
        "/api/admin/llm-routing/tasks/coaching_report",
        json={"chain": chain},
    )
    assert resp.status_code == 200

    resp = await admin_client.get("/api/admin/llm-routing/tasks")
    assert resp.status_code == 200
    configs = resp.json()["task_routes"]
    assert "coaching_report" in configs
    assert configs["coaching_report"]["chain"] == chain


@pytest.mark.anyio
async def test_delete_task_route(admin_client: AsyncClient) -> None:
    # Upsert first
    await admin_client.put(
        "/api/admin/llm-routing/tasks/coaching_report",
        json={"chain": [{"provider": "openai", "model": "gpt-5-mini"}]},
    )
    # Delete
    resp = await admin_client.delete("/api/admin/llm-routing/tasks/coaching_report")
    assert resp.status_code == 200

    # Verify gone
    resp = await admin_client.get("/api/admin/llm-routing/tasks")
    assert "coaching_report" not in resp.json()["task_routes"]


@pytest.mark.anyio
async def test_unknown_task_rejected(admin_client: AsyncClient) -> None:
    resp = await admin_client.put(
        "/api/admin/llm-routing/tasks/nonexistent_task",
        json={"chain": [{"provider": "anthropic", "model": "claude-haiku-4-5-20251001"}]},
    )
    assert resp.status_code == 400
```

**Step 4: Commit**

```
feat(api): add per-task LLM routing CRUD endpoints + DB sync
```

---

## Task 4: Frontend API Layer

**Files:**
- Modify: `frontend/src/lib/admin-api.ts` — add types + fetch functions

**Step 1: Add types and API functions**

```typescript
export interface LlmModelInfo {
  provider: string;
  model: string;
  display: string;
  cost_in: number;
  cost_out: number;
}

export interface LlmRouteEntry {
  provider: string;
  model: string;
}

export interface LlmModelsResponse {
  models: LlmModelInfo[];
  tasks: string[];
  available_providers: string[];
}

export interface LlmTaskRoutesResponse {
  task_routes: Record<string, { chain: LlmRouteEntry[] }>;
  tasks: string[];
}

export async function getLlmModels(): Promise<LlmModelsResponse> {
  return fetchApi("/api/admin/llm-routing/models");
}

export async function getLlmTaskRoutes(): Promise<LlmTaskRoutesResponse> {
  return fetchApi("/api/admin/llm-routing/tasks");
}

export async function setLlmTaskRoute(
  task: string,
  chain: LlmRouteEntry[],
): Promise<{ task: string; config: { chain: LlmRouteEntry[] } }> {
  return fetchApi(`/api/admin/llm-routing/tasks/${task}`, {
    method: "PUT",
    body: JSON.stringify({ chain }),
  });
}

export async function deleteLlmTaskRoute(
  task: string,
): Promise<{ status: string; task: string }> {
  return fetchApi(`/api/admin/llm-routing/tasks/${task}`, {
    method: "DELETE",
  });
}
```

**Step 2: Commit**

```
feat(frontend): add LLM routing config API types and functions
```

---

## Task 5: Routing Config UI Component

**Files:**
- Create: `frontend/src/components/admin/TaskRoutingConfig.tsx`
- Modify: `frontend/src/components/admin/LlmCostDashboard.tsx` — integrate new component

**Step 1: Install dnd-kit**

```bash
cd frontend && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

**Step 2: Create `TaskRoutingConfig.tsx`**

This component renders:
- One expandable row per known task
- Inside each row: a sortable list of model entries (drag to reorder)
- An "Add fallback" dropdown to append a new model to the chain
- A "Reset to default" button to delete the DB config
- Cost estimate badges next to each model
- Visual indicator showing which providers have API keys configured

Key UX:
- Each task row shows current primary model or "Default (Haiku 4.5)" if unconfigured
- Expanding shows the full chain with drag handles
- Changes save immediately on drop/add/remove (optimistic update)
- Disabled models (no API key) shown grayed out with "No key" badge

```typescript
// Core component structure (implement fully):
// - useQuery for getLlmModels() and getLlmTaskRoutes()
// - useMutation for setLlmTaskRoute() and deleteLlmTaskRoute()
// - DndContext + SortableContext for drag-reorder
// - Each chain entry: drag handle | provider badge | model name | cost | remove button
// - "Add model" dropdown filtered to exclude already-in-chain models
// - Save triggers on: drag end, add, remove
```

**Step 3: Integrate into `LlmCostDashboard.tsx`**

Add the `<TaskRoutingConfig />` component as a new `<Card>` section between the header and the KPI cards:

```tsx
<section>
  <Card className="border-slate-700/40 bg-slate-900/70 py-4">
    <CardHeader className="px-4 pb-2">
      <CardTitle className="text-base">Task Routing Configuration</CardTitle>
      <CardDescription>Configure primary model and fallback chain per task.</CardDescription>
    </CardHeader>
    <CardContent className="px-4">
      <TaskRoutingConfig />
    </CardContent>
  </Card>
</section>
```

**Step 4: Commit**

```
feat(frontend): add per-task routing config UI with drag-reorder fallback chains
```

---

## Task 6: TypeScript Check + Quality Gates

**Step 1:** `cd frontend && npx tsc --noEmit`
**Step 2:** `ruff format && ruff check` on all changed Python files
**Step 3:** `dmypy run` on changed gateway/admin files
**Step 4:** `pytest tests/test_llm_routing_config.py backend/tests/test_llm_routing_config.py -v`
**Step 5:** Full test suite: `pytest tests/ backend/tests/ -v -n auto`
**Step 6:** Code review via `superpowers:code-reviewer`
**Step 7:** Commit any fixes

```
chore: quality gates pass for LLM routing config feature
```

---

## Task 7: Deploy + Visual QA

**Step 1:** Push to staging
**Step 2:** Wait ~2-3 min for Railway deploy
**Step 3:** Check Railway build logs for both services
**Step 4:** Playwright visual QA on `/admin/llm-dashboard`:
  - Verify "Task Routing Configuration" card renders
  - Expand a task → see "Default" state
  - Select a model → verify it appears as primary
  - Add a fallback → drag reorder → verify order persisted
  - Delete config → verify reverts to "Default"
  - Check mobile viewport (360px) — card should stack cleanly

```
chore: deploy and verify LLM routing config UI on staging
```

---

## Implementation Notes

- **DB-backed config takes priority** over env-var routing. This means the admin UI is the single source of truth when configured. Env vars are legacy fallback.
- **15s sync interval** means changes are eventually consistent across multiple backend instances. The `upsert_task_route` endpoint forces an immediate sync for the instance that handles the request.
- **No API key = model disabled** in the UI. The `/models` endpoint returns `available_providers` so the frontend can gray out models whose provider has no key.
- **Chain semantics**: First entry = primary. Gateway tries each entry in order, skipping any whose provider has no API key. If all fail, the original `call_text_completion` error handling applies.
- **Empty chain = caller defaults**. Deleting a task route makes the gateway fall through to the hardcoded defaults in each caller file (Haiku for coaching, etc.).

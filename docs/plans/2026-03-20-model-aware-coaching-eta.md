# Model-Aware Coaching ETA Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the coaching progress bar ETA model-aware by querying historical per-model latency from the DB, with fallback to in-memory average → 60s default.

**Architecture:** Add `get_task_median_latency_s()` async DB query to `llm_usage_store.py`. Make `_generating_response()` in coaching router async, resolve the currently-routed model via `get_task_route_chain()`, try DB median first, fall back to existing in-memory `get_estimated_duration_s()`.

**Tech Stack:** SQLAlchemy async, PostgreSQL `LLMUsageEvent` table, existing `llm_gateway` routing resolution

---

### Task 1: Add `get_task_median_latency_s` to llm_usage_store

**Files:**
- Modify: `backend/api/services/llm_usage_store.py:231-239` (insert before `get_llm_usage_dashboard_db`)
- Test: `backend/tests/test_admin_llm_usage.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_admin_llm_usage.py`:

```python
@pytest.mark.asyncio
async def test_get_task_median_latency_s_returns_median(db_session: AsyncSession) -> None:
    """Median latency from recent successful events for a specific task+model."""
    from backend.api.services.llm_usage_store import get_task_median_latency_s

    base = datetime.now(UTC)
    events = [
        LLMUsageEvent(
            event_timestamp=base - timedelta(seconds=i),
            task="coaching_report",
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            success=True,
            input_tokens=100,
            output_tokens=100,
            cached_input_tokens=0,
            cache_creation_input_tokens=0,
            latency_ms=ms,
            cost_usd=0.01,
        )
        for i, ms in enumerate([10000, 20000, 30000, 40000, 50000])
    ]
    db_session.add_all(events)
    await db_session.flush()

    result = await get_task_median_latency_s(db_session, "coaching_report", "claude-haiku-4-5-20251001")
    assert result is not None
    # Median of [10000, 20000, 30000, 40000, 50000] ms = 30000 ms = 30.0 s
    assert result == 30.0


@pytest.mark.asyncio
async def test_get_task_median_latency_s_no_data(db_session: AsyncSession) -> None:
    """Returns None when no matching events exist."""
    from backend.api.services.llm_usage_store import get_task_median_latency_s

    result = await get_task_median_latency_s(db_session, "coaching_report", "nonexistent-model")
    assert result is None


@pytest.mark.asyncio
async def test_get_task_median_latency_s_ignores_failures(db_session: AsyncSession) -> None:
    """Only successful events are included in the median."""
    from backend.api.services.llm_usage_store import get_task_median_latency_s

    base = datetime.now(UTC)
    db_session.add_all([
        LLMUsageEvent(
            event_timestamp=base,
            task="coaching_report",
            provider="anthropic",
            model="test-model",
            success=True,
            input_tokens=100,
            output_tokens=100,
            cached_input_tokens=0,
            cache_creation_input_tokens=0,
            latency_ms=5000,
            cost_usd=0.01,
        ),
        LLMUsageEvent(
            event_timestamp=base - timedelta(seconds=1),
            task="coaching_report",
            provider="anthropic",
            model="test-model",
            success=False,
            input_tokens=100,
            output_tokens=0,
            cached_input_tokens=0,
            cache_creation_input_tokens=0,
            latency_ms=120000,
            cost_usd=0.0,
            error="timeout",
        ),
    ])
    await db_session.flush()

    result = await get_task_median_latency_s(db_session, "coaching_report", "test-model")
    assert result is not None
    assert result == 5.0  # Only the successful 5000ms event


@pytest.mark.asyncio
async def test_get_task_median_latency_s_filters_by_model(db_session: AsyncSession) -> None:
    """Events for different models are not mixed."""
    from backend.api.services.llm_usage_store import get_task_median_latency_s

    base = datetime.now(UTC)
    db_session.add_all([
        LLMUsageEvent(
            event_timestamp=base,
            task="coaching_report",
            provider="anthropic",
            model="model-a",
            success=True,
            input_tokens=100,
            output_tokens=100,
            cached_input_tokens=0,
            cache_creation_input_tokens=0,
            latency_ms=10000,
            cost_usd=0.01,
        ),
        LLMUsageEvent(
            event_timestamp=base - timedelta(seconds=1),
            task="coaching_report",
            provider="openai",
            model="model-b",
            success=True,
            input_tokens=100,
            output_tokens=100,
            cached_input_tokens=0,
            cache_creation_input_tokens=0,
            latency_ms=50000,
            cost_usd=0.01,
        ),
    ])
    await db_session.flush()

    result_a = await get_task_median_latency_s(db_session, "coaching_report", "model-a")
    result_b = await get_task_median_latency_s(db_session, "coaching_report", "model-b")
    assert result_a == 10.0
    assert result_b == 50.0
```

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_admin_llm_usage.py -v -k "median_latency"`
Expected: FAIL with `ImportError` — `get_task_median_latency_s` doesn't exist yet.

**Step 3: Write the implementation**

Insert in `backend/api/services/llm_usage_store.py` before line 241 (`get_llm_usage_dashboard_db`):

```python
async def get_task_median_latency_s(
    db: AsyncSession,
    task: str,
    model: str,
    *,
    limit: int = 50,
) -> float | None:
    """Return median latency (seconds) for a task+model from recent successful events.

    Returns None if no matching events exist.
    """
    stmt = (
        select(LLMUsageEvent.latency_ms)
        .where(
            LLMUsageEvent.task == task,
            LLMUsageEvent.model == model,
            LLMUsageEvent.success.is_(True),
        )
        .order_by(LLMUsageEvent.event_timestamp.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return None
    sorted_ms = sorted(rows)
    median_ms = _percentile(sorted_ms, 0.50)
    return round(median_ms / 1000.0, 1)
```

**Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_admin_llm_usage.py -v -k "median_latency"`
Expected: All 4 PASS.

**Step 5: Commit**

```bash
git add backend/api/services/llm_usage_store.py backend/tests/test_admin_llm_usage.py
git commit -m "feat: add get_task_median_latency_s for model-aware ETA"
```

---

### Task 2: Wire DB median into `_generating_response`

**Files:**
- Modify: `backend/api/routers/coaching.py:143-157` (`_generating_response`)

**Step 1: Update `_generating_response` to be async and accept db**

Replace lines 143-157 with:

```python
async def _generating_response(
    session_id: str,
    skill_level: str,
    remaining: int,
    db: AsyncSession,
) -> CoachingReportResponse:
    """Build a standard 'generating' response with model-aware ETA.

    Fallback chain: DB median (per-model) → in-memory average → 60s default.
    """
    started = get_generation_started_at(session_id, skill_level)

    # Resolve the currently-routed model for coaching_report
    chain = get_task_route_chain("coaching_report", "anthropic", "claude-haiku-4-5-20251001")
    _provider, model = chain[0]

    # Try DB-backed median first
    estimated_s: float | None = None
    try:
        estimated_s = await get_task_median_latency_s(db, "coaching_report", model)
    except Exception:  # noqa: BLE001
        logger.debug("DB median latency lookup failed, using in-memory fallback")

    # Fallback to in-memory average, then default
    if estimated_s is None:
        estimated_s = get_estimated_duration_s()

    return CoachingReportResponse(
        session_id=session_id,
        status="generating",
        regen_remaining=remaining,
        regen_max=MAX_DAILY_REGENS,
        generation_started_at=started.isoformat() if started else None,
        generation_estimated_s=estimated_s,
    )
```

**Step 2: Add imports at top of `coaching.py`**

Add to the existing imports:

```python
from cataclysm.llm_gateway import get_task_route_chain
from backend.api.services.llm_usage_store import get_task_median_latency_s
```

**Step 3: Update all 3 call sites to pass `db` and `await`**

Line ~242 (POST generate_report, already-generating early return):
```python
        return await _generating_response(session_id, body.skill_level, remaining, db)
```

Line ~270 (POST generate_report, after mark_generating):
```python
    return await _generating_response(session_id, body.skill_level, remaining, db)
```

Line ~631 (GET get_report):
```python
        return await _generating_response(session_id, skill_level, remaining, db)
```

**Step 4: Run quality gates**

Run: `ruff check backend/api/routers/coaching.py` and `dmypy run -- backend/`
Expected: No errors.

**Step 5: Commit**

```bash
git add backend/api/routers/coaching.py
git commit -m "feat: wire model-aware DB median into coaching ETA response"
```

---

### Task 3: Integration test for fallback chain

**Files:**
- Test: `backend/tests/test_coaching_extended.py`

**Step 1: Add integration test**

Add to `TestCoachingStoreMissingLines` class (or a new class after it):

```python
class TestModelAwareEta:
    """Test the model-aware ETA fallback chain in _generating_response."""

    @pytest.mark.asyncio
    async def test_generating_response_uses_db_median(self, db_session: AsyncSession) -> None:
        """When DB has latency data for the routed model, use it."""
        from backend.api.services.llm_usage_store import get_task_median_latency_s

        base = datetime.now(UTC)
        db_session.add_all([
            LLMUsageEvent(
                event_timestamp=base - timedelta(seconds=i),
                task="coaching_report",
                provider="anthropic",
                model="claude-haiku-4-5-20251001",
                success=True,
                input_tokens=100,
                output_tokens=100,
                cached_input_tokens=0,
                cache_creation_input_tokens=0,
                latency_ms=ms,
                cost_usd=0.01,
            )
            for i, ms in enumerate([8000, 12000, 10000])
        ])
        await db_session.flush()

        result = await get_task_median_latency_s(
            db_session, "coaching_report", "claude-haiku-4-5-20251001"
        )
        assert result is not None
        assert result == 10.0  # median of [8000, 10000, 12000] ms

    def test_inmemory_fallback_still_works(self) -> None:
        """In-memory average remains as middle fallback."""
        from backend.api.services.coaching_store import (
            get_estimated_duration_s,
            record_generation_duration,
        )

        clear_all_coaching()
        record_generation_duration(15.0)
        record_generation_duration(25.0)
        assert get_estimated_duration_s() == 20.0
        clear_all_coaching()

    def test_default_fallback(self) -> None:
        """When no DB data and no in-memory data, returns 60s default."""
        from backend.api.services.coaching_store import get_estimated_duration_s

        clear_all_coaching()
        assert get_estimated_duration_s() == 60.0
        clear_all_coaching()
```

**Step 2: Run tests**

Run: `pytest backend/tests/test_coaching_extended.py -v -k "ModelAwareEta"`
Expected: All 3 PASS.

**Step 3: Commit**

```bash
git add backend/tests/test_coaching_extended.py
git commit -m "test: add model-aware ETA fallback chain tests"
```

---

### Task 4: Full quality gates

**Step 1: Run ruff**

```bash
ruff format cataclysm/ tests/ backend/ && ruff check cataclysm/ tests/ backend/
```

**Step 2: Run mypy**

```bash
dmypy run -- cataclysm/ backend/
```

**Step 3: Run full test suite**

```bash
pytest tests/ backend/tests/ -v -n auto
```

**Step 4: Fix any issues**

All gates must pass. Fix all errors including pre-existing.

**Step 5: Final commit if any fixes needed**

```bash
git add -u
git commit -m "fix: quality gate fixes for model-aware ETA"
```

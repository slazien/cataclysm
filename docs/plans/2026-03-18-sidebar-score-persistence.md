# Sidebar Score Persistence Fix

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make session scores persist across backend restarts and update the sidebar live when coaching finishes.

**Architecture:** Scores are currently computed on-the-fly from in-memory `SessionData`. After any deploy/restart, sessions evict from RAM and the `list_sessions` DB fallback path returns `None` for all four score fields because the `Session` table has no score columns. Fix: persist computed scores into the existing `snapshot_json` JSONB column (no migration needed — follows the same pattern as weather/GPS data). Frontend: invalidate `["sessions"]` query when coaching transitions to `"ready"`.

**Tech Stack:** Python/FastAPI (backend), React Query (frontend)

---

### Task 1: Backend — Read scores from `snapshot_json` in DB fallback path

**Files:**
- Modify: `backend/api/routers/sessions.py` (Path B in `list_sessions`, lines ~622-651)

**Step 1: Add score reading in Path B**

In `list_sessions`, the `else` branch (session not in memory) builds `SessionSummary` from DB row. Currently omits all score fields. Read them from `snapshot_json`:

```python
# Inside the else branch, after existing snap = row.snapshot_json or {}
score_data = snap.get("scores")
```

Then pass into the `SessionSummary` constructor:

```python
session_score=score_data.get("total") if score_data else None,
score_consistency=score_data.get("consistency") if score_data else None,
score_pace=score_data.get("pace") if score_data else None,
score_technique=score_data.get("technique") if score_data else None,
optimal_lap_time_s=score_data.get("optimal_lap_time_s") if score_data else None,
```

Also read equipment fields from snapshot:

```python
eq_data = snap.get("equipment")
```

And pass:

```python
tire_model=eq_data.get("tire_model") if eq_data else None,
compound_category=eq_data.get("compound_category") if eq_data else None,
equipment_profile_name=eq_data.get("profile_name") if eq_data else None,
```

**Step 2: Run tests**

Run: `pytest tests/ backend/tests/ -v -n auto -x`
Expected: All existing tests pass (no behavior change yet — no scores in snapshot_json to read).

**Step 3: Commit**

```bash
git add backend/api/routers/sessions.py
git commit -m "fix: read scores and equipment from snapshot_json in DB fallback path"
```

---

### Task 2: Backend — Persist scores to `snapshot_json` in list_sessions Path A

**Files:**
- Modify: `backend/api/routers/sessions.py` (Path A in `list_sessions`, lines ~581-621)

**Step 1: Add helper to persist scores**

Add a module-level helper near `_compute_session_score`:

```python
async def _persist_sidebar_fields(
    db: AsyncSession,
    session_id: str,
    score: ScoreResult,
    tire_model: str | None,
    compound_category: str | None,
    profile_name: str | None,
) -> None:
    """Write sidebar-visible fields to snapshot_json so they survive restarts."""
    from backend.api.services.db_session_store import get_session_row

    row = await get_session_row(db, session_id)
    if row is None:
        return
    snap = dict(row.snapshot_json or {})
    new_scores = {
        "total": score.total,
        "consistency": score.consistency,
        "pace": score.pace,
        "technique": score.technique,
        "optimal_lap_time_s": score.optimal_lap_time_s,
    }
    new_eq = {
        "tire_model": tire_model,
        "compound_category": compound_category,
        "profile_name": profile_name,
    }
    # Only write if changed (avoid unnecessary DB writes)
    if snap.get("scores") != new_scores or snap.get("equipment") != new_eq:
        snap["scores"] = new_scores
        snap["equipment"] = new_eq
        row.snapshot_json = snap
        await db.commit()
```

**Step 2: Call helper in Path A (fire-and-forget)**

After the `items.append(SessionSummary(...))` in Path A, persist scores in the background. Since we're already in an async context with `db`, wrap in a try/except to not break the list response:

```python
# After appending the SessionSummary in Path A:
try:
    await _persist_sidebar_fields(
        db, sd.session_id, score,
        tire_model, compound_category, profile_name,
    )
except Exception:
    logger.debug("Failed to persist sidebar fields for %s", sd.session_id, exc_info=True)
```

**Important**: The `db` session is shared across the loop. Each `_persist_sidebar_fields` call may commit. This is OK — weather backfill already does this pattern in the same endpoint.

**Step 3: Run tests**

Run: `pytest tests/ backend/tests/ -v -n auto -x`

**Step 4: Commit**

```bash
git add backend/api/routers/sessions.py
git commit -m "fix: persist scores to snapshot_json when sessions are in memory"
```

---

### Task 3: Backend — Persist scores after coaching generation completes

**Files:**
- Modify: `backend/api/routers/coaching.py` (end of `_run_generation`, after `store_coaching_report`)

**Step 1: Add score persistence after coaching completes**

After `await store_coaching_report(session_id, response, skill_level)` and the log line, add:

```python
# Persist scores to snapshot_json so sidebar shows them after restart
try:
    from backend.api.db.database import async_session_factory
    from backend.api.routers.sessions import _compute_session_score, _persist_sidebar_fields
    from backend.api.services import equipment_store

    score = await _compute_session_score(sd)
    tire_model, compound_category, profile_name = None, None, None
    se = equipment_store.get_session_equipment(session_id)
    if se is not None:
        tire_model = se.tire_compound or None
        profile = equipment_store.get_profile(se.profile_id)
        if profile:
            profile_name = profile.name
            compound_category = profile.compound_category

    async with async_session_factory() as db_session:
        await _persist_sidebar_fields(
            db_session, session_id, score,
            tire_model, compound_category, profile_name,
        )
except Exception:
    logger.debug("Failed to persist scores after coaching for %s", session_id, exc_info=True)
```

**Note**: `_run_generation` is a background task without its own DB session, so we create one via `async_session_factory`. The `_equipment_fields` helper in `sessions.py` is private; replicate the logic or extract it. Check `_equipment_fields` for the exact field extraction pattern and match it.

**Step 2: Run tests**

Run: `pytest tests/ backend/tests/ -v -n auto -x`

**Step 3: Commit**

```bash
git add backend/api/routers/coaching.py
git commit -m "fix: persist scores to snapshot_json after coaching generation"
```

---

### Task 4: Frontend — Invalidate `["sessions"]` when coaching transitions to `"ready"`

**Files:**
- Modify: `frontend/src/hooks/useAutoReport.ts`

**Step 1: Add sessions invalidation on coaching ready**

Add a `useEffect` that detects when `isReady` transitions to `true` and invalidates the sessions list query:

```typescript
// Inside useAutoReport, after the existing useEffect hooks:
const wasReady = useRef(false);

useEffect(() => {
  if (isReady && !wasReady.current) {
    // Coaching just transitioned to ready — update sidebar scores
    void queryClient.invalidateQueries({ queryKey: ['sessions'] });
  }
  wasReady.current = isReady;
}, [isReady, queryClient]);
```

**Important**: The `wasReady` ref prevents re-invalidation on every render when the report is already ready. It only fires on the `false → true` transition.

Also reset `wasReady` when session changes (alongside existing `hasTriggered` reset):

```typescript
// In the existing session change reset effect:
useEffect(() => {
  hasTriggered.current = false;
  wasReady.current = false;
}, [sessionId]);
```

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

**Step 3: Commit**

```bash
git add frontend/src/hooks/useAutoReport.ts
git commit -m "fix: invalidate sessions query when coaching report is ready"
```

---

### Task 5: Quality gates

**Step 1: Backend linting + types**

```bash
ruff format cataclysm/ tests/ backend/
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
```

**Step 2: Full test suite**

```bash
pytest tests/ backend/tests/ -v -n auto
```

**Step 3: Frontend type check**

```bash
cd frontend && npx tsc --noEmit
```

**Step 4: Code review**

Use `superpowers:code-reviewer` on all changed files.

**Step 5: Push to staging**

```bash
git push origin temp/sidebar-scores:staging
```

**Step 6: Verify Railway deploy**

Wait ~2-3 min. Check `list-deployments` for both services. Get logs to confirm no errors.

**Step 7: Visual QA**

Use Playwright to:
1. Open staging → verify sidebar shows scores for sessions
2. Upload a new CSV → wait for coaching → verify sidebar score appears without refresh

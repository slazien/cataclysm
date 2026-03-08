# Physics Track-Level Cache + Coaching Shimmer Fix

**Date:** 2026-03-08
**Status:** Approved

## Problem

1. **Physics cache not shared across sessions**: Optimal profile computation (~8s) is keyed by `(session_id, endpoint, profile_id)`. Two sessions on the same track with the same equipment recompute independently, even though the optimal profile is ~99% determined by track geometry + vehicle params.

2. **Coaching shimmer persists until refresh**: When a coaching report is generated for the first time, the frontend polling (`refetchInterval`) stops permanently after a single transient network error because `data` becomes `undefined` → callback returns `false`. Additionally, the backend error path stores error reports under default `skill_level="intermediate"` regardless of actual skill level.

## Design

### Fix 1: Track-Level Physics Cache

#### Cache Key Structure

| Tier | Key | Used by | Shared? |
|------|-----|---------|---------|
| Track-level | `(track_slug, "profile", profile_id, calibrated_mu_2dp)` | `get_optimal_profile_data()` | All sessions on same track |
| Session-level | `(session_id, "comparison", profile_id)` | `get_optimal_comparison_data()` | Per-session (unchanged) |

`calibrated_mu_2dp` = final mu rounded to 2 decimals. Sessions with near-identical grip calibration share cache; materially different conditions (wet vs dry) get separate entries.

#### Flow: `get_optimal_profile_data()`

1. Resolve `track_slug` from `session_data.layout` (unknown track → session-keyed fallback)
2. Capture `profile_id`, `vehicle_params`, `mu_cap`
3. Run grip calibration to get final `vehicle_params.mu` (cheap, ~1ms)
4. Build track-level cache key: `(track_slug, "profile", profile_id, round(mu, 2))`
5. Check in-memory cache → DB cache
6. HIT → return (no solver)
7. MISS → solve velocity model, store in track-level cache

Calibration is hoisted before the cache check (currently inside `_compute()`). The calibration is the cheap part (~1ms percentile math); the expensive part is the velocity solver (~5-8s).

#### Flow: `get_optimal_comparison_data()`

1. Call `get_optimal_profile_data()` → cached optimal profile (near-instant on hit)
2. Deserialize `OptimalProfile` from cached dict
3. Run `compare_with_optimal(best_lap_df, corners, optimal)` (~50ms)
4. Cache comparison result per-session as before

This eliminates the redundant velocity solver call inside comparison.

#### DB Schema

Add to `PhysicsCacheEntry`:
- `track_slug: String(64), nullable=True, indexed`

Existing entries: `track_slug=NULL` → treated as session-level (backward compat).
New track-level entries: `track_slug` populated, included in DB lookup WHERE clause.

#### Invalidation

| Trigger | Invalidates |
|---------|------------|
| Equipment profile edit/delete | All entries for that profile_id (existing) |
| Physics code version bump | All stale entries on read (existing) |
| Track reference update | NEW: all track-level entries for that track_slug |
| Session delete | Session-level comparison entries (existing) |

#### Unknown Tracks (no layout)

When `session_data.layout is None`, the optimal profile depends on per-session GPS curvature. These stay session-keyed as today — no track-level sharing possible without a canonical reference.

### Fix 2: Coaching Shimmer

#### Frontend (`useCoaching.ts`)

```typescript
refetchInterval: (query) => {
  const { data, status } = query.state;
  if (data?.status === "generating") return 2000;
  if (status === "error") return 3000;
  return false;
},
retry: 1,  // one automatic retry before error state
```

#### Backend (`coaching.py`)

Pass `skill_level` to `store_coaching_report` in the error path:

```python
except Exception:
    await store_coaching_report(
        session_id,
        CoachingReportResponse(session_id=session_id, status="error", summary="..."),
        skill_level,  # was missing, defaulted to "intermediate"
    )
```

## Files Changed

### Backend
- `backend/api/services/pipeline.py` — track-level cache logic, hoist calibration, refactor comparison to reuse profile
- `backend/api/services/db_physics_cache.py` — track_slug parameter in get/set/invalidate
- `backend/api/db/models.py` — add `track_slug` column to `PhysicsCacheEntry`
- `backend/api/routers/coaching.py` — fix missing skill_level in error path
- `cataclysm/track_reference.py` — export `track_slug_from_layout` (if not already public)

### Frontend
- `frontend/src/hooks/useCoaching.ts` — resilient refetchInterval + retry:1

### Migration
- Alembic migration for `track_slug` column on `physics_cache` table

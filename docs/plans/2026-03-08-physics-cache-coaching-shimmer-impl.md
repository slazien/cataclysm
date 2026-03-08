# Physics Track-Level Cache + Coaching Shimmer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Share physics optimal profile computation across sessions on the same track, and fix coaching report polling that stops permanently after a transient error.

**Architecture:** Two-tier physics cache keyed by `(track_slug, profile_id, calibrated_mu)` for the optimal profile (shared) and `(session_id, profile_id)` for the comparison (session-specific). Comparison endpoint reuses the cached profile instead of re-solving. Frontend coaching polling made resilient to transient errors.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0, Alembic, React Query v5, TypeScript

**Design doc:** `docs/plans/2026-03-08-physics-cache-coaching-shimmer-design.md`

---

## Task 1: Coaching shimmer — fix backend error path skill_level

**Files:**
- Modify: `backend/api/routers/coaching.py:445-454`
- Test: `backend/tests/test_coaching.py` (add test)

**Step 1: Write the failing test**

In `backend/tests/test_coaching.py`, add a test that verifies the error path stores the report under the correct skill level:

```python
@pytest.mark.asyncio
async def test_run_generation_error_stores_correct_skill_level():
    """Error path in _run_generation must store report under the actual skill_level, not default."""
    from backend.api.routers.coaching import _run_generation
    from backend.api.services.coaching_store import get_coaching_report, clear_all_coaching

    clear_all_coaching()

    sd = _make_session_data()  # use existing test helper

    # Patch generate_coaching_report to raise an exception
    with patch("backend.api.routers.coaching.compute_corner_analysis", side_effect=RuntimeError("boom")):
        await _run_generation("test-session", sd, "advanced")

    # The error report should be stored under "advanced", NOT "intermediate"
    report = await get_coaching_report("test-session", "advanced")
    assert report is not None
    assert report.status == "error"

    # Should NOT be under "intermediate"
    report_intermediate = await get_coaching_report("test-session", "intermediate")
    assert report_intermediate is None

    clear_all_coaching()
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/d/OneDrive/Dokumenty/vscode/cataclysm && source .venv/bin/activate && pytest backend/tests/test_coaching.py::test_run_generation_error_stores_correct_skill_level -v`
Expected: FAIL — error report stored under "intermediate" instead of "advanced"

**Step 3: Fix the error path**

In `backend/api/routers/coaching.py`, line ~447, change:

```python
    except Exception:  # noqa: BLE001
        logger.exception("Failed to generate coaching report for %s", session_id)
        await store_coaching_report(
            session_id,
            CoachingReportResponse(
                session_id=session_id,
                status="error",
                summary="AI coaching is temporarily unavailable. Please retry in a few minutes.",
            ),
            skill_level,
        )
```

The only change is adding `skill_level,` as the third argument (was omitted, defaulting to `"intermediate"`).

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_coaching.py::test_run_generation_error_stores_correct_skill_level -v`
Expected: PASS

**Step 5: Run full test suite + lint**

Run: `ruff format backend/ && ruff check backend/ && pytest backend/tests/ -v -n auto`

**Step 6: Commit**

```bash
git add backend/api/routers/coaching.py backend/tests/test_coaching.py
git commit -m "fix: pass skill_level in coaching error path (was defaulting to intermediate)"
```

---

## Task 2: Coaching shimmer — resilient frontend polling

**Files:**
- Modify: `frontend/src/hooks/useCoaching.ts:10-24`

**Step 1: Update refetchInterval and add retry**

In `frontend/src/hooks/useCoaching.ts`, change the `useQuery` config:

```typescript
export function useCoachingReport(sessionId: string | null) {
  const skillLevel = useUiStore((s) => s.skillLevel);
  return useQuery<CoachingReport>({
    queryKey: ["coaching-report", sessionId, skillLevel],
    queryFn: () => getCoachingReport(sessionId!, skillLevel),
    enabled: !!sessionId,
    retry: 1,
    refetchOnWindowFocus: false,
    staleTime: 5 * 60 * 1000,
    refetchInterval: (query) => {
      const { data, status } = query.state;
      if (data?.status === "generating") return 2000;
      // Keep polling on errors — transient failures shouldn't kill the loop
      if (status === "error") return 3000;
      return false;
    },
  });
}
```

Changes from current:
- `retry: false` → `retry: 1` (one automatic retry before error state)
- `refetchInterval` callback: added `if (status === "error") return 3000;` to keep polling at 3s on errors

**Step 2: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

**Step 3: Commit**

```bash
git add frontend/src/hooks/useCoaching.ts
git commit -m "fix: coaching polling survives transient errors (retry:1 + error refetch)"
```

---

## Task 3: DB migration — add track_slug column

**Files:**
- Create: `backend/api/db/migrations/versions/c1d2e3f4a5b6_add_track_slug_to_physics_cache.py`
- Modify: `backend/api/db/models.py:402-426`

**Step 1: Update the SQLAlchemy model**

In `backend/api/db/models.py`, add `track_slug` column and a new unique constraint to `PhysicsCacheEntry`:

```python
class PhysicsCacheEntry(Base):
    """Persistent cache for physics computation results (optimal profile/comparison).

    Survives backend restarts and Railway deploys.  Keyed by session+endpoint+profile
    for session-level entries, or track_slug+endpoint+profile+calibrated_mu for
    track-level entries.  A ``code_version`` column enables bulk invalidation
    when the physics algorithm changes.
    """

    __tablename__ = "physics_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)  # "profile" | "comparison"
    profile_id: Mapped[str] = mapped_column(
        String, nullable=False, server_default=""
    )  # "" = no equipment
    track_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    calibrated_mu: Mapped[str | None] = mapped_column(String(8), nullable=True)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    code_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("session_id", "endpoint", "profile_id", name="uq_physics_cache_key"),
        UniqueConstraint(
            "track_slug", "endpoint", "profile_id", "calibrated_mu",
            name="uq_physics_cache_track_key",
        ),
        Index("ix_physics_cache_session", "session_id"),
        Index("ix_physics_cache_profile", "profile_id"),
        Index("ix_physics_cache_track_slug", "track_slug"),
    )
```

**Step 2: Create the Alembic migration**

Create `backend/api/db/migrations/versions/c1d2e3f4a5b6_add_track_slug_to_physics_cache.py`:

```python
"""Add track_slug and calibrated_mu columns to physics_cache for track-level caching.

Revision ID: c1d2e3f4a5b6
Revises: e535e52061ee
Create Date: 2026-03-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "e535e52061ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("physics_cache", sa.Column("track_slug", sa.String(64), nullable=True))
    op.add_column("physics_cache", sa.Column("calibrated_mu", sa.String(8), nullable=True))
    op.create_index("ix_physics_cache_track_slug", "physics_cache", ["track_slug"])
    op.create_unique_constraint(
        "uq_physics_cache_track_key",
        "physics_cache",
        ["track_slug", "endpoint", "profile_id", "calibrated_mu"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_physics_cache_track_key", "physics_cache", type_="unique")
    op.drop_index("ix_physics_cache_track_slug", table_name="physics_cache")
    op.drop_column("physics_cache", "calibrated_mu")
    op.drop_column("physics_cache", "track_slug")
```

**Important:** Check the latest migration's revision ID first — the `down_revision` must match the current head. Run `cd backend && alembic heads` to verify. Adjust `down_revision` if needed.

**Step 3: Verify migration applies**

Run: `cd /mnt/d/OneDrive/Dokumenty/vscode/cataclysm/backend && alembic upgrade head`
Expected: applies cleanly (or check in Railway staging after push)

**Step 4: Commit**

```bash
git add backend/api/db/models.py backend/api/db/migrations/versions/c1d2e3f4a5b6_add_track_slug_to_physics_cache.py
git commit -m "feat: add track_slug + calibrated_mu columns to physics_cache table"
```

---

## Task 4: DB cache layer — track-level get/set/invalidate

**Files:**
- Modify: `backend/api/services/db_physics_cache.py`
- Test: `backend/tests/test_pipeline_extended.py` (add tests)

**Step 1: Write failing tests**

Add to `backend/tests/test_pipeline_extended.py`:

```python
class TestDbPhysicsCacheTrackLevel:
    """Tests for track-level DB cache functions."""

    @pytest.mark.asyncio
    async def test_track_level_set_and_get(self) -> None:
        """Track-level cache stores and retrieves by track_slug."""
        from backend.api.services.db_physics_cache import (
            db_get_cached_by_track, db_set_cached_by_track,
        )
        result = {"lap_time_s": 90.5}
        await db_set_cached_by_track("barber", "profile", result, "prof1", "1.05")
        cached = await db_get_cached_by_track("barber", "profile", "prof1", "1.05")
        assert cached is not None
        assert cached["lap_time_s"] == 90.5

    @pytest.mark.asyncio
    async def test_track_level_miss_returns_none(self) -> None:
        cached = await db_get_cached_by_track("nonexistent", "profile", "p1", "1.00")
        assert cached is None

    @pytest.mark.asyncio
    async def test_invalidate_track_clears_entries(self) -> None:
        from backend.api.services.db_physics_cache import (
            db_get_cached_by_track, db_set_cached_by_track, db_invalidate_track,
        )
        await db_set_cached_by_track("laguna", "profile", {"a": 1}, "p1", "1.10")
        await db_invalidate_track("laguna")
        cached = await db_get_cached_by_track("laguna", "profile", "p1", "1.10")
        assert cached is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_pipeline_extended.py::TestDbPhysicsCacheTrackLevel -v`
Expected: ImportError — functions don't exist yet

**Step 3: Implement track-level DB cache functions**

In `backend/api/services/db_physics_cache.py`, add three new functions:

```python
async def db_get_cached_by_track(
    track_slug: str,
    endpoint: str,
    profile_id: str | None,
    calibrated_mu: str,
) -> dict | None:
    """Look up a track-level cached result from PostgreSQL."""
    pid = profile_id or ""
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(PhysicsCacheEntry.result_json).where(
                    PhysicsCacheEntry.track_slug == track_slug,
                    PhysicsCacheEntry.endpoint == endpoint,
                    PhysicsCacheEntry.profile_id == pid,
                    PhysicsCacheEntry.calibrated_mu == calibrated_mu,
                    PhysicsCacheEntry.code_version == PHYSICS_CODE_VERSION,
                )
            )
            row = result.scalar_one_or_none()
            if row is not None:
                logger.debug("DB track cache HIT: %s/%s/%s/mu=%s", track_slug, endpoint, pid, calibrated_mu)
                return dict(row)
            return None
    except Exception:
        logger.warning("DB track cache read failed", exc_info=True)
        return None


async def db_set_cached_by_track(
    track_slug: str,
    endpoint: str,
    result: dict,
    profile_id: str | None,
    calibrated_mu: str,
) -> None:
    """Upsert a track-level physics result into PostgreSQL."""
    pid = profile_id or ""
    try:
        async with async_session_factory() as db:
            stmt = pg_insert(PhysicsCacheEntry).values(
                session_id=f"_track:{track_slug}",  # sentinel — not a real session
                endpoint=endpoint,
                profile_id=pid,
                track_slug=track_slug,
                calibrated_mu=calibrated_mu,
                result_json=result,
                code_version=PHYSICS_CODE_VERSION,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_physics_cache_track_key",
                set_={
                    "result_json": stmt.excluded.result_json,
                    "code_version": stmt.excluded.code_version,
                    "session_id": stmt.excluded.session_id,
                    "created_at": stmt.excluded.created_at,
                },
            )
            await db.execute(stmt)
            await db.commit()
    except Exception:
        logger.warning("DB track cache write failed", exc_info=True)


async def db_invalidate_track(track_slug: str) -> None:
    """Delete all track-level cached entries for a track."""
    try:
        async with async_session_factory() as db:
            cursor = await db.execute(
                delete(PhysicsCacheEntry).where(
                    PhysicsCacheEntry.track_slug == track_slug,
                )
            )
            deleted = cursor.rowcount  # type: ignore[attr-defined]
            if deleted:
                logger.info(
                    "DB physics cache: deleted %d track-level entries for %s",
                    deleted,
                    track_slug,
                )
            await db.commit()
    except Exception:
        logger.warning("DB track cache invalidation failed", exc_info=True)
```

Note: `session_id` is set to `"_track:{track_slug}"` sentinel to satisfy the NOT NULL constraint while making it clear this is a track-level entry.

**Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_pipeline_extended.py::TestDbPhysicsCacheTrackLevel -v`
Expected: PASS

**Step 5: Lint + commit**

```bash
ruff format backend/ && ruff check backend/
git add backend/api/services/db_physics_cache.py backend/tests/test_pipeline_extended.py
git commit -m "feat: track-level DB cache functions (get/set/invalidate by track_slug)"
```

---

## Task 5: In-memory cache — track-level layer in pipeline.py

**Files:**
- Modify: `backend/api/services/pipeline.py` (cache helpers)
- Test: `backend/tests/test_pipeline_extended.py` (add tests)

**Step 1: Write failing tests**

Add to `backend/tests/test_pipeline_extended.py`:

```python
class TestTrackLevelMemoryCache:
    """Tests for track-level in-memory cache helpers."""

    def setup_method(self) -> None:
        pipeline_module._track_physics_cache.clear()

    def test_get_track_cached_miss(self) -> None:
        from backend.api.services.pipeline import _get_track_cached
        assert _get_track_cached("barber", "profile", "p1", "1.05") is None

    def test_set_and_get_track_cached(self) -> None:
        from backend.api.services.pipeline import _get_track_cached, _set_track_cached
        data = {"lap_time_s": 88.0}
        _set_track_cached("barber", "profile", data, "p1", "1.05")
        assert _get_track_cached("barber", "profile", "p1", "1.05") == data

    def test_track_cache_expired_returns_none(self) -> None:
        from backend.api.services.pipeline import _get_track_cached, _set_track_cached
        _set_track_cached("barber", "profile", {"a": 1}, "p1", "1.05")
        # Artificially expire
        key = ("barber:profile", "p1", "1.05")
        pipeline_module._track_physics_cache[key] = ({"a": 1}, time.time() - 7200)
        assert _get_track_cached("barber", "profile", "p1", "1.05") is None

    def test_invalidate_track_cache(self) -> None:
        from backend.api.services.pipeline import (
            _get_track_cached, _set_track_cached, invalidate_track_physics_cache,
        )
        _set_track_cached("barber", "profile", {"a": 1}, "p1", "1.05")
        _set_track_cached("barber", "profile", {"a": 2}, "p2", "1.10")
        invalidate_track_physics_cache("barber")
        assert _get_track_cached("barber", "profile", "p1", "1.05") is None
        assert _get_track_cached("barber", "profile", "p2", "1.10") is None
```

**Step 2: Run tests — expect ImportError (functions don't exist)**

**Step 3: Implement track-level in-memory cache**

Add to `backend/api/services/pipeline.py`, after the existing session-level cache variables:

```python
# ---------------------------------------------------------------------------
# Track-level physics cache: shares optimal profile across sessions on the
# same track with the same equipment. Key includes calibrated_mu (2dp) so
# sessions with materially different grip don't share.
# Key = (f"{track_slug}:{endpoint}", profile_id_or_None, calibrated_mu_str)
# Value = (result_dict, timestamp)
# ---------------------------------------------------------------------------
_track_physics_cache: dict[tuple[str, str | None, str], tuple[dict[str, object], float]] = {}
TRACK_CACHE_TTL_S = 3600  # 1 hour — track geometry doesn't change


def _get_track_cached(
    track_slug: str,
    key_suffix: str,
    profile_id: str | None,
    calibrated_mu: str,
) -> dict[str, object] | None:
    cache_key = (f"{track_slug}:{key_suffix}", profile_id, calibrated_mu)
    entry = _track_physics_cache.get(cache_key)
    if entry and (time.time() - entry[1]) < TRACK_CACHE_TTL_S:
        logger.debug("Track cache HIT for %s", cache_key)
        return entry[0]
    return None


def _set_track_cached(
    track_slug: str,
    key_suffix: str,
    result: dict[str, object],
    profile_id: str | None,
    calibrated_mu: str,
) -> None:
    cache_key = (f"{track_slug}:{key_suffix}", profile_id, calibrated_mu)
    _track_physics_cache[cache_key] = (result, time.time())
    # LRU eviction — same limit as session cache
    if len(_track_physics_cache) > PHYSICS_CACHE_MAX_ENTRIES:
        oldest_key = min(_track_physics_cache, key=lambda k: _track_physics_cache[k][1])
        del _track_physics_cache[oldest_key]


def invalidate_track_physics_cache(track_slug: str) -> None:
    """Clear all track-level cache entries for a track (in-memory + DB)."""
    keys_to_remove = [k for k in _track_physics_cache if k[0].startswith(f"{track_slug}:")]
    for k in keys_to_remove:
        del _track_physics_cache[k]
    if keys_to_remove:
        logger.info(
            "Invalidated %d track-level cache entries for %s",
            len(keys_to_remove),
            track_slug,
        )
    asyncio.ensure_future(db_invalidate_track(track_slug))
```

Add import at top of pipeline.py:

```python
from backend.api.services.db_physics_cache import (
    db_get_cached,
    db_get_cached_by_track,
    db_invalidate_profile,
    db_invalidate_session,
    db_invalidate_track,
    db_set_cached,
    db_set_cached_by_track,
)
```

**Step 4: Run tests**

Run: `pytest backend/tests/test_pipeline_extended.py::TestTrackLevelMemoryCache -v`
Expected: PASS

**Step 5: Lint + commit**

```bash
ruff format backend/ && ruff check backend/
git add backend/api/services/pipeline.py backend/tests/test_pipeline_extended.py
git commit -m "feat: track-level in-memory physics cache with LRU eviction"
```

---

## Task 6: Refactor get_optimal_profile_data — hoist calibration, use track cache

**Files:**
- Modify: `backend/api/services/pipeline.py:626-752` (`get_optimal_profile_data`)
- Modify: `backend/api/services/pipeline.py` (add import for `track_slug_from_layout`)

**Step 1: Add track_slug_from_layout import**

In pipeline.py, update the track_reference import:

```python
from cataclysm.track_reference import (
    align_reference_to_session,
    get_track_reference,
    maybe_update_track_reference,
    track_slug_from_layout,
)
```

**Step 2: Refactor get_optimal_profile_data**

Replace the entire function body. Key changes:
- Hoist grip calibration BEFORE cache check (cheap ~1ms)
- Build track-level cache key using `track_slug + calibrated_mu`
- Check track cache first, then session cache, then compute
- Unknown tracks (no layout) fall back to session-keyed caching

```python
async def get_optimal_profile_data(session_data: SessionData) -> dict[str, object]:
    """Compute the physics-optimal velocity profile for a session.

    Uses a two-tier cache: track-level (shared across sessions) then session-level.
    Track-level caching works when a canonical track reference exists; unknown
    tracks fall back to session-keyed caching.
    """
    session_id = session_data.session_id

    profile_id = _current_profile_id(session_id)
    vehicle_params = resolve_vehicle_params(session_id)
    mu_cap = _get_compound_mu_cap(session_id)

    # Hoist grip calibration before cache check — it's cheap (~1ms) and we need
    # the calibrated mu to build the track-level cache key.
    processed = session_data.processed
    calibration_data = _collect_independent_calibration_telemetry(
        session_data,
        target_lap=processed.best_lap,
    )
    if calibration_data is not None:
        lat_g, lon_g, calibration_laps = calibration_data
        grip = calibrate_grip_from_telemetry(lat_g, lon_g)
        if grip is not None:
            base = vehicle_params or default_vehicle_params()
            vehicle_params = apply_calibration_to_params(base, grip, mu_cap=mu_cap)
            logger.info(
                "Grip calibration [profile] sid=%s laps=%s: mu=%.3f lat_g=%.3f "
                "brake_g=%.3f accel_g=%.3f confidence=%s mu_cap=%s",
                session_id, calibration_laps,
                vehicle_params.mu, grip.max_lateral_g,
                grip.max_brake_g, grip.max_accel_g,
                grip.confidence, mu_cap,
            )

    calibrated_mu_str = f"{vehicle_params.mu:.2f}" if vehicle_params else "default"

    # --- Track-level cache (shared across sessions) ---
    track_slug: str | None = None
    layout = session_data.layout
    if layout is not None:
        track_slug = track_slug_from_layout(layout)

        cached = _get_track_cached(track_slug, "profile", profile_id, calibrated_mu_str)
        if cached is not None:
            return cached

        db_cached = await db_get_cached_by_track(track_slug, "profile", profile_id, calibrated_mu_str)
        if db_cached is not None:
            _set_track_cached(track_slug, "profile", db_cached, profile_id, calibrated_mu_str)
            return db_cached

    # --- Session-level cache fallback (unknown tracks) ---
    cached = _get_physics_cached(session_id, "profile", profile_id)
    if cached is not None:
        return cached

    db_cached = await db_get_cached(session_id, "profile", profile_id)
    if db_cached is not None:
        _set_physics_cached(session_id, "profile", db_cached, profile_id)
        return db_cached

    # --- Cache miss: compute ---
    lidar_alt = await _try_lidar_elevation(session_data)

    def _compute() -> dict[str, object]:
        best_lap_df = processed.resampled_laps[processed.best_lap]

        curvature_result, resolved_alt = _resolve_curvature_and_elevation(session_data, lidar_alt)

        gradient_sin = None
        vert_curvature = None
        alt = resolved_alt
        if alt is None and "altitude_m" in best_lap_df.columns:
            alt = best_lap_df["altitude_m"].to_numpy()
        if alt is not None and not np.all(np.isnan(alt)):
            dist = best_lap_df["lap_distance_m"].to_numpy()
            gradient_sin = compute_gradient_array(alt, dist)
            vert_curvature = compute_vertical_curvature(alt, dist)

        optimal = compute_optimal_profile(
            curvature_result,
            params=vehicle_params,
            gradient_sin=gradient_sin,
            mu_array=None,
            vertical_curvature=vert_curvature,
        )

        return {
            "distance_m": optimal.distance_m.tolist(),
            "optimal_speed_mph": (optimal.optimal_speed_mps * MPS_TO_MPH).tolist(),
            "max_cornering_speed_mph": (optimal.max_cornering_speed_mps * MPS_TO_MPH).tolist(),
            "brake_points": optimal.optimal_brake_points,
            "throttle_points": optimal.optimal_throttle_points,
            "lap_time_s": optimal.lap_time_s,
            "vehicle_params": {
                "mu": optimal.vehicle_params.mu,
                "max_accel_g": optimal.vehicle_params.max_accel_g,
                "max_decel_g": optimal.vehicle_params.max_decel_g,
                "max_lateral_g": optimal.vehicle_params.max_lateral_g,
                "top_speed_mps": optimal.vehicle_params.top_speed_mps,
                "calibrated": optimal.vehicle_params.calibrated,
            },
            "equipment_profile_id": profile_id,
        }

    result = await asyncio.to_thread(_compute)

    # Store in track-level cache if we have a track slug
    if track_slug is not None:
        _set_track_cached(track_slug, "profile", result, profile_id, calibrated_mu_str)
        await db_set_cached_by_track(track_slug, "profile", result, profile_id, calibrated_mu_str)
    # Always store session-level too (for unknown-track fallback + backward compat)
    _set_physics_cached(session_id, "profile", result, profile_id)
    await db_set_cached(session_id, "profile", result, profile_id)

    return result
```

**Step 3: Run existing tests**

Run: `pytest backend/tests/test_pipeline_extended.py -v -n auto`
Expected: existing tests still PASS

**Step 4: Lint**

Run: `ruff format backend/ && ruff check backend/ && dmypy run -- backend/`

**Step 5: Commit**

```bash
git add backend/api/services/pipeline.py
git commit -m "feat: get_optimal_profile_data uses track-level cache, hoists calibration"
```

---

## Task 7: Refactor get_optimal_comparison_data — reuse cached profile

**Files:**
- Modify: `backend/api/services/pipeline.py:755-906` (`get_optimal_comparison_data`)

**Step 1: Add OptimalProfile import**

In pipeline.py imports, add:

```python
from cataclysm.velocity_profile import (
    OptimalProfile,
    VehicleParams,
    compute_optimal_profile,
    default_vehicle_params,
)
```

**Step 2: Add helper to reconstruct OptimalProfile from cached dict**

Add near the cache helpers section:

```python
def _reconstruct_optimal_profile(cached: dict[str, object]) -> OptimalProfile:
    """Reconstruct an OptimalProfile from the cached dict serialization."""
    vp = cached.get("vehicle_params", {})
    return OptimalProfile(
        distance_m=np.array(cached["distance_m"]),
        optimal_speed_mps=np.array(cached["optimal_speed_mph"]) / MPS_TO_MPH,
        curvature=np.zeros(len(cached["distance_m"])),  # not needed for comparison
        max_cornering_speed_mps=np.array(cached["max_cornering_speed_mph"]) / MPS_TO_MPH,
        optimal_brake_points=cached["brake_points"],
        optimal_throttle_points=cached["throttle_points"],
        lap_time_s=cached["lap_time_s"],
        vehicle_params=VehicleParams(
            mu=vp.get("mu", 1.0),
            max_accel_g=vp.get("max_accel_g", 0.5),
            max_decel_g=vp.get("max_decel_g", 1.2),
            max_lateral_g=vp.get("max_lateral_g", 1.2),
            top_speed_mps=vp.get("top_speed_mps", 80.0),
            calibrated=vp.get("calibrated", False),
        ),
    )
```

**Step 3: Refactor get_optimal_comparison_data**

Replace the function body. The key change: call `get_optimal_profile_data()` instead of re-solving the velocity model.

```python
async def get_optimal_comparison_data(session_data: SessionData) -> dict[str, object]:
    """Compare the best lap against the physics-optimal profile per-corner.

    Reuses the cached optimal profile from get_optimal_profile_data() instead
    of re-solving the velocity model.
    """
    session_id = session_data.session_id

    profile_id = _current_profile_id(session_id)

    # Session-level comparison cache (unchanged — comparison is per-session)
    cached = _get_physics_cached(session_id, "comparison", profile_id)
    if cached is not None:
        return cached

    db_cached = await db_get_cached(session_id, "comparison", profile_id)
    if db_cached is not None:
        _set_physics_cached(session_id, "comparison", db_cached, profile_id)
        return db_cached

    # Get the optimal profile (track-level cached, near-instant on hit)
    profile_data = await get_optimal_profile_data(session_data)
    optimal = _reconstruct_optimal_profile(profile_data)

    vehicle_params = optimal.vehicle_params

    def _compute() -> dict[str, object]:
        processed = session_data.processed
        best_lap_df = processed.resampled_laps[processed.best_lap]
        corners = session_data.corners
        has_equipment = profile_id is not None

        logger.info(
            "Optimal comparison [params] sid=%s has_equipment=%s profile_id=%s "
            "mu=%.3f lat_g=%.3f decel_g=%.3f accel_g=%.3f",
            session_id, has_equipment, profile_id,
            vehicle_params.mu, vehicle_params.max_lateral_g,
            vehicle_params.max_decel_g, vehicle_params.max_accel_g,
        )

        result = compare_with_optimal(best_lap_df, corners, optimal)

        if not result.is_valid:
            logger.warning(
                "Optimal comparison INVALID sid=%s: total_gap=%.3f reasons=%s",
                session_id, result.total_gap_s, result.invalid_reasons,
            )

        return {
            "corner_opportunities": [
                {
                    "corner_number": opp.corner_number,
                    "actual_min_speed_mph": round(opp.actual_min_speed_mps * MPS_TO_MPH, 2),
                    "optimal_min_speed_mph": round(opp.optimal_min_speed_mps * MPS_TO_MPH, 2),
                    "speed_gap_mph": round(opp.speed_gap_mph, 2),
                    "brake_gap_m": (
                        round(opp.brake_gap_m, 2) if opp.brake_gap_m is not None else None
                    ),
                    "time_cost_s": round(opp.time_cost_s, 3),
                }
                for opp in result.corner_opportunities
            ],
            "actual_lap_time_s": round(result.actual_lap_time_s, 3),
            "optimal_lap_time_s": round(result.optimal_lap_time_s, 3),
            "total_gap_s": round(result.total_gap_s, 3),
            "is_valid": result.is_valid,
            "invalid_reasons": result.invalid_reasons,
        }

    result = await asyncio.to_thread(_compute)
    _set_physics_cached(session_id, "comparison", result, profile_id)
    await db_set_cached(session_id, "comparison", result, profile_id)
    return result
```

**Step 4: Run full test suite**

Run: `pytest backend/tests/ -v -n auto`
Expected: all PASS

**Step 5: Lint + type check**

Run: `ruff format backend/ cataclysm/ && ruff check backend/ cataclysm/ && dmypy run -- backend/ cataclysm/`

**Step 6: Commit**

```bash
git add backend/api/services/pipeline.py
git commit -m "feat: comparison endpoint reuses cached optimal profile instead of re-solving"
```

---

## Task 8: Track reference invalidation hook

**Files:**
- Modify: `backend/api/services/pipeline.py` (call invalidate on track reference update)

**Step 1: Hook into maybe_update_track_reference**

In `pipeline.py`, find where `maybe_update_track_reference` is called (around line 321-330 in `_run_pipeline_sync`). After the call, if the reference was updated, invalidate the track cache:

```python
if layout is not None and coaching_laps:
    try:
        quality_score = gps_quality.overall_score if gps_quality else 50.0
        ref = maybe_update_track_reference(
            layout, processed, coaching_laps,
            session_id=session_id, gps_quality_score=quality_score,
        )
        if ref is not None:
            # Track reference was updated — invalidate track-level physics cache
            invalidate_track_physics_cache(ref.track_slug)
    except Exception:
        logger.warning("Track reference update failed", exc_info=True)
```

Note: `maybe_update_track_reference` returns `TrackReference | None`. It returns `None` when the existing reference is already better quality. We only invalidate when a new reference is saved.

**Step 2: Run tests**

Run: `pytest backend/tests/ -v -n auto`

**Step 3: Commit**

```bash
git add backend/api/services/pipeline.py
git commit -m "feat: invalidate track physics cache when track reference updates"
```

---

## Task 9: Full quality gates

**Step 1: Backend lint + type check + tests**

```bash
source .venv/bin/activate
ruff format cataclysm/ tests/ backend/
ruff check cataclysm/ tests/ backend/
dmypy run -- cataclysm/ backend/
pytest tests/ backend/tests/ -v -n auto
```

**Step 2: Frontend TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Fix any issues found**

**Step 4: Commit any fixes**

---

## Task 10: Push to staging + verify deployment

**Step 1: Push**

```bash
git push origin staging
```

**Step 2: Wait for Railway deploy (~2-3 min)**

Check with: `railway list-deployments --service backend` → get latest ID → `railway get-logs <id>`

**Step 3: Verify backend starts cleanly**

Check logs for any migration errors or import failures.

**Step 4: Visual QA with Playwright**

Open the app, upload a session (or use existing), switch equipment — verify:
1. First session computes optimal profile (~8s as before)
2. Second session on same track with same equipment is near-instant
3. Coaching report generates and shimmer resolves without refresh
4. Equipment switch shows pulse animation then new values

**Step 5: Commit any fixes found during QA**

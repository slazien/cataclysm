"""Persistent physics cache backed by PostgreSQL.

Stores velocity-solver results so they survive backend restarts and
Railway deploys.  Works alongside the in-memory LRU cache in pipeline.py:

    1. Check in-memory cache (fast, nanoseconds)
    2. Check DB cache (async, milliseconds)
    3. Compute (sync in threadpool, seconds)
    4. Write to both caches

A ``PHYSICS_CODE_VERSION`` constant is bumped whenever the physics algorithm
changes (solver, calibration, curvature, elevation).  DB entries with a stale
version are treated as misses and get overwritten on next computation.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.api.db.database import async_session_factory
from backend.api.db.models import PhysicsCacheEntry

logger = logging.getLogger(__name__)

# Bump this whenever the physics algorithm output changes.
# Format: YYYY-MM-DD.N where N is a daily counter.
PHYSICS_CODE_VERSION = "2026-03-07.1"


async def db_get_cached(
    session_id: str,
    endpoint: str,
    profile_id: str | None,
) -> dict | None:
    """Look up a cached result from PostgreSQL.

    Returns the result dict if found and the code version matches,
    otherwise None.
    """
    pid = profile_id or ""
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(PhysicsCacheEntry.result_json).where(
                    PhysicsCacheEntry.session_id == session_id,
                    PhysicsCacheEntry.endpoint == endpoint,
                    PhysicsCacheEntry.profile_id == pid,
                    PhysicsCacheEntry.code_version == PHYSICS_CODE_VERSION,
                )
            )
            row = result.scalar_one_or_none()
            if row is not None:
                logger.debug("DB physics cache HIT: %s/%s/%s", session_id, endpoint, pid)
                return dict(row)  # JSONB → dict
            return None
    except Exception:
        logger.warning("DB physics cache read failed", exc_info=True)
        return None


async def db_set_cached(
    session_id: str,
    endpoint: str,
    result: dict,
    profile_id: str | None,
) -> None:
    """Upsert a physics result into PostgreSQL.

    Uses PostgreSQL ON CONFLICT to insert-or-update atomically.
    """
    pid = profile_id or ""
    try:
        async with async_session_factory() as db:
            stmt = pg_insert(PhysicsCacheEntry).values(
                session_id=session_id,
                endpoint=endpoint,
                profile_id=pid,
                result_json=result,
                code_version=PHYSICS_CODE_VERSION,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_physics_cache_key",
                set_={
                    "result_json": stmt.excluded.result_json,
                    "code_version": stmt.excluded.code_version,
                    "created_at": stmt.excluded.created_at,
                },
            )
            await db.execute(stmt)
            await db.commit()
    except Exception:
        logger.warning("DB physics cache write failed", exc_info=True)


async def db_invalidate_session(session_id: str) -> None:
    """Delete all cached entries for a session."""
    try:
        async with async_session_factory() as db:
            cursor = await db.execute(
                delete(PhysicsCacheEntry).where(
                    PhysicsCacheEntry.session_id == session_id,
                )
            )
            deleted = cursor.rowcount  # type: ignore[attr-defined]
            if deleted:
                logger.info(
                    "DB physics cache: deleted %d entries for session %s",
                    deleted,
                    session_id,
                )
            await db.commit()
    except Exception:
        logger.warning("DB physics cache session invalidation failed", exc_info=True)


async def db_invalidate_profile(profile_id: str) -> None:
    """Delete all cached entries using a specific equipment profile."""
    try:
        async with async_session_factory() as db:
            cursor = await db.execute(
                delete(PhysicsCacheEntry).where(
                    PhysicsCacheEntry.profile_id == profile_id,
                )
            )
            deleted = cursor.rowcount  # type: ignore[attr-defined]
            if deleted:
                logger.info(
                    "DB physics cache: deleted %d entries for profile %s",
                    deleted,
                    profile_id,
                )
            await db.commit()
    except Exception:
        logger.warning("DB physics cache profile invalidation failed", exc_info=True)


# ---------------------------------------------------------------------------
# Track-level cache functions
# ---------------------------------------------------------------------------


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
                logger.debug(
                    "DB track cache HIT: %s/%s/%s/mu=%s",
                    track_slug,
                    endpoint,
                    pid,
                    calibrated_mu,
                )
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
                session_id=f"_track:{track_slug}",
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

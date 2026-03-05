"""In-memory coaching store with async PostgreSQL persistence.

Keeps generated coaching reports and follow-up chat contexts keyed by
session_id.  In-memory dicts provide fast reads; writes are persisted to
PostgreSQL via ``async_session_factory`` so data survives container restarts.
On cache miss, a lazy DB fallback populates the in-memory cache.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from cataclysm.coaching import CoachingContext
from sqlalchemy.exc import SQLAlchemyError

from backend.api.db.database import async_session_factory
from backend.api.schemas.coaching import CoachingReportResponse
from backend.api.services.db_coaching_store import (
    delete_coaching_data_db,
    delete_coaching_report_for_skill_db,
    get_any_coaching_report_db,
    get_coaching_context_db,
    get_coaching_report_db,
    upsert_coaching_context_db,
    upsert_coaching_report_db,
)

logger = logging.getLogger(__name__)

# Maximum coaching items to keep in memory before evicting oldest.
MAX_COACHING_CACHE: int = 300

# Module-level in-memory caches
_reports: dict[str, dict[str, CoachingReportResponse]] = {}  # session_id -> {skill_level: report}
_contexts: dict[str, CoachingContext] = {}
_generating: set[tuple[str, str]] = set()  # (session_id, skill_level) pairs currently generating

# Daily regeneration rate limiting (per-user)
MAX_DAILY_REGENS: int = 2
_regen_counts: dict[str, dict[str, int]] = {}  # user_id -> {date_str: count}


def _evict_oldest_reports() -> None:
    """Evict oldest coaching report(s) when cache exceeds MAX_COACHING_CACHE.

    Counts sessions (not individual skill-level reports) for the eviction limit.
    """
    while len(_reports) > MAX_COACHING_CACHE:
        oldest_id = next(iter(_reports))
        _reports.pop(oldest_id)
        _contexts.pop(oldest_id, None)
        logger.info(
            "Evicted coaching cache for %s (at %d/%d)",
            oldest_id,
            len(_reports),
            MAX_COACHING_CACHE,
        )


async def store_coaching_report(
    session_id: str,
    report: CoachingReportResponse,
    skill_level: str = "intermediate",
) -> None:
    """Persist a coaching report in-memory and to the database."""
    _reports.setdefault(session_id, {})[skill_level] = report
    _evict_oldest_reports()
    try:
        async with async_session_factory() as db:
            await upsert_coaching_report_db(db, session_id, report, skill_level)
            await db.commit()
    except SQLAlchemyError:
        logger.warning("Failed to persist coaching report to DB for %s", session_id, exc_info=True)


async def get_coaching_report(
    session_id: str, skill_level: str = "intermediate"
) -> CoachingReportResponse | None:
    """Retrieve a coaching report for a specific skill level.

    Memory first, lazy DB fallback on miss.
    """
    inner = _reports.get(session_id, {})
    cached = inner.get(skill_level)
    if cached is not None:
        return cached

    # Lazy load from DB
    try:
        async with async_session_factory() as db:
            report = await get_coaching_report_db(db, session_id, skill_level)
        if report is not None and report.status == "ready":
            _reports.setdefault(session_id, {})[skill_level] = report
            return report
    except SQLAlchemyError:
        logger.warning("Failed to load coaching report from DB for %s", session_id, exc_info=True)
    return None


async def get_any_coaching_report(session_id: str) -> CoachingReportResponse | None:
    """Retrieve the most recently stored report for a session (any skill level).

    Used by chat/PDF endpoints that don't know the skill level.
    """
    inner = _reports.get(session_id)
    if inner:
        return next(reversed(inner.values()))

    # DB fallback: get most recent by created_at
    try:
        async with async_session_factory() as db:
            report = await get_any_coaching_report_db(db, session_id)
        if report is not None and report.status == "ready":
            sl = report.skill_level or "intermediate"
            _reports.setdefault(session_id, {})[sl] = report
            return report
    except SQLAlchemyError:
        logger.warning("Failed to load coaching report from DB for %s", session_id, exc_info=True)
    return None


async def store_coaching_context(session_id: str, context: CoachingContext) -> None:
    """Persist a coaching conversation context in-memory and to the database."""
    _contexts[session_id] = context
    try:
        async with async_session_factory() as db:
            await upsert_coaching_context_db(db, session_id, context.messages)
            await db.commit()
    except SQLAlchemyError:
        logger.warning("Failed to persist coaching context to DB for %s", session_id, exc_info=True)


async def get_coaching_context(session_id: str) -> CoachingContext | None:
    """Retrieve a coaching context — memory first, lazy DB fallback on miss."""
    cached = _contexts.get(session_id)
    if cached is not None:
        return cached

    # Lazy load from DB
    try:
        async with async_session_factory() as db:
            messages = await get_coaching_context_db(db, session_id)
        if messages is not None:
            ctx = CoachingContext(messages=messages)
            _contexts[session_id] = ctx
            return ctx
    except SQLAlchemyError:
        logger.warning("Failed to load coaching context from DB for %s", session_id, exc_info=True)
    return None


async def clear_coaching_data(session_id: str) -> None:
    """Remove ALL coaching data for a session from memory and the database."""
    _reports.pop(session_id, None)
    _contexts.pop(session_id, None)
    try:
        async with async_session_factory() as db:
            await delete_coaching_data_db(db, session_id)
            await db.commit()
    except SQLAlchemyError:
        logger.warning("Failed to delete coaching data from DB for %s", session_id, exc_info=True)


async def clear_coaching_report(session_id: str, skill_level: str) -> None:
    """Remove a single skill level's coaching report from memory and the database."""
    inner = _reports.get(session_id)
    if inner:
        inner.pop(skill_level, None)
        if not inner:
            _reports.pop(session_id, None)
    try:
        async with async_session_factory() as db:
            await delete_coaching_report_for_skill_db(db, session_id, skill_level)
            await db.commit()
    except SQLAlchemyError:
        logger.warning(
            "Failed to delete coaching report from DB for %s/%s",
            session_id,
            skill_level,
            exc_info=True,
        )


def mark_generating(session_id: str, skill_level: str = "intermediate") -> None:
    """Mark a session+skill_level as currently generating a coaching report."""
    _generating.add((session_id, skill_level))


def unmark_generating(session_id: str, skill_level: str = "intermediate") -> None:
    """Remove the generating flag for a session+skill_level."""
    _generating.discard((session_id, skill_level))


def is_generating(session_id: str, skill_level: str = "intermediate") -> bool:
    """Check if a session+skill_level is currently generating a coaching report."""
    return (session_id, skill_level) in _generating


def clear_all_coaching() -> None:
    """Remove all coaching data from memory (test cleanup only)."""
    _reports.clear()
    _contexts.clear()
    _generating.clear()
    _regen_counts.clear()


def _today_str() -> str:
    """Return today's date as YYYY-MM-DD in UTC."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def get_regen_remaining(user_id: str) -> int:
    """Return how many regenerations the user has left today."""
    today = _today_str()
    used = _regen_counts.get(user_id, {}).get(today, 0)
    return max(0, MAX_DAILY_REGENS - used)


def record_regeneration(user_id: str) -> int:
    """Record a regeneration use and return remaining count after this use.

    Returns -1 if the limit has already been reached (caller should reject).
    """
    today = _today_str()
    user_counts = _regen_counts.setdefault(user_id, {})
    # Purge stale day entries
    for d in [k for k in user_counts if k != today]:
        del user_counts[d]
    used = user_counts.get(today, 0)
    if used >= MAX_DAILY_REGENS:
        return -1
    user_counts[today] = used + 1
    return MAX_DAILY_REGENS - used - 1

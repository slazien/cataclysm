"""In-memory coaching store with async PostgreSQL persistence.

Keeps generated coaching reports and follow-up chat contexts keyed by
session_id.  In-memory dicts provide fast reads; writes are persisted to
PostgreSQL via ``async_session_factory`` so data survives container restarts.
On cache miss, a lazy DB fallback populates the in-memory cache.
"""

from __future__ import annotations

import logging

from cataclysm.coaching import CoachingContext

from backend.api.db.database import async_session_factory
from backend.api.schemas.coaching import CoachingReportResponse
from backend.api.services.db_coaching_store import (
    delete_coaching_data_db,
    get_coaching_context_db,
    get_coaching_report_db,
    upsert_coaching_context_db,
    upsert_coaching_report_db,
)

logger = logging.getLogger(__name__)

# Module-level in-memory caches
_reports: dict[str, CoachingReportResponse] = {}
_contexts: dict[str, CoachingContext] = {}
_generating: set[str] = set()  # session IDs currently generating


async def store_coaching_report(
    session_id: str,
    report: CoachingReportResponse,
    skill_level: str = "intermediate",
) -> None:
    """Persist a coaching report in-memory and to the database."""
    _reports[session_id] = report
    try:
        async with async_session_factory() as db:
            await upsert_coaching_report_db(db, session_id, report, skill_level)
            await db.commit()
    except Exception:
        logger.warning("Failed to persist coaching report to DB for %s", session_id, exc_info=True)


async def get_coaching_report(session_id: str) -> CoachingReportResponse | None:
    """Retrieve a coaching report — memory first, lazy DB fallback on miss."""
    cached = _reports.get(session_id)
    if cached is not None:
        return cached

    # Lazy load from DB
    try:
        async with async_session_factory() as db:
            report = await get_coaching_report_db(db, session_id)
        if report is not None and report.status == "ready":
            _reports[session_id] = report
            return report
    except Exception:
        logger.warning("Failed to load coaching report from DB for %s", session_id, exc_info=True)
    return None


async def store_coaching_context(session_id: str, context: CoachingContext) -> None:
    """Persist a coaching conversation context in-memory and to the database."""
    _contexts[session_id] = context
    try:
        async with async_session_factory() as db:
            await upsert_coaching_context_db(db, session_id, context.messages)
            await db.commit()
    except Exception:
        logger.warning(
            "Failed to persist coaching context to DB for %s", session_id, exc_info=True
        )


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
    except Exception:
        logger.warning(
            "Failed to load coaching context from DB for %s", session_id, exc_info=True
        )
    return None


async def clear_coaching_data(session_id: str) -> None:
    """Remove coaching data for a session from memory and the database."""
    _reports.pop(session_id, None)
    _contexts.pop(session_id, None)
    try:
        async with async_session_factory() as db:
            await delete_coaching_data_db(db, session_id)
            await db.commit()
    except Exception:
        logger.warning(
            "Failed to delete coaching data from DB for %s", session_id, exc_info=True
        )


def mark_generating(session_id: str) -> None:
    """Mark a session as currently generating a coaching report."""
    _generating.add(session_id)


def unmark_generating(session_id: str) -> None:
    """Remove the generating flag for a session."""
    _generating.discard(session_id)


def is_generating(session_id: str) -> bool:
    """Check if a session is currently generating a coaching report."""
    return session_id in _generating


def clear_all_coaching() -> None:
    """Remove all coaching data from memory (test cleanup only)."""
    _reports.clear()
    _contexts.clear()
    _generating.clear()

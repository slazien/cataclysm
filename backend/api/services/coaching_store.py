"""In-memory store for coaching reports and conversation contexts.

Keeps generated coaching reports and follow-up chat contexts keyed by
session_id. Will be replaced by database persistence in a later phase.
"""

from __future__ import annotations

from cataclysm.coaching import CoachingContext

from backend.api.schemas.coaching import CoachingReportResponse

# Module-level in-memory stores
_reports: dict[str, CoachingReportResponse] = {}
_contexts: dict[str, CoachingContext] = {}
_generating: set[str] = set()  # session IDs currently generating


def store_coaching_report(session_id: str, report: CoachingReportResponse) -> None:
    """Persist a coaching report in the in-memory store."""
    _reports[session_id] = report


def get_coaching_report(session_id: str) -> CoachingReportResponse | None:
    """Retrieve a coaching report by session ID, or None if not found."""
    return _reports.get(session_id)


def store_coaching_context(session_id: str, context: CoachingContext) -> None:
    """Persist a coaching conversation context."""
    _contexts[session_id] = context


def get_coaching_context(session_id: str) -> CoachingContext | None:
    """Retrieve a coaching conversation context, or None if not found."""
    return _contexts.get(session_id)


def clear_coaching_data(session_id: str) -> None:
    """Remove coaching data for a session."""
    _reports.pop(session_id, None)
    _contexts.pop(session_id, None)


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
    """Remove all coaching data."""
    _reports.clear()
    _contexts.clear()
    _generating.clear()

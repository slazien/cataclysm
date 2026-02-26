"""In-memory store for coaching reports with JSON disk persistence.

Keeps generated coaching reports and follow-up chat contexts keyed by
session_id.  Reports are persisted as JSON files under the configured
``coaching_data_dir`` so they survive server restarts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cataclysm.coaching import CoachingContext

from backend.api.schemas.coaching import CoachingReportResponse

logger = logging.getLogger(__name__)

# Module-level in-memory stores
_reports: dict[str, CoachingReportResponse] = {}
_contexts: dict[str, CoachingContext] = {}
_generating: set[str] = set()  # session IDs currently generating

# Disk persistence directory (set via init_coaching_dir on startup)
_coaching_dir: Path | None = None


def init_coaching_dir(path: str) -> None:
    """Configure the directory used for persisting coaching reports."""
    global _coaching_dir  # noqa: PLW0603
    _coaching_dir = Path(path)
    _coaching_dir.mkdir(parents=True, exist_ok=True)


def _persist(session_id: str, report: CoachingReportResponse) -> None:
    """Write a coaching report to disk as JSON."""
    if _coaching_dir is None:
        return
    try:
        out = _coaching_dir / f"{session_id}.json"
        out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    except Exception:
        logger.warning("Failed to persist coaching report for %s", session_id, exc_info=True)


def _delete_persisted(session_id: str) -> None:
    """Remove a persisted coaching report from disk."""
    if _coaching_dir is None:
        return
    path = _coaching_dir / f"{session_id}.json"
    path.unlink(missing_ok=True)


def load_persisted_reports() -> int:
    """Load all persisted coaching reports from disk into memory.

    Returns the number of reports loaded.
    """
    if _coaching_dir is None or not _coaching_dir.exists():
        return 0

    count = 0
    for path in _coaching_dir.glob("*.json"):
        session_id = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            report = CoachingReportResponse.model_validate(data)
            # Only load successful reports; discard persisted errors
            if report.status == "ready":
                _reports[session_id] = report
                count += 1
        except Exception:
            logger.warning("Failed to load coaching report from %s", path, exc_info=True)
    return count


def store_coaching_report(session_id: str, report: CoachingReportResponse) -> None:
    """Persist a coaching report in-memory and to disk."""
    _reports[session_id] = report
    _persist(session_id, report)


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
    _delete_persisted(session_id)


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

"""In-memory session data store.

Provides a dict-based store for session data. Each session holds all
pipeline outputs (parsed, processed, corners, consistency, gains, grip)
keyed by session_id. This will be replaced by database persistence in a
later phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cataclysm.consistency import SessionConsistency
from cataclysm.corners import Corner
from cataclysm.engine import ProcessedSession
from cataclysm.gains import GainEstimate
from cataclysm.grip import GripEstimate
from cataclysm.lap_tags import LapTagStore
from cataclysm.parser import ParsedSession
from cataclysm.trends import SessionSnapshot


@dataclass
class SessionData:
    """All data associated with a single processed session."""

    session_id: str
    snapshot: SessionSnapshot
    parsed: ParsedSession
    processed: ProcessedSession
    corners: list[Corner]
    all_lap_corners: dict[int, list[Corner]]
    consistency: SessionConsistency | None = None
    gains: GainEstimate | None = None
    grip: GripEstimate | None = None
    lap_tags: LapTagStore = field(default_factory=LapTagStore)
    coaching_laps: list[int] = field(default_factory=list)
    anomalous_laps: set[int] = field(default_factory=set)


# Module-level in-memory store
_store: dict[str, SessionData] = {}


def store_session(session_id: str, data: SessionData) -> None:
    """Persist a session in the in-memory store."""
    _store[session_id] = data


def get_session(session_id: str) -> SessionData | None:
    """Retrieve a session by ID, or None if not found."""
    return _store.get(session_id)


def delete_session(session_id: str) -> bool:
    """Delete a session by ID. Returns True if it existed."""
    return _store.pop(session_id, None) is not None


def list_sessions() -> list[SessionData]:
    """Return all stored sessions, sorted by date descending."""
    return sorted(
        _store.values(),
        key=lambda s: s.snapshot.session_date_parsed,
        reverse=True,
    )


def clear_all() -> int:
    """Delete all sessions. Returns the count of deleted sessions."""
    count = len(_store)
    _store.clear()
    return count

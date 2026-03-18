"""In-memory session data store with LRU eviction.

Provides a dict-based store for session data. Each session holds all
pipeline outputs (parsed, processed, corners, consistency, gains, grip)
keyed by session_id. PostgreSQL persists metadata and raw CSV bytes;
this in-memory store provides fast access to the processed telemetry.

Eviction: when the store exceeds ``MAX_SESSIONS``, the oldest sessions
(by insertion order) are evicted to prevent unbounded memory growth.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from cataclysm.consistency import SessionConsistency
from cataclysm.corner_line import CornerLineProfile
from cataclysm.corners import Corner
from cataclysm.engine import ProcessedSession
from cataclysm.equipment import SessionConditions
from cataclysm.gains import GainEstimate
from cataclysm.gps_line import GPSTrace, ReferenceCenterline
from cataclysm.gps_quality import GPSQualityReport
from cataclysm.grip import GripEstimate
from cataclysm.lap_tags import LapTagStore
from cataclysm.parser import ParsedSession
from cataclysm.track_db import TrackLayout
from cataclysm.trends import SessionSnapshot

logger = logging.getLogger(__name__)


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
    gps_quality: GPSQualityReport | None = None
    lap_tags: LapTagStore = field(default_factory=LapTagStore)
    weather: SessionConditions | None = None
    coaching_laps: list[int] = field(default_factory=list)
    anomalous_laps: set[int] = field(default_factory=set)
    user_id: str | None = None
    is_anonymous: bool = False
    created_at: float = field(default_factory=time.time)
    client_ip: str | None = None
    # Line analysis (Phase 5) — populated when GPS quality is A or B
    gps_traces: list[GPSTrace] = field(default_factory=list)
    reference_centerline: ReferenceCenterline | None = None
    corner_line_profiles: list[CornerLineProfile] = field(default_factory=list)
    # Track layout detected during processing (None for unknown tracks)
    layout: TrackLayout | None = None
    # Corner override content hash (None = no override or pre-versioning)
    corner_override_version: str | None = None
    # Transient: nulled after DB persistence. Only DB copy (SessionFileModel) is authoritative.
    csv_bytes: bytes | None = field(default=None, repr=False)


# Maximum sessions to keep in memory before evicting oldest.
# Each session uses ~5-20MB; 200 sessions ≈ 1-4GB RAM.
MAX_SESSIONS: int = 200

# Anonymous session TTL in seconds (24 hours)
ANON_SESSION_TTL: int = 86400

# Module-level in-memory store
_store: dict[str, SessionData] = {}

# --- Rehydration concurrency controls ---
_REHYDRATION_LOCKS: dict[str, asyncio.Lock] = {}
MAX_CONCURRENT_REHYDRATIONS: int = 4
_REHYDRATION_SEMAPHORE: asyncio.Semaphore | None = None
_REHYDRATION_FAILURES: dict[str, float] = {}  # session_id -> failure timestamp
REHYDRATION_FAILURE_TTL_S: int = 300  # 5 min


def _get_semaphore() -> asyncio.Semaphore:
    """Lazy-init the global semaphore (must be created inside a running loop)."""
    global _REHYDRATION_SEMAPHORE  # noqa: PLW0603
    if _REHYDRATION_SEMAPHORE is None:
        _REHYDRATION_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REHYDRATIONS)
    return _REHYDRATION_SEMAPHORE


def set_session_weather(session_id: str, weather: SessionConditions) -> None:
    """Attach weather conditions to an existing session in the store."""
    sd = _store.get(session_id)
    if sd is not None:
        sd.weather = weather


def _evict_oldest() -> None:
    """Evict the oldest session(s) when the store exceeds MAX_SESSIONS."""
    while len(_store) > MAX_SESSIONS:
        oldest_id = next(iter(_store))
        _store.pop(oldest_id)
        logger.info(
            "Evicted oldest session %s (store at %d/%d)",
            oldest_id,
            len(_store),
            MAX_SESSIONS,
        )


def store_session(session_id: str, data: SessionData) -> None:
    """Persist a session in the in-memory store, evicting oldest if full."""
    _store[session_id] = data
    _evict_oldest()
    logger.info("Storing session %s (total: %d)", session_id, len(_store))


def get_session(session_id: str) -> SessionData | None:
    """Retrieve a session by ID, or None if not found."""
    result = _store.get(session_id)
    if result is None and _store:
        logger.debug(
            "Session %s not found in memory store (store has %d sessions)",
            session_id,
            len(_store),
        )
    return result


def get_session_for_user(session_id: str, user_id: str) -> SessionData | None:
    """Retrieve a session by ID, returning None if not found or not owned by user.

    During dev-auth-bypass (user_id="dev-user"), ownership is not enforced
    so that QA testing works without real users.

    Anonymous sessions (``is_anonymous=True``) are accessible by session_id
    regardless of user_id, since they have no owner yet.
    """
    sd = _store.get(session_id)
    if sd is None:
        return None
    # Anonymous sessions are accessible to anyone with the session_id
    if sd.is_anonymous:
        return sd
    # Skip ownership check for dev users or sessions without user_id set
    if user_id == "dev-user" or sd.user_id is None:
        return sd
    if sd.user_id != user_id:
        logger.warning(
            "Ownership mismatch for %s: stored=%s requested=%s",
            session_id,
            sd.user_id,
            user_id,
        )
        return None
    return sd


def sync_user_id(old_id: str, new_id: str) -> None:
    """Update all in-memory sessions owned by old_id to new_id.

    Called when ``ensure_user_exists`` migrates a user's OAuth ID so that
    ``get_session_for_user`` immediately works with the new ID without
    waiting for ``list_sessions`` to sync.
    """
    count = 0
    for sd in _store.values():
        if sd.user_id == old_id:
            sd.user_id = new_id
            count += 1
    if count:
        logger.info("Synced %d in-memory session(s) from user %s → %s", count, old_id, new_id)


def delete_session(session_id: str) -> bool:
    """Delete a session by ID. Returns True if it existed."""
    existed = _store.pop(session_id, None) is not None
    if existed:
        logger.info("Deleted session %s from memory (remaining: %d)", session_id, len(_store))
    else:
        logger.warning("Attempted to delete non-existent session %s", session_id)
    return existed


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


def cleanup_expired_anonymous() -> int:
    """Remove anonymous sessions older than ``ANON_SESSION_TTL``.

    Returns the count of removed sessions.
    """
    now = time.time()
    cutoff = now - ANON_SESSION_TTL
    expired = [sid for sid, sd in _store.items() if sd.is_anonymous and sd.created_at < cutoff]
    for sid in expired:
        _store.pop(sid, None)
    if expired:
        logger.info("Cleaned up %d expired anonymous session(s)", len(expired))
    return len(expired)


def get_anonymous_sessions_by_ip(ip: str) -> list[SessionData]:
    """Return all anonymous sessions originating from the given IP address."""
    return [sd for sd in _store.values() if sd.is_anonymous and sd.client_ip == ip]


def claim_session(session_id: str, user_id: str) -> bool:
    """Claim an anonymous session for an authenticated user.

    Sets ``is_anonymous=False`` and ``user_id`` on the session data.
    Returns True if the session existed and was claimed, False otherwise.
    """
    sd = _store.get(session_id)
    if sd is None or not sd.is_anonymous:
        return False
    sd.is_anonymous = False
    sd.user_id = user_id
    logger.info("Session %s claimed by user %s", session_id, user_id)
    return True


async def rehydrate_session(
    session_id: str,
    db: object,  # AsyncSession — typed loosely to avoid import cycle
) -> SessionData | None:
    """Re-process a session from DB-stored CSV on cache miss.

    Concurrency-safe: per-session lock (singleflight) + global semaphore
    (backpressure). Negative cache prevents repeated attempts on corrupt CSVs.
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

    from backend.api.db.models import Session as SessionModel
    from backend.api.db.models import SessionFile

    assert isinstance(db, _AsyncSession)

    # Check negative cache
    fail_ts = _REHYDRATION_FAILURES.get(session_id)
    if fail_ts and (time.time() - fail_ts) < REHYDRATION_FAILURE_TTL_S:
        logger.debug("Skipping rehydration for %s (negative cache hit)", session_id)
        return None

    # Get or create per-session lock (singleflight)
    if session_id not in _REHYDRATION_LOCKS:
        _REHYDRATION_LOCKS[session_id] = asyncio.Lock()

    async with _get_semaphore(), _REHYDRATION_LOCKS[session_id]:
        # Double-check after acquiring lock — another request may have rehydrated
        sd = get_session(session_id)
        if sd is not None:
            return sd

        # Check session exists in DB
        meta = await db.execute(
            select(SessionModel).where(SessionModel.session_id == session_id)
        )
        meta_row = meta.scalar_one_or_none()
        if meta_row is None:
            return None

        # Fetch CSV bytes
        file_result = await db.execute(
            select(SessionFile).where(SessionFile.session_id == session_id)
        )
        file_row = file_result.scalar_one_or_none()
        if file_row is None or file_row.csv_bytes is None:
            return None

        try:
            from backend.api.services.pipeline import reprocess_session_from_csv

            sd = await reprocess_session_from_csv(
                session_id=session_id,
                csv_bytes=file_row.csv_bytes,
                filename=file_row.filename,
            )
            if sd is not None:
                sd.user_id = meta_row.user_id
                logger.info("Lazy-rehydrated session %s", session_id)
            return sd
        except Exception:
            logger.exception("Failed to rehydrate session %s", session_id)
            _REHYDRATION_FAILURES[session_id] = time.time()
            return None

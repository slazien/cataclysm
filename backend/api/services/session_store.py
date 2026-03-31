"""In-memory session data store with LRU eviction.

Provides an OrderedDict-based store for session data. Each session holds
all pipeline outputs (parsed, processed, corners, consistency, gains,
grip) keyed by session_id. PostgreSQL persists metadata and raw CSV
bytes; this in-memory store provides fast access to the processed
telemetry.

Eviction: when the store exceeds ``MAX_SESSIONS``, the least-recently-
used sessions are evicted.  Lazy rehydration handles cache misses.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import OrderedDict
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


class RehydrationError(Exception):
    """Raised when a session exists in DB but failed to reprocess."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Failed to rehydrate session {session_id}")


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
    # Timezone resolved from GPS / track_db
    timezone_name: str | None = None
    session_date_local: str | None = None
    session_date_iso: str | None = None
    # Transient: nulled after DB persistence. Only DB copy (SessionFileModel) is authoritative.
    csv_bytes: bytes | None = field(default=None, repr=False)


# Maximum sessions to keep in memory before evicting LRU.
# Configurable via env var for tuning without redeploy.
MAX_SESSIONS: int = int(os.environ.get("MAX_SESSIONS", "100"))

# Anonymous session TTL in seconds (24 hours)
ANON_SESSION_TTL: int = 86400

# Module-level in-memory store (OrderedDict for LRU eviction)
_store: OrderedDict[str, SessionData] = OrderedDict()

# --- Rehydration concurrency controls ---
_MAX_REHYDRATION_LOCKS: int = 200
_REHYDRATION_LOCKS: OrderedDict[str, asyncio.Lock] = OrderedDict()
MAX_CONCURRENT_REHYDRATIONS: int = 4
_REHYDRATION_SEMAPHORE: asyncio.Semaphore | None = None
_MAX_REHYDRATION_FAILURES: int = 500
_REHYDRATION_FAILURES: OrderedDict[str, float] = OrderedDict()  # session_id -> ts
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
    """Evict the least-recently-used session(s) when the store exceeds MAX_SESSIONS."""
    from backend.api.services.demo_session import DEMO_SESSION_ID

    while len(_store) > MAX_SESSIONS:
        lru_id = next(iter(_store))
        if lru_id == DEMO_SESSION_ID:
            # Move demo to end (most recent) and try next
            _store.move_to_end(lru_id)
            lru_id = next(iter(_store))
            if lru_id == DEMO_SESSION_ID:
                break  # Only demo left, can't evict
        _store.pop(lru_id)
        logger.info(
            "Evicted LRU session %s (store at %d/%d)",
            lru_id,
            len(_store),
            MAX_SESSIONS,
        )


def store_session(session_id: str, data: SessionData) -> None:
    """Persist a session in the in-memory store, evicting oldest if full."""
    _store[session_id] = data
    _evict_oldest()
    logger.info("Storing session %s (total: %d)", session_id, len(_store))


def get_session(session_id: str) -> SessionData | None:
    """Retrieve a session by ID, or None if not found.

    On cache hit the session is moved to the end of the OrderedDict
    so that recently accessed sessions survive LRU eviction.
    """
    result = _store.get(session_id)
    if result is not None:
        _store.move_to_end(session_id)
    elif _store:
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

    Promotes the session in LRU on successful access.
    """
    from backend.api.services.demo_session import is_demo_session

    sd = _store.get(session_id)
    if sd is None:
        return None
    # Demo session is accessible to anyone
    if is_demo_session(session_id):
        _store.move_to_end(session_id)
        return sd
    # Anonymous sessions are accessible to anyone with the session_id
    if sd.is_anonymous:
        _store.move_to_end(session_id)
        return sd
    # Skip ownership check for dev users or sessions without user_id set
    if user_id == "dev-user" or sd.user_id is None:
        _store.move_to_end(session_id)
        return sd
    if sd.user_id != user_id:
        logger.warning(
            "Ownership mismatch for %s: stored=%s requested=%s",
            session_id,
            sd.user_id,
            user_id,
        )
        return None
    _store.move_to_end(session_id)
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
        list(_store.values()),
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

    # Check negative cache (with TTL eviction of expired entries)
    now = time.time()
    fail_ts = _REHYDRATION_FAILURES.get(session_id)
    if fail_ts is not None:
        if (now - fail_ts) < REHYDRATION_FAILURE_TTL_S:
            logger.debug("Skipping rehydration for %s (negative cache hit)", session_id)
            return None
        # Expired — remove stale entry
        _REHYDRATION_FAILURES.pop(session_id, None)

    # Get or create per-session lock (singleflight) with LRU eviction
    lock = _REHYDRATION_LOCKS.get(session_id)
    if lock is None:
        # Evict oldest locks if at capacity
        while len(_REHYDRATION_LOCKS) >= _MAX_REHYDRATION_LOCKS:
            _REHYDRATION_LOCKS.popitem(last=False)
        lock = asyncio.Lock()
        _REHYDRATION_LOCKS[session_id] = lock
    else:
        _REHYDRATION_LOCKS.move_to_end(session_id)

    async with _get_semaphore(), lock:
        # Double-check after acquiring lock — another request may have rehydrated
        sd = get_session(session_id)
        if sd is not None:
            return sd

        # Check session exists in DB
        meta = await db.execute(select(SessionModel).where(SessionModel.session_id == session_id))
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
            from backend.api.services.db_session_store import restore_weather_from_snapshot
            from backend.api.services.lap_tag_store import load_lap_tags
            from backend.api.services.pipeline import (
                recalculate_coaching_laps,
                reprocess_session_from_csv,
            )

            sd = await reprocess_session_from_csv(
                session_id=session_id,
                csv_bytes=file_row.csv_bytes,
                filename=file_row.filename,
            )

            # Restore metadata from DB (mirrors startup rehydration in main.py)
            sd.user_id = meta_row.user_id
            if meta_row.user_id is None:
                sd.is_anonymous = True
            if meta_row.snapshot_json:
                weather = restore_weather_from_snapshot(meta_row.snapshot_json)
                if weather is not None:
                    sd.weather = weather

            # Restore lap tags and recalculate coaching_laps
            sd.lap_tags = await load_lap_tags(db, session_id)
            all_laps = sorted(sd.processed.resampled_laps.keys())
            in_out = {all_laps[0], all_laps[-1]} if len(all_laps) >= 2 else set()
            sd.coaching_laps = recalculate_coaching_laps(
                all_laps=all_laps,
                anomalous=sd.anomalous_laps,
                in_out=in_out,
                best_lap=sd.processed.best_lap,
                tags=sd.lap_tags,
            )

            # Store AFTER all metadata is populated (prevents brief window
            # where session is visible with incomplete data)
            store_session(session_id, sd)
            logger.info("Lazy-rehydrated session %s", session_id)
            return sd
        except Exception:
            logger.exception("Failed to rehydrate session %s", session_id)
            # Record failure with bounded size (evict oldest on overflow)
            _REHYDRATION_FAILURES[session_id] = time.time()
            _REHYDRATION_FAILURES.move_to_end(session_id)
            while len(_REHYDRATION_FAILURES) > _MAX_REHYDRATION_FAILURES:
                _REHYDRATION_FAILURES.popitem(last=False)
            raise RehydrationError(session_id) from None

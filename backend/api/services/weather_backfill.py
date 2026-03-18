"""Background weather backfill service.

Scans the database for sessions missing weather data and fetches it from
Open-Meteo with rate limiting and retry logic.  Runs as an asyncio background
task started during application lifespan.

Two entry points:
- ``start_weather_backfill()`` — kicks off the background loop.
- ``stop_weather_backfill()``  — cancels it gracefully on shutdown.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from datetime import UTC, datetime

from cataclysm.equipment import SessionConditions
from cataclysm.weather_client import lookup_weather

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCAN_INTERVAL_S = 30 * 60  # Re-scan every 30 minutes
REQUEST_DELAY_S = 2.0  # Pause between Open-Meteo calls (be polite)
MAX_RETRIES_PER_SESSION = 3
INITIAL_SCAN_DELAY_S = 30  # Wait for startup to finish before first scan

# ---------------------------------------------------------------------------
# Lazy-retry cooldown (shared with the router for on-demand retries)
# ---------------------------------------------------------------------------

_weather_retry_cooldown: dict[str, float] = {}  # session_id → monotonic timestamp
WEATHER_RETRY_COOLDOWN_S = 300  # 5 minutes between attempts per session


def should_retry_weather(session_id: str) -> bool:
    """Return True if enough time has passed since the last weather retry."""
    last = _weather_retry_cooldown.get(session_id)
    if last is None:
        return True
    return (time.monotonic() - last) >= WEATHER_RETRY_COOLDOWN_S


def record_weather_attempt(session_id: str) -> None:
    """Record that a weather fetch was attempted for *session_id*."""
    _weather_retry_cooldown[session_id] = time.monotonic()


# ---------------------------------------------------------------------------
# Weather dict serialization helper (DRY)
# ---------------------------------------------------------------------------


def weather_to_dict(w: SessionConditions) -> dict[str, object]:
    """Serialize a SessionConditions to a snapshot-compatible dict."""
    return {
        "track_condition": w.track_condition.value
        if hasattr(w.track_condition, "value")
        else str(w.track_condition),
        "ambient_temp_c": w.ambient_temp_c,
        "track_temp_c": w.track_temp_c,
        "humidity_pct": w.humidity_pct,
        "wind_speed_kmh": w.wind_speed_kmh,
        "wind_direction_deg": w.wind_direction_deg,
        "precipitation_mm": w.precipitation_mm,
        "surface_water_mm": w.surface_water_mm,
        "weather_source": w.weather_source,
        "weather_confidence": w.weather_confidence,
        "dew_point_c": w.dew_point_c,
        "track_condition_is_manual": w.track_condition_is_manual,
        "timezone_name": w.timezone_name,
    }


# ---------------------------------------------------------------------------
# Re-backfill (admin-triggered, re-runs surface water model on all sessions)
# ---------------------------------------------------------------------------

REBACKFILL_BATCH_DELAY_S = 0.5


async def rebackfill_all_sessions() -> dict[str, int]:
    """Re-run the surface water model for all existing sessions.

    Returns stats: {updated, skipped_manual, skipped_no_coords, failed, total}.
    Respects manual overrides (track_condition_is_manual=True).
    Uses a semaphore to avoid hammering Open-Meteo.
    """
    from sqlalchemy import select

    from backend.api.db.database import async_session_factory
    from backend.api.db.models import Session as SessionModel
    from backend.api.services import session_store

    stats: dict[str, int] = {
        "updated": 0,
        "skipped_manual": 0,
        "skipped_no_coords": 0,
        "failed": 0,
        "total": 0,
    }

    async with async_session_factory() as db:
        stmt = select(SessionModel).where(
            SessionModel.snapshot_json.isnot(None),
        )
        rows = (await db.execute(stmt)).scalars().all()
        stats["total"] = len(rows)

        for row in rows:
            snap = dict(row.snapshot_json or {})
            existing_weather = snap.get("weather", {})

            # Skip manual overrides
            if existing_weather.get("track_condition_is_manual", False):
                stats["skipped_manual"] += 1
                continue

            # Extract GPS centroid
            centroid = snap.get("gps_centroid")
            lat: float | None = None
            lon: float | None = None
            if centroid:
                lat = centroid.get("lat")
                lon = centroid.get("lon")

            if lat is None or lon is None:
                # Try in-memory session for GPS data
                sd = session_store.get_session(row.session_id)
                if sd is not None and hasattr(sd, "parsed"):
                    df = sd.parsed.data
                    if not df.empty and "lat" in df.columns and "lon" in df.columns:
                        lat = float(df["lat"].mean())
                        lon = float(df["lon"].mean())

            if lat is None or lon is None:
                stats["skipped_no_coords"] += 1
                continue

            # Parse session date
            session_dt: datetime | None = None
            if row.session_date:
                dt = row.session_date
                session_dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt

            if session_dt is None:
                stats["skipped_no_coords"] += 1
                continue

            try:
                weather = await lookup_weather(lat, lon, session_dt)
                if weather is None:
                    stats["failed"] += 1
                    await asyncio.sleep(REBACKFILL_BATCH_DELAY_S)
                    continue

                # Preserve track_temp_c and timezone_name from old data
                if existing_weather.get("track_temp_c") is not None:
                    weather.track_temp_c = existing_weather["track_temp_c"]
                if existing_weather.get("timezone_name") is not None:
                    weather.timezone_name = existing_weather["timezone_name"]

                snap["weather"] = weather_to_dict(weather)
                row.snapshot_json = snap
                await db.commit()

                # Update in-memory store
                sd = session_store.get_session(row.session_id)
                if sd is not None:
                    sd.weather = weather

                stats["updated"] += 1
                logger.info(
                    "Rebackfilled weather for %s: %s (%.2f confidence)",
                    row.session_id,
                    weather.track_condition.value
                    if hasattr(weather.track_condition, "value")
                    else str(weather.track_condition),
                    weather.weather_confidence or 0,
                )
            except Exception:
                logger.warning(
                    "Rebackfill failed for %s",
                    row.session_id,
                    exc_info=True,
                )
                await db.rollback()
                stats["failed"] += 1

            await asyncio.sleep(REBACKFILL_BATCH_DELAY_S)

    logger.info("Weather rebackfill complete: %s", stats)
    return stats


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

_backfill_task: asyncio.Task[None] | None = None
_retry_counts: dict[str, int] = {}  # session_id → number of failed attempts


async def _backfill_loop() -> None:
    """Periodically scan DB for sessions without weather and fetch it."""
    await asyncio.sleep(INITIAL_SCAN_DELAY_S)

    while True:
        try:
            await _run_backfill_scan()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Weather backfill scan failed", exc_info=True)

        await asyncio.sleep(SCAN_INTERVAL_S)


async def _run_backfill_scan() -> None:
    """One scan: find sessions missing weather, fetch and persist."""
    from sqlalchemy import select

    from backend.api.db.database import async_session_factory
    from backend.api.db.models import Session as SessionModel
    from backend.api.services import session_store

    async with async_session_factory() as db:
        # Find sessions where snapshot_json has no weather key
        stmt = select(SessionModel).where(
            SessionModel.snapshot_json.isnot(None),
        )
        rows = (await db.execute(stmt)).scalars().all()

        candidates = [
            r
            for r in rows
            if not (r.snapshot_json or {}).get("weather")
            and _retry_counts.get(r.session_id, 0) < MAX_RETRIES_PER_SESSION
        ]

        if not candidates:
            return

        logger.info("Weather backfill: %d session(s) missing weather data", len(candidates))

        backfilled = 0
        for row in candidates:
            snap = dict(row.snapshot_json or {})

            # Extract GPS centroid
            centroid = snap.get("gps_centroid")
            lat: float | None = None
            lon: float | None = None

            if centroid:
                lat = centroid.get("lat")
                lon = centroid.get("lon")

            if lat is None or lon is None:
                # Try in-memory session for GPS data
                sd = session_store.get_session(row.session_id)
                if sd is not None and hasattr(sd, "parsed"):
                    df = sd.parsed.data
                    if not df.empty and "lat" in df.columns and "lon" in df.columns:
                        lat = float(df["lat"].mean())
                        lon = float(df["lon"].mean())

            if lat is None or lon is None:
                _retry_counts[row.session_id] = MAX_RETRIES_PER_SESSION  # skip permanently
                continue

            # Parse session date
            session_dt: datetime | None = None
            if row.session_date:
                dt = row.session_date
                session_dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt

            if session_dt is None:
                _retry_counts[row.session_id] = MAX_RETRIES_PER_SESSION
                continue

            try:
                weather = await lookup_weather(lat, lon, session_dt)
                if weather is None:
                    _retry_counts[row.session_id] = _retry_counts.get(row.session_id, 0) + 1
                    await asyncio.sleep(REQUEST_DELAY_S)
                    continue

                # Persist to DB (commit per-row so failures don't roll back others)
                snap["weather"] = weather_to_dict(weather)
                row.snapshot_json = snap
                await db.commit()

                # Update in-memory store
                sd = session_store.get_session(row.session_id)
                if sd is not None:
                    sd.weather = weather

                # Evict from tracking dicts — this session is done
                _weather_retry_cooldown.pop(row.session_id, None)
                _retry_counts.pop(row.session_id, None)

                backfilled += 1
                logger.info(
                    "Backfilled weather for %s: %s, %.1f°C",
                    row.session_id,
                    weather.track_condition.value
                    if hasattr(weather.track_condition, "value")
                    else str(weather.track_condition),
                    weather.ambient_temp_c or 0,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Weather backfill failed for %s", row.session_id, exc_info=True)
                _retry_counts[row.session_id] = _retry_counts.get(row.session_id, 0) + 1

            # Rate limit between requests
            await asyncio.sleep(REQUEST_DELAY_S)

        if backfilled:
            logger.info("Weather backfill complete: %d session(s) updated", backfilled)


def start_weather_backfill() -> None:
    """Start the background weather backfill task."""
    global _backfill_task
    if _backfill_task is not None:
        return
    _backfill_task = asyncio.create_task(_backfill_loop(), name="weather-backfill")
    logger.info("Weather backfill background task started")


async def stop_weather_backfill() -> None:
    """Cancel and await the background weather backfill task."""
    global _backfill_task
    if _backfill_task is None:
        return
    _backfill_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await _backfill_task
    _backfill_task = None
    logger.info("Weather backfill background task stopped")

"""FastAPI application entry point."""

from __future__ import annotations

import logging
import logging.config
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC
from typing import Annotated, cast

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from backend.api.config import Settings
from backend.api.db.database import get_db
from backend.api.rate_limit import limiter
from backend.api.routers import (
    achievements,
    admin,
    analysis,
    auth,
    coaching,
    equipment,
    instructor,
    leaderboards,
    notes,
    organizations,
    progress,
    sessions,
    sharing,
    stickies,
    track_admin,
    tracks,
    trends,
    wrapped,
)


def _configure_logging() -> None:
    """Configure root logger with timestamp, level, and module context."""
    import os

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s:%(lineno)d %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
            "loggers": {
                "uvicorn.access": {"level": "WARNING"},
                "sqlalchemy.engine": {"level": "WARNING"},
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
                "anthropic": {"level": "WARNING"},
                "openai": {"level": "WARNING"},
                "google": {"level": "WARNING"},
            },
        }
    )


_configure_logging()

logger = logging.getLogger(__name__)

# Only rehydrate the N most-recent sessions at startup.  Older sessions
# are lazily rehydrated on demand (2-5 s).
STARTUP_REHYDRATION_LIMIT: int = int(os.environ.get("STARTUP_REHYDRATION_LIMIT", "100"))


async def _reload_sessions_from_db() -> int:
    """Re-process CSV files stored in the database into the in-memory store.

    This ensures sessions survive Railway redeployments where ephemeral
    disk is wiped.  Each ``SessionFile`` row contains the raw CSV bytes
    that were originally uploaded.
    """
    from sqlalchemy import select

    from backend.api.db.database import async_session_factory
    from backend.api.db.models import Session as SessionModel
    from backend.api.db.models import SessionFile as SessionFileModel
    from backend.api.services.db_session_store import restore_weather_from_snapshot
    from backend.api.services.lap_tag_store import load_lap_tags
    from backend.api.services.pipeline import process_upload, recalculate_coaching_laps
    from backend.api.services.session_store import get_session

    loaded = 0
    try:
        async with async_session_factory() as db:
            stmt = (
                select(SessionFileModel)
                .order_by(SessionFileModel.created_at.desc())
                .limit(STARTUP_REHYDRATION_LIMIT)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()
            logger.info(
                "Found %d session file(s) in database (limit %d)",
                len(rows),
                STARTUP_REHYDRATION_LIMIT,
            )

            # Build a lookup of session metadata (for snapshot_json) keyed by session_id
            sess_result = await db.execute(select(SessionModel))
            sess_rows = {s.session_id: s for s in sess_result.scalars().all()}

            for row in rows:
                try:
                    upload_result = await process_upload(row.csv_bytes, row.filename)
                    sid = str(upload_result["session_id"])

                    # Restore immutable data (weather, GPS centroid, etc.) from DB
                    sess_meta = sess_rows.get(sid) or sess_rows.get(row.session_id)
                    sd = get_session(sid)
                    if sd is not None and sess_meta:
                        # Tag session with owner for access control
                        sd.user_id = sess_meta.user_id
                        if sess_meta.user_id is None:
                            sd.is_anonymous = True
                        if sess_meta.snapshot_json:
                            weather = restore_weather_from_snapshot(sess_meta.snapshot_json)
                            if weather is not None:
                                sd.weather = weather
                    elif sd is not None:
                        logger.warning(
                            "Reload: %s has no session metadata — user_id unset",
                            sid,
                        )

                    # Overlay persisted lap tags and recalculate coaching_laps
                    if sd is not None:
                        sd.lap_tags = await load_lap_tags(db, sid)
                        all_laps = sorted(sd.processed.resampled_laps.keys())
                        in_out = {all_laps[0], all_laps[-1]} if len(all_laps) >= 2 else set()
                        sd.coaching_laps = recalculate_coaching_laps(
                            all_laps=all_laps,
                            anomalous=sd.anomalous_laps,
                            in_out=in_out,
                            best_lap=sd.processed.best_lap,
                            tags=sd.lap_tags,
                        )

                    loaded += 1
                except (ValueError, KeyError, IndexError, OSError) as exc:
                    logger.warning(
                        "Failed to reload session %s from DB: %s",
                        row.session_id,
                        exc,
                        exc_info=True,
                    )
    except (SQLAlchemyError, OSError):
        logger.warning("Database session reload failed", exc_info=True)

    return loaded


async def _ensure_track_references() -> int:
    """Build missing track reference NPZ files for all unique tracks in the DB.

    After startup rehydration (which is capped by STARTUP_REHYDRATION_LIMIT),
    some tracks may lack NPZ files because none of their sessions were in the
    rehydration window.  This function queries all distinct track names, checks
    which NPZ files are missing, and processes ONE session per missing track
    to generate the reference.
    """
    import re
    from pathlib import Path

    from sqlalchemy import distinct, select

    from backend.api.db.database import async_session_factory
    from backend.api.db.models import Session as SessionModel
    from backend.api.db.models import SessionFile as SessionFileModel
    from backend.api.services.pipeline import process_upload

    track_ref_dir = Path(
        os.environ.get(
            "TRACK_REF_DIR",
            str(Path(__file__).resolve().parent.parent.parent / "data" / "track_reference"),
        )
    )
    track_ref_dir.mkdir(parents=True, exist_ok=True)

    built = 0
    try:
        async with async_session_factory() as db:
            # Get all unique track names from sessions table
            result = await db.execute(
                select(distinct(SessionModel.track_name)).where(
                    SessionModel.track_name.isnot(None),
                    SessionModel.track_name != "",
                )
            )
            track_names: list[str] = [row[0] for row in result.all()]

            for track_name in track_names:
                # Slugify using the same logic as track_slug_from_layout
                slug = re.sub(r"[^a-z0-9]+", "-", track_name.lower().strip()).strip("-")
                npz_path = track_ref_dir / f"{slug}.npz"

                if npz_path.exists():
                    continue

                # Find one session file for this track to build the reference from
                sf_result = await db.execute(
                    select(SessionFileModel)
                    .join(SessionModel, SessionModel.session_id == SessionFileModel.session_id)
                    .where(SessionModel.track_name == track_name)
                    .order_by(SessionFileModel.created_at.desc())
                    .limit(1)
                )
                sf_row = sf_result.scalar_one_or_none()
                if sf_row is None:
                    continue

                try:
                    await process_upload(sf_row.csv_bytes, sf_row.filename)
                    if npz_path.exists():
                        built += 1
                        logger.info(
                            "Built missing track reference for %s (%s)",
                            track_name,
                            slug,
                        )
                except (ValueError, KeyError, IndexError, OSError) as exc:
                    logger.warning(
                        "Failed to build track reference for %s: %s",
                        track_name,
                        exc,
                    )
    except (SQLAlchemyError, OSError):
        logger.warning("Track reference build failed", exc_info=True)

    return built


async def _backfill_sidebar_scores() -> int:
    """Backfill snapshot_json.scores for sessions that lack persisted scores.

    Temporarily rehydrates each session (via process_upload) to compute scores,
    persists them to snapshot_json, then evicts the session from memory to keep
    RAM stable.  Does NOT trigger auto-coaching.
    """
    from sqlalchemy import select

    from backend.api.db.database import async_session_factory
    from backend.api.db.models import Session as SessionModel
    from backend.api.db.models import SessionFile as SessionFileModel
    from backend.api.routers.sessions import _compute_session_score, _equipment_fields
    from backend.api.routers.sessions import (
        _persist_sidebar_fields as persist_sidebar,
    )
    from backend.api.services.pipeline import process_upload
    from backend.api.services.session_store import delete_session, get_session

    backfilled = 0
    try:
        async with async_session_factory() as db:
            # Find sessions missing scores in snapshot_json
            result = await db.execute(select(SessionModel).where(SessionModel.user_id.isnot(None)))
            rows = result.scalars().all()
            missing = [r for r in rows if not (r.snapshot_json or {}).get("scores")]

            if not missing:
                return 0

            logger.info("Score backfill: %d session(s) need scores", len(missing))

            for row in missing:
                # Check if already in memory (from rehydration)
                already_in_memory = get_session(row.session_id) is not None

                if not already_in_memory:
                    # Need CSV bytes to rehydrate
                    sf_result = await db.execute(
                        select(SessionFileModel).where(
                            SessionFileModel.session_id == row.session_id
                        )
                    )
                    sf_row = sf_result.scalar_one_or_none()
                    if sf_row is None:
                        continue

                    try:
                        await process_upload(sf_row.csv_bytes, sf_row.filename)
                    except (ValueError, KeyError, IndexError, OSError) as exc:
                        logger.warning(
                            "Score backfill: failed to rehydrate %s: %s",
                            row.session_id,
                            exc,
                        )
                        continue

                sd = get_session(row.session_id)
                if sd is None:
                    continue

                try:
                    score = await _compute_session_score(sd)
                    tire_model, compound_category, profile_name = _equipment_fields(sd.session_id)
                    await persist_sidebar(
                        db, sd.session_id, score, tire_model, compound_category, profile_name
                    )
                    await db.commit()
                    backfilled += 1
                except Exception:
                    logger.warning(
                        "Score backfill: failed to compute/persist for %s",
                        row.session_id,
                        exc_info=True,
                    )

                # Evict from memory if we loaded it just for backfill
                if not already_in_memory:
                    delete_session(row.session_id)

    except (SQLAlchemyError, OSError):
        logger.warning("Score backfill failed", exc_info=True)

    return backfilled


async def _reload_sessions_from_disk() -> int:
    """Re-process CSV files from the data directory into the in-memory store.

    This ensures sessions survive backend restarts.  The DB keeps metadata
    (for the session list) but telemetry lives in memory only — this fills
    the gap by re-processing the CSV files that are already on disk.

    Also persists session metadata to the database for the dev user so that
    ``list_sessions_for_user`` returns results after a restart.
    """
    from pathlib import Path

    from backend.api.db.database import async_session_factory
    from backend.api.db.models import Session as SessionModel
    from backend.api.db.models import User as UserModel
    from backend.api.services.db_session_store import _parse_session_date
    from backend.api.services.pipeline import process_file_path
    from backend.api.services.session_store import get_session

    data_dir = Path(settings.session_data_dir)
    if not data_dir.is_dir():
        logger.info("Session data dir %s does not exist, skipping reload", data_dir)
        return 0

    csv_files = sorted(data_dir.rglob("*.csv"))
    logger.info("Found %d CSV file(s) in %s", len(csv_files), data_dir)
    loaded = 0
    dev_user_id = "dev-user"

    async with async_session_factory() as db:
        # Ensure the dev user row exists (FK target for sessions)
        existing = await db.get(UserModel, dev_user_id)
        if existing is None:
            db.add(
                UserModel(
                    id=dev_user_id,
                    email="dev@localhost",
                    name="Dev User",
                )
            )
            await db.flush()

        for csv_path in csv_files:
            try:
                result = await process_file_path(csv_path)
                sid = str(result["session_id"])
                sd = get_session(sid)
                if sd is not None:
                    sd.user_id = dev_user_id
                    snap = sd.snapshot
                    date_val = (
                        _parse_session_date(snap.metadata.session_date)
                        if isinstance(snap.metadata.session_date, str)
                        else snap.metadata.session_date
                    )
                    # merge handles both insert and update (idempotent)
                    await db.merge(
                        SessionModel(
                            session_id=sid,
                            user_id=dev_user_id,
                            track_name=snap.metadata.track_name,
                            session_date=date_val,
                            file_key=sid,
                            n_laps=snap.n_laps,
                            n_clean_laps=snap.n_clean_laps,
                            best_lap_time_s=snap.best_lap_time_s,
                            top3_avg_time_s=snap.top3_avg_time_s,
                            avg_lap_time_s=snap.avg_lap_time_s,
                            consistency_score=snap.consistency_score,
                        )
                    )
                    loaded += 1
            except (ValueError, KeyError, IndexError, OSError):
                logger.warning("Failed to reload %s on startup", csv_path.name, exc_info=True)
        await db.commit()

    return loaded


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    from cataclysm.llm_gateway import set_usage_event_sink

    from backend.api.services.llm_usage_store import (
        enqueue_llm_usage_event,
        prune_old_llm_usage_events,
        start_llm_usage_persistence_worker,
        stop_llm_usage_persistence_worker,
    )
    from backend.api.services.runtime_settings import (
        start_runtime_settings_sync,
        stop_runtime_settings_sync,
    )

    usage_persistence_started = False
    runtime_settings_started = False

    await start_runtime_settings_sync(default_routing_enabled=bool(settings.llm_routing_enabled))
    runtime_settings_started = True

    if settings.llm_usage_telemetry_enabled:
        await start_llm_usage_persistence_worker()
        set_usage_event_sink(enqueue_llm_usage_event)
        usage_persistence_started = True
        try:
            from backend.api.db.database import async_session_factory as _usage_asf

            async with _usage_asf() as _usage_db:
                deleted = await prune_old_llm_usage_events(
                    _usage_db, retention_days=settings.llm_usage_retention_days
                )
                if deleted:
                    logger.info(
                        "Pruned %d old LLM usage event(s) older than %d day(s)",
                        deleted,
                        settings.llm_usage_retention_days,
                    )
        except Exception:
            logger.warning("Failed to prune old LLM usage events", exc_info=True)
    else:
        set_usage_event_sink(None)

    # Coaching reports are now persisted in PostgreSQL with lazy DB fallback —
    # no startup loading needed.

    from backend.api.services.equipment_store import (
        init_equipment_dir,
        load_equipment_from_db,
        load_persisted_profiles,
        load_persisted_session_equipment,
    )

    init_equipment_dir(settings.equipment_data_dir)

    # Try DB first (survives Railway redeployments), fall back to disk
    n_eq, n_se = await load_equipment_from_db()
    if n_eq or n_se:
        logger.info("Loaded %d equipment profile(s), %d session assignment(s) from DB", n_eq, n_se)
    else:
        # Fallback to disk for local dev
        n_eq = load_persisted_profiles()
        n_se = load_persisted_session_equipment()
        if n_eq or n_se:
            logger.info(
                "Loaded %d equipment profile(s), %d session assignment(s) from disk", n_eq, n_se
            )

    # Seed hardcoded tracks into DB (idempotent — skips existing slugs)
    from backend.api.db.database import async_session_factory as _corner_asf
    from backend.api.services.track_seed import seed_tracks_from_hardcoded

    try:
        async with _corner_asf() as _seed_db:
            n_seeded = await seed_tracks_from_hardcoded(_seed_db)
            await _seed_db.commit()
            if n_seeded:
                logger.info("Seeded %d hardcoded track(s) into DB", n_seeded)
    except Exception:
        logger.warning("Failed to seed hardcoded tracks into DB", exc_info=True)

    # Load DB tracks into hybrid cache (DB-first, Python constants fallback)
    from cataclysm.track_db_hybrid import load_db_tracks

    try:
        async with _corner_asf() as _tracks_db:
            n_tracks = await load_db_tracks(_tracks_db)
            if n_tracks:
                logger.info("Hybrid track cache seeded with %d DB track(s)", n_tracks)
    except Exception:
        logger.warning("Failed to load DB tracks into hybrid cache", exc_info=True)

    # Migrate legacy TrackCornerConfig → TrackCornerV2 (one-time per startup)
    from backend.api.services.track_corners import (
        compute_all_corner_hashes,
        migrate_legacy_corner_configs,
    )

    try:
        async with _corner_asf() as _migrate_db:
            migrated = await migrate_legacy_corner_configs(_migrate_db)
            if migrated:
                logger.info("Migrated %d legacy corner config(s) to TrackCornerV2", migrated)
    except Exception:
        logger.warning("Failed to migrate legacy corner configs", exc_info=True)

    # Compute corner version hashes for staleness detection
    compute_all_corner_hashes()

    # Reload CSV session data into memory so GET endpoints don't 404
    # Try database first (survives Railway redeployments), fall back to disk
    n_sessions = await _reload_sessions_from_db()
    if n_sessions:
        logger.info("Reloaded %d session(s) from database", n_sessions)
    else:
        # Fallback to disk reload for local dev
        n_sessions = await _reload_sessions_from_disk()
        if n_sessions:
            logger.info("Reloaded %d session(s) from disk", n_sessions)

    # Build missing track references for tracks not covered by rehydration
    n_refs = await _ensure_track_references()
    if n_refs:
        logger.info("Built %d missing track reference(s) at startup", n_refs)

    # Backfill sidebar scores for sessions that predate score persistence
    n_backfilled = await _backfill_sidebar_scores()
    if n_backfilled:
        logger.info("Backfilled sidebar scores for %d session(s)", n_backfilled)

    # Clean up any expired anonymous sessions from a previous run
    from backend.api.services.session_store import cleanup_expired_anonymous, list_sessions

    n_cleaned = cleanup_expired_anonymous()
    if n_cleaned:
        logger.info("Cleaned up %d expired anonymous session(s) at startup", n_cleaned)

    # Clean up expired anonymous sessions from the database (>24h, unclaimed)
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import select as _cleanup_select

        from backend.api.db.database import async_session_factory as _cleanup_asf
        from backend.api.db.models import Session as SessionModel

        async with _cleanup_asf() as _cleanup_db:
            cutoff = datetime.now(UTC) - timedelta(hours=24)
            result = await _cleanup_db.execute(
                _cleanup_select(SessionModel).where(
                    SessionModel.user_id.is_(None),
                    SessionModel.session_date < cutoff,
                )
            )
            expired_rows = result.scalars().all()
            for row in expired_rows:
                await _cleanup_db.delete(row)  # CASCADE deletes SessionFile
            if expired_rows:
                await _cleanup_db.commit()
                logger.info("Cleaned up %d expired anonymous DB session(s)", len(expired_rows))
    except Exception:
        logger.warning("Failed to clean up anonymous DB sessions", exc_info=True)

    # Auto-generate coaching reports for sessions that don't have one yet
    from backend.api.db.database import async_session_factory as _asf
    from backend.api.db.models import User as UserModel
    from backend.api.routers.coaching import trigger_auto_coaching
    from backend.api.schemas.coaching import SkillLevel

    # Build user_id → skill_level lookup so we generate the right report
    _valid: tuple[SkillLevel, ...] = ("novice", "intermediate", "advanced")
    user_skill: dict[str, SkillLevel] = {}
    try:
        async with _asf() as _db:
            from sqlalchemy import select as _sa_select

            for u in (await _db.execute(_sa_select(UserModel))).scalars():
                raw = u.skill_level if u.skill_level in _valid else "intermediate"
                user_skill[u.id] = cast(SkillLevel, raw)
    except Exception:
        logger.warning("Failed to load user skill levels", exc_info=True)

    all_sessions = list_sessions()
    if settings.llm_lazy_generation_enabled:
        if all_sessions:
            logger.info(
                "LLM lazy generation enabled; skipped startup coaching pre-generation "
                "for %d session(s)",
                len(all_sessions),
            )
    else:
        _auto_triggered = 0
        max_auto = 5  # Cap startup auto-coaching to avoid thundering herd
        for sd in all_sessions:
            if not sd.is_anonymous:
                skill: SkillLevel = user_skill.get(sd.user_id or "", "intermediate")
                if _auto_triggered >= max_auto:
                    logger.info(
                        "Auto-coaching cap reached (%d); deferring remaining sessions",
                        max_auto,
                    )
                    break
                await trigger_auto_coaching(sd.session_id, sd, skill_level=skill)
                # Count how many actually triggered (check if is_generating changed)
                from backend.api.services.coaching_store import is_generating

                if is_generating(sd.session_id, skill):
                    _auto_triggered += 1
        if all_sessions:
            logger.info(
                "Checked %d session(s) for missing coaching reports; %d triggered",
                len(all_sessions),
                _auto_triggered,
            )

    # Start background weather backfill for sessions missing weather data
    from backend.api.services.weather_backfill import (
        start_weather_backfill,
        stop_weather_backfill,
    )

    start_weather_backfill()

    try:
        yield
    finally:
        await stop_weather_backfill()
        set_usage_event_sink(None)
        if usage_persistence_started:
            await stop_llm_usage_persistence_worker()
        if runtime_settings_started:
            await stop_runtime_settings_sync()

        # Shutdown: clear in-memory store
        from backend.api.services.session_store import clear_all

        clear_all()


load_dotenv()  # Populate os.environ from .env before reading settings
settings = Settings()

if settings.dev_auth_bypass:
    logger.warning(
        "DEV_AUTH_BYPASS is ENABLED — all authentication is disabled! "
        "All requests authenticate as 'dev-user'. "
        "Do NOT use this in production with real user data."
    )

app = FastAPI(
    title="Cataclysm API",
    description="Motorsport telemetry analysis and AI coaching",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# -- Rate limiting ---------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


# -- Cache-Control middleware --------------------------------------------------

# Route prefix -> Cache-Control header value
_CACHE_RULES: list[tuple[str, str]] = [
    # Coaching endpoints: mutable (generated on demand)
    ("/api/coaching", "no-cache"),
    # Equipment endpoints: mutable (CRUD)
    ("/api/equipment", "no-cache"),
    # Leaderboard endpoints: mutable (changes on new records)
    ("/api/leaderboards", "no-cache"),
    # Notes endpoints: mutable (CRUD)
    ("/api/notes", "no-cache"),
    # Stickies endpoints: mutable (CRUD)
    ("/api/stickies", "no-cache"),
    # Session list: mutable (changes on upload/delete)
    ("/api/sessions/upload", "no-cache"),
    # Analysis sub-routes: immutable once computed for a session
    ("/api/sessions/", "max-age=60"),
    # Trends: immutable for a given set of sessions
    ("/api/trends", "max-age=60"),
    # Tracks: static reference data
    ("/api/tracks", "max-age=3600"),
]


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Set Cache-Control headers based on the request path and method."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip WebSocket connections — BaseHTTPMiddleware cannot handle them
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        response = await call_next(request)

        # Only apply to successful GET responses without an existing header
        if request.method != "GET" or response.status_code >= 400:
            return response
        if "cache-control" in response.headers:
            return response

        path = request.url.path
        for prefix, value in _CACHE_RULES:
            if path.startswith(prefix):
                response.headers["Cache-Control"] = value
                break
        else:
            # Default: no-cache for any unmatched GET
            response.headers["Cache-Control"] = "no-cache"

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        import time

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        # Skip noisy health/metrics polling
        path = request.url.path
        if path not in ("/health", "/metrics"):
            logger.info(
                "%s %s %d %.0fms",
                request.method,
                path,
                response.status_code,
                duration_ms,
            )

        return response


# -- Exception handlers --------------------------------------------------------


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions.

    Logs the full traceback server-side but returns a safe generic message
    to the client (no internal details leaked).
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Return 422 for ValueError (bad input data that passed validation)."""
    logger.warning("ValueError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid input data"},
    )


# -- Middleware (order matters: last added = first executed) ------------------

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CacheControlMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Prometheus metrics -------------------------------------------------------

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# -- Routers -----------------------------------------------------------------

app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(track_admin.router, prefix="/api/track-admin", tags=["track-admin"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(analysis.router, prefix="/api/sessions", tags=["analysis"])
app.include_router(coaching.router, prefix="/api/coaching", tags=["coaching"])
app.include_router(equipment.router, prefix="/api/equipment", tags=["equipment"])
app.include_router(trends.router, prefix="/api/trends", tags=["trends"])
app.include_router(tracks.router, prefix="/api/tracks", tags=["tracks"])
app.include_router(wrapped.router, prefix="/api/wrapped", tags=["wrapped"])
app.include_router(achievements.router, prefix="/api/achievements", tags=["achievements"])
app.include_router(leaderboards.router, prefix="/api/leaderboards", tags=["leaderboards"])
app.include_router(sharing.router, prefix="/api/sharing", tags=["sharing"])
app.include_router(instructor.router, prefix="/api/instructor", tags=["instructor"])
app.include_router(organizations.router, prefix="/api/orgs", tags=["organizations"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(stickies.router, prefix="/api/stickies", tags=["stickies"])
app.include_router(progress.router, prefix="/api/progress", tags=["progress"])


# -- Health ------------------------------------------------------------------


@app.get("/health")
async def health_check(db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, str]:
    """Health check that verifies database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001
        db_status = "error"
    status = "ok" if db_status == "ok" else "degraded"
    return {"status": status, "db": db_status}

"""Session management endpoints: upload, list, get, delete."""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Annotated, Literal, cast

import numpy as np
from cataclysm.constants import MPS_TO_MPH
from fastapi import APIRouter, Body, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.config import Settings
from backend.api.db.database import get_db
from backend.api.db.models import SessionFile as SessionFileModel
from backend.api.dependencies import (
    AuthenticatedUser,
    get_current_user,
    get_optional_user,
    get_settings,
    get_user_or_anon,
)
from backend.api.rate_limit import limiter
from backend.api.routers.coaching import trigger_auto_coaching
from backend.api.schemas.comparison import ComparisonResult
from backend.api.schemas.session import (
    ClaimSessionRequest,
    LapData,
    LapSummary,
    SessionList,
    SessionSummary,
    UploadResponse,
)
from backend.api.schemas.track_guide import (
    KeyCorner,
    TrackGuideCorner,
    TrackGuideLandmark,
    TrackGuideResponse,
    TrackPeculiarity,
)
from backend.api.services import equipment_store, session_store
from backend.api.services.anon_rate_limit import check_and_record_anon_upload
from backend.api.services.coaching_store import clear_coaching_data, get_any_coaching_report
from backend.api.services.comparison import compare_sessions as run_comparison
from backend.api.services.db_session_store import (
    delete_session_db,
    ensure_user_exists,
    get_session_for_user_with_db_sync,
    list_sessions_for_user,
    restore_weather_from_snapshot,
    store_session_db,
)
from backend.api.services.lap_tag_store import save_lap_tags
from backend.api.services.pipeline import (
    invalidate_physics_cache,
    process_upload,
    recalculate_coaching_laps,
    trigger_lidar_prefetch,
)
from backend.api.services.weather_backfill import weather_to_dict

logger = logging.getLogger(__name__)

router = APIRouter()


async def _auto_fetch_weather(sd: session_store.SessionData) -> None:
    """Auto-fetch weather for a session using its GPS centroid and date.

    Weather is immutable per session — fetched once and stored permanently.
    """
    from datetime import UTC, datetime

    from cataclysm.weather_client import lookup_weather

    parsed = sd.parsed
    df = parsed.data
    if df.empty or "lat" not in df.columns or "lon" not in df.columns:
        return

    lat = float(df["lat"].mean())
    lon = float(df["lon"].mean())

    # Parse session date + derive approximate hour from first timestamp
    date_str = parsed.metadata.session_date
    hour = 12  # default noon
    if "timestamp" in df.columns:
        try:
            first_ts = float(df["timestamp"].iloc[0])
            dt = datetime.fromtimestamp(first_ts, tz=UTC)
            hour = dt.hour
        except (ValueError, TypeError, OSError):
            pass

    # Try parsing session date
    session_dt: datetime | None = None
    for fmt in [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y,%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]:
        try:
            session_dt = datetime.strptime(date_str.strip(), fmt).replace(  # noqa: DTZ007
                hour=hour, tzinfo=UTC
            )
            break
        except ValueError:
            continue

    if session_dt is None:
        logger.warning("Could not parse session date '%s' for weather lookup", date_str)
        return

    weather = await lookup_weather(lat, lon, session_dt)
    if weather is not None:
        sd.weather = weather
        logger.info(
            "Auto-fetched weather for %s: %s, %.1f°C",
            sd.session_id,
            weather.track_condition.value,
            weather.ambient_temp_c or 0,
        )


async def _lazy_weather_fetch(sd: session_store.SessionData, session_id: str) -> None:
    """Fire-and-forget weather fetch: called from GET /sessions/{id}.

    Uses its own DB session so the request handler isn't blocked.
    """
    from backend.api.db.database import async_session_factory
    from backend.api.db.models import Session as SessionModel
    from backend.api.services.weather_backfill import (
        record_weather_attempt,
        weather_to_dict,
    )

    record_weather_attempt(session_id)
    try:
        await _auto_fetch_weather(sd)
        if sd.weather is not None:
            async with async_session_factory() as db:
                from sqlalchemy import select

                row = (
                    await db.execute(
                        select(SessionModel).where(SessionModel.session_id == session_id)
                    )
                ).scalar_one_or_none()
                if row is not None:
                    snap = dict(row.snapshot_json or {})
                    snap["weather"] = weather_to_dict(sd.weather)
                    row.snapshot_json = snap
                    await db.commit()
    except Exception:
        logger.warning("Lazy weather retry failed for %s", session_id, exc_info=True)


def _weather_fields(
    sd: session_store.SessionData,
) -> tuple[float | None, str | None, float | None, float | None, float | None]:
    """Extract weather fields from a session.

    Returns (temp_c, condition, humidity_pct, wind_kmh, precipitation_mm).
    """
    w = sd.weather
    if w is None:
        return None, None, None, None, None
    condition = (
        w.track_condition.value if hasattr(w.track_condition, "value") else str(w.track_condition)
    )
    return w.ambient_temp_c, condition, w.humidity_pct, w.wind_speed_kmh, w.precipitation_mm


def _equipment_fields(session_id: str) -> tuple[str | None, str | None, str | None]:
    """Look up equipment for a session. Returns (tire_model, compound_category, profile_name)."""
    se = equipment_store.get_session_equipment(session_id)
    if se is None:
        return None, None, None
    profile = equipment_store.get_profile(se.profile_id)
    if profile is None:
        return None, None, None
    return profile.tires.model, profile.tires.compound_category.value, profile.name


def _normalize_score(raw: float) -> float:
    """Normalize a score that may be 0-1 or 0-100 to the 0-100 range."""
    return raw * 100 if raw <= 1 else raw


def _is_valid_pace_reference(best_lap_time_s: float, optimal_time_s: float | None) -> bool:
    """True when the reference pace is finite, positive, and not slower than the lap."""
    if optimal_time_s is None or best_lap_time_s <= 0:
        return False
    if not math.isfinite(optimal_time_s) or optimal_time_s <= 0:
        return False
    # Tolerance of 0.5s: speed-distance integration can drift ~100-200ms
    # from directly-measured lap time due to resampling artifacts.
    return optimal_time_s <= best_lap_time_s + 0.5


async def _compute_ideal_lap_time(sd: session_store.SessionData) -> float | None:
    """Integrate ideal-lap speed/distance arrays for the most accurate optimal time.

    Returns None if the session has fewer than 2 clean laps (required for
    ideal lap reconstruction) or if computation fails.
    """
    from backend.api.services.pipeline import get_ideal_lap_data

    if len(sd.coaching_laps) < 2:
        return None
    try:
        data = await get_ideal_lap_data(sd)
        distance_m: list[float] = data["distance_m"]  # type: ignore[assignment]
        speed_mph: list[float] = data["speed_mph"]  # type: ignore[assignment]
        if len(distance_m) < 2:
            return None
        total = 0.0
        for i in range(1, len(distance_m)):
            ds = distance_m[i] - distance_m[i - 1]
            avg_mps = ((speed_mph[i] + speed_mph[i - 1]) / 2) / MPS_TO_MPH
            if avg_mps > 0:
                total += ds / avg_mps
        return total if total > 0 else None
    except (ValueError, KeyError, IndexError):
        logger.debug("Ideal lap integration failed for %s", sd.session_id)
        return None


@dataclass
class ScoreResult:
    """Session score with per-component breakdown."""

    total: float | None = None
    consistency: float | None = None
    pace: float | None = None
    technique: float | None = None
    optimal_lap_time_s: float | None = None


async def _compute_session_score(sd: session_store.SessionData) -> ScoreResult:
    """Compute composite session score matching the dashboard formula.

    Weighted composite: consistency 40% + pace 30% + corner grades 30%.
    Falls back gracefully when some components are unavailable.
    """
    components: list[tuple[float, float]] = []  # (value, weight)
    result = ScoreResult()

    # Consistency (40%)
    if sd.consistency and sd.consistency.lap_consistency:
        result.consistency = _normalize_score(sd.consistency.lap_consistency.consistency_score)
        components.append((result.consistency, 0.4))

    # Pace: best lap vs ideal lap (30%)
    snap = sd.snapshot
    if snap.best_lap_time_s > 0:
        optimal_time = await _compute_ideal_lap_time(sd)
        if optimal_time is None:
            optimal_time = snap.optimal_lap_time_s
        if _is_valid_pace_reference(snap.best_lap_time_s, optimal_time):
            result.optimal_lap_time_s = cast(float, optimal_time)
            gap_pct = 1 - (result.optimal_lap_time_s / snap.best_lap_time_s)
            result.pace = min(100.0, max(0.0, 100 - gap_pct * 500))
            components.append((result.pace, 0.3))

    # Corner grades (30%)
    report = await get_any_coaching_report(sd.session_id)
    if report and report.corner_grades:
        grade_map = {"A": 100, "B": 80, "C": 60, "D": 40, "F": 20}
        total = 0
        count = 0
        for cg in report.corner_grades:
            for field in ("braking", "trail_braking", "min_speed", "throttle"):
                letter = getattr(cg, field, "")[:1].upper()
                if letter in grade_map:
                    total += grade_map[letter]
                    count += 1
        if count > 0:
            result.technique = total / count
            components.append((result.technique, 0.3))

    if not components:
        return result

    total_weight = sum(w for _, w in components)
    result.total = sum(v * (w / total_weight) for v, w in components)
    return result


async def _persist_sidebar_fields(
    db: AsyncSession,
    session_id: str,
    score: ScoreResult,
    tire_model: str | None,
    compound_category: str | None,
    profile_name: str | None,
) -> None:
    """Write sidebar-visible fields to snapshot_json so they survive restarts."""
    from backend.api.db.models import Session as SessionModel

    result = await db.execute(select(SessionModel).where(SessionModel.session_id == session_id))
    row = result.scalar_one_or_none()
    if row is None:
        return
    snap = dict(row.snapshot_json or {})
    new_scores = {
        "total": score.total,
        "consistency": score.consistency,
        "pace": score.pace,
        "technique": score.technique,
        "optimal_lap_time_s": score.optimal_lap_time_s,
    }
    new_eq = {
        "tire_model": tire_model,
        "compound_category": compound_category,
        "profile_name": profile_name,
    }
    # Only write if changed — flush (not commit) so list_sessions' get_db auto-commits
    if snap.get("scores") != new_scores or snap.get("equipment") != new_eq:
        snap["scores"] = new_scores
        snap["equipment"] = new_eq
        row.snapshot_json = snap
        await db.flush()


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("10/hour")
async def upload_sessions(
    request: Request,
    files: list[UploadFile],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[AuthenticatedUser | None, Depends(get_optional_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadResponse:
    """Upload one or more RaceChrono CSV files and create sessions.

    Supports both authenticated and anonymous uploads. Both are persisted
    to PostgreSQL (Session + SessionFile rows) so they survive redeployments.
    Anonymous sessions use user_id=NULL and are rate-limited per IP.
    """
    is_anonymous = current_user is None

    # Anonymous rate limiting by IP
    if is_anonymous:
        client_ip = request.client.host if request.client else "unknown"
        allowed, reason = check_and_record_anon_upload(client_ip)
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)
    else:
        assert current_user is not None  # narrowing for mypy
        client_ip = None
        await ensure_user_exists(db, current_user)
        await db.commit()  # Commit user row before heavy file processing

    # Look up user's skill_level for coaching generation
    from backend.api.schemas.coaching import SkillLevel

    user_skill_level: SkillLevel = "intermediate"
    if current_user is not None:
        from sqlalchemy import select as sa_select

        from backend.api.db.models import User as UserModel

        user_row = (
            await db.execute(sa_select(UserModel).where(UserModel.id == current_user.user_id))
        ).scalar_one_or_none()
        _raw_level = user_row.skill_level if user_row else "intermediate"
        if _raw_level not in ("novice", "intermediate", "advanced"):
            _raw_level = "intermediate"
        user_skill_level = cast(SkillLevel, _raw_level)

    session_ids: list[str] = []
    errors: list[str] = []
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    lazy_generation_enabled = bool(getattr(settings, "llm_lazy_generation_enabled", False))

    for f in files:
        if not f.filename:
            errors.append("File with no name skipped")
            continue
        try:
            # Check size before reading entire file into memory
            if f.size is not None and f.size > max_bytes:
                errors.append(f"{f.filename}: exceeds {settings.max_upload_size_mb}MB size limit")
                continue
            file_bytes = await f.read()
            # Double-check after read (f.size may be None for chunked uploads)
            if len(file_bytes) > max_bytes:
                errors.append(f"{f.filename}: exceeds {settings.max_upload_size_mb}MB size limit")
                continue

            # Skip duplicate: compute session_id cheaply from CSV header
            from backend.api.services.pipeline import compute_session_id_from_csv

            try:
                existing_sid = compute_session_id_from_csv(file_bytes, f.filename)
            except (ValueError, KeyError, IndexError):
                existing_sid = None
            if existing_sid and session_store.get_session(existing_sid) is not None:
                logger.info("Skipping duplicate upload: %s already in memory", existing_sid)
                session_ids.append(existing_sid)
                # Grant anonymous access to the existing session — possession of
                # the raw CSV bytes is sufficient proof of access intent.
                if is_anonymous:
                    existing_sd = session_store.get_session(existing_sid)
                    if existing_sd is not None:
                        existing_sd.is_anonymous = True
                continue

            result = await process_upload(file_bytes, f.filename)
            sid = str(result["session_id"])
            session_ids.append(sid)

            sd = session_store.get_session(sid)
            if sd is not None:
                if is_anonymous:
                    # Tag as anonymous with client IP for rate limiting lookups
                    sd.is_anonymous = True
                    sd.client_ip = client_ip
                    sd.csv_bytes = file_bytes  # kept for claim path compat
                elif current_user is not None:
                    # Tag session with user for ownership enforcement
                    sd.user_id = current_user.user_id

            # Auto-fetch weather (immutable per session, stored in DB)
            if sd is not None and sd.weather is None:
                try:
                    await _auto_fetch_weather(sd)
                except (ValueError, TypeError, OSError):
                    logger.warning("Auto weather fetch failed for %s", sid, exc_info=True)

            # Persist session metadata + CSV to DB (both authenticated & anonymous)
            if sd is not None:
                owner_id = current_user.user_id if current_user is not None else None
                await store_session_db(db, owner_id, sd)
                await db.commit()

                # Persist raw CSV bytes so sessions survive redeployments.
                # Separate try/except: metadata is already committed above.
                try:
                    await db.merge(
                        SessionFileModel(
                            session_id=sid,
                            filename=f.filename or "",
                            csv_bytes=file_bytes,
                        )
                    )
                    await db.commit()
                    # Free in-memory CSV bytes — DB has the authoritative copy
                    sd.csv_bytes = None
                except SQLAlchemyError:
                    logger.warning("Failed to persist CSV bytes for %s", sid, exc_info=True)
                    await db.rollback()

            # Auto-assign default equipment profile (authenticated users only)
            if sd is not None and current_user is not None:
                try:
                    existing_eq = equipment_store.get_session_equipment(sid)
                    if existing_eq is None:
                        default_profile = equipment_store.get_default_profile(
                            current_user.user_id,
                        )
                        if default_profile is not None:
                            from cataclysm.equipment import SessionEquipment

                            se = SessionEquipment(
                                session_id=sid,
                                profile_id=default_profile.id,
                            )
                            equipment_store.store_session_equipment(se)
                            await equipment_store.db_persist_session_equipment(se)
                            logger.info(
                                "Auto-assigned default equipment %s to session %s",
                                default_profile.id,
                                sid,
                            )
                except Exception:
                    logger.warning(
                        "Auto-assign equipment failed for %s",
                        sid,
                        exc_info=True,
                    )

            # Auto-generate coaching report unless lazy-generation mode is enabled.
            if sd is not None and not lazy_generation_enabled:
                try:
                    await trigger_auto_coaching(sid, sd, skill_level=user_skill_level)
                except (ValueError, TypeError, KeyError):
                    logger.warning("Auto-coaching failed for %s", sid, exc_info=True)

                # Pre-warm LIDAR elevation cache so Speed Gap panel loads fast
                try:
                    trigger_lidar_prefetch(sd)
                except Exception:
                    logger.warning("LIDAR prefetch failed for %s", sid, exc_info=True)

        except (ValueError, KeyError, IndexError, OSError) as exc:
            logger.warning("Failed to process %s: %s", f.filename, exc, exc_info=True)
            errors.append(f"{f.filename}: {exc}")

    # Check achievements after all files are processed (authenticated only)
    all_newly_unlocked: list[str] = []
    if session_ids and current_user is not None:
        try:
            from backend.api.services.achievement_engine import check_achievements

            for sid in session_ids:
                unlocked = await check_achievements(db, current_user.user_id, session_id=sid)
                all_newly_unlocked.extend(unlocked)
            await db.commit()
        except Exception:
            logger.warning("Achievement check failed", exc_info=True)
            await db.rollback()

    msg = f"Processed {len(session_ids)} file(s)"
    if errors:
        msg += f"; {len(errors)} error(s): {'; '.join(errors)}"

    return UploadResponse(session_ids=session_ids, message=msg, newly_unlocked=all_newly_unlocked)


@router.post("/claim")
async def claim_anonymous_session(
    body: ClaimSessionRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Claim an anonymous session for the authenticated user.

    Migrates the session from anonymous in-memory storage to the user's
    account, persisting session metadata to PostgreSQL. The coaching
    report (already generated and cached) is preserved.
    """
    sd = session_store.get_session(body.session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if not sd.is_anonymous:
        raise HTTPException(status_code=400, detail="Session already claimed")

    # Ensure user row exists for FK references
    await ensure_user_exists(db, current_user)

    # Claim in-memory session
    session_store.claim_session(body.session_id, current_user.user_id)

    # Persist session metadata to PostgreSQL
    await store_session_db(db, current_user.user_id, sd)
    await db.commit()

    # SessionFile already persisted at upload time (both anon and auth).
    # Free in-memory CSV bytes now that session is claimed and DB-backed.
    sd.csv_bytes = None

    # Migrate any anon-owned equipment profile to the new user
    se = equipment_store.get_session_equipment(body.session_id)
    if se is not None:
        profile_owner = equipment_store.get_profile_owner(se.profile_id)
        if profile_owner == "anon":
            equipment_store.set_profile_owner(se.profile_id, current_user.user_id)
            profile = equipment_store.get_profile(se.profile_id)
            if profile is not None:
                try:
                    await equipment_store.db_persist_profile(profile, user_id=current_user.user_id)
                except Exception:
                    logger.warning(
                        "Failed to persist anon equipment profile on claim", exc_info=True
                    )
            try:
                await equipment_store.db_persist_session_equipment(se)
            except Exception:
                logger.warning("Failed to persist anon session equipment on claim", exc_info=True)

    # Check achievements for the newly claimed session
    try:
        from backend.api.services.achievement_engine import check_achievements

        await check_achievements(db, current_user.user_id, session_id=body.session_id)
        await db.commit()
    except Exception:
        logger.warning("Achievement check failed on claim", exc_info=True)
        await db.rollback()

    return {"message": f"Session {body.session_id} claimed successfully"}


@router.get("", response_model=SessionList)
async def list_sessions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionList:
    """List user's sessions ordered by date descending.

    Uses DB metadata for the list; enriches from in-memory store if available.
    Calls ensure_user_exists so that OAuth sub changes trigger FK migration
    (sessions move from old user_id to current user_id).
    """
    await ensure_user_exists(db, current_user)
    db_rows = await list_sessions_for_user(db, current_user.user_id)
    logger.info(
        "list_sessions: user_id=%s email=%s → %d session(s)",
        current_user.user_id,
        current_user.email,
        len(db_rows),
    )
    items: list[SessionSummary] = []
    for row in db_rows:
        # Try in-memory store for richer data (e.g. after upload)
        sd = session_store.get_session(row.session_id)
        if sd is not None:
            # Sync in-memory user_id after ensure_user_exists migration.
            # DB is already migrated; update memory so get_session_for_user works.
            if sd.user_id != current_user.user_id:
                sd.user_id = current_user.user_id
            # Backfill weather from DB snapshot for sessions uploaded before auto-fetch
            if sd.weather is None and row.snapshot_json:
                restored = restore_weather_from_snapshot(row.snapshot_json)
                if restored is not None:
                    sd.weather = restored
            tire_model, compound_category, profile_name = _equipment_fields(sd.session_id)
            w_temp, w_cond, w_hum, w_wind, w_precip = _weather_fields(sd)
            score = await _compute_session_score(sd)
            items.append(
                SessionSummary(
                    session_id=sd.session_id,
                    track_name=sd.snapshot.metadata.track_name,
                    session_date=sd.snapshot.metadata.session_date,
                    n_laps=sd.snapshot.n_laps,
                    n_clean_laps=sd.snapshot.n_clean_laps,
                    best_lap_time_s=sd.snapshot.best_lap_time_s,
                    top3_avg_time_s=sd.snapshot.top3_avg_time_s,
                    avg_lap_time_s=sd.snapshot.avg_lap_time_s,
                    consistency_score=sd.snapshot.consistency_score,
                    session_score=score.total,
                    score_consistency=score.consistency,
                    score_pace=score.pace,
                    score_technique=score.technique,
                    optimal_lap_time_s=score.optimal_lap_time_s,
                    gps_quality_score=sd.gps_quality.overall_score if sd.gps_quality else None,
                    gps_quality_grade=sd.gps_quality.grade if sd.gps_quality else None,
                    tire_model=tire_model,
                    compound_category=compound_category,
                    equipment_profile_name=profile_name,
                    weather_temp_c=w_temp,
                    weather_condition=w_cond,
                    weather_humidity_pct=w_hum,
                    weather_wind_kmh=w_wind,
                    weather_precipitation_mm=w_precip,
                )
            )
            try:
                await _persist_sidebar_fields(
                    db,
                    sd.session_id,
                    score,
                    tire_model,
                    compound_category,
                    profile_name,
                )
            except Exception:
                logger.warning(
                    "Failed to persist sidebar fields for %s",
                    sd.session_id,
                    exc_info=True,
                )
        else:
            # Fallback to DB metadata (telemetry not in memory — needs re-upload)
            snap = row.snapshot_json or {}
            # Prefer the original display string saved at upload time;
            # fall back to strftime (no raw isoformat with +00:00 timezone).
            date_str = snap.get("session_date_display") or (
                row.session_date.strftime("%d/%m/%Y %H:%M") if row.session_date else ""
            )
            w_data = snap.get("weather")
            gps_data = snap.get("gps_quality")
            score_data = snap.get("scores")
            eq_data = snap.get("equipment")
            items.append(
                SessionSummary(
                    session_id=row.session_id,
                    track_name=row.track_name,
                    session_date=date_str,
                    n_laps=row.n_laps,
                    n_clean_laps=row.n_clean_laps,
                    best_lap_time_s=row.best_lap_time_s,
                    top3_avg_time_s=row.top3_avg_time_s,
                    avg_lap_time_s=row.avg_lap_time_s,
                    consistency_score=row.consistency_score,
                    session_score=score_data.get("total") if score_data else None,
                    score_consistency=score_data.get("consistency") if score_data else None,
                    score_pace=score_data.get("pace") if score_data else None,
                    score_technique=score_data.get("technique") if score_data else None,
                    optimal_lap_time_s=score_data.get("optimal_lap_time_s") if score_data else None,
                    gps_quality_score=gps_data.get("overall_score") if gps_data else None,
                    gps_quality_grade=gps_data.get("grade") if gps_data else None,
                    tire_model=eq_data.get("tire_model") if eq_data else None,
                    compound_category=eq_data.get("compound_category") if eq_data else None,
                    equipment_profile_name=eq_data.get("profile_name") if eq_data else None,
                    weather_temp_c=w_data.get("ambient_temp_c") if w_data else None,
                    weather_condition=w_data.get("track_condition") if w_data else None,
                    weather_humidity_pct=w_data.get("humidity_pct") if w_data else None,
                    weather_wind_kmh=w_data.get("wind_speed_kmh") if w_data else None,
                    weather_precipitation_mm=w_data.get("precipitation_mm") if w_data else None,
                )
            )
    return SessionList(items=items, total=len(items))


@router.get("/{session_id}", response_model=SessionSummary)
async def get_session(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionSummary:
    """Get metadata and summary for a single session."""
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Lazy weather retry: fire-and-forget background task to avoid stalling the response.
    # React Query polls every 30s — weather will appear on the next fetch.
    if sd.weather is None:
        from backend.api.services.weather_backfill import should_retry_weather

        if should_retry_weather(session_id):
            asyncio.create_task(
                _lazy_weather_fetch(sd, session_id),
                name=f"lazy-weather-{session_id}",
            )

    tire_model, compound_category, profile_name = _equipment_fields(sd.session_id)
    w_temp, w_cond, w_hum, w_wind, w_precip = _weather_fields(sd)
    score = await _compute_session_score(sd)
    return SessionSummary(
        session_id=sd.session_id,
        track_name=sd.snapshot.metadata.track_name,
        session_date=sd.snapshot.metadata.session_date,
        n_laps=sd.snapshot.n_laps,
        n_clean_laps=sd.snapshot.n_clean_laps,
        best_lap_time_s=sd.snapshot.best_lap_time_s,
        top3_avg_time_s=sd.snapshot.top3_avg_time_s,
        avg_lap_time_s=sd.snapshot.avg_lap_time_s,
        consistency_score=sd.snapshot.consistency_score,
        session_score=score.total,
        score_consistency=score.consistency,
        score_pace=score.pace,
        score_technique=score.technique,
        optimal_lap_time_s=score.optimal_lap_time_s,
        gps_quality_score=sd.gps_quality.overall_score if sd.gps_quality else None,
        gps_quality_grade=sd.gps_quality.grade if sd.gps_quality else None,
        tire_model=tire_model,
        compound_category=compound_category,
        equipment_profile_name=profile_name,
        weather_temp_c=w_temp,
        weather_condition=w_cond,
        weather_humidity_pct=w_hum,
        weather_wind_kmh=w_wind,
        weather_precipitation_mm=w_precip,
    )


@router.get("/{session_id}/compare/{other_id}", response_model=ComparisonResult)
async def compare_sessions(
    session_id: str,
    other_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ComparisonResult:
    """Compare best laps of two sessions (multi-driver comparison)."""
    sd_a = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd_a is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    sd_b = await get_session_for_user_with_db_sync(db, other_id, current_user.user_id)
    if sd_b is None:
        raise HTTPException(status_code=404, detail=f"Session {other_id} not found")

    result = await run_comparison(sd_a, sd_b)
    return ComparisonResult(**result)


@router.delete("/all/clear")
async def delete_all_sessions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Delete all sessions for the current user.

    Uses bulk SQL deletes instead of per-session loops to avoid timeouts.
    """
    from sqlalchemy import delete

    from backend.api.db.models import CoachingReport as CoachingReportModel
    from backend.api.db.models import Session as SessionModel
    from backend.api.services.coaching_store import _contexts, _reports

    db_rows = await list_sessions_for_user(db, current_user.user_id)
    sids = [row.session_id for row in db_rows]
    if not sids:
        return {"message": "Deleted 0 session(s)"}

    # Bulk-delete from all related tables in one transaction
    await db.execute(delete(CoachingReportModel).where(CoachingReportModel.session_id.in_(sids)))
    await db.execute(delete(SessionFileModel).where(SessionFileModel.session_id.in_(sids)))
    await db.execute(
        delete(SessionModel).where(
            SessionModel.session_id.in_(sids),
            SessionModel.user_id == current_user.user_id,
        )
    )
    await db.commit()

    # Clear in-memory stores
    for sid in sids:
        session_store.delete_session(sid)
        equipment_store.delete_session_equipment(sid)
        invalidate_physics_cache(sid)
        _reports.pop(sid, None)
        _contexts.pop(sid, None)

    return {"message": f"Deleted {len(sids)} session(s)"}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Delete a session owned by the current user."""
    db_deleted = await delete_session_db(db, session_id, current_user.user_id)
    if not db_deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    # Also remove from in-memory store and clear coaching/equipment/physics cache
    session_store.delete_session(session_id)
    equipment_store.delete_session_equipment(session_id)
    invalidate_physics_cache(session_id)
    await clear_coaching_data(session_id)
    return {"message": f"Session {session_id} deleted"}


@router.get("/{session_id}/weather")
async def get_session_weather(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Get weather conditions for a session.

    Returns cached weather if available. If not yet fetched, attempts a
    live lookup using the session's GPS centroid and date, then stores
    the result permanently.
    """
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Return cached weather if available
    if sd.weather is not None:
        return {"session_id": session_id, "weather": weather_to_dict(sd.weather)}

    # Try live fetch if not cached
    try:
        await _auto_fetch_weather(sd)
    except Exception:
        logger.warning("On-demand weather fetch failed for %s", session_id, exc_info=True)

    if sd.weather is not None:
        return {"session_id": session_id, "weather": weather_to_dict(sd.weather)}

    return {"session_id": session_id, "weather": None}


@router.post("/backfill-weather")
async def backfill_weather(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Backfill weather for all user sessions missing it.

    Uses the stored GPS centroid and session date from snapshot_json
    to fetch weather from Open-Meteo for sessions that were uploaded
    before weather auto-fetch was implemented.
    """
    from datetime import UTC, datetime

    from cataclysm.weather_client import lookup_weather

    db_rows = await list_sessions_for_user(db, current_user.user_id)
    backfilled = 0
    skipped = 0
    failed = 0

    for row in db_rows:
        snap = row.snapshot_json or {}

        # Skip if weather already exists in snapshot
        if snap.get("weather"):
            skipped += 1
            continue

        # Need GPS centroid to fetch weather
        centroid = snap.get("gps_centroid")
        if not centroid:
            # Try in-memory session for GPS data
            sd = session_store.get_session(row.session_id)
            if sd is not None and sd.weather is None:
                try:
                    await _auto_fetch_weather(sd)
                    if sd.weather is not None:
                        # Persist to DB snapshot_json
                        snap["weather"] = weather_to_dict(sd.weather)
                        row.snapshot_json = snap
                        await db.flush()
                        backfilled += 1
                        continue
                except Exception:
                    logger.warning("Backfill via memory failed for %s", row.session_id)
            skipped += 1
            continue

        lat = centroid.get("lat")
        lon = centroid.get("lon")
        if lat is None or lon is None:
            skipped += 1
            continue

        # Parse session date
        session_dt: datetime | None = None
        if row.session_date:
            dt = row.session_date
            session_dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
        if session_dt is None:
            skipped += 1
            continue

        try:
            weather = await lookup_weather(lat, lon, session_dt)
            if weather is None:
                failed += 1
                continue

            # Update snapshot_json with weather
            snap["weather"] = weather_to_dict(weather)
            row.snapshot_json = snap
            await db.flush()

            # Also update in-memory store if available
            sd = session_store.get_session(row.session_id)
            if sd is not None:
                sd.weather = weather

            backfilled += 1
            logger.info(
                "Backfilled weather for %s: %s, %.1f°C",
                row.session_id,
                weather.track_condition.value
                if hasattr(weather.track_condition, "value")
                else str(weather.track_condition),
                weather.ambient_temp_c or 0,
            )
        except Exception:
            logger.warning("Weather backfill failed for %s", row.session_id, exc_info=True)
            failed += 1

    await db.commit()
    return {
        "backfilled": backfilled,
        "skipped": skipped,
        "failed": failed,
        "total": len(db_rows),
    }


@router.get("/{session_id}/track-guide", response_model=TrackGuideResponse)
async def get_track_guide(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrackGuideResponse:
    """Get structured track guide data for the Track Briefing Card.

    Returns 404 if the session's track is not in the track database.
    """
    from cataclysm.track_db import get_key_corners, get_peculiarities
    from cataclysm.track_db_hybrid import lookup_track_hybrid

    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    track_name = sd.snapshot.metadata.track_name
    layout = lookup_track_hybrid(track_name)
    if layout is None:
        raise HTTPException(status_code=404, detail=f"Track '{track_name}' not in database")

    corners = [
        TrackGuideCorner(
            number=c.number,
            name=c.name,
            fraction=c.fraction,
            direction=c.direction,
            corner_type=c.corner_type,
            elevation_trend=c.elevation_trend,
            camber=c.camber,
            blind=c.blind,
            coaching_notes=c.coaching_notes,
            character=c.character,
        )
        for c in layout.corners
    ]

    key_corners = [
        KeyCorner(
            number=c.number,
            name=c.name,
            straight_after_m=round(gap_m, 0),
            coaching_notes=c.coaching_notes,
            direction=c.direction,
            blind=c.blind,
            camber=c.camber,
        )
        for c, gap_m in get_key_corners(layout)
    ]

    peculiarities = [
        TrackPeculiarity(
            corner_number=c.number,
            corner_name=c.name,
            description=desc,
        )
        for c, desc in get_peculiarities(layout)
    ]

    landmarks = [
        TrackGuideLandmark(
            name=lm.name,
            distance_m=lm.distance_m,
            landmark_type=lm.landmark_type.value,
            description=lm.description,
        )
        for lm in layout.landmarks
    ]

    response = TrackGuideResponse(
        track_name=layout.name,
        length_m=layout.length_m,
        elevation_range_m=layout.elevation_range_m,
        country=layout.country,
        n_corners=len(layout.corners),
        corners=corners,
        key_corners=key_corners,
        peculiarities=peculiarities,
        landmarks=landmarks,
    )
    return response


@router.get("/{session_id}/laps", response_model=list[LapSummary])
async def get_lap_summaries(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LapSummary]:
    """Get lap summaries for a session."""
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return [
        LapSummary(
            lap_number=s.lap_number,
            lap_time_s=s.lap_time_s,
            lap_distance_m=s.lap_distance_m,
            max_speed_mps=s.max_speed_mps,
            is_clean=s.lap_number not in sd.anomalous_laps
            and s.lap_number not in sd.lap_tags.excluded_laps(),
            tags=sorted(sd.lap_tags.get_tags(s.lap_number)),
        )
        for s in sd.processed.lap_summaries
    ]


@router.get("/{session_id}/laps/{lap_number}/data", response_model=LapData)
async def get_lap_data(
    session_id: str,
    lap_number: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LapData:
    """Get resampled telemetry data for a specific lap (columnar JSON)."""
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if lap_number not in sd.processed.resampled_laps:
        raise HTTPException(
            status_code=404, detail=f"Lap {lap_number} not found in session {session_id}"
        )

    df = sd.processed.resampled_laps[lap_number]
    altitude = df["altitude_m"].tolist() if "altitude_m" in df.columns else None

    def _finite_list_or_none(col: str) -> list[float] | None:
        """Return column values as a list only if finite data exists."""
        if col not in df.columns:
            return None
        arr = df[col].to_numpy()
        if not np.any(np.isfinite(arr)):
            return None
        return arr.tolist()

    return LapData(
        lap_number=lap_number,
        distance_m=df["lap_distance_m"].tolist(),
        speed_mph=(df["speed_mps"] * MPS_TO_MPH).tolist(),
        lat=df["lat"].tolist(),
        lon=df["lon"].tolist(),
        heading_deg=df["heading_deg"].tolist(),
        lateral_g=_finite_list_or_none("lateral_g"),
        longitudinal_g=_finite_list_or_none("longitudinal_g"),
        lap_time_s=df["lap_time_s"].tolist(),
        altitude_m=altitude,
    )


@router.get("/{session_id}/laps/{lap_number}/tags")
async def get_lap_tags(
    session_id: str,
    lap_number: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Get tags for a specific lap."""
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if lap_number not in sd.processed.resampled_laps:
        raise HTTPException(
            status_code=404,
            detail=f"Lap {lap_number} not found in session {session_id}",
        )

    return {"lap_number": lap_number, "tags": sorted(sd.lap_tags.get_tags(lap_number))}


@router.put("/{session_id}/laps/{lap_number}/tags")
async def set_lap_tags(
    session_id: str,
    lap_number: int,
    tags: Annotated[list[str], Body()],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Set tags for a specific lap."""
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if lap_number not in sd.processed.resampled_laps:
        raise HTTPException(
            status_code=404,
            detail=f"Lap {lap_number} not found in session {session_id}",
        )

    # 1. Update in-memory tags
    sd.lap_tags.tags[lap_number] = set(tags)

    # 2. Persist to DB
    await save_lap_tags(db, session_id, sd.lap_tags)

    # 3. Recalculate coaching_laps with tag-aware exclusion
    all_laps = sorted(sd.processed.resampled_laps.keys())
    in_out = {all_laps[0], all_laps[-1]} if len(all_laps) >= 2 else set()
    sd.coaching_laps = recalculate_coaching_laps(
        all_laps=all_laps,
        anomalous=sd.anomalous_laps,
        in_out=in_out,
        best_lap=sd.processed.best_lap,
        tags=sd.lap_tags,
    )

    # 4. Invalidate downstream caches so they regenerate with updated coaching_laps
    invalidate_physics_cache(session_id)
    await clear_coaching_data(session_id)

    return {"lap_number": lap_number, "tags": sorted(tags)}


# ---------------------------------------------------------------------------
# Manual track-condition override
# ---------------------------------------------------------------------------


class TrackConditionOverride(BaseModel):
    """Body for manually overriding the track surface condition."""

    condition: Literal["dry", "damp", "wet"] | None


@router.patch("/{session_id}/track-condition")
async def override_track_condition(
    session_id: str,
    body: TrackConditionOverride,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Override or clear the manual track-condition tag.

    - If ``condition`` is a valid value (``dry`` / ``damp`` / ``wet``),
      sets the condition and marks ``track_condition_is_manual = True``.
    - If ``condition`` is ``null``, clears the manual flag and re-derives
      the condition from weather data.
    """
    from cataclysm.equipment import TrackCondition

    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if sd.weather is None:
        raise HTTPException(
            status_code=409,
            detail="No weather data available for this session yet",
        )

    if body.condition is None:
        # Clear manual override — re-derive from model
        old_is_manual = sd.weather.track_condition_is_manual
        sd.weather.track_condition_is_manual = False
        # Re-run weather lookup to get model-derived condition
        try:
            await _auto_fetch_weather(sd)
        except Exception:
            # Restore manual flag — can't re-derive, keep user's tag
            sd.weather.track_condition_is_manual = old_is_manual
            logger.warning(
                "Weather re-fetch failed while clearing override for %s",
                session_id,
                exc_info=True,
            )
    else:
        sd.weather.track_condition = TrackCondition(body.condition)
        sd.weather.track_condition_is_manual = True

    # Persist to snapshot_json so the override survives backend restarts
    from sqlalchemy import select

    from backend.api.db.models import Session as SessionModel
    from backend.api.services.weather_backfill import weather_to_dict

    row = (
        await db.execute(select(SessionModel).where(SessionModel.session_id == session_id))
    ).scalar_one_or_none()
    if row is not None:
        snap = dict(row.snapshot_json or {})
        snap["weather"] = weather_to_dict(sd.weather)
        row.snapshot_json = snap
        await db.commit()

    # Invalidate downstream caches (coaching depends on track condition)
    invalidate_physics_cache(session_id)
    await clear_coaching_data(session_id)

    cond = sd.weather.track_condition
    return {
        "track_condition": cond.value if hasattr(cond, "value") else str(cond),
        "track_condition_is_manual": sd.weather.track_condition_is_manual,
    }

"""Session management endpoints: upload, list, get, delete."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.config import Settings
from backend.api.db.database import get_db
from backend.api.db.models import SessionFile as SessionFileModel
from backend.api.dependencies import AuthenticatedUser, get_current_user, get_settings
from backend.api.routers.coaching import trigger_auto_coaching
from backend.api.schemas.comparison import ComparisonResult
from backend.api.schemas.session import (
    LapData,
    LapSummary,
    SessionList,
    SessionSummary,
    UploadResponse,
)
from backend.api.services import equipment_store, session_store
from backend.api.services.coaching_store import clear_coaching_data, get_coaching_report
from backend.api.services.comparison import compare_sessions as run_comparison
from backend.api.services.db_session_store import (
    delete_session_db,
    ensure_user_exists,
    list_sessions_for_user,
    store_session_db,
)
from backend.api.services.pipeline import process_upload

logger = logging.getLogger(__name__)

router = APIRouter()

MPS_TO_MPH = 2.23694


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


async def _compute_session_score(sd: session_store.SessionData) -> float | None:
    """Compute composite session score matching the dashboard formula.

    Weighted composite: consistency 40% + pace 30% + corner grades 30%.
    Falls back gracefully when some components are unavailable.
    """
    components: list[tuple[float, float]] = []  # (value, weight)

    # Consistency (40%)
    if sd.consistency and sd.consistency.lap_consistency:
        components.append(
            (_normalize_score(sd.consistency.lap_consistency.consistency_score), 0.4)
        )

    # Pace: best lap vs optimal (30%)
    snap = sd.snapshot
    if snap.best_lap_time_s > 0:
        optimal = snap.optimal_lap_time_s
        gap_pct = 1 - (optimal / snap.best_lap_time_s)
        pace_value = min(100.0, max(0.0, 100 - gap_pct * 500))
        components.append((pace_value, 0.3))

    # Corner grades (30%)
    report = await get_coaching_report(sd.session_id)
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
            components.append((total / count, 0.3))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    return sum(v * (w / total_weight) for v, w in components)


@router.post("/upload", response_model=UploadResponse)
async def upload_sessions(
    files: list[UploadFile],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadResponse:
    """Upload one or more RaceChrono CSV files and create sessions."""
    await ensure_user_exists(db, current_user)

    session_ids: list[str] = []
    errors: list[str] = []

    for f in files:
        if not f.filename:
            errors.append("File with no name skipped")
            continue
        try:
            file_bytes = await f.read()
            result = await process_upload(file_bytes, f.filename)
            sid = str(result["session_id"])
            session_ids.append(sid)

            # Auto-fetch weather (immutable per session, stored in DB)
            sd = session_store.get_session(sid)
            if sd is not None and sd.weather is None:
                try:
                    await _auto_fetch_weather(sd)
                except Exception:
                    logger.warning("Auto weather fetch failed for %s", sid, exc_info=True)

            # Persist session metadata to DB for user scoping.
            # Commit immediately so the session appears in the list even if
            # subsequent operations (CSV bytes, coaching) fail.
            if sd is not None:
                await store_session_db(db, current_user.user_id, sd)
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
                except Exception:
                    logger.warning("Failed to persist CSV bytes for %s", sid, exc_info=True)
                    await db.rollback()

                # Auto-generate coaching report in the background
                try:
                    await trigger_auto_coaching(sid, sd)
                except Exception:
                    logger.warning("Auto-coaching failed for %s", sid, exc_info=True)
        except Exception as exc:
            logger.warning("Failed to process %s: %s", f.filename, exc, exc_info=True)
            errors.append(f"{f.filename}: {exc}")

    msg = f"Processed {len(session_ids)} file(s)"
    if errors:
        msg += f"; {len(errors)} error(s): {'; '.join(errors)}"

    return UploadResponse(session_ids=session_ids, message=msg)


@router.get("", response_model=SessionList)
async def list_sessions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionList:
    """List user's sessions ordered by date descending.

    Uses DB metadata for the list; enriches from in-memory store if available.
    """
    db_rows = await list_sessions_for_user(db, current_user.user_id)
    items: list[SessionSummary] = []
    for row in db_rows:
        # Try in-memory store for richer data (e.g. after upload)
        sd = session_store.get_session(row.session_id)
        if sd is not None:
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
                    session_score=score,
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
        else:
            # Fallback to DB metadata (telemetry not in memory — needs re-upload)
            date_str = row.session_date.isoformat() if row.session_date else ""
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
                )
            )
    return SessionList(items=items, total=len(items))


@router.get("/{session_id}", response_model=SessionSummary)
async def get_session(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> SessionSummary:
    """Get metadata and summary for a single session."""
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

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
        session_score=score,
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
) -> ComparisonResult:
    """Compare best laps of two sessions (multi-driver comparison)."""
    sd_a = session_store.get_session(session_id)
    if sd_a is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    sd_b = session_store.get_session(other_id)
    if sd_b is None:
        raise HTTPException(status_code=404, detail=f"Session {other_id} not found")

    result = await run_comparison(sd_a, sd_b)
    return ComparisonResult(**result)


@router.delete("/all/clear")
async def delete_all_sessions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Delete all sessions for the current user."""
    db_rows = await list_sessions_for_user(db, current_user.user_id)
    sids = [row.session_id for row in db_rows]
    for sid in sids:
        await delete_session_db(db, sid, current_user.user_id)
        session_store.delete_session(sid)
        await clear_coaching_data(sid)
    await db.commit()
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
    # Also remove from in-memory store and clear coaching cache
    session_store.delete_session(session_id)
    await clear_coaching_data(session_id)
    return {"message": f"Session {session_id} deleted"}


@router.get("/{session_id}/weather")
async def get_session_weather(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, object]:
    """Get weather conditions for a session.

    Returns cached weather if available. If not yet fetched, attempts a
    live lookup using the session's GPS centroid and date, then stores
    the result permanently.
    """
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Return cached weather if available
    if sd.weather is not None:
        w = sd.weather
        return {
            "session_id": session_id,
            "weather": {
                "track_condition": w.track_condition.value
                if hasattr(w.track_condition, "value")
                else str(w.track_condition),
                "ambient_temp_c": w.ambient_temp_c,
                "humidity_pct": w.humidity_pct,
                "wind_speed_kmh": w.wind_speed_kmh,
                "wind_direction_deg": w.wind_direction_deg,
                "precipitation_mm": w.precipitation_mm,
                "weather_source": w.weather_source,
            },
        }

    # Try live fetch if not cached
    try:
        await _auto_fetch_weather(sd)
    except Exception:
        logger.warning("On-demand weather fetch failed for %s", session_id, exc_info=True)

    if sd.weather is not None:
        w = sd.weather
        return {
            "session_id": session_id,
            "weather": {
                "track_condition": w.track_condition.value
                if hasattr(w.track_condition, "value")
                else str(w.track_condition),
                "ambient_temp_c": w.ambient_temp_c,
                "humidity_pct": w.humidity_pct,
                "wind_speed_kmh": w.wind_speed_kmh,
                "wind_direction_deg": w.wind_direction_deg,
                "precipitation_mm": w.precipitation_mm,
                "weather_source": w.weather_source,
            },
        }

    return {"session_id": session_id, "weather": None}


@router.get("/{session_id}/laps", response_model=list[LapSummary])
async def get_lap_summaries(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[LapSummary]:
    """Get lap summaries for a session."""
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return [
        LapSummary(
            lap_number=s.lap_number,
            lap_time_s=s.lap_time_s,
            lap_distance_m=s.lap_distance_m,
            max_speed_mps=s.max_speed_mps,
            is_clean=s.lap_number not in sd.anomalous_laps,
            tags=sorted(sd.lap_tags.get_tags(s.lap_number)),
        )
        for s in sd.processed.lap_summaries
    ]


@router.get("/{session_id}/laps/{lap_number}/data", response_model=LapData)
async def get_lap_data(
    session_id: str,
    lap_number: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> LapData:
    """Get resampled telemetry data for a specific lap (columnar JSON)."""
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if lap_number not in sd.processed.resampled_laps:
        raise HTTPException(
            status_code=404, detail=f"Lap {lap_number} not found in session {session_id}"
        )

    df = sd.processed.resampled_laps[lap_number]
    altitude = df["altitude_m"].tolist() if "altitude_m" in df.columns else None
    return LapData(
        lap_number=lap_number,
        distance_m=df["lap_distance_m"].tolist(),
        speed_mph=(df["speed_mps"] * MPS_TO_MPH).tolist(),
        lat=df["lat"].tolist(),
        lon=df["lon"].tolist(),
        heading_deg=df["heading_deg"].tolist(),
        lateral_g=df["lateral_g"].tolist(),
        longitudinal_g=df["longitudinal_g"].tolist(),
        lap_time_s=df["lap_time_s"].tolist(),
        altitude_m=altitude,
    )


@router.get("/{session_id}/laps/{lap_number}/tags")
async def get_lap_tags(
    session_id: str,
    lap_number: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, object]:
    """Get tags for a specific lap."""
    sd = session_store.get_session(session_id)
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
    tags: list[str],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, object]:
    """Set tags for a specific lap."""
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if lap_number not in sd.processed.resampled_laps:
        raise HTTPException(
            status_code=404,
            detail=f"Lap {lap_number} not found in session {session_id}",
        )

    # Clear existing tags and set new ones
    sd.lap_tags.tags[lap_number] = set(tags)
    return {"lap_number": lap_number, "tags": sorted(tags)}

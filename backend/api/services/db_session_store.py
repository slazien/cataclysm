"""DB-backed session metadata store for user-scoped persistence.

The in-memory session store holds full telemetry data (too large for DB).
This module persists lightweight metadata to PostgreSQL for:
- User-scoped session lists (sidebar)
- Session ownership verification
- Persistence across backend restarts (users re-upload for telemetry)
"""

from __future__ import annotations

from datetime import datetime

from cataclysm.equipment import SessionConditions, TrackCondition
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import Session as SessionModel
from backend.api.db.models import User as UserModel
from backend.api.dependencies import AuthenticatedUser
from backend.api.services.session_store import SessionData

# RaceChrono date formats — mirrors cataclysm.trends._DATE_FORMATS
_DATE_FORMATS = [
    "%d/%m/%Y %H:%M",  # RaceChrono EU format
    "%d/%m/%Y,%H:%M",  # RaceChrono comma-separated
    "%m/%d/%Y %H:%M",  # US format
    "%Y-%m-%d %H:%M:%S",  # ISO
    "%Y-%m-%d %H:%M",  # ISO short
    "%Y-%m-%dT%H:%M:%S",  # ISO 8601
    "%Y-%m-%dT%H:%M",  # ISO 8601 short
    "%d/%m/%Y",  # Date only EU
    "%Y-%m-%d",  # Date only ISO
]


def _parse_session_date(date_str: str) -> datetime:
    """Parse a session date string into a datetime, trying multiple formats."""
    cleaned = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)  # noqa: DTZ007
        except ValueError:
            continue
    return datetime.min  # noqa: DTZ001


async def ensure_user_exists(db: AsyncSession, user: AuthenticatedUser) -> None:
    """Create the User row if it doesn't already exist (FK target for sessions)."""
    result = await db.execute(select(UserModel).where(UserModel.id == user.user_id))
    if result.scalar_one_or_none() is None:
        db.add(
            UserModel(
                id=user.user_id,
                email=user.email,
                name=user.name,
                avatar_url=user.picture,
            )
        )
        await db.flush()


async def store_session_db(
    db: AsyncSession,
    user_id: str,
    session_data: SessionData,
) -> None:
    """Persist session metadata to the database after upload.

    Uses ``merge`` so re-uploading the same session updates rather than errors.
    """
    snap = session_data.snapshot
    # Build snapshot JSON for immutable per-session data.
    # These are computed/fetched once and never change for a given session.
    snapshot_json: dict[str, object] = {}

    # Weather conditions (fetched from Open-Meteo on upload)
    if session_data.weather is not None:
        w = session_data.weather
        snapshot_json["weather"] = {
            "track_condition": w.track_condition.value
            if hasattr(w.track_condition, "value")
            else str(w.track_condition),
            "ambient_temp_c": w.ambient_temp_c,
            "track_temp_c": w.track_temp_c,
            "humidity_pct": w.humidity_pct,
            "wind_speed_kmh": w.wind_speed_kmh,
            "wind_direction_deg": w.wind_direction_deg,
            "precipitation_mm": w.precipitation_mm,
            "weather_source": w.weather_source,
        }

    # GPS centroid (derived from session telemetry)
    try:
        df = session_data.parsed.data
        if not df.empty and "lat" in df.columns and "lon" in df.columns:
            snapshot_json["gps_centroid"] = {
                "lat": round(float(df["lat"].mean()), 6),
                "lon": round(float(df["lon"].mean()), 6),
            }
    except Exception:
        pass  # Non-critical, skip if data is unavailable

    # GPS quality assessment (computed from telemetry)
    if session_data.gps_quality is not None:
        gps = session_data.gps_quality
        snapshot_json["gps_quality"] = {
            "overall_score": gps.overall_score,
            "grade": gps.grade,
            "is_usable": gps.is_usable,
        }

    session_row = SessionModel(
        session_id=session_data.session_id,
        user_id=user_id,
        track_name=snap.metadata.track_name,
        session_date=_parse_session_date(snap.metadata.session_date)
        if isinstance(snap.metadata.session_date, str)
        else snap.metadata.session_date,
        file_key=session_data.session_id,
        n_laps=snap.n_laps,
        n_clean_laps=snap.n_clean_laps,
        best_lap_time_s=snap.best_lap_time_s,
        top3_avg_time_s=snap.top3_avg_time_s,
        avg_lap_time_s=snap.avg_lap_time_s,
        consistency_score=snap.consistency_score,
        snapshot_json=snapshot_json if snapshot_json else None,
    )
    await db.merge(session_row)
    await db.flush()


def restore_weather_from_snapshot(snapshot_json: dict | None) -> SessionConditions | None:
    """Restore weather conditions from a DB snapshot_json blob.

    Returns None if no weather data is stored.
    """
    if not snapshot_json or "weather" not in snapshot_json:
        return None
    w = snapshot_json["weather"]
    return SessionConditions(
        track_condition=TrackCondition(w.get("track_condition", "dry")),
        ambient_temp_c=w.get("ambient_temp_c"),
        track_temp_c=w.get("track_temp_c"),
        humidity_pct=w.get("humidity_pct"),
        wind_speed_kmh=w.get("wind_speed_kmh"),
        wind_direction_deg=w.get("wind_direction_deg"),
        precipitation_mm=w.get("precipitation_mm"),
        weather_source=w.get("weather_source"),
    )


async def list_sessions_for_user(
    db: AsyncSession,
    user_id: str,
) -> list[SessionModel]:
    """Return all session metadata rows for a user, newest first."""
    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.user_id == user_id)
        .order_by(SessionModel.session_date.desc())
    )
    return list(result.scalars().all())


async def verify_session_owner(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> bool:
    """Check if a session belongs to the given user."""
    result = await db.execute(
        select(SessionModel.session_id).where(
            SessionModel.session_id == session_id,
            SessionModel.user_id == user_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def delete_session_db(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> bool:
    """Delete a session metadata row if owned by user. Returns True if deleted."""
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.session_id == session_id,
            SessionModel.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    await db.delete(row)
    await db.flush()
    return True

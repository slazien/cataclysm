"""DB-backed session metadata store for user-scoped persistence.

The in-memory session store holds full telemetry data (too large for DB).
This module persists lightweight metadata to PostgreSQL for:
- User-scoped session lists (sidebar)
- Session ownership verification
- Persistence across backend restarts (users re-upload for telemetry)
"""

from __future__ import annotations

import logging

from cataclysm.equipment import SessionConditions, TrackCondition
from cataclysm.trends import _parse_session_date  # noqa: F401 — re-exported for callers
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import Session as SessionModel
from backend.api.db.models import User as UserModel
from backend.api.dependencies import AuthenticatedUser
from backend.api.services.session_store import SessionData

logger = logging.getLogger(__name__)


async def ensure_user_exists(db: AsyncSession, user: AuthenticatedUser) -> None:
    """Create or update the User row (FK target for sessions).

    Handles the case where a user already exists with the same email but a
    different ID (e.g. dev-user row from DEV_AUTH_BYPASS, or OAuth provider
    returning a different ``sub`` claim).

    Also consolidates duplicate email entries: when multiple auth sessions
    (e.g. mobile vs desktop, or stale NextAuth sessions) resolve to different
    user IDs for the same email, all data is merged into the current user_id
    to prevent ownership ping-pong.
    """
    _fk_refs = [
        ("user_id", "sessions"),
        ("user_id", "equipment_profiles"),
        ("user_id", "user_achievements"),
        ("user_id", "corner_records"),
        ("user_id", "corner_kings"),
        ("user_id", "shared_sessions"),
        ("instructor_id", "instructor_students"),
        ("student_id", "instructor_students"),
        ("student_id", "student_flags"),
        ("user_id", "org_memberships"),
        ("user_id", "notes"),
        ("user_id", "stickies"),
    ]

    # Check by primary key first
    result = await db.execute(select(UserModel).where(UserModel.id == user.user_id))
    existing = result.scalar_one_or_none()
    if existing is not None:
        # Update name/avatar in case they changed
        existing.name = user.name
        existing.avatar_url = user.picture

        # Consolidate: check for OTHER user rows with the same email.
        # This prevents migration ping-pong when two auth sessions for the
        # same email resolve to different user IDs (e.g. mobile vs desktop
        # with stale NextAuth sessions).
        dups = await db.execute(
            select(UserModel).where(
                UserModel.email == user.email,
                UserModel.id != user.user_id,
            )
        )
        dup_rows = dups.scalars().all()
        if dup_rows:
            from backend.api.services import equipment_store
            from backend.api.services.session_store import sync_user_id

            for dup in dup_rows:
                old_id = dup.id
                db.expunge(dup)
                try:
                    async with db.begin_nested():
                        for col, table in _fk_refs:
                            # Try UPDATE; on unique constraint conflict, delete
                            # the old row instead (new user's row wins).
                            try:
                                async with db.begin_nested():
                                    await db.execute(
                                        text(
                                            f"UPDATE {table} SET {col} = :new_id "  # noqa: S608
                                            f"WHERE {col} = :old_id"
                                        ),
                                        {"new_id": user.user_id, "old_id": old_id},
                                    )
                            except Exception:
                                # Unique constraint violation — delete old rows
                                await db.execute(
                                    text(
                                        f"DELETE FROM {table} "  # noqa: S608
                                        f"WHERE {col} = :old_id"
                                    ),
                                    {"old_id": old_id},
                                )
                        await db.execute(
                            text("DELETE FROM users WHERE id = :old_id"),
                            {"old_id": old_id},
                        )
                    sync_user_id(old_id, user.user_id)
                    equipment_store.sync_user_id(old_id, user.user_id)
                    logger.info(
                        "Consolidated duplicate user %s → %s (email=%s)",
                        old_id,
                        user.user_id,
                        user.email,
                    )
                except Exception:
                    logger.warning(
                        "Failed to consolidate user %s → %s, skipping",
                        old_id,
                        user.user_id,
                        exc_info=True,
                    )
            await db.flush()
        return

    # Not found by ID — check if email already exists under a different ID
    result = await db.execute(select(UserModel).where(UserModel.email == user.email))
    by_email = result.scalar_one_or_none()
    if by_email is not None:
        old_id = by_email.id
        # Evict ORM object before raw SQL to avoid identity-map conflicts
        db.expunge(by_email)

        # Migration strategy: insert new user with temp email, migrate FKs,
        # delete old user, then fix email. This avoids FK violations (can't
        # UPDATE FKs to new_id before new_id exists) and email uniqueness
        # conflicts (can't have two rows with same email).

        # 1. Insert new user row with temporary email (FK target must exist first)
        # Must include all NOT NULL columns — raw SQL bypasses ORM defaults.
        temp_email = f"migrating-{user.user_id}"
        await db.execute(
            text(
                "INSERT INTO users "
                "(id, email, name, avatar_url, skill_level, role) "
                "VALUES (:new_id, :temp_email, :name, :avatar, "
                "'intermediate', 'driver')"
            ),
            {
                "new_id": user.user_id,
                "temp_email": temp_email,
                "name": user.name,
                "avatar": user.picture,
            },
        )

        # 2. Migrate all FK references from old_id to new_id
        for col, table in _fk_refs:
            try:
                async with db.begin_nested():
                    await db.execute(
                        text(
                            f"UPDATE {table} SET {col} = :new_id "  # noqa: S608
                            f"WHERE {col} = :old_id"
                        ),
                        {"new_id": user.user_id, "old_id": old_id},
                    )
            except Exception:
                # Unique constraint violation — delete old rows (new user wins)
                await db.execute(
                    text(
                        f"DELETE FROM {table} "  # noqa: S608
                        f"WHERE {col} = :old_id"
                    ),
                    {"old_id": old_id},
                )

        # 3. Delete old user row (no FKs point to it now)
        await db.execute(
            text("DELETE FROM users WHERE id = :old_id"),
            {"old_id": old_id},
        )

        # 4. Set correct email on new user row
        await db.execute(
            text("UPDATE users SET email = :email WHERE id = :new_id"),
            {"email": user.email, "new_id": user.user_id},
        )
        await db.flush()

        # 5. Sync in-memory stores so ownership checks work immediately
        #    (DB FKs are migrated but memory still has old_id)
        from backend.api.services import equipment_store
        from backend.api.services.session_store import sync_user_id

        sync_user_id(old_id, user.user_id)
        equipment_store.sync_user_id(old_id, user.user_id)
        return

    # Truly new user
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
    user_id: str | None,
    session_data: SessionData,
) -> None:
    """Persist session metadata to the database after upload.

    Uses ``merge`` so re-uploading the same session updates rather than errors.
    """
    snap = session_data.snapshot
    # Build snapshot JSON for immutable per-session data.
    # These are computed/fetched once and never change for a given session.
    snapshot_json: dict[str, object] = {}

    # Preserve the raw session date string for display (avoids isoformat +00:00)
    if snap.metadata.session_date:
        snapshot_json["session_date_display"] = snap.metadata.session_date

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
            "timezone_name": w.timezone_name,
        }

    # GPS centroid (derived from session telemetry)
    try:
        df = session_data.parsed.data
        if not df.empty and "lat" in df.columns and "lon" in df.columns:
            snapshot_json["gps_centroid"] = {
                "lat": round(float(df["lat"].mean()), 6),
                "lon": round(float(df["lon"].mean()), 6),
            }
    except (ValueError, KeyError, AttributeError):
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
        surface_water_mm=w.get("surface_water_mm"),
        weather_source=w.get("weather_source"),
        weather_confidence=w.get("weather_confidence"),
        dew_point_c=w.get("dew_point_c"),
        timezone_name=w.get("timezone_name"),
        track_condition_is_manual=w.get("track_condition_is_manual", False),
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


async def get_session_for_user_with_db_sync(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> SessionData | None:
    """Get session for user, with DB-backed ownership sync on mismatch.

    When the in-memory store has a stale user_id (e.g. after OAuth sub change
    and backend restart), the DB may already have the correct FK but the
    in-memory store still holds the old user_id.  This checks the DB and
    syncs the in-memory user_id when ownership is confirmed.
    """
    from backend.api.services.session_store import get_session, get_session_for_user

    # Fast path: in-memory ownership matches
    sd = get_session_for_user(session_id, user_id)
    if sd is not None:
        return sd

    # Session might exist with stale user_id — check if it's in memory at all
    sd = get_session(session_id)
    if sd is None:
        # Attempt lazy rehydration from DB-stored CSV
        from backend.api.services.session_store import rehydrate_session

        sd = await rehydrate_session(session_id, db)
    if sd is None:
        return None  # Session truly doesn't exist

    # Verify ownership in DB (which ensure_user_exists keeps up to date)
    if await verify_session_owner(db, session_id, user_id):
        # DB confirms ownership — sync in-memory store
        sd.user_id = user_id
        return sd

    return None


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

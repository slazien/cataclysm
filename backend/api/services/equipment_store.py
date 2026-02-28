"""In-memory store for equipment profiles with JSON disk persistence.

Keeps equipment profiles and session-equipment linkages keyed by profile ID
and session ID respectively.  Data is persisted as JSON files under the
configured ``equipment_dir`` so they survive server restarts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from cataclysm.equipment import (
    BrakeSpec,
    EquipmentProfile,
    MuSource,
    SessionConditions,
    SessionEquipment,
    SuspensionSpec,
    TireCompoundCategory,
    TireSpec,
    TrackCondition,
)
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level in-memory stores
# ---------------------------------------------------------------------------

_profiles: dict[str, EquipmentProfile] = {}
_session_equipment: dict[str, SessionEquipment] = {}

# Disk persistence directory (set via init_equipment_dir on startup)
_equipment_dir: Path | None = None


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def init_equipment_dir(path: str) -> None:
    """Configure the directory used for persisting equipment data.

    Creates subdirectories ``profiles/`` and ``sessions/`` under *path*.
    """
    global _equipment_dir  # noqa: PLW0603
    _equipment_dir = Path(path)
    (_equipment_dir / "profiles").mkdir(parents=True, exist_ok=True)
    (_equipment_dir / "sessions").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Internal persistence helpers
# ---------------------------------------------------------------------------


def _persist_profile(profile: EquipmentProfile) -> None:
    """Write an equipment profile to disk as JSON."""
    if _equipment_dir is None:
        return
    try:
        out = _equipment_dir / "profiles" / f"{profile.id}.json"
        out.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")
    except OSError:
        logger.warning("Failed to persist equipment profile %s", profile.id, exc_info=True)


def _delete_persisted_profile(profile_id: str) -> None:
    """Remove a persisted equipment profile from disk."""
    if _equipment_dir is None:
        return
    path = _equipment_dir / "profiles" / f"{profile_id}.json"
    path.unlink(missing_ok=True)


def _persist_session_equipment(se: SessionEquipment) -> None:
    """Write a session-equipment linkage to disk as JSON."""
    if _equipment_dir is None:
        return
    try:
        out = _equipment_dir / "sessions" / f"{se.session_id}.json"
        out.write_text(json.dumps(asdict(se), indent=2), encoding="utf-8")
    except OSError:
        logger.warning(
            "Failed to persist session equipment for %s",
            se.session_id,
            exc_info=True,
        )


def _delete_persisted_session_equipment(session_id: str) -> None:
    """Remove a persisted session-equipment linkage from disk."""
    if _equipment_dir is None:
        return
    path = _equipment_dir / "sessions" / f"{session_id}.json"
    path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Deserialization helpers
# ---------------------------------------------------------------------------


def _opt_str(d: dict[str, object], key: str) -> str | None:
    """Extract an optional string value from *d*."""
    v = d.get(key)
    return str(v) if v is not None else None


def _opt_float(d: dict[str, object], key: str) -> float | None:
    """Extract an optional float value from *d*."""
    v = d.get(key)
    return float(v) if v is not None else None  # type: ignore[arg-type]


def _opt_int(d: dict[str, object], key: str) -> int | None:
    """Extract an optional int value from *d*."""
    v = d.get(key)
    if v is None:
        return None
    return v if isinstance(v, int) else int(str(v))


def _tire_spec_from_dict(d: dict[str, object]) -> TireSpec:
    """Reconstruct a TireSpec from a plain dict."""
    return TireSpec(
        model=str(d["model"]),
        compound_category=TireCompoundCategory(str(d["compound_category"])),
        size=str(d["size"]),
        treadwear_rating=_opt_int(d, "treadwear_rating"),
        estimated_mu=float(d["estimated_mu"]),  # type: ignore[arg-type]
        mu_source=MuSource(str(d["mu_source"])),
        mu_confidence=str(d["mu_confidence"]),
        pressure_psi=_opt_float(d, "pressure_psi"),
        brand=_opt_str(d, "brand"),
        age_sessions=_opt_int(d, "age_sessions"),
    )


def _brake_spec_from_dict(d: dict[str, object]) -> BrakeSpec:
    """Reconstruct a BrakeSpec from a plain dict."""
    return BrakeSpec(
        compound=_opt_str(d, "compound"),
        rotor_type=_opt_str(d, "rotor_type"),
        pad_temp_range=_opt_str(d, "pad_temp_range"),
        fluid_type=_opt_str(d, "fluid_type"),
    )


def _suspension_spec_from_dict(d: dict[str, object]) -> SuspensionSpec:
    """Reconstruct a SuspensionSpec from a plain dict."""
    return SuspensionSpec(
        type=_opt_str(d, "type"),
        front_spring_rate=_opt_str(d, "front_spring_rate"),
        rear_spring_rate=_opt_str(d, "rear_spring_rate"),
        front_camber_deg=_opt_float(d, "front_camber_deg"),
        rear_camber_deg=_opt_float(d, "rear_camber_deg"),
        front_toe=_opt_str(d, "front_toe"),
        rear_toe=_opt_str(d, "rear_toe"),
        front_rebound=_opt_int(d, "front_rebound"),
        front_compression=_opt_int(d, "front_compression"),
        rear_rebound=_opt_int(d, "rear_rebound"),
        rear_compression=_opt_int(d, "rear_compression"),
        sway_bar_front=_opt_str(d, "sway_bar_front"),
        sway_bar_rear=_opt_str(d, "sway_bar_rear"),
    )


def _profile_from_dict(d: dict[str, object]) -> EquipmentProfile:
    """Reconstruct an EquipmentProfile from a plain dict."""
    tires_raw = d["tires"]
    assert isinstance(tires_raw, dict)
    brakes_raw = d.get("brakes")
    suspension_raw = d.get("suspension")
    brakes = _brake_spec_from_dict(brakes_raw) if isinstance(brakes_raw, dict) else None
    suspension = (
        _suspension_spec_from_dict(suspension_raw) if isinstance(suspension_raw, dict) else None
    )
    return EquipmentProfile(
        id=str(d["id"]),
        name=str(d["name"]),
        tires=_tire_spec_from_dict(tires_raw),
        brakes=brakes,
        suspension=suspension,
        notes=_opt_str(d, "notes"),
    )


def _session_conditions_from_dict(
    d: dict[str, object],
) -> SessionConditions:
    """Reconstruct SessionConditions from a plain dict."""
    return SessionConditions(
        track_condition=TrackCondition(str(d["track_condition"])),
        ambient_temp_c=_opt_float(d, "ambient_temp_c"),
        track_temp_c=_opt_float(d, "track_temp_c"),
        humidity_pct=_opt_float(d, "humidity_pct"),
        wind_speed_kmh=_opt_float(d, "wind_speed_kmh"),
        wind_direction_deg=_opt_float(d, "wind_direction_deg"),
        precipitation_mm=_opt_float(d, "precipitation_mm"),
        weather_source=_opt_str(d, "weather_source"),
    )


def _session_equipment_from_dict(
    d: dict[str, object],
) -> SessionEquipment:
    """Reconstruct a SessionEquipment from a plain dict."""
    conditions_raw = d.get("conditions")
    overrides_raw = d.get("overrides")
    conditions = (
        _session_conditions_from_dict(conditions_raw) if isinstance(conditions_raw, dict) else None
    )
    return SessionEquipment(
        session_id=str(d["session_id"]),
        profile_id=str(d["profile_id"]),
        overrides=(dict(overrides_raw) if isinstance(overrides_raw, dict) else {}),
        conditions=conditions,
    )


# ---------------------------------------------------------------------------
# Public API — Profiles
# ---------------------------------------------------------------------------


def store_profile(profile: EquipmentProfile) -> None:
    """Persist an equipment profile in-memory and to disk."""
    _profiles[profile.id] = profile
    _persist_profile(profile)


def get_profile(profile_id: str) -> EquipmentProfile | None:
    """Retrieve an equipment profile by ID, or None if not found."""
    return _profiles.get(profile_id)


def list_profiles() -> list[EquipmentProfile]:
    """Return all equipment profiles sorted by name."""
    return sorted(_profiles.values(), key=lambda p: p.name)


def delete_profile(profile_id: str) -> bool:
    """Remove an equipment profile from memory and disk.

    Returns True if the profile existed and was deleted.
    """
    if profile_id not in _profiles:
        return False
    del _profiles[profile_id]
    _delete_persisted_profile(profile_id)
    return True


# ---------------------------------------------------------------------------
# Public API — Session Equipment
# ---------------------------------------------------------------------------


def store_session_equipment(se: SessionEquipment) -> None:
    """Persist a session-equipment linkage in-memory and to disk."""
    _session_equipment[se.session_id] = se
    _persist_session_equipment(se)


def get_session_equipment(session_id: str) -> SessionEquipment | None:
    """Retrieve session equipment by session ID, or None if not found."""
    return _session_equipment.get(session_id)


def delete_session_equipment(session_id: str) -> bool:
    """Remove session equipment from memory and disk.

    Returns True if the session equipment existed and was deleted.
    """
    if session_id not in _session_equipment:
        return False
    del _session_equipment[session_id]
    _delete_persisted_session_equipment(session_id)
    return True


# ---------------------------------------------------------------------------
# Disk loading
# ---------------------------------------------------------------------------


def load_persisted_profiles() -> int:
    """Load all persisted equipment profiles from disk into memory.

    Returns the number of profiles loaded.
    """
    if _equipment_dir is None or not (_equipment_dir / "profiles").exists():
        return 0

    count = 0
    for path in (_equipment_dir / "profiles").glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            profile = _profile_from_dict(data)
            _profiles[profile.id] = profile
            count += 1
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError):
            logger.warning("Failed to load equipment profile from %s", path, exc_info=True)
    return count


def load_persisted_session_equipment() -> int:
    """Load all persisted session-equipment linkages from disk into memory.

    Returns the number of session-equipment records loaded.
    """
    if _equipment_dir is None or not (_equipment_dir / "sessions").exists():
        return 0

    count = 0
    for path in (_equipment_dir / "sessions").glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            se = _session_equipment_from_dict(data)
            _session_equipment[se.session_id] = se
            count += 1
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError):
            logger.warning("Failed to load session equipment from %s", path, exc_info=True)
    return count


# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------


def clear_all_equipment() -> None:
    """Remove all equipment data from memory (does not delete disk files)."""
    _profiles.clear()
    _session_equipment.clear()


# ---------------------------------------------------------------------------
# Database persistence helpers
# ---------------------------------------------------------------------------


async def db_persist_profile(profile: EquipmentProfile, user_id: str | None = None) -> None:
    """Write an equipment profile to PostgreSQL.

    Uses upsert semantics (merge) so it works for both create and update.
    """
    from backend.api.db.database import async_session_factory
    from backend.api.db.models import EquipmentProfileDB

    try:
        async with async_session_factory() as db:
            await db.merge(
                EquipmentProfileDB(
                    id=profile.id,
                    user_id=user_id,
                    name=profile.name,
                    profile_json=asdict(profile),
                )
            )
            await db.commit()
    except SQLAlchemyError:
        logger.warning("Failed to persist equipment profile %s to DB", profile.id, exc_info=True)


async def db_delete_profile(profile_id: str) -> None:
    """Delete an equipment profile from PostgreSQL."""
    from sqlalchemy import delete

    from backend.api.db.database import async_session_factory
    from backend.api.db.models import EquipmentProfileDB

    try:
        async with async_session_factory() as db:
            await db.execute(delete(EquipmentProfileDB).where(EquipmentProfileDB.id == profile_id))
            await db.commit()
    except SQLAlchemyError:
        logger.warning("Failed to delete equipment profile %s from DB", profile_id, exc_info=True)


async def db_persist_session_equipment(se: SessionEquipment) -> None:
    """Write a session-equipment assignment to PostgreSQL."""
    from backend.api.db.database import async_session_factory
    from backend.api.db.models import SessionEquipmentDB

    try:
        async with async_session_factory() as db:
            await db.merge(
                SessionEquipmentDB(
                    session_id=se.session_id,
                    profile_id=se.profile_id,
                    assignment_json=asdict(se),
                )
            )
            await db.commit()
    except SQLAlchemyError:
        logger.warning(
            "Failed to persist session equipment for %s to DB",
            se.session_id,
            exc_info=True,
        )


async def db_delete_session_equipment(session_id: str) -> None:
    """Delete a session-equipment assignment from PostgreSQL."""
    from sqlalchemy import delete

    from backend.api.db.database import async_session_factory
    from backend.api.db.models import SessionEquipmentDB

    try:
        async with async_session_factory() as db:
            await db.execute(
                delete(SessionEquipmentDB).where(SessionEquipmentDB.session_id == session_id)
            )
            await db.commit()
    except SQLAlchemyError:
        logger.warning(
            "Failed to delete session equipment for %s from DB",
            session_id,
            exc_info=True,
        )


async def load_equipment_from_db() -> tuple[int, int]:
    """Load all equipment profiles and session assignments from PostgreSQL.

    Returns (n_profiles, n_assignments) loaded.
    """
    from sqlalchemy import select

    from backend.api.db.database import async_session_factory
    from backend.api.db.models import EquipmentProfileDB, SessionEquipmentDB

    n_profiles = 0
    n_assignments = 0

    try:
        async with async_session_factory() as db:
            # Load profiles
            profile_result = await db.execute(select(EquipmentProfileDB))
            profile_rows = profile_result.scalars().all()
            for p_row in profile_rows:
                try:
                    if p_row.profile_json:
                        profile = _profile_from_dict(p_row.profile_json)
                        _profiles[profile.id] = profile
                        n_profiles += 1
                except (KeyError, TypeError, ValueError):
                    logger.warning(
                        "Failed to deserialize equipment profile %s from DB",
                        p_row.id,
                        exc_info=True,
                    )

            # Load session equipment
            se_result = await db.execute(select(SessionEquipmentDB))
            se_rows = se_result.scalars().all()
            for se_row in se_rows:
                try:
                    if se_row.assignment_json:
                        se = _session_equipment_from_dict(se_row.assignment_json)
                        _session_equipment[se.session_id] = se
                        n_assignments += 1
                except (KeyError, TypeError, ValueError):
                    logger.warning(
                        "Failed to deserialize session equipment for %s from DB",
                        se_row.session_id,
                        exc_info=True,
                    )
    except SQLAlchemyError:
        logger.warning("Database equipment load failed", exc_info=True)

    return n_profiles, n_assignments

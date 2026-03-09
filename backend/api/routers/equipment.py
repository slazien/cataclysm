"""Equipment profile CRUD and session-equipment assignment endpoints."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC
from typing import Annotated

from cataclysm.equipment import (
    CATEGORY_MU_DEFAULTS,
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
from cataclysm.vehicle_db import VehicleSpec
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.dependencies import AuthenticatedUser, get_current_user, get_user_or_anon
from backend.api.schemas.equipment import (
    BrakePadSearchResult,
    BrakeSpecSchema,
    EquipmentProfileCreate,
    EquipmentProfileList,
    EquipmentProfileResponse,
    InlineEquipmentSet,
    SessionConditionsSchema,
    SessionEquipmentResponse,
    SessionEquipmentSet,
    SuspensionSpecSchema,
    TireSpecSchema,
    VehicleSearchResult,
    VehicleSpecSchema,
)
from backend.api.services import equipment_store
from backend.api.services.db_session_store import get_session_for_user_with_db_sync
from backend.api.services.pipeline import invalidate_physics_cache, invalidate_profile_cache

router = APIRouter()
_logger = logging.getLogger(__name__)

# Track fire-and-forget DB tasks to prevent GC collection
_bg_tasks: set[asyncio.Task[None]] = set()


def _fire_and_forget(coro: object) -> None:
    """Schedule a coroutine as a background task with error logging."""
    task: asyncio.Task[None] = asyncio.create_task(coro)  # type: ignore[arg-type]
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    task.add_done_callback(
        lambda t: (
            _logger.warning("Background DB write failed: %s", t.exception())
            if not t.cancelled() and t.exception()
            else None
        )
    )


# ---------------------------------------------------------------------------
# Tire search (must be defined before /{session_id} routes)
# ---------------------------------------------------------------------------


@router.get("/tires/search")
async def search_tires(
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    q: str = "",
) -> list[TireSpecSchema]:
    """Search curated tire database. Returns matching tires."""
    from cataclysm.tire_db import list_all_curated_tires, search_curated_tires

    curated = list_all_curated_tires() if not q else search_curated_tires(q)
    return [
        TireSpecSchema(
            model=t.model,
            compound_category=t.compound_category.value,
            size=t.size,
            treadwear_rating=t.treadwear_rating,
            estimated_mu=t.estimated_mu,
            mu_source=t.mu_source.value,
            mu_confidence=t.mu_confidence,
            brand=t.brand,
        )
        for t in curated
    ]


# ---------------------------------------------------------------------------
# Brake pad search (must be defined before /{session_id} routes)
# ---------------------------------------------------------------------------


@router.get("/brakes/search")
async def search_brake_pads(
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    q: str = "",
) -> list[BrakePadSearchResult]:
    """Search curated brake pad database. Returns matching pads."""
    from cataclysm.brake_pad_db import list_all_curated_brake_pads, search_curated_brake_pads

    curated = list_all_curated_brake_pads() if not q else search_curated_brake_pads(q)
    return [
        BrakePadSearchResult(
            model=p.model,
            brand=p.brand,
            category=p.category,
            temp_range=p.temp_range,
            initial_bite=p.initial_bite,
            notes=p.notes,
        )
        for p in curated
    ]


# ---------------------------------------------------------------------------
# Vehicle database (must be defined before /{session_id} routes)
# ---------------------------------------------------------------------------


def _vehicle_to_schema(v: VehicleSpec) -> VehicleSpecSchema:
    """Convert a domain VehicleSpec to the API schema."""
    return VehicleSpecSchema(
        make=v.make,
        model=v.model,
        generation=v.generation,
        year_range=list(v.year_range),
        weight_kg=v.weight_kg,
        wheelbase_m=v.wheelbase_m,
        track_width_front_m=v.track_width_front_m,
        track_width_rear_m=v.track_width_rear_m,
        cg_height_m=v.cg_height_m,
        weight_dist_front_pct=v.weight_dist_front_pct,
        drivetrain=v.drivetrain,
        hp=v.hp,
        torque_nm=v.torque_nm,
        has_aero=v.has_aero,
        notes=v.notes,
    )


def _vehicle_to_search_result(slug: str, v: VehicleSpec) -> VehicleSearchResult:
    """Convert a VehicleSpec to a lightweight search result."""
    return VehicleSearchResult(
        slug=slug,
        make=v.make,
        model=v.model,
        generation=v.generation,
        year_range=list(v.year_range),
        hp=v.hp,
        weight_kg=v.weight_kg,
        drivetrain=v.drivetrain,
    )


@router.get("/vehicles/makes")
async def get_vehicle_makes(
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
) -> list[str]:
    """List all available vehicle makes."""
    from cataclysm.vehicle_db import list_makes

    return list_makes()


@router.get("/vehicles/search")
async def search_vehicles_endpoint(
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    q: str = "",
) -> list[VehicleSearchResult]:
    """Search vehicles by make, model, or generation."""
    from cataclysm.vehicle_db import VEHICLE_DATABASE, search_vehicles

    if not q:
        # Return all vehicles when no query
        results: list[VehicleSearchResult] = []
        for slug, spec in sorted(VEHICLE_DATABASE.items()):
            results.append(_vehicle_to_search_result(slug, spec))
        return results

    matches = search_vehicles(q)
    results = []
    for spec in matches:
        # Find slug for this spec
        for slug, db_spec in VEHICLE_DATABASE.items():
            if db_spec is spec:
                results.append(_vehicle_to_search_result(slug, spec))
                break
    return results


@router.get("/vehicles/{make}/models")
async def get_vehicle_models(
    make: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
) -> list[str]:
    """List all models for a given make."""
    from cataclysm.vehicle_db import list_models

    return list_models(make)


@router.get("/vehicles/{make}/{model}")
async def get_vehicle_spec(
    make: str,
    model: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    generation: str | None = None,
) -> VehicleSpecSchema:
    """Get vehicle spec by make/model, optionally filtered by generation."""
    from cataclysm.vehicle_db import find_vehicle

    spec = find_vehicle(make, model, generation)
    if spec is None:
        detail = f"Vehicle {make} {model}"
        if generation:
            detail += f" ({generation})"
        detail += " not found"
        raise HTTPException(status_code=404, detail=detail)
    return _vehicle_to_schema(spec)


# ---------------------------------------------------------------------------
# Reference data (must be defined before /{session_id} routes)
# ---------------------------------------------------------------------------


@router.get("/reference/tire-sizes")
async def get_reference_tire_sizes(
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
) -> list[str]:
    """Return common tire sizes for track days."""
    from cataclysm.tire_db import list_common_tire_sizes

    return list_common_tire_sizes()


@router.get("/reference/brake-fluids")
async def get_reference_brake_fluids(
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
) -> list[str]:
    """Return common brake fluid options."""
    from cataclysm.brake_pad_db import COMMON_BRAKE_FLUIDS

    return list(COMMON_BRAKE_FLUIDS)


# ---------------------------------------------------------------------------
# Weather lookup (must be defined before /{session_id} routes)
# ---------------------------------------------------------------------------


class WeatherLookupRequest(BaseModel):
    """Request body for looking up weather conditions."""

    lat: float
    lon: float
    session_date: str  # "YYYY-MM-DD"
    hour: int = 12


@router.post("/weather/lookup")
async def weather_lookup(
    body: WeatherLookupRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, object]:
    """Look up weather conditions for a track location and date."""
    from datetime import datetime

    from cataclysm.weather_client import lookup_weather

    dt = datetime.strptime(body.session_date, "%Y-%m-%d").replace(hour=body.hour, tzinfo=UTC)
    result = await lookup_weather(body.lat, body.lon, dt)
    if result is None:
        return {"conditions": None, "message": "Weather data unavailable"}

    return {
        "conditions": SessionConditionsSchema(
            track_condition=result.track_condition.value,
            ambient_temp_c=result.ambient_temp_c,
            humidity_pct=result.humidity_pct,
            wind_speed_kmh=result.wind_speed_kmh,
            wind_direction_deg=result.wind_direction_deg,
            precipitation_mm=result.precipitation_mm,
            weather_source=result.weather_source,
        ).model_dump(),
    }


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _schema_to_tire(s: TireSpecSchema) -> TireSpec:
    """Convert a TireSpecSchema to the domain TireSpec dataclass."""
    mu = s.estimated_mu
    mu_source = MuSource(s.mu_source)
    category = TireCompoundCategory(s.compound_category)

    # When mu is the uncalibrated default (1.0 from formula with no treadwear),
    # upgrade to the compound-category default for a more useful estimate.
    if mu_source == MuSource.FORMULA_ESTIMATE and mu == 1.0:
        mu = CATEGORY_MU_DEFAULTS.get(category, 1.0)

    return TireSpec(
        model=s.model,
        compound_category=category,
        size=s.size,
        treadwear_rating=s.treadwear_rating,
        estimated_mu=mu,
        mu_source=mu_source,
        mu_confidence=s.mu_confidence,
        pressure_psi=s.pressure_psi,
        brand=s.brand,
        age_sessions=s.age_sessions,
    )


def _schema_to_brakes(s: BrakeSpecSchema) -> BrakeSpec:
    """Convert a BrakeSpecSchema to the domain BrakeSpec dataclass."""
    return BrakeSpec(
        compound=s.compound,
        rotor_type=s.rotor_type,
        pad_temp_range=s.pad_temp_range,
        fluid_type=s.fluid_type,
    )


def _schema_to_suspension(s: SuspensionSpecSchema) -> SuspensionSpec:
    """Convert a SuspensionSpecSchema to the domain SuspensionSpec dataclass."""
    return SuspensionSpec(
        type=s.type,
        front_spring_rate=s.front_spring_rate,
        rear_spring_rate=s.rear_spring_rate,
        front_camber_deg=s.front_camber_deg,
        rear_camber_deg=s.rear_camber_deg,
        front_toe=s.front_toe,
        rear_toe=s.rear_toe,
        front_rebound=s.front_rebound,
        front_compression=s.front_compression,
        rear_rebound=s.rear_rebound,
        rear_compression=s.rear_compression,
        sway_bar_front=s.sway_bar_front,
        sway_bar_rear=s.sway_bar_rear,
    )


def _tire_to_schema(t: TireSpec) -> TireSpecSchema:
    """Convert a domain TireSpec to the API schema."""
    return TireSpecSchema(
        model=t.model,
        compound_category=t.compound_category.value,
        size=t.size,
        treadwear_rating=t.treadwear_rating,
        estimated_mu=t.estimated_mu,
        mu_source=t.mu_source.value,
        mu_confidence=t.mu_confidence,
        pressure_psi=t.pressure_psi,
        brand=t.brand,
        age_sessions=t.age_sessions,
    )


def _brakes_to_schema(b: BrakeSpec) -> BrakeSpecSchema:
    """Convert a domain BrakeSpec to the API schema."""
    return BrakeSpecSchema(
        compound=b.compound,
        rotor_type=b.rotor_type,
        pad_temp_range=b.pad_temp_range,
        fluid_type=b.fluid_type,
    )


def _suspension_to_schema(s: SuspensionSpec) -> SuspensionSpecSchema:
    """Convert a domain SuspensionSpec to the API schema."""
    return SuspensionSpecSchema(
        type=s.type,
        front_spring_rate=s.front_spring_rate,
        rear_spring_rate=s.rear_spring_rate,
        front_camber_deg=s.front_camber_deg,
        rear_camber_deg=s.rear_camber_deg,
        front_toe=s.front_toe,
        rear_toe=s.rear_toe,
        front_rebound=s.front_rebound,
        front_compression=s.front_compression,
        rear_rebound=s.rear_rebound,
        rear_compression=s.rear_compression,
        sway_bar_front=s.sway_bar_front,
        sway_bar_rear=s.sway_bar_rear,
    )


def _schema_to_vehicle(s: VehicleSpecSchema) -> VehicleSpec:
    """Convert a VehicleSpecSchema to the domain VehicleSpec dataclass."""
    return VehicleSpec(
        make=s.make,
        model=s.model,
        generation=s.generation,
        year_range=(s.year_range[0], s.year_range[1]),
        weight_kg=s.weight_kg,
        wheelbase_m=s.wheelbase_m,
        track_width_front_m=s.track_width_front_m,
        track_width_rear_m=s.track_width_rear_m,
        cg_height_m=s.cg_height_m,
        weight_dist_front_pct=s.weight_dist_front_pct,
        drivetrain=s.drivetrain,
        hp=s.hp,
        torque_nm=s.torque_nm,
        has_aero=s.has_aero,
        notes=s.notes,
    )


def _profile_to_response(p: EquipmentProfile) -> EquipmentProfileResponse:
    """Convert a domain EquipmentProfile to the API response schema."""
    return EquipmentProfileResponse(
        id=p.id,
        name=p.name,
        tires=_tire_to_schema(p.tires),
        vehicle=_vehicle_to_schema(p.vehicle) if p.vehicle else None,
        brakes=_brakes_to_schema(p.brakes) if p.brakes else None,
        suspension=_suspension_to_schema(p.suspension) if p.suspension else None,
        vehicle_overrides=p.vehicle_overrides,
        notes=p.notes,
        is_default=p.is_default,
    )


def _conditions_to_schema(c: SessionConditions) -> SessionConditionsSchema:
    """Convert domain SessionConditions to the API schema."""
    return SessionConditionsSchema(
        track_condition=c.track_condition.value,
        ambient_temp_c=c.ambient_temp_c,
        track_temp_c=c.track_temp_c,
        humidity_pct=c.humidity_pct,
        wind_speed_kmh=c.wind_speed_kmh,
        wind_direction_deg=c.wind_direction_deg,
        precipitation_mm=c.precipitation_mm,
        weather_source=c.weather_source,
    )


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------


@router.post("/profiles", response_model=EquipmentProfileResponse, status_code=201)
async def create_profile(
    body: EquipmentProfileCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> EquipmentProfileResponse:
    """Create a new equipment profile."""
    profile_id = f"eq_{uuid.uuid4().hex[:12]}"
    profile = EquipmentProfile(
        id=profile_id,
        name=body.name,
        tires=_schema_to_tire(body.tires),
        vehicle=_schema_to_vehicle(body.vehicle) if body.vehicle else None,
        brakes=_schema_to_brakes(body.brakes) if body.brakes else None,
        suspension=_schema_to_suspension(body.suspension) if body.suspension else None,
        vehicle_overrides=dict(body.vehicle_overrides),
        notes=body.notes,
        is_default=body.is_default,
    )
    equipment_store.store_profile(profile)
    equipment_store.set_profile_owner(profile_id, current_user.user_id)

    # Enforce single-default: unset others if this is marked default
    if profile.is_default:
        changed = equipment_store.ensure_single_default(current_user.user_id, profile_id)
        for cid in changed:
            cp = equipment_store.get_profile(cid)
            if cp is not None:
                await equipment_store.db_persist_profile(cp, user_id=current_user.user_id)

    await equipment_store.db_persist_profile(profile, user_id=current_user.user_id)
    return _profile_to_response(profile)


@router.get("/profiles", response_model=EquipmentProfileList)
async def list_profiles(
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
) -> EquipmentProfileList:
    """List equipment profiles owned by the current user.

    Returns an empty list for anonymous users — they have no persistent profiles.
    """
    if current_user.user_id == "anon":
        return EquipmentProfileList(items=[], total=0)
    profiles = equipment_store.list_profiles_for_user(current_user.user_id)
    items = [_profile_to_response(p) for p in profiles]
    return EquipmentProfileList(items=items, total=len(items))


@router.get("/profiles/{profile_id}", response_model=EquipmentProfileResponse)
async def get_profile(
    profile_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> EquipmentProfileResponse:
    """Get a single equipment profile by ID."""
    profile = equipment_store.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    owner = equipment_store.get_profile_owner(profile_id)
    if owner is not None and owner != current_user.user_id:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    return _profile_to_response(profile)


@router.patch("/profiles/{profile_id}", response_model=EquipmentProfileResponse)
async def update_profile(
    profile_id: str,
    body: EquipmentProfileCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> EquipmentProfileResponse:
    """Update an existing equipment profile."""
    existing = equipment_store.get_profile(profile_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    owner = equipment_store.get_profile_owner(profile_id)
    if owner is not None and owner != current_user.user_id:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")

    updated = EquipmentProfile(
        id=profile_id,
        name=body.name,
        tires=_schema_to_tire(body.tires),
        vehicle=_schema_to_vehicle(body.vehicle) if body.vehicle else None,
        brakes=_schema_to_brakes(body.brakes) if body.brakes else None,
        suspension=_schema_to_suspension(body.suspension) if body.suspension else None,
        vehicle_overrides=dict(body.vehicle_overrides),
        notes=body.notes,
        is_default=body.is_default,
    )
    equipment_store.store_profile(updated)
    invalidate_profile_cache(profile_id)

    # Enforce single-default: unset others if this is marked default
    if updated.is_default:
        changed = equipment_store.ensure_single_default(current_user.user_id, profile_id)
        for cid in changed:
            cp = equipment_store.get_profile(cid)
            if cp is not None:
                await equipment_store.db_persist_profile(cp, user_id=current_user.user_id)

    await equipment_store.db_persist_profile(updated, user_id=current_user.user_id)
    return _profile_to_response(updated)


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, str]:
    """Delete an equipment profile."""
    owner = equipment_store.get_profile_owner(profile_id)
    if owner is not None and owner != current_user.user_id:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    deleted = equipment_store.delete_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    invalidate_profile_cache(profile_id)
    await equipment_store.db_delete_profile(profile_id)
    return {"message": f"Profile {profile_id} deleted"}


# ---------------------------------------------------------------------------
# Session Equipment
# ---------------------------------------------------------------------------


@router.put("/{session_id}/equipment", response_model=SessionEquipmentResponse)
async def set_session_equipment(
    session_id: str,
    body: SessionEquipmentSet,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionEquipmentResponse:
    """Assign an equipment profile to a session."""
    # Validate session exists and ownership — use DB-backed sync so that
    # stale in-memory user_ids (e.g. after backend restart) don't cause 404s.
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Validate profile exists
    profile = equipment_store.get_profile(body.profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {body.profile_id} not found")

    # Build domain object
    conditions: SessionConditions | None = None
    if body.conditions is not None:
        conditions = SessionConditions(
            track_condition=TrackCondition(body.conditions.track_condition),
            ambient_temp_c=body.conditions.ambient_temp_c,
            track_temp_c=body.conditions.track_temp_c,
            humidity_pct=body.conditions.humidity_pct,
            wind_speed_kmh=body.conditions.wind_speed_kmh,
            wind_direction_deg=body.conditions.wind_direction_deg,
            precipitation_mm=body.conditions.precipitation_mm,
            weather_source=body.conditions.weather_source,
        )

    se = SessionEquipment(
        session_id=session_id,
        profile_id=body.profile_id,
        overrides=dict(body.overrides),
        conditions=conditions,
    )
    equipment_store.store_session_equipment(se)
    invalidate_physics_cache(session_id)
    # Fire-and-forget: in-memory store is authoritative, DB is crash recovery.
    # Don't block the HTTP response for the Postgres round-trip.
    _fire_and_forget(equipment_store.db_persist_session_equipment(se))

    return SessionEquipmentResponse(
        session_id=session_id,
        profile_id=profile.id,
        profile_name=profile.name,
        overrides=se.overrides,
        tires=_tire_to_schema(profile.tires),
        brakes=_brakes_to_schema(profile.brakes) if profile.brakes else None,
        suspension=_suspension_to_schema(profile.suspension) if profile.suspension else None,
        conditions=_conditions_to_schema(conditions) if conditions else None,
    )


@router.put("/{session_id}/equipment/inline", response_model=SessionEquipmentResponse)
async def set_session_equipment_inline(
    session_id: str,
    body: InlineEquipmentSet,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionEquipmentResponse:
    """Assign equipment to a session without creating a named profile.

    Works for both anonymous and authenticated users.  The ephemeral profile is
    stored in-memory and promoted to a persistent profile when the user signs up
    (via the session claim endpoint).
    """
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        category = TireCompoundCategory(body.compound_category)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid compound_category: {body.compound_category}",
        ) from exc

    mu = (
        body.estimated_mu
        if body.estimated_mu is not None
        else CATEGORY_MU_DEFAULTS.get(category, 0.93)
    )
    tire_schema = TireSpecSchema(
        model="OEM / Stock",
        compound_category=body.compound_category,
        size=body.tire_size.strip(),
        estimated_mu=mu,
        mu_source="formula_estimate",
        mu_confidence="low",
    )
    profile_id = f"eq_{uuid.uuid4().hex[:12]}"
    profile = EquipmentProfile(
        id=profile_id,
        name="Track Day Setup",
        tires=_schema_to_tire(tire_schema),
        is_default=False,
    )
    equipment_store.store_profile(profile)
    equipment_store.set_profile_owner(profile_id, current_user.user_id)

    se = SessionEquipment(session_id=session_id, profile_id=profile_id)
    equipment_store.store_session_equipment(se)
    invalidate_physics_cache(session_id)

    # Only persist to DB for authenticated users; anon profiles migrate on claim.
    if current_user.user_id != "anon":
        _fire_and_forget(equipment_store.db_persist_profile(profile, user_id=current_user.user_id))
        _fire_and_forget(equipment_store.db_persist_session_equipment(se))

    return SessionEquipmentResponse(
        session_id=session_id,
        profile_id=profile.id,
        profile_name=profile.name,
        overrides={},
        tires=_tire_to_schema(profile.tires),
        brakes=None,
        suspension=None,
        conditions=None,
    )


@router.get("/{session_id}/equipment", response_model=SessionEquipmentResponse)
async def get_session_equipment(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionEquipmentResponse:
    """Get the effective equipment assignment for a session."""
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    se = equipment_store.get_session_equipment(session_id)
    if se is None:
        raise HTTPException(
            status_code=404,
            detail=f"No equipment assigned to session {session_id}",
        )

    profile = equipment_store.get_profile(se.profile_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Profile {se.profile_id} referenced by session no longer exists",
        )

    return SessionEquipmentResponse(
        session_id=session_id,
        profile_id=profile.id,
        profile_name=profile.name,
        overrides=se.overrides,
        tires=_tire_to_schema(profile.tires),
        brakes=_brakes_to_schema(profile.brakes) if profile.brakes else None,
        suspension=_suspension_to_schema(profile.suspension) if profile.suspension else None,
        conditions=_conditions_to_schema(se.conditions) if se.conditions else None,
    )

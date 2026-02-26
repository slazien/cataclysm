"""Equipment profile CRUD and session-equipment assignment endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC
from typing import Annotated

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
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.equipment import (
    BrakeSpecSchema,
    EquipmentProfileCreate,
    EquipmentProfileList,
    EquipmentProfileResponse,
    SessionConditionsSchema,
    SessionEquipmentResponse,
    SessionEquipmentSet,
    SuspensionSpecSchema,
    TireSpecSchema,
)
from backend.api.services import equipment_store, session_store

router = APIRouter()


# ---------------------------------------------------------------------------
# Tire search (must be defined before /{session_id} routes)
# ---------------------------------------------------------------------------


@router.get("/tires/search")
async def search_tires(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    q: str = "",
) -> list[TireSpecSchema]:
    """Search curated tire database. Returns matching tires."""
    from cataclysm.tire_db import search_curated_tires

    if not q or len(q) < 2:
        return []

    curated = search_curated_tires(q)
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
    return TireSpec(
        model=s.model,
        compound_category=TireCompoundCategory(s.compound_category),
        size=s.size,
        treadwear_rating=s.treadwear_rating,
        estimated_mu=s.estimated_mu,
        mu_source=MuSource(s.mu_source),
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


def _profile_to_response(p: EquipmentProfile) -> EquipmentProfileResponse:
    """Convert a domain EquipmentProfile to the API response schema."""
    return EquipmentProfileResponse(
        id=p.id,
        name=p.name,
        tires=_tire_to_schema(p.tires),
        brakes=_brakes_to_schema(p.brakes) if p.brakes else None,
        suspension=_suspension_to_schema(p.suspension) if p.suspension else None,
        notes=p.notes,
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
        brakes=_schema_to_brakes(body.brakes) if body.brakes else None,
        suspension=_schema_to_suspension(body.suspension) if body.suspension else None,
        notes=body.notes,
    )
    equipment_store.store_profile(profile)
    await equipment_store.db_persist_profile(profile, user_id=current_user.user_id)
    return _profile_to_response(profile)


@router.get("/profiles", response_model=EquipmentProfileList)
async def list_profiles(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> EquipmentProfileList:
    """List all equipment profiles."""
    profiles = equipment_store.list_profiles()
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

    updated = EquipmentProfile(
        id=profile_id,
        name=body.name,
        tires=_schema_to_tire(body.tires),
        brakes=_schema_to_brakes(body.brakes) if body.brakes else None,
        suspension=_schema_to_suspension(body.suspension) if body.suspension else None,
        notes=body.notes,
    )
    equipment_store.store_profile(updated)
    await equipment_store.db_persist_profile(updated, user_id=current_user.user_id)
    return _profile_to_response(updated)


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, str]:
    """Delete an equipment profile."""
    deleted = equipment_store.delete_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
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
) -> SessionEquipmentResponse:
    """Assign an equipment profile to a session."""
    # Validate session exists
    sd = session_store.get_session(session_id)
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
    await equipment_store.db_persist_session_equipment(se)

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


@router.get("/{session_id}/equipment", response_model=SessionEquipmentResponse)
async def get_session_equipment(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> SessionEquipmentResponse:
    """Get the effective equipment assignment for a session."""
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

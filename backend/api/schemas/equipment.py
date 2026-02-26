"""Pydantic schemas for equipment profile and session-equipment endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TireSpecSchema(BaseModel):
    """Tire specification for an equipment profile."""

    model: str
    compound_category: str
    size: str
    treadwear_rating: int | None = None
    estimated_mu: float
    mu_source: str
    mu_confidence: str
    pressure_psi: float | None = None
    brand: str | None = None
    age_sessions: int | None = None


class BrakeSpecSchema(BaseModel):
    """Brake specification for an equipment profile."""

    compound: str | None = None
    rotor_type: str | None = None
    pad_temp_range: str | None = None
    fluid_type: str | None = None


class SuspensionSpecSchema(BaseModel):
    """Suspension specification for an equipment profile."""

    type: str | None = None
    front_spring_rate: str | None = None
    rear_spring_rate: str | None = None
    front_camber_deg: float | None = None
    rear_camber_deg: float | None = None
    front_toe: str | None = None
    rear_toe: str | None = None
    front_rebound: int | None = None
    front_compression: int | None = None
    rear_rebound: int | None = None
    rear_compression: int | None = None
    sway_bar_front: str | None = None
    sway_bar_rear: str | None = None


class EquipmentProfileCreate(BaseModel):
    """Request body for creating an equipment profile."""

    name: str = Field(..., min_length=1, max_length=100)
    tires: TireSpecSchema
    brakes: BrakeSpecSchema | None = None
    suspension: SuspensionSpecSchema | None = None
    notes: str | None = None


class EquipmentProfileResponse(BaseModel):
    """Equipment profile returned from the API."""

    id: str
    name: str
    tires: TireSpecSchema
    brakes: BrakeSpecSchema | None = None
    suspension: SuspensionSpecSchema | None = None
    notes: str | None = None


class EquipmentProfileList(BaseModel):
    """Paginated list of equipment profiles."""

    items: list[EquipmentProfileResponse]
    total: int


class BrakePadSearchResult(BaseModel):
    """Curated brake pad search result."""

    model: str
    brand: str
    category: str
    temp_range: str
    initial_bite: str
    notes: str


class SessionConditionsSchema(BaseModel):
    """Environmental conditions during a session."""

    track_condition: str = "dry"
    ambient_temp_c: float | None = None
    track_temp_c: float | None = None
    humidity_pct: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    precipitation_mm: float | None = None
    weather_source: str | None = None


class SessionEquipmentSet(BaseModel):
    """Request body for assigning equipment to a session."""

    profile_id: str
    overrides: dict[str, object] = Field(default_factory=dict)
    conditions: SessionConditionsSchema | None = None


class SessionEquipmentResponse(BaseModel):
    """Resolved equipment assignment for a session."""

    session_id: str
    profile_id: str
    profile_name: str
    overrides: dict[str, object]
    tires: TireSpecSchema
    brakes: BrakeSpecSchema | None = None
    suspension: SuspensionSpecSchema | None = None
    conditions: SessionConditionsSchema | None = None

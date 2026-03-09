"""Pydantic schemas for equipment profile and session-equipment endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class VehicleSpecSchema(BaseModel):
    """Vehicle specification from the curated vehicle database."""

    make: str
    model: str
    generation: str
    year_range: list[int]  # [start_year, end_year]

    @field_validator("year_range")
    @classmethod
    def validate_year_range(cls, v: list[int]) -> list[int]:
        """Enforce exactly 2 elements in year_range."""
        if len(v) != 2:
            msg = "year_range must contain exactly 2 elements [start, end]"
            raise ValueError(msg)
        if v[0] > v[1]:
            msg = "year_range start must be <= end"
            raise ValueError(msg)
        return v

    weight_kg: float
    wheelbase_m: float
    track_width_front_m: float
    track_width_rear_m: float
    cg_height_m: float
    weight_dist_front_pct: float
    drivetrain: str  # "RWD" | "FWD" | "AWD"
    hp: int
    torque_nm: int
    has_aero: bool
    stock_tire_size_front: str | None = None
    stock_tire_size_rear: str | None = None
    notes: str | None = None


class VehicleSearchResult(BaseModel):
    """Lightweight vehicle search result for autocomplete/dropdowns."""

    slug: str
    make: str
    model: str
    generation: str
    year_range: list[int]
    hp: int
    weight_kg: float
    drivetrain: str


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


_VALID_VEHICLE_OVERRIDE_KEYS = frozenset(
    {
        "weight_kg",
        "cg_height_m",
        "weight_dist_front_pct",
        "hp",
        "torque_nm",
    }
)


class EquipmentProfileCreate(BaseModel):
    """Request body for creating an equipment profile."""

    name: str = Field(..., min_length=1, max_length=100)
    tires: TireSpecSchema
    vehicle: VehicleSpecSchema | None = None
    brakes: BrakeSpecSchema | None = None
    suspension: SuspensionSpecSchema | None = None
    vehicle_overrides: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None
    is_default: bool = False

    @field_validator("vehicle_overrides")
    @classmethod
    def validate_override_keys(cls, v: dict[str, float]) -> dict[str, float]:
        """Only allow known vehicle override keys."""
        bad = set(v) - _VALID_VEHICLE_OVERRIDE_KEYS
        if bad:
            allowed = sorted(_VALID_VEHICLE_OVERRIDE_KEYS)
            msg = f"Invalid vehicle_overrides keys: {sorted(bad)}. Allowed: {allowed}"
            raise ValueError(msg)
        return v


class EquipmentProfileResponse(BaseModel):
    """Equipment profile returned from the API."""

    id: str
    name: str
    tires: TireSpecSchema
    vehicle: VehicleSpecSchema | None = None
    brakes: BrakeSpecSchema | None = None
    suspension: SuspensionSpecSchema | None = None
    vehicle_overrides: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None
    is_default: bool = False


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


class InlineEquipmentSet(BaseModel):
    """Request body for assigning equipment inline (no named profile required).

    Used by anonymous users during the post-upload interstitial.  On session
    claim the ephemeral profile is promoted to a persistent one.
    """

    compound_category: str
    tire_size: str = Field(..., min_length=3, max_length=30)
    estimated_mu: float | None = None


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

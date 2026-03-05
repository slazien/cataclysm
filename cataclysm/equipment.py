"""Equipment tracking data model for tires, brakes, and suspension.

Defines dataclasses and enums for recording the equipment configuration
used during each track session.  This enables grip-aware coaching and
session-over-session comparisons that account for equipment changes.

The tire grip estimate uses the HPWizard formula:
    mu = 2.25 / TW^0.15
where TW is the UTQG treadwear rating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cataclysm.vehicle_db import VehicleSpec
    from cataclysm.velocity_profile import VehicleParams

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TireCompoundCategory(StrEnum):
    """Broad tire compound categories ordered by increasing grip potential."""

    STREET = "street"
    ENDURANCE_200TW = "endurance_200tw"
    SUPER_200TW = "super_200tw"
    TW_100 = "100tw"
    R_COMPOUND = "r_comp"
    SLICK = "slick"


class MuSource(StrEnum):
    """How the friction coefficient estimate was obtained."""

    FORMULA_ESTIMATE = "formula_estimate"
    CURATED_TABLE = "curated_table"
    MANUFACTURER_SPEC = "manufacturer_spec"
    USER_OVERRIDE = "user_override"


class TrackCondition(StrEnum):
    """Surface condition at the time of the session."""

    DRY = "dry"
    DAMP = "damp"
    WET = "wet"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORY_MU_DEFAULTS: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 0.85,
    TireCompoundCategory.ENDURANCE_200TW: 1.00,
    TireCompoundCategory.SUPER_200TW: 1.10,
    TireCompoundCategory.TW_100: 1.20,
    TireCompoundCategory.R_COMPOUND: 1.35,
    TireCompoundCategory.SLICK: 1.50,
}

# Drivetrain-limited peak acceleration by compound category.
# Acceleration is drivetrain-limited, not grip-limited, so it doesn't
# scale 1:1 with tire mu.  Higher-grip tires allow slightly more
# traction off corners but the engine/gearing is the primary bottleneck.
_CATEGORY_ACCEL_G: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 0.40,
    TireCompoundCategory.ENDURANCE_200TW: 0.50,
    TireCompoundCategory.SUPER_200TW: 0.55,
    TireCompoundCategory.TW_100: 0.60,
    TireCompoundCategory.R_COMPOUND: 0.65,
    TireCompoundCategory.SLICK: 0.70,
}

CATEGORY_WARMUP_LAPS: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 0.5,
    TireCompoundCategory.ENDURANCE_200TW: 1.0,
    TireCompoundCategory.SUPER_200TW: 1.0,
    TireCompoundCategory.TW_100: 1.0,
    TireCompoundCategory.R_COMPOUND: 1.5,
    TireCompoundCategory.SLICK: 2.5,
}

CATEGORY_LOAD_SENSITIVITY_EXPONENT: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 0.85,
    TireCompoundCategory.ENDURANCE_200TW: 0.82,
    TireCompoundCategory.SUPER_200TW: 0.82,
    TireCompoundCategory.TW_100: 0.80,
    TireCompoundCategory.R_COMPOUND: 0.78,
    TireCompoundCategory.SLICK: 0.75,
}

CATEGORY_FRICTION_CIRCLE_EXPONENT: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 1.8,
    TireCompoundCategory.ENDURANCE_200TW: 2.0,
    TireCompoundCategory.SUPER_200TW: 2.0,
    TireCompoundCategory.TW_100: 2.1,
    TireCompoundCategory.R_COMPOUND: 2.2,
    TireCompoundCategory.SLICK: 2.3,
}

_BRAKE_EFFICIENCY = 0.95  # real-world brake efficiency factor


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def estimate_mu_from_treadwear(treadwear: int) -> float:
    """Estimate tire friction coefficient from UTQG treadwear rating.

    Uses the HPWizard formula: mu = 2.25 / TW^0.15

    Args:
        treadwear: UTQG treadwear rating (e.g., 200, 340).
            Values <= 0 are treated as invalid and return 1.0.

    Returns:
        Estimated peak friction coefficient.
    """
    if treadwear <= 0:
        return 1.0
    return float(2.25 / (treadwear**0.15))


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TireSpec:
    """Specification for the tires used in a session."""

    model: str
    compound_category: TireCompoundCategory
    size: str
    treadwear_rating: int | None
    estimated_mu: float
    mu_source: MuSource
    mu_confidence: str
    pressure_psi: float | None = None
    brand: str | None = None
    age_sessions: int | None = None


@dataclass
class BrakeSpec:
    """Specification for the brake setup used in a session."""

    compound: str | None = None
    rotor_type: str | None = None
    pad_temp_range: str | None = None
    fluid_type: str | None = None


@dataclass
class SuspensionSpec:
    """Specification for the suspension setup used in a session."""

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


@dataclass
class EquipmentProfile:
    """A named equipment configuration that can be reused across sessions."""

    id: str
    name: str
    tires: TireSpec
    vehicle: VehicleSpec | None = None
    brakes: BrakeSpec | None = None
    suspension: SuspensionSpec | None = None
    vehicle_overrides: dict[str, float] = field(default_factory=dict)
    notes: str | None = None


@dataclass
class SessionConditions:
    """Environmental conditions during a session."""

    track_condition: TrackCondition = TrackCondition.DRY
    ambient_temp_c: float | None = None
    track_temp_c: float | None = None
    humidity_pct: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    precipitation_mm: float | None = None
    weather_source: str | None = None


@dataclass
class SessionEquipment:
    """Links an equipment profile to a specific session with optional overrides."""

    session_id: str
    profile_id: str
    overrides: dict[str, object] = field(default_factory=dict)
    conditions: SessionConditions | None = None


# ---------------------------------------------------------------------------
# Vehicle params mapping
# ---------------------------------------------------------------------------


def equipment_to_vehicle_params(profile: EquipmentProfile) -> VehicleParams:
    """Convert an equipment profile to physics solver vehicle parameters.

    Mapping:
    - ``mu`` and ``max_lateral_g`` come directly from the tire's estimated_mu
      (lateral grip scales linearly with tire friction).
    - ``max_accel_g`` is looked up from a per-category table since acceleration
      is drivetrain-limited, not purely grip-limited.  When a vehicle spec is
      attached, we refine max_accel_g based on power-to-weight ratio.
    - ``max_decel_g`` is mu scaled by a brake efficiency factor (0.95) to
      account for real-world brake system losses.
    - ``top_speed_mps`` is fixed at 80 m/s (~179 mph).

    Vehicle overrides (``vehicle_overrides``) can fine-tune the weight
    (key ``"weight_kg"``) to account for driver weight, roll cage, etc.
    """
    from cataclysm.velocity_profile import VehicleParams

    mu = profile.tires.estimated_mu
    category = profile.tires.compound_category
    base_accel_g = _CATEGORY_ACCEL_G[category]

    # Refine acceleration estimate when vehicle specs are available.
    # Higher power-to-weight ratio cars can accelerate harder.
    # We scale the base category accel by a factor derived from hp/weight.
    accel_g = base_accel_g
    if profile.vehicle is not None:
        weight_kg = profile.vehicle.weight_kg
        # Apply user weight override if provided
        if "weight_kg" in profile.vehicle_overrides:
            weight_kg = profile.vehicle_overrides["weight_kg"]
        hp = profile.vehicle.hp
        # Power-to-weight ratio scaling: reference is ~250 hp/tonne
        # (typical track-day car).  Scale proportionally but cap the bonus
        # to avoid unrealistic values.
        pw_ratio = hp / (weight_kg / 1000.0)  # hp per tonne
        pw_factor = min(pw_ratio / 250.0, 1.5)  # cap at 1.5x
        accel_g = base_accel_g * max(pw_factor, 0.7)  # floor at 0.7x

    return VehicleParams(
        mu=mu,
        max_lateral_g=mu,
        max_accel_g=accel_g,
        max_decel_g=mu * _BRAKE_EFFICIENCY,
        top_speed_mps=80.0,
        friction_circle_exponent=CATEGORY_FRICTION_CIRCLE_EXPONENT[category],
    )

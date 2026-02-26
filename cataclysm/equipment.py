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
    brakes: BrakeSpec | None = None
    suspension: SuspensionSpec | None = None
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

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
    TireCompoundCategory.R_COMPOUND: 1.28,
    TireCompoundCategory.SLICK: 1.42,
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

# Peak slip angle by compound — tires generate lateral force at a slip angle,
# which creates an induced drag: F_drag = F_lateral * sin(alpha).  Higher-grip
# compounds operate at larger slip angles → more cornering drag.
# Values from Paradigm Shift Racing, Pacejka, and GRM R-comp tire tests.
CATEGORY_PEAK_SLIP_ANGLE_DEG: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 3.0,
    TireCompoundCategory.ENDURANCE_200TW: 4.0,
    TireCompoundCategory.SUPER_200TW: 5.0,
    TireCompoundCategory.TW_100: 7.0,
    TireCompoundCategory.R_COMPOUND: 8.5,
    TireCompoundCategory.SLICK: 10.0,
}

# Braking-to-lateral mu ratio — tread pattern alignment is the largest contributor
# to longitudinal/lateral asymmetry (~5-8%). Less tread = more isotropic.
# Street tires (deep directional tread) have the highest ratio; slicks (no tread)
# are nearly isotropic with only contact-patch and belt effects remaining.
CATEGORY_BRAKING_MU_RATIO: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 1.10,
    TireCompoundCategory.ENDURANCE_200TW: 1.09,
    TireCompoundCategory.SUPER_200TW: 1.07,
    TireCompoundCategory.TW_100: 1.06,
    TireCompoundCategory.R_COMPOUND: 1.04,
    TireCompoundCategory.SLICK: 1.03,
}

# Grip utilization factor — accounts for the gap between laboratory peak mu and
# achievable track-average mu.  Higher-grip compounds have narrower thermal
# windows, steeper slip-angle peaks, and faster transient force build-up, so
# a smaller fraction of peak mu is realised over an entire lap.
# Derived from ChassisSim grip-factor literature (0.85–0.95 for club racing),
# GG-diagram utilisation studies, and calibration against our 33-entry dataset.
CATEGORY_GRIP_UTILIZATION: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 1.00,
    TireCompoundCategory.ENDURANCE_200TW: 1.00,
    TireCompoundCategory.SUPER_200TW: 0.99,
    TireCompoundCategory.TW_100: 0.97,
    TireCompoundCategory.R_COMPOUND: 0.94,
    TireCompoundCategory.SLICK: 0.93,
}

# Thermal penalty — high-grip compounds generate more slip-work heat per corner,
# pushing the tire above its optimal thermal window more frequently within a lap.
# Street tires rarely overheat at typical track speeds; R-compound and slicks
# experience measurable grip fade from the first hard sector onward.
# Values from Prisma Electronics and MDPI 2019 FSAE thermal validation.
CATEGORY_THERMAL_PENALTY: dict[TireCompoundCategory, float] = {
    TireCompoundCategory.STREET: 1.00,
    TireCompoundCategory.ENDURANCE_200TW: 1.00,
    TireCompoundCategory.SUPER_200TW: 1.00,
    TireCompoundCategory.TW_100: 0.99,
    TireCompoundCategory.R_COMPOUND: 0.97,
    TireCompoundCategory.SLICK: 0.97,
}

_BRAKE_EFFICIENCY = 0.95  # real-world brake efficiency factor
_AIR_DENSITY = 1.225  # kg/m^3, sea level ISA standard atmosphere
_DRIVETRAIN_EFFICIENCY: dict[str, float] = {"RWD": 0.85, "FWD": 0.82, "AWD": 0.80}
# Real-world aero is less than theoretical: ride height variation under load,
# yaw angle in corners, turbulence, and imperfect sealing reduce effective CL.
# Racing engineering literature suggests 70-85% of wind-tunnel CL on track.
_AERO_EFFICIENCY = 0.85


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
    is_default: bool = False


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
    surface_water_mm: float | None = None
    weather_source: str | None = None
    weather_confidence: float | None = None
    dew_point_c: float | None = None
    timezone_name: str | None = None
    track_condition_is_manual: bool = False


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

    mu_raw = profile.tires.estimated_mu
    category = profile.tires.compound_category
    grip_util = CATEGORY_GRIP_UTILIZATION.get(category, 0.96)
    thermal = CATEGORY_THERMAL_PENALTY.get(category, 1.00)
    mu = mu_raw * grip_util * thermal
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

    # Compute aerodynamic drag coefficient: k = CdA * rho / (2 * m)
    # Used in solver: drag_g = k * v^2 / G
    drag_coeff = 0.0
    if profile.vehicle is not None and profile.vehicle.cd_a > 0:
        drag_coeff = profile.vehicle.cd_a * _AIR_DENSITY / (2.0 * weight_kg)

    # Compute wheel power for power-limited acceleration model
    wheel_power_w = 0.0
    mass_for_params = 0.0
    if profile.vehicle is not None:
        dt_eff = _DRIVETRAIN_EFFICIENCY.get(profile.vehicle.drivetrain, 0.85)
        wheel_power_w = profile.vehicle.hp * 745.7 * dt_eff
        mass_for_params = weight_kg

    # Compute aero downforce coefficient: k = 0.5 * rho * CL_A / (m * G)
    # Used in solver: mu_effective = mu + k * v^2
    from cataclysm.velocity_profile import G

    aero_coeff = 0.0
    if profile.vehicle is not None and profile.vehicle.cl_a > 0 and mass_for_params > 0:
        aero_coeff = (
            0.5 * _AIR_DENSITY * profile.vehicle.cl_a * _AERO_EFFICIENCY / (mass_for_params * G)
        )

    braking_ratio = CATEGORY_BRAKING_MU_RATIO.get(category, 1.10)
    import math

    slip_angle_deg = CATEGORY_PEAK_SLIP_ANGLE_DEG.get(category, 6.0)
    cornering_drag = math.sin(math.radians(slip_angle_deg))

    return VehicleParams(
        mu=mu,
        max_lateral_g=mu,
        max_accel_g=accel_g,
        max_decel_g=mu * braking_ratio * _BRAKE_EFFICIENCY,
        braking_mu_ratio=braking_ratio,
        top_speed_mps=80.0,
        friction_circle_exponent=CATEGORY_FRICTION_CIRCLE_EXPONENT[category],
        aero_coefficient=aero_coeff,
        drag_coefficient=drag_coeff,
        load_sensitivity_exponent=CATEGORY_LOAD_SENSITIVITY_EXPONENT[category],
        cg_height_m=profile.vehicle.cg_height_m if profile.vehicle is not None else 0.0,
        track_width_m=(
            0.5 * (profile.vehicle.track_width_front_m + profile.vehicle.track_width_rear_m)
            if profile.vehicle is not None
            else 0.0
        ),
        wheel_power_w=wheel_power_w,
        mass_kg=mass_for_params,
        cornering_drag_factor=cornering_drag,
    )

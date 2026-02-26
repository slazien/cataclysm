# Equipment Tracking & Session Conditions Design

## Problem

Lap time comparisons are misleading when equipment changes between sessions. Example: January Barber sessions on Bridgestone RE-71RS vs February on Hankook RS4 — different tires invalidate direct comparisons. The physics-optimal profile also assumes fixed grip, producing incorrect targets when equipment differs.

## Goals

1. Track equipment per session (tires, brake pads, suspension) with named profiles and per-session overrides
2. Filter/compare sessions by equipment for apples-to-apples analysis
3. Feed real tire grip values into the velocity solver so optimal profiles match the actual car
4. Auto-populate weather conditions from a free API
5. Clearly indicate whether tire values are estimates or verified data

## Data Model

### EquipmentProfile

Named, reusable configuration assigned to sessions.

```python
class TireCompoundCategory(str, Enum):
    STREET = "street"              # 300+ TW, all-season/summer
    ENDURANCE_200TW = "endurance_200tw"  # 200 TW, durable (e.g., RS4, RT660)
    SUPER_200TW = "super_200tw"    # 200 TW, grippy (e.g., RE-71RS, AD09)
    TW_100 = "100tw"               # 100 TW (e.g., Rival S, A052)
    R_COMPOUND = "r_comp"          # R-compound / DOT slick (e.g., Hoosier R7)
    SLICK = "slick"                # Full slick (race only)

class MuSource(str, Enum):
    FORMULA_ESTIMATE = "formula_estimate"    # HPWizard UTQG formula
    CURATED_TABLE = "curated_table"          # Community/editorial values
    MANUFACTURER_SPEC = "manufacturer_spec"  # From manufacturer datasheets
    USER_OVERRIDE = "user_override"          # User manually set this value

@dataclass
class TireSpec:
    # Essential (always visible)
    model: str                          # e.g., "Bridgestone Potenza RE-71RS"
    compound_category: TireCompoundCategory
    size: str                           # e.g., "255/40R17"
    treadwear_rating: int | None        # UTQG TW (e.g., 200)

    # Physics
    estimated_mu: float                 # grip coefficient used by solver
    mu_source: MuSource                 # where the value came from
    mu_confidence: str                  # human-readable note

    # Advanced (expandable)
    pressure_psi: float | None          # hot target pressure
    brand: str | None
    age_sessions: int | None            # approximate session count on this set

@dataclass
class BrakeSpec:
    # Essential
    compound: str | None                # e.g., "Hawk DTC-60", "Ferodo DS2500"
    rotor_type: str | None              # e.g., "OEM", "slotted", "2-piece"

    # Advanced
    pad_temp_range: str | None          # e.g., "200-650C"
    fluid_type: str | None              # e.g., "Motul RBF 660"

@dataclass
class SuspensionSpec:
    # Essential
    type: str | None                    # e.g., "coilover", "stock + springs"
    front_spring_rate: str | None       # e.g., "10kg/mm"
    rear_spring_rate: str | None

    # Advanced
    front_camber_deg: float | None
    rear_camber_deg: float | None
    front_toe: str | None
    rear_toe: str | None
    front_rebound: int | None           # clicks
    front_compression: int | None
    rear_rebound: int | None
    rear_compression: int | None
    sway_bar_front: str | None
    sway_bar_rear: str | None

@dataclass
class EquipmentProfile:
    id: str
    name: str                           # e.g., "Track Day - RE-71RS"
    tires: TireSpec
    brakes: BrakeSpec | None
    suspension: SuspensionSpec | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
```

### SessionConditions

Per-session weather and track conditions, auto-populated from weather API with user override.

```python
class TrackCondition(str, Enum):
    DRY = "dry"
    DAMP = "damp"
    WET = "wet"

@dataclass
class SessionConditions:
    # Essential
    track_condition: TrackCondition
    ambient_temp_c: float | None

    # Optional (auto-populated from weather API)
    track_temp_c: float | None
    humidity_pct: float | None
    wind_speed_kmh: float | None
    wind_direction_deg: float | None
    precipitation_mm: float | None
    weather_source: str | None          # "open-meteo" or "user"
```

### Per-Session Equipment Override

Sessions inherit from their assigned EquipmentProfile but any field can be overridden (e.g., tire pressure changed between sessions).

```python
@dataclass
class SessionEquipment:
    session_id: str
    profile_id: str                     # base profile
    overrides: dict[str, Any]           # field path -> overridden value
    conditions: SessionConditions | None
```

Effective equipment = profile values with overrides applied on top. Original profile values preserved for "reset to default."

## Tire Compound Defaults

Category-level defaults for physics solver when no specific tire data available:

| Category | Default mu | Typical TW | Source |
|----------|-----------|------------|--------|
| street | 0.85 | 400-600 | Conservative estimate |
| endurance_200tw | 1.00 | 200 | Track test aggregates |
| super_200tw | 1.10 | 200 | Track test aggregates |
| 100tw | 1.20 | 100 | Track test aggregates |
| r_comp | 1.35 | 40-100 | Track test aggregates |
| slick | 1.50 | N/A | Race data |

These are starting points. The curated tire table and user overrides refine them.

## Physics Integration

Equipment maps to `VehicleParams` for the velocity solver:

```python
def equipment_to_vehicle_params(profile: EquipmentProfile) -> VehicleParams:
    mu = profile.tires.estimated_mu
    # Category determines max_lateral_g and max_decel_g scaling
    category = profile.tires.compound_category
    return VehicleParams(
        mu=mu,
        max_lateral_g=mu,           # lateral grip scales with tire mu
        max_accel_g=...,            # from category defaults
        max_decel_g=...,            # from brake compound + tire mu
    )
```

Brake compound influences `max_decel_g` — street pads fade at track temps, race pads maintain grip. Category defaults provided; user can override.

## Tire Value Source Tracking

Every tire's grip coefficient displays its provenance:

| MuSource | Badge | Color | Meaning |
|----------|-------|-------|---------|
| FORMULA_ESTIMATE | "Est." | Orange | From UTQG treadwear via HPWizard formula |
| CURATED_TABLE | "Curated" | Blue | Community/editorial data from testing |
| MANUFACTURER_SPEC | "Verified" | Green | From manufacturer datasheets |
| USER_OVERRIDE | "Custom" | Purple | User manually set this value |

Formula used for estimates: `mu = 2.25 / TW^0.15` (HPWizard approximation from UTQG treadwear rating).

## Tire Search Flow

1. User types tire name → autocomplete searches curated table first
2. If not found → query NHTSA UTQG API (`data.transportation.gov`, Socrata dataset `rfqx-2vcg`) by manufacturer + model → get treadwear rating
3. Apply formula → store as `mu_source = FORMULA_ESTIMATE`
4. User can override → `mu_source = USER_OVERRIDE`, original value preserved

## Weather Auto-Populate

- Open-Meteo forecast API (free, no API key) for sessions within last 7 days
- Open-Meteo historical API for older sessions
- Query by track GPS coordinates + session date/time
- Auto-fill: ambient temp, humidity, wind speed, precipitation
- User can override any auto-populated value

## API Endpoints

```
# Equipment profiles
GET    /api/equipment/profiles          # list user's profiles
POST   /api/equipment/profiles          # create profile
PATCH  /api/equipment/profiles/{id}     # update profile
DELETE /api/equipment/profiles/{id}     # delete profile

# Tire lookup
GET    /api/equipment/tires/search?q=   # autocomplete (curated + UTQG)
GET    /api/equipment/tires/{id}/specs  # specs + mu + source badge

# Session conditions & overrides
GET    /api/sessions/{id}/conditions    # get conditions
PUT    /api/sessions/{id}/conditions    # set/override conditions
PUT    /api/sessions/{id}/equipment     # set/override equipment
GET    /api/sessions/{id}/equipment     # effective equipment (profile + overrides)

# Weather
POST   /api/weather/lookup             # {lat, lon, datetime} -> conditions
```

## Frontend UX

**Equipment profile management** (settings/modal page):
- "My Setups" list with named profiles
- Tiered form: essential fields visible, advanced expandable
- Each tire value shows source badge (Est./Curated/Verified/Custom)

**Session association:**
- Session detail page gains "Equipment" section
- Default: inherits from profile assigned to that day
- Override button per field (e.g., tire pressure for one session only)
- Overridden fields highlighted with "Override" badge

**Filtering & comparison:**
- Session list gains filter chips: "Tire: RE-71RS", "Compound: 200TW"
- Compare view warns about equipment mismatches
- Sort by equipment similarity

## Phased Rollout

| Phase | Scope | Depends on |
|-------|-------|------------|
| A | Equipment profiles + session association + filtering | DB schema |
| B | Tire lookup (curated table + UTQG API) + source badges | Phase A |
| C | Weather auto-populate (Open-Meteo) | Phase A |
| D | Physics integration (equipment -> VehicleParams -> optimal profile) | Phase B |
| E | Coaching context (pass equipment + conditions to Claude prompt) | Phase D |

Phase A is the MVP. Each subsequent phase adds automation and intelligence.

# Garage & Vehicle Profiles Plan

## Problem Statement

The velocity profile solver needs accurate vehicle physics parameters (weight, power, CG height, track width, CdA, tire grip) to produce realistic optimal lap times. Currently:

1. **No vehicle attached = bad predictions**: Without a vehicle, the solver uses flat 0.5G accel, no power model, no aero drag. User's Barber session shows 1:45 optimal vs 1:46 actual (unrealistically close).
2. **47 curated vehicles exist** in `vehicle_db.py` but require manual lookup. No stock tire mapping.
3. **Equipment profile UX is buried**: Settings gear icon > "Equipment" dropdown. Abstract naming, no visual identity.
4. **Tire grip estimation is formula-only**: HPWizard `mu = 2.25 / TW^0.15` with no real-world validation data per tire model.

## Goals

- Pre-built stock vehicle profiles for popular track cars (stock tires auto-populated)
- User-overridable parameters (HP, weight, tire choice)
- Expanded tire database with better grip data sources
- "Garage" UX concept replacing the current Equipment Profile abstraction
- Minimal additional infrastructure (leverage existing equipment system)

## Research Findings

### Vehicle Data Sources (ranked by usefulness)

| Source | Fields | Coverage | Cost | Verdict |
|--------|--------|----------|------|---------|
| **ilyasozkurt/automobile-models-and-specs** (GitHub) | Weight, HP, track width F/R, wheelbase, Cd, OEM tire size | 30K+ variants, 124 makes | Free (scraped from autoevolution) | Best single dataset for physics params |
| **Canadian Vehicle Specifications (CVS)** | Track widths F/R, wheelbase, dimensions | 2011-2023, govt-measured | Free, public domain | Best supplementary source for track width |
| **NHTSA vPIC API** | VIN decode, HP, displacement, drivetrain | All US vehicles | Free, no key | Good for VIN lookup, but weight/track width rarely populated |
| **EPA FuelEconomy.gov** | Displacement, cylinders, fuel type | 1984-2026 | Free | No HP, no weight -- fuel economy only |
| **CarQuery API** | HP, weight, torque, dimensions | Global | $75-95 DB download | Good coverage but paid |
| **Wheel-Size.com API** | OEM tire/wheel fitment | 2M+ configs | 5K free req/day | Best for stock tire lookup |

**Decision**: Continue curating `vehicle_db.py` manually for the top 60-80 HPDE cars (physics accuracy matters more than breadth). Use ilyasozkurt dataset as a cross-reference for validation. Consider Wheel-Size.com API for stock tire auto-fill in the future.

### Tire Grip Data Sources

| Method | Accuracy | Data Available |
|--------|----------|----------------|
| **HPWizard formula** (`mu = 2.25 / TW^0.15`) | +/- 10% | Any tire with a treadwear rating |
| **UTQG Traction Grade** (AA/A/B/C) | Wet braking only | 2,400+ tire lines on data.transportation.gov |
| **Curated mu values** (our tire_db.py) | Best -- based on published test data | 10 tires currently |
| **Pacejka parameters** | Gold standard | Proprietary, not publicly available |
| **Load sensitivity coefficient** | ~0.89 for passenger tires | Generic, not per-tire |

**Decision**: Expand curated tire_db.py with real-world data from Tire Rack tests, GRM articles, and manufacturer specs. Add `utqg_traction_grade` field. Use HPWizard formula only as fallback for unknown tires. Add category-based load sensitivity defaults.

### Competing App Approaches

| App | Car DB | Setup Friction | Philosophy |
|-----|--------|----------------|------------|
| RaceChrono | None | High (all manual) | Power user, full control |
| Harry's Lap Timer | Edmunds + crowdsource | Medium | Database-assisted |
| TrackAddict | VIN decoder only | Low | OBD does the work |
| Garmin Catalyst | Make/model/year fields | Low | Self-calibrating |
| APEX Pro | None needed | Zero | AI learns from driving |

**Decision**: Adopt "stock-then-override" pattern (like MOTORMIA). Auto-populate everything from database, let users override individual fields. Show stock values as reference with delta indicators.

### Most Popular HPDE Cars (priority order)

**Tier 1** (ubiquitous): Miata (NA/NB/NC/ND), BMW M3/M4, Corvette (C5-C8), Mustang GT, Porsche 911/Cayman
**Tier 2** (very common): GR86/BRZ, Civic Type R, 370Z/Z, S2000, Elantra N/Veloster N
**Tier 3** (common): WRX STI, Focus RS, Camaro SS/ZL1, GR Supra, GR Corolla, Lotus Elise/Exige

Current `vehicle_db.py` already covers most of these (47 vehicles). Gaps to fill identified below.

## Architecture

### Current Equipment System (what exists)

```
EquipmentProfile (JSON, persisted per-user)
  -> TireSpec (brand, model, width_mm, aspect_ratio, category, mu)
  -> VehicleSpec (from vehicle_db.py: weight, HP, CG, track width, CdA, drivetrain)
  -> BrakeSpec (optional: pad compound)
  -> equipment_to_vehicle_params() -> VehicleParams (for velocity solver)
```

Backend: Full CRUD API at `/api/sessions/equipment/*`
Frontend: `EquipmentModal.tsx`, `EquipmentSelector.tsx`, `EquipmentBadge.tsx`

### Proposed Changes

The existing equipment system is well-designed. Changes are evolutionary, not revolutionary:

1. **Add stock tire mapping** to `VehicleSpec` (new field: `stock_tire_slug`)
2. **Expand tire database** with more tires and better mu data
3. **Add "Popular Cars" quick-select** to vehicle selection UX
4. **Rename "Equipment" to "Garage"** in the UI (backend names stay)
5. **Auto-populate tire when vehicle selected** (if stock tire is in tire_db)
6. **Show stock-vs-current deltas** for overridden parameters

## Implementation Plan

### Wave 1: Data Foundation (backend only, no frontend changes)

**1a. Add stock tire mapping to VehicleSpec**
- File: `cataclysm/vehicle_db.py`
- Add `stock_tire_slug: str | None = None` to `VehicleSpec` dataclass
- Map each vehicle to its stock tire in `VEHICLE_DATABASE`
- Example: `"toyota_gr86_zn8"` -> `stock_tire_slug="michelin_primacy_hp"` (OEM 215/40R18)

**1b. Expand tire database**
- File: `cataclysm/tire_db.py`
- Add 15-20 more popular track tires with curated mu values
- New tires to add (with mu from published test data):
  - Bridgestone RE-71RS (mu~1.15, super_200tw)
  - Yokohama AD09 (mu~1.10, super_200tw)
  - Continental ExtremeContact Sport 02 (mu~1.05, endurance_200tw)
  - Michelin Pilot Sport 4S (mu~1.05, street)
  - Michelin Pilot Sport Cup 2 (mu~1.20, 100tw)
  - Toyo R888R (mu~1.25, 100tw)
  - Yokohama A052 (mu~1.20, 100tw)
  - Nankang AR-1 (mu~1.18, 100tw)
  - Hoosier R7 (mu~1.40, r_comp)
  - BFGoodrich R1S (mu~1.35, r_comp)
  - Toyo RR (mu~1.38, r_comp)
  - Federal 595 RS-RR (mu~1.05, endurance_200tw)
  - Firestone Firehawk Indy 500 (mu~0.98, street)
  - Goodyear Eagle F1 Asymmetric 6 (mu~1.00, street)
  - Kumho Ecsta V730 (mu~1.12, super_200tw)
- Add `utqg_traction_grade: str | None` field to `TireSpec` (AA/A/B/C)
- Add `utqg_treadwear: int | None` field (actual UTQG rating)

**1c. Add stock OEM tires to tire_db**
- Common OEM tires that come stock on track cars:
  - Michelin Primacy HP (GR86/BRZ stock)
  - Bridgestone Potenza S001 (various)
  - Dunlop Sport Maxx RT2 (BMW M cars)
  - Pirelli P Zero (Porsche, Ferrari)
  - Continental ContiSportContact 5P (various)
  - Goodyear Eagle F1 SuperSport (Corvette C8)

**1d. Fill vehicle_db gaps**
- Add missing popular HPDE cars:
  - Porsche 718 Cayman (982) -- base and S/GTS
  - Porsche 911 992 -- Carrera and GT3
  - Honda Civic Type R FK8
  - Honda S2000 AP1/AP2
  - BMW M2 G87
  - Chevrolet Camaro SS (6th gen)
  - Subaru WRX STI (VA)
  - Dodge Challenger SRT (LC)

**1e. Add CG height estimation fallback**
- File: `cataclysm/vehicle_db.py`
- For vehicles without measured CG: use NHTSA LVIPD regression
  `cg_height_m = 0.00018 * curb_weight_kg + 0.34338`
- Add vehicle-class adjustments: sports car -0.05m, SUV +0.10m
- Only as fallback -- keep manually curated values where available

### Wave 2: Auto-populate Logic (backend)

**2a. Stock tire auto-fill on vehicle selection**
- File: `backend/api/routers/equipment.py`
- When user selects a vehicle and has no tire set, auto-populate with stock tire
- Use `VehicleSpec.stock_tire_slug` -> look up in `TIRE_DATABASE`
- Return suggested tire in the equipment profile response

**2b. Equipment profile enrichment endpoint**
- New endpoint: `GET /api/sessions/equipment/suggest?vehicle_slug=toyota_gr86_zn8`
- Returns: suggested tire, all stock specs, overridable fields with defaults
- Used by frontend to show "stock setup" before user customizes

### Wave 3: Frontend "Garage" UX

**3a. Rename Equipment to Garage**
- Update all user-facing strings: "Equipment" -> "Garage" / "My Cars"
- Keep backend route names unchanged (backward compat)
- Update icon from wrench/gear to car silhouette icon
- Files: `EquipmentModal.tsx`, `EquipmentSelector.tsx`, `EquipmentBadge.tsx`, nav labels

**3b. Popular Cars quick-select grid**
- In vehicle selection, show a grid of 8-12 most popular track cars as clickable cards
- Cards show: car silhouette/icon, name, key specs (HP/weight/drivetrain)
- Clicking auto-populates all fields including stock tire
- Covers ~60-70% of users in one tap

**3c. Stock-vs-current delta indicators**
- When a field differs from stock: show "(stock: 228 HP)" in muted text
- Visual badge on the equipment card when anything is overridden
- Similar to existing `MuSource` badge pattern

**3d. Dual-path vehicle selection**
- Keep existing Make > Model > Generation cascading selects
- Add type-ahead search combobox: "BMW M3 E46" matches immediately
- Popular cars grid as a third option above both

### Wave 4: Tire Data Quality (ongoing)

**4a. Cross-reference mu values against published data**
- Tire Rack test results (cornering g-force tests)
- Grassroots Motorsports tire tests
- Manufacturer published skidpad numbers
- Document sources in tire_db.py comments

**4b. Category-based load sensitivity defaults**
- Add to `CATEGORY_LOAD_SENSITIVITY_EXPONENT` table:
  - street: 0.85 (more load sensitive)
  - endurance_200tw: 0.87
  - super_200tw: 0.89
  - 100tw: 0.90
  - r_comp: 0.92 (less load sensitive)
  - slick: 0.93
- These are already wired into `equipment_to_vehicle_params()`

## Testing

- `tests/test_vehicle_db.py` -- stock tire mapping, CG estimation fallback, new vehicles
- `tests/test_tire_db.py` -- new tires, UTQG fields, mu value ranges
- `backend/tests/test_equipment.py` -- auto-fill logic, suggest endpoint
- Existing tests must pass unchanged

## Files Changed

### Wave 1 (data)
- `cataclysm/vehicle_db.py` -- stock_tire_slug field, new vehicles, CG fallback
- `cataclysm/tire_db.py` -- new tires, UTQG fields

### Wave 2 (backend logic)
- `backend/api/routers/equipment.py` -- auto-fill, suggest endpoint
- `backend/api/schemas/equipment.py` -- response schema updates

### Wave 3 (frontend)
- `frontend/src/components/equipment/EquipmentModal.tsx` -- Garage rename, popular cars grid
- `frontend/src/components/equipment/EquipmentSelector.tsx` -- type-ahead search
- `frontend/src/components/equipment/EquipmentBadge.tsx` -- delta indicators
- Various nav/label strings

### Wave 4 (data quality)
- `cataclysm/tire_db.py` -- mu validation, sources
- `cataclysm/equipment.py` -- load sensitivity table updates

## Non-Goals (for now)

- VIN barcode scanning (nice but adds complexity, limited physics value)
- Crowdsourced vehicle data (Harry's Lap Timer model -- too early for our user base)
- External API integration (Wheel-Size.com, CarQuery -- curated data is more accurate)
- Modification tracking (roll cage weight, tune HP deltas -- future feature)
- Multiple car profiles per user (already supported by equipment system)

## Success Criteria

1. User selects "Toyota GR86" from popular cars grid -> all fields auto-populated including stock tire
2. User overrides HP from 228 to 250 -> shows "(stock: 228 HP)" delta
3. Optimal lap time prediction accuracy improves measurably (target: within 3-5% of real achievable times)
4. Setup flow takes <30 seconds for a common track car (vs current multi-minute manual entry)

## Sources

- [NHTSA vPIC API](https://vpic.nhtsa.dot.gov/api/)
- [ilyasozkurt/automobile-models-and-specs](https://github.com/ilyasozkurt/automobile-models-and-specs)
- [Canadian Vehicle Specifications](https://open.canada.ca/data/en/dataset/913f8940-036a-45f2-a5f2-19bde76c1252)
- [NHTSA LVIPD CG Height Analysis](https://kktse.github.io/jekyll/update/2020/10/25/estimating-vehicle-inertia-properties-with-nhtsa-database.html)
- [HPWizard Tire Friction Coefficient](https://hpwizard.com/tire-friction-coefficient.html)
- [NHTSA UTQG Database](https://data.transportation.gov/Automobiles/Uniform-Tire-Quality-Grading-System-UTQGS-Tire-Rat/sku7-utyd)
- [Wheel-Size.com Fitment API](https://developer.wheel-size.com/)
- [Grassroots Motorsports Track Tire Guide](https://grassrootsmotorsports.com/articles/track-tire-buyers-guide/)
- [Garmin Catalyst Car Profile](https://www8.garmin.com/manuals/webhelp/GUID-16C78876-E016-40FD-8A0A-049BA52B462B/EN-US/GUID-D22D07C5-0470-4982-B7D7-FF4614931B86.html)
- [PRI 2024 State of Racing Market Report](https://www.performanceracing.com/magazine/featured/08-05-2024/special-report-2024-state-racing-market-report)

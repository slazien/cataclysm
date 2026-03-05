# Tire-Grip Model Integration Research

> Research conducted 2026-03-05. Investigating how tire compound properties should influence velocity model parameters.

## Current State

Our equipment system (`cataclysm/equipment.py`) already maps tire compound to `VehicleParams`:
- `estimated_mu` (from TireSpec) → `mu`, `max_lateral_g`, `max_decel_g` (via brake efficiency)
- Compound category → `max_accel_g` (from per-category table)
- Vehicle power/weight → accel_g scaling

The grip calibration system (P0, just implemented) overrides these with observed G-G data. So the flow is: **tire database → equipment params → calibration override**.

## What Changes When a User Switches Tires

When a user changes from e.g. 200TW to R-compound:
1. `estimated_mu` changes (1.10 → 1.35)
2. `max_lateral_g` changes accordingly
3. `max_decel_g` changes (mu * 0.95)
4. `max_accel_g` changes (category table lookup)
5. After calibration from G-G data, all values get overridden anyway

**Key insight**: For sessions WITH telemetry, calibration from observed data already captures the tire effect perfectly — the driver's actual G-G envelope IS the grip model. The tire database matters most for:
- **First-time predictions** before any laps are driven
- **"What if" comparisons** (what would my optimal be on stickier tires?)
- **Cross-session normalization** (was I faster because of skill or tires?)

## Feasible Enhancements

### Enhancement 1: Per-Compound Load Sensitivity (FEASIBLE, MEDIUM VALUE)

**Formula** (from DrRacing "No Data" approach):
```
mu(Fz) = a + Fz^b
```
Where `a` = base friction, `b` = load sensitivity exponent (typically -0.1 to -0.3).

**Typical values by compound:**

| Compound | Base mu (a) | Load sensitivity (b) | Notes |
|----------|-------------|---------------------|-------|
| Street (400+ TW) | 0.90 | ~0.85 exponent | Less sensitive |
| 200TW Performance | 1.10 | ~0.82 exponent | Moderate |
| R-Compound (40-100) | 1.35 | ~0.78 exponent | More sensitive |
| Slick | 1.50 | ~0.75 exponent | Most sensitive |

**Power law**: `Fy = mu_ref * Fz^n` where n = 0.7-0.9 for real tires. Softer compounds tend to have HIGHER load sensitivity (lower n), meaning grip drops more per unit of added load. This is because softer rubber deforms more under high contact pressure.

**Implementation**: Add `load_sensitivity_exponent: float` to `TireSpec`, default per category. This already aligns with Task 11 (Tire Load Sensitivity) — just need compound-specific defaults.

### Enhancement 2: Per-Compound Thermal Operating Window (FEASIBLE, LOW-MEDIUM VALUE)

**Typical operating windows:**

| Compound | Cold threshold | Optimal range | Overheat threshold |
|----------|---------------|---------------|-------------------|
| Street | 5C (41F) | 40-80C | 100C |
| 200TW (Endurance) | 15C (60F) | 60-100C | 120C |
| 200TW (Super) | 20C (68F) | 70-110C | 130C |
| R-Compound | 30C (86F) | 80-120C | 140C |
| Slick | 40C (104F) | 90-130C | 150C |

**Problem**: We don't have tire temperature sensors. We only know:
- Ambient temperature (could add to session conditions)
- Lap number (proxy for thermal state)
- Session duration (proxy for heat soak)

**Implementation**: Already partially covered by Task 10 (Tire Thermal Model) which adds a first-lap warmup multiplier. Could be enhanced with compound-specific warmup rates:
- Street tires: warm up in ~0.5 laps
- 200TW: warm up in ~1 lap
- R-compound: warm up in ~1.5-2 laps
- Slick: warm up in ~2-3 laps

### Enhancement 3: Compound-Specific Friction Circle Shape (FEASIBLE, LOW VALUE)

Different compounds have different friction ellipse shapes:
- Street tires: p ≈ 1.8 (more diamond-like, less combined grip)
- Performance 200TW: p ≈ 2.0 (standard ellipse)
- R-compound: p ≈ 2.2 (more square, better combined grip)
- Slick: p ≈ 2.3-2.5 (most square)

**Implementation**: Add `friction_circle_exponent` default per compound category. Currently hardcoded at 2.0 in VehicleParams.

### Enhancement 4: Tire Wear Degradation (NOT FEASIBLE WITHOUT SENSORS)

Without tire temperature or wear sensors, we can't meaningfully model degradation within a session. The `age_sessions` field on TireSpec could provide a rough inter-session degradation model, but the effect is small (2-5% over tire life) and highly tire-dependent.

**Skip for now.**

## Recommendation

### What to implement (add to existing tasks):

1. **Extend Task 11 (Load Sensitivity)**: Add per-compound `load_sensitivity_exponent` to TireSpec and compound category defaults. When Task 11 implements the load-sensitive mu formula, use the compound-specific exponent.

2. **Extend Task 10 (Thermal Model)**: Add per-compound `warmup_laps` to TireSpec/compound category. Softer compounds need more warmup. Use in the warmup factor calculation.

3. **Extend `equipment_to_vehicle_params()`**: Map compound-specific `friction_circle_exponent` default.

These are small additions to existing tasks, not new tasks.

### What NOT to implement:

- Full tire temperature model (no sensors)
- Wear degradation (no data)
- Grassroots Motorsports letter grades (subjective, not numerical)
- Magic Formula fitting (needs tire test data we don't have)

### The data-driven calibration already handles the hard part

The most important insight: **once a driver has even one session on a tire, the G-G calibration (Task 1, already done) automatically captures the tire's actual performance**. The compound-specific defaults are just a better starting point for the FIRST session before calibration kicks in.

## Sources

- [DrRacing "No Data" tire modeling](https://drracing.wordpress.com/2014/12/01/380/) — practical calibration from track data
- [HPWizard tire friction coefficients](https://hpwizard.com/tire-friction-coefficient.html) — treadwear formula: mu = 2.25 / TW^0.15
- [Wikipedia: Tire load sensitivity](https://en.wikipedia.org/wiki/Tire_load_sensitivity) — Fy = mu * Fz^n, n = 0.7-0.9
- [Paradigm Shift Racing: Tire setup science](https://www.paradigmshiftracing.com/racing-basics/car-setup-science-2-tires) — load sensitivity effects
- [Grassroots Motorsports ultimate tire guide](https://grassrootsmotorsports.com/articles/track-tire-buyers-guide/) — subjective grading
- [Raceteq: Tire performance](https://www.raceteq.com/articles/2024/12/how-motorsport-teams-extract-the-maximum-performance-from-tyres) — thermal windows
- [Q&A: R-comp vs 200TW](https://grassrootsmotorsports.com/articles/q-tire-engineer-r-comp-race-tires-vs-200-treadwear/) — compound differences

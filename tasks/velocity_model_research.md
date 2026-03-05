# Velocity Profile Model: State-of-the-Art Research

> Research conducted 2026-03-05. Two-iteration deep dive across 60+ sources.

## Current Model Limitations (Kapania 2016 forward-backward solver)

| # | Limitation | Impact |
|---|-----------|--------|
| 1 | No elevation/gradient | Underestimates speed downhill, overestimates uphill |
| 2 | GPS-derived curvature noise | Tight corners get over-smoothed or spiky curvature |
| 3 | Constant mu (no load sensitivity) | Ignores weight transfer effects on grip |
| 4 | No speed-dependent aero | Misses downforce contribution at high speed |
| 5 | Symmetric friction circle | Real cars brake harder than they accelerate |
| 6 | No banking/camber model | Off-camber and banked turns treated identically |
| 7 | Independent corner metrics | Linked corners (chicanes, esses) evaluated in isolation |

---

## 1. Elevation / Gradient Integration

### The Fix (one equation change per pass)

Add `g*sin(theta)` to the longitudinal force balance. In each solver pass:

```
# Forward pass (acceleration)
net_accel_g = available_accel_g - drag_g - g*sin(theta)/g

# Backward pass (braking)
effective_decel_g = available_decel_g + drag_g + g*sin(theta)/g
```

Uphill (`theta > 0`): reduces acceleration, assists braking.
Downhill (`theta < 0`): assists acceleration, reduces braking distance.

Normal force also changes: `F_N = m*g*cos(theta)`, reducing available grip.
For grades < 10%, `cos(theta) > 0.995` -- small but easy to include.

### Numerical Impact

A 3% grade changes braking distance by ~2.5%. At Barber's steeper sections
or tracks like Laguna Seca (corkscrew ~17% grade), the effect is massive.

### Elevation Data Sources (ranked)

1. **Curated track database** -- bake elevation profile per track (best quality, no per-session noise)
2. **DEM APIs** -- Open Topo Data, Open-Elevation, Open-Meteo (~6-30m accuracy, free)
3. **Multi-session GPS averaging** -- 10+ sessions reduces noise by 3x+
4. **Single-session GPS** -- 0.75-1.5m vertical accuracy (multi-band GNSS) -- too noisy for gradient without heavy smoothing

### Key Papers

- **Lovato & Massaro (2022)** "3D free-trajectory QSS optimal-control" -- extends QSS to 3D with g-g-g diagrams. Vehicle System Dynamics 60(5).
- **Perantoni & Limebeer (2015)** "Optimal Control on a 3D Track" -- full 3D track ribbon model. ASME JDSMC 137(5).
- **Heilmeier et al. (2019)** "QSS Lap Time Sim for Electrified Race Cars" -- includes elevation/banking in QSS.
- **OpenLAP** (Cabrera, GitHub) -- open-source MATLAB solver with inclination and banking channels.

---

## 2. GPS Curvature Quality

### Problem

Curvature is a second derivative of position. GPS noise (~0.5m) gets amplified
severely. Tight corners and chicanes produce unrealistic curvature spikes.

### Solutions (ranked by impact)

| # | Method | Effort | Impact |
|---|--------|--------|--------|
| 1 | **Smoothing spline** fit before curvature | Low | High |
| 2 | **Multi-lap averaging** (DTW alignment) | Medium | High |
| 3 | **Clothoid spline fitting** | Medium-High | High |
| 4 | **Track centerline database** (TUMFTM) | Low | High (limited tracks) |

**Smoothing splines** (Early & Sykulski 2020): Fit a spline to (x,y) in the
distance domain with a physics-based tension parameter (max jerk limit).
Compute curvature analytically from the spline. Avoids double-differentiation
noise entirely.

**Multi-lap averaging**: Re-parameterize all laps by distance, align via DTW
(Dynamic Time Warping), average coordinates, smooth, compute curvature.
10 laps -> 3.2x noise reduction. 50 laps -> 7x.

**Clothoid fitting** (Bertolazzi & Frego 2013): Racing tracks are designed
with clothoid (Euler spiral) transitions. Fitting piecewise clothoids produces
curvature that is piecewise-linear by construction -- physically correct and
smooth. Solves a scalar equation per segment (fast).

**TUMFTM database** (GitHub): Smoothed centerlines + track widths for 20+ F1/DTM
tracks. Direct drop-in for tracks in the database.

---

## 3. Tire Grip Model Improvements

### 3a. Load Sensitivity (Degressive Grip)

Tire mu decreases with increasing vertical load. Simple linear model:

```
mu(Fz) = mu0 + k * Fz    # k ~ -0.05 per kN
```

Or power-law: `mu(Fz) = a + Fz^b` where b < 1 makes it degressive.

Practical calibration: measure max lateral G in a fast corner (high load) and
slow corner (low load), solve for `a` and `b`. (DrRacing "No Data" approach)

### 3b. Data-Driven Grip Calibration (highest impact, lowest effort)

**Instead of modeling grip from first principles, extract it from observed G-G data.**

The G-G diagram's outer boundary IS the grip model. Three levels of sophistication:

**Level 1 -- Three semi-axis values** (replaces single mu):
- `a_lat_max` = 99th percentile |ay| when |ax| < 0.2g
- `a_brake_max` = 99th percentile |ax| when ax < -0.2g, |ay| < 0.2g
- `a_accel_max` = 99th percentile |ax| when ax > 0.2g, |ay| < 0.2g
- Use p=2 elliptical model with asymmetric accel/brake

**Level 2 -- Per-corner mu_effective**:
- For each corner: `mu_eff_i = max_observed_lateral_G_i / g`
- Implicitly captures banking, surface grip variation, driver confidence
- Velocity solver uses corner-specific limits

**Level 3 -- Full GGV surface** (speed-bucketed G-G envelopes):
- Build G-G boundary in ~36 angular sectors per speed bucket (5 m/s bins)
- Use 99th percentile from top-3 laps for robustness
- Solver queries this 3D surface at (speed, heading) for max capability
- Captures power limitation, aero, everything -- from data, not physics

**Key insight**: Professional lap sims (OptimumLap, TUM FSAE) already use GGV
surfaces internally. We're just populating the surface from observed data
instead of from vehicle parameters.

### 3c. HPWizard Empirical Formula

Quick approximation: `mu = 2.25 / TW^0.15` (+-10%), where TW = treadwear rating.

| Tire Class | TW | Approx mu |
|---|---|---|
| All-season | 400-700 | 0.85-0.95 |
| 200TW perf | 200 | ~1.07 |
| R-compound | 40-100 | 1.15-1.30 |
| Slick | N/A | 1.40-1.90 |

### 3d. Thermal Effects (low priority)

Parabolic model: `mu(T) = mu0 * max(1 - k*(T - T_opt)^2, 0.1)`.
For coaching, a first-lap warmup multiplier (0.75 -> 1.0 over lap 1) captures
the dominant effect without tire temp sensors.

---

## 4. Friction Ellipse (not Circle)

### Why It Matters

Real cars have asymmetric acceleration capability:

| Direction | Typical track day car |
|-----------|----------------------|
| Braking | 1.0 - 1.3G (all 4 tires) |
| Lateral | 0.9 - 1.2G |
| Acceleration | 0.4 - 0.8G (power/rear-tire limited) |

Current model uses `friction_circle_exponent = 2.0` with equal `max_accel_g`
and `max_decel_g`, but doesn't capture the full asymmetry.

### Generalized Friction Shape

```
(ax / ax_max)^p + (ay / ay_max)^p <= 1
```

- p=1: diamond (too conservative)
- p=2: ellipse (standard, matches most tire data)
- p>2: rounded square (some race tires)

The p=2 ellipse with separate `max_accel_g`, `max_decel_g`, `max_lateral_g`
is the standard in motorsport engineering.

### Fitting from Data

Simple approach (recommended over full Fitzgibbon ellipse fitting):
Extract three semi-axis values directly from G-G boundary data (see 3b Level 1).

---

## 5. Banking / Camber Effects

### Physics

Banking angle theta increases effective lateral grip:

```
mu_eff = (mu + tan(theta)) / (1 - mu*tan(theta))
```

For small angles: `mu_eff ~ mu + tan(theta)`

| Banking | mu=1.0 -> mu_eff | Impact |
|---------|-----------------|--------|
| 3 deg | 1.056 | +5.6% |
| 5 deg | 1.095 | +9.5% |
| 10 deg | 1.206 | +20.6% |

Off-camber (negative banking) reduces grip by the same mechanism.

### Integration

Store per-corner banking angle in track profile. Apply banking correction
to available lateral G at each track point.

---

## 6. Linked Corner Dynamics

### Key Insight

The forward-backward velocity solver already captures corner coupling
through the continuous curvature profile. The problem is in the
**corner-level metrics**, not the solver.

### Corner Grouping

Two corners are "linked" if the car never reaches steady-state straight-line
speed between them. Detectable from the velocity profile:

```python
# Between corner N exit and corner N+1 entry:
if max_speed_between < 0.95 * v_max_straight:
    corners are linked
```

Simpler heuristic: gap distance < threshold (speed-dependent braking distance).

### Compound Section Metrics

For linked corners, report:
- **Section time** (entry of first corner to exit of last)
- **Section entry/exit speed**
- **Section min speed**
- **Per-corner breakdown within section** (for coaching: "sacrificing T14 entry for T16 exit is correct")

Professional tools (MoTeC i2, Pi Toolbox) treat linked corners as single
analysis sections, not independent corners.

### Curvature Variation Index (Kontaratos 2024)

CVI = variation of curvature within a section. High CVI = complex/chicane.
Useful for auto-classifying corner types (simple arc vs chicane vs esses).

---

## Implementation Priority (recommended order)

| Priority | Feature | Effort | Impact | Why |
|----------|---------|--------|--------|-----|
| **P0** | Data-driven grip (Level 1: 3 semi-axes) | Low | Very High | Replaces constant mu with observed capability. Fixes the "faster than optimal" problem immediately. |
| **P1** | Friction ellipse (asymmetric accel/brake/lat) | Low | High | Current model already has the parameters; just need to extract from data. |
| **P2** | Elevation/gradient | Medium | High | One equation change per pass + elevation data source. |
| **P3** | Smoothing spline curvature | Low | High | Drop-in replacement for current curvature computation. |
| **P4** | Linked corner grouping + section metrics | Medium | Medium | Fixes misleading per-corner metrics for chicanes/esses. |
| **P5** | Per-corner mu calibration (Level 2) | Low | Medium | Captures track surface variation and banking implicitly. |
| **P6** | Banking/camber model | Low | Medium | Simple formula, needs per-corner banking data in track profiles. |
| **P7** | Multi-lap curvature averaging | Medium | Medium | Cumulative improvement to curvature quality over sessions. |
| **P8** | Full GGV surface (Level 3) | Medium | Medium | Speed-bucketed envelopes for power/aero effects. |
| **P9** | Clothoid spline fitting | High | Medium | Physically perfect curvature, but complex implementation. |
| **P10** | Tire thermal model | High | Low | First-lap warmup multiplier is sufficient for now. |
| **P11** | Tire load sensitivity | Medium | Low | Mostly absorbed by data-driven grip calibration. |

---

## Key Academic References

1. Kapania & Gerdes (2016) -- "Sequential Two-Step Algorithm for Vehicle Racing Trajectories" -- our current solver basis
2. Lovato & Massaro (2022) -- "3D free-trajectory QSS optimal-control" -- 3D extension with g-g-g diagrams
3. Perantoni & Limebeer (2015) -- "Optimal Control on a 3D Track" -- full 3D track ribbon model
4. Heilmeier et al. (2019) -- "QSS Lap Time Sim for Electrified Race Cars" -- elevation/banking in QSS
5. Bertolazzi & Frego (2013) -- "Fast G1 fitting of clothoid curves" -- curvature from clothoids
6. Early & Sykulski (2020) -- "Smoothing Noisy GPS Data with Smoothing Splines" -- GPS filtering
7. Kontaratos et al. (2024) -- "Curvature-Based Geometric Difficulty Analysis of F1 Racing Lines"
8. Brach & Brach (2011) -- "The Tire-Force Ellipse and Tire Characteristics" -- SAE 2011-01-0094
9. Brayshaw & Harrison (2005) -- "QSS approach to race car lap simulation"
10. Lenzo & Rossi (2020) -- "Simple Mono-Dimensional Approach for Lap Time Optimisation"

## Key Open-Source References

- [TUMFTM/racetrack-database](https://github.com/TUMFTM/racetrack-database) -- track centerlines
- [TUMFTM/laptime-simulation](https://github.com/TUMFTM/laptime-simulation) -- reference QSS solver
- [TUMFTM/global_racetrajectory_optimization](https://github.com/TUMFTM/global_racetrajectory_optimization)
- [OpenLAP](https://github.com/mc12027/OpenLAP-Lap-Time-Simulator) -- MATLAB solver with elevation
- [Speed Dreams TireTempDeg](https://sourceforge.net/p/speed-dreams/wiki/TireTempDeg/) -- thermal model reference

## Key Practitioner References

- [DrRacing Blog](https://drracing.wordpress.com) -- practical MATLAB lap sim with tire modeling
- [HPWizard](https://hpwizard.com) -- tire friction coefficients, G-G analysis
- [Occam's Racer](https://occamsracers.com) -- aerodynamic coefficients for track day cars
- [Trailbrake](https://trailbrake.com) -- G-G diagram analysis for coaching

# Solver Implementation Audit — 2026-03-08

> Cross-referencing `tasks/velocity_model_research.md` (P0-P11) and both implementation plans against actual codebase.

## Phase 1 Plan (P0-P11 from velocity_model_research.md)

| # | Feature | Status | Evidence |
|---|---------|--------|----------|
| P0 | Data-driven grip (3 semi-axes) | ✅ Done | `grip_calibration.py`: `CalibratedGrip`, `calibrate_grip_from_telemetry()`, `apply_calibration_to_params()` |
| P1 | Friction ellipse (asymmetric accel/brake/lat) | ✅ Done | `velocity_profile.py`: `VehicleParams` has `max_accel_g`, `max_decel_g`, `max_lateral_g`, `friction_circle_exponent` (2.0=ellipse). `_available_accel()` uses exponent. `equipment.py`: `CATEGORY_FRICTION_CIRCLE_EXPONENT` wired per compound. |
| P2 | Elevation/gradient | ✅ Done | `elevation_profile.py`: `compute_gradient_array()`, `compute_vertical_curvature()`. `velocity_profile.py`: `gradient_sin` + `vertical_curvature` params in solver. |
| P3 | Smoothing spline curvature | ✅ Done | `curvature.py`: `compute_curvature()` uses `UnivariateSpline`, `_limit_curvature_rate()`, `MAX_PHYSICAL_CURVATURE=0.33`, `MAX_CURVATURE_RATE=0.02`. |
| P4 | Linked corner grouping | ✅ Done | `linked_corners.py`: `CornerGroup`, `LinkedCornerResult`, `detect_linked_corners()`, `compute_curvature_variation_index()`. `corners.py`: `Corner.linked_group_id`. |
| P5 | Per-corner mu calibration | ✅ Done | `grip_calibration.py`: `calibrate_per_corner_grip()`. `velocity_profile.py`: `mu_array` param in `_compute_max_cornering_speed()`. |
| P6 | Banking/camber model | ✅ Done | `banking.py`: `effective_mu_with_banking()`, `apply_banking_to_mu_array()`. `corners.py`: `Corner.banking_deg`. `track_db.py`: per-corner `camber` + `banking_deg` data. |
| P7 | Multi-lap curvature averaging | ✅ Done | `curvature_averaging.py`: `average_lap_coordinates()`, `compute_averaged_curvature()`. `track_reference.py` uses it for canonical profiles. |
| P8 | Full GGV surface | ✅ Done | `grip_calibration.py`: `GGVSurface`, `build_ggv_surface()`, `query_ggv_max_g()`. |
| P9 | Clothoid spline fitting | ✅ Done | `clothoid_fitting.py`: `fit_clothoid_segment()`, `compute_clothoid_curvature()`, helper functions `_find_knots()`, `_fit_segments()`. |
| P10 | Tire thermal model | ✅ Done | `grip_calibration.py`: `compute_warmup_factor()`. `equipment.py`: `CATEGORY_WARMUP_LAPS` per compound. |
| P11 | Load sensitivity | ✅ Done | `grip_calibration.py`: `load_sensitive_mu()`. `velocity_profile.py`: `load_sensitivity_exponent`, `cg_height_m`, `track_width_m` in `VehicleParams`, correction in `_compute_max_cornering_speed()`. `equipment.py`: `CATEGORY_LOAD_SENSITIVITY_EXPONENT` wired. |

## Phase 2 Plan (velocity-model-phase2.md)

| # | Feature | Status | Evidence |
|---|---------|--------|----------|
| T1 | Fix Barber elevation_range_m (60→24) | ✅ Done | `track_db.py` (verified in prior session) |
| T2 | Wire friction circle exponent | ✅ Done | `equipment.py`: `CATEGORY_FRICTION_CIRCLE_EXPONENT` used in `equipment_to_vehicle_params()` |
| T3 | Drag coefficient from CdA | ✅ Done | `equipment.py`: `_AIR_DENSITY`, `drag_coefficient` computed from `cd_a`. `velocity_profile.py`: `drag_coefficient` used in forward/backward passes. |
| T4 | Load sensitivity wiring | ✅ Done | See P11 above. |
| T5 | Power-limited acceleration | ✅ Done | `velocity_profile.py`: `wheel_power_w`, `mass_kg` in `VehicleParams`. `_forward_pass()` computes `power_accel_g = wheel_power_w / (mass_kg * v * G)`. `equipment.py`: `_DRIVETRAIN_EFFICIENCY`, `wheel_power_w` wired. |
| T6 | USGS 3DEP LIDAR elevation | ✅ Done | `elevation_service.py` exists (confirmed in prior session). |

## Summary

**All 12 planned improvements (P0-P11) have code written + tests passing.**
**All 6 Phase 2 tasks have code written + tests passing.**

## CRITICAL: Dead Code — Implemented but NOT Wired into Pipeline

The following features exist in `cataclysm/` with full test coverage but are **never called from `backend/api/services/pipeline.py`** — they have zero effect on actual user-facing results:

| Feature | Module | Function | Refs outside tests? |
|---------|--------|----------|---------------------|
| GGV surface | `grip_calibration.py` | `build_ggv_surface()`, `query_ggv_max_g()` | ❌ No |
| Tire warmup | `grip_calibration.py` | `compute_warmup_factor()` | ❌ No |
| Load sensitive mu (linear) | `grip_calibration.py` | `load_sensitive_mu()` | ❌ No |
| Linked corners | `linked_corners.py` | `detect_linked_corners()` | ❌ No |
| Banking corrections | `banking.py` | `apply_banking_to_mu_array()` | ❌ No |
| Clothoid curvature | `clothoid_fitting.py` | `compute_clothoid_curvature()` | ❌ No |

**Note:** Load sensitivity IS wired via the power-law correction in `_compute_max_cornering_speed()` (using `VehicleParams.load_sensitivity_exponent`). The separate `load_sensitive_mu()` function (linear model) is an alternative that's not used.

### Features that ARE wired into the pipeline:

| Feature | Pipeline import | Called at |
|---------|----------------|----------|
| Grip calibration (3 semi-axes) | `calibrate_grip_from_telemetry`, `apply_calibration_to_params` | Optimal profile computation |
| Per-corner mu | `calibrate_per_corner_grip` | Optimal profile computation |
| Grip estimation (multi-approach) | `estimate_grip_limit` | Session processing (step 8) |
| Elevation gradient + vertical curvature | `compute_gradient_array`, `compute_vertical_curvature` | Solver passes |
| Curvature (spline + rate limiter) | `compute_curvature` | Solver input |
| Multi-lap curvature averaging | via `track_reference.py` | Canonical track reference |
| Equipment → VehicleParams | `equipment_to_vehicle_params` | Profile resolution |
| LIDAR elevation | `fetch_lidar_elevations` | Pre-solver async fetch |
| Friction circle exponent | wired in `equipment_to_vehicle_params()` | `_available_accel()` |
| Load sensitivity (power-law) | wired in `equipment_to_vehicle_params()` | `_compute_max_cornering_speed()` |
| Drag coefficient | wired in `equipment_to_vehicle_params()` | Forward/backward passes |
| Power-limited accel | wired in `equipment_to_vehicle_params()` | `_forward_pass()` |

## What the Multi-Model Review Should Focus On

### Priority 1: Wire dead code into the pipeline
- **Banking corrections** — track_db already has banking_deg data per corner; just needs `apply_banking_to_mu_array()` call in pipeline
- **Linked corner grouping** — `detect_linked_corners()` needs to run after optimal profile, tag corners, expose via API
- **Tire warmup** — `compute_warmup_factor()` should adjust grip for lap 1 analysis

### Priority 2: Validate formula correctness (via octo:discover)
- Is the vertical curvature denom floor (50% of lateral) physically justified?
- Is p95 the right percentile for grip calibration? (was p99, changed to p95)
- Is the cornering speed formula with aero correct?
- Is the load sensitivity power-law correction mathematically right?

### Priority 3: Missing features not in original research
- Trail braking model (combined braking+cornering optimization)
- Track surface variation (wet/damp grip multiplier)
- Tire degradation over session (grip fade after N laps)
- Yaw rate / stability model

### Priority 4: Numerical stability & performance
- Division by zero guards in curvature denominators
- NaN propagation through solver passes
- Performance of per-corner grip calibration at scale

## Key Files Summary

| File | Lines | Symbols |
|------|-------|---------|
| `velocity_profile.py` | 657 | VehicleParams, OptimalProfile, compute_optimal_profile, _forward_pass, _backward_pass, _compute_max_cornering_speed |
| `grip_calibration.py` | 581 | CalibratedGrip, GGVSurface, calibrate_grip_from_telemetry, calibrate_per_corner_grip, build_ggv_surface, compute_warmup_factor, load_sensitive_mu |
| `grip.py` | 524 | GripEstimate, estimate_grip_limit (4 approaches: envelope, ellipse, speed-dependent, convex hull) |
| `equipment.py` | 330+ | TireCompoundCategory, equipment_to_vehicle_params, compound constants tables |
| `elevation_profile.py` | 200+ | compute_gradient_array, compute_vertical_curvature |
| `curvature.py` | 600+ | CurvatureResult, compute_curvature, _limit_curvature_rate |
| `optimal_comparison.py` | 312 | CornerOpportunity, compare_with_optimal, apex window analysis |
| `corners.py` | 663 | Corner, detect_corners, extract_corner_kpis_for_lap |
| `linked_corners.py` | 150+ | CornerGroup, detect_linked_corners, curvature_variation_index |
| `banking.py` | 130+ | effective_mu_with_banking, apply_banking_to_mu_array |
| `curvature_averaging.py` | 150+ | average_lap_coordinates, compute_averaged_curvature |
| `clothoid_fitting.py` | 270+ | fit_clothoid_segment, compute_clothoid_curvature |

# Velocity Model Phase 2 — Physics Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire existing-but-unused physics models into the velocity solver and fix data quality issues, reducing simulation error from ~8-10% to ~3-5%.

**Architecture:** Six independent improvements to the forward-backward velocity solver (`velocity_profile.py`). Most code already exists in `equipment.py` and `grip_calibration.py` but isn't connected. Changes flow through `equipment_to_vehicle_params()` → `VehicleParams` → solver internals. One task is a data fix (Barber elevation), one adds external data (USGS LIDAR).

**Tech Stack:** Python 3.11+, NumPy, httpx (for USGS API), pytest, dataclasses

---

## Task 1: Fix Barber `elevation_range_m` (P0 — Data Bug)

**Files:**
- Modify: `cataclysm/track_db.py:127`
- Test: `tests/test_track_db.py` (new test)

**Context:** Barber's `elevation_range_m=60.0` is wrong. The actual min-to-max altitude range is ~24m (80 feet). The 60m value was likely from cumulative ups+downs (190 feet / 58m), not the range. AMP=30.0 and Roebling=8.0 are correct.

**Step 1: Write the failing test**

In `tests/test_track_db.py`, add:

```python
def test_barber_elevation_range_is_correct():
    """Barber elevation range is ~24m (80ft), not 60m."""
    from cataclysm.track_db import TRACK_LAYOUTS

    barber = TRACK_LAYOUTS.get("barber_motorsports_park")
    assert barber is not None
    assert barber.elevation_range_m is not None
    # Real range is ~24m (80 feet).  Must be < 30m.
    assert barber.elevation_range_m < 30.0
    assert barber.elevation_range_m == 24.0
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_track_db.py::test_barber_elevation_range_is_correct -v`
Expected: FAIL — `assert 60.0 < 30.0`

**Step 3: Fix the value**

In `cataclysm/track_db.py:127`, change:
```python
    elevation_range_m=60.0,
```
to:
```python
    elevation_range_m=24.0,
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_track_db.py::test_barber_elevation_range_is_correct -v`
Expected: PASS

**Step 5: Run full suite and commit**

Run: `source .venv/bin/activate && ruff check cataclysm/track_db.py tests/test_track_db.py && pytest tests/ -x -q`

```bash
git add cataclysm/track_db.py tests/test_track_db.py
git commit -m "fix: correct Barber elevation_range_m from 60m to 24m

The 60m value was cumulative elevation gain+loss, not the actual
min-to-max altitude range which is ~24m (80 feet)."
```

---

## Task 2: Wire Friction Circle Exponent from Equipment (P1)

**Files:**
- Modify: `cataclysm/equipment.py:265-271` (`equipment_to_vehicle_params`)
- Test: `tests/test_equipment.py`

**Context:** `CATEGORY_FRICTION_CIRCLE_EXPONENT` (lines 99-106) maps tire compound to exponent (1.8 for street to 2.3 for slick). `VehicleParams.friction_circle_exponent` defaults to 2.0 and is used by `_available_accel()` (velocity_profile.py:186). But `equipment_to_vehicle_params()` never sets it — it's always 2.0. Fix: add one line to the return statement.

**Step 1: Write the failing test**

In `tests/test_equipment.py`, add:

```python
def test_equipment_to_vehicle_params_sets_friction_circle_exponent():
    """Friction circle exponent should come from compound category table."""
    from cataclysm.equipment import (
        CATEGORY_FRICTION_CIRCLE_EXPONENT,
        EquipmentProfile,
        MuSource,
        TireCompoundCategory,
        TireSpec,
        equipment_to_vehicle_params,
    )

    for category in TireCompoundCategory:
        tire = TireSpec(
            model="Test",
            compound_category=category,
            size="255/40R17",
            treadwear_rating=200,
            estimated_mu=1.0,
            mu_source=MuSource.FORMULA_ESTIMATE,
            mu_confidence="medium",
        )
        profile = EquipmentProfile(id="test", name="test", tires=tire)
        params = equipment_to_vehicle_params(profile)
        expected = CATEGORY_FRICTION_CIRCLE_EXPONENT[category]
        assert params.friction_circle_exponent == expected, (
            f"{category}: got {params.friction_circle_exponent}, expected {expected}"
        )
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_equipment.py::test_equipment_to_vehicle_params_sets_friction_circle_exponent -v`
Expected: FAIL — `STREET: got 2.0, expected 1.8`

**Step 3: Add friction_circle_exponent to VehicleParams construction**

In `cataclysm/equipment.py`, in `equipment_to_vehicle_params()`, change the return statement (lines 265-271) from:

```python
    return VehicleParams(
        mu=mu,
        max_lateral_g=mu,
        max_accel_g=accel_g,
        max_decel_g=mu * _BRAKE_EFFICIENCY,
        top_speed_mps=80.0,
    )
```

to:

```python
    return VehicleParams(
        mu=mu,
        max_lateral_g=mu,
        max_accel_g=accel_g,
        max_decel_g=mu * _BRAKE_EFFICIENCY,
        top_speed_mps=80.0,
        friction_circle_exponent=CATEGORY_FRICTION_CIRCLE_EXPONENT[category],
    )
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_equipment.py::test_equipment_to_vehicle_params_sets_friction_circle_exponent -v`
Expected: PASS

**Step 5: Run full suite and commit**

Run: `source .venv/bin/activate && ruff check cataclysm/equipment.py tests/test_equipment.py && pytest tests/ -x -q`

```bash
git add cataclysm/equipment.py tests/test_equipment.py
git commit -m "feat: wire friction circle exponent from tire compound category

CATEGORY_FRICTION_CIRCLE_EXPONENT was defined but never used.
Street tires (1.8/diamond) now behave differently from slicks
(2.3/squarish) in the friction circle budget calculation."
```

---

## Task 3: Populate Drag Coefficient from Vehicle Spec (P2)

**Files:**
- Modify: `cataclysm/vehicle_db.py` (add `cd_a` field to `VehicleSpec`)
- Modify: `cataclysm/equipment.py:226-271` (`equipment_to_vehicle_params`)
- Test: `tests/test_equipment.py`

**Context:** `VehicleParams.drag_coefficient` is used in `_forward_pass()` (line 227) and `_backward_pass()` (line 268) but is always 0.0. The drag coefficient absorbs `Cd * A * rho / (2 * m)` so it has units of 1/m. For a Miata: Cd=0.32, A=1.8m², rho=1.225, m=1050kg → drag_coefficient ≈ 0.000336. At 100 mph (44.7 m/s): drag_g = 0.000336 * 44.7² / 9.81 ≈ 0.068 G. This matters.

**Step 1: Add `cd_a` field to VehicleSpec**

In `cataclysm/vehicle_db.py`, add a new field to `VehicleSpec` after `has_aero`:

```python
    cd_a: float = 0.0  # Cd * frontal_area (m^2); 0 = unknown/not set
```

Then populate known values for the most common track-day cars:

```python
# Miata NA/NB/NC/ND: Cd ≈ 0.32-0.34, A ≈ 1.79-1.83 m²
"mazda_miata_na": ... cd_a=0.58,   # 0.32 * 1.81
"mazda_miata_nb": ... cd_a=0.58,   # 0.32 * 1.81
"mazda_miata_nc": ... cd_a=0.60,   # 0.33 * 1.81
"mazda_miata_nd": ... cd_a=0.56,   # 0.31 * 1.80
# BMW E46 M3: Cd ≈ 0.32, A ≈ 2.14 m²
"bmw_m3_e46": ... cd_a=0.69,       # 0.32 * 2.14
# Porsche 911 (996): Cd ≈ 0.30, A ≈ 1.99 m²
"porsche_911_996": ... cd_a=0.60,   # 0.30 * 1.99
# Corvette C6: Cd ≈ 0.29, A ≈ 2.14 m²
"chevy_corvette_c6": ... cd_a=0.62, # 0.29 * 2.14
```

For cars where CdA isn't known, leave `cd_a=0.0` (the default).

**Step 2: Write the failing test**

In `tests/test_equipment.py`, add:

```python
def test_equipment_to_vehicle_params_sets_drag_coefficient():
    """drag_coefficient should be computed from vehicle CdA and weight."""
    from cataclysm.equipment import (
        EquipmentProfile,
        MuSource,
        TireCompoundCategory,
        TireSpec,
        equipment_to_vehicle_params,
    )
    from cataclysm.vehicle_db import VEHICLE_DATABASE

    tire = TireSpec(
        model="Test",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="205/50R15",
        treadwear_rating=200,
        estimated_mu=1.0,
        mu_source=MuSource.FORMULA_ESTIMATE,
        mu_confidence="medium",
    )
    vehicle = VEHICLE_DATABASE["mazda_miata_nd"]
    profile = EquipmentProfile(
        id="test", name="test", tires=tire, vehicle=vehicle
    )
    params = equipment_to_vehicle_params(profile)

    # drag_coefficient = Cd * A * rho / (2 * m)
    # For ND Miata: cd_a=0.56, rho=1.225, m=1058 → ~0.000324
    assert params.drag_coefficient > 0.0
    assert 0.0002 < params.drag_coefficient < 0.0005


def test_equipment_to_vehicle_params_drag_zero_without_cda():
    """drag_coefficient should be 0 when vehicle has no CdA data."""
    from cataclysm.equipment import (
        EquipmentProfile,
        MuSource,
        TireCompoundCategory,
        TireSpec,
        equipment_to_vehicle_params,
    )
    from cataclysm.vehicle_db import VehicleSpec

    tire = TireSpec(
        model="Test",
        compound_category=TireCompoundCategory.STREET,
        size="205/50R15",
        treadwear_rating=300,
        estimated_mu=1.0,
        mu_source=MuSource.FORMULA_ESTIMATE,
        mu_confidence="medium",
    )
    # Vehicle with default cd_a=0.0
    vehicle = VehicleSpec(
        make="Test", model="Car", generation="V1",
        year_range=(2020, 2025), weight_kg=1200,
        wheelbase_m=2.5, track_width_front_m=1.5,
        track_width_rear_m=1.5, cg_height_m=0.5,
        weight_dist_front_pct=55.0, drivetrain="FWD",
        hp=150, torque_nm=200, has_aero=False,
    )
    profile = EquipmentProfile(
        id="test", name="test", tires=tire, vehicle=vehicle
    )
    params = equipment_to_vehicle_params(profile)
    assert params.drag_coefficient == 0.0
```

**Step 3: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/test_equipment.py::test_equipment_to_vehicle_params_sets_drag_coefficient tests/test_equipment.py::test_equipment_to_vehicle_params_drag_zero_without_cda -v`
Expected: FAIL

**Step 4: Implement drag coefficient computation**

In `cataclysm/equipment.py`, in `equipment_to_vehicle_params()`, add drag computation before the return. Insert after the acceleration refinement block and before the `return`:

```python
    # Compute aerodynamic drag coefficient: k = CdA * rho / (2 * m)
    # drag_g = k * v^2 / G  in the solver
    _AIR_DENSITY = 1.225  # kg/m^3, sea level ISA
    drag_coeff = 0.0
    if profile.vehicle is not None and profile.vehicle.cd_a > 0:
        mass_kg = weight_kg if profile.vehicle is not None else 1200.0
        drag_coeff = profile.vehicle.cd_a * _AIR_DENSITY / (2.0 * mass_kg)
```

Then add `drag_coefficient=drag_coeff` to the VehicleParams constructor.

Note: `weight_kg` is already computed earlier in the function when `profile.vehicle is not None`.

**Step 5: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/test_equipment.py -k "drag" -v`
Expected: PASS

**Step 6: Run full suite and commit**

Run: `source .venv/bin/activate && ruff check cataclysm/ tests/ && pytest tests/ -x -q`

```bash
git add cataclysm/vehicle_db.py cataclysm/equipment.py tests/test_equipment.py
git commit -m "feat: populate drag coefficient from vehicle CdA

Adds cd_a (Cd * frontal area) to VehicleSpec for common track cars.
equipment_to_vehicle_params() now computes drag_coefficient = CdA*rho/(2m).
At 100mph this produces ~0.06G drag for a Miata, significantly affecting
the forward/backward pass acceleration budgets."
```

---

## Task 4: Wire Load Sensitivity into the Solver (P3)

**Files:**
- Modify: `cataclysm/velocity_profile.py` (add `load_sensitivity_exponent` to `VehicleParams`, modify `_compute_max_cornering_speed`)
- Modify: `cataclysm/equipment.py:265-271` (`equipment_to_vehicle_params`)
- Test: `tests/test_velocity_profile.py`

**Context:** Tire grip decreases per unit load as vertical load increases. The power-law model is: `mu_eff = mu_ref * (Fz_actual / Fz_ref)^(n-1)` where `n = 0.78-0.85` (from `CATEGORY_LOAD_SENSITIVITY_EXPONENT`). For a 1050 kg car at 2G cornering, outer tires carry ~60% more load than static → mu drops ~8-10%. The existing `load_sensitive_mu()` in `grip_calibration.py` uses a linear model, but the power-law is more standard. We'll implement a simplified version: apply a flat correction factor to mu based on the expected average weight transfer during cornering, rather than computing per-point weight transfer (which requires track-width and CG data at every step).

The simplified approach: at high lateral G, the average tire mu is lower than the reference. The correction factor is approximately:
```
mu_effective = mu_ref * correction_factor
correction_factor ≈ (1 + lateral_load_ratio)^(n-1)  where lateral_load_ratio = (a_lat * cg_height) / track_width
```

For initial implementation, we apply a static correction factor to mu at the cornering speed calculation, rather than making it speed-dependent (which would require iterative solving).

**Step 1: Add `load_sensitivity_exponent` to VehicleParams**

In `cataclysm/velocity_profile.py`, add to `VehicleParams`:

```python
    load_sensitivity_exponent: float = 1.0  # n=1 means no sensitivity; <1 = mu drops with load
    static_weight_n: float = 0.0  # vehicle static weight in Newtons (for load sensitivity calc)
    cg_height_m: float = 0.0  # CG height for weight transfer estimation
    track_width_m: float = 0.0  # average track width for weight transfer estimation
```

**Step 2: Write the failing test**

In `tests/test_velocity_profile.py`, add:

```python
def test_load_sensitivity_reduces_cornering_speed():
    """Load sensitivity should reduce max cornering speed vs constant-mu model."""
    from cataclysm.curvature import CurvatureResult
    from cataclysm.velocity_profile import VehicleParams, compute_optimal_profile

    n = 200
    distance = np.linspace(0, 200, n)
    # Constant curvature (50m radius turn)
    curvature = np.full(n, 1.0 / 50.0)

    cr = CurvatureResult(
        curvature=curvature,
        abs_curvature=np.abs(curvature),
        distance_m=distance,
        smooth_lat=np.zeros(n),
        smooth_lon=np.zeros(n),
    )

    # No load sensitivity (n=1.0)
    params_no_ls = VehicleParams(
        mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0,
        load_sensitivity_exponent=1.0,
    )
    profile_no_ls = compute_optimal_profile(cr, params_no_ls, closed_circuit=False)

    # With load sensitivity (n=0.82, typical 200TW tire, with Miata-like dimensions)
    params_ls = VehicleParams(
        mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0,
        load_sensitivity_exponent=0.82,
        static_weight_n=1050.0 * 9.81,
        cg_height_m=0.46,
        track_width_m=1.41,
    )
    profile_ls = compute_optimal_profile(cr, params_ls, closed_circuit=False)

    # Load sensitivity should produce lower cornering speeds
    mid = n // 2  # mid-corner where speed is limited by grip
    assert profile_ls.optimal_speed_mps[mid] < profile_no_ls.optimal_speed_mps[mid]
    # Expect ~4-8% reduction in cornering speed
    speed_reduction_pct = (
        1.0 - profile_ls.optimal_speed_mps[mid] / profile_no_ls.optimal_speed_mps[mid]
    ) * 100
    assert 2.0 < speed_reduction_pct < 15.0, f"Got {speed_reduction_pct:.1f}%"
```

**Step 3: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_velocity_profile.py::test_load_sensitivity_reduces_cornering_speed -v`
Expected: FAIL (both profiles produce identical speeds since load sensitivity isn't wired)

**Step 4: Implement load sensitivity in cornering speed**

In `_compute_max_cornering_speed()`, after computing `effective_mu` (around line 123), add load sensitivity correction:

```python
    # Load sensitivity: mu drops under lateral weight transfer.
    # Correction: mu_eff = mu * ((Fz_outer + Fz_inner) / (2 * Fz_static))^(n-1)
    # For a given lateral G, lateral load transfer ratio = a_lat * h_cg / track_w
    # Average tire mu (inner+outer) = mu_ref * 0.5 * ((1+dLT)^(n-1) + (1-dLT)^(n-1))
    # We pre-compute this for the max cornering speed at each point.
    n_exp = params.load_sensitivity_exponent
    if n_exp < 1.0 and params.track_width_m > 0 and params.cg_height_m > 0:
        # At cornering limit: a_lat ≈ mu * g, so dLT = mu * g * h_cg / (g * track_w)
        # = mu * h_cg / track_w
        dlt = effective_mu * params.cg_height_m / params.track_width_m
        # Average mu correction across inner/outer tires
        # outer sees (1+dLT)*Fz_static, inner sees (1-dLT)*Fz_static
        dlt_clamp = np.clip(dlt, 0.0, 0.95)
        correction = 0.5 * (
            np.power(1.0 + dlt_clamp, n_exp - 1.0)
            + np.power(np.maximum(1.0 - dlt_clamp, 0.05), n_exp - 1.0)
        )
        effective_mu = effective_mu * correction
```

This must go before the `curved_mask` line (currently line 134).

**Step 5: Wire load sensitivity params in equipment_to_vehicle_params**

In `cataclysm/equipment.py`, add to the VehicleParams return in `equipment_to_vehicle_params()`:

```python
        load_sensitivity_exponent=CATEGORY_LOAD_SENSITIVITY_EXPONENT[category],
        static_weight_n=weight_kg * 9.81 if profile.vehicle is not None else 0.0,
        cg_height_m=profile.vehicle.cg_height_m if profile.vehicle is not None else 0.0,
        track_width_m=(
            0.5 * (profile.vehicle.track_width_front_m + profile.vehicle.track_width_rear_m)
            if profile.vehicle is not None
            else 0.0
        ),
```

Note: `weight_kg` variable already exists from the acceleration refinement block. If `profile.vehicle is None`, the exponent is set but `track_width_m=0.0` triggers the `if` guard and load sensitivity is effectively disabled.

**Step 6: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_velocity_profile.py::test_load_sensitivity_reduces_cornering_speed -v`
Expected: PASS

**Step 7: Write equipment integration test**

In `tests/test_equipment.py`, add:

```python
def test_equipment_to_vehicle_params_sets_load_sensitivity():
    """Load sensitivity fields should be populated from equipment + vehicle."""
    from cataclysm.equipment import (
        CATEGORY_LOAD_SENSITIVITY_EXPONENT,
        EquipmentProfile,
        MuSource,
        TireCompoundCategory,
        TireSpec,
        equipment_to_vehicle_params,
    )
    from cataclysm.vehicle_db import VEHICLE_DATABASE

    tire = TireSpec(
        model="Test",
        compound_category=TireCompoundCategory.R_COMPOUND,
        size="255/40R17",
        treadwear_rating=None,
        estimated_mu=1.35,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="high",
    )
    vehicle = VEHICLE_DATABASE["mazda_miata_nd"]
    profile = EquipmentProfile(
        id="test", name="test", tires=tire, vehicle=vehicle
    )
    params = equipment_to_vehicle_params(profile)
    assert params.load_sensitivity_exponent == CATEGORY_LOAD_SENSITIVITY_EXPONENT[
        TireCompoundCategory.R_COMPOUND
    ]
    assert params.cg_height_m > 0
    assert params.track_width_m > 0
    assert params.static_weight_n > 0
```

**Step 8: Run full suite and commit**

Run: `source .venv/bin/activate && ruff check cataclysm/ tests/ && ruff format cataclysm/ tests/ && pytest tests/ -x -q`

```bash
git add cataclysm/velocity_profile.py cataclysm/equipment.py tests/test_velocity_profile.py tests/test_equipment.py
git commit -m "feat: wire tire load sensitivity into velocity solver

Implements lateral weight transfer correction to effective mu in
cornering speed calculation. Uses power-law model with per-compound
exponents (0.75-0.85). Averages inner/outer tire grip under
load transfer. Typical effect: 4-8% lower cornering speeds,
making the model more conservative and realistic."
```

---

## Task 5: Add Power-Limited Acceleration Model (P4)

**Files:**
- Modify: `cataclysm/velocity_profile.py:34-54` (`VehicleParams`), lines 196-234 (`_forward_pass`)
- Modify: `cataclysm/equipment.py:226-271` (`equipment_to_vehicle_params`)
- Test: `tests/test_velocity_profile.py`

**Context:** Currently `max_accel_g` is constant regardless of speed. Real cars are power-limited above a crossover speed: `F = min(mu*m*g*driven_fraction, P_wheel/v) - F_drag`. For a 155hp Miata at ~50mph, power becomes the bottleneck. Above that, available acceleration drops as ~1/v. This makes the model much more realistic at high speed.

The physics: `a_power = P_wheel / (m * v)` in G = `P_wheel / (m * v * g)`. We need wheel power (after drivetrain losses), so `P_wheel = P_engine * drivetrain_efficiency`. Typical efficiencies: 0.85 (RWD), 0.82 (FWD), 0.80 (AWD).

**Step 1: Add power fields to VehicleParams**

In `cataclysm/velocity_profile.py`, add to `VehicleParams`:

```python
    wheel_power_w: float = 0.0  # Wheel power (after drivetrain loss) in Watts; 0 = disabled
    mass_kg: float = 0.0  # Vehicle mass in kg; 0 = use max_accel_g only
```

**Step 2: Write the failing test**

In `tests/test_velocity_profile.py`, add:

```python
def test_power_limited_acceleration_at_high_speed():
    """Above crossover speed, acceleration should be power-limited (lower than grip-limited)."""
    from cataclysm.curvature import CurvatureResult
    from cataclysm.velocity_profile import VehicleParams, compute_optimal_profile

    n = 500
    distance = np.linspace(0, 500, n)
    # Straight road (zero curvature)
    curvature = np.zeros(n)

    cr = CurvatureResult(
        curvature=curvature,
        abs_curvature=np.abs(curvature),
        distance_m=distance,
        smooth_lat=np.zeros(n),
        smooth_lon=np.zeros(n),
    )

    # Without power limit — constant accel
    params_const = VehicleParams(
        mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0,
        top_speed_mps=70.0,
    )
    profile_const = compute_optimal_profile(cr, params_const, closed_circuit=False)

    # With power limit — 155hp Miata (115kW * 0.85 drivetrain eff)
    params_power = VehicleParams(
        mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0,
        top_speed_mps=70.0,
        wheel_power_w=115_000 * 0.85,  # ~97.75 kW at wheels
        mass_kg=1050.0,
    )
    profile_power = compute_optimal_profile(cr, params_power, closed_circuit=False)

    # At the end of a 500m straight, power-limited car should be slower
    assert profile_power.optimal_speed_mps[-1] < profile_const.optimal_speed_mps[-1]

    # At low speed (early in the straight), speeds should be similar
    # (grip-limited regime, P/v > mu*m*g)
    assert abs(profile_power.optimal_speed_mps[10] - profile_const.optimal_speed_mps[10]) < 2.0
```

**Step 3: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_velocity_profile.py::test_power_limited_acceleration_at_high_speed -v`
Expected: FAIL (both profiles are identical since wheel_power_w is ignored)

**Step 4: Implement power-limited acceleration in _forward_pass**

In `_forward_pass()`, replace the line:

```python
        accel_g = _available_accel(v_prev, lateral_g, params, "accel")
```

with:

```python
        accel_g = _available_accel(v_prev, lateral_g, params, "accel")
        # Power-limited regime: a = P_wheel / (m * v * g) at high speed
        if params.wheel_power_w > 0 and params.mass_kg > 0 and v_prev > MIN_SPEED_MPS:
            power_accel_g = params.wheel_power_w / (params.mass_kg * v_prev * G)
            accel_g = min(accel_g, power_accel_g)
```

This smoothly transitions from grip-limited (low speed) to power-limited (high speed). The crossover happens when `P/(m*v) = max_accel_g * g`, i.e., `v_crossover = P / (m * max_accel_g * g)`.

**Step 5: Wire power fields in equipment_to_vehicle_params**

In `cataclysm/equipment.py`, in `equipment_to_vehicle_params()`, add power computation. Add these lines before the return statement:

```python
    # Compute wheel power for power-limited acceleration model
    _DRIVETRAIN_EFFICIENCY = {"RWD": 0.85, "FWD": 0.82, "AWD": 0.80}
    wheel_power_w = 0.0
    mass_kg_for_params = 0.0
    if profile.vehicle is not None:
        hp_to_watts = 745.7
        dt_eff = _DRIVETRAIN_EFFICIENCY.get(profile.vehicle.drivetrain, 0.85)
        wheel_power_w = profile.vehicle.hp * hp_to_watts * dt_eff
        mass_kg_for_params = weight_kg
```

Then add to VehicleParams constructor:
```python
        wheel_power_w=wheel_power_w,
        mass_kg=mass_kg_for_params,
```

**Step 6: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_velocity_profile.py::test_power_limited_acceleration_at_high_speed -v`
Expected: PASS

**Step 7: Run full suite and commit**

Run: `source .venv/bin/activate && ruff check cataclysm/ tests/ && ruff format cataclysm/ tests/ && pytest tests/ -x -q`

```bash
git add cataclysm/velocity_profile.py cataclysm/equipment.py tests/test_velocity_profile.py tests/test_equipment.py
git commit -m "feat: add power-limited acceleration model

Above the crossover speed (~50mph for a 155hp Miata), acceleration
is limited by P/(m*v) instead of grip. Uses wheel power after
drivetrain efficiency losses (RWD 85%, FWD 82%, AWD 80%).
This makes straights much more realistic — a Miata can't
accelerate at 0.5G at 100mph."
```

---

## Task 6: Improve Elevation Data via USGS 3DEP LIDAR (P5 — Research + Implementation)

**Files:**
- Create: `cataclysm/elevation_service.py`
- Create: `cataclysm/data/elevation_cache/` (directory)
- Modify: `backend/api/services/pipeline.py` (use LIDAR altitude instead of GPS)
- Test: `tests/test_elevation_service.py`

**Context:** GPS altitude has ~3m sigma vertical accuracy (RaceBox). The 120m smoothing window needed to denoise GPS altitude is 3-6x wider than compression features (20-40m), severely attenuating the signal. USGS 3DEP LIDAR provides 5-15cm accuracy at 1-3m horizontal resolution. Available across most of the US. The API is free and doesn't require authentication.

The approach: given GPS lat/lon from a lap, query the USGS 3DEP Elevation Point Query Service to get LIDAR altitude at each point. Cache results per-track (keyed by track name and grid resolution). The LIDAR elevations replace GPS altitude for gradient and vertical curvature calculations.

**Step 1: Research the USGS 3DEP API**

The USGS 3DEP Elevation Point Query Service endpoint:
```
GET https://epqs.nationalmap.gov/v1/json?x={longitude}&y={latitude}&wkid=4326&units=Meters&includeDate=false
```

For batch queries, we can use multiple concurrent requests or the batch endpoint. The service supports up to ~100 requests per second.

For efficiency, we'll:
1. Subsample the GPS trace to ~1m spacing (typical lap has 2000-5000 points)
2. Query LIDAR elevation for each subsampled point
3. Interpolate back to full resolution
4. Cache results keyed by track name + GPS bounding box hash

**Step 2: Write the failing test**

In `tests/test_elevation_service.py`:

```python
"""Tests for USGS 3DEP LIDAR elevation service."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from cataclysm.elevation_service import (
    fetch_lidar_elevations,
    ElevationResult,
)


@pytest.fixture
def mock_lidar_response():
    """Mock a single USGS 3DEP API response."""
    return {"value": 195.3}


@pytest.mark.asyncio
async def test_fetch_lidar_elevations_returns_array():
    """fetch_lidar_elevations should return an array of elevations."""
    lats = np.array([33.536, 33.537, 33.538])
    lons = np.array([-86.621, -86.622, -86.623])

    # Mock the HTTP client
    mock_values = [195.3, 196.1, 194.8]

    async def mock_get(url, **kwargs):
        # Extract which point this is based on the y parameter
        resp = AsyncMock()
        resp.status_code = 200
        resp.json.return_value = {"value": mock_values.pop(0)}
        resp.raise_for_status = lambda: None
        return resp

    with patch("cataclysm.elevation_service.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.get = mock_get
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await fetch_lidar_elevations(lats, lons)

    assert isinstance(result, ElevationResult)
    assert len(result.altitude_m) == 3
    assert result.altitude_m[0] == pytest.approx(195.3)
    assert result.source == "usgs_3dep"


def test_elevation_result_fallback_to_gps():
    """If LIDAR fetch fails, result should indicate GPS fallback."""
    result = ElevationResult(
        altitude_m=np.array([100.0, 101.0]),
        source="gps_fallback",
        accuracy_m=3.0,
    )
    assert result.source == "gps_fallback"
    assert result.accuracy_m == 3.0
```

**Step 3: Implement the elevation service**

Create `cataclysm/elevation_service.py`:

```python
"""USGS 3DEP LIDAR elevation service for high-accuracy track altitude.

Queries the USGS 3DEP Elevation Point Query Service to get LIDAR-grade
altitude (5-15cm accuracy) instead of relying on GPS altitude (~3m).
Results are cached per-track to avoid repeated API calls.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np

logger = logging.getLogger(__name__)

_USGS_3DEP_URL = "https://epqs.nationalmap.gov/v1/json"
_CACHE_DIR = Path("data/elevation_cache")
_MAX_CONCURRENT = 20  # Max parallel requests to USGS API
_SUBSAMPLE_SPACING_M = 2.0  # Query every 2m of track distance


@dataclass
class ElevationResult:
    """Result of elevation lookup."""

    altitude_m: np.ndarray
    source: str  # "usgs_3dep" | "gps_fallback"
    accuracy_m: float  # Estimated accuracy in meters


def _cache_key(lats: np.ndarray, lons: np.ndarray) -> str:
    """Generate a cache key from GPS coordinates bounding box."""
    bbox = f"{lats.min():.4f},{lats.max():.4f},{lons.min():.4f},{lons.max():.4f},{len(lats)}"
    return hashlib.md5(bbox.encode()).hexdigest()


def _load_cache(key: str) -> np.ndarray | None:
    """Load cached elevation data if available."""
    path = _CACHE_DIR / f"{key}.json"
    if path.exists():
        data = json.loads(path.read_text())
        return np.array(data["elevations"], dtype=np.float64)
    return None


def _save_cache(key: str, elevations: np.ndarray) -> None:
    """Save elevation data to cache."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps({"elevations": elevations.tolist()}))


async def _query_single_point(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    semaphore: asyncio.Semaphore,
) -> float | None:
    """Query USGS 3DEP for a single point."""
    async with semaphore:
        try:
            resp = await client.get(
                _USGS_3DEP_URL,
                params={"x": f"{lon:.6f}", "y": f"{lat:.6f}", "wkid": 4326, "units": "Meters"},
                timeout=10.0,
            )
            resp.raise_for_status()
            value = resp.json().get("value")
            if value is not None and value != -1000000:
                return float(value)
            return None
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.debug("3DEP query failed for (%.6f, %.6f): %s", lat, lon, exc)
            return None


async def fetch_lidar_elevations(
    lats: np.ndarray,
    lons: np.ndarray,
    *,
    subsample_spacing_m: float = _SUBSAMPLE_SPACING_M,
) -> ElevationResult:
    """Fetch LIDAR elevations for a GPS trace from USGS 3DEP.

    Parameters
    ----------
    lats, lons
        GPS coordinates arrays (same length).
    subsample_spacing_m
        Spacing between queried points in meters.  Points are
        subsampled, queried, then interpolated back to full resolution.

    Returns
    -------
    ElevationResult
        LIDAR elevations if successful, or a GPS-fallback indicator.
    """
    n = len(lats)
    cache_key = _cache_key(lats, lons)
    cached = _load_cache(cache_key)
    if cached is not None and len(cached) == n:
        return ElevationResult(altitude_m=cached, source="usgs_3dep", accuracy_m=0.1)

    # Subsample: pick every Nth point based on approximate spacing
    # Use haversine-approximate distance between consecutive points
    if n > 50:
        dlat = np.diff(lats)
        dlon = np.diff(lons)
        # Approximate distance in meters (flat-earth OK for short segments)
        step_m = np.sqrt((dlat * 111_320) ** 2 + (dlon * 111_320 * np.cos(np.radians(lats[:-1]))) ** 2)
        cum_dist = np.concatenate([[0], np.cumsum(step_m)])
        total_dist = cum_dist[-1]
        n_samples = max(10, int(total_dist / subsample_spacing_m))
        sample_dists = np.linspace(0, total_dist, n_samples)
        sample_indices = np.searchsorted(cum_dist, sample_dists).clip(0, n - 1)
        sample_indices = np.unique(sample_indices)
    else:
        sample_indices = np.arange(n)
        cum_dist = np.arange(n, dtype=np.float64)

    sample_lats = lats[sample_indices]
    sample_lons = lons[sample_indices]

    # Query USGS 3DEP
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    async with httpx.AsyncClient() as client:
        tasks = [
            _query_single_point(client, float(lat), float(lon), semaphore)
            for lat, lon in zip(sample_lats, sample_lons)
        ]
        results = await asyncio.gather(*tasks)

    # Check success rate
    valid = [r for r in results if r is not None]
    if len(valid) < len(results) * 0.8:
        logger.warning(
            "LIDAR elevation: only %d/%d points returned, falling back to GPS",
            len(valid), len(results),
        )
        return ElevationResult(altitude_m=np.array([]), source="gps_fallback", accuracy_m=3.0)

    # Fill gaps via linear interpolation
    sample_elevations = np.array(
        [r if r is not None else np.nan for r in results], dtype=np.float64
    )
    mask = np.isnan(sample_elevations)
    if mask.any() and not mask.all():
        xp = np.where(~mask)[0]
        fp = sample_elevations[~mask]
        sample_elevations = np.interp(np.arange(len(sample_elevations)), xp, fp)

    # Interpolate back to full resolution
    if len(sample_indices) < n:
        full_elevations = np.interp(
            np.arange(n),
            sample_indices.astype(np.float64),
            sample_elevations,
        )
    else:
        full_elevations = sample_elevations

    _save_cache(cache_key, full_elevations)

    return ElevationResult(altitude_m=full_elevations, source="usgs_3dep", accuracy_m=0.1)
```

**Step 4: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_elevation_service.py -v`
Expected: PASS

**Step 5: Wire into pipeline**

In `backend/api/services/pipeline.py`, in `get_optimal_profile_data()`, after deriving GPS altitude but before computing gradient/curvature, attempt to use LIDAR:

```python
        # Try LIDAR elevation for better accuracy
        if "latitude" in best_lap_df.columns and "longitude" in best_lap_df.columns:
            try:
                from cataclysm.elevation_service import fetch_lidar_elevations

                lidar_result = asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: asyncio.run(fetch_lidar_elevations(
                        best_lap_df["latitude"].to_numpy(),
                        best_lap_df["longitude"].to_numpy(),
                    ))
                )
                # This is inside a sync _compute(), so use a simple approach
                import asyncio as _aio

                loop = _aio.new_event_loop()
                lidar_result = loop.run_until_complete(fetch_lidar_elevations(
                    best_lap_df["latitude"].to_numpy(),
                    best_lap_df["longitude"].to_numpy(),
                ))
                loop.close()

                if lidar_result.source == "usgs_3dep" and len(lidar_result.altitude_m) > 0:
                    alt = lidar_result.altitude_m
                    logger.info("Using USGS 3DEP LIDAR elevation (%d points)", len(alt))
            except Exception:
                logger.debug("LIDAR elevation fetch failed, using GPS altitude", exc_info=True)
```

**Important:** The pipeline's `_compute()` runs in a thread via `asyncio.to_thread()`. Inside a thread, we can't use the outer event loop, so we create a new one. A cleaner approach is to make the LIDAR fetch happen before `_compute()` in the async context. The implementer should decide the cleanest integration pattern.

**Step 6: Write pipeline integration test**

In `tests/test_elevation_service.py`, add:

```python
def test_elevation_result_dataclass():
    """ElevationResult should store source and accuracy metadata."""
    result = ElevationResult(
        altitude_m=np.array([100.0, 101.0, 102.0]),
        source="usgs_3dep",
        accuracy_m=0.1,
    )
    assert result.source == "usgs_3dep"
    assert result.accuracy_m == 0.1
    assert len(result.altitude_m) == 3
```

**Step 7: Run full suite and commit**

Run: `source .venv/bin/activate && ruff check cataclysm/ tests/ backend/ && ruff format cataclysm/ tests/ backend/ && pytest tests/ -x -q`

```bash
git add cataclysm/elevation_service.py tests/test_elevation_service.py backend/api/services/pipeline.py
git commit -m "feat: add USGS 3DEP LIDAR elevation service

Queries the USGS National Map for LIDAR-grade elevation data
(5-15cm accuracy vs ~3m GPS altitude). Subsamples GPS trace,
queries in parallel with concurrency limit, interpolates back,
and caches per-track. Falls back to GPS altitude gracefully.
This enables detecting 20-40m compression features that the
120m GPS smoothing window attenuates."
```

---

## Summary of Changes

| Task | File(s) | Impact |
|------|---------|--------|
| 1. Fix Barber elevation | `track_db.py` | Correct 60m→24m data bug |
| 2. Friction circle exponent | `equipment.py` | Street 1.8 / slick 2.3 (was always 2.0) |
| 3. Drag coefficient | `vehicle_db.py`, `equipment.py` | ~0.06G drag at 100mph (was 0) |
| 4. Load sensitivity | `velocity_profile.py`, `equipment.py` | 4-8% lower cornering speeds |
| 5. Power-limited accel | `velocity_profile.py`, `equipment.py` | Realistic high-speed acceleration |
| 6. LIDAR elevation | New `elevation_service.py`, `pipeline.py` | 20x better vertical accuracy |

**Estimated error reduction:** From ~8-10% to ~3-5% for tracks with equipment configured. Tasks 1-5 require no external dependencies. Task 6 requires `httpx` (already in deps) and internet access for first LIDAR fetch.

**Dependencies between tasks:** None — all 6 tasks are independent and can be implemented in any order. The VehicleParams fields accumulate across Tasks 2-5 but don't conflict.

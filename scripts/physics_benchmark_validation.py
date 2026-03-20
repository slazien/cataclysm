#!/usr/bin/env python3
"""Multi-car benchmark validation: prove solver predictions are physically plausible.

For ~12 cars spanning the performance spectrum (Miata NA → Corvette C8 Z06),
predicts lap times at all 3 tracks and validates:
  - Correct relative ranking (faster cars = faster times)
  - Plausible absolute times
  - Power-to-weight vs. lap time correlation
  - Mu sensitivity: street → R-comp shows expected improvement

Runs WITHOUT the backend — uses the cataclysm library directly on canonical
track references.
"""

from __future__ import annotations

import csv
import math
import os
import sys
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cataclysm.equipment import (
    _CATEGORY_ACCEL_G,
    CATEGORY_BRAKING_MU_RATIO,
    CATEGORY_FRICTION_CIRCLE_EXPONENT,
    CATEGORY_GRIP_UTILIZATION,
    CATEGORY_LATERAL_JERK_GS,
    CATEGORY_LLTD_PENALTY,
    CATEGORY_LOAD_SENSITIVITY_EXPONENT,
    CATEGORY_MU_DEFAULTS,
    CATEGORY_PEAK_SLIP_ANGLE_DEG,
    CATEGORY_THERMAL_PENALTY,
    TireCompoundCategory,
)
from cataclysm.track_db import lookup_track
from cataclysm.track_reference import get_track_reference
from cataclysm.vehicle_db import VehicleSpec, find_vehicle
from cataclysm.velocity_profile import G, VehicleParams, compute_optimal_profile

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_BRAKE_EFFICIENCY = 0.95
_AIR_DENSITY = 1.225
_DRIVETRAIN_EFFICIENCY: dict[str, float] = {"RWD": 0.85, "FWD": 0.88, "AWD": 0.80}
_DRIVETRAIN_TRACTION_MULTIPLIER: dict[str, float] = {"RWD": 1.0, "FWD": 1.0, "AWD": 1.05}
_AERO_EFFICIENCY = 0.85  # real-world aero efficiency

# ---------------------------------------------------------------------------
# Benchmark car selection — spanning the performance spectrum
# ---------------------------------------------------------------------------

# (make, model, generation_or_None, label)
BENCHMARK_CARS: list[tuple[str, str, str | None, str]] = [
    ("Mazda", "Miata", "NA", "Miata NA (116hp, 960kg)"),
    ("Toyota", "MR2 Spyder", None, "MR2 Spyder (138hp, 975kg)"),
    ("Mazda", "Miata", "ND", "Miata ND (181hp, 1058kg)"),
    ("Lotus", "Elise", None, "Elise S2 (189hp, 860kg)"),
    ("Toyota", "GR86", None, "GR86 (228hp, 1270kg)"),
    ("Honda", "Civic Type R", "FL5", "Civic Type R FL5 (315hp, 1426kg)"),
    ("Porsche", "Cayman GT4", "718", "Cayman GT4 718 (414hp, 1450kg)"),
    ("BMW", "M2", "G87", "BMW M2 G87 (453hp, 1710kg)"),
    ("Ford", "Mustang GT", "S550", "Mustang GT S550 (460hp, 1720kg)"),
    ("Porsche", "911 Carrera S", "992", "911 992S (443hp, 1535kg)"),
    ("Porsche", "911 GT3", "992", "911 GT3 992 (502hp, 1435kg)"),
    ("Chevrolet", "Corvette Z06", "C8", "Corvette C8 Z06 (670hp, 1507kg)"),
]

# Expected approximate ranking (by index) — lower index = slower car.
# Ties are acceptable for close cars but major inversions are failures.

TRACKS_TO_TEST: list[str] = [
    "Barber Motorsports Park",
    "Atlanta Motorsports Park",
    "Roebling Road Raceway",
]


@dataclass
class BenchmarkResult:
    """Predicted lap time for one car at one track."""

    car_label: str
    make: str
    model: str
    track: str
    lap_time_s: float
    mu: float
    compound: str
    hp: int
    weight_kg: float
    pw_ratio: float  # hp per tonne
    drivetrain: str


@dataclass
class MuSweepResult:
    """Lap time for one car at one track across different mu values."""

    car_label: str
    track: str
    compound: str
    mu: float
    lap_time_s: float
    pct_vs_street: float  # % faster than street compound


def _vehicle_spec_to_params(
    spec: VehicleSpec,
    compound: TireCompoundCategory = TireCompoundCategory.ENDURANCE_200TW,
) -> VehicleParams:
    """Build VehicleParams from a VehicleSpec + tire compound.

    Mirrors the logic in equipment.equipment_to_vehicle_params() but works
    directly from VehicleSpec without needing an EquipmentProfile.
    """
    mu_raw = CATEGORY_MU_DEFAULTS[compound]
    grip_util = CATEGORY_GRIP_UTILIZATION.get(compound, 0.96)
    thermal = CATEGORY_THERMAL_PENALTY.get(compound, 1.00)
    lltd = CATEGORY_LLTD_PENALTY.get(compound, 1.00)
    mu = mu_raw * grip_util * thermal * lltd
    weight_kg = spec.weight_kg

    # Acceleration from drivetrain power-to-weight ratio

    base_accel_g = _CATEGORY_ACCEL_G[compound]
    pw_ratio = spec.hp / (weight_kg / 1000.0)
    pw_factor = min(pw_ratio / 200.0, 1.5)
    accel_g = base_accel_g * max(pw_factor, 0.7)

    # Aerodynamic drag
    drag_coeff = 0.0
    if spec.cd_a > 0:
        drag_coeff = spec.cd_a * _AIR_DENSITY / (2.0 * weight_kg)

    # Aerodynamic downforce
    aero_coeff = 0.0
    if spec.cl_a > 0 and weight_kg > 0:
        aero_coeff = 0.5 * _AIR_DENSITY * spec.cl_a * _AERO_EFFICIENCY / (weight_kg * G)

    # Braking mu ratio (friction ellipse)
    braking_ratio = CATEGORY_BRAKING_MU_RATIO.get(compound, 1.10)
    slip_angle_deg = CATEGORY_PEAK_SLIP_ANGLE_DEG.get(compound, 6.0)
    cornering_drag = math.sin(math.radians(slip_angle_deg))
    lateral_jerk = CATEGORY_LATERAL_JERK_GS.get(compound, 5.0)

    # Wheel power
    dt_eff = _DRIVETRAIN_EFFICIENCY.get(spec.drivetrain, 0.85)
    wheel_power_w = spec.hp * 745.7 * dt_eff
    traction_mult = _DRIVETRAIN_TRACTION_MULTIPLIER.get(spec.drivetrain, 1.0)

    return VehicleParams(
        mu=mu,
        max_lateral_g=mu,
        max_accel_g=accel_g,
        max_decel_g=mu * braking_ratio * _BRAKE_EFFICIENCY,
        top_speed_mps=80.0,
        friction_circle_exponent=CATEGORY_FRICTION_CIRCLE_EXPONENT[compound],
        drag_coefficient=drag_coeff,
        aero_coefficient=aero_coeff,
        braking_mu_ratio=braking_ratio,
        load_sensitivity_exponent=CATEGORY_LOAD_SENSITIVITY_EXPONENT[compound],
        cg_height_m=spec.cg_height_m,
        track_width_m=0.5 * (spec.track_width_front_m + spec.track_width_rear_m),
        wheel_power_w=wheel_power_w,
        mass_kg=weight_kg,
        cornering_drag_factor=cornering_drag,
        max_lateral_jerk_gs=lateral_jerk,
        traction_multiplier=traction_mult,
        power_band_factor=spec.power_band_factor,
    )


def run_benchmarks() -> tuple[list[BenchmarkResult], list[MuSweepResult]]:
    """Run all cars across all tracks, return results."""
    results: list[BenchmarkResult] = []
    mu_sweep: list[MuSweepResult] = []

    # Load track references
    from cataclysm.curvature import CurvatureResult
    from cataclysm.track_db import TrackLayout

    track_data: dict[str, tuple[CurvatureResult, TrackLayout]] = {}
    for track_name in TRACKS_TO_TEST:
        layout = lookup_track(track_name)
        if layout is None:
            print(f"  WARN: Track '{track_name}' not found in track_db, skipping")
            continue
        ref = get_track_reference(layout)
        if ref is None:
            print(f"  WARN: No canonical reference for '{track_name}', skipping")
            continue
        track_data[track_name] = (ref.curvature_result, layout)
        print(f"  Loaded: {track_name} ({ref.track_length_m:.0f}m)")

    if not track_data:
        print("ERROR: No tracks loaded!")
        return results, mu_sweep

    # Load and validate benchmark cars
    loaded_cars: list[tuple[str, VehicleSpec]] = []
    default_compound = TireCompoundCategory.ENDURANCE_200TW
    default_mu = CATEGORY_MU_DEFAULTS[default_compound]
    print(f"\nBenchmark compound: {default_compound.value} (mu={default_mu:.2f})")
    print()

    for make, model, gen, label in BENCHMARK_CARS:
        spec = find_vehicle(make, model, gen)
        if spec is None:
            print(f"  WARN: Vehicle not found: {make} {model} {gen}, skipping")
            continue
        loaded_cars.append((label, spec))
        print(f"  Loaded: {label} — {spec.hp}hp, {spec.weight_kg}kg, {spec.drivetrain}")

    print(f"\n{'=' * 90}")
    print("BENCHMARK RESULTS")
    print(f"{'=' * 90}\n")

    # Run solver for each car × track combination
    for track_name, (curvature_result, _layout) in track_data.items():
        print(f"\n--- {track_name} ---")
        print(f"{'Car':<35} {'Lap Time':>10} {'HP':>5} {'Wt(kg)':>7} {'HP/t':>7} {'DT':>4}")
        print("-" * 75)

        for label, spec in loaded_cars:
            params = _vehicle_spec_to_params(spec, default_compound)
            optimal = compute_optimal_profile(curvature_result, params=params)
            pw = spec.hp / (spec.weight_kg / 1000.0)

            # Format lap time as M:SS.ss
            mins = int(optimal.lap_time_s // 60)
            secs = optimal.lap_time_s % 60
            time_str = f"{mins}:{secs:05.2f}"

            print(
                f"  {label:<33} {time_str:>10} {spec.hp:>5} "
                f"{spec.weight_kg:>7.0f} {pw:>7.1f} {spec.drivetrain:>4}"
            )

            results.append(
                BenchmarkResult(
                    car_label=label,
                    make=spec.make,
                    model=spec.model,
                    track=track_name,
                    lap_time_s=optimal.lap_time_s,
                    mu=CATEGORY_MU_DEFAULTS[default_compound],
                    compound=default_compound.value,
                    hp=spec.hp,
                    weight_kg=spec.weight_kg,
                    pw_ratio=pw,
                    drivetrain=spec.drivetrain,
                )
            )

    # Mu sensitivity sweep — pick 3 representative cars
    sweep_cars: list[tuple[str, str, str | None, str]] = [
        ("Mazda", "Miata", "ND", "Miata ND"),
        ("Toyota", "GR86", None, "GR86"),
        ("Porsche", "911 GT3", "992", "911 GT3 992"),
    ]
    sweep_compounds: list[TireCompoundCategory] = [
        TireCompoundCategory.STREET,
        TireCompoundCategory.ENDURANCE_200TW,
        TireCompoundCategory.SUPER_200TW,
        TireCompoundCategory.R_COMPOUND,
    ]

    print(f"\n\n{'=' * 90}")
    print("MU SENSITIVITY SWEEP")
    print(f"{'=' * 90}")

    for make, model, gen, label in sweep_cars:
        spec = find_vehicle(make, model, gen)
        if spec is None:
            continue

        print(f"\n--- {label} ({spec.hp}hp, {spec.weight_kg}kg) ---")

        for track_name, (curvature_result, _) in track_data.items():
            print(f"\n  {track_name}:")
            print(f"  {'Compound':<18} {'Mu':>5} {'Lap Time':>10} {'vs Street':>10}")
            print(f"  {'-' * 50}")

            street_time: float | None = None
            for compound in sweep_compounds:
                params = _vehicle_spec_to_params(spec, compound)
                optimal = compute_optimal_profile(curvature_result, params=params)

                if compound == TireCompoundCategory.STREET:
                    street_time = optimal.lap_time_s

                pct_vs_street = 0.0
                if street_time is not None and street_time > 0:
                    pct_vs_street = (1.0 - optimal.lap_time_s / street_time) * 100

                mins = int(optimal.lap_time_s // 60)
                secs = optimal.lap_time_s % 60
                time_str = f"{mins}:{secs:05.2f}"
                delta_str = f"-{pct_vs_street:.1f}%" if pct_vs_street > 0 else "baseline"

                mu_val = CATEGORY_MU_DEFAULTS[compound]
                print(f"  {compound.value:<18} {mu_val:>5.2f} {time_str:>10} {delta_str:>10}")

                mu_sweep.append(
                    MuSweepResult(
                        car_label=label,
                        track=track_name,
                        compound=compound.value,
                        mu=mu_val,
                        lap_time_s=optimal.lap_time_s,
                        pct_vs_street=pct_vs_street,
                    )
                )

    return results, mu_sweep


def validate_results(results: list[BenchmarkResult]) -> None:
    """Check ranking correctness, absolute plausibility, and P-W correlation."""
    print(f"\n\n{'=' * 90}")
    print("VALIDATION CHECKS")
    print(f"{'=' * 90}")

    tracks = sorted(set(r.track for r in results))
    issues: list[str] = []

    # --- Check 1: Ranking per track ---
    print("\n1. RANKING VALIDATION (should match expected performance order)")

    for track in tracks:
        track_results = sorted(
            [r for r in results if r.track == track],
            key=lambda r: r.lap_time_s,
            reverse=True,  # slowest first
        )
        print(f"\n  {track} (slowest → fastest):")
        for i, r in enumerate(track_results, 1):
            mins = int(r.lap_time_s // 60)
            secs = r.lap_time_s % 60
            print(f"    {i:>2}. {r.car_label:<35} {mins}:{secs:05.2f}  ({r.pw_ratio:.0f} hp/t)")

        # Check for obvious inversions — e.g., Miata faster than GT3
        labels = [r.car_label for r in track_results]
        for slow_car, fast_car in [
            ("Miata NA", "GT3"),
            ("Miata NA", "Z06"),
            ("GR86", "GT3"),
            ("Miata ND", "911"),
        ]:
            slow_idx = next((idx for idx, lbl in enumerate(labels) if slow_car in lbl), None)
            fast_idx = next((idx for idx, lbl in enumerate(labels) if fast_car in lbl), None)
            if slow_idx is not None and fast_idx is not None and slow_idx > fast_idx:
                issues.append(f"RANKING INVERSION at {track}: {slow_car} faster than {fast_car}")

    # --- Check 2: Absolute lap time plausibility ---
    print("\n2. ABSOLUTE LAP TIME PLAUSIBILITY")

    # Rough expected ranges (in seconds) for physics-optimal times.
    # These are OPTIMAL (100% of limit), so faster than any amateur would achieve.
    # Real pros on R-comps get close; our endurance_200tw baseline should be moderately slower.
    plausibility: dict[str, tuple[float, float]] = {
        "Barber Motorsports Park": (70.0, 160.0),  # ~1:10 to ~2:40
        "Atlanta Motorsports Park": (55.0, 130.0),  # ~0:55 to ~2:10
        "Roebling Road Raceway": (60.0, 140.0),  # ~1:00 to ~2:20
    }

    for track in tracks:
        track_results = [r for r in results if r.track == track]
        times = [r.lap_time_s for r in track_results]
        lo, hi = plausibility.get(track, (50.0, 200.0))
        out_of_range = [r for r in track_results if r.lap_time_s < lo or r.lap_time_s > hi]

        if out_of_range:
            for r in out_of_range:
                issues.append(
                    f"OUT OF RANGE at {track}: {r.car_label} = "
                    f"{r.lap_time_s:.1f}s (expected {lo:.0f}-{hi:.0f}s)"
                )
            print(f"  {track}: FAIL — {len(out_of_range)} cars outside plausible range")
        else:
            fastest = min(times)
            slowest = max(times)
            print(
                f"  {track}: PASS — "
                f"range [{fastest:.1f}s, {slowest:.1f}s] within [{lo:.0f}s, {hi:.0f}s]"
            )

    # --- Check 3: Power-to-weight correlation ---
    print("\n3. POWER-TO-WEIGHT CORRELATION")

    for track in tracks:
        track_results = [r for r in results if r.track == track]
        pw = np.array([r.pw_ratio for r in track_results])
        times_arr = np.array([r.lap_time_s for r in track_results])

        # Compute R² — higher pw_ratio should correlate with lower lap time
        if len(pw) > 2:
            correlation = float(np.corrcoef(pw, times_arr)[0, 1])
            r_squared = float(correlation**2)
            sign = "negative" if correlation < 0 else "POSITIVE (wrong direction!)"

            status = "PASS" if r_squared > 0.5 and correlation < 0 else "WARN"
            if correlation > 0:
                status = "FAIL"
                issues.append(
                    f"PW CORRELATION INVERTED at {track}: R²={r_squared:.3f}, "
                    f"correlation={correlation:.3f}"
                )

            print(
                f"  {track}: {status} — R²={r_squared:.3f}, correlation={correlation:.3f} ({sign})"
            )

    # --- Check 4: Spread between slowest and fastest ---
    print("\n4. PERFORMANCE SPREAD (Miata NA vs C8 Z06)")

    for track in tracks:
        track_results = [r for r in results if r.track == track]
        time_map = {r.car_label: r.lap_time_s for r in track_results}

        miata_label = next((lbl for lbl in time_map if "Miata NA" in lbl), None)
        z06_label = next((lbl for lbl in time_map if "C8 Z06" in lbl), None)

        if miata_label and z06_label:
            delta = time_map[miata_label] - time_map[z06_label]
            pct = (delta / time_map[miata_label]) * 100
            status = "PASS" if 10 < delta < 60 else "WARN"
            print(f"  {track}: {status} — delta={delta:.1f}s ({pct:.1f}%)")
        else:
            print(f"  {track}: SKIP — missing Miata NA or C8 Z06")

    # --- Verdict ---
    print(f"\n{'-' * 90}")
    if issues:
        print(f"ISSUES FOUND ({len(issues)}):")
        for issue in issues:
            print(f"  !! {issue}")
    else:
        print("ALL CHECKS PASS — Solver produces physically plausible, correctly ranked lap times.")
    print(f"{'-' * 90}")


def validate_mu_sweep(mu_results: list[MuSweepResult]) -> None:
    """Check that grip improvements produce expected lap time reductions."""
    print(f"\n\n{'=' * 90}")
    print("MU SWEEP VALIDATION")
    print(f"{'=' * 90}")

    issues: list[str] = []

    # Group by car × track
    keys = sorted(set((r.car_label, r.track) for r in mu_results))
    for car_label, track in keys:
        group = [r for r in mu_results if r.car_label == car_label and r.track == track]
        r_comp = next((r for r in group if "r_comp" in r.compound), None)

        if r_comp is not None:
            pct = r_comp.pct_vs_street
            # Physics-optimal sensitivity: mu 0.85→1.35 = +59% grip.
            # Cornering speed ~ sqrt(mu), so ~26% speed gain.
            # Compounding with braking/accel gives 15-25% total lap time.
            # Real-world amateur improvement is less (5-10%) because drivers
            # don't fully exploit extra grip.  Here we validate physics limit.
            if pct < 10.0:
                issues.append(
                    f"MU SENSITIVITY TOO LOW: {car_label} at {track}: "
                    f"R-comp only {pct:.1f}% faster than street (expected 15-25%)"
                )
            elif pct > 30.0:
                issues.append(
                    f"MU SENSITIVITY TOO HIGH: {car_label} at {track}: "
                    f"R-comp {pct:.1f}% faster than street (expected 15-25%)"
                )

    if issues:
        print(f"\nISSUES ({len(issues)}):")
        for issue in issues:
            print(f"  !! {issue}")
    else:
        print(
            "\nPASS — Mu sensitivity in expected 15-25% range for street → R-comp at physics limit."
        )


def export_csv(
    results: list[BenchmarkResult],
    mu_results: list[MuSweepResult],
) -> None:
    """Export results to CSV for external plotting."""
    benchmark_path = os.path.join(OUTPUT_DIR, "benchmark_laptimes.csv")
    mu_path = os.path.join(OUTPUT_DIR, "benchmark_mu_sweep.csv")

    with open(benchmark_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "car_label",
                "make",
                "model",
                "track",
                "lap_time_s",
                "mu",
                "compound",
                "hp",
                "weight_kg",
                "pw_ratio",
                "drivetrain",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.car_label,
                    r.make,
                    r.model,
                    r.track,
                    f"{r.lap_time_s:.2f}",
                    f"{r.mu:.2f}",
                    r.compound,
                    r.hp,
                    f"{r.weight_kg:.0f}",
                    f"{r.pw_ratio:.1f}",
                    r.drivetrain,
                ]
            )
    print(f"\nExported benchmarks CSV: {benchmark_path}")

    with open(mu_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "car_label",
                "track",
                "compound",
                "mu",
                "lap_time_s",
                "pct_vs_street",
            ]
        )
        for mr in mu_results:
            writer.writerow(
                [
                    mr.car_label,
                    mr.track,
                    mr.compound,
                    f"{mr.mu:.2f}",
                    f"{mr.lap_time_s:.2f}",
                    f"{mr.pct_vs_street:.1f}",
                ]
            )
    print(f"Exported mu sweep CSV: {mu_path}")


def main() -> None:
    print("=" * 90)
    print("PHYSICS BENCHMARK VALIDATION")
    print("Predicting lap times for 12 cars across 3 tracks")
    print("=" * 90)
    print()

    results, mu_results = run_benchmarks()

    if not results:
        print("\nNo results generated!")
        return

    validate_results(results)
    validate_mu_sweep(mu_results)
    export_csv(results, mu_results)


if __name__ == "__main__":
    main()

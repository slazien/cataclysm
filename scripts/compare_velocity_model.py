"""Compare old vs new velocity model grip calibration outputs.

Simulates the bug: old model diluted by below-limit cornering data → underestimates mu.
New model: min_lateral_g=0.3 filter + p95 → accurate tire limit.
"""

from __future__ import annotations

import numpy as np
import sys

# Make sure we use the project's cataclysm package
sys.path.insert(0, "/mnt/d/OneDrive/Dokumenty/vscode/cataclysm")

from cataclysm.grip_calibration import calibrate_grip_from_telemetry


def simulate_telemetry(
    rng: np.random.Generator,
    n_hard_corners: int = 400,   # near-limit cornering: 0.6-1.1G
    n_soft_corners: int = 600,   # below-limit (sweepers, lane changes): 0.05-0.28G
    n_braking: int = 300,
    n_accel: int = 200,
    noise_sigma: float = 0.05,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate telemetry with a mix of hard and soft cornering.

    The 'soft corners' represent sweeper sections, gentle chicanes, and
    highway-speed lane changes — real data a racing session contains.
    OLD model treated them as cornering events; NEW model filters them out.
    """
    lat_parts = []
    lon_parts = []

    # Hard cornering (near tire limit) — what we actually want to calibrate
    hard_lat = rng.uniform(0.6, 1.1, size=n_hard_corners) * rng.choice([-1, 1], size=n_hard_corners)
    hard_lon = rng.uniform(-0.15, 0.15, size=n_hard_corners)  # pure lateral
    lat_parts.append(hard_lat)
    lon_parts.append(hard_lon)

    # Soft cornering — dilutes OLD model's distribution
    soft_lat = rng.uniform(0.05, 0.28, size=n_soft_corners) * rng.choice([-1, 1], size=n_soft_corners)
    soft_lon = rng.uniform(-0.15, 0.15, size=n_soft_corners)  # still pure lateral
    lat_parts.append(soft_lat)
    lon_parts.append(soft_lon)

    # Braking events
    brake_lon = -rng.uniform(0.5, 1.1, size=n_braking)
    brake_lat = rng.uniform(-0.15, 0.15, size=n_braking)
    lat_parts.append(brake_lat)
    lon_parts.append(brake_lon)

    # Acceleration events
    accel_lon = rng.uniform(0.3, 0.6, size=n_accel)
    accel_lat = rng.uniform(-0.15, 0.15, size=n_accel)
    lat_parts.append(accel_lat)
    lon_parts.append(accel_lon)

    lat = np.concatenate(lat_parts) + rng.normal(0, noise_sigma, size=sum([n_hard_corners, n_soft_corners, n_braking, n_accel]))
    lon = np.concatenate(lon_parts) + rng.normal(0, noise_sigma, size=sum([n_hard_corners, n_soft_corners, n_braking, n_accel]))
    return lat, lon


def run_comparison() -> None:
    rng = np.random.default_rng(42)
    lat, lon = simulate_telemetry(rng)

    # --- OLD MODEL (p90, no min_lateral_g filter) ---
    old = calibrate_grip_from_telemetry(lat, lon, percentile=90.0, min_lateral_g=0.0)
    # --- NEW MODEL (p95, min_lateral_g=0.3) ---
    new = calibrate_grip_from_telemetry(lat, lon, percentile=95.0, min_lateral_g=0.3)

    print("=" * 60)
    print("Velocity Model Grip Calibration: Old vs New")
    print("=" * 60)
    print(f"\nSimulated telemetry:")
    print(f"  Hard cornering (0.6–1.1G): 400 samples")
    print(f"  Soft cornering (0.05–0.28G, sweepers): 600 samples")
    print(f"  Braking: 300 samples | Acceleration: 200 samples")

    if old is None or new is None:
        print("\nERROR: calibration returned None")
        return

    # Count samples that pass old vs new lat filter
    lat_mask_old = (np.abs(lon) < 0.2) & (np.abs(lat) >= 0.0)
    lat_mask_new = (np.abs(lon) < 0.2) & (np.abs(lat) >= 0.3)
    print(f"\nLateral samples used:")
    print(f"  OLD filter (|lat| >= 0.0G): {lat_mask_old.sum()} samples")
    print(f"  NEW filter (|lat| >= 0.3G): {lat_mask_new.sum()} samples")
    print(f"  Soft cornering excluded by new filter: {lat_mask_old.sum() - lat_mask_new.sum()} samples")

    print(f"\nCalibrated max_lateral_g (mu):")
    print(f"  OLD model (p90, no floor): {old.max_lateral_g:.3f}G")
    print(f"  NEW model (p95, >=0.3G):   {new.max_lateral_g:.3f}G")
    print(f"  Improvement: +{new.max_lateral_g - old.max_lateral_g:.3f}G "
          f"({(new.max_lateral_g/old.max_lateral_g - 1)*100:.1f}%)")

    # True tire limit in simulation is uniform(0.6, 1.1) → mean=0.85, p95≈1.05
    # The "correct" calibration should find ~1.0G (p95 of hard corners only)
    hard_lat_vals = np.abs(lat[(np.abs(lat) >= 0.3) & (np.abs(lon) < 0.2)])
    true_p95 = float(np.percentile(hard_lat_vals, 95)) if len(hard_lat_vals) > 0 else 0.0
    print(f"  True p95 (hard corners only): {true_p95:.3f}G  ← ground truth")

    print(f"\nCalibrated braking / acceleration:")
    print(f"  OLD braking:  {old.max_brake_g:.3f}G  | NEW: {new.max_brake_g:.3f}G")
    print(f"  OLD accel:    {old.max_accel_g:.3f}G    | NEW: {new.max_accel_g:.3f}G")
    print(f"  (braking/accel unaffected by min_lateral_g filter)")

    # Estimate optimal corner speed at a representative corner:
    #   Using circular approximation: v = sqrt(mu * g * R)
    #   For R=50m (typical hairpin), g=9.81 m/s^2
    R = 50.0
    g = 9.81
    v_old = (old.max_lateral_g * g * R) ** 0.5 * 3.6  # km/h
    v_new = (new.max_lateral_g * g * R) ** 0.5 * 3.6
    v_true = (true_p95 * g * R) ** 0.5 * 3.6
    print(f"\nPredicted optimal corner speed (R={R}m hairpin):")
    print(f"  OLD model: {v_old:.1f} km/h")
    print(f"  NEW model: {v_new:.1f} km/h")
    print(f"  True p95:  {v_true:.1f} km/h")
    print(f"  OLD under-prediction error: -{v_true - v_old:.1f} km/h")
    print(f"  NEW under-prediction error: -{max(0, v_true - v_new):.1f} km/h")

    print(f"\nConclusion:")
    if new.max_lateral_g > old.max_lateral_g + 0.05:
        print(f"  ✓ NEW model corrects systematic under-prediction.")
        print(f"  ✓ Mu raised from {old.max_lateral_g:.3f} → {new.max_lateral_g:.3f}G")
        print(f"  ✓ Corner speed prediction improved by {v_new - v_old:.1f} km/h")
        if abs(new.max_lateral_g - true_p95) < abs(old.max_lateral_g - true_p95):
            print(f"  ✓ Closer to ground truth (true p95={true_p95:.3f}G)")
    else:
        print(f"  ✗ Models converged — check if soft_corner dilution was sufficient")
    print("=" * 60)

    # --- Scenario 2: Real-world typical session ---
    print("\n\nScenario 2: Typical track day (more soft corners, typical ratio)")
    print("-" * 60)
    rng2 = np.random.default_rng(123)
    lat2, lon2 = simulate_telemetry(
        rng2,
        n_hard_corners=200,   # fewer hard corners (short session)
        n_soft_corners=1200,  # lots of sweepers on a flowing track
    )
    old2 = calibrate_grip_from_telemetry(lat2, lon2, percentile=90.0, min_lateral_g=0.0)
    new2 = calibrate_grip_from_telemetry(lat2, lon2, percentile=95.0, min_lateral_g=0.3)
    if old2 and new2:
        print(f"  OLD: {old2.max_lateral_g:.3f}G | NEW: {new2.max_lateral_g:.3f}G | "
              f"Delta: +{new2.max_lateral_g - old2.max_lateral_g:.3f}G")
        print(f"  Confidence: OLD={old2.confidence} | NEW={new2.confidence}")

    # --- Scenario 3: Short session (fewer laps) ---
    print("\nScenario 3: Short session (100 hard, 400 soft corners)")
    rng3 = np.random.default_rng(999)
    lat3, lon3 = simulate_telemetry(rng3, n_hard_corners=100, n_soft_corners=400)
    old3 = calibrate_grip_from_telemetry(lat3, lon3, percentile=90.0, min_lateral_g=0.0)
    new3 = calibrate_grip_from_telemetry(lat3, lon3, percentile=95.0, min_lateral_g=0.3)
    if old3 and new3:
        print(f"  OLD: {old3.max_lateral_g:.3f}G | NEW: {new3.max_lateral_g:.3f}G | "
              f"Delta: +{new3.max_lateral_g - old3.max_lateral_g:.3f}G")
        print(f"  Confidence: OLD={old3.confidence} | NEW={new3.confidence}")


if __name__ == "__main__":
    run_comparison()

"""Analyze Roebling Road telemetry to determine correct corner fractions.

Parses the reference session, finds speed minimums and heading-rate peaks
for the best lap, and compares them against current track_db.py fractions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cataclysm.engine import process_session
from cataclysm.parser import parse_racechrono_csv
from cataclysm.track_db import ROEBLING_ROAD_RACEWAY

SESSION_FILE = (
    Path(__file__).resolve().parent.parent
    / "data/session/roebling_road_raceway/session_20260111_075431_roebling_road_v3.csv"
)

# Current fractions from track_db.py for comparison
CURRENT_FRACTIONS = {
    c.number: (c.name, c.fraction, c.direction) for c in ROEBLING_ROAD_RACEWAY.corners
}


def main() -> None:
    print(f"Loading session: {SESSION_FILE.name}")
    parsed = parse_racechrono_csv(str(SESSION_FILE))
    processed = process_session(parsed.data)
    best_lap = processed.best_lap
    print(f"Best lap: #{best_lap}")

    lap_df = processed.resampled_laps[best_lap]
    dist = lap_df["lap_distance_m"].to_numpy()
    speed = lap_df["speed_mps"].to_numpy()
    lat = lap_df["lat"].to_numpy()
    lon = lap_df["lon"].to_numpy()
    heading = lap_df["heading_deg"].to_numpy()
    yaw_rate = lap_df["yaw_rate_dps"].to_numpy()

    lap_length = dist[-1]
    print(f"Lap distance: {lap_length:.1f} m")

    # --- Speed minimums (corner apexes) ---
    # Invert speed to find minimums as peaks
    # Use prominence and distance to filter noise
    neg_speed = -speed
    speed_peaks, speed_props = find_peaks(
        neg_speed,
        prominence=2.0,  # At least 2 m/s slower than surroundings
        distance=100,  # At least 100 samples apart (~70m at 0.7m step)
    )

    print("\n" + "=" * 90)
    print("SPEED MINIMUMS (corner apexes)")
    print("=" * 90)
    print(
        f"{'Idx':>5} | {'Dist(m)':>8} | {'Frac':>6} | {'Speed(mph)':>10} | "
        f"{'Lat':>10} | {'Lon':>11} | {'Hdg':>5} | {'YawRate':>8}"
    )
    print("-" * 90)

    for idx in speed_peaks:
        frac = dist[idx] / lap_length
        speed_mph = speed[idx] * 2.237
        print(
            f"{idx:5d} | {dist[idx]:8.1f} | {frac:6.3f} | {speed_mph:10.1f} | "
            f"{lat[idx]:10.6f} | {lon[idx]:11.6f} | {heading[idx]:5.0f} | "
            f"{yaw_rate[idx]:8.1f}"
        )

    # --- Heading rate peaks (maximum turning) ---
    abs_yaw = np.abs(yaw_rate)
    yaw_peaks, yaw_props = find_peaks(
        abs_yaw,
        prominence=5.0,  # At least 5 deg/s more than surroundings
        distance=100,
    )

    print("\n" + "=" * 90)
    print("HEADING-RATE PEAKS (maximum turning points)")
    print("=" * 90)
    print(
        f"{'Idx':>5} | {'Dist(m)':>8} | {'Frac':>6} | {'YawRate':>8} | "
        f"{'Speed(mph)':>10} | {'Lat':>10} | {'Lon':>11} | {'Hdg':>5} | {'Dir':>5}"
    )
    print("-" * 90)

    for idx in yaw_peaks:
        frac = dist[idx] / lap_length
        speed_mph = speed[idx] * 2.237
        direction = "LEFT" if yaw_rate[idx] < 0 else "RIGHT"
        print(
            f"{idx:5d} | {dist[idx]:8.1f} | {frac:6.3f} | {yaw_rate[idx]:8.1f} | "
            f"{speed_mph:10.1f} | {lat[idx]:10.6f} | {lon[idx]:11.6f} | "
            f"{heading[idx]:5.0f} | {direction:>5}"
        )

    # --- Current track_db.py fractions ---
    print("\n" + "=" * 90)
    print("CURRENT track_db.py FRACTIONS")
    print("=" * 90)
    print(f"{'Corner':>7} | {'Name':<25} | {'Frac':>6} | {'Dir':>5} | {'Dist(m)':>8}")
    print("-" * 90)

    for num in sorted(CURRENT_FRACTIONS.keys()):
        name, frac, direction = CURRENT_FRACTIONS[num]
        dist_m = frac * lap_length
        print(f"  T{num:<5} | {name:<25} | {frac:6.3f} | {direction or '?':>5} | {dist_m:8.1f}")

    # --- Cross-reference: for each current corner, find nearest speed minimum ---
    print("\n" + "=" * 90)
    print("CROSS-REFERENCE: Current corners vs nearest speed minimum")
    print("=" * 90)
    print(
        f"{'Corner':>7} | {'CurFrac':>7} | {'CurDist':>8} | "
        f"{'NearestMin':>10} | {'MinFrac':>7} | {'MinDist':>8} | "
        f"{'Delta(m)':>8} | {'MinSpd(mph)':>11}"
    )
    print("-" * 90)

    for num in sorted(CURRENT_FRACTIONS.keys()):
        name, frac, direction = CURRENT_FRACTIONS[num]
        cur_dist = frac * lap_length
        # Find nearest speed minimum
        if len(speed_peaks) > 0:
            peak_dists = dist[speed_peaks]
            nearest_idx = np.argmin(np.abs(peak_dists - cur_dist))
            near_peak = speed_peaks[nearest_idx]
            min_dist = dist[near_peak]
            min_frac = min_dist / lap_length
            delta = min_dist - cur_dist
            min_speed_mph = speed[near_peak] * 2.237
            print(
                f"  T{num:<5} | {frac:7.3f} | {cur_dist:8.1f} | "
                f"{nearest_idx:10d} | {min_frac:7.3f} | {min_dist:8.1f} | "
                f"{delta:8.1f} | {min_speed_mph:11.1f}"
            )

    # --- Detailed lap trace for manual inspection ---
    print("\n" + "=" * 90)
    print("LAP TRACE (sampled every 50m for manual inspection)")
    print("=" * 90)
    print(
        f"{'Dist(m)':>8} | {'Frac':>6} | {'Speed(mph)':>10} | "
        f"{'Lat':>10} | {'Lon':>11} | {'Hdg':>5} | {'YawRate':>8}"
    )
    print("-" * 90)

    sample_step = 50  # meters
    for target_dist in np.arange(0, lap_length, sample_step):
        idx = np.argmin(np.abs(dist - target_dist))
        frac = dist[idx] / lap_length
        speed_mph = speed[idx] * 2.237
        print(
            f"{dist[idx]:8.1f} | {frac:6.3f} | {speed_mph:10.1f} | "
            f"{lat[idx]:10.6f} | {lon[idx]:11.6f} | {heading[idx]:5.0f} | "
            f"{yaw_rate[idx]:8.1f}"
        )


if __name__ == "__main__":
    main()

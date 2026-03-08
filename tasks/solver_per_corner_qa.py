#!/usr/bin/env python3
"""Per-corner QA: replicate production pipeline locally and validate solver output.

Traces through every corner on every track, checking that the solver's
optimal speed makes physical sense for an HPDE3 driver.

Runs WITHOUT the backend — uses the cataclysm library directly.
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cataclysm.constants import MPS_TO_MPH
from cataclysm.corners import Corner, extract_corner_kpis_for_lap
from cataclysm.curvature import CurvatureResult, compute_curvature
from cataclysm.elevation_profile import compute_gradient_array, compute_vertical_curvature
from cataclysm.engine import process_session
from cataclysm.grip_calibration import (
    apply_calibration_to_params,
    calibrate_grip_from_telemetry,
    calibrate_per_corner_grip,
)
from cataclysm.linked_corners import detect_linked_corners
from cataclysm.optimal_comparison import (
    APEX_WINDOW_FRACTION,
    MIN_APEX_WINDOW_M,
    compare_with_optimal,
)
from cataclysm.parser import parse_racechrono_csv
from cataclysm.track_db import locate_official_corners
from cataclysm.track_match import detect_track_or_lookup
from cataclysm.track_reference import (
    align_reference_to_session,
    get_track_reference,
    track_slug_from_layout,
)
from cataclysm.velocity_profile import (
    compute_optimal_profile,
    default_vehicle_params,
)

G_ACCEL = 9.81
SESSION_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "session")


def _build_mu_array(
    distance_m: np.ndarray,
    corners: list[Corner],
    per_corner_mu: dict[int, float],
    global_mu: float,
) -> np.ndarray:
    """Replicate pipeline._build_mu_array."""
    mu_arr = np.full(len(distance_m), global_mu, dtype=np.float64)
    for corner in corners:
        if corner.number not in per_corner_mu:
            continue
        corner_mu = max(global_mu, per_corner_mu[corner.number])
        mask = (distance_m >= corner.entry_distance_m) & (distance_m <= corner.exit_distance_m)
        mu_arr[mask] = corner_mu
    return mu_arr


def _implied_mu_from_corners(
    corners: list[Corner],
    curvature_result: CurvatureResult,
) -> dict[int, float]:
    """Replicate pipeline._implied_mu_from_corners (max curvature in apex window)."""
    result: dict[int, float] = {}
    for corner in corners:
        zone_width = corner.exit_distance_m - corner.entry_distance_m
        half_win = max(zone_width * APEX_WINDOW_FRACTION, MIN_APEX_WINDOW_M)
        apex_start = max(corner.apex_distance_m - half_win, corner.entry_distance_m)
        apex_end = min(corner.apex_distance_m + half_win, corner.exit_distance_m)
        apex_mask = (curvature_result.distance_m >= apex_start) & (
            curvature_result.distance_m <= apex_end
        )
        if not apex_mask.any():
            continue
        kappa_max = float(np.max(curvature_result.abs_curvature[apex_mask]))
        if kappa_max < 1e-4:
            continue
        mu = corner.min_speed_mps**2 * kappa_max / G_ACCEL
        result[corner.number] = mu
    return result


def pick_best_session(csv_files: list[str]) -> tuple[str, float]:
    """Pick the session with the fastest best lap (lowest lap time)."""
    best_file = None
    best_time = float("inf")
    for csv_path in csv_files:
        try:
            parsed = parse_racechrono_csv(csv_path)
            processed = process_session(parsed.data)
            t = processed.lap_summaries[processed.best_lap - 1].lap_time_s
            if t < best_time:
                best_time = t
                best_file = csv_path
        except Exception as e:
            print(f"  SKIP {os.path.basename(csv_path)}: {e}")
    return best_file, best_time  # type: ignore[return-value]


def analyze_session(csv_path: str) -> None:
    """Full pipeline replication for one session file."""
    basename = os.path.basename(csv_path)
    print(f"\n{'=' * 70}")
    print(f"Session: {basename}")
    print(f"{'=' * 70}")

    # 1. Parse & process
    parsed = parse_racechrono_csv(csv_path)
    processed = process_session(parsed.data)
    best_lap = processed.best_lap
    best_lap_df = processed.resampled_laps[best_lap]
    n_laps = len(processed.lap_summaries)
    best_time = processed.lap_summaries[best_lap - 1].lap_time_s

    print(f"  Laps: {n_laps}, Best lap: L{best_lap} ({best_time:.2f}s)")

    # 2. Detect track layout
    layout = detect_track_or_lookup(parsed.data, parsed.metadata.track_name)
    if layout is None:
        print("  !! No track layout found — skipping")
        return

    track_slug = track_slug_from_layout(layout)
    print(f"  Track: {layout.name} ({track_slug})")

    # 3. Get corners using official positions (production path)
    skeletons = locate_official_corners(best_lap_df, layout)
    corners = extract_corner_kpis_for_lap(best_lap_df, skeletons)
    print(f"  Corners: {len(corners)} official")

    if not corners:
        print("  !! 0 corners — cannot QA")
        return

    # 4. Get curvature — canonical track reference if available
    ref = get_track_reference(layout)
    if ref is not None:
        session_dist = best_lap_df["lap_distance_m"].to_numpy()
        curvature_result, resolved_alt = align_reference_to_session(ref, session_dist)
        n_avg = ref.n_laps_averaged
        q_score = ref.gps_quality_score
        print(f"  Curvature: canonical reference ({n_avg} laps, q={q_score:.1f})")
    else:
        curvature_result = compute_curvature(best_lap_df, savgol_window=15)
        resolved_alt = None
        print("  Curvature: per-session (no canonical reference)")

    # 5. Grip calibration (combine all coaching laps)
    coaching_laps = [
        ln for ln, s in enumerate(processed.lap_summaries, 1) if ln in processed.resampled_laps
    ]

    # Global calibration
    all_lat_g: list[np.ndarray] = []
    all_lon_g: list[np.ndarray] = []
    for lap_num in coaching_laps:
        lap_df = processed.resampled_laps.get(lap_num)
        if lap_df is None:
            continue
        if "lateral_g" not in lap_df.columns or "longitudinal_g" not in lap_df.columns:
            continue
        lat_g = lap_df["lateral_g"].to_numpy()
        lon_g = lap_df["longitudinal_g"].to_numpy()
        finite = np.isfinite(lat_g) & np.isfinite(lon_g)
        all_lat_g.append(lat_g[finite])
        all_lon_g.append(lon_g[finite])

    base_params = default_vehicle_params()
    if all_lat_g:
        grip = calibrate_grip_from_telemetry(
            np.concatenate(all_lat_g),
            np.concatenate(all_lon_g),
        )
        if grip is not None:
            vehicle_params = apply_calibration_to_params(base_params, grip)
            print(
                f"  Grip: mu={vehicle_params.mu:.3f} lat={grip.max_lateral_g:.3f} "
                f"brake={grip.max_brake_g:.3f} accel={grip.max_accel_g:.3f} "
                f"({grip.confidence})"
            )
        else:
            vehicle_params = base_params
            print("  Grip: calibration failed, using defaults")
    else:
        vehicle_params = base_params
        print("  Grip: no telemetry, using defaults")

    # 6. Per-corner mu + implied mu
    per_corner_mu: dict[int, float] = {}
    # Collect per-corner from lateral G across all coaching laps
    all_pcm_lat_g: list[np.ndarray] = []
    all_pcm_dist: list[np.ndarray] = []
    for lap_num in coaching_laps:
        lap_df = processed.resampled_laps.get(lap_num)
        if lap_df is None or "lateral_g" not in lap_df.columns:
            continue
        lat_g = lap_df["lateral_g"].to_numpy()
        dist = lap_df["lap_distance_m"].to_numpy()
        finite = np.isfinite(lat_g)
        all_pcm_lat_g.append(lat_g[finite])
        all_pcm_dist.append(dist[finite])

    if all_pcm_lat_g:
        per_corner_mu = calibrate_per_corner_grip(
            np.concatenate(all_pcm_lat_g),
            np.concatenate(all_pcm_dist),
            corners,
        )

    # Implied mu from driver's actual speed
    implied_mu = _implied_mu_from_corners(corners, curvature_result)
    for cn, mu in implied_mu.items():
        per_corner_mu[cn] = max(per_corner_mu.get(cn, 0.0), mu)

    mu_array = None
    if per_corner_mu:
        mu_array = _build_mu_array(
            curvature_result.distance_m,
            corners,
            per_corner_mu,
            vehicle_params.mu,
        )

    # 7. Elevation
    gradient_sin = None
    vert_curvature = None
    alt = resolved_alt
    if alt is None and "altitude_m" in best_lap_df.columns:
        alt = best_lap_df["altitude_m"].to_numpy()
    if alt is not None and not np.all(np.isnan(alt)):
        dist = best_lap_df["lap_distance_m"].to_numpy()
        gradient_sin = compute_gradient_array(alt, dist)
        vert_curvature = compute_vertical_curvature(alt, dist)
        g_min = float(np.min(gradient_sin))
        g_max = float(np.max(gradient_sin))
        print(f"  Elevation: gradient=[{g_min:.4f}, {g_max:.4f}]")

    # 8. Compute optimal profile
    optimal = compute_optimal_profile(
        curvature_result,
        params=vehicle_params,
        gradient_sin=gradient_sin,
        mu_array=mu_array,
        vertical_curvature=vert_curvature,
    )
    print(f"  Optimal lap: {optimal.lap_time_s:.2f}s")

    # 9. Compare with actual
    result = compare_with_optimal(best_lap_df, corners, optimal)
    gap_pct = (result.total_gap_s / result.actual_lap_time_s) * 100
    print(f"  Actual lap:  {result.actual_lap_time_s:.2f}s")
    print(f"  Gap: {result.total_gap_s:.2f}s ({gap_pct:.1f}%)")
    print(f"  Valid: {result.is_valid}", end="")
    if not result.is_valid:
        print(f" — {result.invalid_reasons}")
    else:
        print()

    # 10. Linked corners
    linked = detect_linked_corners(corners, optimal.optimal_speed_mps, optimal.distance_m)
    if linked.groups:
        group_strs = [
            f"G{g.group_id}=[{','.join(f'T{c}' for c in g.corner_numbers)}]" for g in linked.groups
        ]
        print(f"  Linked: {' '.join(group_strs)}")

    # 11. Per-corner detail
    print(
        f"\n  {'Corner':>8s} {'Act mph':>8s} {'Opt mph':>8s} {'Gap mph':>8s} "
        f"{'Time s':>7s} {'Brk gap':>8s} {'Zone mu':>8s} {'Impl mu':>8s} {'Flags':>12s}"
    )
    print(
        f"  {'-' * 8:>8s} {'-' * 8:>8s} {'-' * 8:>8s} {'-' * 8:>8s} "
        f"{'-' * 7:>7s} {'-' * 8:>8s} {'-' * 8:>8s} {'-' * 8:>8s} {'-' * 12:>12s}"
    )

    issues = []
    for opp in result.corner_opportunities:
        cn = opp.corner_number
        act_mph = opp.actual_min_speed_mps * MPS_TO_MPH
        opt_mph = opp.optimal_min_speed_mps * MPS_TO_MPH
        gap_mph = opp.speed_gap_mph
        time_s = opp.time_cost_s
        brk = f"{opp.brake_gap_m:+.1f}" if opp.brake_gap_m is not None else "—"
        z_mu = f"{per_corner_mu.get(cn, 0):.3f}" if cn in per_corner_mu else "—"
        i_mu = f"{implied_mu.get(cn, 0):.3f}" if cn in implied_mu else "—"
        group = linked.corner_to_group.get(cn)

        flags = []
        if gap_mph < -0.5:
            flags.append("OPT<ACT")
        if gap_mph > 25:
            flags.append("GAP>25")
        if opp.brake_gap_m is not None and opp.brake_gap_m < -5:
            flags.append("NEG_BRK")
        if group is not None:
            flags.append(f"G{group}")

        flag_str = " ".join(flags)
        print(
            f"  T{cn:>6d} {act_mph:>8.1f} {opt_mph:>8.1f} {gap_mph:>+8.1f} "
            f"{time_s:>7.3f} {brk:>8s} {z_mu:>8s} {i_mu:>8s} {flag_str:>12s}"
        )

        if "OPT<ACT" in flag_str or "GAP>25" in flag_str or "NEG_BRK" in flag_str:
            issues.append(f"T{cn}: {flag_str}")

    # 12. Lap time gap sanity
    if gap_pct < 3:
        issues.append(f"Total gap too small ({gap_pct:.1f}%) — model too conservative")
    elif gap_pct > 20:
        issues.append(f"Total gap too large ({gap_pct:.1f}%) — model too aggressive")

    # 13. Summary
    if issues:
        print(f"\n  !! ISSUES ({len(issues)}):")
        for issue in issues:
            print(f"     - {issue}")
    else:
        print("\n  All corners look physically reasonable")

    # 14. Curvature comparison (canonical vs session)
    if ref is not None:
        session_curv = compute_curvature(best_lap_df, savgol_window=15)
        print("\n  Curvature comparison (canonical / session):")
        for corner in corners:
            # Canonical zone curvature
            c_mask = (curvature_result.distance_m >= corner.entry_distance_m) & (
                curvature_result.distance_m <= corner.exit_distance_m
            )
            if not c_mask.any():
                continue
            c_p95 = float(np.percentile(curvature_result.abs_curvature[c_mask], 95))

            # Session zone curvature
            s_mask = (session_curv.distance_m >= corner.entry_distance_m) & (
                session_curv.distance_m <= corner.exit_distance_m
            )
            if not s_mask.any():
                continue
            s_p95 = float(np.percentile(session_curv.abs_curvature[s_mask], 95))

            ratio = c_p95 / s_p95 if s_p95 > 1e-6 else float("inf")
            flag = ""
            if ratio > 1.15:
                flag = " !! canonical >> session"
            elif ratio < 0.85:
                flag = " !! canonical << session"
            cn = corner.number
            print(f"    T{cn:>3d}: canon={c_p95:.5f} sess={s_p95:.5f} ratio={ratio:.2f}{flag}")


def main() -> None:
    """Run QA for all tracks, picking the best session per track."""
    tracks = sorted(os.listdir(SESSION_DIR))
    print(f"Found {len(tracks)} track directories: {tracks}\n")

    for track_dir in tracks:
        track_path = os.path.join(SESSION_DIR, track_dir)
        if not os.path.isdir(track_path):
            continue
        csv_files = sorted(glob.glob(os.path.join(track_path, "*.csv")))
        if not csv_files:
            print(f"\n{track_dir}: No CSV files")
            continue

        print(f"\n{'#' * 70}")
        print(f"# {track_dir.upper()} — {len(csv_files)} sessions")
        print(f"{'#' * 70}")

        best_file, best_time = pick_best_session(csv_files)
        if best_file is None:
            print("  No valid sessions found")
            continue

        print(f"  Best session: {os.path.basename(best_file)} ({best_time:.2f}s)")
        analyze_session(best_file)


if __name__ == "__main__":
    main()

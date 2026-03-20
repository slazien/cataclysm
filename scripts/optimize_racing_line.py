#!/usr/bin/env python3
"""Minimum-curvature racing line optimizer.

Takes an OSM-derived track centerline (stored as NPZ) and computes a smoother
racing line within track boundaries.  The optimized line uses the full track
width to increase corner radii, reducing curvature by 10-25% on average and
20-40% at peaks (tight corners).

Algorithm (multi-scale direct curvature minimization):
1. Load centerline from canonical track reference NPZ
2. Compute track boundaries (left/right edges) perpendicular to heading
3. Parameterize each point as alpha in [0,1] between right and left edge
4. Stage 1: Coarse optimization (subsample=20, ~260 vars) minimizing
   sum(kappa^2) via L-BFGS-B with numerical gradient
5. Stage 2: Fine optimization (subsample=10, ~500 vars) warm-started
   from stage 1 via linear interpolation
6. Interpolate to full resolution with linear interp + SavGol smoothing
7. Recompute true curvature of the optimized racing line

Usage:
    python scripts/optimize_racing_line.py \\
        --slug weathertech-raceway-laguna-seca --track-width 13.0
    python scripts/optimize_racing_line.py \\
        --slug weathertech-raceway-laguna-seca --track-width 13.0 --save
    python scripts/optimize_racing_line.py \\
        --slug weathertech-raceway-laguna-seca --track-width 13.0 --plot
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize
from scipy.signal import savgol_filter

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def compute_heading(x: NDArray, y: NDArray) -> NDArray:
    """Heading angle (radians) from XY via numpy gradient."""
    dx = np.gradient(x)
    dy = np.gradient(y)
    return np.arctan2(dy, dx)


def compute_normals(heading: NDArray) -> tuple[NDArray, NDArray]:
    """Unit normals pointing LEFT of heading direction."""
    nx = -np.sin(heading)
    ny = np.cos(heading)
    return nx, ny


def compute_curvature_xy(x: NDArray, y: NDArray) -> NDArray:
    """Signed curvature from the parametric formula.

    kappa = (x'y'' - y'x'') / (x'^2 + y'^2)^(3/2)
    """
    dx = np.gradient(x)
    dy = np.gradient(y)
    ddx = np.gradient(dx)
    ddy = np.gradient(dy)
    num = dx * ddy - dy * ddx
    denom = (dx**2 + dy**2) ** 1.5
    denom = np.where(denom < 1e-12, 1e-12, denom)
    return num / denom


def compute_distance(x: NDArray, y: NDArray) -> NDArray:
    """Cumulative arc-length distance along a polyline."""
    dx = np.diff(x)
    dy = np.diff(y)
    ds = np.sqrt(dx**2 + dy**2)
    return np.concatenate([[0.0], np.cumsum(ds)])


# ---------------------------------------------------------------------------
# Track edge computation
# ---------------------------------------------------------------------------


def compute_track_edges(
    x_center: NDArray,
    y_center: NDArray,
    half_width: float,
) -> tuple[NDArray, NDArray, NDArray, NDArray]:
    """Compute left/right track edges perpendicular to heading.

    Returns (x_right, y_right, dx_lr, dy_lr) where dx_lr/dy_lr are the
    direction vectors from right edge to left edge.
    """
    heading = compute_heading(x_center, y_center)
    nx, ny = compute_normals(heading)

    x_left = x_center + half_width * nx
    y_left = y_center + half_width * ny
    x_right = x_center - half_width * nx
    y_right = y_center - half_width * ny

    return x_right, y_right, x_left - x_right, y_left - y_right


# ---------------------------------------------------------------------------
# Direct curvature cost function
# ---------------------------------------------------------------------------


def curvature_cost(
    alpha: NDArray,
    x_right: NDArray,
    y_right: NDArray,
    dx_lr: NDArray,
    dy_lr: NDArray,
) -> float:
    """Sum of squared curvature for the alpha-parameterized line.

    Each point: x_i = x_right_i + alpha_i * dx_lr_i (right-to-left interp).
    alpha=0 => right edge, alpha=0.5 => centerline, alpha=1 => left edge.
    """
    x = x_right + alpha * dx_lr
    y = y_right + alpha * dy_lr
    kappa = compute_curvature_xy(x, y)
    return float(np.sum(kappa**2))


# ---------------------------------------------------------------------------
# Multi-scale optimizer
# ---------------------------------------------------------------------------


def _run_stage(
    label: str,
    x_center_sub: NDArray,
    y_center_sub: NDArray,
    hw: float,
    alpha_init: NDArray,
    max_iter: int,
    max_fun: int,
) -> NDArray:
    """Run one optimization stage, return optimized alpha array."""
    n = len(x_center_sub)
    xr, yr, dx_lr, dy_lr = compute_track_edges(x_center_sub, y_center_sub, hw)

    cost0 = curvature_cost(alpha_init, xr, yr, dx_lr, dy_lr)

    t0 = time.time()
    result = minimize(
        curvature_cost,
        alpha_init,
        args=(xr, yr, dx_lr, dy_lr),
        method="L-BFGS-B",
        bounds=[(0.0, 1.0)] * n,
        options={
            "maxiter": max_iter,
            "maxfun": max_fun,
            "ftol": 1e-16,
            "gtol": 1e-10,
        },
    )
    elapsed = time.time() - t0

    reduction_pct = (1.0 - result.fun / cost0) * 100.0
    print(
        f"  {label}: {n} pts, {elapsed:.1f}s, {result.nit} iters, "
        f"cost reduction={reduction_pct:.1f}%, success={result.success}"
    )
    if not result.success:
        msg = result.message
        if isinstance(msg, bytes):
            msg = msg.decode()
        print(f"    ({msg})")

    return result.x


def optimize_racing_line(
    x_center: NDArray,
    y_center: NDArray,
    half_width: float,
    max_iter: int = 1000,
) -> tuple[NDArray, NDArray, NDArray]:
    """Optimize racing line via multi-scale curvature minimization.

    Two-stage approach:
    - Stage 1: Coarse grid (every 20th point, ~260 variables).
      L-BFGS-B with numerical gradient converges in ~60-300 iters.
    - Stage 2: Fine grid (every 10th point, ~500 variables),
      warm-started from stage 1 via linear interpolation.

    The optimized alpha values are interpolated to full resolution using
    linear interpolation + Savitzky-Golay smoothing to avoid cubic-spline
    ringing artifacts.

    Parameters
    ----------
    x_center, y_center:
        Centerline coordinates in meters.
    half_width:
        Half the track width in meters (max lateral offset).
    max_iter:
        Maximum L-BFGS-B iterations per stage.

    Returns
    -------
    x_opt, y_opt, kappa_opt:
        Optimized racing line coordinates and curvature at full resolution.
    """
    n_full = len(x_center)
    margin = 0.5  # safety margin from barriers (meters)
    hw = half_width - margin

    print(f"Optimizing racing line (multi-scale, effective width={2 * hw:.1f}m)...")

    # --- Stage 1: Coarse (subsample=20) ---
    sub1 = 20
    idx1 = np.arange(0, n_full, sub1)
    alpha1 = _run_stage(
        "Stage 1 (coarse)",
        x_center[idx1],
        y_center[idx1],
        hw,
        alpha_init=np.full(len(idx1), 0.5),
        max_iter=max_iter,
        max_fun=500_000,
    )

    # --- Stage 2: Fine (subsample=10), warm-started from stage 1 ---
    sub2 = 10
    idx2 = np.arange(0, n_full, sub2)
    alpha2_init = np.clip(np.interp(idx2, idx1, alpha1), 0.0, 1.0)
    alpha2 = _run_stage(
        "Stage 2 (fine) ",
        x_center[idx2],
        y_center[idx2],
        hw,
        alpha_init=alpha2_init,
        max_iter=max_iter,
        max_fun=2_000_000,
    )

    # --- Interpolate to full resolution ---
    # Linear interpolation (avoids cubic-spline ringing), then SavGol
    # smooth with a window matching ~2% of track length to remove
    # interpolation step artifacts while preserving the optimized shape.
    alpha_full = np.interp(np.arange(n_full), idx2, alpha2)

    # SavGol window: approximately 10x the fine subsample interval,
    # must be odd. This is about 70m of track -- enough to smooth interp
    # steps without erasing corner-level detail.
    sg_alpha = sub2 * 10 + 1  # 101
    alpha_full = savgol_filter(alpha_full, window_length=sg_alpha, polyorder=3)
    alpha_full = np.clip(alpha_full, 0.0, 1.0)

    # Build full-resolution racing line
    heading_full = compute_heading(x_center, y_center)
    nx_f, ny_f = compute_normals(heading_full)
    x_left = x_center + hw * nx_f
    y_left = y_center + hw * ny_f
    x_right = x_center - hw * nx_f
    y_right = y_center - hw * ny_f

    x_opt = x_right + alpha_full * (x_left - x_right)
    y_opt = y_right + alpha_full * (y_left - y_right)

    # Curvature of optimized line with light smoothing
    kappa_opt = compute_curvature_xy(x_opt, y_opt)
    sg_curv = max(5, int(n_full * 0.01) | 1)
    kappa_opt = savgol_filter(kappa_opt, window_length=sg_curv, polyorder=3)

    # Report offset statistics
    offsets_m = (alpha_full - 0.5) * 2.0 * hw
    print(
        f"  Offsets: mean={np.mean(np.abs(offsets_m)):.2f}m, "
        f"max={np.max(np.abs(offsets_m)):.2f}m (limit={hw:.1f}m)"
    )

    return x_opt, y_opt, kappa_opt


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_stats(
    label: str,
    kappa: NDArray,
    spike_threshold: float = 0.04,
) -> dict[str, float]:
    """Print curvature statistics and return them as a dict."""
    abs_k = np.abs(kappa)
    stats = {
        "mean_k": float(np.mean(abs_k)),
        "max_k": float(np.max(abs_k)),
        "spikes": int(np.sum(abs_k > spike_threshold)),
    }
    print(
        f"{label}: mean_kappa={stats['mean_k']:.4f}  "
        f"max_kappa={stats['max_k']:.4f}  "
        f"spikes(>{spike_threshold})={stats['spikes']}"
    )
    return stats


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def save_plot(
    x_center: NDArray,
    y_center: NDArray,
    x_opt: NDArray,
    y_opt: NDArray,
    kappa_before: NDArray,
    kappa_after: NDArray,
    distance: NDArray,
    out_path: Path,
    half_width: float,
) -> None:
    """Save a comparison PNG: track layout + curvature profiles."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    # --- Top: track layout ---
    ax = axes[0]
    heading = compute_heading(x_center, y_center)
    nx, ny = compute_normals(heading)
    x_left = x_center + half_width * nx
    y_left = y_center + half_width * ny
    x_right = x_center - half_width * nx
    y_right = y_center - half_width * ny

    ax.fill(
        np.concatenate([x_left, x_right[::-1]]),
        np.concatenate([y_left, y_right[::-1]]),
        color="#e0e0e0",
        alpha=0.5,
        label="Track surface",
    )
    ax.plot(
        x_center,
        y_center,
        "b-",
        lw=0.5,
        alpha=0.5,
        label="Centerline",
    )
    ax.plot(x_opt, y_opt, "r-", lw=1.0, label="Racing line")
    ax.plot(x_left, y_left, "k-", lw=0.3, alpha=0.4)
    ax.plot(x_right, y_right, "k-", lw=0.3, alpha=0.4)
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("Track Layout: Centerline vs Racing Line")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")

    # --- Bottom: curvature comparison ---
    ax2 = axes[1]
    ax2.plot(
        distance,
        np.abs(kappa_before),
        "b-",
        lw=0.5,
        alpha=0.6,
        label="Centerline",
    )
    ax2.plot(
        distance,
        np.abs(kappa_after),
        "r-",
        lw=0.8,
        label="Racing line",
    )
    ax2.axhline(
        0.04,
        color="gray",
        linestyle="--",
        lw=0.5,
        alpha=0.5,
        label="Spike threshold",
    )
    ax2.set_xlabel("Distance (m)")
    ax2.set_ylabel("|Curvature| (1/m)")
    ax2.set_title("Curvature Profile: Before vs After Optimization")
    ax2.legend(loc="upper right", fontsize=8)
    kmax = max(np.max(np.abs(kappa_before)), np.max(np.abs(kappa_after)))
    ax2.set_ylim(0, kmax * 1.1)

    plt.tight_layout()
    fig.savefig(str(out_path), dpi=150)
    plt.close(fig)
    print(f"Plot saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Minimum-curvature racing line optimizer for OSM track references")
    )
    parser.add_argument("--slug", required=True, help="Track reference slug")
    parser.add_argument(
        "--track-width",
        type=float,
        default=12.0,
        help="Track width in meters (default: 12.0)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Overwrite NPZ with optimized curvature (default: dry run)",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Save a PNG comparison plot",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=1000,
        help="Max optimizer iterations per stage (default: 1000)",
    )

    args = parser.parse_args()

    # Resolve paths
    project_root = Path(__file__).resolve().parent.parent
    ref_dir = project_root / "data" / "track_reference"
    npz_path = ref_dir / f"{args.slug}.npz"

    if not npz_path.exists():
        print(f"Error: track reference not found: {npz_path}")
        sys.exit(1)

    # Load NPZ (allow_pickle for metadata string stored as numpy array)
    data = np.load(str(npz_path), allow_pickle=True)  # noqa: S301
    x_center: NDArray = data["x_smooth"]
    y_center: NDArray = data["y_smooth"]
    distance: NDArray = data["distance_m"]
    kappa_before: NDArray = data["curvature"]

    track_length = float(distance[-1])
    n_points = len(x_center)

    print(f"Loaded: {args.slug} ({track_length:.0f}m, {n_points} points)")
    print(f"Track width: {args.track_width}m")

    half_width = args.track_width / 2.0
    before = print_stats("Before", kappa_before)

    # Optimize
    x_opt, y_opt, kappa_opt = optimize_racing_line(
        x_center,
        y_center,
        half_width,
        max_iter=args.max_iter,
    )

    after = print_stats("After ", kappa_opt)

    # Summary
    mean_red = (1.0 - after["mean_k"] / before["mean_k"]) * 100
    max_red = (1.0 - after["max_k"] / before["max_k"]) * 100
    print(f"Curvature reduction: mean {mean_red:.0f}%, max {max_red:.0f}%")

    # Recompute distance and heading for the optimized line
    distance_opt = compute_distance(x_opt, y_opt)
    heading_opt = compute_heading(x_opt, y_opt)

    if args.plot:
        plot_path = project_root / f"racing_line_{args.slug}.png"
        save_plot(
            x_center,
            y_center,
            x_opt,
            y_opt,
            kappa_before,
            kappa_opt,
            distance,
            plot_path,
            half_width,
        )

    if args.save:
        save_dict: dict[str, object] = {}
        for key in data.files:
            save_dict[key] = data[key]

        save_dict["curvature"] = kappa_opt
        save_dict["x_smooth"] = x_opt
        save_dict["y_smooth"] = y_opt
        save_dict["distance_m"] = distance_opt
        save_dict["heading_rad"] = heading_opt

        # Preserve the original centerline for reference
        save_dict["x_centerline"] = x_center
        save_dict["y_centerline"] = y_center
        save_dict["curvature_centerline"] = kappa_before

        metadata_str = str(data["metadata"])
        try:
            meta = json.loads(metadata_str)
        except (json.JSONDecodeError, ValueError):
            meta = {}
        meta["racing_line_optimized"] = True
        meta["racing_line_track_width_m"] = args.track_width
        meta["racing_line_mean_curvature_reduction_pct"] = round(mean_red, 1)
        meta["racing_line_max_curvature_reduction_pct"] = round(max_red, 1)
        save_dict["metadata"] = json.dumps(meta)

        np.savez(str(npz_path), **save_dict)
        print(f"Saved optimized reference: {npz_path}")
    else:
        print("(dry run -- use --save to write)")


if __name__ == "__main__":
    main()

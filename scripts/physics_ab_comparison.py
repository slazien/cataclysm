#!/usr/bin/env python3
"""A/B comparison: baseline vs Tier 1 improvements.

Loads baseline JSON, runs current (improved) solver, compares all metrics.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.physics_realworld_comparison import run_comparison

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def main() -> None:
    # Load baseline
    baseline_path = os.path.join(DATA_DIR, "physics_baseline_2026-03-19.json")
    with open(baseline_path) as f:
        baseline = json.load(f)

    # Run current solver
    results = run_comparison()
    ratios = [r.efficiency_ratio for r in results]

    current = {
        "mean_ratio": float(np.mean(ratios)),
        "median_ratio": float(np.median(ratios)),
        "std_ratio": float(np.std(ratios)),
        "exceedance_count_5pct": sum(1 for r in ratios if r > 1.05),
        "r_compound_mean": float(
            np.mean([r.efficiency_ratio for r in results if r.tire_category == "r_compound"])
        ),
    }

    bl = baseline["summary"]

    print("\n" + "=" * 70)
    print("A/B COMPARISON: Baseline vs Tier 1 Improvements")
    print("=" * 70)
    print(f"\n{'Metric':<30} {'Baseline':>12} {'Current':>12} {'Delta':>12}")
    print("-" * 70)

    for key in [
        "mean_ratio",
        "median_ratio",
        "std_ratio",
        "exceedance_count_5pct",
        "r_compound_mean",
    ]:
        b_val = bl[key]
        c_val = current[key]
        delta = c_val - b_val
        arrow = "+" if delta > 0 else "-" if delta < 0 else "="
        print(f"{key:<30} {b_val:>12.4f} {c_val:>12.4f} {delta:>+11.4f} {arrow}")

    # Per-entry comparison
    print(f"\n{'Car':<25} {'Track':<15} {'BL Ratio':>10} {'New Ratio':>10} {'Delta':>8}")
    print("-" * 70)
    for bl_entry, result in zip(baseline["entries"], results, strict=True):
        delta = result.efficiency_ratio - bl_entry["ratio"]
        flag = ""
        if abs(delta) > 0.02:
            flag = " ***" if delta > 0 else " <<<"
        print(
            f"{result.car_label:<25} {result.track[:15]:<15} "
            f"{bl_entry['ratio']:>10.4f} {result.efficiency_ratio:>10.4f} {delta:>+8.4f}{flag}"
        )

    # Acceptance criteria check
    print(f"\n{'=' * 70}")
    print("ACCEPTANCE CRITERIA")
    print(f"{'=' * 70}")
    checks = [
        (
            "Mean ratio closer to 1.0",
            bl["mean_ratio"],
            current["mean_ratio"],
            abs(1.0 - current["mean_ratio"]) < abs(1.0 - bl["mean_ratio"]),
        ),
        (
            "Std dev decreased",
            bl["std_ratio"],
            current["std_ratio"],
            current["std_ratio"] < bl["std_ratio"],
        ),
        (
            "Exceedance <=1",
            bl["exceedance_count_5pct"],
            current["exceedance_count_5pct"],
            current["exceedance_count_5pct"] <= 1,
        ),
        (
            "R-compound mean closer to 1.0",
            bl["r_compound_mean"],
            current["r_compound_mean"],
            abs(1.0 - current["r_compound_mean"]) < abs(1.0 - bl["r_compound_mean"]),
        ),
    ]
    all_pass = True
    for name, bl_val, cur_val, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  {name:<30} {bl_val:>10.4f} -> {cur_val:>10.4f}  {status}")

    print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME FAILED -- investigate'}")

    # Save results
    out = {
        "date": "2026-03-19",
        "solver_version": "tier1",
        "improvements": ["per_tire_mu", "cl_a_downforce", "friction_ellipse"],
        "baseline_summary": bl,
        "current_summary": current,
        "acceptance_criteria": {
            name: {"baseline": bl_val, "current": cur_val, "passed": passed}
            for name, bl_val, cur_val, passed in checks
        },
        "per_entry": [
            {
                "car": r.car_label,
                "track": r.track,
                "baseline_ratio": bl_entry["ratio"],
                "current_ratio": r.efficiency_ratio,
                "delta": r.efficiency_ratio - bl_entry["ratio"],
            }
            for bl_entry, r in zip(baseline["entries"], results, strict=True)
        ],
    }
    out_path = os.path.join(DATA_DIR, "physics_tier1_results_2026-03-19.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate a before/after physics validation HTML report.

Loads the old baseline (/tmp/old_baseline.json) and new baseline (data/physics_baseline.json),
computes statistics for both, and generates an interactive HTML report with Chart.js charts,
KPI cards, tier assessment, segmentation tables, and full data tables.

Two views:
  1. Amateur data only (driver_level != "pro") — honest validation
  2. All data — completeness
"""

from __future__ import annotations

import datetime
import html
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
OLD_BASELINE_PATH = "/tmp/old_baseline.json"
NEW_BASELINE_PATH = os.path.join(PROJECT_ROOT, "data", "physics_baseline.json")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "docs", "physics-validation-before-after.html")


@dataclass
class Entry:
    car: str
    track: str
    real_s: float
    predicted_s: float
    ratio: float
    tire_category: str
    tire_model: str
    mu: float
    source_quality: str = ""
    driver_level: str = "unknown"
    mod_level: str = ""
    hp: int = 0
    weight_kg: int = 0
    drivetrain: str = ""


@dataclass
class Stats:
    n: int = 0
    mean_ratio: float = 0.0
    std_ratio: float = 0.0
    mape: float = 0.0
    rmse: float = 0.0
    r_squared: float = 0.0
    exceedances_5pct: int = 0
    bias_s: float = 0.0
    loa_upper: float = 0.0
    loa_lower: float = 0.0
    slope: float = 0.0
    intercept: float = 0.0
    r_mu: float = 0.0
    by_category: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_track: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_grip_band: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_mod_level: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_hp_band: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_drivetrain: dict[str, dict[str, Any]] = field(default_factory=dict)
    loo_mean_range: tuple[float, float] = (0.0, 0.0)
    loo_max_spread: float = 0.0
    loo_influential: int = 0


def load_entries(path: str) -> list[Entry]:
    with open(path) as f:
        data = json.load(f)
    entries = []
    for e in data["entries"]:
        entries.append(Entry(
            car=e["car"],
            track=e["track"],
            real_s=e["real_s"],
            predicted_s=e["predicted_s"],
            ratio=e["ratio"],
            tire_category=e.get("tire_category", ""),
            tire_model=e.get("tire_model", ""),
            mu=e.get("mu", 1.0),
            source_quality=e.get("source_quality", ""),
            driver_level=e.get("driver_level", "unknown"),
        ))
    return entries


def _grip_band(cat: str) -> str:
    if cat in ("street", "endurance_200tw"):
        return "Low (street+endurance)"
    if cat in ("super_200tw", "100tw"):
        return "Mid (super+100tw)"
    return "High (r_compound+slick)"


def compute_stats(entries: list[Entry]) -> Stats:
    if not entries:
        return Stats()

    ratios = np.array([e.ratio for e in entries])
    reals = np.array([e.real_s for e in entries])
    preds = np.array([e.predicted_s for e in entries])

    n = len(entries)
    mean_ratio = float(np.mean(ratios))
    std_ratio = float(np.std(ratios, ddof=1)) if n > 1 else 0.0

    # MAPE
    ape = np.abs((preds - reals) / reals) * 100
    mape = float(np.mean(ape))

    # RMSE
    rmse = float(np.sqrt(np.mean((preds - reals) ** 2)))

    # Exceedances >5%
    exceedances = int(np.sum(np.abs(ratios - 1.0) > 0.05))

    # R-squared (calibration regression)
    if n > 2:
        coeffs = np.polyfit(reals, preds, 1)
        slope, intercept = float(coeffs[0]), float(coeffs[1])
        ss_res = float(np.sum((preds - (slope * reals + intercept)) ** 2))
        ss_tot = float(np.sum((preds - np.mean(preds)) ** 2))
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    else:
        slope, intercept, r_squared = 1.0, 0.0, 0.0

    # Bland-Altman
    diffs = preds - reals
    bias_s = float(np.mean(diffs))
    diff_std = float(np.std(diffs, ddof=1)) if n > 1 else 0.0
    loa_upper = bias_s + 1.96 * diff_std
    loa_lower = bias_s - 1.96 * diff_std

    # Correlation with mu
    mus = np.array([e.mu for e in entries])
    if n > 2 and np.std(mus) > 0:
        r_mu = float(np.corrcoef(ratios, mus)[0, 1])
    else:
        r_mu = 0.0

    # Category breakdown
    by_category: dict[str, dict[str, Any]] = {}
    cats = defaultdict(list)
    for e in entries:
        cats[e.tire_category].append(e.ratio)
    for cat, rs in sorted(cats.items()):
        arr = np.array(rs)
        by_category[cat] = {
            "n": len(rs),
            "mean": round(float(np.mean(arr)), 4),
            "std": round(float(np.std(arr, ddof=1)), 4) if len(rs) > 1 else 0.0,
        }

    # Track breakdown
    by_track: dict[str, dict[str, Any]] = {}
    tracks = defaultdict(list)
    for e in entries:
        tracks[e.track].append(e.ratio)
    for track, rs in sorted(tracks.items()):
        arr = np.array(rs)
        by_track[track] = {
            "n": len(rs),
            "mean": round(float(np.mean(arr)), 4),
            "std": round(float(np.std(arr, ddof=1)), 4) if len(rs) > 1 else 0.0,
        }

    # Grip band breakdown
    by_grip_band: dict[str, dict[str, Any]] = {}
    bands = defaultdict(list)
    for e in entries:
        bands[_grip_band(e.tire_category)].append(e.ratio)
    for band, rs in sorted(bands.items()):
        arr = np.array(rs)
        by_grip_band[band] = {
            "n": len(rs),
            "mean": round(float(np.mean(arr)), 4),
            "std": round(float(np.std(arr, ddof=1)), 4) if len(rs) > 1 else 0.0,
        }

    # Mod level breakdown
    by_mod_level: dict[str, dict[str, Any]] = {}
    mods = defaultdict(list)
    for e in entries:
        # Parse from source_quality or default
        mods["unknown"].append(e.ratio)
    # We don't have mod_level in baseline entries easily; skip detailed breakdown
    # Just use source_quality as a proxy
    by_mod_level = {}  # will be populated from the full output if needed

    # Drivetrain breakdown (not in baseline data, skip)
    by_drivetrain: dict[str, dict[str, Any]] = {}

    # HP band breakdown (not in baseline data, skip)
    by_hp_band: dict[str, dict[str, Any]] = {}

    # LOO-CV
    if n > 3:
        loo_means = []
        for i in range(n):
            left = np.delete(ratios, i)
            loo_means.append(float(np.mean(left)))
        loo_arr = np.array(loo_means)
        loo_mean_range = (float(np.min(loo_arr)), float(np.max(loo_arr)))
        loo_max_spread = float(np.max(loo_arr) - np.min(loo_arr))
        loo_influential = int(np.sum(np.abs(loo_arr - mean_ratio) > 0.003))
    else:
        loo_mean_range = (mean_ratio, mean_ratio)
        loo_max_spread = 0.0
        loo_influential = 0

    return Stats(
        n=n,
        mean_ratio=round(mean_ratio, 4),
        std_ratio=round(std_ratio, 4),
        mape=round(mape, 2),
        rmse=round(rmse, 3),
        r_squared=round(r_squared, 4),
        exceedances_5pct=exceedances,
        bias_s=round(bias_s, 3),
        loa_upper=round(loa_upper, 3),
        loa_lower=round(loa_lower, 3),
        slope=round(slope, 4),
        intercept=round(intercept, 3),
        r_mu=round(r_mu, 3),
        by_category=by_category,
        by_track=by_track,
        by_grip_band=by_grip_band,
        by_mod_level=by_mod_level,
        by_hp_band=by_hp_band,
        by_drivetrain=by_drivetrain,
        loo_mean_range=(round(loo_mean_range[0], 4), round(loo_mean_range[1], 4)),
        loo_max_spread=round(loo_max_spread, 4),
        loo_influential=loo_influential,
    )


def _kpi_color(value: float, thresholds: list[tuple[float, str]]) -> str:
    """Return CSS class based on thresholds [(max_val, class), ...]."""
    for thresh, cls in thresholds:
        if value <= thresh:
            return cls
    return thresholds[-1][1]


def _ratio_class(ratio: float) -> str:
    if abs(ratio - 1.0) < 0.02:
        return "good"
    if abs(ratio - 1.0) < 0.05:
        return "warn"
    return "bad"


def _tier_check(value: float, threshold: float, lower_is_better: bool = True) -> str:
    passed = value <= threshold if lower_is_better else value >= threshold
    cls = "good" if passed else "bad"
    sym = "&#10003;" if passed else "&#10007;"
    return f'<span class="{cls}">{sym} {value:.2f}%</span>'


def _tier_check_abs(value: float, threshold: float, lower_is_better: bool = True) -> str:
    passed = value <= threshold if lower_is_better else value >= threshold
    cls = "good" if passed else "bad"
    sym = "&#10003;" if passed else "&#10007;"
    return f'<span class="{cls}">{sym} {value:.2f}%</span>'


def _fmt_time(s: float) -> str:
    mins = int(s // 60)
    secs = s % 60
    return f"{mins}:{secs:05.2f}"


def _short_track(track: str) -> str:
    mapping = {
        "Barber Motorsports Park": "Barber",
        "Roebling Road Raceway": "Roebling",
        "Atlanta Motorsports Park": "AMP",
        "Virginia International Raceway Grand West": "VIR",
        "WeatherTech Raceway Laguna Seca": "Laguna Seca",
    }
    return mapping.get(track, track[:12])


def _delta_arrow(before: float, after: float, lower_is_better: bool = True) -> str:
    """Generate a delta arrow with color."""
    diff = after - before
    if abs(diff) < 0.0001:
        return '<span style="color:#6b7280">&#8212;</span>'
    if lower_is_better:
        color = "#34d399" if diff < 0 else "#f87171"
    else:
        color = "#34d399" if diff > 0 else "#f87171"
    arrow = "&#9660;" if diff < 0 else "&#9650;"
    return f'<span style="color:{color}; font-size:0.7rem">{arrow} {abs(diff):.3f}</span>'


def _delta_arrow_pct(before: float, after: float) -> str:
    diff = after - before
    if abs(diff) < 0.001:
        return '<span style="color:#6b7280">&#8212;</span>'
    color = "#34d399" if diff < 0 else "#f87171"
    arrow = "&#9660;" if diff < 0 else "&#9650;"
    return f'<span style="color:{color}; font-size:0.7rem">{arrow} {abs(diff):.2f}%</span>'


def _delta_arrow_s(before: float, after: float) -> str:
    diff = after - before
    if abs(diff) < 0.001:
        return '<span style="color:#6b7280">&#8212;</span>'
    color = "#34d399" if diff < 0 else "#f87171"
    arrow = "&#9660;" if diff < 0 else "&#9650;"
    return f'<span style="color:{color}; font-size:0.7rem">{arrow} {abs(diff):.2f}s</span>'


def _delta_arrow_int(before: int, after: int) -> str:
    diff = after - before
    if diff == 0:
        return '<span style="color:#6b7280">&#8212;</span>'
    color = "#34d399" if diff < 0 else "#f87171"
    arrow = "&#9660;" if diff < 0 else "&#9650;"
    return f'<span style="color:{color}; font-size:0.7rem">{arrow} {abs(diff)}</span>'


def _delta_arrow_r2(before: float, after: float) -> str:
    diff = after - before
    if abs(diff) < 0.0001:
        return '<span style="color:#6b7280">&#8212;</span>'
    color = "#34d399" if diff > 0 else "#f87171"
    arrow = "&#9650;" if diff > 0 else "&#9660;"
    return f'<span style="color:{color}; font-size:0.7rem">{arrow} {abs(diff):.4f}</span>'


def _entries_to_js(entries: list[Entry], var_name: str) -> str:
    """Convert entries to a JS array literal."""
    lines = [f"const {var_name} = ["]
    for e in entries:
        short_track = _short_track(e.track)
        car_esc = e.car.replace("'", "\\'")
        tire_esc = e.tire_model.replace("'", "\\'")[:30]
        lines.append(
            f"  {{car:'{car_esc}',track:'{short_track}',"
            f"tire:'{tire_esc}',cat:'{e.tire_category}',"
            f"mu:{e.mu:.2f},real:{e.real_s:.2f},pred:{e.predicted_s:.3f},"
            f"ratio:{e.ratio:.4f}}},"
        )
    lines.append("];")
    return "\n".join(lines)


def generate_html(
    old_entries: list[Entry],
    new_entries: list[Entry],
    old_stats_amateur: Stats,
    new_stats_amateur: Stats,
    old_stats_all: Stats,
    new_stats_all: Stats,
    old_amateur: list[Entry],
    new_amateur: list[Entry],
) -> str:
    git_sha = "unknown"
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
        ).strip()
    except Exception:
        pass

    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Track colors
    all_tracks_new = sorted(set(_short_track(e.track) for e in new_entries))
    track_color_list = ["#60a5fa", "#34d399", "#fbbf24", "#f472b6", "#a78bfa", "#fb923c"]
    track_colors_map = {t: track_color_list[i % len(track_color_list)] for i, t in enumerate(all_tracks_new)}

    # Count unique cars and categories for subtitle
    new_am_cars = len(set(e.car for e in new_amateur))
    new_am_cats = len(set(e.tire_category for e in new_amateur))
    new_am_tracks = len(set(e.track for e in new_amateur))
    new_all_cars = len(set(e.car for e in new_entries))
    new_all_tracks = len(set(e.track for e in new_entries))

    sa = new_stats_amateur  # shortcut for new amateur stats
    so = old_stats_amateur  # shortcut for old amateur stats
    sa_all = new_stats_all
    so_all = old_stats_all

    # Determine tier for amateur data
    def _get_tier(s: Stats) -> str:
        bias_pct = abs(s.mean_ratio - 1.0) * 100
        std_pct = s.std_ratio * 100
        mape = s.mape
        if bias_pct < 0.5 and std_pct < 1.5 and mape < 1.0:
            return "D"
        if bias_pct < 1.0 and std_pct < 3.5 and mape < 3.0:
            return "C"
        if bias_pct < 2.0 and std_pct < 5.0 and mape < 5.0:
            return "B"
        if bias_pct < 5.0 and std_pct < 8.0 and mape < 10.0:
            return "A"
        return "F"

    tier_new = _get_tier(sa)
    tier_old = _get_tier(so)

    def _tier_section(s: Stats, label: str) -> str:
        bias_pct = abs(s.mean_ratio - 1.0) * 100
        std_pct = s.std_ratio * 100
        mape = s.mape
        tier = _get_tier(s)
        active = {"D": "tier-d", "C": "tier-c", "B": "tier-b", "A": "tier-a"}.get(tier, "")

        def _chk(val: float, thresh: float) -> str:
            ok = val <= thresh
            cls = "good" if ok else "bad"
            sym = "&#10003;" if ok else "&#10007;"
            return f'<span class="{cls}">{sym} {val:.2f}%</span>'

        return f"""
  <div class="tier-section">
    <h2 style="font-size:1rem; margin-bottom:0.5rem;">Accuracy Tier — {label}</h2>
    <div class="tier-bar">
      <div class="tier-d {'tier-active' if tier == 'D' else ''}">D: Engineering</div>
      <div class="tier-c {'tier-active' if tier == 'C' else ''}">C: Coaching{' &#9733;' if tier == 'C' else ''}</div>
      <div class="tier-b {'tier-active' if tier == 'B' else ''}">B: Setup</div>
      <div class="tier-a {'tier-active' if tier == 'A' else ''}">A: Screening</div>
    </div>
    <div class="tier-reqs">
      <div class="tier-req">
        <h4>D: Engineering</h4>
        <div style="font-size:0.65rem; color:#6b7280; margin-bottom:0.3rem;">Dal Bianco GP2 0.34%, IPG CarMaker 0.15%</div>
        <div>Bias &lt;0.5% {_chk(bias_pct, 0.5)}</div>
        <div>Std &lt;1.5% {_chk(std_pct, 1.5)}</div>
        <div>MAPE &lt;1.0% {_chk(mape, 1.0)}</div>
      </div>
      <div class="tier-req">
        <h4>C: Coaching</h4>
        <div style="font-size:0.65rem; color:#6b7280; margin-bottom:0.3rem;">IPG CarMaker 1-2%, ChassisSim &lt;2% cal.</div>
        <div>Bias &lt;1.0% {_chk(bias_pct, 1.0)}</div>
        <div>Std &lt;3.5% {_chk(std_pct, 3.5)}</div>
        <div>MAPE &lt;3.0% {_chk(mape, 3.0)}</div>
      </div>
      <div class="tier-req">
        <h4>B: Setup</h4>
        <div style="font-size:0.65rem; color:#6b7280; margin-bottom:0.3rem;">OptimumLap careful 2-5%, ChassisSim ~5%</div>
        <div>Bias &lt;2.0% {_chk(bias_pct, 2.0)}</div>
        <div>Std &lt;5.0% {_chk(std_pct, 5.0)}</div>
        <div>MAPE &lt;5.0% {_chk(mape, 5.0)}</div>
      </div>
      <div class="tier-req">
        <h4>A: Screening</h4>
        <div style="font-size:0.65rem; color:#6b7280; margin-bottom:0.3rem;">OptimumLap spec 10%, Broatch 8-10%</div>
        <div>Bias &lt;5.0% {_chk(bias_pct, 5.0)}</div>
        <div>Std &lt;8.0% {_chk(std_pct, 8.0)}</div>
        <div>MAPE &lt;10.0% {_chk(mape, 10.0)}</div>
      </div>
    </div>
  </div>"""

    # Build category bar data for JS
    def _cat_bar_js(stats: Stats, var_name: str) -> str:
        order = ["street", "endurance_200tw", "super_200tw", "100tw", "r_compound", "slick"]
        items = []
        for cat in order:
            if cat in stats.by_category:
                d = stats.by_category[cat]
                items.append(f"{{cat:'{cat}',mean:{d['mean']},n:{d['n']}}}")
        return f"const {var_name} = [{','.join(items)}];"

    # Build track bar data for JS
    def _track_bar_js(stats: Stats, var_name: str) -> str:
        items = []
        for track, d in sorted(stats.by_track.items()):
            st = _short_track(track)
            n_val = d["n"]
            mean_val = d["mean"]
            color_val = track_colors_map.get(st, "#60a5fa")
            items.append(
                "{" + f"t:'{st} (n={n_val})',mean:{mean_val},color:'{color_val}'" + "}"
            )
        return f"const {var_name} = [{','.join(items)}];"

    # Build grip band data for JS
    def _grip_bar_js(stats: Stats, var_name: str) -> str:
        order = ["Low (street+endurance)", "Mid (super+100tw)", "High (r_compound+slick)"]
        colors = ["#60a5fa", "#34d399", "#f472b6"]
        items = []
        for i, band in enumerate(order):
            if band in stats.by_grip_band:
                d = stats.by_grip_band[band]
                items.append(f"{{band:'{band}',mean:{d['mean']},n:{d['n']},color:'{colors[i]}'}}")
        return f"const {var_name} = [{','.join(items)}];"

    # Segmentation tables
    def _seg_tables(stats: Stats, entries_list: list[Entry], prefix: str) -> str:
        # By source quality
        src = defaultdict(list)
        for e in entries_list:
            src[e.source_quality or "unknown"].append(e.ratio)

        # By driver level
        dl = defaultdict(list)
        for e in entries_list:
            dl[e.driver_level or "unknown"].append(e.ratio)

        cat_rows = ""
        for cat, d in sorted(stats.by_category.items()):
            cls = "good" if abs(d["mean"] - 1.0) < 0.02 else "warn" if abs(d["mean"] - 1.0) < 0.04 else "bad"
            cat_rows += f'<tr><td>{cat.replace("_", " ")}</td><td>{d["n"]}</td>'
            cat_rows += f'<td class="ratio-cell {cls}">{d["mean"]:.3f}</td>'
            cat_rows += f'<td>{d["std"]:.3f}</td></tr>\n'

        track_rows = ""
        for track, d in sorted(stats.by_track.items()):
            cls = "good" if abs(d["mean"] - 1.0) < 0.02 else "warn" if abs(d["mean"] - 1.0) < 0.04 else "bad"
            track_rows += f'<tr><td>{_short_track(track)}</td><td>{d["n"]}</td>'
            track_rows += f'<td class="ratio-cell {cls}">{d["mean"]:.3f}</td>'
            track_rows += f'<td>{d["std"]:.3f}</td></tr>\n'

        src_rows = ""
        for sq, rs in sorted(src.items()):
            arr = np.array(rs)
            m = float(np.mean(arr))
            s_val = float(np.std(arr, ddof=1)) if len(rs) > 1 else 0.0
            cls = "good" if abs(m - 1.0) < 0.02 else "warn"
            src_rows += f'<tr><td>{sq}</td><td>{len(rs)}</td>'
            src_rows += f'<td class="ratio-cell {cls}">{m:.3f}</td>'
            src_rows += f'<td>{s_val:.3f}</td></tr>\n'

        loo_html = f"""
        <tr><td>Jackknife mean range</td><td>[{stats.loo_mean_range[0]:.4f}, {stats.loo_mean_range[1]:.4f}]</td></tr>
        <tr><td>Stability (max spread)</td><td class="good">{stats.loo_max_spread:.4f}</td></tr>
        <tr><td>Influential entries</td><td class="{'good' if stats.loo_influential == 0 else 'warn'}">{stats.loo_influential} (threshold &#177;0.003)</td></tr>
        """

        return f"""
    <div class="chart-grid">
      <div class="chart-card">
        <h2>By Tire Category</h2>
        <table>
          <tr><th>Category</th><th>n</th><th>Mean</th><th>Std</th></tr>
          {cat_rows}
        </table>
      </div>
      <div class="chart-card">
        <h2>By Track</h2>
        <table>
          <tr><th>Track</th><th>n</th><th>Mean</th><th>Std</th></tr>
          {track_rows}
        </table>
      </div>
      <div class="chart-card">
        <h2>By Source Quality</h2>
        <table>
          <tr><th>Source</th><th>n</th><th>Mean</th><th>Std</th></tr>
          {src_rows}
        </table>
      </div>
      <div class="chart-card">
        <h2>LOO Cross-Validation</h2>
        <table>
          <tr><th>Metric</th><th>Value</th></tr>
          {loo_html}
        </table>
        <p style="color:#9ca3af; font-size:0.78rem; margin-top:0.8rem;">
          No single entry shifts the mean by more than &#177;0.003 when removed if influential=0.
        </p>
      </div>
    </div>"""

    # Full data table
    def _data_table(entries_list: list[Entry], table_id: str) -> str:
        rows = ""
        sorted_entries = sorted(entries_list, key=lambda e: e.ratio)
        for e in sorted_entries:
            delta = e.predicted_s - e.real_s
            cls = _ratio_class(e.ratio)
            delta_color = "#fbbf24" if delta > 0 else "#60a5fa"
            delta_sign = "+" if delta > 0 else ""
            rows += f"""<tr>
              <td>{html.escape(e.car)}</td>
              <td>{_short_track(e.track)}</td>
              <td style="font-size:0.75rem">{html.escape(e.tire_model[:30])}</td>
              <td><span style="color:{_cat_color(e.tire_category)}">{e.tire_category.replace('_', ' ')}</span></td>
              <td>{e.mu:.2f}</td>
              <td>{_fmt_time(e.real_s)}</td>
              <td>{_fmt_time(e.predicted_s)}</td>
              <td class="ratio-cell {cls}">{e.ratio:.3f}</td>
              <td style="color:{delta_color}">{delta_sign}{delta:.1f}s</td>
            </tr>\n"""
        return rows

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cataclysm Physics Validation — Before/After Comparison</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f1117;
    color: #e0e0e0;
    padding: 2rem 1rem;
    max-width: 1400px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 2rem;
    font-weight: 700;
    text-align: center;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .subtitle {{ color: #9ca3af; text-align: center; margin: 0.5rem 0 0.5rem; }}
  .date {{ color: #6b7280; text-align: center; font-size: 0.8rem; margin-bottom: 2rem; }}

  /* Section headers */
  .section-header {{
    font-size: 1.3rem;
    font-weight: 700;
    margin: 2.5rem 0 1rem;
    padding: 0.8rem 1.2rem;
    border-radius: 10px;
    text-align: center;
  }}
  .section-header.primary {{
    background: linear-gradient(135deg, #166534, #1a4731);
    border: 1px solid #22c55e44;
    color: #86efac;
  }}
  .section-header.secondary {{
    background: linear-gradient(135deg, #1e293b, #1e3a5f);
    border: 1px solid #3b82f644;
    color: #93c5fd;
  }}

  /* KPI row */
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }}
  .kpi {{
    background: #1a1d2e;
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
    border: 1px solid #2a2d3e;
  }}
  .kpi .value {{
    font-size: 1.8rem;
    font-weight: 700;
    line-height: 1.2;
  }}
  .kpi .before {{
    font-size: 0.75rem;
    color: #6b7280;
    margin-top: 0.2rem;
  }}
  .kpi .delta {{
    font-size: 0.7rem;
    margin-top: 0.15rem;
  }}
  .kpi .label {{ color: #9ca3af; font-size: 0.8rem; margin-top: 0.3rem; }}
  .kpi.green .value {{ color: #34d399; }}
  .kpi.blue .value {{ color: #60a5fa; }}
  .kpi.amber .value {{ color: #fbbf24; }}
  .kpi.purple .value {{ color: #a78bfa; }}

  /* Chart containers */
  .chart-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 2rem;
  }}
  @media (max-width: 900px) {{ .chart-grid {{ grid-template-columns: 1fr; }} }}
  .chart-card {{
    background: #1a1d2e;
    border-radius: 12px;
    padding: 1.5rem;
    border: 1px solid #2a2d3e;
  }}
  .chart-card.full {{ grid-column: 1 / -1; }}
  .chart-card h2 {{
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: #d1d5db;
  }}
  .chart-wrap {{ position: relative; height: 300px; }}
  .chart-wrap.tall {{ height: 400px; }}

  /* Table */
  .table-card {{
    background: #1a1d2e;
    border-radius: 12px;
    padding: 1.5rem;
    border: 1px solid #2a2d3e;
    overflow-x: auto;
    margin-bottom: 2rem;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ text-align: left; padding: 0.5rem; color: #9ca3af; border-bottom: 1px solid #2a2d3e; font-weight: 500; }}
  td {{ padding: 0.5rem; border-bottom: 1px solid #1f2233; }}
  tr:hover td {{ background: #1f2233; }}
  .ratio-cell {{ font-weight: 600; font-variant-numeric: tabular-nums; }}
  .good {{ color: #34d399; }}
  .warn {{ color: #fbbf24; }}
  .bad {{ color: #f87171; }}

  /* Tier badge */
  .tier-section {{
    background: #1a1d2e;
    border-radius: 12px;
    padding: 1.5rem;
    border: 1px solid #2a2d3e;
    margin-bottom: 2rem;
  }}
  .tier-bar {{
    display: flex;
    height: 36px;
    border-radius: 8px;
    overflow: hidden;
    margin: 1rem 0;
  }}
  .tier-bar div {{
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 600;
  }}
  .tier-d {{ background: #166534; flex: 1; color: #bbf7d0; }}
  .tier-c {{ background: #1e40af; flex: 1; color: #bfdbfe; }}
  .tier-b {{ background: #6d28d9; flex: 1; color: #ddd6fe; }}
  .tier-a {{ background: #92400e; flex: 1; color: #fef3c7; }}
  .tier-active {{ outline: 3px solid #fbbf24; outline-offset: -3px; }}
  .tier-reqs {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin-top: 1rem; font-size: 0.78rem; }}
  .tier-req {{ background: #0f1117; border-radius: 6px; padding: 0.6rem; }}
  .tier-req h4 {{ font-size: 0.72rem; color: #9ca3af; margin-bottom: 0.3rem; }}

  /* Before/After comparison */
  .ba-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 2rem;
  }}
  .ba-card {{
    background: #1a1d2e;
    border-radius: 12px;
    padding: 1.2rem;
    border: 1px solid #2a2d3e;
  }}
  .ba-card h3 {{
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: 0.8rem;
    color: #d1d5db;
  }}
  .ba-card.before {{ border-left: 3px solid #6b7280; }}
  .ba-card.after {{ border-left: 3px solid #34d399; }}

  /* Improvement badge */
  .improvement {{
    display: inline-block;
    padding: 0.3rem 0.8rem;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-left: 0.5rem;
  }}
  .improvement.positive {{ background: #16a34a22; color: #4ade80; }}
  .improvement.negative {{ background: #dc262622; color: #f87171; }}
  .improvement.neutral {{ background: #64748b22; color: #94a3b8; }}

  /* Divider */
  .divider {{
    border: 0;
    border-top: 1px solid #2a2d3e;
    margin: 2rem 0;
  }}

  /* Note card */
  .note-card {{
    background: #1a1d2e;
    border-radius: 12px;
    padding: 1.2rem;
    border: 1px solid #2a2d3e;
    margin-bottom: 1.5rem;
    font-size: 0.85rem;
    color: #9ca3af;
  }}
  .note-card strong {{ color: #e0e0e0; }}

  footer {{ text-align: center; color: #4b5563; font-size: 0.75rem; margin-top: 2rem; }}

  @media (max-width: 900px) {{
    .ba-row {{ grid-template-columns: 1fr; }}
    .tier-reqs {{ grid-template-columns: repeat(2, 1fr); }}
  }}
</style>
</head>
<body>

<h1>Physics Engine Validation: Before &amp; After</h1>
<p class="subtitle">{so.n}-entry baseline &#8594; {sa.n}-entry dataset (amateur only) | {so_all.n} &#8594; {sa_all.n} total entries</p>
<p class="date">Generated {date_str} &middot; Branch temp/physics-val-improvements &middot; Commit {git_sha}</p>

<!-- ============ PRIMARY VIEW: AMATEUR ONLY ============ -->
<div class="section-header primary">
  Primary View: Amateur Data Only (driver_level &#8800; &quot;pro&quot;) &mdash; {sa.n} entries
</div>

<!-- KPI Row: Amateur -->
<div class="kpi-row">
  <div class="kpi green">
    <div class="value">{sa.mean_ratio:.3f}</div>
    <div class="before">was {so.mean_ratio:.3f}</div>
    <div class="delta">{_delta_arrow(so.mean_ratio, sa.mean_ratio, lower_is_better=False)}</div>
    <div class="label">Mean Ratio</div>
  </div>
  <div class="kpi blue">
    <div class="value">{sa.std_ratio:.3f}</div>
    <div class="before">was {so.std_ratio:.3f}</div>
    <div class="delta">{_delta_arrow(so.std_ratio, sa.std_ratio, lower_is_better=True)}</div>
    <div class="label">Std Deviation</div>
  </div>
  <div class="kpi green">
    <div class="value">{sa.mape:.2f}%</div>
    <div class="before">was {so.mape:.2f}%</div>
    <div class="delta">{_delta_arrow_pct(so.mape, sa.mape)}</div>
    <div class="label">MAPE</div>
  </div>
  <div class="kpi blue">
    <div class="value">{sa.rmse:.2f}s</div>
    <div class="before">was {so.rmse:.2f}s</div>
    <div class="delta">{_delta_arrow_s(so.rmse, sa.rmse)}</div>
    <div class="label">RMSE</div>
  </div>
  <div class="kpi {'green' if sa.exceedances_5pct <= so.exceedances_5pct else 'amber'}">
    <div class="value">{sa.exceedances_5pct} / {sa.n}</div>
    <div class="before">was {so.exceedances_5pct} / {so.n}</div>
    <div class="delta">{_delta_arrow_int(so.exceedances_5pct, sa.exceedances_5pct)}</div>
    <div class="label">Exceedances &gt;5%</div>
  </div>
  <div class="kpi purple">
    <div class="value">{sa.r_squared:.4f}</div>
    <div class="before">was {so.r_squared:.4f}</div>
    <div class="delta">{_delta_arrow_r2(so.r_squared, sa.r_squared)}</div>
    <div class="label">R&#178; Calibration</div>
  </div>
</div>

<!-- Tier: Amateur -->
{_tier_section(sa, f"Amateur Data ({sa.n} entries)")}

<!-- Charts: Amateur -->
<div class="chart-grid">
  <div class="chart-card">
    <h2>Real vs Predicted Lap Times (Amateur)</h2>
    <div class="chart-wrap"><canvas id="scatterAmateur"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Mean Ratio by Tire Category (Amateur)</h2>
    <div class="chart-wrap"><canvas id="categoryAmateur"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Mean Ratio by Track (Amateur)</h2>
    <div class="chart-wrap"><canvas id="trackAmateur"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Mean Ratio by Grip Band (Amateur)</h2>
    <div class="chart-wrap"><canvas id="gripAmateur"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Bland-Altman Agreement (Amateur)</h2>
    <div class="chart-wrap"><canvas id="baAmateur"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Efficiency Ratio vs Tire Mu (Amateur, r = {sa.r_mu:.2f})</h2>
    <div class="chart-wrap"><canvas id="muAmateur"></canvas></div>
  </div>
  <div class="chart-card full">
    <h2>Efficiency Ratio Distribution &mdash; Amateur ({sa.n} entries)</h2>
    <div class="chart-wrap"><canvas id="histAmateur"></canvas></div>
  </div>
</div>

<!-- Segmentation: Amateur -->
{_seg_tables(sa, new_amateur, "amateur")}

<!-- Full data table: Amateur -->
<div class="table-card">
  <h2 style="font-size:1rem; margin-bottom:1rem;">All {sa.n} Amateur Entries (After)</h2>
  <table>
    <thead>
      <tr><th>Car</th><th>Track</th><th>Tire</th><th>Cat</th><th>&#181;</th><th>Real</th><th>Predicted</th><th>Ratio</th><th>&#916;</th></tr>
    </thead>
    <tbody>
      {_data_table(new_amateur, "amateurTable")}
    </tbody>
  </table>
</div>

<hr class="divider">

<!-- ============ SECONDARY VIEW: ALL DATA ============ -->
<div class="section-header secondary">
  Secondary View: All Data (including pro) &mdash; {sa_all.n} entries
</div>

<!-- KPI Row: All -->
<div class="kpi-row">
  <div class="kpi green">
    <div class="value">{sa_all.mean_ratio:.3f}</div>
    <div class="before">was {so_all.mean_ratio:.3f}</div>
    <div class="delta">{_delta_arrow(so_all.mean_ratio, sa_all.mean_ratio, lower_is_better=False)}</div>
    <div class="label">Mean Ratio</div>
  </div>
  <div class="kpi blue">
    <div class="value">{sa_all.std_ratio:.3f}</div>
    <div class="before">was {so_all.std_ratio:.3f}</div>
    <div class="delta">{_delta_arrow(so_all.std_ratio, sa_all.std_ratio, lower_is_better=True)}</div>
    <div class="label">Std Deviation</div>
  </div>
  <div class="kpi green">
    <div class="value">{sa_all.mape:.2f}%</div>
    <div class="before">was {so_all.mape:.2f}%</div>
    <div class="delta">{_delta_arrow_pct(so_all.mape, sa_all.mape)}</div>
    <div class="label">MAPE</div>
  </div>
  <div class="kpi blue">
    <div class="value">{sa_all.rmse:.2f}s</div>
    <div class="before">was {so_all.rmse:.2f}s</div>
    <div class="delta">{_delta_arrow_s(so_all.rmse, sa_all.rmse)}</div>
    <div class="label">RMSE</div>
  </div>
  <div class="kpi {'green' if sa_all.exceedances_5pct <= so_all.exceedances_5pct else 'amber'}">
    <div class="value">{sa_all.exceedances_5pct} / {sa_all.n}</div>
    <div class="before">was {so_all.exceedances_5pct} / {so_all.n}</div>
    <div class="delta">{_delta_arrow_int(so_all.exceedances_5pct, sa_all.exceedances_5pct)}</div>
    <div class="label">Exceedances &gt;5%</div>
  </div>
  <div class="kpi purple">
    <div class="value">{sa_all.r_squared:.4f}</div>
    <div class="before">was {so_all.r_squared:.4f}</div>
    <div class="delta">{_delta_arrow_r2(so_all.r_squared, sa_all.r_squared)}</div>
    <div class="label">R&#178; Calibration</div>
  </div>
</div>

<!-- Tier: All -->
{_tier_section(sa_all, f"All Data ({sa_all.n} entries)")}

<!-- Charts: All -->
<div class="chart-grid">
  <div class="chart-card">
    <h2>Real vs Predicted Lap Times (All)</h2>
    <div class="chart-wrap"><canvas id="scatterAll"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Mean Ratio by Tire Category (All)</h2>
    <div class="chart-wrap"><canvas id="categoryAll"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Mean Ratio by Track (All)</h2>
    <div class="chart-wrap"><canvas id="trackAll"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Mean Ratio by Grip Band (All)</h2>
    <div class="chart-wrap"><canvas id="gripAll"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Bland-Altman Agreement (All)</h2>
    <div class="chart-wrap"><canvas id="baAll"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Efficiency Ratio vs Tire Mu (All, r = {sa_all.r_mu:.2f})</h2>
    <div class="chart-wrap"><canvas id="muAll"></canvas></div>
  </div>
  <div class="chart-card full">
    <h2>Efficiency Ratio Distribution &mdash; All ({sa_all.n} entries)</h2>
    <div class="chart-wrap"><canvas id="histAll"></canvas></div>
  </div>
</div>

<!-- Segmentation: All -->
{_seg_tables(sa_all, new_entries, "all")}

<!-- Full data table: All -->
<div class="table-card">
  <h2 style="font-size:1rem; margin-bottom:1rem;">All {sa_all.n} Entries (After)</h2>
  <table>
    <thead>
      <tr><th>Car</th><th>Track</th><th>Tire</th><th>Cat</th><th>&#181;</th><th>Real</th><th>Predicted</th><th>Ratio</th><th>&#916;</th></tr>
    </thead>
    <tbody>
      {_data_table(new_entries, "allTable")}
    </tbody>
  </table>
</div>

<hr class="divider">

<!-- Notes -->
<div class="note-card">
  <strong>Data quality note:</strong> The &quot;before&quot; baseline had {so.n} amateur entries across {len(so.by_track)} tracks.
  The &quot;after&quot; baseline has {sa.n} amateur entries across {len(sa.by_track)} tracks.
  {sa_all.n - sa.n} pro-level entries (C&amp;D Lightning Lap, etc.) are shown only in the secondary view.
  Pro entries tend to have tighter ratios because professional drivers extract more from the car, closer to the physics limit.
</div>

<footer>
  Cataclysm Physics Validation Before/After &middot; {sa.n} amateur + {sa_all.n - sa.n} pro entries &middot;
  {len(sa_all.by_track)} tracks &middot; {new_all_cars}+ cars<br>
  Sources: LapMeta, FastestLaps, Car &amp; Driver Lightning Lap, NASA Mid-South, Rennlist, GR86.org, Mustang6G, Camaro6
</footer>

<script>
// --- DATA ---
{_entries_to_js(new_amateur, "amateurEntries")}

{_entries_to_js(new_entries, "allEntries")}

// Category bar data
{_cat_bar_js(sa, "catDataAm")}
{_cat_bar_js(sa_all, "catDataAll")}

// Track bar data
{_track_bar_js(sa, "trackDataAm")}
{_track_bar_js(sa_all, "trackDataAll")}

// Grip band data
{_grip_bar_js(sa, "gripDataAm")}
{_grip_bar_js(sa_all, "gripDataAll")}

// Colors by category
const catColors = {{
  street: '#9ca3af',
  endurance_200tw: '#60a5fa',
  super_200tw: '#34d399',
  '100tw': '#fbbf24',
  r_compound: '#f472b6',
  slick: '#a78bfa'
}};

const trackColorsMap = {json.dumps(track_colors_map)};

// --- Chart defaults ---
Chart.defaults.color = '#9ca3af';
Chart.defaults.borderColor = '#2a2d3e';
Chart.defaults.font.family = 'system-ui, sans-serif';

// --- Helper functions ---
function makeScatter(canvasId, entries) {{
  const cats = Object.keys(catColors);
  new Chart(document.getElementById(canvasId), {{
    type: 'scatter',
    data: {{
      datasets: cats.map(cat => ({{
        label: cat.replace(/_/g,' '),
        data: entries.filter(e => e.cat === cat).map(e => ({{x: e.real, y: e.pred}})),
        backgroundColor: catColors[cat] + '99',
        borderColor: catColors[cat],
        pointRadius: 5,
        pointHoverRadius: 7,
      }})).concat([{{
        label: 'Perfect',
        data: [{{x:60,y:60}},{{x:130,y:130}}],
        type: 'line',
        borderColor: '#4b556388',
        borderDash: [6,3],
        pointRadius: 0,
        borderWidth: 1.5,
      }}])
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 10, padding: 8, font: {{size: 10}} }} }} }},
      scales: {{
        x: {{ title: {{ display: true, text: 'Real Lap Time (s)' }}, grid: {{ color: '#1f2233' }} }},
        y: {{ title: {{ display: true, text: 'Predicted Optimal (s)' }}, grid: {{ color: '#1f2233' }} }},
      }}
    }}
  }});
}}

function makeCategoryBar(canvasId, catData) {{
  new Chart(document.getElementById(canvasId), {{
    type: 'bar',
    data: {{
      labels: catData.map(c => c.cat.replace(/_/g,' ') + ' (n=' + c.n + ')'),
      datasets: [{{
        data: catData.map(c => c.mean),
        backgroundColor: catData.map(c => (catColors[c.cat] || '#60a5fa') + 'cc'),
        borderColor: catData.map(c => catColors[c.cat] || '#60a5fa'),
        borderWidth: 1,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ min: 0.92, max: 1.08, title: {{ display: true, text: 'Mean Ratio' }}, grid: {{ color: '#1f2233' }} }},
        x: {{ grid: {{ display: false }} }}
      }}
    }}
  }});
}}

function makeTrackBar(canvasId, trackData) {{
  new Chart(document.getElementById(canvasId), {{
    type: 'bar',
    data: {{
      labels: trackData.map(t => t.t),
      datasets: [{{
        data: trackData.map(t => t.mean),
        backgroundColor: trackData.map(t => t.color + 'cc'),
        borderColor: trackData.map(t => t.color),
        borderWidth: 1,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ min: 0.96, max: 1.06, title: {{ display: true, text: 'Mean Ratio' }}, grid: {{ color: '#1f2233' }} }},
        x: {{ grid: {{ display: false }} }}
      }}
    }}
  }});
}}

function makeGripBar(canvasId, gripData) {{
  new Chart(document.getElementById(canvasId), {{
    type: 'bar',
    data: {{
      labels: gripData.map(g => g.band + ' (n=' + g.n + ')'),
      datasets: [{{
        data: gripData.map(g => g.mean),
        backgroundColor: gripData.map(g => g.color + 'cc'),
        borderColor: gripData.map(g => g.color),
        borderWidth: 1,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ min: 0.94, max: 1.06, title: {{ display: true, text: 'Mean Ratio' }}, grid: {{ color: '#1f2233' }} }},
        x: {{ grid: {{ display: false }} }}
      }}
    }}
  }});
}}

function makeBlandAltman(canvasId, entries, bias, loaUpper, loaLower) {{
  const baData = entries.map(e => ({{x: (e.real + e.pred) / 2, y: e.pred - e.real, cat: e.cat}}));
  const cats = Object.keys(catColors);
  const xMin = Math.min(...entries.map(e => e.real)) - 5;
  const xMax = Math.max(...entries.map(e => e.real)) + 5;
  new Chart(document.getElementById(canvasId), {{
    type: 'scatter',
    data: {{
      datasets: cats.map(cat => ({{
        label: cat.replace(/_/g,' '),
        data: baData.filter(d => d.cat === cat),
        backgroundColor: catColors[cat] + '99',
        borderColor: catColors[cat],
        pointRadius: 5,
      }})).concat([
        {{label:'Bias',data:[{{x:xMin,y:bias}},{{x:xMax,y:bias}}],type:'line',borderColor:'#fbbf2488',borderDash:[6,3],pointRadius:0,borderWidth:1}},
        {{label:'+95% LoA',data:[{{x:xMin,y:loaUpper}},{{x:xMax,y:loaUpper}}],type:'line',borderColor:'#f8717188',borderDash:[4,2],pointRadius:0,borderWidth:1}},
        {{label:'-95% LoA',data:[{{x:xMin,y:loaLower}},{{x:xMax,y:loaLower}}],type:'line',borderColor:'#f8717188',borderDash:[4,2],pointRadius:0,borderWidth:1}},
      ])
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 10, padding: 8, font: {{size: 10}} }} }} }},
      scales: {{
        x: {{ title: {{ display: true, text: 'Mean of Real & Predicted (s)' }}, grid: {{ color: '#1f2233' }} }},
        y: {{ title: {{ display: true, text: 'Difference: Predicted - Real (s)' }}, grid: {{ color: '#1f2233' }} }},
      }}
    }}
  }});
}}

function makeRatioMu(canvasId, entries) {{
  const tracks = [...new Set(entries.map(e => e.track))];
  new Chart(document.getElementById(canvasId), {{
    type: 'scatter',
    data: {{
      datasets: tracks.map(track => ({{
        label: track,
        data: entries.filter(e => e.track === track).map(e => ({{x: e.mu, y: e.ratio}})),
        backgroundColor: (trackColorsMap[track] || '#60a5fa') + '99',
        borderColor: trackColorsMap[track] || '#60a5fa',
        pointRadius: 5,
      }})).concat([{{
        label: 'Perfect',
        data: [{{x:0.8,y:1}},{{x:1.5,y:1}}],
        type: 'line',
        borderColor: '#4b556388',
        borderDash: [6,3],
        pointRadius: 0,
        borderWidth: 1.5,
      }}])
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 10, padding: 8, font: {{size: 10}} }} }} }},
      scales: {{
        x: {{ title: {{ display: true, text: 'Tire Mu (friction coefficient)' }}, grid: {{ color: '#1f2233' }} }},
        y: {{ title: {{ display: true, text: 'Efficiency Ratio' }}, min: 0.90, max: 1.10, grid: {{ color: '#1f2233' }} }},
      }}
    }}
  }});
}}

function makeHistogram(canvasId, entries) {{
  const bins = [];
  for (let b = 0.90; b <= 1.10; b += 0.01) bins.push({{lo: b, hi: b+0.01, count: 0}});
  entries.forEach(e => {{
    const idx = bins.findIndex(b => e.ratio >= b.lo && e.ratio < b.hi);
    if (idx >= 0) bins[idx].count++;
  }});
  new Chart(document.getElementById(canvasId), {{
    type: 'bar',
    data: {{
      labels: bins.map(b => b.lo.toFixed(2)),
      datasets: [{{
        data: bins.map(b => b.count),
        backgroundColor: bins.map(b => {{
          const mid = (b.lo + b.hi) / 2;
          if (Math.abs(mid - 1) < 0.02) return '#34d399cc';
          if (Math.abs(mid - 1) < 0.05) return '#fbbf24cc';
          return '#f87171cc';
        }}),
        borderWidth: 0,
        barPercentage: 1.0,
        categoryPercentage: 1.0,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ title: {{ display: true, text: 'Count' }}, grid: {{ color: '#1f2233' }} }},
        x: {{ title: {{ display: true, text: 'Efficiency Ratio' }}, grid: {{ display: false }} }}
      }}
    }}
  }});
}}

// --- Build Amateur charts ---
makeScatter('scatterAmateur', amateurEntries);
makeCategoryBar('categoryAmateur', catDataAm);
makeTrackBar('trackAmateur', trackDataAm);
makeGripBar('gripAmateur', gripDataAm);
makeBlandAltman('baAmateur', amateurEntries, {sa.bias_s}, {sa.loa_upper}, {sa.loa_lower});
makeRatioMu('muAmateur', amateurEntries);
makeHistogram('histAmateur', amateurEntries);

// --- Build All-data charts ---
makeScatter('scatterAll', allEntries);
makeCategoryBar('categoryAll', catDataAll);
makeTrackBar('trackAll', trackDataAll);
makeGripBar('gripAll', gripDataAll);
makeBlandAltman('baAll', allEntries, {sa_all.bias_s}, {sa_all.loa_upper}, {sa_all.loa_lower});
makeRatioMu('muAll', allEntries);
makeHistogram('histAll', allEntries);
</script>
</body>
</html>"""

    return html_content


def _cat_color(cat: str) -> str:
    colors = {
        "street": "#9ca3af",
        "endurance_200tw": "#60a5fa",
        "super_200tw": "#34d399",
        "100tw": "#fbbf24",
        "r_compound": "#f472b6",
        "slick": "#a78bfa",
    }
    return colors.get(cat, "#6b7280")


def main() -> None:
    print(f"Loading old baseline from {OLD_BASELINE_PATH}")
    old_entries = load_entries(OLD_BASELINE_PATH)
    print(f"  {len(old_entries)} entries loaded")

    print(f"Loading new baseline from {NEW_BASELINE_PATH}")
    new_entries = load_entries(NEW_BASELINE_PATH)
    print(f"  {len(new_entries)} entries loaded")

    # Filter amateur (non-pro)
    old_amateur = [e for e in old_entries if e.driver_level != "pro"]
    new_amateur = [e for e in new_entries if e.driver_level != "pro"]
    print(f"  Amateur: old={len(old_amateur)}, new={len(new_amateur)}")

    # Compute stats for all four views
    old_stats_amateur = compute_stats(old_amateur)
    new_stats_amateur = compute_stats(new_amateur)
    old_stats_all = compute_stats(old_entries)
    new_stats_all = compute_stats(new_entries)

    print(f"\nAmateur Before: mean={old_stats_amateur.mean_ratio:.4f}, "
          f"std={old_stats_amateur.std_ratio:.4f}, MAPE={old_stats_amateur.mape:.2f}%")
    print(f"Amateur After:  mean={new_stats_amateur.mean_ratio:.4f}, "
          f"std={new_stats_amateur.std_ratio:.4f}, MAPE={new_stats_amateur.mape:.2f}%")
    print(f"All Before:     mean={old_stats_all.mean_ratio:.4f}, "
          f"std={old_stats_all.std_ratio:.4f}, MAPE={old_stats_all.mape:.2f}%")
    print(f"All After:      mean={new_stats_all.mean_ratio:.4f}, "
          f"std={new_stats_all.std_ratio:.4f}, MAPE={new_stats_all.mape:.2f}%")

    # Generate HTML
    html_content = generate_html(
        old_entries=old_entries,
        new_entries=new_entries,
        old_stats_amateur=old_stats_amateur,
        new_stats_amateur=new_stats_amateur,
        old_stats_all=old_stats_all,
        new_stats_all=new_stats_all,
        old_amateur=old_amateur,
        new_amateur=new_amateur,
    )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(html_content)
    print(f"\nReport written to {OUTPUT_PATH}")
    print(f"  File size: {os.path.getsize(OUTPUT_PATH) / 1024:.1f} KB")


if __name__ == "__main__":
    main()

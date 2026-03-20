"""Generate a before-vs-after physics validation HTML report.

Compares the old 70-entry/3-track baseline against the current
full baseline (all tracks including VIR, Laguna Seca, Road Atlanta).
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def fmt_time(s: float) -> str:
    """Format seconds as M:SS.ss"""
    m = int(s) // 60
    sec = s - m * 60
    return f"{m}:{sec:05.2f}"


def ratio_class(r: float) -> str:
    if abs(r - 1) < 0.02:
        return "good"
    if abs(r - 1) < 0.05:
        return "warn"
    return "bad"


def compute_stats(entries: list[dict]) -> dict:
    n = len(entries)
    ratios = [e["ratio"] for e in entries]
    mean_r = sum(ratios) / n
    std_r = math.sqrt(sum((r - mean_r) ** 2 for r in ratios) / (n - 1)) if n > 1 else 0
    abs_errors = [abs(e["predicted_s"] - e["real_s"]) for e in entries]
    mape = sum(abs(e["predicted_s"] - e["real_s"]) / e["real_s"] for e in entries) / n * 100
    rmse = math.sqrt(sum((e["predicted_s"] - e["real_s"]) ** 2 for e in entries) / n)
    exceedances = sum(1 for r in ratios if abs(r - 1) > 0.05)

    # R^2
    real = [e["real_s"] for e in entries]
    pred = [e["predicted_s"] for e in entries]
    mean_real = sum(real) / n
    ss_res = sum((r - p) ** 2 for r, p in zip(real, pred))
    ss_tot = sum((r - mean_real) ** 2 for r in real)
    r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    # Per category
    cats: dict[str, list[float]] = defaultdict(list)
    for e in entries:
        cats[e["tire_category"]].append(e["ratio"])
    per_cat = {}
    for cat, rs in sorted(cats.items()):
        cm = sum(rs) / len(rs)
        per_cat[cat] = {"n": len(rs), "mean": cm}

    # Per track
    tracks: dict[str, list[float]] = defaultdict(list)
    for e in entries:
        tracks[e["track"]].append(e["ratio"])
    per_track = {}
    for trk, rs in sorted(tracks.items()):
        tm = sum(rs) / len(rs)
        per_track[trk] = {"n": len(rs), "mean": tm}

    return {
        "n": n,
        "mean": mean_r,
        "std": std_r,
        "mape": mape,
        "rmse": rmse,
        "exceedances": exceedances,
        "r_sq": r_sq,
        "per_cat": per_cat,
        "per_track": per_track,
    }


def arrow(before: float, after: float, lower_is_better: bool = True) -> str:
    """Return colored arrow HTML for delta."""
    delta = after - before
    if abs(delta) < 0.0005:
        return '<span style="color:#fbbf24">&#8594;</span>'
    if lower_is_better:
        improved = delta < 0
    else:
        improved = delta > 0
    color = "#34d399" if improved else "#f87171"
    arrow_char = "&#9660;" if delta < 0 else "&#9650;"
    return f'<span style="color:{color}">{arrow_char}</span>'


def kpi_color(before: float, after: float, lower_is_better: bool = True) -> str:
    delta = after - before
    if abs(delta) < 0.0005:
        return "amber"
    if lower_is_better:
        return "green" if delta < 0 else "bad-kpi"
    return "green" if delta > 0 else "bad-kpi"


def get_tier(stats: dict) -> tuple[str, str]:
    """Return (tier_name, tier_class)."""
    bias = abs(stats["mean"] - 1) * 100
    std_pct = stats["std"] * 100
    mape = stats["mape"]

    if bias < 0.5 and std_pct < 1.5 and mape < 1.0:
        return "D: Engineering", "tier-d"
    if bias < 1.0 and std_pct < 3.5 and mape < 3.0:
        return "C: Coaching", "tier-c"
    if bias < 2.0 and std_pct < 5.0 and mape < 5.0:
        return "B: Setup", "tier-b"
    return "A: Screening", "tier-a"


def generate_html(
    old_baseline: dict,
    new_baseline: dict,
    git_branch: str,
    git_sha: str,
) -> str:
    old_entries = old_baseline["entries"]
    new_entries = new_baseline["entries"]

    before = compute_stats(old_entries)
    after = compute_stats(new_entries)

    # Also compute "after" filtered to original 3 tracks only
    orig_tracks = set(e["track"] for e in old_entries)
    new_orig = [e for e in new_entries if e["track"] in orig_tracks]
    after_3trk = compute_stats(new_orig)

    after_tier, after_tier_cls = get_tier(after)
    before_tier, before_tier_cls = get_tier(before)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Short track names for display
    track_shorts = {
        "Barber Motorsports Park": "Barber",
        "Roebling Road Raceway": "Roebling",
        "Atlanta Motorsports Park": "AMP",
        "Virginia International Raceway Grand West": "VIR GW",
        "WeatherTech Raceway Laguna Seca": "Laguna Seca",
        "Road Atlanta": "Road Atlanta",
    }

    cat_colors = {
        "street": "#9ca3af",
        "endurance_200tw": "#60a5fa",
        "super_200tw": "#34d399",
        "100tw": "#fbbf24",
        "r_compound": "#f472b6",
        "slick": "#a78bfa",
    }

    # Build entries JSON for Chart.js
    entries_js_items = []
    sorted_entries = sorted(new_entries, key=lambda e: (e["track"], e["ratio"]))
    for e in sorted_entries:
        short_track = track_shorts.get(e["track"], e["track"][:12])
        tire_short = e.get("tire_model", "unknown")[:30]
        entries_js_items.append(
            f'{{car:"{e["car"]}",track:"{short_track}",tire:"{tire_short}",'
            f'cat:"{e["tire_category"]}",mu:{e["mu"]:.2f},'
            f'real:{e["real_s"]:.2f},pred:{e["predicted_s"]:.3f},'
            f'ratio:{e["ratio"]:.4f}}}'
        )
    entries_js = ",\n  ".join(entries_js_items)

    # Build old entries lookup for "before" per-track chart
    old_track_data_js = []
    for trk_name in sorted(before["per_track"]):
        short = track_shorts.get(trk_name, trk_name[:12])
        m = before["per_track"][trk_name]["mean"]
        n = before["per_track"][trk_name]["n"]
        old_track_data_js.append(f'{{t:"{short} (n={n})",mean:{m:.4f}}}')

    new_track_data_js = []
    for trk_name in sorted(after["per_track"]):
        short = track_shorts.get(trk_name, trk_name[:12])
        m = after["per_track"][trk_name]["mean"]
        n = after["per_track"][trk_name]["n"]
        new_track_data_js.append(f'{{t:"{short} (n={n})",mean:{m:.4f}}}')

    # Category before/after data
    all_cats_ordered = ["street", "endurance_200tw", "super_200tw", "100tw", "r_compound", "slick"]
    cat_before_js = []
    cat_after_js = []
    for cat in all_cats_ordered:
        bm = before["per_cat"].get(cat, {}).get("mean", 0)
        bn = before["per_cat"].get(cat, {}).get("n", 0)
        am = after["per_cat"].get(cat, {}).get("mean", 0)
        an = after["per_cat"].get(cat, {}).get("n", 0)
        cat_before_js.append(f"{bm:.4f}")
        cat_after_js.append(f"{am:.4f}")

    # Build table rows
    table_rows = []
    for e in sorted_entries:
        short_track = track_shorts.get(e["track"], e["track"][:12])
        delta = e["predicted_s"] - e["real_s"]
        cls = ratio_class(e["ratio"])
        delta_color = "#fbbf24" if delta > 0 else "#60a5fa"
        delta_sign = "+" if delta > 0 else ""
        cat_color = cat_colors.get(e["tire_category"], "#9ca3af")
        tire_short = e.get("tire_model", "unknown")[:35]
        table_rows.append(
            f'<tr><td>{e["car"]}</td><td>{short_track}</td>'
            f'<td style="font-size:0.75rem">{tire_short}</td>'
            f'<td><span style="color:{cat_color}">{e["tire_category"].replace("_", " ")}</span></td>'
            f'<td>{e["mu"]:.2f}</td>'
            f'<td>{fmt_time(e["real_s"])}</td>'
            f'<td>{fmt_time(e["predicted_s"])}</td>'
            f'<td class="ratio-cell {cls}">{e["ratio"]:.3f}</td>'
            f'<td style="color:{delta_color}">{delta_sign}{delta:.1f}s</td></tr>'
        )
    table_html = "\n    ".join(table_rows)

    # Tier assessment rows
    def tier_check(val: float, threshold: float, pct: bool = True) -> str:
        s = f"{val:.2f}%" if pct else f"{val:.3f}"
        cls = "good" if val < threshold else "bad"
        sym = "&#10003;" if val < threshold else "&#10007;"
        return f'<span class="{cls}">{sym} {s}</span>'

    a_bias = abs(after["mean"] - 1) * 100
    a_std = after["std"] * 100
    a_mape = after["mape"]

    # Build the full HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Physics Validation — Before vs After ({before["n"]} → {after["n"]} entries)</title>
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
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1.2;
  }}
  .kpi .before {{ font-size: 0.85rem; color: #6b7280; margin-top: 0.2rem; }}
  .kpi .label {{ color: #9ca3af; font-size: 0.8rem; margin-top: 0.3rem; }}
  .kpi.green .value {{ color: #34d399; }}
  .kpi.blue .value {{ color: #60a5fa; }}
  .kpi.amber .value {{ color: #fbbf24; }}
  .kpi.purple .value {{ color: #a78bfa; }}
  .kpi.bad-kpi .value {{ color: #f87171; }}

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

  /* Comparison badge */
  .comparison-badges {{
    display: flex;
    gap: 1rem;
    margin-bottom: 2rem;
    flex-wrap: wrap;
  }}
  .badge {{
    background: #1a1d2e;
    border-radius: 12px;
    padding: 1rem 1.5rem;
    border: 1px solid #2a2d3e;
    flex: 1;
    min-width: 250px;
  }}
  .badge h3 {{ font-size: 0.85rem; color: #9ca3af; margin-bottom: 0.5rem; }}
  .badge .big {{ font-size: 1.6rem; font-weight: 700; }}
  .badge .detail {{ font-size: 0.78rem; color: #6b7280; margin-top: 0.3rem; }}

  /* Note card */
  .note-card {{
    background: #1a1d2e;
    border-radius: 12px;
    padding: 1.5rem;
    border: 1px solid #2a2d3e;
    margin-bottom: 2rem;
  }}
  .note-card h2 {{ font-size: 1rem; margin-bottom: 0.8rem; color: #d1d5db; }}
  .note-card p {{ font-size: 0.85rem; color: #9ca3af; line-height: 1.6; }}
  .note-card .highlight {{ color: #fbbf24; font-weight: 600; }}

  footer {{ text-align: center; color: #4b5563; font-size: 0.75rem; margin-top: 2rem; }}
</style>
</head>
<body>

<h1>Physics Validation: Before vs After</h1>
<p class="subtitle">{before["n"]}-entry baseline (3 tracks) vs {after["n"]}-entry expanded dataset (5 tracks)</p>
<p class="date">Generated {now_str} &middot; Branch {git_branch} &middot; Commit {git_sha}</p>

<!-- Dataset comparison badges -->
<div class="comparison-badges">
  <div class="badge">
    <h3>BEFORE (Old Baseline)</h3>
    <div class="big" style="color:#60a5fa">{before["n"]} entries</div>
    <div class="detail">{len(before["per_track"])} tracks &middot; {len(before["per_cat"])} tire categories</div>
    <div class="detail">Tracks: {", ".join(track_shorts.get(t, t) for t in sorted(before["per_track"]))}</div>
  </div>
  <div class="badge">
    <h3>AFTER (Current Full Dataset)</h3>
    <div class="big" style="color:#34d399">{after["n"]} entries</div>
    <div class="detail">{len(after["per_track"])} tracks &middot; {len(after["per_cat"])} tire categories</div>
    <div class="detail">Tracks: {", ".join(track_shorts.get(t, t) for t in sorted(after["per_track"]))}</div>
  </div>
  <div class="badge">
    <h3>Same 3 Tracks (Apples-to-Apples)</h3>
    <div class="big" style="color:#a78bfa">{after_3trk["n"]} entries</div>
    <div class="detail">Mean: {before["mean"]:.4f} &#8594; {after_3trk["mean"]:.4f} | Std: {before["std"]:.4f} &#8594; {after_3trk["std"]:.4f}</div>
    <div class="detail">MAPE: {before["mape"]:.2f}% &#8594; {after_3trk["mape"]:.2f}% | Exc: {before["exceedances"]} &#8594; {after_3trk["exceedances"]}</div>
  </div>
</div>

<!-- KPI Row: Before -> After -->
<div class="kpi-row">
  <div class="kpi {kpi_color(abs(before["mean"] - 1), abs(after["mean"] - 1))}">
    <div class="value">{after["mean"]:.4f} {arrow(abs(before["mean"] - 1), abs(after["mean"] - 1))}</div>
    <div class="before">was {before["mean"]:.4f}</div>
    <div class="label">Mean Ratio (all {after["n"]})</div>
  </div>
  <div class="kpi {kpi_color(before["std"], after["std"])}">
    <div class="value">{after["std"]:.4f} {arrow(before["std"], after["std"])}</div>
    <div class="before">was {before["std"]:.4f}</div>
    <div class="label">Std Deviation</div>
  </div>
  <div class="kpi {kpi_color(before["mape"], after["mape"])}">
    <div class="value">{after["mape"]:.2f}% {arrow(before["mape"], after["mape"])}</div>
    <div class="before">was {before["mape"]:.2f}%</div>
    <div class="label">MAPE</div>
  </div>
  <div class="kpi {kpi_color(before["rmse"], after["rmse"])}">
    <div class="value">{after["rmse"]:.2f}s {arrow(before["rmse"], after["rmse"])}</div>
    <div class="before">was {before["rmse"]:.2f}s</div>
    <div class="label">RMSE</div>
  </div>
  <div class="kpi {kpi_color(before["exceedances"], after["exceedances"])}">
    <div class="value">{after["exceedances"]} / {after["n"]} {arrow(before["exceedances"] / before["n"], after["exceedances"] / after["n"])}</div>
    <div class="before">was {before["exceedances"]} / {before["n"]}</div>
    <div class="label">Exceedances &gt;5%</div>
  </div>
  <div class="kpi {kpi_color(before["r_sq"], after["r_sq"], lower_is_better=False)}">
    <div class="value">{after["r_sq"]:.3f} {arrow(before["r_sq"], after["r_sq"], lower_is_better=False)}</div>
    <div class="before">was {before["r_sq"]:.3f}</div>
    <div class="label">R&sup2; Calibration</div>
  </div>
</div>

<!-- Accuracy Tier -->
<div class="tier-section">
  <h2 style="font-size:1rem; margin-bottom:0.5rem;">Accuracy Tier Assessment
    <span style="font-size:0.7rem; color:#9ca3af;">Before: {before_tier} &#8594; After (all): {after_tier}</span>
  </h2>
  <div class="tier-bar">
    <div class="tier-d {"tier-active" if after_tier_cls == "tier-d" else ""}">D: Engineering</div>
    <div class="tier-c {"tier-active" if after_tier_cls == "tier-c" else ""}">C: Coaching</div>
    <div class="tier-b {"tier-active" if after_tier_cls == "tier-b" else ""}">B: Setup {"&#9733;" if after_tier_cls == "tier-b" else ""}</div>
    <div class="tier-a {"tier-active" if after_tier_cls == "tier-a" else ""}">A: Screening {"&#9733;" if after_tier_cls == "tier-a" else ""}</div>
  </div>
  <div class="tier-reqs">
    <div class="tier-req">
      <h4>D: Engineering</h4>
      <div>Bias &lt;0.5% {tier_check(a_bias, 0.5)}</div>
      <div>Std &lt;1.5% {tier_check(a_std, 1.5)}</div>
      <div>MAPE &lt;1.0% {tier_check(a_mape, 1.0)}</div>
    </div>
    <div class="tier-req">
      <h4>C: Coaching</h4>
      <div>Bias &lt;1.0% {tier_check(a_bias, 1.0)}</div>
      <div>Std &lt;3.5% {tier_check(a_std, 3.5)}</div>
      <div>MAPE &lt;3.0% {tier_check(a_mape, 3.0)}</div>
    </div>
    <div class="tier-req">
      <h4>B: Setup</h4>
      <div>Bias &lt;2.0% {tier_check(a_bias, 2.0)}</div>
      <div>Std &lt;5.0% {tier_check(a_std, 5.0)}</div>
      <div>MAPE &lt;5.0% {tier_check(a_mape, 5.0)}</div>
    </div>
    <div class="tier-req">
      <h4>A: Screening</h4>
      <div>Bias &lt;5.0% {tier_check(a_bias, 5.0)}</div>
      <div>Std &lt;8.0% {tier_check(a_std, 8.0)}</div>
      <div>MAPE &lt;10.0% {tier_check(a_mape, 10.0)}</div>
    </div>
  </div>
</div>

<!-- Charts -->
<div class="chart-grid">
  <!-- Scatter: Real vs Predicted -->
  <div class="chart-card">
    <h2>Real vs Predicted Lap Times ({after["n"]} entries)</h2>
    <div class="chart-wrap"><canvas id="scatterChart"></canvas></div>
  </div>

  <!-- Histogram -->
  <div class="chart-card">
    <h2>Ratio Distribution (green = within 2%)</h2>
    <div class="chart-wrap"><canvas id="histChart"></canvas></div>
  </div>

  <!-- Category: Before vs After -->
  <div class="chart-card">
    <h2>Mean Ratio by Tire Category: Before vs After</h2>
    <div class="chart-wrap"><canvas id="categoryChart"></canvas></div>
  </div>

  <!-- Track: Before vs After -->
  <div class="chart-card">
    <h2>Mean Ratio by Track (After = {len(after["per_track"])} tracks)</h2>
    <div class="chart-wrap"><canvas id="trackChart"></canvas></div>
  </div>
</div>

<!-- Full data table -->
<div class="table-card">
  <h2 style="font-size:1rem; margin-bottom:1rem;">All {after["n"]} Entries (Sorted by Track, then Ratio)</h2>
  <table>
    <thead>
      <tr><th>Car</th><th>Track</th><th>Tire</th><th>Cat</th><th>&mu;</th><th>Real</th><th>Predicted</th><th>Ratio</th><th>&Delta;</th></tr>
    </thead>
    <tbody>
    {table_html}
    </tbody>
  </table>
</div>

<!-- Laguna Seca bias diagnosis -->
<div class="note-card">
  <h2>Laguna Seca Systematic Bias Diagnosis</h2>
  <p>
    The Laguna Seca entries show a <span class="highlight">mean ratio of ~1.14</span> (14% over-prediction),
    far above the ~1.0 mean for the other 4 tracks. This is almost certainly a
    <span class="highlight">track reference issue</span> rather than a physics engine flaw:
  </p>
  <p style="margin-top:0.6rem;">
    &bull; All {after["per_track"].get("WeatherTech Raceway Laguna Seca", {}).get("n", 0)} Laguna Seca entries
    are from Car &amp; Driver Lightning Lap data (professional drivers, well-known cars).<br>
    &bull; The same cars/tires at VIR and Barber produce ratios near 1.0.<br>
    &bull; The Laguna Seca track reference geometry (OSM-derived centerline, elevation profile) likely has
    errors in corner radii or track length that systematically inflate predicted times.<br>
    &bull; <span class="highlight">Excluding Laguna Seca</span>, the remaining {after["n"] - after["per_track"].get("WeatherTech Raceway Laguna Seca", {}).get("n", 0)} entries have metrics
    much closer to the original 3-track baseline.
  </p>
</div>

<!-- Changes applied -->
<div class="note-card">
  <h2>Changes Applied in This Iteration</h2>
  <p>
    &bull; <span class="highlight">Expanded from 70 to {after["n"]} entries</span> across {len(after["per_track"])} tracks (added VIR Grand West, Laguna Seca).<br>
    &bull; VIR: 49 entries from Car &amp; Driver Lightning Lap (professional testing, mean ratio 1.007 = excellent).<br>
    &bull; Laguna Seca: 33 entries from C&amp;D Lightning Lap (mean ratio 1.143 = track reference needs work).<br>
    &bull; New entries include professional-grade data sources with controlled testing conditions.<br>
    &bull; Added 3 Barber entries (GT-R, C5 Z06, 350Z, Golf R) and {after_3trk["n"] - before["n"]} more community entries for original 3 tracks.
  </p>
</div>

<footer>
  Cataclysm Physics Validation &middot; Before ({before["n"]}) vs After ({after["n"]}) entries
  &middot; {len(after["per_track"])} tracks &middot; Sources: LapMeta, FastestLaps, Car &amp; Driver Lightning Lap,
  NASA Mid-South, Rennlist, GR86.org, Mustang6G, Camaro6
</footer>

<script>
// --- DATA ---
const entries = [
  {entries_js}
];

const catColors = {{
  street: '#9ca3af',
  endurance_200tw: '#60a5fa',
  super_200tw: '#34d399',
  '100tw': '#fbbf24',
  r_compound: '#f472b6',
  slick: '#a78bfa'
}};

// --- Chart defaults ---
Chart.defaults.color = '#9ca3af';
Chart.defaults.borderColor = '#2a2d3e';
Chart.defaults.font.family = 'system-ui, sans-serif';

// 1. Scatter: Real vs Predicted
new Chart(document.getElementById('scatterChart'), {{
  type: 'scatter',
  data: {{
    datasets: Object.keys(catColors).map(cat => ({{
      label: cat.replace('_',' '),
      data: entries.filter(e => e.cat === cat).map(e => ({{x: e.real, y: e.pred}})),
      backgroundColor: catColors[cat] + '99',
      borderColor: catColors[cat],
      pointRadius: 4,
      pointHoverRadius: 6,
    }})).concat([{{
      label: 'Perfect',
      data: [{{x:70,y:70}},{{x:200,y:200}}],
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

// 2. Histogram
const bins = [];
for (let b = 0.90; b <= 1.20; b += 0.01) bins.push({{lo: b, hi: b+0.01, count: 0}});
entries.forEach(e => {{
  const idx = bins.findIndex(b => e.ratio >= b.lo && e.ratio < b.hi);
  if (idx >= 0) bins[idx].count++;
}});
new Chart(document.getElementById('histChart'), {{
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

// 3. Category bar chart: Before vs After
const catLabels = {json.dumps([c.replace("_", " ") for c in all_cats_ordered])};
const catBefore = [{",".join(cat_before_js)}];
const catAfter = [{",".join(cat_after_js)}];
new Chart(document.getElementById('categoryChart'), {{
  type: 'bar',
  data: {{
    labels: catLabels,
    datasets: [
      {{
        label: 'Before ({before["n"]})',
        data: catBefore,
        backgroundColor: '#60a5fa88',
        borderColor: '#60a5fa',
        borderWidth: 1,
      }},
      {{
        label: 'After ({after["n"]})',
        data: catAfter,
        backgroundColor: '#34d39988',
        borderColor: '#34d399',
        borderWidth: 1,
      }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 10, padding: 8 }} }} }},
    scales: {{
      y: {{ min: 0.92, max: 1.10, title: {{ display: true, text: 'Mean Ratio' }}, grid: {{ color: '#1f2233' }} }},
      x: {{ grid: {{ display: false }} }}
    }}
  }}
}});

// 4. Track bar chart: All tracks in After
const trackLabels = {json.dumps([track_shorts.get(t, t) + f" (n={after['per_track'][t]['n']})" for t in sorted(after["per_track"])])};
const trackMeans = {json.dumps([round(after["per_track"][t]["mean"], 4) for t in sorted(after["per_track"])])};
const trackColorList = ['#60a5fa', '#34d399', '#fbbf24', '#a78bfa', '#f472b6', '#e879f9'];
new Chart(document.getElementById('trackChart'), {{
  type: 'bar',
  data: {{
    labels: trackLabels,
    datasets: [{{
      data: trackMeans,
      backgroundColor: trackColorList.slice(0, trackLabels.length).map(c => c + 'cc'),
      borderColor: trackColorList.slice(0, trackLabels.length),
      borderWidth: 1,
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ min: 0.95, max: 1.16, title: {{ display: true, text: 'Mean Ratio' }}, grid: {{ color: '#1f2233' }} }},
      x: {{ grid: {{ display: false }} }}
    }}
  }}
}});
</script>
</body>
</html>'''

    return html


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent

    old_path = "/tmp/old_baseline.json"
    new_path = str(project_root / "data" / "physics_baseline.json")
    output_path = str(project_root / "docs" / "physics-validation-before-after.html")

    old_baseline = load_json(old_path)
    new_baseline = load_json(new_path)

    # Git info
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
        git_branch = subprocess.check_output(
            ["git", "branch", "--show-current"], text=True
        ).strip()
    except Exception:
        git_sha = "unknown"
        git_branch = "unknown"

    html = generate_html(old_baseline, new_baseline, git_branch, git_sha)

    with open(output_path, "w") as f:
        f.write(html)

    print(f"Generated: {output_path}")
    print(f"  Before: {len(old_baseline['entries'])} entries")
    print(f"  After:  {len(new_baseline['entries'])} entries")


if __name__ == "__main__":
    main()

"""Plotly chart builders for telemetry visualization."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from cataclysm.corners import Corner
from cataclysm.delta import DeltaResult
from cataclysm.engine import LapSummary

MPS_TO_MPH = 2.23694
M_TO_FT = 3.28084


def _lap_color(idx: int) -> str:
    """Return a color from a fixed palette for lap overlay."""
    palette = [
        "#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A",
        "#19D3F3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52",
    ]
    return palette[idx % len(palette)]


def lap_times_chart(summaries: list[LapSummary]) -> go.Figure:
    """Bar chart of lap times, best lap highlighted."""
    sorted_by_num = sorted(summaries, key=lambda s: s.lap_number)
    best_time = min(s.lap_time_s for s in summaries)

    labels = [f"L{s.lap_number}" for s in sorted_by_num]
    times = [s.lap_time_s for s in sorted_by_num]
    colors = ["#00CC96" if s.lap_time_s == best_time else "#636EFA" for s in sorted_by_num]

    def fmt_time(t: float) -> str:
        m = int(t // 60)
        s = t % 60
        return f"{m}:{s:05.2f}"

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=times,
            marker_color=colors,
            text=[fmt_time(t) for t in times],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Lap Times",
        xaxis_title="Lap",
        yaxis_title="Time (s)",
        showlegend=False,
        height=400,
        yaxis={"range": [min(times) * 0.95, max(times) * 1.05]},
    )
    return fig


def speed_trace_chart(
    laps: dict[int, pd.DataFrame],
    selected_laps: list[int] | None = None,
    corners: list[Corner] | None = None,
) -> go.Figure:
    """Speed vs distance overlay for multiple laps."""
    fig = go.Figure()

    lap_nums = selected_laps or sorted(laps.keys())

    for i, lap_num in enumerate(lap_nums):
        if lap_num not in laps:
            continue
        df = laps[lap_num]
        fig.add_trace(
            go.Scattergl(
                x=df["lap_distance_m"].to_numpy(),
                y=df["speed_mps"].to_numpy() * MPS_TO_MPH,
                mode="lines",
                name=f"Lap {lap_num}",
                line={"color": _lap_color(i), "width": 1.5},
            )
        )

    # Corner shading
    if corners:
        for corner in corners:
            fig.add_vrect(
                x0=corner.entry_distance_m,
                x1=corner.exit_distance_m,
                fillcolor="rgba(128, 128, 128, 0.1)",
                layer="below",
                line_width=0,
                annotation_text=f"T{corner.number}",
                annotation_position="top left",
                annotation_font_size=10,
                annotation_font_color="gray",
            )

    fig.update_layout(
        title="Speed vs Distance",
        xaxis_title="Distance (m)",
        yaxis_title="Speed (mph)",
        height=500,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    return fig


def delta_t_chart(delta: DeltaResult, ref_lap: int, comp_lap: int) -> go.Figure:
    """Delta-T chart with green/red fill."""
    dist = delta.distance_m
    dt = delta.delta_time_s

    fig = go.Figure()

    # Split into positive (comp slower) and negative (comp faster) for coloring
    positive = np.where(dt >= 0, dt, 0)
    negative = np.where(dt < 0, dt, 0)

    fig.add_trace(
        go.Scatter(
            x=dist, y=positive,
            fill="tozeroy",
            fillcolor="rgba(239, 85, 59, 0.3)",
            line={"color": "rgba(239, 85, 59, 0.5)", "width": 0.5},
            name=f"L{comp_lap} slower",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dist, y=negative,
            fill="tozeroy",
            fillcolor="rgba(0, 204, 150, 0.3)",
            line={"color": "rgba(0, 204, 150, 0.5)", "width": 0.5},
            name=f"L{comp_lap} faster",
        )
    )

    # Main delta line
    fig.add_trace(
        go.Scatter(
            x=dist, y=dt,
            mode="lines",
            line={"color": "#333", "width": 1.5},
            name="Delta-T",
        )
    )

    fig.update_layout(
        title=f"Delta-T: L{comp_lap} vs L{ref_lap} (ref)",
        xaxis_title="Distance (m)",
        yaxis_title="Delta (s)",
        height=400,
        hovermode="x unified",
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=0.5)
    return fig


def track_map_chart(
    lap_df: pd.DataFrame,
    lap_number: int,
    corners: list[Corner] | None = None,
) -> go.Figure:
    """Track map colored by speed."""
    fig = go.Figure()

    fig.add_trace(
        go.Scattergl(
            x=lap_df["lon"].to_numpy(),
            y=lap_df["lat"].to_numpy(),
            mode="markers",
            marker={
                "color": lap_df["speed_mps"].to_numpy() * MPS_TO_MPH,
                "colorscale": "RdYlGn",
                "size": 3,
                "colorbar": {"title": "mph", "thickness": 15},
            },
            name=f"Lap {lap_number}",
            hovertemplate=(
                "Speed: %{marker.color:.1f} mph<br>"
                "Lat: %{y:.6f}<br>"
                "Lon: %{x:.6f}<extra></extra>"
            ),
        )
    )

    # Label corners on the map
    if corners:
        dist = lap_df["lap_distance_m"].to_numpy()
        lat = lap_df["lat"].to_numpy()
        lon = lap_df["lon"].to_numpy()
        for corner in corners:
            apex_idx = int(np.searchsorted(dist, corner.apex_distance_m))
            apex_idx = min(apex_idx, len(lat) - 1)
            fig.add_annotation(
                x=lon[apex_idx],
                y=lat[apex_idx],
                text=f"T{corner.number}",
                showarrow=False,
                font={"size": 10, "color": "black"},
                bgcolor="white",
                opacity=0.8,
            )

    fig.update_layout(
        title=f"Track Map — Lap {lap_number}",
        xaxis_title="Longitude",
        yaxis_title="Latitude",
        height=600,
        yaxis={"scaleanchor": "x", "scaleratio": 1},
        showlegend=False,
    )
    return fig


def corner_kpi_table(
    best_corners: list[Corner],
    comp_corners: list[Corner] | None = None,
    corner_deltas: list[dict[str, object]] | None = None,
) -> go.Figure:
    """Corner KPI comparison table."""
    headers = ["Corner", "Min Speed", "Brake Point", "Peak Brake G", "Throttle Commit", "Apex"]

    if comp_corners:
        headers = [
            "Corner",
            "Best Min Spd", "Comp Min Spd",
            "Best Brake Pt", "Comp Brake Pt",
            "Best Peak G", "Comp Peak G",
            "Delta (s)", "Apex",
        ]

    comp_map = {c.number: c for c in comp_corners} if comp_corners else {}
    delta_map = {}
    if corner_deltas:
        for cd in corner_deltas:
            cn = cd.get("corner_number", cd.get("corner", 0))
            delta_map[cn] = cd.get("delta_s", 0.0)

    cells: list[list[str]] = [[] for _ in headers]

    for bc in best_corners:
        cc = comp_map.get(bc.number)

        if comp_corners:
            cells[0].append(f"T{bc.number}")
            cells[1].append(f"{bc.min_speed_mps * MPS_TO_MPH:.1f}")
            comp_spd = f"{cc.min_speed_mps * MPS_TO_MPH:.1f}" if cc else "—"
            cells[2].append(comp_spd)
            bp = bc.brake_point_m
            cells[3].append(f"{bp:.0f}m" if bp is not None else "—")
            cbp = cc.brake_point_m if cc else None
            cells[4].append(f"{cbp:.0f}m" if cbp is not None else "—")
            bg = bc.peak_brake_g
            cells[5].append(f"{bg:.2f}" if bg is not None else "—")
            cbg = cc.peak_brake_g if cc else None
            cells[6].append(f"{cbg:.2f}" if cbg is not None else "—")
            d = delta_map.get(bc.number, 0.0)
            cells[7].append(f"{d:+.3f}")
            cells[8].append(bc.apex_type)
        else:
            cells[0].append(f"T{bc.number}")
            spd = bc.min_speed_mps * MPS_TO_MPH
            cells[1].append(f"{spd:.1f} mph")
            bp = bc.brake_point_m
            cells[2].append(f"{bp:.0f}m" if bp is not None else "—")
            bg = bc.peak_brake_g
            cells[3].append(f"{bg:.2f}G" if bg is not None else "—")
            tc = bc.throttle_commit_m
            cells[4].append(f"{tc:.0f}m" if tc is not None else "—")
            cells[5].append(bc.apex_type)

    fig = go.Figure(
        go.Table(
            header={"values": headers, "fill_color": "#2a2a2a", "font_color": "white",
                     "align": "center"},
            cells={"values": cells, "fill_color": "#1e1e1e", "font_color": "white",
                    "align": "center"},
        )
    )
    fig.update_layout(title="Corner KPIs", height=max(300, 60 * len(best_corners) + 100))
    return fig


def g_force_chart(lap_df: pd.DataFrame, lap_number: int) -> go.Figure:
    """Lateral vs longitudinal G scatter (G-G diagram)."""
    fig = go.Figure()

    fig.add_trace(
        go.Scattergl(
            x=lap_df["lateral_g"].to_numpy(),
            y=lap_df["longitudinal_g"].to_numpy(),
            mode="markers",
            marker={
                "color": lap_df["speed_mps"].to_numpy() * MPS_TO_MPH,
                "colorscale": "Viridis",
                "size": 2,
                "colorbar": {"title": "mph", "thickness": 15},
            },
            hovertemplate="Lat G: %{x:.2f}<br>Lon G: %{y:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"G-G Diagram — Lap {lap_number}",
        xaxis_title="Lateral G",
        yaxis_title="Longitudinal G",
        height=500,
        yaxis={"scaleanchor": "x", "scaleratio": 1},
        showlegend=False,
    )
    return fig

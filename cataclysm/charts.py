"""Plotly chart builders for telemetry visualization."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from cataclysm.consistency import (
    CornerConsistencyEntry,
    LapConsistency,
    TrackPositionConsistency,
)
from cataclysm.corners import Corner
from cataclysm.delta import DeltaResult
from cataclysm.engine import LapSummary
from cataclysm.gains import (
    CompositeGainResult,
    ConsistencyGainResult,
)

MPS_TO_MPH = 2.23694
M_TO_FT = 3.28084


def _lap_color(idx: int) -> str:
    """Return a color from a fixed palette for lap overlay."""
    palette = [
        "#636EFA",
        "#EF553B",
        "#00CC96",
        "#AB63FA",
        "#FFA15A",
        "#19D3F3",
        "#FF6692",
        "#B6E880",
        "#FF97FF",
        "#FECB52",
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
            x=dist,
            y=positive,
            fill="tozeroy",
            fillcolor="rgba(239, 85, 59, 0.3)",
            line={"color": "rgba(239, 85, 59, 0.5)", "width": 0.5},
            name=f"L{comp_lap} slower",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dist,
            y=negative,
            fill="tozeroy",
            fillcolor="rgba(0, 204, 150, 0.3)",
            line={"color": "rgba(0, 204, 150, 0.5)", "width": 0.5},
            name=f"L{comp_lap} faster",
        )
    )

    # Main delta line
    fig.add_trace(
        go.Scatter(
            x=dist,
            y=dt,
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
                "Speed: %{marker.color:.1f} mph<br>Lat: %{y:.6f}<br>Lon: %{x:.6f}<extra></extra>"
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
            "Best Min Spd",
            "Comp Min Spd",
            "Best Brake Pt",
            "Comp Brake Pt",
            "Best Peak G",
            "Comp Peak G",
            "Delta (s)",
            "Apex",
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
            header={
                "values": headers,
                "fill_color": "#2a2a2a",
                "font_color": "white",
                "align": "center",
            },
            cells={
                "values": cells,
                "fill_color": "#1e1e1e",
                "font_color": "white",
                "align": "center",
            },
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


def linked_speed_map_html(
    laps: dict[int, pd.DataFrame],
    selected_laps: list[int],
    corners: list[Corner] | None = None,
    map_lap: int | None = None,
    delta_distance: list[float] | None = None,
    delta_time: list[float] | None = None,
    ref_lap: int | None = None,
    comp_lap: int | None = None,
) -> str:
    """Return HTML with linked speed trace, optional delta-T, and track map.

    Single-column 3-row layout. Hover on speed or delta chart moves a
    directional cursor on the track map. All client-side JS.
    """
    if not selected_laps:
        return "<p style='color:#ccc'>No laps selected.</p>"

    has_delta = delta_distance is not None and delta_time is not None

    map_lap_num = map_lap if map_lap is not None else selected_laps[0]
    if map_lap_num not in laps:
        map_lap_num = selected_laps[0]

    map_df = laps[map_lap_num]

    # --- Serialize data for JS ---------------------------------------------------
    lap_data_js: dict[str, dict[str, list[float]]] = {}
    for lap_num in selected_laps:
        if lap_num not in laps:
            continue
        df = laps[lap_num]
        lap_data_js[str(lap_num)] = {
            "distance": df["lap_distance_m"].tolist(),
            "speed": (df["speed_mps"] * MPS_TO_MPH).tolist(),
        }

    map_data = {
        "lat": map_df["lat"].tolist(),
        "lon": map_df["lon"].tolist(),
        "heading": map_df["heading_deg"].tolist(),
        "speed": (map_df["speed_mps"] * MPS_TO_MPH).tolist(),
        "distance": map_df["lap_distance_m"].tolist(),
    }

    delta_data: dict[str, list[float]] = {}
    map_delta: list[float] = []
    if has_delta:
        delta_data = {
            "distance": delta_distance,  # type: ignore[dict-item]
            "delta": delta_time,  # type: ignore[dict-item]
        }
        # Interpolate delta onto map lap's distance grid for track coloring
        map_delta = np.interp(
            map_df["lap_distance_m"].to_numpy(),
            np.asarray(delta_distance),
            np.asarray(delta_time),
        ).tolist()

    corner_data: list[dict[str, object]] = []
    if corners:
        dist = map_df["lap_distance_m"].to_numpy()
        lat = map_df["lat"].to_numpy()
        lon = map_df["lon"].to_numpy()
        for c in corners:
            apex_idx = int(np.searchsorted(dist, c.apex_distance_m))
            apex_idx = min(apex_idx, len(lat) - 1)
            corner_data.append(
                {
                    "number": c.number,
                    "entry": c.entry_distance_m,
                    "exit": c.exit_distance_m,
                    "apex_lat": float(lat[apex_idx]),
                    "apex_lon": float(lon[apex_idx]),
                }
            )

    lap_colors: dict[str, str] = {}
    for i, lap_num in enumerate(selected_laps):
        lap_colors[str(lap_num)] = _lap_color(i)

    # Height allocation
    speed_h = 350
    delta_h = 250 if has_delta else 0
    map_h = 400
    total_h = speed_h + delta_h + map_h + 16  # 16 for gaps

    delta_title = ""
    if has_delta and ref_lap is not None and comp_lap is not None:
        delta_title = f"Delta-T: L{comp_lap} vs L{ref_lap} (ref)"

    # --- Build HTML ---------------------------------------------------------------
    delta_div = ""
    if has_delta:
        delta_div = f'<div id="deltaDiv" style="width:100%;height:{delta_h}px;"></div>'

    return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0e1117; font-family: sans-serif; }}
  .container {{
    display: flex; flex-direction: column;
    gap: 4px; width: 100%; height: {total_h}px;
  }}
</style>
</head>
<body>
<div class="container">
  <div id="speedDiv" style="width:100%;height:{speed_h}px;"></div>
  {delta_div}
  <div id="mapDiv" style="width:100%;height:{map_h}px;"></div>
</div>
<script>
(function() {{
  var lapData = {json.dumps(lap_data_js)};
  var mapData = {json.dumps(map_data)};
  var corners = {json.dumps(corner_data)};
  var lapColors = {json.dumps(lap_colors)};
  var hasDelta = {"true" if has_delta else "false"};
  var deltaData = {json.dumps(delta_data) if has_delta else "{}"};
  var mapDelta = {json.dumps(map_delta) if map_delta else "[]"};

  // ---- Speed trace ----
  var speedTraces = [];
  var lapNums = {json.dumps([str(n) for n in selected_laps])};
  for (var i = 0; i < lapNums.length; i++) {{
    var ln = lapNums[i];
    if (!lapData[ln]) continue;
    speedTraces.push({{
      x: lapData[ln].distance,
      y: lapData[ln].speed,
      type: 'scattergl',
      mode: 'lines',
      name: 'Lap ' + ln,
      line: {{ color: lapColors[ln], width: 1.5 }},
    }});
  }}

  var speedShapes = [];
  var speedAnnotations = [];
  for (var ci = 0; ci < corners.length; ci++) {{
    var c = corners[ci];
    speedShapes.push({{
      type: 'rect', xref: 'x', yref: 'paper',
      x0: c.entry, x1: c.exit, y0: 0, y1: 1,
      fillcolor: 'rgba(128,128,128,0.1)',
      line: {{ width: 0 }}, layer: 'below',
    }});
    speedAnnotations.push({{
      x: c.entry, y: 1, xref: 'x', yref: 'paper',
      text: 'T' + c.number, showarrow: false,
      font: {{ size: 10, color: '#888' }},
      xanchor: 'left', yanchor: 'bottom',
    }});
  }}

  var speedLayout = {{
    title: {{ text: 'Speed vs Distance',
             font: {{ color: '#ddd', size: 14 }} }},
    xaxis: {{ title: hasDelta ? '' : 'Distance (m)',
              color: '#aaa', gridcolor: '#333' }},
    yaxis: {{ title: 'Speed (mph)',
              color: '#aaa', gridcolor: '#333' }},
    plot_bgcolor: '#0e1117',
    paper_bgcolor: '#0e1117',
    font: {{ color: '#ddd' }},
    hovermode: 'x unified',
    legend: {{ orientation: 'h', y: 1.15,
               font: {{ color: '#ccc' }} }},
    shapes: speedShapes,
    annotations: speedAnnotations,
    margin: {{ l: 55, r: 15, t: 45, b: hasDelta ? 10 : 40 }},
  }};

  Plotly.newPlot('speedDiv', speedTraces, speedLayout,
                 {{ responsive: true }});

  // ---- Delta-T (optional) ----
  if (hasDelta) {{
    var dd = deltaData.distance;
    var dt = deltaData.delta;

    // Positive fill (comp slower — red)
    var posY = dt.map(function(v) {{ return v >= 0 ? v : 0; }});
    // Negative fill (comp faster — green)
    var negY = dt.map(function(v) {{ return v < 0 ? v : 0; }});

    var deltaTraces = [
      {{
        x: dd, y: posY, type: 'scatter', fill: 'tozeroy',
        fillcolor: 'rgba(239,85,59,0.3)',
        line: {{ color: 'rgba(239,85,59,0.5)', width: 0.5 }},
        name: 'L{comp_lap or ""} slower',
        hoverinfo: 'skip',
      }},
      {{
        x: dd, y: negY, type: 'scatter', fill: 'tozeroy',
        fillcolor: 'rgba(0,204,150,0.3)',
        line: {{ color: 'rgba(0,204,150,0.5)', width: 0.5 }},
        name: 'L{comp_lap or ""} faster',
        hoverinfo: 'skip',
      }},
      {{
        x: dd, y: dt, type: 'scatter', mode: 'lines',
        line: {{ color: '#999', width: 1.5 }},
        name: 'Delta-T',
      }},
    ];

    var deltaShapes = corners.map(function(c) {{
      return {{
        type: 'rect', xref: 'x', yref: 'paper',
        x0: c.entry, x1: c.exit, y0: 0, y1: 1,
        fillcolor: 'rgba(128,128,128,0.1)',
        line: {{ width: 0 }}, layer: 'below',
      }};
    }});

    var deltaLayout = {{
      title: {{ text: '{delta_title}',
               font: {{ color: '#ddd', size: 14 }} }},
      xaxis: {{ title: '', color: '#aaa', gridcolor: '#333' }},
      yaxis: {{ title: 'Delta (s)',
                color: '#aaa', gridcolor: '#333' }},
      plot_bgcolor: '#0e1117',
      paper_bgcolor: '#0e1117',
      font: {{ color: '#ddd' }},
      hovermode: 'x unified',
      legend: {{ orientation: 'h', y: 1.18,
                 font: {{ color: '#ccc', size: 10 }} }},
      shapes: deltaShapes.concat([{{
        type: 'line', xref: 'paper', yref: 'y',
        x0: 0, x1: 1, y0: 0, y1: 0,
        line: {{ color: '#666', width: 0.5, dash: 'dash' }},
      }}]),
      margin: {{ l: 55, r: 15, t: 40, b: 10 }},
    }};

    Plotly.newPlot('deltaDiv', deltaTraces, deltaLayout,
                   {{ responsive: true }});
  }}

  // ---- Track map ----
  var mapTraces = [];

  // Color by delta-T when available, otherwise by speed
  var mapMarker;
  if (hasDelta && mapDelta.length > 0) {{
    var absMax = Math.max.apply(null, mapDelta.map(Math.abs)) || 0.5;
    mapMarker = {{
      color: mapDelta, colorscale: [
        [0, '#00CC96'], [0.5, '#eeeeee'], [1, '#EF553B']
      ],
      cmin: -absMax, cmax: absMax,
      size: 3,
      colorbar: {{ title: 'delta (s)', thickness: 12,
        tickfont: {{ color: '#aaa' }},
        titlefont: {{ color: '#aaa' }} }},
    }};
  }} else {{
    mapMarker = {{
      color: mapData.speed, colorscale: 'RdYlGn', size: 3,
      colorbar: {{ title: 'mph', thickness: 12,
        tickfont: {{ color: '#aaa' }},
        titlefont: {{ color: '#aaa' }} }},
    }};
  }}

  mapTraces.push({{
    x: mapData.lon, y: mapData.lat,
    type: 'scattergl', mode: 'markers',
    marker: mapMarker,
    hoverinfo: 'skip', showlegend: false,
  }});

  // Cursor arrow (initially hidden)
  mapTraces.push({{
    x: [mapData.lon[0]], y: [mapData.lat[0]],
    type: 'scatter', mode: 'markers',
    marker: {{
      symbol: 'triangle-up',
      angle: [mapData.heading[0]], angleref: 'up',
      size: 16, color: '#ffffff',
      line: {{ color: '#000', width: 2 }},
      opacity: 0,
    }},
    hoverinfo: 'skip', showlegend: false,
  }});

  var mapAnnotations = corners.map(function(c) {{
    return {{
      x: c.apex_lon, y: c.apex_lat,
      text: '<b>T' + c.number + '</b>', showarrow: false,
      font: {{ size: 13, color: '#fff' }},
      bgcolor: 'rgba(50,50,50,0.85)',
      bordercolor: '#888',
      borderwidth: 1,
      borderpad: 3,
    }};
  }});

  var mapTitle = hasDelta && mapDelta.length > 0
    ? 'Track Map — Delta-T (Lap {map_lap_num})'
    : 'Track Map — Speed (Lap {map_lap_num})';
  var mapLayout = {{
    title: {{ text: mapTitle,
             font: {{ color: '#ddd', size: 14 }} }},
    xaxis: {{ title: 'Longitude', color: '#aaa',
              gridcolor: '#333', showgrid: false }},
    yaxis: {{ title: 'Latitude', color: '#aaa',
              gridcolor: '#333', showgrid: false,
              scaleanchor: 'x', scaleratio: 1 }},
    plot_bgcolor: '#0e1117',
    paper_bgcolor: '#0e1117',
    font: {{ color: '#ddd' }},
    showlegend: false,
    annotations: mapAnnotations,
    margin: {{ l: 55, r: 15, t: 45, b: 40 }},
  }};

  Plotly.newPlot('mapDiv', mapTraces, mapLayout,
                 {{ responsive: true }});

  // ---- Hover linking ----
  var distArr = mapData.distance;

  function bisect(arr, val) {{
    var lo = 0, hi = arr.length - 1;
    while (lo < hi) {{
      var mid = (lo + hi) >> 1;
      if (arr[mid] < val) lo = mid + 1;
      else hi = mid;
    }}
    return lo;
  }}

  function moveCursor(xVal) {{
    var idx = bisect(distArr, xVal);
    if (idx >= distArr.length) idx = distArr.length - 1;
    Plotly.restyle('mapDiv', {{
      'x': [[mapData.lon[idx]]],
      'y': [[mapData.lat[idx]]],
      'marker.angle': [[mapData.heading[idx]]],
      'marker.opacity': [1],
    }}, [1]);
  }}

  function hideCursor() {{
    Plotly.restyle('mapDiv', {{ 'marker.opacity': [0] }}, [1]);
  }}

  var speedDiv = document.getElementById('speedDiv');
  speedDiv.on('plotly_hover', function(evt) {{
    if (evt.points && evt.points.length)
      moveCursor(evt.points[0].x);
  }});
  speedDiv.on('plotly_unhover', hideCursor);

  if (hasDelta) {{
    var deltaDiv = document.getElementById('deltaDiv');
    deltaDiv.on('plotly_hover', function(evt) {{
      if (evt.points && evt.points.length)
        moveCursor(evt.points[0].x);
    }});
    deltaDiv.on('plotly_unhover', hideCursor);

    // Sync x-axis zoom/pan between speed and delta charts
    var syncing = false;
    function syncXRange(source, target, evtData) {{
      if (syncing) return;
      syncing = true;
      var update = {{}};
      if (evtData['xaxis.range[0]'] !== undefined) {{
        update['xaxis.range[0]'] = evtData['xaxis.range[0]'];
        update['xaxis.range[1]'] = evtData['xaxis.range[1]'];
      }} else if (evtData['xaxis.autorange']) {{
        update['xaxis.autorange'] = true;
      }}
      if (Object.keys(update).length > 0)
        Plotly.relayout(target, update);
      syncing = false;
    }}

    speedDiv.on('plotly_relayout', function(evtData) {{
      syncXRange('speedDiv', 'deltaDiv', evtData);
    }});
    deltaDiv.on('plotly_relayout', function(evtData) {{
      syncXRange('deltaDiv', 'speedDiv', evtData);
    }});
  }}
}})();
</script>
</body>
</html>"""


def lap_consistency_chart(lap: LapConsistency) -> go.Figure:
    """Two-subplot chart: lap times with mean/std band, and consecutive delta bars."""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.6, 0.4],
        vertical_spacing=0.08,
    )

    lap_labels = [f"L{n}" for n in lap.lap_numbers]
    times = lap.lap_times_s
    mean_time = np.mean(times)
    std_time = np.std(times)

    # Top subplot: lap times as connected scatter
    fig.add_trace(
        go.Scatter(
            x=lap_labels,
            y=times,
            mode="lines+markers",
            name="Lap Time",
            line={"color": "#636EFA", "width": 2},
            marker={"size": 8, "color": "#636EFA"},
        ),
        row=1,
        col=1,
    )

    # Horizontal mean line
    fig.add_trace(
        go.Scatter(
            x=lap_labels,
            y=[mean_time] * len(lap_labels),
            mode="lines",
            name=f"Mean ({mean_time:.2f}s)",
            line={"color": "gray", "width": 1, "dash": "dash"},
        ),
        row=1,
        col=1,
    )

    # +/- 1 std dev band
    upper = [mean_time + std_time] * len(lap_labels)
    lower = [mean_time - std_time] * len(lap_labels)
    fig.add_trace(
        go.Scatter(
            x=lap_labels,
            y=upper,
            mode="lines",
            line={"width": 0},
            showlegend=False,
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=lap_labels,
            y=lower,
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(99, 110, 250, 0.15)",
            name="\u00b11 Std Dev",
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )

    # Bottom subplot: consecutive delta bars
    delta_labels = [
        f"L{lap.lap_numbers[i]}\u2192L{lap.lap_numbers[i + 1]}"
        for i in range(len(lap.consecutive_deltas_s))
    ]
    deltas = lap.consecutive_deltas_s
    mean_delta = float(np.mean(np.abs(deltas))) if deltas else 0.0
    bar_colors = ["#00CC96" if abs(d) < mean_delta else "#EF553B" for d in deltas]

    fig.add_trace(
        go.Bar(
            x=delta_labels,
            y=deltas,
            marker_color=bar_colors,
            name="Delta",
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title="Lap Consistency",
        height=500,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font={"color": "#ddd"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    fig.update_xaxes(color="#aaa", gridcolor="#333")
    fig.update_yaxes(color="#aaa", gridcolor="#333")
    fig.update_yaxes(title_text="Time (s)", row=1, col=1)
    fig.update_yaxes(title_text="Delta (s)", row=2, col=1)

    return fig


def corner_consistency_chart(
    entries: list[CornerConsistencyEntry],
) -> go.Figure:
    """Horizontal bar chart ranking corners by consistency score."""
    sorted_entries = sorted(entries, key=lambda e: e.consistency_score)

    labels = [f"T{e.corner_number}" for e in sorted_entries]
    scores = [e.consistency_score for e in sorted_entries]
    bar_colors = [
        f"rgb("
        f"{int(239 - (239 - 0) * s / 100)}, "
        f"{int(85 + (204 - 85) * s / 100)}, "
        f"{int(59 + (150 - 59) * s / 100)})"
        for s in scores
    ]

    fig = go.Figure(
        go.Bar(
            y=labels,
            x=scores,
            orientation="h",
            marker_color=bar_colors,
            text=[f"{s:.0f}" for s in scores],
            textposition="inside",
            textfont={"color": "white"},
        )
    )

    fig.update_layout(
        title="Corner Consistency Ranking",
        xaxis_title="Consistency Score",
        xaxis={"range": [0, 100], "color": "#aaa", "gridcolor": "#333"},
        yaxis={"color": "#aaa", "gridcolor": "#333"},
        height=max(300, 50 * len(entries) + 100),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font={"color": "#ddd"},
        showlegend=False,
    )

    return fig


def _score_to_rgb(score: float) -> str:
    """Map a 0-100 consistency score to an RGB color (red→green)."""
    t = max(0.0, min(score, 100.0)) / 100.0
    r = int(239 - (239 - 0) * t)
    g = int(85 + (204 - 85) * t)
    b = int(59 + (150 - 59) * t)
    return f"rgb({r},{g},{b})"


def track_consistency_map(
    track: TrackPositionConsistency,
    corners: list[Corner] | None = None,
    corner_consistency: list[CornerConsistencyEntry] | None = None,
) -> go.Figure:
    """Track map colored by speed std dev with corner consistency labels.

    Corner labels show "T<n> <score>" and are colored from red (low score)
    to green (high score) when ``corner_consistency`` is provided.
    """
    fig = go.Figure()

    fig.add_trace(
        go.Scattergl(
            x=track.lon,
            y=track.lat,
            mode="markers",
            marker={
                "color": track.speed_std_mph,
                "colorscale": [
                    [0, "#00CC96"],
                    [0.5, "#FFA15A"],
                    [1, "#EF553B"],
                ],
                "size": 3,
                "colorbar": {"title": "Speed Std (mph)", "thickness": 15},
            },
            hovertemplate=(
                "Speed Std: %{marker.color:.2f} mph<br>"
                "Mean Speed: %{customdata:.1f} mph<br>"
                "Lat: %{y:.6f}<br>"
                "Lon: %{x:.6f}<extra></extra>"
            ),
            customdata=track.speed_mean_mph,
        )
    )

    # Label corners on the map, colored by consistency score when available
    if corners:
        cc_map = {e.corner_number: e for e in (corner_consistency or [])}
        dist = track.distance_m
        lat = track.lat
        lon = track.lon
        for corner in corners:
            apex_idx = int(np.searchsorted(dist, corner.apex_distance_m))
            apex_idx = min(apex_idx, len(lat) - 1)
            entry = cc_map.get(corner.number)
            if entry is not None:
                label = f"T{corner.number} {entry.consistency_score:.0f}"
                bg = _score_to_rgb(entry.consistency_score)
                font_color = "white"
            else:
                label = f"T{corner.number}"
                bg = "white"
                font_color = "black"
            fig.add_annotation(
                x=lon[apex_idx],
                y=lat[apex_idx],
                text=label,
                showarrow=False,
                font={"size": 10, "color": font_color},
                bgcolor=bg,
                opacity=0.9,
            )

    fig.update_layout(
        title=f"Track Consistency Map ({track.n_laps} laps)",
        xaxis_title="Longitude",
        yaxis_title="Latitude",
        height=600,
        yaxis={"scaleanchor": "x", "scaleratio": 1},
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font={"color": "#ddd"},
        showlegend=False,
    )

    return fig


def track_median_speed_map(
    track: TrackPositionConsistency,
    corners: list[Corner] | None = None,
    corner_consistency: list[CornerConsistencyEntry] | None = None,
) -> go.Figure:
    """Track map colored by median speed across all clean laps.

    Corner labels show "T<n> <score>" colored by consistency score
    when ``corner_consistency`` is provided.
    """
    fig = go.Figure()

    fig.add_trace(
        go.Scattergl(
            x=track.lon,
            y=track.lat,
            mode="markers",
            marker={
                "color": track.speed_median_mph,
                "colorscale": "RdYlGn",
                "size": 3,
                "colorbar": {"title": "Median mph", "thickness": 15},
            },
            hovertemplate=(
                "Median Speed: %{marker.color:.1f} mph<br>"
                "Lat: %{y:.6f}<br>"
                "Lon: %{x:.6f}<extra></extra>"
            ),
        )
    )

    if corners:
        cc_map = {e.corner_number: e for e in (corner_consistency or [])}
        dist = track.distance_m
        lat = track.lat
        lon = track.lon
        for corner in corners:
            apex_idx = int(np.searchsorted(dist, corner.apex_distance_m))
            apex_idx = min(apex_idx, len(lat) - 1)
            entry = cc_map.get(corner.number)
            if entry is not None:
                label = f"T{corner.number} {entry.consistency_score:.0f}"
                bg = _score_to_rgb(entry.consistency_score)
                font_color = "white"
            else:
                label = f"T{corner.number}"
                bg = "rgba(50,50,50,0.85)"
                font_color = "white"
            fig.add_annotation(
                x=lon[apex_idx],
                y=lat[apex_idx],
                text=label,
                showarrow=False,
                font={"size": 12, "color": font_color},
                bgcolor=bg,
                borderpad=2,
                opacity=0.9,
            )

    fig.update_layout(
        title=f"Track Map — Median Speed ({track.n_laps} laps)",
        xaxis_title="Longitude",
        yaxis_title="Latitude",
        height=600,
        yaxis={"scaleanchor": "x", "scaleratio": 1},
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font={"color": "#ddd"},
        showlegend=False,
    )

    return fig


def gain_per_corner_chart(
    consistency: ConsistencyGainResult,
    composite: CompositeGainResult,
) -> go.Figure:
    """Grouped horizontal bar chart showing per-corner gains."""
    # Build lookup from composite segment gains keyed by segment name
    comp_map: dict[str, float] = {}
    for sg in composite.segment_gains:
        if sg.segment.is_corner:
            comp_map[sg.segment.name] = sg.gain_s

    # Collect corner segments from consistency, filter straights and tiny gains
    rows: list[tuple[str, float, float]] = []
    for sg in consistency.segment_gains:
        if not sg.segment.is_corner:
            continue
        cons_gain = sg.gain_s
        comp_gain = comp_map.get(sg.segment.name, 0.0)
        if cons_gain < 0.01 and comp_gain < 0.01:
            continue
        rows.append((sg.segment.name, cons_gain, comp_gain))

    # Sort by consistency gain descending (biggest opportunity at top)
    rows.sort(key=lambda r: r[1], reverse=True)

    names = [r[0] for r in rows]
    cons_vals = [r[1] for r in rows]
    comp_vals = [r[2] for r in rows]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            y=names,
            x=cons_vals,
            orientation="h",
            name="Consistency (avg \u2192 best)",
            marker_color="#636EFA",
            text=[f"{v:.2f}s" for v in cons_vals],
            textposition="auto",
        )
    )

    fig.add_trace(
        go.Bar(
            y=names,
            x=comp_vals,
            orientation="h",
            name="Composite (best lap \u2192 best sector)",
            marker_color="#FFA15A",
            text=[f"{v:.2f}s" for v in comp_vals],
            textposition="auto",
        )
    )

    fig.update_layout(
        title="Per-Corner Gain Breakdown",
        xaxis_title="Time Gain (s)",
        barmode="group",
        height=max(350, 50 * len(names) + 150),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font={"color": "#ddd"},
        xaxis={"color": "#aaa", "gridcolor": "#333"},
        yaxis={"color": "#aaa", "autorange": "reversed"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )

    return fig

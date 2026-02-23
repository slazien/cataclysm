"""Cataclysm — Post-session telemetry analysis and AI coaching."""

from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd
import streamlit as st

from cataclysm.charts import (
    corner_kpi_table,
    g_force_chart,
    gain_per_corner_chart,
    lap_consistency_chart,
    lap_times_chart,
    linked_speed_map_html,
    track_consistency_map,
    track_median_speed_map,
)
from cataclysm.coaching import CoachingContext, ask_followup, generate_coaching_report
from cataclysm.consistency import compute_session_consistency
from cataclysm.corners import Corner, detect_corners, extract_corner_kpis_for_lap
from cataclysm.delta import compute_delta
from cataclysm.engine import ProcessedSession, find_anomalous_laps, process_session
from cataclysm.gains import GainEstimate, estimate_gains
from cataclysm.parser import ParsedSession, parse_racechrono_csv
from cataclysm.track_db import locate_official_corners, lookup_track

# Type alias for readability
AllLapCorners = dict[int, list[Corner]]

MPS_TO_MPH = 2.23694

st.set_page_config(page_title="Cataclysm", page_icon="🏎️", layout="wide")

st.title("Cataclysm")
st.caption("Post-session telemetry analysis & AI coaching")


# ---------------------------------------------------------------------------
# Session loading
# ---------------------------------------------------------------------------
def _find_existing_sessions() -> list[str]:
    """Find session CSVs in the repo."""
    patterns = ["session_*.csv", "sample_data/*.csv"]
    files: list[str] = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    return sorted(files)


def _load_session(
    source: str | object,
) -> tuple[ParsedSession, ProcessedSession]:
    """Parse and process a session from file path or uploaded file."""
    parsed = parse_racechrono_csv(source)  # type: ignore[arg-type]
    processed = process_session(parsed.data)
    return parsed, processed


# Sidebar: session picker
st.sidebar.header("Session")

existing = _find_existing_sessions()
upload_option = "Upload new CSV..."

source_options = existing + [upload_option]
chosen = st.sidebar.selectbox("Select session", source_options)

uploaded_file = None
if chosen == upload_option:
    uploaded_file = st.sidebar.file_uploader("Upload RaceChrono CSV v3", type=["csv"])

session_source = uploaded_file if uploaded_file else chosen
if session_source is None or session_source == upload_option:
    st.info("Select a session file or upload a RaceChrono CSV v3 export to get started.")
    st.stop()


# Cache processing per file
@st.cache_data(show_spinner="Processing session...")
def cached_process(file_key: str, _source: object) -> tuple[ParsedSession, ProcessedSession]:
    return _load_session(_source)


file_key = uploaded_file.name if uploaded_file else str(session_source)
try:
    parsed, processed = cached_process(file_key, session_source)
except Exception as exc:
    st.error(f"Failed to process session: {exc}")
    st.stop()

# ---------------------------------------------------------------------------
# Session overview
# ---------------------------------------------------------------------------
meta = parsed.metadata
summaries = processed.lap_summaries

best_summary = min(summaries, key=lambda s: s.lap_time_s)
worst_summary = max(summaries, key=lambda s: s.lap_time_s)
avg_time = float(np.mean([s.lap_time_s for s in summaries]))


def fmt_time(t: float) -> str:
    m = int(t // 60)
    s = t % 60
    return f"{m}:{s:05.2f}"


st.sidebar.markdown("---")
st.sidebar.markdown(f"**Track**: {meta.track_name}")
st.sidebar.markdown(f"**Date**: {meta.session_date}")
st.sidebar.markdown(f"**Laps**: {len(summaries)}")
st.sidebar.markdown(f"**Best**: L{best_summary.lap_number} — {fmt_time(best_summary.lap_time_s)}")
st.sidebar.markdown(
    f"**Worst**: L{worst_summary.lap_number} — {fmt_time(worst_summary.lap_time_s)}"
)
st.sidebar.markdown(f"**Average**: {fmt_time(avg_time)}")

# ---------------------------------------------------------------------------
# Detect corners on best lap
# ---------------------------------------------------------------------------
best_lap_df = processed.resampled_laps[processed.best_lap]


@st.cache_data(show_spinner="Detecting corners...")
def cached_corners(_key: str, _lap_df: object, _track_name: str) -> list[Corner]:
    layout = lookup_track(_track_name)  # type: ignore[arg-type]
    if layout is not None:
        skeletons = locate_official_corners(_lap_df, layout)  # type: ignore[arg-type]
        return extract_corner_kpis_for_lap(_lap_df, skeletons)  # type: ignore[arg-type]
    return detect_corners(_lap_df)  # type: ignore[arg-type]


corners = cached_corners(f"{file_key}_L{processed.best_lap}", best_lap_df, meta.track_name)

# ---------------------------------------------------------------------------
# Extract corners for ALL laps (used by Overview consistency + AI Coach)
# ---------------------------------------------------------------------------
anomalous = find_anomalous_laps(summaries)
all_laps = sorted(processed.resampled_laps.keys())
coaching_laps = [n for n in all_laps if n not in anomalous]


@st.cache_data(show_spinner="Extracting corner data...")
def cached_all_lap_corners(
    _key: str,
    _resampled: object,
    _corners: object,
    _best: int,
    _coaching_laps: list[int],
) -> AllLapCorners:
    result: AllLapCorners = {}
    for lap_num in _coaching_laps:
        lap_df = processed.resampled_laps[lap_num]
        if lap_num == _best:
            result[lap_num] = corners  # type: ignore[assignment]
        else:
            result[lap_num] = extract_corner_kpis_for_lap(
                lap_df,
                corners,  # type: ignore[arg-type]
            )
    return result


all_lap_corners = cached_all_lap_corners(
    f"{file_key}_corners_all",
    processed.resampled_laps,
    corners,
    processed.best_lap,
    coaching_laps,
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_overview, tab_speed, tab_corners, tab_coaching = st.tabs(
    ["Overview", "Speed Trace", "Corners", "AI Coach"]
)

# --- Overview Tab ---
with tab_overview:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Best Lap",
        fmt_time(best_summary.lap_time_s),
        f"L{best_summary.lap_number}",
    )
    col2.metric(
        "Worst Lap",
        fmt_time(worst_summary.lap_time_s),
        f"L{worst_summary.lap_number}",
    )
    col3.metric("Average", fmt_time(avg_time))
    col4.metric(
        "Top Speed",
        f"{max(s.max_speed_mps for s in summaries) * MPS_TO_MPH:.1f} mph",
    )

    st.plotly_chart(lap_times_chart(summaries), use_container_width=True)

    # --- Session Consistency ---
    st.markdown("---")
    st.subheader("Session Consistency")

    if len(coaching_laps) >= 2:
        consistency = compute_session_consistency(
            summaries,
            all_lap_corners,
            processed.resampled_laps,
            processed.best_lap,
            anomalous,
        )

        lc = consistency.lap_consistency
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Score", f"{lc.consistency_score:.0f}/100")
        mc2.metric("Avg Delta", f"{lc.mean_abs_consecutive_delta_s:.1f}s")
        mc3.metric("Spread", f"{lc.spread_s:.1f}s")

        st.plotly_chart(lap_consistency_chart(lc), use_container_width=True)

        # Track maps: median speed + consistency side by side
        map_col1, map_col2 = st.columns(2)
        with map_col1:
            st.plotly_chart(
                track_median_speed_map(
                    consistency.track_position,
                    corners,
                    consistency.corner_consistency or None,
                ),
                use_container_width=True,
            )
        with map_col2:
            st.plotly_chart(
                track_consistency_map(
                    consistency.track_position,
                    corners,
                    consistency.corner_consistency or None,
                ),
                use_container_width=True,
            )
    else:
        st.info("Need at least 2 clean laps to compute consistency metrics.")

    st.plotly_chart(
        g_force_chart(best_lap_df, processed.best_lap),
        use_container_width=True,
    )

# --- Speed Trace Tab ---
with tab_speed:
    selected_laps = st.multiselect(
        "Select laps to overlay",
        all_laps,
        default=[all_laps[0], processed.best_lap]
        if len(all_laps) >= 2 and all_laps[0] != processed.best_lap
        else all_laps[:2],
        format_func=lambda n: f"Lap {n}",
    )
    if selected_laps:
        delta_dist: list[float] | None = None
        delta_time: list[float] | None = None
        ref: int | None = None
        comp: int | None = None
        if len(selected_laps) == 2:
            ref, comp = selected_laps
            delta_result = compute_delta(
                processed.resampled_laps[ref],
                processed.resampled_laps[comp],
                corners,
            )
            delta_dist = delta_result.distance_m.tolist()
            delta_time = delta_result.delta_time_s.tolist()
        html = linked_speed_map_html(
            processed.resampled_laps,
            selected_laps,
            corners,
            delta_distance=delta_dist,
            delta_time=delta_time,
            ref_lap=ref,
            comp_lap=comp,
        )
        height = 1020 if len(selected_laps) == 2 else 770
        st.components.v1.html(html, height=height)
    else:
        st.info("Select at least one lap to display.")

# --- Corners Tab ---
with tab_corners:
    if not corners:
        st.info("No corners detected. This may happen with very short laps.")
    else:
        st.markdown(f"**{len(corners)} corners detected** on best lap (L{processed.best_lap})")

        # Compare best vs another lap
        other_laps = [lap_num for lap_num in all_laps if lap_num != processed.best_lap]
        corner_comp_lap = st.selectbox(
            "Compare corners with lap",
            other_laps,
            format_func=lambda n: f"Lap {n}",
            key="corner_comp",
        )

        comp_corners: list[Corner] = []
        delta_dicts: list[dict[str, object]] | None = None

        if corner_comp_lap in processed.resampled_laps:
            comp_corners = extract_corner_kpis_for_lap(
                processed.resampled_laps[corner_comp_lap], corners
            )
            delta = compute_delta(
                processed.resampled_laps[processed.best_lap],
                processed.resampled_laps[corner_comp_lap],
                corners,
            )
            delta_dicts = [
                {
                    "corner_number": cd.corner_number,
                    "delta_s": cd.delta_s,
                }
                for cd in delta.corner_deltas
            ]

        fig = corner_kpi_table(corners, comp_corners or None, delta_dicts)
        st.plotly_chart(fig, use_container_width=True)

# --- AI Coach Tab ---
with tab_coaching:
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

    if not has_key:
        st.warning(
            "Set the `ANTHROPIC_API_KEY` environment variable "
            "to enable AI coaching.\n\n"
            "```bash\nexport ANTHROPIC_API_KEY=sk-ant-...\n```"
        )

    st.caption(f"Analyzes all {len(all_laps)} laps across {len(corners)} detected corners.")

    if anomalous:
        excluded = ", ".join(f"L{n}" for n in sorted(anomalous))
        st.info(f"Excluding anomalous laps from analysis: {excluded}")

    coaching_summaries = [s for s in summaries if s.lap_number not in anomalous]

    # --- Estimated Time Gains (deterministic, no API key needed) ---
    gains: GainEstimate | None = None
    if len(coaching_laps) >= 2:

        @st.cache_data(show_spinner="Computing gain estimates...")
        def cached_gains(
            _key: str,
            _resampled: object,
            _corners: object,
            _summaries: object,
            _coaching_laps: list[int],
            _best_lap: int,
        ) -> GainEstimate:
            return estimate_gains(
                processed.resampled_laps,
                corners,  # type: ignore[arg-type]
                summaries,
                _coaching_laps,
                _best_lap,
            )

        gains = cached_gains(
            f"{file_key}_gains",
            processed.resampled_laps,
            corners,
            summaries,
            coaching_laps,
            processed.best_lap,
        )

        st.subheader("Estimated Time Gains")
        g1, g2, g3 = st.columns(3)
        g1.metric(
            "Consistency",
            f"{gains.consistency.total_gain_s:.2f}s",
            help="Avg lap improvement if you hit your best at every section",
        )
        g2.metric(
            "Composite Best",
            f"{gains.composite.gain_s:.2f}s",
            help="Gap: best lap vs combining best sectors from any lap",
        )
        g3.metric(
            "Theoretical Best",
            f"{gains.theoretical.gain_s:.2f}s",
            help="Gap: best lap vs best 10m micro-sectors from any lap",
        )

        def _fmt_lt(t: float) -> str:
            m = int(t // 60)
            s = t % 60
            return f"{m}:{s:05.2f}"

        avg_t = _fmt_lt(gains.consistency.avg_lap_time_s)
        best_t = _fmt_lt(gains.consistency.best_lap_time_s)
        comp_t = _fmt_lt(gains.composite.composite_time_s)
        theo_t = _fmt_lt(gains.theoretical.theoretical_time_s)
        st.caption(
            f"Avg Lap **{avg_t}** · Best Lap **{best_t}** · "
            f"Composite **{comp_t}** · Theoretical **{theo_t}**"
        )

        st.plotly_chart(
            gain_per_corner_chart(gains.consistency, gains.composite),
            use_container_width=True,
        )
    else:
        st.info("Need at least 2 clean laps to estimate gains.")

    # --- Generate Coaching Report ---
    if st.button("Generate Coaching Report", disabled=not has_key):
        with st.spinner("AI coach is analyzing your session..."):
            report = generate_coaching_report(
                coaching_summaries,
                all_lap_corners,
                meta.track_name,
                gains=gains,
            )
            st.session_state["coaching_report"] = report
            st.session_state["coaching_context"] = CoachingContext()

    if "coaching_report" in st.session_state:
        report = st.session_state["coaching_report"]

        st.subheader("Session Summary")
        st.write(report.summary)

        if report.raw_response and not report.priority_corners:
            with st.expander("Raw AI response (parsing failed)"):
                st.code(report.raw_response)

        if report.priority_corners:
            st.subheader("Priority Corners")
            for pc in report.priority_corners:
                cost = pc.get("time_cost_s", 0)
                st.markdown(
                    f"**T{pc.get('corner', '?')}** "
                    f"— {pc.get('issue', '')} "
                    f"({cost:+.3f}s)\n\n"
                    f"> {pc.get('tip', '')}"
                )

        if report.corner_grades:
            st.subheader("Corner Grades")
            grade_cols = ["Braking", "Trail Brake", "Min Speed", "Throttle"]
            grade_score = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
            grade_color = {
                "A": "#2d6a2e",
                "B": "#1a6b5a",
                "C": "#8a7a00",
                "D": "#a85e00",
                "F": "#a83232",
            }
            df_grades = pd.DataFrame(
                {
                    "Corner": [f"T{g.corner}" for g in report.corner_grades],
                    "Braking": [g.braking for g in report.corner_grades],
                    "Trail Brake": [g.trail_braking for g in report.corner_grades],
                    "Min Speed": [g.min_speed for g in report.corner_grades],
                    "Throttle": [g.throttle for g in report.corner_grades],
                    "Notes": [g.notes for g in report.corner_grades],
                }
            )
            df_grades["_avg"] = (
                df_grades[grade_cols].map(lambda v: grade_score.get(v, 0)).mean(axis=1)
            )
            df_grades = df_grades.sort_values("_avg").drop(columns="_avg").reset_index(drop=True)

            def _color_grade(val: object) -> str:
                bg = grade_color.get(str(val), "")
                if bg:
                    return f"background-color: {bg}; color: white"
                return ""

            styled = df_grades.style.map(
                _color_grade,
                subset=grade_cols,  # type: ignore[arg-type]
            )
            st.dataframe(styled, use_container_width=True)

        if report.patterns:
            st.subheader("Patterns")
            for p in report.patterns:
                st.markdown(f"- {p}")

        # Chat follow-up
        st.markdown("---")
        st.subheader("Ask the Coach")
        question = st.chat_input("Ask about a specific corner, technique, or anything else...")
        if question:
            ctx = st.session_state.get("coaching_context", CoachingContext())
            with st.spinner("Thinking..."):
                answer = ask_followup(ctx, question, report)
            st.session_state["coaching_context"] = ctx

            # Display conversation
            for msg in ctx.messages:
                if msg["role"] == "user":
                    st.chat_message("user").write(msg["content"])
                else:
                    st.chat_message("assistant").write(msg["content"])

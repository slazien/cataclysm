"""Cataclysm — Post-session telemetry analysis and AI coaching."""

from __future__ import annotations

import glob
import os

import numpy as np
import streamlit as st

from cataclysm.charts import (
    corner_kpi_table,
    delta_t_chart,
    g_force_chart,
    lap_times_chart,
    speed_trace_chart,
    track_map_chart,
)
from cataclysm.coaching import CoachingContext, ask_followup, generate_coaching_report
from cataclysm.corners import Corner, detect_corners, extract_corner_kpis_for_lap
from cataclysm.delta import compute_delta
from cataclysm.engine import find_anomalous_laps
from cataclysm.track_db import locate_official_corners, lookup_track

# Type alias for readability
AllLapCorners = dict[int, list[Corner]]
from cataclysm.engine import ProcessedSession, process_session
from cataclysm.parser import ParsedSession, parse_racechrono_csv

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
    uploaded_file = st.sidebar.file_uploader(
        "Upload RaceChrono CSV v3", type=["csv"]
    )

session_source = uploaded_file if uploaded_file else chosen
if session_source is None or session_source == upload_option:
    st.info(
        "Select a session file or upload a RaceChrono CSV v3 export "
        "to get started."
    )
    st.stop()


# Cache processing per file
@st.cache_data(show_spinner="Processing session...")
def cached_process(
    file_key: str, _source: object
) -> tuple[ParsedSession, ProcessedSession]:
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
st.sidebar.markdown(
    f"**Best**: L{best_summary.lap_number} "
    f"— {fmt_time(best_summary.lap_time_s)}"
)
st.sidebar.markdown(
    f"**Worst**: L{worst_summary.lap_number} "
    f"— {fmt_time(worst_summary.lap_time_s)}"
)
st.sidebar.markdown(f"**Average**: {fmt_time(avg_time)}")

# ---------------------------------------------------------------------------
# Detect corners on best lap
# ---------------------------------------------------------------------------
best_lap_df = processed.resampled_laps[processed.best_lap]


@st.cache_data(show_spinner="Detecting corners...")
def cached_corners(
    _key: str, _lap_df: object, _track_name: str
) -> list[Corner]:
    layout = lookup_track(_track_name)  # type: ignore[arg-type]
    if layout is not None:
        skeletons = locate_official_corners(_lap_df, layout)  # type: ignore[arg-type]
        return extract_corner_kpis_for_lap(_lap_df, skeletons)  # type: ignore[arg-type]
    return detect_corners(_lap_df)  # type: ignore[arg-type]


corners = cached_corners(
    f"{file_key}_L{processed.best_lap}", best_lap_df, meta.track_name
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_overview, tab_speed, tab_map, tab_delta, tab_corners, tab_coaching = (
    st.tabs(
        ["Overview", "Speed Trace", "Track Map", "Delta-T", "Corners",
         "AI Coach"]
    )
)

# --- Overview Tab ---
with tab_overview:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Best Lap", fmt_time(best_summary.lap_time_s),
        f"L{best_summary.lap_number}",
    )
    col2.metric(
        "Worst Lap", fmt_time(worst_summary.lap_time_s),
        f"L{worst_summary.lap_number}",
    )
    col3.metric("Average", fmt_time(avg_time))
    col4.metric(
        "Top Speed",
        f"{max(s.max_speed_mps for s in summaries) * MPS_TO_MPH:.1f} mph",
    )

    st.plotly_chart(
        lap_times_chart(summaries), use_container_width=True
    )
    st.plotly_chart(
        g_force_chart(best_lap_df, processed.best_lap),
        use_container_width=True,
    )

# --- Speed Trace Tab ---
with tab_speed:
    all_laps = sorted(processed.resampled_laps.keys())
    selected_laps = st.multiselect(
        "Select laps to overlay",
        all_laps,
        default=all_laps[:3],
        format_func=lambda n: f"Lap {n}",
    )
    if selected_laps:
        fig = speed_trace_chart(
            processed.resampled_laps, selected_laps, corners
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Select at least one lap to display.")

# --- Track Map Tab ---
with tab_map:
    map_lap = st.selectbox(
        "Show map for lap",
        all_laps,
        index=(
            all_laps.index(processed.best_lap)
            if processed.best_lap in all_laps else 0
        ),
        format_func=lambda n: f"Lap {n}",
        key="map_lap",
    )
    if map_lap in processed.resampled_laps:
        fig = track_map_chart(
            processed.resampled_laps[map_lap], map_lap, corners
        )
        st.plotly_chart(fig, use_container_width=True)

# --- Delta-T Tab ---
with tab_delta:
    col_ref, col_comp = st.columns(2)
    with col_ref:
        ref_lap = st.selectbox(
            "Reference lap",
            all_laps,
            index=(
                all_laps.index(processed.best_lap)
                if processed.best_lap in all_laps else 0
            ),
            format_func=lambda n: f"Lap {n}",
            key="delta_ref",
        )
    with col_comp:
        comp_default = [
            lap_num for lap_num in all_laps if lap_num != ref_lap
        ]
        comp_lap = st.selectbox(
            "Comparison lap",
            comp_default,
            format_func=lambda n: f"Lap {n}",
            key="delta_comp",
        )

    if (
        ref_lap in processed.resampled_laps
        and comp_lap in processed.resampled_laps
        and ref_lap != comp_lap
    ):
        delta = compute_delta(
            processed.resampled_laps[ref_lap],
            processed.resampled_laps[comp_lap],
            corners,
        )
        st.plotly_chart(
            delta_t_chart(delta, ref_lap, comp_lap),
            use_container_width=True,
        )

        st.metric(
            "Total Delta",
            f"{delta.total_delta_s:+.3f}s",
            delta=(
                f"L{comp_lap} "
                f"{'slower' if delta.total_delta_s > 0 else 'faster'}"
            ),
            delta_color="inverse",
        )

        if delta.corner_deltas:
            st.markdown("**Per-corner deltas:**")
            corner_cols = st.columns(
                min(len(delta.corner_deltas), 6)
            )
            for i, cd in enumerate(delta.corner_deltas):
                col = corner_cols[i % len(corner_cols)]
                col.metric(
                    f"T{cd.corner_number}",
                    f"{cd.delta_s:+.3f}s",
                    delta_color="inverse",
                )
    elif ref_lap == comp_lap:
        st.warning("Select different laps for reference and comparison.")

# --- Corners Tab ---
with tab_corners:
    if not corners:
        st.info("No corners detected. This may happen with very short laps.")
    else:
        st.markdown(
            f"**{len(corners)} corners detected** "
            f"on best lap (L{processed.best_lap})"
        )

        # Compare best vs another lap
        other_laps = [
            lap_num for lap_num in all_laps
            if lap_num != processed.best_lap
        ]
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

        fig = corner_kpi_table(
            corners, comp_corners or None, delta_dicts
        )
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

    st.caption(
        f"Analyzes all {len(all_laps)} laps across "
        f"{len(corners)} detected corners."
    )

    anomalous = find_anomalous_laps(summaries)
    if anomalous:
        excluded = ", ".join(f"L{n}" for n in sorted(anomalous))
        st.info(f"Excluding anomalous laps from analysis: {excluded}")

    coaching_laps = [n for n in all_laps if n not in anomalous]
    coaching_summaries = [s for s in summaries if s.lap_number not in anomalous]

    if st.button("Generate Coaching Report", disabled=not has_key):
        with st.spinner("Extracting corner data for all laps..."):
            all_lap_corners: AllLapCorners = {}
            for lap_num in coaching_laps:
                lap_df = processed.resampled_laps[lap_num]
                if lap_num == processed.best_lap:
                    all_lap_corners[lap_num] = corners
                else:
                    all_lap_corners[lap_num] = extract_corner_kpis_for_lap(
                        lap_df, corners
                    )

        with st.spinner("AI coach is analyzing your session..."):
            report = generate_coaching_report(
                coaching_summaries,
                all_lap_corners,
                meta.track_name,
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
            grade_data = {
                "Corner": [
                    f"T{g.corner}" for g in report.corner_grades
                ],
                "Braking": [
                    g.braking for g in report.corner_grades
                ],
                "Trail Brake": [
                    g.trail_braking for g in report.corner_grades
                ],
                "Min Speed": [
                    g.min_speed for g in report.corner_grades
                ],
                "Throttle": [
                    g.throttle for g in report.corner_grades
                ],
                "Notes": [
                    g.notes for g in report.corner_grades
                ],
            }
            st.dataframe(grade_data, use_container_width=True)

        if report.patterns:
            st.subheader("Patterns")
            for p in report.patterns:
                st.markdown(f"- {p}")

        # Chat follow-up
        st.markdown("---")
        st.subheader("Ask the Coach")
        question = st.chat_input(
            "Ask about a specific corner, technique, or anything else..."
        )
        if question:
            ctx = st.session_state.get(
                "coaching_context", CoachingContext()
            )
            with st.spinner("Thinking..."):
                answer = ask_followup(ctx, question, report)
            st.session_state["coaching_context"] = ctx

            # Display conversation
            for msg in ctx.messages:
                if msg["role"] == "user":
                    st.chat_message("user").write(msg["content"])
                else:
                    st.chat_message("assistant").write(
                        msg["content"]
                    )

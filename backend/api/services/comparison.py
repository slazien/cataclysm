"""Multi-driver session comparison service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from cataclysm.constants import MPS_TO_MPH
from cataclysm.corners import Corner
from cataclysm.delta import compute_delta

from backend.api.schemas.coaching import CoachingReportResponse, CornerGradeSchema
from backend.api.services.coaching_store import get_coaching_report
from backend.api.services.session_store import SessionData

logger = logging.getLogger(__name__)

# Map letter grades to numeric scores for skill dimension aggregation
GRADE_SCORES: dict[str, float] = {"A": 100, "B": 80, "C": 60, "D": 40, "F": 20}


def _compute_skill_dims(grades: list[CornerGradeSchema]) -> dict[str, float]:
    """Aggregate per-corner letter grades into skill dimension scores (0-100)."""
    dims: dict[str, list[float]] = {
        "braking": [],
        "trail_braking": [],
        "throttle": [],
        "line": [],
    }
    for g in grades:
        for dim_key, grade_field in [
            ("braking", "braking"),
            ("trail_braking", "trail_braking"),
            ("throttle", "throttle"),
            ("line", "min_speed"),
        ]:
            letter = getattr(g, grade_field, "C")
            score = GRADE_SCORES.get(letter, 60.0)
            dims[dim_key].append(score)
    return {k: round(sum(v) / len(v), 1) if v else 60.0 for k, v in dims.items()}


async def _get_skill_dimensions(session_id: str) -> dict[str, float] | None:
    """Extract skill dimensions from a session's coaching report, if available."""
    report: CoachingReportResponse | None = await get_coaching_report(session_id)
    if report is None or not report.corner_grades:
        return None
    return _compute_skill_dims(report.corner_grades)


async def compare_sessions(sd_a: SessionData, sd_b: SessionData) -> dict[str, Any]:
    """Compare best laps of two sessions.

    Returns a structured dict suitable for ``ComparisonResult`` construction.
    The delta convention is: positive delta_s means session B is slower than A
    (i.e. ``comp_time - ref_time`` where A is the reference).
    """
    best_a = sd_a.processed.best_lap
    best_b = sd_b.processed.best_lap

    df_a = sd_a.processed.resampled_laps[best_a]
    df_b = sd_b.processed.resampled_laps[best_b]

    # Use session A's corners as the reference for per-corner deltas
    corners = sd_a.corners

    delta_result = await asyncio.to_thread(compute_delta, df_a, df_b, corners)

    # Build per-corner speed differences using all_lap_corners for each session
    corners_a = sd_a.all_lap_corners.get(best_a, sd_a.corners)
    corners_b = sd_b.all_lap_corners.get(best_b, sd_b.corners)

    # Index corners_b by number for O(1) lookup
    corners_b_by_num: dict[int, Corner] = {c.number: c for c in corners_b}

    corner_deltas: list[dict[str, Any]] = []
    for ca in corners_a:
        cb = corners_b_by_num.get(ca.number)
        if cb is None:
            continue
        a_mph = ca.min_speed_mps * MPS_TO_MPH
        b_mph = cb.min_speed_mps * MPS_TO_MPH
        corner_deltas.append(
            {
                "corner_number": ca.number,
                "speed_diff_mph": round(a_mph - b_mph, 2),
                "a_min_speed_mph": round(a_mph, 2),
                "b_min_speed_mph": round(b_mph, 2),
                "entry_distance_m": round(ca.entry_distance_m, 1),
                "exit_distance_m": round(ca.exit_distance_m, 1),
            }
        )

    # Best lap times
    best_time_a: float | None = None
    best_time_b: float | None = None
    for ls in sd_a.processed.lap_summaries:
        if ls.lap_number == best_a:
            best_time_a = ls.lap_time_s
            break
    for ls in sd_b.processed.lap_summaries:
        if ls.lap_number == best_b:
            best_time_b = ls.lap_time_s
            break

    # Speed traces — speed vs distance for both best laps
    speed_traces: dict[str, dict[str, list[float]]] = {
        "a": {
            "distance_m": df_a["lap_distance_m"].tolist(),
            "speed_mph": (df_a["speed_mps"] * MPS_TO_MPH).tolist(),
        },
        "b": {
            "distance_m": df_b["lap_distance_m"].tolist(),
            "speed_mph": (df_b["speed_mps"] * MPS_TO_MPH).tolist(),
        },
    }

    # Skill dimensions from coaching reports (if available)
    skill_dims_a, skill_dims_b = await asyncio.gather(
        _get_skill_dimensions(sd_a.session_id),
        _get_skill_dimensions(sd_b.session_id),
    )
    # Only include skill_dimensions when BOTH drivers have coaching data
    # (radar chart requires both datasets; partial data would crash frontend)
    skill_dimensions: dict[str, dict[str, float]] | None = None
    if skill_dims_a is not None and skill_dims_b is not None:
        skill_dimensions = {"a": skill_dims_a, "b": skill_dims_b}

    # Weather conditions for mismatch detection
    weather_a = sd_a.weather
    weather_b = sd_b.weather

    return {
        "session_a_id": sd_a.session_id,
        "session_b_id": sd_b.session_id,
        "session_a_track": sd_a.snapshot.metadata.track_name,
        "session_b_track": sd_b.snapshot.metadata.track_name,
        "session_a_best_lap": best_time_a,
        "session_b_best_lap": best_time_b,
        "delta_s": delta_result.total_delta_s,
        "distance_m": delta_result.distance_m.tolist(),
        "delta_time_s": delta_result.delta_time_s.tolist(),
        "corner_deltas": corner_deltas,
        "speed_traces": speed_traces,
        "skill_dimensions": skill_dimensions,
        "ai_verdict": None,  # populated by AI narrative endpoint (Task 4)
        "session_a_weather_condition": weather_a.track_condition.value if weather_a else None,
        "session_a_weather_temp_c": weather_a.ambient_temp_c if weather_a else None,
        "session_b_weather_condition": weather_b.track_condition.value if weather_b else None,
        "session_b_weather_temp_c": weather_b.ambient_temp_c if weather_b else None,
    }

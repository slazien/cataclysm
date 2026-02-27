"""Season Wrapped aggregation service.

Collects annual statistics from in-memory sessions and coaching reports.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.api.services import session_store
from backend.api.services.coaching_store import get_coaching_report

logger = logging.getLogger(__name__)

# Personality mapping: grade dimension → (name, description)
_PERSONALITIES: list[tuple[str, str, str]] = [
    (
        "braking",
        "The Late Braker",
        "You thrive on pinpoint braking — pushing deep into corners with confidence and precision.",
    ),
    (
        "trail_braking",
        "The Smooth Operator",
        "Your trail braking finesse sets you apart. Seamless transitions from brake to throttle.",
    ),
    (
        "throttle",
        "The Throttle Master",
        "You dominate on corner exit. Maximum drive out of every turn.",
    ),
]

_MACHINE_DESC = "Metronomic consistency. You deliver the same lap, corner after corner."
_WARRIOR_DESC = "Every session is a chance to improve. Keep pushing."


def _classify_personality(
    grade_counts: dict[str, dict[str, int]],
    best_consistency: float,
) -> tuple[str, str]:
    """Determine driving personality from coaching grade distribution."""
    if not grade_counts:
        if best_consistency >= 85:
            return "The Machine", _MACHINE_DESC
        return "The Track Day Warrior", _WARRIOR_DESC

    # Check each dimension for high A/B counts
    best_dim = ""
    best_ratio = 0.0
    for dim, _name, _desc in _PERSONALITIES:
        counts = grade_counts.get(dim, {})
        total = sum(counts.values())
        if total == 0:
            continue
        good = counts.get("A", 0) + counts.get("B", 0)
        ratio = good / total
        if ratio > best_ratio:
            best_ratio = ratio
            best_dim = dim

    if best_ratio >= 0.6:
        for dim, name, desc in _PERSONALITIES:
            if dim == best_dim:
                return name, desc

    if best_consistency >= 85:
        return "The Machine", _MACHINE_DESC

    return "The Track Day Warrior", _WARRIOR_DESC


async def compute_wrapped(year: int) -> dict[str, Any]:
    """Aggregate session data for a given year.

    Uses the in-memory session store and coaching reports.
    """
    all_sessions = session_store.list_sessions()

    # Filter by year
    year_sessions = [sd for sd in all_sessions if sd.snapshot.session_date_parsed.year == year]

    if not year_sessions:
        return {
            "year": year,
            "total_sessions": 0,
            "total_laps": 0,
            "total_distance_km": 0.0,
            "tracks_visited": [],
            "total_track_time_hours": 0.0,
            "biggest_improvement_track": None,
            "biggest_improvement_s": None,
            "best_consistency_score": 0.0,
            "personality": "The Track Day Warrior",
            "personality_description": ("Upload some sessions to get your year in review!"),
            "top_corner_grade": None,
            "highlights": [],
        }

    # Basic aggregations
    total_laps = sum(sd.snapshot.n_laps for sd in year_sessions)
    tracks = list({sd.snapshot.metadata.track_name for sd in year_sessions})
    best_consistency = max(sd.snapshot.consistency_score for sd in year_sessions)

    # Total distance and track time
    total_distance_km = 0.0
    total_time_s = 0.0
    for sd in year_sessions:
        lap_df = sd.processed.resampled_laps.get(sd.processed.best_lap)
        if lap_df is not None and "distance_m" in lap_df.columns:
            track_len_m = float(lap_df["distance_m"].iloc[-1])
            total_distance_km += (track_len_m * sd.snapshot.n_laps) / 1000.0
        total_time_s += sd.snapshot.avg_lap_time_s * sd.snapshot.n_laps

    total_hours = total_time_s / 3600.0

    # Biggest improvement per track
    track_sessions: dict[str, list[Any]] = {}
    for sd in year_sessions:
        track = sd.snapshot.metadata.track_name
        track_sessions.setdefault(track, []).append(sd)

    biggest_track: str | None = None
    biggest_delta: float | None = None
    for track, sessions in track_sessions.items():
        if len(sessions) < 2:
            continue
        sorted_s = sorted(sessions, key=lambda s: s.snapshot.session_date_parsed)
        first_best = sorted_s[0].snapshot.best_lap_time_s
        last_best = sorted_s[-1].snapshot.best_lap_time_s
        delta = first_best - last_best
        if biggest_delta is None or delta > biggest_delta:
            biggest_delta = delta
            biggest_track = track

    # Coaching grade aggregation for personality
    grade_counts: dict[str, dict[str, int]] = {}
    top_grade: str | None = None
    for sd in year_sessions:
        report = await get_coaching_report(sd.session_id)
        if report and report.corner_grades:
            for cg in report.corner_grades:
                for dim in ("braking", "trail_braking", "throttle"):
                    grade = getattr(cg, dim, None)
                    if grade:
                        grade_counts.setdefault(dim, {})
                        counts = grade_counts[dim]
                        counts[grade] = counts.get(grade, 0) + 1
                        if grade == "A" and top_grade != "A":
                            top_grade = "A"
                        elif grade == "B" and top_grade not in ("A",):
                            top_grade = "B"

    personality, personality_desc = _classify_personality(grade_counts, best_consistency)

    # Build highlights
    highlights: list[dict[str, str]] = [
        {
            "label": "Total Laps",
            "value": str(total_laps),
            "category": "stat",
        },
        {
            "label": "Distance Covered",
            "value": f"{total_distance_km:.0f} km",
            "category": "stat",
        },
        {
            "label": "Track Time",
            "value": f"{total_hours:.1f} hours",
            "category": "stat",
        },
        {
            "label": "Tracks Visited",
            "value": str(len(tracks)),
            "category": "stat",
        },
    ]

    if biggest_delta is not None and biggest_delta > 0:
        highlights.append(
            {
                "label": "Biggest Improvement",
                "value": f"-{biggest_delta:.2f}s at {biggest_track}",
                "category": "achievement",
            }
        )

    return {
        "year": year,
        "total_sessions": len(year_sessions),
        "total_laps": total_laps,
        "total_distance_km": round(total_distance_km, 1),
        "tracks_visited": tracks,
        "total_track_time_hours": round(total_hours, 1),
        "biggest_improvement_track": biggest_track,
        "biggest_improvement_s": (round(biggest_delta, 3) if biggest_delta else None),
        "best_consistency_score": round(best_consistency, 1),
        "personality": personality,
        "personality_description": personality_desc,
        "top_corner_grade": top_grade,
        "highlights": highlights,
    }

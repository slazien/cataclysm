"""Pre-session briefing — generate a focused warm-up brief for returning drivers.

Uses historical coaching memory to surface focus areas, progress summaries,
and drill reminders before the driver's next session at a given track.
"""

from __future__ import annotations

from dataclasses import dataclass

from cataclysm.coaching_memory import SessionMemoryExtract


@dataclass
class PreSessionBriefing:
    """Briefing for a driver returning to a track."""

    track_name: str
    focus_areas: list[str]
    progress_summary: str
    drill_reminder: list[str]
    lap_target: str
    session_count: int


def generate_briefing(
    track_name: str,
    history: list[SessionMemoryExtract],
) -> PreSessionBriefing | None:
    """Generate a pre-session briefing from historical coaching memories.

    Filters history to the given track, extracts focus areas from the most
    recent session, computes a progress summary, and suggests a lap target.

    Returns None if no history exists for the track.
    """
    track_history = [h for h in history if h.track_name == track_name]
    if not track_history:
        return None

    # Sort by date descending — most recent first
    track_history.sort(key=lambda h: h.session_date, reverse=True)
    most_recent = track_history[0]

    focus_areas = _extract_focus_areas(most_recent)
    progress_summary = _compute_progress_summary(track_history)
    drill_reminder = most_recent.drills_assigned[:3]
    lap_target = _suggest_lap_target(track_history)

    return PreSessionBriefing(
        track_name=track_name,
        focus_areas=focus_areas,
        progress_summary=progress_summary,
        drill_reminder=drill_reminder,
        lap_target=lap_target,
        session_count=len(track_history),
    )


def _extract_focus_areas(session: SessionMemoryExtract) -> list[str]:
    """Extract 1-3 focus areas from the most recent session."""
    areas: list[str] = []

    if session.primary_focus:
        areas.append(session.primary_focus)

    for weakness in session.key_weaknesses[:2]:
        if weakness not in areas:
            areas.append(weakness)

    return areas[:3]


def _compute_progress_summary(track_history: list[SessionMemoryExtract]) -> str:
    """Compute a progress narrative from session history."""
    if len(track_history) == 1:
        session = track_history[0]
        minutes = int(session.best_lap_s // 60)
        seconds = session.best_lap_s % 60
        return f"First session at this track. Best lap: {minutes}:{seconds:05.2f}."

    best_times = [(h.session_date, h.best_lap_s) for h in track_history]
    best_times.sort(key=lambda x: x[0])  # Chronological

    first_best = best_times[0][1]
    overall_best = min(t for _, t in best_times)

    improvement = first_best - overall_best
    trend_parts: list[str] = []

    if improvement > 0.1:
        trend_parts.append(
            f"Improved {improvement:.1f}s over {len(track_history)} sessions"
        )
    else:
        trend_parts.append(f"Consistent across {len(track_history)} sessions")

    minutes = int(overall_best // 60)
    seconds = overall_best % 60
    trend_parts.append(f"PB: {minutes}:{seconds:05.2f}")

    # Check for corner grade trends
    recent = track_history[0]
    if recent.priority_corners:
        corners_str = ", ".join(f"T{c}" for c in recent.priority_corners[:2])
        trend_parts.append(f"Focus corners: {corners_str}")

    return ". ".join(trend_parts) + "."


def _suggest_lap_target(track_history: list[SessionMemoryExtract]) -> str:
    """Suggest a realistic lap time target based on progression."""
    best_times = sorted(h.best_lap_s for h in track_history)
    current_pb = best_times[0]

    if len(track_history) >= 3:
        # Look at improvement rate over last 3 sessions
        recent = sorted(track_history, key=lambda h: h.session_date, reverse=True)[:3]
        recent_bests = [h.best_lap_s for h in recent]
        avg_recent = sum(recent_bests) / len(recent_bests)
        target = current_pb - max(0.3, (avg_recent - current_pb) * 0.5)
    else:
        # Suggest 0.5s improvement for early sessions
        target = current_pb - 0.5

    minutes = int(target // 60)
    seconds = target % 60
    return f"Target: {minutes}:{seconds:05.2f}"

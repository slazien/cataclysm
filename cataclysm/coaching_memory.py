"""Coaching memory — extract and persist session coaching summaries.

Enables longitudinal tracking by extracting structured data from coaching
reports.  History can be injected into future coaching prompts so the AI
coach remembers what it said last time and tracks driver progress.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from cataclysm.coaching import CoachingReport

logger = logging.getLogger(__name__)

# Maximum number of historical sessions to include in the prompt.
_MAX_HISTORY_SESSIONS = 5

# Token budget for history section (approximate, in characters).
_HISTORY_TOKEN_BUDGET_CHARS = 4000


@dataclass
class SessionMemoryExtract:
    """Extracted from a completed coaching report for persistence."""

    session_id: str
    track_name: str
    session_date: datetime
    best_lap_s: float
    top3_avg_s: float
    priority_corners: list[int]
    corner_grades: dict[int, dict[str, str]]
    key_strengths: list[str]
    key_weaknesses: list[str]
    drills_assigned: list[str]
    primary_focus: str = ""
    conditions: str | None = None
    equipment: str | None = None
    timekiller_corner: int | None = None
    detected_archetype: str | None = None
    detected_skill: str | None = None


def extract_memory_from_report(
    report: CoachingReport,
    session_id: str,
    track_name: str,
    session_date: datetime,
    best_lap_s: float,
    top3_avg_s: float,
    conditions: str | None = None,
    equipment: str | None = None,
    timekiller_corner: int | None = None,
    detected_archetype: str | None = None,
    detected_skill: str | None = None,
) -> SessionMemoryExtract:
    """Parse a completed coaching report into structured memory.

    Extracts the most important signals for longitudinal tracking:
    - Priority corners and their grades
    - Key strengths and weaknesses from patterns
    - Assigned drills
    """
    # Extract priority corners.
    priorities: list[int] = []
    for pc in report.priority_corners:
        corner = pc.get("corner")
        if isinstance(corner, int):
            priorities.append(corner)

    # Convert corner grades to a serializable dict.
    grades: dict[int, dict[str, str]] = {}
    for cg in report.corner_grades:
        grades[cg.corner] = {
            "braking": cg.braking,
            "trail_braking": cg.trail_braking,
            "min_speed": cg.min_speed,
            "throttle": cg.throttle,
        }

    # Extract strengths and weaknesses from patterns.
    strengths: list[str] = []
    weaknesses: list[str] = []
    for pattern in report.patterns:
        lower = pattern.lower()
        if any(w in lower for w in ("strength", "strong", "excellent", "good", "improved")):
            strengths.append(pattern[:120])
        elif any(w in lower for w in ("weakness", "issue", "problem", "work on", "needs")):
            weaknesses.append(pattern[:120])

    # Cap at 3 each.
    strengths = strengths[:3]
    weaknesses = weaknesses[:3]

    # If no explicit strengths/weaknesses found, derive from grades.
    if not strengths:
        best_grades = [
            cg
            for cg in report.corner_grades
            if cg.braking in ("A", "B") and cg.min_speed in ("A", "B")
        ]
        for cg in best_grades[:2]:
            strengths.append(f"T{cg.corner}: strong braking + speed")

    if not weaknesses:
        worst_grades = [
            cg
            for cg in report.corner_grades
            if cg.braking in ("D", "F") or cg.min_speed in ("D", "F")
        ]
        for cg in worst_grades[:2]:
            weaknesses.append(f"T{cg.corner}: needs work on technique")

    return SessionMemoryExtract(
        session_id=session_id,
        track_name=track_name,
        session_date=session_date,
        best_lap_s=best_lap_s,
        top3_avg_s=top3_avg_s,
        priority_corners=priorities,
        corner_grades=grades,
        key_strengths=strengths,
        key_weaknesses=weaknesses,
        drills_assigned=report.drills[:3],
        primary_focus=report.primary_focus,
        conditions=conditions,
        equipment=equipment,
        timekiller_corner=timekiller_corner,
        detected_archetype=detected_archetype,
        detected_skill=detected_skill,
    )


def build_history_prompt_section(
    memories: list[SessionMemoryExtract],
    current_track: str,
) -> str:
    """Format session history for injection into the coaching prompt.

    Uses hierarchical summarization:
    - Most recent session: detailed (grades, priorities, drills)
    - Older sessions: compressed (best lap, priority corners, key issue)

    The total output is capped at ~4000 chars (~1000 tokens) to avoid
    bloating the prompt.
    """
    if not memories:
        return ""

    # Filter to current track and sort by date descending.
    track_memories = [m for m in memories if m.track_name == current_track]
    if not track_memories:
        return ""
    track_memories.sort(key=lambda m: m.session_date, reverse=True)

    # Cap at _MAX_HISTORY_SESSIONS.
    track_memories = track_memories[:_MAX_HISTORY_SESSIONS]

    lines: list[str] = ["\n## Session History"]
    lines.append(f"Track: {current_track} | {len(track_memories)} previous sessions")

    # Lap time progression.
    times = [(m.session_date.strftime("%Y-%m-%d"), m.best_lap_s) for m in reversed(track_memories)]
    if len(times) >= 2:
        first_time = times[0][1]
        last_time = times[-1][1]
        improvement = first_time - last_time
        lines.append(
            f"Lap time progression: {times[0][1]:.2f}s → "
            f"{times[-1][1]:.2f}s ({improvement:+.2f}s over {len(times)} sessions)"
        )

    # Most recent session — detailed.
    most_recent = track_memories[0]
    lines.append(f"\nLast session ({most_recent.session_date.strftime('%Y-%m-%d')}):")
    lines.append(
        f"  Best: {most_recent.best_lap_s:.2f}s | Top-3 avg: {most_recent.top3_avg_s:.2f}s"
    )
    if most_recent.priority_corners:
        lines.append(
            f"  Priority corners: {', '.join(f'T{c}' for c in most_recent.priority_corners)}"
        )
    if most_recent.key_strengths:
        lines.append(f"  Strengths: {'; '.join(most_recent.key_strengths)}")
    if most_recent.key_weaknesses:
        lines.append(f"  Weaknesses: {'; '.join(most_recent.key_weaknesses)}")
    if most_recent.primary_focus:
        lines.append(f"  Primary focus: {most_recent.primary_focus}")
    if most_recent.drills_assigned:
        lines.append(f"  Drills assigned: {'; '.join(most_recent.drills_assigned)}")

    # Older sessions — compressed.
    for m in track_memories[1:]:
        date_str = m.session_date.strftime("%Y-%m-%d")
        priority_str = ", ".join(f"T{c}" for c in m.priority_corners[:2])
        weakness_str = m.key_weaknesses[0] if m.key_weaknesses else "none"
        lines.append(
            f"  {date_str}: best {m.best_lap_s:.2f}s | focus: {priority_str} | {weakness_str}"
        )

    # Coaching instruction.
    lines.append(
        "\nReference this history when coaching. Acknowledge progress "
        '("Your T5 brake point improved since last session") and '
        "check whether previously assigned drills were practiced. "
        "Don't repeat the same advice if the driver already improved."
    )

    result = "\n".join(lines)
    # Truncate if over budget.
    if len(result) > _HISTORY_TOKEN_BUDGET_CHARS:
        result = result[:_HISTORY_TOKEN_BUDGET_CHARS] + "\n[History truncated]"
    return result

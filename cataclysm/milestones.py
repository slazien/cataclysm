"""Milestone detection — identify noteworthy achievements across sessions.

Compares the current session against historical coaching memories to detect
personal bests, technique unlocks, consistency improvements, and flow states.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cataclysm.coaching_memory import SessionMemoryExtract
from cataclysm.flow_lap import FlowLapResult


class MilestoneType(StrEnum):
    PERSONAL_BEST = "personal_best"
    CORNER_PB = "corner_pb"
    CONSISTENCY_UNLOCK = "consistency_unlock"
    BRAKE_POINT_IMPROVEMENT = "brake_point_improvement"
    SUB_LAP_TIME = "sub_lap_time"
    TECHNIQUE_UNLOCK = "technique_unlock"
    FLOW_STATE = "flow_state"


@dataclass
class Milestone:
    """A noteworthy achievement in the current session."""

    type: MilestoneType
    description: str  # "New personal best: 1:42.3 (-0.8s)"
    magnitude: float  # Size of improvement (seconds for time, grade for technique)
    corner: int | None = None  # None for session-wide milestones


def detect_milestones(
    current: SessionMemoryExtract,
    history: list[SessionMemoryExtract],
    flow_result: FlowLapResult | None = None,
) -> list[Milestone]:
    """Compare current session to history to detect milestone events.

    Only considers sessions at the same track. Returns milestones sorted
    by magnitude (biggest first).
    """
    milestones: list[Milestone] = []

    # Filter history to same track
    track_history = [h for h in history if h.track_name == current.track_name]

    if track_history:
        milestones.extend(_check_personal_best(current, track_history))
        milestones.extend(_check_corner_improvements(current, track_history))
        milestones.extend(_check_technique_unlock(current, track_history))
        milestones.extend(_check_sub_lap_time(current, track_history))

    if flow_result is not None:
        milestones.extend(_check_flow_state(flow_result))

    # Sort by magnitude descending
    milestones.sort(key=lambda m: m.magnitude, reverse=True)
    return milestones


def _check_personal_best(
    current: SessionMemoryExtract,
    history: list[SessionMemoryExtract],
) -> list[Milestone]:
    """Check if this session set a new personal best lap time."""
    previous_best = min(h.best_lap_s for h in history)
    if current.best_lap_s < previous_best:
        improvement = previous_best - current.best_lap_s
        minutes = int(current.best_lap_s // 60)
        seconds = current.best_lap_s % 60
        return [
            Milestone(
                type=MilestoneType.PERSONAL_BEST,
                description=(
                    f"New personal best: {minutes}:{seconds:05.2f} "
                    f"({improvement:+.2f}s improvement)"
                ),
                magnitude=improvement,
            )
        ]
    return []


def _check_corner_improvements(
    current: SessionMemoryExtract,
    history: list[SessionMemoryExtract],
) -> list[Milestone]:
    """Check for corner-level grade improvements vs most recent session."""
    if not history:
        return []
    most_recent = max(history, key=lambda h: h.session_date)
    milestones: list[Milestone] = []

    grade_order = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4}

    for corner_num, current_grades in current.corner_grades.items():
        prev_grades = most_recent.corner_grades.get(corner_num, {})
        for criterion in ("braking", "min_speed", "throttle"):
            cur_grade = current_grades.get(criterion, "")
            prev_grade = prev_grades.get(criterion, "")
            cur_val = grade_order.get(cur_grade, -1)
            prev_val = grade_order.get(prev_grade, -1)
            if cur_val > prev_val and prev_val >= 0:
                jump = cur_val - prev_val
                milestones.append(
                    Milestone(
                        type=MilestoneType.CORNER_PB,
                        description=(f"T{corner_num} {criterion}: {prev_grade} -> {cur_grade}"),
                        magnitude=float(jump),
                        corner=corner_num,
                    )
                )
    return milestones


def _check_technique_unlock(
    current: SessionMemoryExtract,
    history: list[SessionMemoryExtract],
) -> list[Milestone]:
    """Check if a technique appeared for the first time (e.g., trail braking).

    Detects when a corner's trail_braking grade goes from N/A or F to a passing grade.
    """
    if not history:
        return []
    most_recent = max(history, key=lambda h: h.session_date)
    milestones: list[Milestone] = []
    passing_grades = {"A", "B", "C"}

    for corner_num, current_grades in current.corner_grades.items():
        prev_grades = most_recent.corner_grades.get(corner_num, {})
        cur_tb = current_grades.get("trail_braking", "")
        prev_tb = prev_grades.get("trail_braking", "")
        if cur_tb in passing_grades and prev_tb in ("N/A", "F", ""):
            milestones.append(
                Milestone(
                    type=MilestoneType.TECHNIQUE_UNLOCK,
                    description=(
                        f"Trail braking unlocked at T{corner_num}! "
                        f"({prev_tb or 'none'} -> {cur_tb})"
                    ),
                    magnitude=2.0,
                    corner=corner_num,
                )
            )
    return milestones


def _check_sub_lap_time(
    current: SessionMemoryExtract,
    history: list[SessionMemoryExtract],
) -> list[Milestone]:
    """Check if the driver broke through a round-number barrier.

    E.g., first time under 1:30, 1:40, 1:50, 2:00, etc.
    """
    all_previous_bests = [h.best_lap_s for h in history]
    previous_overall_best = min(all_previous_bests) if all_previous_bests else float("inf")

    milestones: list[Milestone] = []
    # Check common round-number barriers (in seconds)
    for barrier_s in range(60, 300, 10):
        if current.best_lap_s < barrier_s <= previous_overall_best:
            minutes = barrier_s // 60
            secs = barrier_s % 60
            milestones.append(
                Milestone(
                    type=MilestoneType.SUB_LAP_TIME,
                    description=f"First time under {minutes}:{secs:02d}!",
                    magnitude=previous_overall_best - current.best_lap_s,
                )
            )
    return milestones


def _check_flow_state(flow_result: FlowLapResult) -> list[Milestone]:
    """Check if any flow laps were detected."""
    if flow_result.flow_laps:
        return [
            Milestone(
                type=MilestoneType.FLOW_STATE,
                description=(
                    f"Flow state detected on "
                    f"{'lap' if len(flow_result.flow_laps) == 1 else 'laps'} "
                    f"{', '.join(f'L{lap}' for lap in flow_result.flow_laps)}"
                ),
                magnitude=len(flow_result.flow_laps) * 0.5,
            )
        ]
    return []


def format_milestones_for_prompt(milestones: list[Milestone]) -> str:
    """Format milestones as XML for the coaching prompt."""
    if not milestones:
        return ""

    lines = ['<milestones note="celebrate these with the driver!">']
    for m in milestones[:5]:  # Cap at 5
        corner_attr = f' corner="T{m.corner}"' if m.corner else ""
        lines.append(f'  <milestone type="{m.type.value}"{corner_attr}>')
        lines.append(f"    {m.description}")
        lines.append("  </milestone>")
    lines.append("</milestones>")
    return "\n".join(lines)

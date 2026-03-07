"""Tests for cataclysm.milestones — milestone detection across sessions."""

from __future__ import annotations

from datetime import datetime

import pytest

from cataclysm.coaching_memory import SessionMemoryExtract
from cataclysm.flow_lap import FlowLapResult
from cataclysm.milestones import (
    Milestone,
    MilestoneType,
    _check_corner_improvements,
    _check_technique_unlock,
    detect_milestones,
    format_milestones_for_prompt,
)


def _make_memory(
    session_id: str = "s1",
    track: str = "Barber",
    date: datetime | None = None,
    best_lap: float = 95.0,
    top3_avg: float = 96.5,
    corner_grades: dict[int, dict[str, str]] | None = None,
    priority_corners: list[int] | None = None,
) -> SessionMemoryExtract:
    if date is None:
        date = datetime(2026, 1, 15)
    if corner_grades is None:
        corner_grades = {
            3: {"braking": "B", "trail_braking": "B", "min_speed": "B", "throttle": "B"},
            5: {"braking": "C", "trail_braking": "C", "min_speed": "C", "throttle": "C"},
        }
    if priority_corners is None:
        priority_corners = [5, 3]
    return SessionMemoryExtract(
        session_id=session_id,
        track_name=track,
        session_date=date,
        best_lap_s=best_lap,
        top3_avg_s=top3_avg,
        priority_corners=priority_corners,
        corner_grades=corner_grades,
        key_strengths=["Good braking at T3"],
        key_weaknesses=["Slow entry at T5"],
        drills_assigned=["Brake at 2-board"],
    )


class TestDetectMilestones:
    def test_personal_best(self) -> None:
        current = _make_memory(best_lap=92.0)
        history = [_make_memory(session_id="old", best_lap=95.0)]
        milestones = detect_milestones(current, history)
        pb = [m for m in milestones if m.type == MilestoneType.PERSONAL_BEST]
        assert len(pb) == 1
        assert pb[0].magnitude == pytest.approx(3.0)

    def test_no_pb_when_slower(self) -> None:
        current = _make_memory(best_lap=96.0)
        history = [_make_memory(session_id="old", best_lap=95.0)]
        milestones = detect_milestones(current, history)
        pb = [m for m in milestones if m.type == MilestoneType.PERSONAL_BEST]
        assert len(pb) == 0

    def test_corner_grade_improvement(self) -> None:
        old_grades = {
            3: {"braking": "C", "trail_braking": "C", "min_speed": "C", "throttle": "C"},
        }
        new_grades = {
            3: {"braking": "A", "trail_braking": "C", "min_speed": "C", "throttle": "C"},
        }
        current = _make_memory(corner_grades=new_grades, date=datetime(2026, 2, 1))
        history = [
            _make_memory(session_id="old", corner_grades=old_grades, date=datetime(2026, 1, 15))
        ]
        milestones = detect_milestones(current, history)
        corner_pbs = [m for m in milestones if m.type == MilestoneType.CORNER_PB]
        assert len(corner_pbs) >= 1
        assert any(m.corner == 3 for m in corner_pbs)

    def test_technique_unlock_trail_braking(self) -> None:
        old_grades = {
            5: {"braking": "C", "trail_braking": "N/A", "min_speed": "C", "throttle": "C"},
        }
        new_grades = {
            5: {"braking": "C", "trail_braking": "B", "min_speed": "C", "throttle": "C"},
        }
        current = _make_memory(corner_grades=new_grades, date=datetime(2026, 2, 1))
        history = [
            _make_memory(session_id="old", corner_grades=old_grades, date=datetime(2026, 1, 15))
        ]
        milestones = detect_milestones(current, history)
        unlocks = [m for m in milestones if m.type == MilestoneType.TECHNIQUE_UNLOCK]
        assert len(unlocks) == 1
        assert unlocks[0].corner == 5

    def test_sub_lap_time_barrier(self) -> None:
        # Previous best was 101s, new is 98s → broke 1:40 barrier (100s)
        current = _make_memory(best_lap=98.0)
        history = [_make_memory(session_id="old", best_lap=101.0)]
        milestones = detect_milestones(current, history)
        sub = [m for m in milestones if m.type == MilestoneType.SUB_LAP_TIME]
        assert len(sub) == 1
        assert "1:40" in sub[0].description

    def test_flow_state_detected(self) -> None:
        current = _make_memory()
        flow = FlowLapResult(flow_laps=[8, 12], scores={8: 0.85, 12: 0.80}, threshold=0.75)
        milestones = detect_milestones(current, [], flow_result=flow)
        flows = [m for m in milestones if m.type == MilestoneType.FLOW_STATE]
        assert len(flows) == 1
        assert "L8" in flows[0].description
        assert "L12" in flows[0].description

    def test_no_flow_when_empty(self) -> None:
        current = _make_memory()
        flow = FlowLapResult(flow_laps=[], scores={}, threshold=0.75)
        milestones = detect_milestones(current, [], flow_result=flow)
        flows = [m for m in milestones if m.type == MilestoneType.FLOW_STATE]
        assert len(flows) == 0

    def test_different_track_ignored(self) -> None:
        current = _make_memory(track="Barber", best_lap=80.0)
        history = [_make_memory(session_id="old", track="Laguna Seca", best_lap=100.0)]
        milestones = detect_milestones(current, history)
        # No PB because history is different track
        pb = [m for m in milestones if m.type == MilestoneType.PERSONAL_BEST]
        assert len(pb) == 0

    def test_milestones_sorted_by_magnitude(self) -> None:
        current = _make_memory(
            best_lap=92.0,
            corner_grades={
                3: {"braking": "A", "trail_braking": "C", "min_speed": "C", "throttle": "C"},
            },
        )
        history = [
            _make_memory(
                session_id="old",
                best_lap=95.0,
                corner_grades={
                    3: {"braking": "C", "trail_braking": "C", "min_speed": "C", "throttle": "C"}
                },
            )
        ]
        milestones = detect_milestones(current, history)
        magnitudes = [m.magnitude for m in milestones]
        assert magnitudes == sorted(magnitudes, reverse=True)

    def test_empty_history(self) -> None:
        current = _make_memory()
        milestones = detect_milestones(current, [])
        assert isinstance(milestones, list)


class TestFormatMilestones:
    def test_empty(self) -> None:
        assert format_milestones_for_prompt([]) == ""

    def test_produces_xml(self) -> None:
        milestones = [
            Milestone(
                type=MilestoneType.PERSONAL_BEST,
                description="New PB: 1:32.5",
                magnitude=1.5,
            ),
        ]
        text = format_milestones_for_prompt(milestones)
        assert "<milestones" in text
        assert "personal_best" in text
        assert "New PB" in text

    def test_caps_at_five(self) -> None:
        milestones = [
            Milestone(
                type=MilestoneType.CORNER_PB,
                description=f"T{i} improved",
                magnitude=float(i),
                corner=i,
            )
            for i in range(10)
        ]
        text = format_milestones_for_prompt(milestones)
        assert text.count("<milestone type=") == 5


class TestCheckHelperEmptyHistory:
    """Target lines 94 and 129: helper functions with empty history return []."""

    def test_check_corner_improvements_empty_history_returns_empty(self) -> None:
        """_check_corner_improvements with empty history returns [] (line 94)."""
        current = _make_memory()
        result = _check_corner_improvements(current, [])
        assert result == []

    def test_check_technique_unlock_empty_history_returns_empty(self) -> None:
        """_check_technique_unlock with empty history returns [] (line 129)."""
        current = _make_memory()
        result = _check_technique_unlock(current, [])
        assert result == []

"""Tests for cataclysm.coaching_memory — session memory extraction and history."""

from __future__ import annotations

from datetime import datetime

from cataclysm.coaching import CoachingReport, CornerGrade
from cataclysm.coaching_memory import (
    _HISTORY_TOKEN_BUDGET_CHARS,
    _MAX_HISTORY_SESSIONS,
    SessionMemoryExtract,
    build_history_prompt_section,
    extract_memory_from_report,
)


def _make_corner_grade(
    corner: int,
    braking: str = "B",
    trail_braking: str = "C",
    min_speed: str = "B",
    throttle: str = "B",
) -> CornerGrade:
    return CornerGrade(
        corner=corner,
        braking=braking,
        trail_braking=trail_braking,
        min_speed=min_speed,
        throttle=throttle,
        notes="",
    )


def _make_report(
    *,
    priority_corners: list[dict] | None = None,
    corner_grades: list[CornerGrade] | None = None,
    patterns: list[str] | None = None,
    drills: list[str] | None = None,
) -> CoachingReport:
    if priority_corners is None:
        priority_corners = [
            {"corner": 3, "reason": "biggest gain"},
            {"corner": 7, "reason": "consistency"},
        ]
    if corner_grades is None:
        corner_grades = [
            _make_corner_grade(3, braking="A", min_speed="A"),
            _make_corner_grade(7, braking="D", min_speed="C"),
        ]
    if patterns is None:
        patterns = [
            "Strength: consistent braking into T3",
            "Weakness: late apex in T7 needs work on entry speed",
        ]
    if drills is None:
        drills = ["Brake 5m later into T7", "Trail brake deeper in T3"]

    return CoachingReport(
        summary="Good session with room to improve T7.",
        priority_corners=priority_corners,
        corner_grades=corner_grades,
        patterns=patterns,
        drills=drills,
    )


def _make_memory(
    session_id: str = "sess-1",
    track: str = "Barber",
    date: datetime | None = None,
    best_lap: float = 95.0,
    top3_avg: float = 96.5,
) -> SessionMemoryExtract:
    if date is None:
        date = datetime(2026, 1, 15)
    report = _make_report()
    return extract_memory_from_report(
        report=report,
        session_id=session_id,
        track_name=track,
        session_date=date,
        best_lap_s=best_lap,
        top3_avg_s=top3_avg,
    )


class TestExtractMemoryFromReport:
    def test_extracts_priority_corners(self) -> None:
        mem = _make_memory()
        assert 3 in mem.priority_corners
        assert 7 in mem.priority_corners

    def test_extracts_corner_grades(self) -> None:
        mem = _make_memory()
        assert 3 in mem.corner_grades
        assert mem.corner_grades[3]["braking"] == "A"
        assert 7 in mem.corner_grades
        assert mem.corner_grades[7]["braking"] == "D"

    def test_extracts_strengths(self) -> None:
        mem = _make_memory()
        assert len(mem.key_strengths) >= 1
        assert any("braking" in s.lower() for s in mem.key_strengths)

    def test_extracts_weaknesses(self) -> None:
        mem = _make_memory()
        assert len(mem.key_weaknesses) >= 1
        assert any("work" in w.lower() or "needs" in w.lower() for w in mem.key_weaknesses)

    def test_caps_strengths_at_3(self) -> None:
        patterns = [f"Strength: item {i}" for i in range(10)]
        report = _make_report(patterns=patterns)
        mem = extract_memory_from_report(
            report=report,
            session_id="s1",
            track_name="T",
            session_date=datetime(2026, 1, 1),
            best_lap_s=90.0,
            top3_avg_s=91.0,
        )
        assert len(mem.key_strengths) <= 3

    def test_drills_extracted(self) -> None:
        mem = _make_memory()
        assert len(mem.drills_assigned) >= 1
        assert len(mem.drills_assigned) <= 3

    def test_derives_strengths_from_grades(self) -> None:
        """When no explicit strength patterns, derive from A/B grades."""
        report = _make_report(patterns=["Some neutral observation"])
        mem = extract_memory_from_report(
            report=report,
            session_id="s1",
            track_name="T",
            session_date=datetime(2026, 1, 1),
            best_lap_s=90.0,
            top3_avg_s=91.0,
        )
        # Should derive from the A-graded T3
        assert len(mem.key_strengths) >= 1

    def test_derives_weaknesses_from_grades(self) -> None:
        """When no explicit weakness patterns, derive from D/F grades."""
        report = _make_report(patterns=["Some neutral observation"])
        mem = extract_memory_from_report(
            report=report,
            session_id="s1",
            track_name="T",
            session_date=datetime(2026, 1, 1),
            best_lap_s=90.0,
            top3_avg_s=91.0,
        )
        # Should derive from the D-graded T7
        assert len(mem.key_weaknesses) >= 1

    def test_optional_fields(self) -> None:
        report = _make_report()
        mem = extract_memory_from_report(
            report=report,
            session_id="s1",
            track_name="Barber",
            session_date=datetime(2026, 1, 1),
            best_lap_s=90.0,
            top3_avg_s=91.0,
            conditions="dry, 75F",
            equipment="Hankook RS4",
            timekiller_corner=5,
            detected_archetype="SMOOTH_OPERATOR",
            detected_skill="intermediate",
        )
        assert mem.conditions == "dry, 75F"
        assert mem.equipment == "Hankook RS4"
        assert mem.timekiller_corner == 5
        assert mem.detected_archetype == "SMOOTH_OPERATOR"
        assert mem.detected_skill == "intermediate"

    def test_handles_non_int_corner_in_priority(self) -> None:
        report = _make_report(priority_corners=[{"corner": "bad"}, {"corner": 3}])
        mem = extract_memory_from_report(
            report=report,
            session_id="s1",
            track_name="T",
            session_date=datetime(2026, 1, 1),
            best_lap_s=90.0,
            top3_avg_s=91.0,
        )
        assert mem.priority_corners == [3]


class TestBuildHistoryPromptSection:
    def test_empty_memories(self) -> None:
        assert build_history_prompt_section([], "Barber") == ""

    def test_wrong_track_returns_empty(self) -> None:
        mem = _make_memory(track="Barber")
        assert build_history_prompt_section([mem], "Laguna Seca") == ""

    def test_single_session_output(self) -> None:
        mem = _make_memory()
        text = build_history_prompt_section([mem], "Barber")
        assert "Session History" in text
        assert "Barber" in text
        assert "95.00" in text

    def test_progression_with_multiple_sessions(self) -> None:
        memories = [
            _make_memory(session_id="s1", date=datetime(2026, 1, 10), best_lap=97.0),
            _make_memory(session_id="s2", date=datetime(2026, 1, 20), best_lap=95.0),
            _make_memory(session_id="s3", date=datetime(2026, 1, 30), best_lap=93.0),
        ]
        text = build_history_prompt_section(memories, "Barber")
        assert "progression" in text.lower()
        assert "97.00" in text
        assert "93.00" in text

    def test_most_recent_is_detailed(self) -> None:
        memories = [
            _make_memory(session_id="s1", date=datetime(2026, 1, 10)),
            _make_memory(session_id="s2", date=datetime(2026, 1, 20)),
        ]
        text = build_history_prompt_section(memories, "Barber")
        assert "Priority corners" in text or "Strengths" in text

    def test_caps_at_max_sessions(self) -> None:
        memories = [
            _make_memory(
                session_id=f"s{i}",
                date=datetime(2026, 1, i + 1),
                best_lap=100.0 - i,
            )
            for i in range(_MAX_HISTORY_SESSIONS + 3)
        ]
        text = build_history_prompt_section(memories, "Barber")
        assert f"{_MAX_HISTORY_SESSIONS} previous sessions" in text

    def test_truncates_long_output(self) -> None:
        # Create many sessions with long patterns to force truncation.
        memories = [
            _make_memory(
                session_id=f"s{i}",
                date=datetime(2026, 1, i + 1),
            )
            for i in range(_MAX_HISTORY_SESSIONS)
        ]
        # Even with max sessions, should not exceed budget + truncation notice.
        text = build_history_prompt_section(memories, "Barber")
        assert len(text) <= _HISTORY_TOKEN_BUDGET_CHARS + 50

    def test_contains_coaching_instruction(self) -> None:
        mem = _make_memory()
        text = build_history_prompt_section([mem], "Barber")
        assert "Reference this history" in text

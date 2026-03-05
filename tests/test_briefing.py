"""Tests for cataclysm.briefing — pre-session briefing generation."""

from __future__ import annotations

from datetime import datetime

from cataclysm.briefing import PreSessionBriefing, generate_briefing
from cataclysm.coaching_memory import SessionMemoryExtract


def _make_memory(
    session_id: str = "s1",
    track: str = "Barber",
    date: datetime | None = None,
    best_lap: float = 95.0,
    top3_avg: float = 96.5,
    primary_focus: str = "Brake later at T5",
) -> SessionMemoryExtract:
    if date is None:
        date = datetime(2026, 1, 15)
    return SessionMemoryExtract(
        session_id=session_id,
        track_name=track,
        session_date=date,
        best_lap_s=best_lap,
        top3_avg_s=top3_avg,
        priority_corners=[5, 3],
        corner_grades={
            3: {"braking": "B", "min_speed": "B", "throttle": "B"},
            5: {"braking": "C", "min_speed": "C", "throttle": "C"},
        },
        key_strengths=["Good braking at T3"],
        key_weaknesses=["Late trail braking at T5", "Wide exit at T3"],
        drills_assigned=["Brake at 2-board", "Focus on throttle commit"],
        primary_focus=primary_focus,
    )


class TestGenerateBriefing:
    def test_no_history_returns_none(self) -> None:
        assert generate_briefing("Barber", []) is None

    def test_wrong_track_returns_none(self) -> None:
        history = [_make_memory(track="Laguna Seca")]
        assert generate_briefing("Barber", history) is None

    def test_single_session_produces_briefing(self) -> None:
        history = [_make_memory()]
        result = generate_briefing("Barber", history)
        assert result is not None
        assert isinstance(result, PreSessionBriefing)
        assert result.track_name == "Barber"
        assert result.session_count == 1

    def test_focus_areas_from_primary_focus(self) -> None:
        history = [_make_memory(primary_focus="Brake later at T5")]
        result = generate_briefing("Barber", history)
        assert result is not None
        assert "Brake later at T5" in result.focus_areas

    def test_focus_areas_include_weaknesses(self) -> None:
        history = [_make_memory(primary_focus="")]
        result = generate_briefing("Barber", history)
        assert result is not None
        assert len(result.focus_areas) >= 1
        assert "Late trail braking at T5" in result.focus_areas

    def test_focus_areas_capped_at_three(self) -> None:
        history = [_make_memory()]
        result = generate_briefing("Barber", history)
        assert result is not None
        assert len(result.focus_areas) <= 3

    def test_drill_reminder_from_last_session(self) -> None:
        history = [_make_memory()]
        result = generate_briefing("Barber", history)
        assert result is not None
        assert "Brake at 2-board" in result.drill_reminder

    def test_progress_summary_single_session(self) -> None:
        history = [_make_memory()]
        result = generate_briefing("Barber", history)
        assert result is not None
        assert "First session" in result.progress_summary

    def test_progress_summary_multiple_sessions(self) -> None:
        history = [
            _make_memory("s1", date=datetime(2026, 1, 1), best_lap=98.0),
            _make_memory("s2", date=datetime(2026, 1, 15), best_lap=96.0),
            _make_memory("s3", date=datetime(2026, 2, 1), best_lap=94.0),
        ]
        result = generate_briefing("Barber", history)
        assert result is not None
        assert "Improved" in result.progress_summary
        assert "3 sessions" in result.progress_summary

    def test_lap_target_improves_on_pb(self) -> None:
        history = [_make_memory(best_lap=95.0)]
        result = generate_briefing("Barber", history)
        assert result is not None
        assert "Target" in result.lap_target
        # Target should be faster than PB
        assert "1:34" in result.lap_target  # 95 - 0.5 = 94.5 = 1:34.50

    def test_uses_most_recent_session(self) -> None:
        old = _make_memory("s1", date=datetime(2026, 1, 1), primary_focus="Old focus")
        new = _make_memory("s2", date=datetime(2026, 2, 1), primary_focus="New focus")
        result = generate_briefing("Barber", [old, new])
        assert result is not None
        assert "New focus" in result.focus_areas

    def test_filters_to_requested_track(self) -> None:
        barber = _make_memory("s1", track="Barber", best_lap=95.0)
        laguna = _make_memory("s2", track="Laguna Seca", best_lap=85.0)
        result = generate_briefing("Barber", [barber, laguna])
        assert result is not None
        assert result.session_count == 1

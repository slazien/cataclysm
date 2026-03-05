"""Tests for Season Wrapped service."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.api.schemas.coaching import CornerGradeSchema
from backend.api.services.wrapped import _classify_personality, compute_wrapped

# ---------------------------------------------------------------------------
# Helpers — build lightweight mock objects for SessionData / SessionSnapshot
# ---------------------------------------------------------------------------


def _make_lap_df(track_len_m: float = 4000.0) -> pd.DataFrame:
    """Build a minimal resampled-lap DataFrame with lap_distance_m column."""
    n = 100
    return pd.DataFrame({"lap_distance_m": np.linspace(0, track_len_m, n)})


def _make_snapshot(
    track_name: str = "Test Circuit",
    session_date: datetime | None = None,
    best_lap_time_s: float = 92.0,
    avg_lap_time_s: float = 94.0,
    n_laps: int = 5,
    consistency_score: float = 75.0,
) -> MagicMock:
    """Return a MagicMock mimicking a SessionSnapshot."""
    snap = MagicMock()
    snap.metadata.track_name = track_name
    snap.session_date_parsed = session_date or datetime(2025, 6, 15, 10, 0)
    snap.best_lap_time_s = best_lap_time_s
    snap.avg_lap_time_s = avg_lap_time_s
    snap.n_laps = n_laps
    snap.consistency_score = consistency_score
    return snap


def _make_session_data(
    session_id: str = "sess-1",
    track_name: str = "Test Circuit",
    session_date: datetime | None = None,
    best_lap_time_s: float = 92.0,
    avg_lap_time_s: float = 94.0,
    n_laps: int = 5,
    consistency_score: float = 75.0,
    track_len_m: float = 4000.0,
    best_lap: int = 1,
) -> MagicMock:
    """Return a MagicMock that mimics SessionData including processed lap frames."""
    sd = MagicMock()
    sd.session_id = session_id
    sd.snapshot = _make_snapshot(
        track_name=track_name,
        session_date=session_date,
        best_lap_time_s=best_lap_time_s,
        avg_lap_time_s=avg_lap_time_s,
        n_laps=n_laps,
        consistency_score=consistency_score,
    )
    lap_df = _make_lap_df(track_len_m)
    sd.processed.best_lap = best_lap
    sd.processed.resampled_laps = {best_lap: lap_df}
    return sd


def _make_corner_grade(
    corner: int = 1,
    braking: str = "A",
    trail_braking: str = "B",
    throttle: str = "A",
) -> CornerGradeSchema:
    """Return a CornerGradeSchema with provided grades."""
    return CornerGradeSchema(
        corner=corner,
        braking=braking,
        trail_braking=trail_braking,
        min_speed="B",
        throttle=throttle,
        notes="test",
    )


def _make_coaching_report(corner_grades: list[CornerGradeSchema]) -> MagicMock:
    """Return a MagicMock coaching report with the given corner grades."""
    report = MagicMock()
    report.corner_grades = corner_grades
    return report


# ---------------------------------------------------------------------------
# _classify_personality — existing tests + new edge cases
# ---------------------------------------------------------------------------


def test_classify_personality_empty_grades() -> None:
    """No coaching data with low consistency defaults to Warrior."""
    name, _ = _classify_personality({}, 50.0)
    assert name == "The Track Day Warrior"


def test_classify_personality_high_consistency() -> None:
    """High consistency with no grades -> The Machine."""
    name, _ = _classify_personality({}, 90.0)
    assert name == "The Machine"


def test_classify_personality_braking_dominant() -> None:
    """Majority A braking grades -> The Late Braker."""
    grade_counts = {
        "braking": {"A": 10, "B": 3, "C": 1},
        "trail_braking": {"B": 5, "C": 9},
        "throttle": {"C": 8, "D": 6},
    }
    name, _ = _classify_personality(grade_counts, 70.0)
    assert name == "The Late Braker"


def test_classify_personality_throttle_dominant() -> None:
    """Majority A/B throttle -> The Throttle Master."""
    grade_counts = {
        "braking": {"C": 10},
        "trail_braking": {"C": 10},
        "throttle": {"A": 8, "B": 4, "C": 2},
    }
    name, _ = _classify_personality(grade_counts, 70.0)
    assert name == "The Throttle Master"


def test_classify_personality_trail_braking_dominant() -> None:
    """Majority A/B trail braking -> The Smooth Operator."""
    grade_counts = {
        "braking": {"C": 10},
        "trail_braking": {"A": 6, "B": 4, "C": 2},
        "throttle": {"C": 10},
    }
    name, _ = _classify_personality(grade_counts, 70.0)
    assert name == "The Smooth Operator"


def test_classify_personality_no_clear_winner() -> None:
    """No dimension has 60%+ A/B -> fallback based on consistency."""
    grade_counts = {
        "braking": {"A": 2, "C": 8},
        "trail_braking": {"A": 2, "C": 8},
        "throttle": {"A": 2, "C": 8},
    }
    name, _ = _classify_personality(grade_counts, 90.0)
    assert name == "The Machine"


def test_classify_personality_no_clear_winner_low_consistency() -> None:
    """No 60% A/B winner AND low consistency -> Warrior."""
    grade_counts = {
        "braking": {"A": 2, "C": 8},
        "trail_braking": {"A": 2, "C": 8},
        "throttle": {"A": 2, "C": 8},
    }
    name, desc = _classify_personality(grade_counts, 60.0)
    assert name == "The Track Day Warrior"
    assert "improve" in desc.lower() or "pushing" in desc.lower()


def test_classify_personality_returns_description() -> None:
    """Each personality returns a non-empty description string."""
    for grade_counts, consistency, expected_name in [
        ({}, 90.0, "The Machine"),
        ({}, 50.0, "The Track Day Warrior"),
        ({"braking": {"A": 10, "C": 1}}, 70.0, "The Late Braker"),
    ]:
        name, desc = _classify_personality(grade_counts, consistency)  # type: ignore[arg-type]
        assert name == expected_name
        assert isinstance(desc, str)
        assert len(desc) > 0


def test_classify_personality_boundary_consistency_exactly_85() -> None:
    """Consistency exactly at 85 triggers The Machine when no dominant dimension."""
    name, _ = _classify_personality({}, 85.0)
    assert name == "The Machine"


def test_classify_personality_boundary_consistency_below_85() -> None:
    """Consistency just below 85 keeps Warrior when grades are empty."""
    name, _ = _classify_personality({}, 84.9)
    assert name == "The Track Day Warrior"


def test_classify_personality_zero_total_dimension_skipped() -> None:
    """A dimension with all-zero counts is skipped, not treated as best."""
    grade_counts = {
        "braking": {},
        "trail_braking": {"A": 6, "B": 4, "C": 2},
        "throttle": {},
    }
    name, _ = _classify_personality(grade_counts, 70.0)
    assert name == "The Smooth Operator"


def test_classify_personality_exactly_60_pct_ratio_qualifies() -> None:
    """A ratio of exactly 0.6 A/B is sufficient for personality classification."""
    grade_counts = {"braking": {"A": 4, "B": 2, "C": 4}}
    name, _ = _classify_personality(grade_counts, 70.0)
    assert name == "The Late Braker"


def test_classify_personality_just_below_60_pct_falls_back() -> None:
    """A ratio just below 0.6 A/B does not qualify for personality classification."""
    grade_counts = {"braking": {"A": 3, "B": 2, "C": 4}}
    name, _ = _classify_personality(grade_counts, 70.0)
    assert name == "The Track Day Warrior"


# ---------------------------------------------------------------------------
# compute_wrapped -- empty year
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_wrapped_empty_year() -> None:
    """No sessions for the year returns empty wrapped data."""
    with patch("backend.api.services.wrapped.session_store") as mock_store:
        mock_store.list_sessions.return_value = []
        result = await compute_wrapped(2025)

    assert result["year"] == 2025
    assert result["total_sessions"] == 0
    assert result["total_laps"] == 0
    assert result["personality"] == "The Track Day Warrior"


@pytest.mark.asyncio
async def test_compute_wrapped_empty_year_all_fields_present() -> None:
    """Empty-year result contains all expected keys with correct defaults."""
    with patch("backend.api.services.wrapped.session_store") as mock_store:
        mock_store.list_sessions.return_value = []
        result = await compute_wrapped(2030)

    assert result["total_distance_km"] == 0.0
    assert result["tracks_visited"] == []
    assert result["total_track_time_hours"] == 0.0
    assert result["biggest_improvement_track"] is None
    assert result["biggest_improvement_s"] is None
    assert result["best_consistency_score"] == 0.0
    assert result["top_corner_grade"] is None
    assert result["highlights"] == []


@pytest.mark.asyncio
async def test_compute_wrapped_year_filter_excludes_wrong_year() -> None:
    """Sessions from a different year are excluded from the aggregation."""
    sd_2024 = _make_session_data(session_id="a")
    sd_2024.snapshot.session_date_parsed = datetime(2024, 3, 1)
    sd_2026 = _make_session_data(session_id="b")
    sd_2026.snapshot.session_date_parsed = datetime(2026, 3, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd_2024, sd_2026]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["total_sessions"] == 0


# ---------------------------------------------------------------------------
# compute_wrapped -- single session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_wrapped_single_session_basics() -> None:
    """Single session with track data produces correct aggregation."""
    sd = _make_session_data(
        session_id="s1",
        track_name="Barber",
        n_laps=8,
        avg_lap_time_s=96.0,
        consistency_score=78.0,
        track_len_m=3700.0,
    )
    sd.snapshot.session_date_parsed = datetime(2025, 5, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["year"] == 2025
    assert result["total_sessions"] == 1
    assert result["total_laps"] == 8
    assert result["tracks_visited"] == ["Barber"]
    assert result["total_distance_km"] == pytest.approx(29.6, abs=0.1)
    assert result["total_track_time_hours"] == pytest.approx(0.2, abs=0.1)


@pytest.mark.asyncio
async def test_compute_wrapped_single_session_no_improvement_field() -> None:
    """Single-session year has no biggest improvement (requires 2+ sessions per track)."""
    sd = _make_session_data(session_id="s1")
    sd.snapshot.session_date_parsed = datetime(2025, 1, 10)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["biggest_improvement_track"] is None
    assert result["biggest_improvement_s"] is None


@pytest.mark.asyncio
async def test_compute_wrapped_single_session_highlights_basic_stats() -> None:
    """Highlights list contains the four basic stat entries for a single session."""
    sd = _make_session_data(session_id="s1")
    sd.snapshot.session_date_parsed = datetime(2025, 3, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    labels = [h["label"] for h in result["highlights"]]
    assert "Total Laps" in labels
    assert "Distance Covered" in labels
    assert "Track Time" in labels
    assert "Tracks Visited" in labels
    assert "Biggest Improvement" not in labels


# ---------------------------------------------------------------------------
# compute_wrapped -- improvement detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_wrapped_biggest_improvement_detected() -> None:
    """Two sessions on same track, first has higher lap time -> improvement detected."""
    sd_first = _make_session_data(
        session_id="s1",
        track_name="Road Atlanta",
        best_lap_time_s=100.0,
    )
    sd_first.snapshot.session_date_parsed = datetime(2025, 3, 1)

    sd_last = _make_session_data(
        session_id="s2",
        track_name="Road Atlanta",
        best_lap_time_s=95.0,
    )
    sd_last.snapshot.session_date_parsed = datetime(2025, 9, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd_first, sd_last]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["biggest_improvement_track"] == "Road Atlanta"
    assert result["biggest_improvement_s"] == pytest.approx(5.0, abs=0.01)


@pytest.mark.asyncio
async def test_compute_wrapped_biggest_improvement_selects_largest_delta() -> None:
    """When multiple tracks have improvements, the largest delta wins."""
    a1 = _make_session_data(session_id="a1", track_name="Track A", best_lap_time_s=90.0)
    a1.snapshot.session_date_parsed = datetime(2025, 1, 1)
    a2 = _make_session_data(session_id="a2", track_name="Track A", best_lap_time_s=87.0)
    a2.snapshot.session_date_parsed = datetime(2025, 6, 1)

    b1 = _make_session_data(session_id="b1", track_name="Track B", best_lap_time_s=105.0)
    b1.snapshot.session_date_parsed = datetime(2025, 2, 1)
    b2 = _make_session_data(session_id="b2", track_name="Track B", best_lap_time_s=97.0)
    b2.snapshot.session_date_parsed = datetime(2025, 8, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [a1, a2, b1, b2]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["biggest_improvement_track"] == "Track B"
    assert result["biggest_improvement_s"] == pytest.approx(8.0, abs=0.01)


@pytest.mark.asyncio
async def test_compute_wrapped_no_improvement_highlight_when_regressed() -> None:
    """Regressed lap time: delta is negative so no improvement highlight is shown."""
    sd_first = _make_session_data(session_id="s1", track_name="Circuit X", best_lap_time_s=88.0)
    sd_first.snapshot.session_date_parsed = datetime(2025, 1, 1)
    sd_last = _make_session_data(session_id="s2", track_name="Circuit X", best_lap_time_s=91.0)
    sd_last.snapshot.session_date_parsed = datetime(2025, 7, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd_first, sd_last]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    labels = [h["label"] for h in result["highlights"]]
    assert "Biggest Improvement" not in labels


@pytest.mark.asyncio
async def test_compute_wrapped_improvement_highlight_appended() -> None:
    """Positive improvement is included in highlights with achievement category."""
    sd_first = _make_session_data(session_id="s1", track_name="Spa", best_lap_time_s=130.0)
    sd_first.snapshot.session_date_parsed = datetime(2025, 4, 1)
    sd_last = _make_session_data(session_id="s2", track_name="Spa", best_lap_time_s=127.5)
    sd_last.snapshot.session_date_parsed = datetime(2025, 10, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd_first, sd_last]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    improvement = next(h for h in result["highlights"] if h["label"] == "Biggest Improvement")
    assert improvement["category"] == "achievement"
    assert "2.50s" in improvement["value"]
    assert "Spa" in improvement["value"]


# ---------------------------------------------------------------------------
# compute_wrapped -- multiple tracks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_wrapped_multiple_tracks_counted() -> None:
    """Sessions on different tracks are all counted and listed."""
    tracks = ["Barber", "Road Atlanta", "VIR"]
    sessions = []
    for i, track in enumerate(tracks):
        sd = _make_session_data(session_id=f"s{i}", track_name=track, n_laps=3)
        sd.snapshot.session_date_parsed = datetime(2025, i + 1, 10)
        sessions.append(sd)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = sessions
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["total_sessions"] == 3
    assert set(result["tracks_visited"]) == set(tracks)


# ---------------------------------------------------------------------------
# compute_wrapped -- distance and time computation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_wrapped_distance_computed_from_lap_df() -> None:
    """Distance uses track length from the best-lap DataFrame."""
    sd = _make_session_data(n_laps=6, track_len_m=4500.0)
    sd.snapshot.session_date_parsed = datetime(2025, 7, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["total_distance_km"] == pytest.approx(27.0, abs=0.1)


@pytest.mark.asyncio
async def test_compute_wrapped_distance_zero_when_no_lap_df() -> None:
    """Distance contribution is zero when resampled_laps has no best-lap entry."""
    sd = _make_session_data(n_laps=4)
    sd.snapshot.session_date_parsed = datetime(2025, 2, 1)
    sd.processed.resampled_laps = {}

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["total_distance_km"] == 0.0


@pytest.mark.asyncio
async def test_compute_wrapped_time_computed_from_avg_lap_time() -> None:
    """Track time uses avg_lap_time_s x n_laps, not best_lap_time_s."""
    sd = _make_session_data(n_laps=30, avg_lap_time_s=120.0)
    sd.snapshot.session_date_parsed = datetime(2025, 8, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["total_track_time_hours"] == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_compute_wrapped_distance_uses_last_row_of_lap_distance() -> None:
    """Track length is taken from the last row of lap_distance_m (iloc[-1])."""
    sd = _make_session_data(n_laps=2)
    sd.snapshot.session_date_parsed = datetime(2025, 4, 1)
    df = pd.DataFrame({"lap_distance_m": [0.0, 1000.0, 3000.0, 5000.0]})
    sd.processed.resampled_laps = {sd.processed.best_lap: df}

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["total_distance_km"] == pytest.approx(10.0, abs=0.1)


# ---------------------------------------------------------------------------
# compute_wrapped -- coaching grades and personality
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_wrapped_coaching_grades_aggregated() -> None:
    """Grade counts aggregate across all sessions with coaching reports."""
    sd1 = _make_session_data(session_id="s1")
    sd1.snapshot.session_date_parsed = datetime(2025, 1, 1)
    sd2 = _make_session_data(session_id="s2")
    sd2.snapshot.session_date_parsed = datetime(2025, 2, 1)

    grades_s1 = [_make_corner_grade(1, braking="A", trail_braking="A", throttle="A")]
    grades_s2 = [_make_corner_grade(2, braking="A", trail_braking="A", throttle="A")]
    report_s1 = _make_coaching_report(grades_s1)
    report_s2 = _make_coaching_report(grades_s2)

    async def _get_report(session_id: str) -> MagicMock:
        return report_s1 if session_id == "s1" else report_s2

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch("backend.api.services.wrapped.get_any_coaching_report", side_effect=_get_report),
    ):
        mock_store.list_sessions.return_value = [sd1, sd2]
        result = await compute_wrapped(2025)

    assert result["personality"] in (
        "The Late Braker",
        "The Smooth Operator",
        "The Throttle Master",
        "The Machine",
    )


@pytest.mark.asyncio
async def test_compute_wrapped_top_corner_grade_a_wins() -> None:
    """top_corner_grade is 'A' when any corner has an A in any dimension."""
    sd = _make_session_data(session_id="s1")
    sd.snapshot.session_date_parsed = datetime(2025, 5, 1)

    report = _make_coaching_report(
        [_make_corner_grade(1, braking="B", trail_braking="C", throttle="A")]
    )

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = report
        result = await compute_wrapped(2025)

    assert result["top_corner_grade"] == "A"


@pytest.mark.asyncio
async def test_compute_wrapped_top_corner_grade_b_when_no_a() -> None:
    """top_corner_grade is 'B' when best grades are B (no A present)."""
    sd = _make_session_data(session_id="s1")
    sd.snapshot.session_date_parsed = datetime(2025, 5, 1)

    report = _make_coaching_report(
        [_make_corner_grade(1, braking="B", trail_braking="B", throttle="C")]
    )

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = report
        result = await compute_wrapped(2025)

    assert result["top_corner_grade"] == "B"


@pytest.mark.asyncio
async def test_compute_wrapped_top_corner_grade_none_without_coaching() -> None:
    """top_corner_grade is None when no coaching reports exist."""
    sd = _make_session_data(session_id="s1")
    sd.snapshot.session_date_parsed = datetime(2025, 5, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["top_corner_grade"] is None


@pytest.mark.asyncio
async def test_compute_wrapped_personality_braking_with_coaching() -> None:
    """Dominant braking A grades across sessions -> The Late Braker personality."""
    sessions = [_make_session_data(session_id=f"s{i}", consistency_score=70.0) for i in range(3)]
    for i, sd in enumerate(sessions):
        sd.snapshot.session_date_parsed = datetime(2025, i + 1, 1)

    braking_heavy_grades = [
        _make_corner_grade(c, braking="A", trail_braking="C", throttle="D") for c in range(1, 6)
    ]
    report = _make_coaching_report(braking_heavy_grades)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = sessions
        mock_cr.return_value = report
        result = await compute_wrapped(2025)

    assert result["personality"] == "The Late Braker"


@pytest.mark.asyncio
async def test_compute_wrapped_sessions_no_coaching_reports() -> None:
    """Sessions without coaching reports still produce valid wrapped data."""
    sd = _make_session_data(n_laps=10)
    sd.snapshot.session_date_parsed = datetime(2025, 6, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["total_sessions"] == 1
    assert result["total_laps"] == 10
    assert result["personality"] in (
        "The Machine",
        "The Track Day Warrior",
        "The Late Braker",
        "The Smooth Operator",
        "The Throttle Master",
    )


# ---------------------------------------------------------------------------
# compute_wrapped -- best consistency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_wrapped_best_consistency_taken_from_max() -> None:
    """best_consistency_score is the maximum across all year sessions."""
    sessions = []
    for i, score in enumerate([65.0, 82.0, 71.0]):
        sd = _make_session_data(session_id=f"s{i}", consistency_score=score)
        sd.snapshot.session_date_parsed = datetime(2025, i + 1, 1)
        sessions.append(sd)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = sessions
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["best_consistency_score"] == pytest.approx(82.0, abs=0.1)


# ---------------------------------------------------------------------------
# compute_wrapped -- return value structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_wrapped_return_value_is_rounded() -> None:
    """Distance and time values are rounded in the return dict."""
    sd = _make_session_data(n_laps=7, avg_lap_time_s=93.7, track_len_m=4235.0)
    sd.snapshot.session_date_parsed = datetime(2025, 9, 1)

    with (
        patch("backend.api.services.wrapped.session_store") as mock_store,
        patch(
            "backend.api.services.wrapped.get_any_coaching_report", new_callable=AsyncMock
        ) as mock_cr,
    ):
        mock_store.list_sessions.return_value = [sd]
        mock_cr.return_value = None
        result = await compute_wrapped(2025)

    assert result["total_distance_km"] == round(result["total_distance_km"], 1)
    assert result["total_track_time_hours"] == round(result["total_track_time_hours"], 1)

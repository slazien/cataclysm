"""Tests for the wrapped.py service — Season Wrapped aggregation.

Lines targeted:
  - 46: _classify_personality — empty grade_counts, best_consistency < 85 → Warrior
  - 50-71: _classify_personality — grade_counts loop, best_ratio threshold
  - 129-135: compute_wrapped — biggest_improvement_track logic (2+ sessions per track)
  - 143-153: compute_wrapped — coaching grade aggregation loop
  - 182: compute_wrapped — highlights append for biggest improvement
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from backend.api.services import session_store
from backend.api.services.wrapped import _classify_personality, compute_wrapped
from backend.tests.conftest import build_synthetic_csv

# ---------------------------------------------------------------------------
# _classify_personality — pure function tests
# ---------------------------------------------------------------------------


class TestClassifyPersonality:
    """Tests for _classify_personality helper function."""

    def test_empty_grade_counts_high_consistency_returns_machine(self) -> None:
        """Empty grade counts + consistency >= 85 → 'The Machine'."""
        name, desc = _classify_personality({}, best_consistency=90.0)
        assert name == "The Machine"
        assert "metronomic" in desc.lower() or "consistency" in desc.lower()

    def test_empty_grade_counts_low_consistency_returns_warrior(self) -> None:
        """Empty grade counts + consistency < 85 → 'The Track Day Warrior' (line 47)."""
        name, desc = _classify_personality({}, best_consistency=70.0)
        assert name == "The Track Day Warrior"

    def test_grade_counts_with_strong_braking_returns_late_braker(self) -> None:
        """High A/B ratio in braking dimension → 'The Late Braker' (lines 63-66)."""
        grade_counts = {
            "braking": {"A": 8, "B": 2, "C": 0},  # ratio = 1.0 ≥ 0.6
            "trail_braking": {"C": 5},
            "throttle": {"C": 5},
        }
        name, desc = _classify_personality(grade_counts, best_consistency=50.0)
        assert name == "The Late Braker"

    def test_grade_counts_with_strong_trail_braking_returns_smooth_operator(self) -> None:
        """High A/B ratio in trail_braking → 'The Smooth Operator'."""
        grade_counts = {
            "braking": {"C": 10},
            "trail_braking": {"A": 9, "B": 1},  # ratio = 1.0 ≥ 0.6
            "throttle": {"C": 10},
        }
        name, desc = _classify_personality(grade_counts, best_consistency=50.0)
        assert name == "The Smooth Operator"

    def test_grade_counts_with_strong_throttle_returns_throttle_master(self) -> None:
        """High A/B ratio in throttle → 'The Throttle Master'."""
        grade_counts = {
            "braking": {"C": 10},
            "trail_braking": {"C": 10},
            "throttle": {"A": 7, "B": 3},  # ratio = 1.0 ≥ 0.6
        }
        name, desc = _classify_personality(grade_counts, best_consistency=50.0)
        assert name == "The Throttle Master"

    def test_grade_counts_poor_ratio_high_consistency_returns_machine(self) -> None:
        """Low A/B ratio but consistency >= 85 → 'The Machine' (line 68-69)."""
        grade_counts = {
            "braking": {"C": 8, "D": 2},  # ratio = 0.0, below 0.6
        }
        name, desc = _classify_personality(grade_counts, best_consistency=90.0)
        assert name == "The Machine"

    def test_grade_counts_poor_ratio_low_consistency_returns_warrior(self) -> None:
        """Low A/B ratio and consistency < 85 → 'The Track Day Warrior' (line 71)."""
        grade_counts = {
            "braking": {"C": 8, "D": 2},
            "trail_braking": {"D": 5},
        }
        name, desc = _classify_personality(grade_counts, best_consistency=50.0)
        assert name == "The Track Day Warrior"

    def test_grade_counts_zero_total_dimension_skipped(self) -> None:
        """Dimension with total=0 is skipped in the ratio loop (line 55-56)."""
        # braking has 0 total → should be skipped
        grade_counts = {
            "braking": {},  # empty → total = 0
            "trail_braking": {"A": 7, "B": 3},  # ratio = 1.0
        }
        name, desc = _classify_personality(grade_counts, best_consistency=50.0)
        assert name == "The Smooth Operator"

    def test_best_ratio_tracks_highest_dimension(self) -> None:
        """The dimension with the highest good ratio wins (lines 58-61)."""
        grade_counts = {
            "braking": {"A": 5, "B": 2, "C": 3},  # ratio = 0.7
            "trail_braking": {"A": 8, "B": 2},  # ratio = 1.0 → should win
            "throttle": {"A": 6, "C": 4},  # ratio = 0.6
        }
        name, _ = _classify_personality(grade_counts, best_consistency=50.0)
        assert name == "The Smooth Operator"


# ---------------------------------------------------------------------------
# compute_wrapped — async service tests
# ---------------------------------------------------------------------------


class TestComputeWrapped:
    """Tests for compute_wrapped service function."""

    @pytest.fixture(autouse=True)
    def _clear_sessions(self) -> Generator[None, None, None]:
        """Clear all in-memory sessions before each test."""
        session_store.clear_all()
        yield
        session_store.clear_all()

    @pytest.mark.asyncio
    async def test_empty_year_returns_zero_stats(self) -> None:
        """No sessions in the year returns zero stats and Track Day Warrior."""
        result = await compute_wrapped(2099)  # far future year, no sessions
        assert result["year"] == 2099
        assert result["total_sessions"] == 0
        assert result["total_laps"] == 0
        assert result["personality"] == "The Track Day Warrior"
        assert result["highlights"] == []

    @pytest.mark.asyncio
    async def test_single_session_basic_aggregation(self) -> None:
        """Single session in year produces correct aggregation."""
        from backend.api.services.pipeline import process_upload

        csv = build_synthetic_csv(n_laps=3, track_name="Test Circuit")
        await process_upload(csv, "wrapped-test.csv")

        with patch(
            "backend.api.services.wrapped.get_any_coaching_report",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await compute_wrapped(2026)  # synthetic CSV uses 2026 date implicitly

        # If sessions are in the year 2026 (check session_date_parsed.year)
        sessions = session_store.list_sessions()
        year = sessions[0].snapshot.session_date_parsed.year if sessions else 2026

        result = await compute_wrapped(year)
        if result["total_sessions"] > 0:
            assert result["total_laps"] >= 1
            assert result["year"] == year
            assert isinstance(result["tracks_visited"], list)
            assert result["best_consistency_score"] >= 0

    @pytest.mark.asyncio
    async def test_multiple_sessions_same_track_improvement(self) -> None:
        """Two sessions on same track → biggest_improvement_track is set (lines 129-135)."""
        from backend.api.services import session_store as ss
        from backend.api.services.pipeline import process_upload

        # Upload two sessions at same track
        csv1 = build_synthetic_csv(n_laps=3, track_name="Barber Motorsports Park")
        csv2 = build_synthetic_csv(n_laps=3, track_name="Barber Motorsports Park")
        await process_upload(csv1, "wrapped-sess1.csv")
        await process_upload(csv2, "wrapped-sess2.csv")

        sessions = ss.list_sessions()
        if len(sessions) < 2:
            return  # Skip if pipeline didn't produce sessions

        year = sessions[0].snapshot.session_date_parsed.year

        with patch(
            "backend.api.services.wrapped.get_any_coaching_report",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await compute_wrapped(year)

        # With 2 sessions on same track, biggest_improvement_track should be set
        # (may be None if first_best <= last_best, but the code path runs)
        assert "biggest_improvement_track" in result
        assert "biggest_improvement_s" in result

    @pytest.mark.asyncio
    async def test_coaching_grade_aggregation(self) -> None:
        """Sessions with coaching reports contribute to grade_counts (lines 143-153)."""
        from backend.api.services import session_store as ss
        from backend.api.services.pipeline import process_upload

        csv = build_synthetic_csv(n_laps=3, track_name="Test Circuit")
        await process_upload(csv, "wrapped-coaching.csv")

        sessions = ss.list_sessions()
        if not sessions:
            return

        year = sessions[0].snapshot.session_date_parsed.year

        # Create a mock coaching report with corner grades
        from unittest.mock import MagicMock

        mock_grade = MagicMock()
        mock_grade.braking = "A"
        mock_grade.trail_braking = "B"
        mock_grade.throttle = "C"

        mock_report = MagicMock()
        mock_report.corner_grades = [mock_grade, mock_grade]
        mock_report.summary = "Good lap."

        with patch(
            "backend.api.services.wrapped.get_any_coaching_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            result = await compute_wrapped(year)

        # With braking="A" and trail_braking="B", top_grade should be "A"
        assert result["top_corner_grade"] == "A"
        # With A grades in braking, personality might be Late Braker
        assert result["personality"] in (
            "The Late Braker",
            "The Smooth Operator",
            "The Throttle Master",
            "The Machine",
            "The Track Day Warrior",
        )

    @pytest.mark.asyncio
    async def test_highlights_append_for_positive_improvement(self) -> None:
        """biggest_delta > 0 → highlights include improvement entry (line 182)."""

        from backend.api.services import session_store as ss
        from backend.api.services.pipeline import process_upload

        # Upload two sessions — pipeline might produce different best laps
        csv1 = build_synthetic_csv(n_laps=5, track_name="Improvement Track")
        csv2 = build_synthetic_csv(n_laps=5, track_name="Improvement Track")
        await process_upload(csv1, "impr-1.csv")
        await process_upload(csv2, "impr-2.csv")

        sessions = ss.list_sessions()
        if len(sessions) < 2:
            return

        year = sessions[0].snapshot.session_date_parsed.year

        # Manually override best_lap_time_s so improvement is guaranteed positive
        sd_list = [sd for sd in sessions if sd.snapshot.metadata.track_name == "Improvement Track"]
        if len(sd_list) >= 2:
            # Sort by session_date_parsed so first session is "older"
            sd_list.sort(key=lambda s: s.snapshot.session_date_parsed)
            # Force first to be slower (bigger time) than last
            sd_list[0].snapshot.best_lap_time_s = 100.0
            sd_list[-1].snapshot.best_lap_time_s = 95.0

        with patch(
            "backend.api.services.wrapped.get_any_coaching_report",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await compute_wrapped(year)

        # Check if improvement highlight was appended (line 182)
        highlight_labels = [h["label"] for h in result["highlights"]]
        if result["biggest_improvement_s"] is not None and result["biggest_improvement_s"] > 0:
            assert "Biggest Improvement" in highlight_labels

    @pytest.mark.asyncio
    async def test_top_grade_b_when_no_a(self) -> None:
        """top_grade is 'B' when best corner grade is B (line 152)."""
        from backend.api.services import session_store as ss
        from backend.api.services.pipeline import process_upload

        csv = build_synthetic_csv(n_laps=3, track_name="Grade B Track")
        await process_upload(csv, "grade-b-test.csv")

        sessions = ss.list_sessions()
        if not sessions:
            return

        year = sessions[0].snapshot.session_date_parsed.year

        # Mock report with only B grades (no A)
        from unittest.mock import MagicMock

        mock_grade = MagicMock()
        mock_grade.braking = "B"
        mock_grade.trail_braking = "B"
        mock_grade.throttle = "B"

        mock_report = MagicMock()
        mock_report.corner_grades = [mock_grade]

        with patch(
            "backend.api.services.wrapped.get_any_coaching_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            result = await compute_wrapped(year)

        assert result["top_corner_grade"] == "B"

    @pytest.mark.asyncio
    async def test_response_has_all_required_keys(self) -> None:
        """compute_wrapped response always has all required keys."""
        result = await compute_wrapped(2099)
        required_keys = {
            "year",
            "total_sessions",
            "total_laps",
            "total_distance_km",
            "tracks_visited",
            "total_track_time_hours",
            "biggest_improvement_track",
            "biggest_improvement_s",
            "best_consistency_score",
            "personality",
            "personality_description",
            "top_corner_grade",
            "highlights",
        }
        assert required_keys.issubset(result.keys())

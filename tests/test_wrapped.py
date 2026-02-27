"""Tests for Season Wrapped service."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.api.services.wrapped import _classify_personality, compute_wrapped


def test_classify_personality_empty_grades() -> None:
    """No coaching data with low consistency defaults to Warrior."""
    name, _ = _classify_personality({}, 50.0)
    assert name == "The Track Day Warrior"


def test_classify_personality_high_consistency() -> None:
    """High consistency with no grades → The Machine."""
    name, _ = _classify_personality({}, 90.0)
    assert name == "The Machine"


def test_classify_personality_braking_dominant() -> None:
    """Majority A braking grades → The Late Braker."""
    grade_counts = {
        "braking": {"A": 10, "B": 3, "C": 1},
        "trail_braking": {"B": 5, "C": 9},
        "throttle": {"C": 8, "D": 6},
    }
    name, _ = _classify_personality(grade_counts, 70.0)
    assert name == "The Late Braker"


def test_classify_personality_throttle_dominant() -> None:
    """Majority A/B throttle → The Throttle Master."""
    grade_counts = {
        "braking": {"C": 10},
        "trail_braking": {"C": 10},
        "throttle": {"A": 8, "B": 4, "C": 2},
    }
    name, _ = _classify_personality(grade_counts, 70.0)
    assert name == "The Throttle Master"


def test_classify_personality_trail_braking_dominant() -> None:
    """Majority A/B trail braking → The Smooth Operator."""
    grade_counts = {
        "braking": {"C": 10},
        "trail_braking": {"A": 6, "B": 4, "C": 2},
        "throttle": {"C": 10},
    }
    name, _ = _classify_personality(grade_counts, 70.0)
    assert name == "The Smooth Operator"


def test_classify_personality_no_clear_winner() -> None:
    """No dimension has 60%+ A/B → fallback based on consistency."""
    grade_counts = {
        "braking": {"A": 2, "C": 8},
        "trail_braking": {"A": 2, "C": 8},
        "throttle": {"A": 2, "C": 8},
    }
    name, _ = _classify_personality(grade_counts, 90.0)
    assert name == "The Machine"


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

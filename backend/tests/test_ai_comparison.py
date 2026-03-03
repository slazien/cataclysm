"""Tests for the AI comparison narrative endpoint and helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_ai_comparison_returns_cached() -> None:
    """If ai_comparison_text already exists, return it without calling Claude."""
    from backend.api.routers.sharing import _get_or_generate_ai_comparison

    mock_report = MagicMock()
    mock_report.ai_comparison_text = "Cached comparison text"
    mock_report.report_json = {}

    result = await _get_or_generate_ai_comparison(mock_report, MagicMock())
    assert result == "Cached comparison text"


@pytest.mark.asyncio
async def test_ai_comparison_generates_on_miss() -> None:
    """If ai_comparison_text is None, generate via Claude and cache."""
    from backend.api.routers.sharing import _get_or_generate_ai_comparison

    mock_report = MagicMock()
    mock_report.ai_comparison_text = None
    mock_report.report_json = {
        "session_a_best_lap": 88.5,
        "session_b_best_lap": 90.1,
        "corner_deltas": [{"corner_number": 1, "speed_diff_mph": 2.3}],
    }
    mock_db = AsyncMock()

    with patch("backend.api.routers.sharing._call_haiku_comparison") as mock_haiku:
        mock_haiku.return_value = "Alex is faster because..."
        result = await _get_or_generate_ai_comparison(mock_report, mock_db)

    assert result == "Alex is faster because..."
    assert mock_report.ai_comparison_text == "Alex is faster because..."


@pytest.mark.asyncio
async def test_ai_comparison_generates_on_empty_string() -> None:
    """If ai_comparison_text is empty string, treat as miss and regenerate."""
    from backend.api.routers.sharing import _get_or_generate_ai_comparison

    mock_report = MagicMock()
    mock_report.ai_comparison_text = ""
    mock_report.report_json = {
        "session_a_best_lap": 88.5,
        "session_b_best_lap": 90.1,
        "corner_deltas": [],
    }
    mock_db = AsyncMock()

    with patch("backend.api.routers.sharing._call_haiku_comparison") as mock_haiku:
        mock_haiku.return_value = "Generated narrative"
        result = await _get_or_generate_ai_comparison(mock_report, mock_db)

    assert result == "Generated narrative"
    assert mock_report.ai_comparison_text == "Generated narrative"


def test_build_comparison_prompt_format() -> None:
    """Test prompt construction from comparison data."""
    from backend.api.routers.sharing import _build_comparison_prompt

    data: dict[str, object] = {
        "session_a_best_lap": 88.5,
        "session_b_best_lap": 90.1,
        "corner_deltas": [
            {"corner_number": 1, "speed_diff_mph": 2.3},
            {"corner_number": 5, "speed_diff_mph": -1.5},
        ],
    }
    prompt = _build_comparison_prompt(data)
    assert "88.500" in prompt
    assert "90.100" in prompt
    assert "Turn 1" in prompt
    assert "Turn 5" in prompt
    assert "A faster" in prompt
    assert "B faster" in prompt


def test_build_comparison_prompt_no_corners() -> None:
    """Prompt handles empty corner deltas gracefully."""
    from backend.api.routers.sharing import _build_comparison_prompt

    data: dict[str, object] = {
        "session_a_best_lap": 60.0,
        "session_b_best_lap": 62.0,
        "corner_deltas": [],
    }
    prompt = _build_comparison_prompt(data)
    assert "60.000" in prompt
    assert "62.000" in prompt
    assert "-2.000" in prompt  # A is faster


def test_build_comparison_prompt_missing_fields() -> None:
    """Prompt handles missing fields without crashing."""
    from backend.api.routers.sharing import _build_comparison_prompt

    data: dict[str, object] = {}
    prompt = _build_comparison_prompt(data)
    assert "0.000" in prompt  # defaults to 0

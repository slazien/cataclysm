"""Tests for auto-flagging engine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.services.auto_flagging import (
    _PASSING_GRADES,
    ATTENTION_CONSISTENCY_THRESHOLD,
    auto_flag_session,
)


class TestAutoFlagging:
    """Test auto-flagging logic paths."""

    @pytest.mark.asyncio
    async def test_no_session_returns_empty(self) -> None:
        """Missing session returns no flags."""
        mock_db = MagicMock()
        mock_db.get = AsyncMock(return_value=None)

        result = await auto_flag_session(mock_db, "user1", "sess1")
        assert result == []

    @pytest.mark.asyncio
    async def test_attention_flag_low_consistency(self) -> None:
        """Low consistency score triggers attention flag."""
        mock_session = MagicMock()
        mock_session.consistency_score = 30.0
        mock_session.best_lap_time_s = 90.0
        mock_session.track_name = "TestTrack"
        mock_session.user_id = "user1"

        mock_db = MagicMock()
        mock_db.get = AsyncMock(return_value=mock_session)

        # prev_best query
        prev_result = MagicMock()
        prev_result.scalar.return_value = 85.0  # not a PB

        # report query
        report_result = MagicMock()
        report_result.scalar.return_value = None

        mock_db.execute = AsyncMock(side_effect=[prev_result, report_result])
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        result = await auto_flag_session(mock_db, "user1", "sess1")
        assert "attention" in result

    @pytest.mark.asyncio
    async def test_improvement_flag_pb(self) -> None:
        """Personal best triggers improvement flag."""
        mock_session = MagicMock()
        mock_session.consistency_score = 80.0  # above threshold
        mock_session.best_lap_time_s = 85.0
        mock_session.track_name = "TestTrack"
        mock_session.user_id = "user1"

        mock_db = MagicMock()
        mock_db.get = AsyncMock(return_value=mock_session)

        prev_result = MagicMock()
        prev_result.scalar.return_value = 90.0  # 85 < 90, so PB

        report_result = MagicMock()
        report_result.scalar.return_value = None

        mock_db.execute = AsyncMock(side_effect=[prev_result, report_result])
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        result = await auto_flag_session(mock_db, "user1", "sess1")
        assert "improvement" in result

    @pytest.mark.asyncio
    async def test_praise_flag_good_grades(self) -> None:
        """All good corner grades triggers praise flag."""
        mock_session = MagicMock()
        mock_session.consistency_score = 80.0
        mock_session.best_lap_time_s = 90.0
        mock_session.track_name = "TestTrack"
        mock_session.user_id = "user1"

        mock_db = MagicMock()
        mock_db.get = AsyncMock(return_value=mock_session)

        prev_result = MagicMock()
        prev_result.scalar.return_value = 85.0  # not PB

        report_result = MagicMock()
        report_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "braking": "A", "trail_braking": "B+"},
                {"corner": 2, "braking": "B", "trail_braking": "A-"},
            ],
            "patterns": [],
        }

        mock_db.execute = AsyncMock(side_effect=[prev_result, report_result])
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        result = await auto_flag_session(mock_db, "user1", "sess1")
        assert "praise" in result

    def test_passing_grades_set(self) -> None:
        """Verify passing grades include expected values."""
        assert "A+" in _PASSING_GRADES
        assert "B" in _PASSING_GRADES
        assert "C" not in _PASSING_GRADES

    def test_attention_threshold(self) -> None:
        """Verify attention threshold is reasonable."""
        assert ATTENTION_CONSISTENCY_THRESHOLD == 50

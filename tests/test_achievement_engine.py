"""Tests for achievement engine seed data and grade checking."""

from __future__ import annotations

import pytest

from backend.api.services.achievement_engine import SEED_ACHIEVEMENTS, _check_all_grades


class TestSeedAchievements:
    """Validate the seed achievement definitions."""

    def test_not_empty(self) -> None:
        assert len(SEED_ACHIEVEMENTS) > 0

    def test_ids_unique(self) -> None:
        ids = [a["id"] for a in SEED_ACHIEVEMENTS]
        assert len(ids) == len(set(ids))

    def test_tiers_valid(self) -> None:
        valid_tiers = {"bronze", "silver", "gold"}
        for a in SEED_ACHIEVEMENTS:
            assert a["tier"] in valid_tiers, f"{a['id']} has invalid tier {a['tier']}"


class TestCheckAllGrades:
    """Test the _check_all_grades helper (no DB required for some paths)."""

    @pytest.mark.asyncio
    async def test_no_session_returns_false(self) -> None:
        """None session_id should return False."""
        result = await _check_all_grades(None, None, "braking", {"A"})  # type: ignore[arg-type]
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_corner_grades(self) -> None:
        """Empty corner grades should return False."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = {"corner_grades": []}
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess1", "braking", {"A"})
        assert result is False

    @pytest.mark.asyncio
    async def test_all_a_braking(self) -> None:
        """All A grades should return True."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "braking": "A"},
                {"corner": 2, "braking": "A+"},
                {"corner": 3, "braking": "A"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess1", "braking", {"A", "A+"})
        assert result is True

    @pytest.mark.asyncio
    async def test_mixed_grades_fails(self) -> None:
        """Mixed grades with a C should return False for A-only."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "braking": "A"},
                {"corner": 2, "braking": "C"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess1", "braking", {"A", "A+"})
        assert result is False

    @pytest.mark.asyncio
    async def test_b_plus_trail_braking(self) -> None:
        """B+ and better trail braking should pass."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = {
            "corner_grades": [
                {"corner": 1, "trail_braking": "B+"},
                {"corner": 2, "trail_braking": "A-"},
            ]
        }
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await _check_all_grades(mock_db, "sess1", "trail_braking", {"A+", "A", "A-", "B+"})
        assert result is True

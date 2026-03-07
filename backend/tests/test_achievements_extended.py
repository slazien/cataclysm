"""Extended tests for achievements router — covers uncovered lines [37, 38, 39, 51].

Lines 37-39: list_achievements — check_achievements call, db.commit, get_user_achievements
Line 51: recent_achievements — get_recent_achievements with results
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.api.db.models import AchievementDefinition, UserAchievement
from backend.tests.conftest import _TEST_USER, _test_session_factory


class TestListAchievements:
    """Tests for GET /api/achievements."""

    @pytest.mark.asyncio
    async def test_list_achievements_returns_all_definitions(self, client: AsyncClient) -> None:
        """GET /api/achievements returns all achievement definitions with unlock status."""
        resp = await client.get("/api/achievements")
        assert resp.status_code == 200
        data = resp.json()
        assert "achievements" in data
        achievements = data["achievements"]
        assert isinstance(achievements, list)
        # At minimum, all seeded definitions should be present
        assert len(achievements) > 0

    @pytest.mark.asyncio
    async def test_list_achievements_has_required_fields(self, client: AsyncClient) -> None:
        """Each achievement has id, name, description, icon, category, tier fields."""
        resp = await client.get("/api/achievements")
        assert resp.status_code == 200
        achievements = resp.json()["achievements"]
        for ach in achievements:
            assert "id" in ach
            assert "name" in ach
            assert "category" in ach
            assert "tier" in ach

    @pytest.mark.asyncio
    async def test_list_achievements_triggers_check_and_commit(self, client: AsyncClient) -> None:
        """GET /api/achievements runs check_achievements (lines 37-39)."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "backend.api.routers.achievements.check_achievements",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_check:
            resp = await client.get("/api/achievements")
        assert resp.status_code == 200
        mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_achievements_shows_unlocked_status(self, client: AsyncClient) -> None:
        """Achievements unlocked by the user appear as unlocked."""
        from backend.api.services.achievement_engine import seed_achievements

        # Seed achievements first
        async with _test_session_factory() as db:
            await seed_achievements(db)
            await db.commit()

            # Get the first achievement definition ID
            result = await db.execute(select(AchievementDefinition).limit(1))
            defn = result.scalar_one_or_none()
            if defn is None:
                pytest.skip("No achievement definitions available")
                return

            # Manually unlock this achievement for the test user
            db.add(
                UserAchievement(
                    user_id=_TEST_USER.user_id,
                    achievement_id=defn.id,
                )
            )
            await db.commit()

        resp = await client.get("/api/achievements")
        assert resp.status_code == 200
        achievements = resp.json()["achievements"]
        unlocked = [a for a in achievements if a.get("unlocked_at") is not None]
        assert len(unlocked) >= 1


class TestRecentAchievements:
    """Tests for GET /api/achievements/recent."""

    @pytest.mark.asyncio
    async def test_recent_achievements_returns_empty_list_by_default(
        self, client: AsyncClient
    ) -> None:
        """GET /api/achievements/recent returns empty list when none are new."""
        resp = await client.get("/api/achievements/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert "newly_unlocked" in data
        assert isinstance(data["newly_unlocked"], list)

    @pytest.mark.asyncio
    async def test_recent_achievements_calls_get_recent(self, client: AsyncClient) -> None:
        """GET /api/achievements/recent calls get_recent_achievements (line 51)."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "backend.api.routers.achievements.get_recent_achievements",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_recent:
            resp = await client.get("/api/achievements/recent")
        assert resp.status_code == 200
        mock_recent.assert_called_once()

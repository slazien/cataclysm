"""Integration tests for the /api/achievements router.

Uses the `client` fixture to make real HTTP requests through the full router →
service → DB path.  No service functions are mocked.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.api.db.models import AchievementDefinition, UserAchievement
from backend.api.services.achievement_engine import SEED_ACHIEVEMENTS

# Imported to access the session factory used by the test DB override
from backend.tests.conftest import _test_session_factory  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# GET /api/achievements — list all achievements with unlock status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_achievements_returns_all_seed_definitions(client: AsyncClient) -> None:
    """GET /api/achievements returns a row for every seed achievement definition."""
    resp = await client.get("/api/achievements")
    assert resp.status_code == 200
    data = resp.json()
    assert "achievements" in data
    assert len(data["achievements"]) == len(SEED_ACHIEVEMENTS)


@pytest.mark.asyncio
async def test_list_achievements_none_unlocked_initially(client: AsyncClient) -> None:
    """For a fresh user every achievement has unlocked=False."""
    resp = await client.get("/api/achievements")
    assert resp.status_code == 200
    unlocked = [a for a in resp.json()["achievements"] if a["unlocked"]]
    assert unlocked == []


@pytest.mark.asyncio
async def test_list_achievements_response_shape(client: AsyncClient) -> None:
    """Each achievement entry has all required AchievementSchema fields."""
    resp = await client.get("/api/achievements")
    assert resp.status_code == 200
    for entry in resp.json()["achievements"]:
        assert "id" in entry
        assert "name" in entry
        assert "description" in entry
        assert "criteria_type" in entry
        assert "criteria_value" in entry
        assert "tier" in entry
        assert "icon" in entry
        assert "unlocked" in entry


@pytest.mark.asyncio
async def test_list_achievements_shows_unlocked_when_manually_granted(
    client: AsyncClient,
) -> None:
    """An achievement that has been manually inserted into user_achievements shows as unlocked."""
    from datetime import UTC, datetime

    async with _test_session_factory() as session:
        # Ensure definitions exist first by calling the endpoint once
        pass

    # Trigger seeding by calling the endpoint
    await client.get("/api/achievements")

    # Manually unlock the first_session achievement in the test DB
    async with _test_session_factory() as session:
        # Verify the definition row was seeded
        result = await session.execute(
            select(AchievementDefinition).where(AchievementDefinition.id == "first_session")
        )
        defn = result.scalar_one_or_none()
        assert defn is not None, "Seed achievement 'first_session' not found in DB"

        session.add(
            UserAchievement(
                user_id="test-user-123",
                achievement_id="first_session",
                session_id=None,
                unlocked_at=datetime.now(UTC),
                is_new=True,
            )
        )
        await session.commit()

    # Now the endpoint should show it as unlocked
    resp = await client.get("/api/achievements")
    assert resp.status_code == 200
    achievements = {a["id"]: a for a in resp.json()["achievements"]}
    assert achievements["first_session"]["unlocked"] is True


# ---------------------------------------------------------------------------
# GET /api/achievements/recent — newly unlocked achievements
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recent_achievements_empty_initially(client: AsyncClient) -> None:
    """GET /api/achievements/recent returns empty list for a fresh user."""
    resp = await client.get("/api/achievements/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert "newly_unlocked" in data
    assert data["newly_unlocked"] == []


@pytest.mark.asyncio
async def test_recent_achievements_returns_new_badge_then_clears(
    client: AsyncClient,
) -> None:
    """A newly unlocked achievement appears in /recent once, then is cleared (is_new=False)."""
    from datetime import UTC, datetime

    # Seed definitions
    await client.get("/api/achievements")

    async with _test_session_factory() as session:
        session.add(
            UserAchievement(
                user_id="test-user-123",
                achievement_id="first_session",
                session_id=None,
                unlocked_at=datetime.now(UTC),
                is_new=True,
            )
        )
        await session.commit()

    # First call — should return the achievement
    resp1 = await client.get("/api/achievements/recent")
    assert resp1.status_code == 200
    unlocked = resp1.json()["newly_unlocked"]
    assert len(unlocked) == 1
    assert unlocked[0]["id"] == "first_session"

    # Second call — is_new was flipped to False; should now be empty
    resp2 = await client.get("/api/achievements/recent")
    assert resp2.status_code == 200
    assert resp2.json()["newly_unlocked"] == []


@pytest.mark.asyncio
async def test_recent_achievements_response_shape(client: AsyncClient) -> None:
    """Each entry in newly_unlocked has all AchievementSchema fields."""
    from datetime import UTC, datetime

    await client.get("/api/achievements")

    async with _test_session_factory() as session:
        session.add(
            UserAchievement(
                user_id="test-user-123",
                achievement_id="track_rat_10",
                session_id=None,
                unlocked_at=datetime.now(UTC),
                is_new=True,
            )
        )
        await session.commit()

    resp = await client.get("/api/achievements/recent")
    assert resp.status_code == 200
    entry = resp.json()["newly_unlocked"][0]
    assert entry["id"] == "track_rat_10"
    assert entry["unlocked"] is True
    assert entry["unlocked_at"] is not None

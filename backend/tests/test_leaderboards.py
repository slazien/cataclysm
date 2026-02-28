"""Endpoint tests for the corner leaderboard router."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import CornerRecord, Session, User


@pytest_asyncio.fixture
async def _seed_leaderboard_data(client: AsyncClient) -> None:
    """Seed users, sessions, and corner records for leaderboard tests."""
    from backend.api.db.database import get_db
    from backend.api.main import app

    db_gen = app.dependency_overrides[get_db]()
    db: AsyncSession = await db_gen.__anext__()

    try:
        db.add(
            User(
                id="user-rival",
                email="rival@test.com",
                name="Rival Driver",
                leaderboard_opt_in=True,
            )
        )
        await db.flush()

        # Opt in the default test user
        result = await db.execute(select(User).where(User.id == "test-user-123"))
        user = result.scalar_one()
        user.leaderboard_opt_in = True
        await db.flush()

        # Create sessions
        db.add(
            Session(
                session_id="sess-test-1",
                user_id="test-user-123",
                track_name="Barber Motorsports Park",
                session_date=datetime(2026, 1, 15, tzinfo=UTC),
                file_key="key-1",
            )
        )
        db.add(
            Session(
                session_id="sess-rival-1",
                user_id="user-rival",
                track_name="Barber Motorsports Park",
                session_date=datetime(2026, 2, 10, tzinfo=UTC),
                file_key="key-2",
            )
        )
        await db.flush()

        # Corner records
        db.add(
            CornerRecord(
                user_id="test-user-123",
                session_id="sess-test-1",
                track_name="Barber Motorsports Park",
                corner_number=1,
                min_speed_mps=25.0,
                sector_time_s=4.5,
                lap_number=3,
            )
        )
        db.add(
            CornerRecord(
                user_id="user-rival",
                session_id="sess-rival-1",
                track_name="Barber Motorsports Park",
                corner_number=1,
                min_speed_mps=26.0,
                sector_time_s=4.2,
                lap_number=5,
            )
        )
        await db.commit()
    except Exception:  # noqa: BLE001 — must rollback on any error before re-raising
        await db.rollback()
        raise


@pytest.mark.asyncio
async def test_corner_leaderboard_empty(client: AsyncClient) -> None:
    """GET /api/leaderboards/{track}/corners returns empty for no data."""
    resp = await client.get(
        "/api/leaderboards/Barber Motorsports Park/corners",
        params={"corner": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["track_name"] == "Barber Motorsports Park"
    assert data["corner_number"] == 1
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_corner_leaderboard_with_data(
    client: AsyncClient,
    _seed_leaderboard_data: None,
) -> None:
    """GET /api/leaderboards/{track}/corners returns ranked entries."""
    resp = await client.get(
        "/api/leaderboards/Barber Motorsports Park/corners",
        params={"corner": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 2
    assert data["entries"][0]["user_name"] == "Rival Driver"
    assert data["entries"][0]["sector_time_s"] == 4.2
    assert data["entries"][0]["rank"] == 1
    assert data["entries"][1]["user_name"] == "Test Driver"
    assert data["entries"][1]["rank"] == 2


@pytest.mark.asyncio
async def test_corner_kings_empty(client: AsyncClient) -> None:
    """GET /api/leaderboards/{track}/kings returns empty when no kings."""
    resp = await client.get("/api/leaderboards/Barber Motorsports Park/kings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["kings"] == []


@pytest.mark.asyncio
async def test_opt_in_toggle(client: AsyncClient) -> None:
    """POST /api/leaderboards/opt-in toggles the leaderboard opt-in flag."""
    resp = await client.post("/api/leaderboards/opt-in", json={"opt_in": True})
    assert resp.status_code == 200
    assert resp.json()["leaderboard_opt_in"] is True

    resp = await client.post("/api/leaderboards/opt-in", json={"opt_in": False})
    assert resp.status_code == 200
    assert resp.json()["leaderboard_opt_in"] is False


@pytest.mark.asyncio
async def test_corner_leaderboard_limit(
    client: AsyncClient,
    _seed_leaderboard_data: None,
) -> None:
    """Limit parameter caps the number of returned entries."""
    resp = await client.get(
        "/api/leaderboards/Barber Motorsports Park/corners",
        params={"corner": 1, "limit": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 1


@pytest.mark.asyncio
async def test_corner_leaderboard_wrong_corner(
    client: AsyncClient,
    _seed_leaderboard_data: None,
) -> None:
    """Querying a corner with no records returns empty entries."""
    resp = await client.get(
        "/api/leaderboards/Barber Motorsports Park/corners",
        params={"corner": 99},
    )
    assert resp.status_code == 200
    assert resp.json()["entries"] == []

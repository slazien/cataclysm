"""Integration tests for the /api/leaderboards router.

Uses the `client` fixture to exercise the full router → service → DB path without
mocking any service functions.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.api.db.models import CornerKing, CornerRecord, Session, User
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.main import app
from backend.tests.conftest import _test_session_factory  # type: ignore[attr-defined]

_TEST_USER_ID = "test-user-123"
_TRACK = "Barber Motorsports Park"

# A user_id that does NOT exist in the test database
_GHOST_USER = AuthenticatedUser(
    user_id="ghost-user-404",
    email="ghost@test.com",
    name="Ghost User",
)


# ---------------------------------------------------------------------------
# DB seeding helpers
# ---------------------------------------------------------------------------


async def _seed_session(session_id: str = "sess-001") -> None:
    """Insert a minimal Session row so CornerRecord FKs resolve."""
    async with _test_session_factory() as session:
        session.add(
            Session(
                session_id=session_id,
                user_id=_TEST_USER_ID,
                track_name=_TRACK,
                session_date=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
                file_key="file.csv",
            )
        )
        await session.commit()


async def _seed_corner_record(
    session_id: str = "sess-001",
    corner_number: int = 1,
    sector_time_s: float = 12.5,
    min_speed_mps: float = 18.0,
    opted_in: bool = True,
) -> None:
    """Insert a CornerRecord row (and optionally set user leaderboard_opt_in)."""
    async with _test_session_factory() as session:
        if opted_in:
            result = await session.execute(select(User).where(User.id == _TEST_USER_ID))
            user = result.scalar_one_or_none()
            if user:
                user.leaderboard_opt_in = True

        session.add(
            CornerRecord(
                user_id=_TEST_USER_ID,
                session_id=session_id,
                track_name=_TRACK,
                corner_number=corner_number,
                min_speed_mps=min_speed_mps,
                sector_time_s=sector_time_s,
                lap_number=1,
            )
        )
        await session.commit()


async def _seed_corner_king(corner_number: int = 1, best_time_s: float = 12.5) -> None:
    """Insert a CornerKing row so the king indicator appears in leaderboard results."""
    async with _test_session_factory() as session:
        session.add(
            CornerKing(
                track_name=_TRACK,
                corner_number=corner_number,
                user_id=_TEST_USER_ID,
                best_time_s=best_time_s,
                session_id="sess-001",
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# GET /api/leaderboards/{track}/corners?corner=N — per-corner leaderboard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_corner_leaderboard_empty_when_no_records(client: AsyncClient) -> None:
    """Corner leaderboard returns empty entries list when no records exist."""
    track_encoded = _TRACK.replace(" ", "%20")
    resp = await client.get(f"/api/leaderboards/{track_encoded}/corners?corner=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["track_name"] == _TRACK
    assert data["corner_number"] == 1
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_corner_leaderboard_returns_opted_in_user(client: AsyncClient) -> None:
    """Corner leaderboard includes an opted-in user's record."""
    await _seed_session()
    await _seed_corner_record(corner_number=1, sector_time_s=11.2, opted_in=True)

    track_encoded = _TRACK.replace(" ", "%20")
    resp = await client.get(f"/api/leaderboards/{track_encoded}/corners?corner=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 1
    entry = data["entries"][0]
    assert entry["rank"] == 1
    assert entry["user_name"] == "Test Driver"
    assert abs(entry["sector_time_s"] - 11.2) < 0.001


@pytest.mark.asyncio
async def test_corner_leaderboard_excludes_opted_out_user(client: AsyncClient) -> None:
    """A user who has not opted into leaderboards does not appear in results."""
    await _seed_session()
    # Insert the record but do NOT set leaderboard_opt_in
    await _seed_corner_record(corner_number=1, sector_time_s=10.0, opted_in=False)

    track_encoded = _TRACK.replace(" ", "%20")
    resp = await client.get(f"/api/leaderboards/{track_encoded}/corners?corner=1")
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


@pytest.mark.asyncio
async def test_corner_leaderboard_marks_king(client: AsyncClient) -> None:
    """The leaderboard entry is flagged as is_king when the user is the corner king."""
    await _seed_session()
    await _seed_corner_record(corner_number=1, sector_time_s=11.0, opted_in=True)
    await _seed_corner_king(corner_number=1, best_time_s=11.0)

    track_encoded = _TRACK.replace(" ", "%20")
    resp = await client.get(f"/api/leaderboards/{track_encoded}/corners?corner=1")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["is_king"] is True


@pytest.mark.asyncio
async def test_corner_leaderboard_response_shape(client: AsyncClient) -> None:
    """Leaderboard response has the expected top-level LeaderboardResponse shape."""
    track_encoded = _TRACK.replace(" ", "%20")
    resp = await client.get(f"/api/leaderboards/{track_encoded}/corners?corner=3")
    assert resp.status_code == 200
    data = resp.json()
    assert "track_name" in data
    assert "corner_number" in data
    assert "entries" in data
    assert data["corner_number"] == 3


@pytest.mark.asyncio
async def test_corner_leaderboard_limit_param_respected(client: AsyncClient) -> None:
    """The limit query parameter caps the number of returned entries."""
    await _seed_session("sess-001")
    await _seed_corner_record("sess-001", corner_number=1, sector_time_s=11.0, opted_in=True)

    track_encoded = _TRACK.replace(" ", "%20")
    resp = await client.get(f"/api/leaderboards/{track_encoded}/corners?corner=1&limit=1")
    assert resp.status_code == 200
    assert len(resp.json()["entries"]) <= 1


# ---------------------------------------------------------------------------
# GET /api/leaderboards/{track}/kings — corner kings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_corner_kings_empty_when_no_data(client: AsyncClient) -> None:
    """Kings endpoint returns empty list when no CornerKing rows exist."""
    track_encoded = _TRACK.replace(" ", "%20")
    resp = await client.get(f"/api/leaderboards/{track_encoded}/kings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["track_name"] == _TRACK
    assert data["kings"] == []


@pytest.mark.asyncio
async def test_corner_kings_returns_seeded_king(client: AsyncClient) -> None:
    """Kings endpoint returns the seeded CornerKing row."""
    await _seed_corner_king(corner_number=1, best_time_s=9.8)

    track_encoded = _TRACK.replace(" ", "%20")
    resp = await client.get(f"/api/leaderboards/{track_encoded}/kings")
    assert resp.status_code == 200
    kings = resp.json()["kings"]
    assert len(kings) == 1
    assert kings[0]["corner_number"] == 1
    assert kings[0]["user_name"] == "Test Driver"
    assert abs(kings[0]["best_time_s"] - 9.8) < 0.001


@pytest.mark.asyncio
async def test_corner_kings_response_shape(client: AsyncClient) -> None:
    """KingsResponse has track_name and kings list."""
    track_encoded = _TRACK.replace(" ", "%20")
    resp = await client.get(f"/api/leaderboards/{track_encoded}/kings")
    assert resp.status_code == 200
    data = resp.json()
    assert "track_name" in data
    assert "kings" in data


# ---------------------------------------------------------------------------
# POST /api/leaderboards/opt-in — toggle leaderboard opt-in
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_opt_in_true_sets_flag(client: AsyncClient) -> None:
    """POST /api/leaderboards/opt-in with opt_in=true sets leaderboard_opt_in to True."""
    resp = await client.post("/api/leaderboards/opt-in", json={"opt_in": True})
    assert resp.status_code == 200
    assert resp.json()["leaderboard_opt_in"] is True


@pytest.mark.asyncio
async def test_opt_in_false_clears_flag(client: AsyncClient) -> None:
    """POST /api/leaderboards/opt-in with opt_in=false clears leaderboard_opt_in."""
    # First opt in
    await client.post("/api/leaderboards/opt-in", json={"opt_in": True})
    # Then opt out
    resp = await client.post("/api/leaderboards/opt-in", json={"opt_in": False})
    assert resp.status_code == 200
    assert resp.json()["leaderboard_opt_in"] is False


@pytest.mark.asyncio
async def test_opt_in_toggles_are_idempotent(client: AsyncClient) -> None:
    """Calling opt-in twice with the same value produces a consistent result."""
    await client.post("/api/leaderboards/opt-in", json={"opt_in": True})
    resp = await client.post("/api/leaderboards/opt-in", json={"opt_in": True})
    assert resp.status_code == 200
    assert resp.json()["leaderboard_opt_in"] is True


@pytest.mark.asyncio
async def test_opt_in_404_user_not_found(client: AsyncClient) -> None:
    """POST /api/leaderboards/opt-in returns 404 when the user doesn't exist in the DB."""
    app.dependency_overrides[get_current_user] = lambda: _GHOST_USER

    resp = await client.post("/api/leaderboards/opt-in", json={"opt_in": True})
    assert resp.status_code == 404
    assert "user not found" in resp.json()["detail"].lower()

    # Restore
    from backend.tests.conftest import _TEST_USER  # type: ignore[attr-defined]

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER

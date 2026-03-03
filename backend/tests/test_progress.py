"""Tests for the progress rate leaderboard endpoint."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient

from backend.api.db.models import Session, User
from backend.tests.conftest import _TEST_USER, _test_session_factory


@pytest_asyncio.fixture
async def _seed_progress_data() -> None:
    """Seed the test database with multiple users and sessions for leaderboard tests."""
    async with _test_session_factory() as db:
        now = datetime.now(tz=UTC)

        # User A: 4 sessions, improving from 100s -> 94s (rate = (94-100)/4 = -1.5)
        user_a = User(
            id="user-a",
            email="a@test.com",
            name="Driver Alpha",
            leaderboard_opt_in=True,
        )
        db.add(user_a)
        for i in range(4):
            db.add(
                Session(
                    session_id=f"sess-a-{i}",
                    user_id="user-a",
                    track_name="Barber Motorsports Park",
                    session_date=now - timedelta(days=30 - i),
                    file_key=f"sess-a-{i}",
                    best_lap_time_s=100.0 - i * 2.0,  # 100, 98, 96, 94
                )
            )

        # User B: 3 sessions, improving from 105s -> 100s (rate = (100-105)/3 = -1.667)
        user_b = User(
            id="user-b",
            email="b@test.com",
            name="Driver Beta",
            leaderboard_opt_in=True,
        )
        db.add(user_b)
        for i in range(3):
            db.add(
                Session(
                    session_id=f"sess-b-{i}",
                    user_id="user-b",
                    track_name="Barber Motorsports Park",
                    session_date=now - timedelta(days=20 - i),
                    file_key=f"sess-b-{i}",
                    best_lap_time_s=105.0 - i * 2.5,  # 105, 102.5, 100
                )
            )

        # User C: 2 sessions (below default min_sessions=3), should be excluded
        user_c = User(
            id="user-c",
            email="c@test.com",
            name="Driver Charlie",
            leaderboard_opt_in=True,
        )
        db.add(user_c)
        for i in range(2):
            db.add(
                Session(
                    session_id=f"sess-c-{i}",
                    user_id="user-c",
                    track_name="Barber Motorsports Park",
                    session_date=now - timedelta(days=10 - i),
                    file_key=f"sess-c-{i}",
                    best_lap_time_s=110.0 - i * 3.0,
                )
            )

        # User D: opted out, should not appear even with enough sessions
        user_d = User(
            id="user-d",
            email="d@test.com",
            name="Driver Delta",
            leaderboard_opt_in=False,
        )
        db.add(user_d)
        for i in range(5):
            db.add(
                Session(
                    session_id=f"sess-d-{i}",
                    user_id="user-d",
                    track_name="Barber Motorsports Park",
                    session_date=now - timedelta(days=25 - i),
                    file_key=f"sess-d-{i}",
                    best_lap_time_s=95.0 - i * 3.0,
                )
            )

        # User E: sessions at a DIFFERENT track, should not appear
        user_e = User(
            id="user-e",
            email="e@test.com",
            name="Driver Echo",
            leaderboard_opt_in=True,
        )
        db.add(user_e)
        for i in range(4):
            db.add(
                Session(
                    session_id=f"sess-e-{i}",
                    user_id="user-e",
                    track_name="Road Atlanta",
                    session_date=now - timedelta(days=15 - i),
                    file_key=f"sess-e-{i}",
                    best_lap_time_s=90.0 - i * 1.0,
                )
            )

        # Make the test user also opted-in with 3 sessions (rate = (97-100)/3 = -1.0)
        test_user_result = await db.get(User, _TEST_USER.user_id)
        if test_user_result:
            test_user_result.leaderboard_opt_in = True
        for i in range(3):
            db.add(
                Session(
                    session_id=f"sess-test-{i}",
                    user_id=_TEST_USER.user_id,
                    track_name="Barber Motorsports Park",
                    session_date=now - timedelta(days=5 - i),
                    file_key=f"sess-test-{i}",
                    best_lap_time_s=100.0 - i * 1.5,  # 100, 98.5, 97
                )
            )

        await db.commit()


@pytest.mark.asyncio
async def test_improvement_leaderboard_ranking(
    client: AsyncClient, _seed_progress_data: None
) -> None:
    """Users with >= min_sessions should appear ranked by improvement rate."""
    resp = await client.get("/api/progress/Barber Motorsports Park/improvement")
    assert resp.status_code == 200

    data = resp.json()
    assert data["track_name"] == "Barber Motorsports Park"
    entries = data["entries"]

    # Should have 3 entries: User B (rate -1.667), User A (rate -1.5), Test User (rate -1.0)
    assert len(entries) == 3

    # Verify ranking order: most negative first
    rates = [e["improvement_rate_s"] for e in entries]
    assert rates == sorted(rates), "Entries should be sorted by improvement rate ascending"

    # Rank 1 should be User B (most negative rate)
    assert entries[0]["user_name"] == "Driver Beta"
    assert entries[0]["rank"] == 1

    # Rank 2 should be User A
    assert entries[1]["user_name"] == "Driver Alpha"
    assert entries[1]["rank"] == 2

    # Rank 3 should be Test User
    assert entries[2]["user_name"] == "Test Driver"
    assert entries[2]["rank"] == 3


@pytest.mark.asyncio
async def test_user_below_min_sessions_excluded(
    client: AsyncClient, _seed_progress_data: None
) -> None:
    """User C has only 2 sessions, below default min_sessions=3."""
    resp = await client.get("/api/progress/Barber Motorsports Park/improvement")
    assert resp.status_code == 200
    names = [e["user_name"] for e in resp.json()["entries"]]
    assert "Driver Charlie" not in names


@pytest.mark.asyncio
async def test_opted_out_user_excluded(client: AsyncClient, _seed_progress_data: None) -> None:
    """User D is opted out, should not appear."""
    resp = await client.get("/api/progress/Barber Motorsports Park/improvement")
    assert resp.status_code == 200
    names = [e["user_name"] for e in resp.json()["entries"]]
    assert "Driver Delta" not in names


@pytest.mark.asyncio
async def test_different_track_excluded(client: AsyncClient, _seed_progress_data: None) -> None:
    """User E only has sessions at Road Atlanta, not Barber."""
    resp = await client.get("/api/progress/Barber Motorsports Park/improvement")
    assert resp.status_code == 200
    names = [e["user_name"] for e in resp.json()["entries"]]
    assert "Driver Echo" not in names


@pytest.mark.asyncio
async def test_your_rank_and_percentile(client: AsyncClient, _seed_progress_data: None) -> None:
    """The test user should have rank/percentile set."""
    resp = await client.get("/api/progress/Barber Motorsports Park/improvement")
    assert resp.status_code == 200
    data = resp.json()

    assert data["your_rank"] == 3
    # percentile = (3-1)/3 * 100 = 66.7
    assert data["your_percentile"] is not None
    assert abs(data["your_percentile"] - 66.7) < 0.1


@pytest.mark.asyncio
async def test_empty_track_returns_empty_list(client: AsyncClient) -> None:
    """A track with no sessions should return an empty entries list."""
    resp = await client.get("/api/progress/Nonexistent Track/improvement")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entries"] == []
    assert data["your_rank"] is None
    assert data["your_percentile"] is None


@pytest.mark.asyncio
async def test_min_sessions_param(client: AsyncClient, _seed_progress_data: None) -> None:
    """Setting min_sessions=2 should include User C."""
    resp = await client.get("/api/progress/Barber Motorsports Park/improvement?min_sessions=2")
    assert resp.status_code == 200
    names = [e["user_name"] for e in resp.json()["entries"]]
    assert "Driver Charlie" in names


@pytest.mark.asyncio
async def test_time_window_filtering(client: AsyncClient, _seed_progress_data: None) -> None:
    """Setting days=7 should only include very recent sessions."""
    resp = await client.get("/api/progress/Barber Motorsports Park/improvement?days=7")
    assert resp.status_code == 200
    # With days=7, only the test user's sessions (within last 5 days) qualify
    # User A sessions are 27-30 days old, User B 18-20, etc.
    data = resp.json()
    # The test user has 3 sessions within 5 days, all within the 7-day window
    names = [e["user_name"] for e in data["entries"]]
    assert "Driver Alpha" not in names
    assert "Driver Beta" not in names


@pytest.mark.asyncio
async def test_improvement_values(client: AsyncClient, _seed_progress_data: None) -> None:
    """Verify the actual improvement values are computed correctly."""
    resp = await client.get("/api/progress/Barber Motorsports Park/improvement")
    data = resp.json()

    # User B: first=105, latest=100, total=-5, rate=-5/3=-1.6667
    beta = next(e for e in data["entries"] if e["user_name"] == "Driver Beta")
    assert beta["best_lap_first"] == 105.0
    assert beta["best_lap_latest"] == 100.0
    assert abs(beta["total_improvement_s"] - (-5.0)) < 0.01
    assert beta["n_sessions"] == 3

    # User A: first=100, latest=94, total=-6, rate=-6/4=-1.5
    alpha = next(e for e in data["entries"] if e["user_name"] == "Driver Alpha")
    assert alpha["best_lap_first"] == 100.0
    assert alpha["best_lap_latest"] == 94.0
    assert abs(alpha["total_improvement_s"] - (-6.0)) < 0.01
    assert alpha["n_sessions"] == 4


@pytest.mark.asyncio
async def test_days_param_validation(client: AsyncClient) -> None:
    """Days param must be between 7 and 365."""
    resp = await client.get("/api/progress/Test/improvement?days=1")
    assert resp.status_code == 422

    resp = await client.get("/api/progress/Test/improvement?days=500")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_min_sessions_param_validation(client: AsyncClient) -> None:
    """min_sessions param must be between 2 and 10."""
    resp = await client.get("/api/progress/Test/improvement?min_sessions=1")
    assert resp.status_code == 422

    resp = await client.get("/api/progress/Test/improvement?min_sessions=20")
    assert resp.status_code == 422

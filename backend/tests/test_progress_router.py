"""Tests for the progress rate leaderboard router (lines 48-120).

Covers:
  - Empty leaderboard (no sessions in window)
  - Users below min_sessions threshold are excluded
  - Ranking, improvement rate, and percentile calculation
  - The requesting user's rank/percentile in the response
  - Multiple users, multiple sessions
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from backend.api.db.models import Session as SessionModel
from backend.api.db.models import User as UserModel
from backend.tests.conftest import _TEST_USER, _test_session_factory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_user(user_id: str, name: str, email: str) -> None:
    """Seed a User row for FK constraints."""
    async with _test_session_factory() as db:
        existing = await db.get(UserModel, user_id)
        if existing is None:
            db.add(UserModel(id=user_id, email=email, name=name))
            await db.commit()


async def _seed_session(
    session_id: str,
    user_id: str,
    track_name: str,
    best_lap_time_s: float,
    days_ago: int = 0,
) -> None:
    """Seed a Session row with a best_lap_time_s."""
    async with _test_session_factory() as db:
        existing = await db.get(SessionModel, session_id)
        if existing is None:
            session_date = datetime.now(UTC) - timedelta(days=days_ago)
            db.add(
                SessionModel(
                    session_id=session_id,
                    user_id=user_id,
                    track_name=track_name,
                    session_date=session_date,
                    file_key=session_id,
                    n_laps=5,
                    best_lap_time_s=best_lap_time_s,
                )
            )
            await db.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestImprovementLeaderboardEmpty:
    """Tests for the empty-result path of improvement_leaderboard."""

    @pytest.mark.asyncio
    async def test_empty_leaderboard_for_unknown_track(self, client: AsyncClient) -> None:
        """Returns empty entries list when no sessions exist for a track."""
        resp = await client.get("/api/progress/no-such-track/improvement")
        assert resp.status_code == 200
        data = resp.json()
        assert data["track_name"] == "no-such-track"
        assert data["entries"] == []
        assert data["your_rank"] is None
        assert data["your_percentile"] is None

    @pytest.mark.asyncio
    async def test_empty_leaderboard_when_sessions_have_no_best_lap(
        self, client: AsyncClient
    ) -> None:
        """Sessions without best_lap_time_s are excluded from leaderboard."""
        # Seed 5 sessions with best_lap_time_s=None
        for i in range(5):
            async with _test_session_factory() as db:
                existing = await db.get(SessionModel, f"null-lap-{i}")
                if existing is None:
                    db.add(
                        SessionModel(
                            session_id=f"null-lap-{i}",
                            user_id=_TEST_USER.user_id,
                            track_name="null-lap-track",
                            session_date=datetime.now(UTC) - timedelta(days=i),
                            file_key=f"null-lap-{i}",
                            n_laps=5,
                            best_lap_time_s=None,  # deliberately null
                        )
                    )
                    await db.commit()

        resp = await client.get("/api/progress/null-lap-track/improvement")
        assert resp.status_code == 200
        assert resp.json()["entries"] == []


class TestImprovementLeaderboardMinSessions:
    """Tests for the min_sessions filter in improvement_leaderboard."""

    @pytest.mark.asyncio
    async def test_users_below_min_sessions_excluded(self, client: AsyncClient) -> None:
        """Users with fewer than min_sessions (default=3) sessions are not ranked."""
        track = "min-sess-track"
        # _TEST_USER has only 2 sessions (below default min_sessions=3)
        await _seed_session("ms-sess-1", _TEST_USER.user_id, track, 95.0, days_ago=10)
        await _seed_session("ms-sess-2", _TEST_USER.user_id, track, 93.0, days_ago=5)

        resp = await client.get(f"/api/progress/{track}/improvement")
        assert resp.status_code == 200
        data = resp.json()
        # User has only 2 sessions, needs 3 — should be excluded
        assert len(data["entries"]) == 0
        assert data["your_rank"] is None

    @pytest.mark.asyncio
    async def test_custom_min_sessions_param(self, client: AsyncClient) -> None:
        """min_sessions=2 query param allows users with 2 sessions to qualify."""
        track = "min-2-sess-track"
        await _seed_session("m2-sess-1", _TEST_USER.user_id, track, 95.0, days_ago=10)
        await _seed_session("m2-sess-2", _TEST_USER.user_id, track, 93.0, days_ago=5)

        resp = await client.get(f"/api/progress/{track}/improvement?min_sessions=2")
        assert resp.status_code == 200
        data = resp.json()
        # User now qualifies with min_sessions=2
        assert len(data["entries"]) == 1
        assert data["entries"][0]["user_name"] == _TEST_USER.name
        assert data["entries"][0]["n_sessions"] == 2

    @pytest.mark.asyncio
    async def test_exactly_min_sessions_qualifies(self, client: AsyncClient) -> None:
        """User with exactly min_sessions sessions qualifies (boundary condition)."""
        track = "exact-min-track"
        await _seed_session("em-sess-1", _TEST_USER.user_id, track, 100.0, days_ago=20)
        await _seed_session("em-sess-2", _TEST_USER.user_id, track, 98.0, days_ago=10)
        await _seed_session("em-sess-3", _TEST_USER.user_id, track, 96.0, days_ago=5)

        resp = await client.get(f"/api/progress/{track}/improvement")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 1


class TestImprovementLeaderboardRanking:
    """Tests for ranking, rate calculation, and percentile in improvement_leaderboard."""

    @pytest.fixture(autouse=True)
    async def _seed_second_user(self) -> None:
        """Seed a second user for multi-user leaderboard tests."""
        await _seed_user("other-user-rank-001", "Other Driver", "other@example.com")

    @pytest.mark.asyncio
    async def test_improvement_rate_calculation(self, client: AsyncClient) -> None:
        """Improvement rate is (last_best - first_best) / n_sessions."""
        track = "rate-calc-track"
        # _TEST_USER: 100.0 → 97.0 over 3 sessions → total_improvement = -3.0, rate = -1.0
        await _seed_session("rc-sess-1", _TEST_USER.user_id, track, 100.0, days_ago=30)
        await _seed_session("rc-sess-2", _TEST_USER.user_id, track, 98.5, days_ago=15)
        await _seed_session("rc-sess-3", _TEST_USER.user_id, track, 97.0, days_ago=5)

        resp = await client.get(f"/api/progress/{track}/improvement")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 1
        entry = data["entries"][0]
        assert entry["n_sessions"] == 3
        assert entry["best_lap_first"] == 100.0
        assert entry["best_lap_latest"] == 97.0
        assert abs(entry["total_improvement_s"] - (-3.0)) < 0.01
        assert abs(entry["improvement_rate_s"] - (-1.0)) < 0.01

    @pytest.mark.asyncio
    async def test_ranking_most_improved_is_rank_1(self, client: AsyncClient) -> None:
        """The user with the most negative improvement rate gets rank 1."""
        track = "ranking-track"
        other_user = "other-user-rank-001"

        # _TEST_USER improves a lot: -3.0 total → rate = -1.0 (3 sessions)
        await _seed_session("rk-t-1", _TEST_USER.user_id, track, 100.0, days_ago=40)
        await _seed_session("rk-t-2", _TEST_USER.user_id, track, 98.0, days_ago=20)
        await _seed_session("rk-t-3", _TEST_USER.user_id, track, 97.0, days_ago=5)

        # other_user improves less: -1.0 total → rate = -0.33 (3 sessions)
        await _seed_session("rk-o-1", other_user, track, 102.0, days_ago=42)
        await _seed_session("rk-o-2", other_user, track, 101.5, days_ago=22)
        await _seed_session("rk-o-3", other_user, track, 101.0, days_ago=7)

        resp = await client.get(f"/api/progress/{track}/improvement")
        assert resp.status_code == 200
        data = resp.json()
        entries = data["entries"]
        assert len(entries) == 2

        # Rank 1 = most improved (most negative rate)
        assert entries[0]["rank"] == 1
        # _TEST_USER improves more, so should be rank 1
        assert entries[0]["user_name"] == _TEST_USER.name
        assert entries[1]["rank"] == 2

    @pytest.mark.asyncio
    async def test_requesting_user_rank_and_percentile(self, client: AsyncClient) -> None:
        """your_rank and your_percentile are set when the requesting user qualifies."""
        track = "percentile-track"
        other_user = "other-user-rank-001"

        # _TEST_USER is the best improver — rank 1 out of 2 → 0th percentile
        await _seed_session("pc-t-1", _TEST_USER.user_id, track, 100.0, days_ago=40)
        await _seed_session("pc-t-2", _TEST_USER.user_id, track, 97.0, days_ago=20)
        await _seed_session("pc-t-3", _TEST_USER.user_id, track, 95.0, days_ago=5)

        # other_user improves less
        await _seed_session("pc-o-1", other_user, track, 100.0, days_ago=42)
        await _seed_session("pc-o-2", other_user, track, 99.0, days_ago=22)
        await _seed_session("pc-o-3", other_user, track, 98.5, days_ago=7)

        resp = await client.get(f"/api/progress/{track}/improvement")
        assert resp.status_code == 200
        data = resp.json()
        assert data["your_rank"] == 1
        assert data["your_percentile"] == 0.0  # rank 1 of 2 → (1-1)/2 * 100 = 0

    @pytest.mark.asyncio
    async def test_requesting_user_not_in_results_has_null_rank(self, client: AsyncClient) -> None:
        """your_rank is None when the requesting user doesn't qualify."""
        track = "null-rank-track"
        other_user = "other-user-rank-001"

        # Only seed sessions for other_user (not _TEST_USER)
        await _seed_session("nr-o-1", other_user, track, 99.0, days_ago=30)
        await _seed_session("nr-o-2", other_user, track, 98.0, days_ago=15)
        await _seed_session("nr-o-3", other_user, track, 97.0, days_ago=5)

        resp = await client.get(f"/api/progress/{track}/improvement")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 1
        assert data["your_rank"] is None
        assert data["your_percentile"] is None

    @pytest.mark.asyncio
    async def test_days_window_filters_old_sessions(self, client: AsyncClient) -> None:
        """Sessions outside the days window are excluded."""
        track = "window-track"
        # Seed 3 sessions — 2 within window, 1 old (91 days ago, outside default 90)
        await _seed_session("wn-1", _TEST_USER.user_id, track, 100.0, days_ago=91)
        await _seed_session("wn-2", _TEST_USER.user_id, track, 98.0, days_ago=20)
        await _seed_session("wn-3", _TEST_USER.user_id, track, 96.0, days_ago=5)

        # Only 2 sessions in window (91-day-old one excluded) → below min_sessions=3
        resp = await client.get(f"/api/progress/{track}/improvement")
        assert resp.status_code == 200
        # Only 2 sessions within 90-day window → user doesn't qualify for default min_sessions=3
        data = resp.json()
        assert len(data["entries"]) == 0

    @pytest.mark.asyncio
    async def test_response_schema_fields_present(self, client: AsyncClient) -> None:
        """Response has all required ProgressLeaderboardResponse fields."""
        track = "schema-check-track"
        await _seed_session("sc-1", _TEST_USER.user_id, track, 100.0, days_ago=30)
        await _seed_session("sc-2", _TEST_USER.user_id, track, 98.0, days_ago=15)
        await _seed_session("sc-3", _TEST_USER.user_id, track, 96.0, days_ago=5)

        resp = await client.get(f"/api/progress/{track}/improvement")
        assert resp.status_code == 200
        data = resp.json()

        # Top-level keys
        assert "track_name" in data
        assert "entries" in data
        assert "your_rank" in data
        assert "your_percentile" in data

        # Entry-level keys
        if data["entries"]:
            entry = data["entries"][0]
            required_entry_fields = {
                "rank",
                "user_name",
                "improvement_rate_s",
                "n_sessions",
                "best_lap_first",
                "best_lap_latest",
                "total_improvement_s",
            }
            assert required_entry_fields.issubset(entry.keys())

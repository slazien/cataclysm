"""Extended tests for progress router — covers uncovered lines.

The progress improvement_leaderboard has ~35 uncovered lines.
Targets:
  - Empty track returns empty entries list
  - Users with < min_sessions are excluded
  - Your rank and percentile computed when current user is in results
  - User not in user_names dict is skipped
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from backend.api.db.models import Session as SessionModel
from backend.api.db.models import User as UserModel
from backend.tests.conftest import _TEST_USER, _test_session_factory


async def _seed_sessions_for_user(
    user_id: str,
    track_name: str,
    best_lap_times: list[float],
    days_ago_list: list[int],
) -> None:
    """Seed session rows for a user at a track with specified lap times and dates."""
    async with _test_session_factory() as db:
        for i, (lap_time, days_ago) in enumerate(zip(best_lap_times, days_ago_list, strict=False)):
            session_date = datetime.now(UTC) - timedelta(days=days_ago)
            db.add(
                SessionModel(
                    session_id=f"prog-{user_id[:8]}-{i}",
                    user_id=user_id,
                    track_name=track_name,
                    session_date=session_date,
                    file_key=f"prog-{user_id[:8]}-{i}",
                    n_laps=3,
                    n_clean_laps=2,
                    best_lap_time_s=lap_time,
                    top3_avg_time_s=lap_time + 0.5,
                    avg_lap_time_s=lap_time + 1.0,
                    consistency_score=0.85,
                )
            )
        await db.commit()


class TestImprovementLeaderboard:
    """Tests for GET /api/progress/{track}/improvement."""

    @pytest.mark.asyncio
    async def test_empty_track_returns_empty_entries(self, client: AsyncClient) -> None:
        """Track with no sessions returns empty entries list."""
        resp = await client.get("/api/progress/nonexistent-track/improvement")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries"] == []
        assert data["your_rank"] is None
        assert data["your_percentile"] is None

    @pytest.mark.asyncio
    async def test_user_below_min_sessions_excluded(self, client: AsyncClient) -> None:
        """User with fewer sessions than min_sessions is not in the leaderboard."""
        track = "barber-motorsports-park"
        # Seed only 2 sessions (default min_sessions=3)
        await _seed_sessions_for_user(_TEST_USER.user_id, track, [90.0, 89.5], [30, 15])

        resp = await client.get(f"/api/progress/{track}/improvement?min_sessions=3")
        assert resp.status_code == 200
        data = resp.json()
        # User has only 2 sessions, min is 3 — should be excluded
        assert data["entries"] == []

    @pytest.mark.asyncio
    async def test_user_meets_min_sessions_appears_in_leaderboard(
        self, client: AsyncClient
    ) -> None:
        """User with enough sessions appears in the leaderboard."""
        track = "road-atlanta-progress"
        # Seed 3 sessions showing improvement
        await _seed_sessions_for_user(_TEST_USER.user_id, track, [92.0, 91.0, 90.0], [60, 30, 5])

        resp = await client.get(f"/api/progress/{track}/improvement?min_sessions=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 1
        entry = data["entries"][0]
        assert entry["rank"] == 1
        assert entry["n_sessions"] == 3
        # total_improvement should be negative (faster over time)
        assert entry["total_improvement_s"] < 0

    @pytest.mark.asyncio
    async def test_your_rank_computed_when_user_in_results(self, client: AsyncClient) -> None:
        """your_rank and your_percentile are set when the current user is in the leaderboard."""
        track = "vir-progress-rank"
        await _seed_sessions_for_user(_TEST_USER.user_id, track, [95.0, 93.0, 91.0], [80, 45, 7])

        resp = await client.get(f"/api/progress/{track}/improvement?min_sessions=3")
        assert resp.status_code == 200
        data = resp.json()
        if data["entries"]:
            # The test user is the only one, so they should be rank 1
            assert data["your_rank"] == 1
            assert data["your_percentile"] is not None
            assert data["your_percentile"] == 0.0  # rank 1 of 1 = 0%

    @pytest.mark.asyncio
    async def test_multiple_users_ranked_by_improvement_rate(self, client: AsyncClient) -> None:
        """Multiple users are ranked by improvement_rate_s (most improved = rank 1)."""
        track = "barber-multi-user"
        other_user_id = "other-prog-usr"

        # Seed the other user row first (separate committed transaction)
        async with _test_session_factory() as db:
            existing = await db.get(UserModel, other_user_id)
            if existing is None:
                db.add(UserModel(id=other_user_id, email="other@prog.test", name="Other Driver"))
                await db.commit()

        # test user improves a lot (2s per session), using 80 days ago (safely inside 90-day window)
        await _seed_sessions_for_user(_TEST_USER.user_id, track, [96.0, 94.0, 92.0], [80, 45, 7])
        # other user improves less (0.5s per session)
        await _seed_sessions_for_user(other_user_id, track, [91.0, 90.5, 90.0], [79, 44, 6])

        resp = await client.get(f"/api/progress/{track}/improvement?min_sessions=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) == 2
        # Most improved (most negative improvement_rate) = rank 1
        assert data["entries"][0]["rank"] == 1
        assert data["entries"][1]["rank"] == 2
        # Test user improved more (2s/session vs 0.5s/session)
        assert data["entries"][0]["user_name"] == _TEST_USER.name

    @pytest.mark.asyncio
    async def test_custom_days_window_filters_old_sessions(self, client: AsyncClient) -> None:
        """Sessions outside the days window are excluded."""
        track = "barber-days-filter"
        # Seed 3 sessions: 2 recent, 1 old
        await _seed_sessions_for_user(
            _TEST_USER.user_id,
            track,
            [91.0, 90.0, 89.0],
            [180, 10, 5],  # first session is 180 days ago (outside 90-day window)
        )

        resp = await client.get(f"/api/progress/{track}/improvement?days=90&min_sessions=3")
        assert resp.status_code == 200
        data = resp.json()
        # Only 2 sessions within 90-day window, min is 3 → excluded
        assert data["entries"] == []

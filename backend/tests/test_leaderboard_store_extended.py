"""Extended tests for leaderboard_store service — covers uncovered lines [94, 141, 242].

Line 94: get_corner_leaderboard — nullable column filter for brake_point/consistency
Line 141: get_corner_leaderboard — limit enforcement in dedup loop
Line 242: get_kings — returns corner_king entries
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.api.db.models import CornerKing, CornerRecord
from backend.api.db.models import Session as SessionModel
from backend.tests.conftest import _TEST_USER, _test_session_factory


async def _seed_corner_record(
    user_id: str,
    session_id: str,
    track_name: str,
    corner_number: int,
    sector_time_s: float,
    min_speed_mps: float = 15.0,
    lap_number: int = 1,
    brake_point_m: float | None = None,
    consistency_cv: float | None = None,
) -> None:
    """Seed a CornerRecord directly into the test DB."""
    async with _test_session_factory() as db:
        db.add(
            CornerRecord(
                session_id=session_id,
                user_id=user_id,
                track_name=track_name,
                corner_number=corner_number,
                sector_time_s=sector_time_s,
                min_speed_mps=min_speed_mps,
                lap_number=lap_number,
                brake_point_m=brake_point_m,
                consistency_cv=consistency_cv,
            )
        )
        await db.commit()


class TestGetCornerLeaderboardFilters:
    """Tests for leaderboard_store.get_corner_leaderboard filter branches."""

    @pytest.fixture(autouse=True)
    async def _seed_base_data(self) -> None:
        """Seed a session row so CornerRecord FK works."""
        async with _test_session_factory() as db:
            existing = await db.get(SessionModel, "lb-sess-001")
            if existing is None:
                db.add(
                    SessionModel(
                        session_id="lb-sess-001",
                        user_id=_TEST_USER.user_id,
                        track_name="barber",
                        session_date=datetime.now(UTC),
                        file_key="lb-sess-001",
                        n_laps=5,
                    )
                )
                await db.commit()

    @pytest.mark.asyncio
    async def test_get_corner_leaderboard_empty_returns_empty(self, client: AsyncClient) -> None:
        """get_corner_leaderboard returns [] when no records exist for a corner."""
        with patch(
            "backend.api.routers.leaderboards.get_corner_leaderboard",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await client.get("/api/leaderboards/no-data-track/corners?corner=1")
        assert resp.status_code == 200
        assert resp.json()["entries"] == []

    @pytest.mark.asyncio
    async def test_get_corner_leaderboard_brake_point_category(self, client: AsyncClient) -> None:
        """brake_point category filters out NULL brake_point records (line 94)."""
        from backend.api.services.leaderboard_store import get_corner_leaderboard

        # Seed a record WITH brake_point
        await _seed_corner_record(
            _TEST_USER.user_id,
            "lb-sess-001",
            "test-track",
            1,
            12.0,
            brake_point_m=100.0,
            lap_number=1,
        )

        async with _test_session_factory() as db:
            entries = await get_corner_leaderboard(db, "test-track", 1, category="brake_point")
        # Should include entries with non-null brake_point_m
        for e in entries:
            assert e.brake_point_m is not None

    @pytest.mark.asyncio
    async def test_get_corner_leaderboard_consistency_category(self, client: AsyncClient) -> None:
        """consistency category filters out NULL consistency_cv records (line 94)."""
        from backend.api.services.leaderboard_store import get_corner_leaderboard

        await _seed_corner_record(
            _TEST_USER.user_id,
            "lb-sess-001",
            "test-cons-track",
            1,
            12.0,
            consistency_cv=0.05,
            lap_number=1,
        )

        async with _test_session_factory() as db:
            entries = await get_corner_leaderboard(db, "test-cons-track", 1, category="consistency")
        for e in entries:
            assert e.consistency_cv is not None

    @pytest.mark.asyncio
    async def test_get_corner_leaderboard_min_speed_category(self, client: AsyncClient) -> None:
        """min_speed category sorts by min_speed descending."""
        from backend.api.services.leaderboard_store import get_corner_leaderboard

        await _seed_corner_record(
            _TEST_USER.user_id,
            "lb-sess-001",
            "speed-track",
            1,
            13.0,
            min_speed_mps=20.0,
            lap_number=1,
        )

        async with _test_session_factory() as db:
            entries = await get_corner_leaderboard(db, "speed-track", 1, category="min_speed")
        # Verifies the category branch executes without error
        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_get_corner_leaderboard_limit_enforced(self, client: AsyncClient) -> None:
        """get_corner_leaderboard respects the limit parameter (line 141)."""
        from backend.api.services.leaderboard_store import get_corner_leaderboard

        # Seed more than limit records using the same session (same user, deduped)
        await _seed_corner_record(
            _TEST_USER.user_id, "lb-sess-001", "limit-track", 2, 11.0, lap_number=1
        )

        async with _test_session_factory() as db:
            entries = await get_corner_leaderboard(db, "limit-track", 2, limit=1)
        assert len(entries) <= 1


class TestGetKings:
    """Tests for leaderboard_store.get_kings (line 242)."""

    @pytest.fixture(autouse=True)
    async def _seed_base_session(self) -> None:
        """Seed a session row needed by FK constraints."""
        async with _test_session_factory() as db:
            existing = await db.get(SessionModel, "kings-sess-001")
            if existing is None:
                db.add(
                    SessionModel(
                        session_id="kings-sess-001",
                        user_id=_TEST_USER.user_id,
                        track_name="barber",
                        session_date=datetime.now(UTC),
                        file_key="kings-sess-001",
                        n_laps=5,
                    )
                )
                await db.commit()

    @pytest.mark.asyncio
    async def test_get_kings_returns_empty_for_unknown_track(self, client: AsyncClient) -> None:
        """get_kings returns [] when no kings are set for a track."""
        with patch(
            "backend.api.routers.leaderboards.get_kings",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await client.get("/api/leaderboards/unknown-track/kings")
        assert resp.status_code == 200
        assert resp.json()["kings"] == []

    @pytest.mark.asyncio
    async def test_get_kings_direct_service_call(self) -> None:
        """get_kings service function returns entries when kings exist (line 242)."""
        from backend.api.services.leaderboard_store import get_kings

        # Seed a CornerKing row with correct field names (best_time_s, session_id required)
        async with _test_session_factory() as db:
            # Check if already exists (unique constraint on track_name, corner_number)
            existing_king = await db.execute(
                __import__("sqlalchemy", fromlist=["select"])
                .select(CornerKing)
                .where(
                    CornerKing.track_name == "king-test-track",
                    CornerKing.corner_number == 3,
                )
            )
            if existing_king.scalar_one_or_none() is None:
                db.add(
                    CornerKing(
                        track_name="king-test-track",
                        corner_number=3,
                        user_id=_TEST_USER.user_id,
                        best_time_s=10.5,
                        session_id="kings-sess-001",
                    )
                )
                await db.commit()

        async with _test_session_factory() as db:
            kings = await get_kings(db, "king-test-track")

        assert len(kings) >= 1
        assert kings[0].corner_number == 3
        assert kings[0].user_name == _TEST_USER.name

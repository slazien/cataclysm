"""Tests for leaderboard_store — record_corner_times and update_kings functions.

Lines covered:
  - 29-45: record_corner_times — inserts CornerRecord rows
  - 207-271: update_kings — recomputes corner kings, upserts CornerKing rows
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.api.db.models import CornerKing, CornerRecord
from backend.api.db.models import Session as SessionModel
from backend.api.schemas.leaderboard import CornerRecordInput
from backend.tests.conftest import _TEST_USER, _test_session_factory


async def _seed_session(session_id: str, user_id: str = _TEST_USER.user_id) -> None:
    """Seed a Session row."""
    async with _test_session_factory() as db:
        existing = await db.get(SessionModel, session_id)
        if existing is None:
            db.add(
                SessionModel(
                    session_id=session_id,
                    user_id=user_id,
                    track_name="barber",
                    session_date=datetime.now(UTC),
                    file_key=session_id,
                    n_laps=5,
                )
            )
            await db.commit()


class TestRecordCornerTimes:
    """Tests for record_corner_times function (lines 29-45)."""

    @pytest.mark.asyncio
    async def test_record_corner_times_inserts_rows(self) -> None:
        """record_corner_times inserts CornerRecord rows for each corner_data entry."""
        from sqlalchemy import select

        from backend.api.services.leaderboard_store import record_corner_times

        session_id = "kings-record-001"
        await _seed_session(session_id)

        inputs = [
            CornerRecordInput(
                corner_number=1,
                sector_time_s=12.5,
                min_speed_mps=20.0,
                lap_number=1,
            ),
            CornerRecordInput(
                corner_number=2,
                sector_time_s=8.0,
                min_speed_mps=35.0,
                lap_number=1,
            ),
        ]

        async with _test_session_factory() as db:
            count = await record_corner_times(db, _TEST_USER.user_id, session_id, "barber", inputs)
            await db.commit()

        assert count == 2

        # Verify rows exist in DB
        async with _test_session_factory() as db:
            result = await db.execute(
                select(CornerRecord).where(CornerRecord.session_id == session_id)
            )
            records = list(result.scalars().all())

        assert len(records) == 2
        corner_nums = {r.corner_number for r in records}
        assert corner_nums == {1, 2}

    @pytest.mark.asyncio
    async def test_record_corner_times_empty_list_returns_zero(self) -> None:
        """record_corner_times with empty list returns 0 without DB error."""
        from backend.api.services.leaderboard_store import record_corner_times

        session_id = "kings-record-empty-001"
        await _seed_session(session_id)

        async with _test_session_factory() as db:
            count = await record_corner_times(db, _TEST_USER.user_id, session_id, "barber", [])
            await db.commit()

        assert count == 0

    @pytest.mark.asyncio
    async def test_record_corner_times_with_optional_fields(self) -> None:
        """record_corner_times correctly stores optional brake_point_m and consistency_cv."""
        from sqlalchemy import select

        from backend.api.services.leaderboard_store import record_corner_times

        session_id = "kings-record-opt-001"
        await _seed_session(session_id)

        inputs = [
            CornerRecordInput(
                corner_number=5,
                sector_time_s=15.0,
                min_speed_mps=25.0,
                lap_number=2,
                brake_point_m=150.0,
                consistency_cv=0.04,
            ),
        ]

        async with _test_session_factory() as db:
            await record_corner_times(db, _TEST_USER.user_id, session_id, "barber", inputs)
            await db.commit()

        async with _test_session_factory() as db:
            result = await db.execute(
                select(CornerRecord).where(
                    CornerRecord.session_id == session_id,
                    CornerRecord.corner_number == 5,
                )
            )
            record = result.scalar_one_or_none()

        assert record is not None
        assert record.brake_point_m == 150.0
        assert record.consistency_cv == 0.04


class TestUpdateKings:
    """Tests for update_kings function (lines 207-271)."""

    @pytest.fixture(autouse=True)
    async def _seed_sessions(self) -> None:
        """Seed session rows for FK constraints."""
        await _seed_session("kings-sess-a")
        await _seed_session("kings-sess-b")

    @pytest.mark.asyncio
    async def test_update_kings_creates_new_king(self) -> None:
        """update_kings creates a CornerKing row for the best time (lines 258-267)."""
        from sqlalchemy import select

        from backend.api.services.leaderboard_store import record_corner_times, update_kings

        track = "update-kings-track-01"

        # Seed a corner record
        inputs = [
            CornerRecordInput(corner_number=1, sector_time_s=11.0, min_speed_mps=20.0, lap_number=1)
        ]
        async with _test_session_factory() as db:
            await record_corner_times(db, _TEST_USER.user_id, "kings-sess-a", track, inputs)
            await db.commit()

        # Run update_kings
        async with _test_session_factory() as db:
            count = await update_kings(db, track)
            await db.commit()

        assert count >= 1

        # Verify king row exists
        async with _test_session_factory() as db:
            result = await db.execute(
                select(CornerKing).where(
                    CornerKing.track_name == track,
                    CornerKing.corner_number == 1,
                )
            )
            king = result.scalar_one_or_none()

        assert king is not None
        assert king.best_time_s == 11.0
        assert king.user_id == _TEST_USER.user_id

    @pytest.mark.asyncio
    async def test_update_kings_returns_zero_for_track_with_no_records(self) -> None:
        """update_kings returns 0 when no records exist for the track."""
        from backend.api.services.leaderboard_store import update_kings

        async with _test_session_factory() as db:
            count = await update_kings(db, "nonexistent-track-xyz")
            await db.commit()

        assert count == 0

    @pytest.mark.asyncio
    async def test_update_kings_updates_existing_king(self) -> None:
        """update_kings updates existing CornerKing row with new best time (lines 252-256)."""
        from sqlalchemy import select

        from backend.api.services.leaderboard_store import record_corner_times, update_kings

        track = "update-kings-track-02"

        # Seed an initial king record
        inputs_initial = [
            CornerRecordInput(corner_number=1, sector_time_s=12.0, min_speed_mps=20.0, lap_number=1)
        ]
        async with _test_session_factory() as db:
            await record_corner_times(db, _TEST_USER.user_id, "kings-sess-a", track, inputs_initial)
            await db.commit()

        async with _test_session_factory() as db:
            await update_kings(db, track)
            await db.commit()

        # Now seed a better record
        inputs_better = [
            CornerRecordInput(corner_number=1, sector_time_s=10.0, min_speed_mps=22.0, lap_number=2)
        ]
        async with _test_session_factory() as db:
            await record_corner_times(db, _TEST_USER.user_id, "kings-sess-b", track, inputs_better)
            await db.commit()

        # Update kings again — should update the existing row
        async with _test_session_factory() as db:
            count = await update_kings(db, track)
            await db.commit()

        assert count >= 1

        async with _test_session_factory() as db:
            result = await db.execute(
                select(CornerKing).where(
                    CornerKing.track_name == track,
                    CornerKing.corner_number == 1,
                )
            )
            king = result.scalar_one_or_none()

        assert king is not None
        assert king.best_time_s == 10.0

    @pytest.mark.asyncio
    async def test_update_kings_handles_multiple_corners(self) -> None:
        """update_kings creates kings for each distinct corner_number."""
        from sqlalchemy import select

        from backend.api.services.leaderboard_store import record_corner_times, update_kings

        track = "update-kings-track-03"

        inputs = [
            CornerRecordInput(
                corner_number=1, sector_time_s=11.0, min_speed_mps=20.0, lap_number=1
            ),
            CornerRecordInput(corner_number=2, sector_time_s=9.0, min_speed_mps=30.0, lap_number=1),
            CornerRecordInput(
                corner_number=3, sector_time_s=14.0, min_speed_mps=18.0, lap_number=1
            ),
        ]
        async with _test_session_factory() as db:
            await record_corner_times(db, _TEST_USER.user_id, "kings-sess-a", track, inputs)
            await db.commit()

        async with _test_session_factory() as db:
            count = await update_kings(db, track)
            await db.commit()

        assert count == 3

        async with _test_session_factory() as db:
            result = await db.execute(select(CornerKing).where(CornerKing.track_name == track))
            kings = list(result.scalars().all())

        assert len(kings) == 3
        corner_nums = {k.corner_number for k in kings}
        assert corner_nums == {1, 2, 3}

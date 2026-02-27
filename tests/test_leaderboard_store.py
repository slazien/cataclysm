"""Unit tests for the leaderboard store service."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import JSON, event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.db.models import Base, CornerRecord, User
from backend.api.schemas.leaderboard import CornerRecordInput
from backend.api.services.leaderboard_store import (
    get_corner_leaderboard,
    get_kings,
    record_corner_times,
    update_kings,
)

# In-memory SQLite for isolated unit tests
_engine = create_async_engine("sqlite+aiosqlite:///", echo=False)


@event.listens_for(_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn: object, connection_record: object) -> None:
    cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Patch JSONB -> JSON for SQLite
for table in Base.metadata.tables.values():
    for column in table.columns:
        if isinstance(column.type, JSONB):
            column.type = JSON()

_session_factory = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _setup_db() -> None:  # type: ignore[misc]
    """Create tables and seed test users before each test."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _session_factory() as session:
        # Create test users
        session.add(User(id="user-a", email="a@test.com", name="Alice", leaderboard_opt_in=True))
        session.add(User(id="user-b", email="b@test.com", name="Bob", leaderboard_opt_in=True))
        session.add(User(id="user-c", email="c@test.com", name="Charlie", leaderboard_opt_in=False))
        await session.commit()

        # Create sessions for FK constraints
        from datetime import UTC, datetime

        from backend.api.db.models import Session as SessionModel

        session.add(
            SessionModel(
                session_id="sess-a1",
                user_id="user-a",
                track_name="Barber Motorsports Park",
                session_date=datetime(2026, 1, 15, tzinfo=UTC),
                file_key="key-a1",
            )
        )
        session.add(
            SessionModel(
                session_id="sess-b1",
                user_id="user-b",
                track_name="Barber Motorsports Park",
                session_date=datetime(2026, 2, 10, tzinfo=UTC),
                file_key="key-b1",
            )
        )
        session.add(
            SessionModel(
                session_id="sess-c1",
                user_id="user-c",
                track_name="Barber Motorsports Park",
                session_date=datetime(2026, 2, 20, tzinfo=UTC),
                file_key="key-c1",
            )
        )
        await session.commit()

    yield  # type: ignore[misc]

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:  # type: ignore[misc]
    """Yield a fresh database session for each test."""
    async with _session_factory() as session:
        yield session  # type: ignore[misc]


@pytest.mark.asyncio
async def test_record_corner_times(db: AsyncSession) -> None:
    """Recording corner times should insert rows."""
    corner_data = [
        CornerRecordInput(corner_number=1, min_speed_mps=25.0, sector_time_s=4.5, lap_number=3),
        CornerRecordInput(corner_number=2, min_speed_mps=20.0, sector_time_s=6.1, lap_number=3),
    ]
    count = await record_corner_times(
        db, "user-a", "sess-a1", "Barber Motorsports Park", corner_data
    )
    await db.commit()
    assert count == 2

    result = await db.execute(select(CornerRecord).where(CornerRecord.user_id == "user-a"))
    records = result.scalars().all()
    assert len(records) == 2


@pytest.mark.asyncio
async def test_record_corner_times_empty(db: AsyncSession) -> None:
    """Recording empty corner data returns 0."""
    count = await record_corner_times(db, "user-a", "sess-a1", "Barber Motorsports Park", [])
    assert count == 0


@pytest.mark.asyncio
async def test_get_corner_leaderboard_empty(db: AsyncSession) -> None:
    """Leaderboard for a corner with no records returns empty."""
    entries = await get_corner_leaderboard(db, "Barber Motorsports Park", 1)
    assert entries == []


@pytest.mark.asyncio
async def test_get_corner_leaderboard_ranked(db: AsyncSession) -> None:
    """Leaderboard ranks opted-in users by sector time."""
    # Alice: corner 1 = 4.5s
    await record_corner_times(
        db,
        "user-a",
        "sess-a1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=25.0, sector_time_s=4.5, lap_number=3)],
    )
    # Bob: corner 1 = 4.2s (faster)
    await record_corner_times(
        db,
        "user-b",
        "sess-b1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=26.0, sector_time_s=4.2, lap_number=5)],
    )
    # Charlie: corner 1 = 3.9s (fastest but NOT opted in)
    await record_corner_times(
        db,
        "user-c",
        "sess-c1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=28.0, sector_time_s=3.9, lap_number=2)],
    )
    await db.commit()

    entries = await get_corner_leaderboard(db, "Barber Motorsports Park", 1)
    assert len(entries) == 2  # Charlie excluded (not opted in)
    assert entries[0].user_name == "Bob"
    assert entries[0].sector_time_s == 4.2
    assert entries[0].rank == 1
    assert entries[1].user_name == "Alice"
    assert entries[1].sector_time_s == 4.5
    assert entries[1].rank == 2


@pytest.mark.asyncio
async def test_get_corner_leaderboard_dedupes_per_user(db: AsyncSession) -> None:
    """Each user appears once with their best time."""
    await record_corner_times(
        db,
        "user-a",
        "sess-a1",
        "Barber Motorsports Park",
        [
            CornerRecordInput(corner_number=1, min_speed_mps=25.0, sector_time_s=5.0, lap_number=1),
            CornerRecordInput(corner_number=1, min_speed_mps=26.0, sector_time_s=4.5, lap_number=3),
        ],
    )
    await db.commit()

    entries = await get_corner_leaderboard(db, "Barber Motorsports Park", 1)
    assert len(entries) == 1
    assert entries[0].sector_time_s == 4.5


@pytest.mark.asyncio
async def test_get_corner_leaderboard_limit(db: AsyncSession) -> None:
    """Limit caps the number of returned entries."""
    await record_corner_times(
        db,
        "user-a",
        "sess-a1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=25.0, sector_time_s=4.5, lap_number=1)],
    )
    await record_corner_times(
        db,
        "user-b",
        "sess-b1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=26.0, sector_time_s=4.2, lap_number=2)],
    )
    await db.commit()

    entries = await get_corner_leaderboard(db, "Barber Motorsports Park", 1, limit=1)
    assert len(entries) == 1
    assert entries[0].user_name == "Bob"


@pytest.mark.asyncio
async def test_get_kings_empty(db: AsyncSession) -> None:
    """Kings for a track with no data returns empty."""
    kings = await get_kings(db, "Barber Motorsports Park")
    assert kings == []


@pytest.mark.asyncio
async def test_update_kings(db: AsyncSession) -> None:
    """update_kings correctly computes kings from opted-in records."""
    await record_corner_times(
        db,
        "user-a",
        "sess-a1",
        "Barber Motorsports Park",
        [
            CornerRecordInput(corner_number=1, min_speed_mps=25.0, sector_time_s=4.5, lap_number=1),
            CornerRecordInput(corner_number=2, min_speed_mps=20.0, sector_time_s=6.0, lap_number=1),
        ],
    )
    await record_corner_times(
        db,
        "user-b",
        "sess-b1",
        "Barber Motorsports Park",
        [
            CornerRecordInput(corner_number=1, min_speed_mps=26.0, sector_time_s=4.2, lap_number=2),
            CornerRecordInput(corner_number=2, min_speed_mps=21.0, sector_time_s=6.3, lap_number=2),
        ],
    )
    await db.commit()

    count = await update_kings(db, "Barber Motorsports Park")
    await db.commit()
    assert count == 2

    kings = await get_kings(db, "Barber Motorsports Park")
    assert len(kings) == 2

    king_map = {k.corner_number: k for k in kings}
    assert king_map[1].user_name == "Bob"  # 4.2 < 4.5
    assert king_map[1].best_time_s == 4.2
    assert king_map[2].user_name == "Alice"  # 6.0 < 6.3
    assert king_map[2].best_time_s == 6.0


@pytest.mark.asyncio
async def test_update_kings_excludes_non_opted_in(db: AsyncSession) -> None:
    """Non-opted-in users cannot become king even with faster times."""
    await record_corner_times(
        db,
        "user-c",
        "sess-c1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=30.0, sector_time_s=3.5, lap_number=1)],
    )
    await record_corner_times(
        db,
        "user-a",
        "sess-a1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=25.0, sector_time_s=4.5, lap_number=1)],
    )
    await db.commit()

    await update_kings(db, "Barber Motorsports Park")
    await db.commit()

    kings = await get_kings(db, "Barber Motorsports Park")
    assert len(kings) == 1
    assert kings[0].user_name == "Alice"


@pytest.mark.asyncio
async def test_update_kings_upserts(db: AsyncSession) -> None:
    """Calling update_kings twice correctly upserts existing king rows."""
    await record_corner_times(
        db,
        "user-a",
        "sess-a1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=25.0, sector_time_s=4.5, lap_number=1)],
    )
    await db.commit()
    await update_kings(db, "Barber Motorsports Park")
    await db.commit()

    kings = await get_kings(db, "Barber Motorsports Park")
    assert kings[0].user_name == "Alice"

    # Bob beats Alice
    await record_corner_times(
        db,
        "user-b",
        "sess-b1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=27.0, sector_time_s=4.0, lap_number=3)],
    )
    await db.commit()
    await update_kings(db, "Barber Motorsports Park")
    await db.commit()

    kings = await get_kings(db, "Barber Motorsports Park")
    assert len(kings) == 1
    assert kings[0].user_name == "Bob"
    assert kings[0].best_time_s == 4.0


@pytest.mark.asyncio
async def test_leaderboard_king_flag(db: AsyncSession) -> None:
    """The is_king flag is set correctly in leaderboard entries."""
    await record_corner_times(
        db,
        "user-a",
        "sess-a1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=25.0, sector_time_s=4.5, lap_number=1)],
    )
    await record_corner_times(
        db,
        "user-b",
        "sess-b1",
        "Barber Motorsports Park",
        [CornerRecordInput(corner_number=1, min_speed_mps=26.0, sector_time_s=4.2, lap_number=2)],
    )
    await db.commit()
    await update_kings(db, "Barber Motorsports Park")
    await db.commit()

    entries = await get_corner_leaderboard(db, "Barber Motorsports Park", 1)
    assert entries[0].is_king is True
    assert entries[1].is_king is False

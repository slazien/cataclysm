"""Service layer for corner leaderboard recording, querying, and king computation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import CornerKing, CornerRecord, Session, User
from backend.api.schemas.leaderboard import CornerKingEntry, CornerRecordEntry, CornerRecordInput

logger = logging.getLogger(__name__)


async def record_corner_times(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    track_name: str,
    corner_data: list[CornerRecordInput],
) -> int:
    """Write CornerRecord rows from processed session corner data.

    Returns the number of records inserted.
    """
    count = 0
    for cd in corner_data:
        record = CornerRecord(
            user_id=user_id,
            session_id=session_id,
            track_name=track_name,
            corner_number=cd.corner_number,
            min_speed_mps=cd.min_speed_mps,
            sector_time_s=cd.sector_time_s,
            lap_number=cd.lap_number,
        )
        db.add(record)
        count += 1
    await db.flush()
    return count


async def get_corner_leaderboard(
    db: AsyncSession,
    track_name: str,
    corner_number: int,
    limit: int = 10,
) -> list[CornerRecordEntry]:
    """Get top N users for a specific corner, ranked by best sector time.

    Only includes users who have opted in to leaderboards.
    Returns the best record per user (deduped).
    """
    from sqlalchemy import func as sa_func

    # Subquery: best sector_time per opted-in user for this corner
    best_per_user = (
        select(
            CornerRecord.user_id,
            sa_func.min(CornerRecord.sector_time_s).label("best_time"),
        )
        .join(User, CornerRecord.user_id == User.id)
        .where(
            CornerRecord.track_name == track_name,
            CornerRecord.corner_number == corner_number,
            User.leaderboard_opt_in.is_(True),
        )
        .group_by(CornerRecord.user_id)
        .subquery()
    )

    # Join back to get the actual record details for each user's best time
    stmt = (
        select(
            CornerRecord,
            User.name.label("user_name"),
            Session.session_date,
        )
        .join(best_per_user, CornerRecord.user_id == best_per_user.c.user_id)
        .join(User, CornerRecord.user_id == User.id)
        .join(Session, CornerRecord.session_id == Session.session_id)
        .where(
            CornerRecord.track_name == track_name,
            CornerRecord.corner_number == corner_number,
            CornerRecord.sector_time_s == best_per_user.c.best_time,
        )
        .order_by(CornerRecord.sector_time_s.asc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Determine who is king (rank 1)
    king_user_id: str | None = None
    king_result = await db.execute(
        select(CornerKing.user_id).where(
            CornerKing.track_name == track_name,
            CornerKing.corner_number == corner_number,
        )
    )
    king_row = king_result.scalar_one_or_none()
    if king_row is not None:
        king_user_id = king_row

    entries: list[CornerRecordEntry] = []
    for rank, row in enumerate(rows, start=1):
        record: CornerRecord = row[0]
        user_name: str = row[1]
        session_date: datetime = row[2]
        entries.append(
            CornerRecordEntry(
                rank=rank,
                user_name=user_name,
                sector_time_s=record.sector_time_s,
                min_speed_mps=record.min_speed_mps,
                session_date=session_date.isoformat(),
                is_king=(record.user_id == king_user_id),
            )
        )

    return entries


async def get_kings(db: AsyncSession, track_name: str) -> list[CornerKingEntry]:
    """Get current king for each corner at a track."""
    stmt = (
        select(CornerKing, User.name.label("user_name"))
        .join(User, CornerKing.user_id == User.id)
        .where(CornerKing.track_name == track_name)
        .order_by(CornerKing.corner_number.asc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        CornerKingEntry(
            corner_number=row[0].corner_number,
            user_name=row[1],
            best_time_s=row[0].best_time_s,
        )
        for row in rows
    ]


async def update_kings(db: AsyncSession, track_name: str) -> int:
    """Recompute kings for all corners at a track after new records.

    Only considers opted-in users. Returns the number of kings updated.
    """
    from sqlalchemy import func as sa_func

    # Find the best sector_time per corner among opted-in users
    best_stmt = (
        select(
            CornerRecord.corner_number,
            sa_func.min(CornerRecord.sector_time_s).label("best_time"),
        )
        .join(User, CornerRecord.user_id == User.id)
        .where(
            CornerRecord.track_name == track_name,
            User.leaderboard_opt_in.is_(True),
        )
        .group_by(CornerRecord.corner_number)
    )

    best_result = await db.execute(best_stmt)
    best_rows = best_result.all()

    updated = 0
    for row in best_rows:
        corner_num: int = row[0]
        best_time: float = row[1]

        # Find the actual record that has this best time
        record_stmt = (
            select(CornerRecord)
            .join(User, CornerRecord.user_id == User.id)
            .where(
                CornerRecord.track_name == track_name,
                CornerRecord.corner_number == corner_num,
                CornerRecord.sector_time_s == best_time,
                User.leaderboard_opt_in.is_(True),
            )
            .limit(1)
        )
        record_result = await db.execute(record_stmt)
        record = record_result.scalar_one_or_none()
        if record is None:
            continue

        # Upsert the king row
        existing_stmt = select(CornerKing).where(
            CornerKing.track_name == track_name,
            CornerKing.corner_number == corner_num,
        )
        existing_result = await db.execute(existing_stmt)
        existing_king = existing_result.scalar_one_or_none()

        if existing_king is not None:
            existing_king.user_id = record.user_id
            existing_king.best_time_s = best_time
            existing_king.session_id = record.session_id
            existing_king.updated_at = datetime.now(UTC)
        else:
            db.add(
                CornerKing(
                    track_name=track_name,
                    corner_number=corner_num,
                    user_id=record.user_id,
                    best_time_s=best_time,
                    session_id=record.session_id,
                    updated_at=datetime.now(UTC),
                )
            )
        updated += 1

    await db.flush()
    return updated

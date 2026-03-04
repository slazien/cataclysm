"""Service layer for corner leaderboard recording, querying, and king computation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import asc, desc, select
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
            brake_point_m=cd.brake_point_m,
            consistency_cv=cd.consistency_cv,
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
    category: str = "sector_time",
) -> list[CornerRecordEntry]:
    """Get top N users for a specific corner, ranked by the chosen category.

    Returns the best record per user (deduped).

    Categories:
      - sector_time: fastest sector time (ASC)
      - min_speed: highest apex speed (DESC)
      - brake_point: latest braking (ASC brake_point_m)
      - consistency: lowest CV (ASC)
    """
    from sqlalchemy import func as sa_func

    # Determine which column to aggregate and how to sort
    sort_config: dict[str, tuple[Any, Any]] = {
        "sector_time": (sa_func.min(CornerRecord.sector_time_s), asc),
        "min_speed": (sa_func.max(CornerRecord.min_speed_mps), desc),
        "brake_point": (sa_func.min(CornerRecord.brake_point_m), asc),
        "consistency": (sa_func.min(CornerRecord.consistency_cv), asc),
    }

    agg_func, sort_fn = sort_config.get(category, sort_config["sector_time"])

    # Map category to the raw column for the join-back WHERE clause
    metric_col_map = {
        "sector_time": CornerRecord.sector_time_s,
        "min_speed": CornerRecord.min_speed_mps,
        "brake_point": CornerRecord.brake_point_m,
        "consistency": CornerRecord.consistency_cv,
    }
    metric_col = metric_col_map.get(category, CornerRecord.sector_time_s)

    # Base filter conditions
    base_filters = [
        CornerRecord.track_name == track_name,
        CornerRecord.corner_number == corner_number,
    ]

    # For nullable columns, filter out NULL values
    if category in ("brake_point", "consistency"):
        base_filters.append(metric_col.isnot(None))

    # Subquery: best metric per user for this corner
    best_per_user = (
        select(
            CornerRecord.user_id,
            agg_func.label("best_metric"),
        )
        .where(*base_filters)
        .group_by(CornerRecord.user_id)
        .subquery()
    )

    # Join back to get the actual record details for each user's best metric.
    # Include user_id in WHERE to avoid cross-user matches on identical metric values.
    join_filters = [
        CornerRecord.track_name == track_name,
        CornerRecord.corner_number == corner_number,
        CornerRecord.user_id == best_per_user.c.user_id,
        metric_col == best_per_user.c.best_metric,
    ]

    # Fetch more rows than limit to account for same-user duplicates (when a user
    # has multiple records with identical best metric values). Dedup in Python below.
    stmt = (
        select(
            CornerRecord,
            User.name.label("user_name"),
            Session.session_date,
        )
        .join(best_per_user, CornerRecord.user_id == best_per_user.c.user_id)
        .join(User, CornerRecord.user_id == User.id)
        .join(Session, CornerRecord.session_id == Session.session_id)
        .where(*join_filters)
        .order_by(sort_fn(metric_col))
        .limit(limit * 3)
    )

    result = await db.execute(stmt)
    all_rows = result.all()

    # Deduplicate: keep only the first (best) row per user
    seen_users: set[str] = set()
    rows: list[Any] = []
    for row in all_rows:
        rec = row[0]
        if rec.user_id in seen_users:
            continue
        seen_users.add(rec.user_id)
        rows.append(row)
        if len(rows) >= limit:
            break

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
                brake_point_m=record.brake_point_m,
                consistency_cv=record.consistency_cv,
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

    Returns the number of kings updated.
    """
    from sqlalchemy import func as sa_func

    # Find the best sector_time per corner
    best_stmt = (
        select(
            CornerRecord.corner_number,
            sa_func.min(CornerRecord.sector_time_s).label("best_time"),
        )
        .where(
            CornerRecord.track_name == track_name,
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
            .where(
                CornerRecord.track_name == track_name,
                CornerRecord.corner_number == corner_num,
                CornerRecord.sector_time_s == best_time,
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

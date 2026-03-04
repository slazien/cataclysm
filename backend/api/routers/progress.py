"""Progress rate leaderboard endpoints."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.db.models import Session, User
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.progress import ProgressEntry, ProgressLeaderboardResponse

router = APIRouter()


@router.get("/{track}/improvement", response_model=ProgressLeaderboardResponse)
async def improvement_leaderboard(
    track: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=7, le=365)] = 90,
    min_sessions: Annotated[int, Query(ge=2, le=10)] = 3,
) -> ProgressLeaderboardResponse:
    """Get the improvement rate leaderboard for a track.

    Returns users ranked by how fast they are improving (seconds per session).
    More negative = improving faster.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)

    # Fetch all sessions at this track within the time window that have a best lap
    stmt = (
        select(Session)
        .where(
            Session.track_name == track,
            Session.session_date >= cutoff,
            Session.best_lap_time_s.isnot(None),
            Session.user_id.isnot(None),
        )
        .order_by(Session.session_date.asc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Group sessions by user_id
    user_sessions: dict[str, list[Session]] = defaultdict(list)
    for row in rows:
        assert row.user_id is not None  # guaranteed by filter  # noqa: S101
        user_sessions[row.user_id].append(row)

    # Fetch all user names
    all_user_ids = list(user_sessions.keys())
    user_names: dict[str, str] = {}
    if all_user_ids:
        name_stmt = select(User.id, User.name).where(User.id.in_(all_user_ids))
        name_result = await db.execute(name_stmt)
        user_names = {uid: name for uid, name in name_result.all()}

    # Compute improvement rate for each qualifying user
    entries: list[ProgressEntry] = []
    for user_id, sessions_list in user_sessions.items():
        if user_id not in user_names:
            continue
        if len(sessions_list) < min_sessions:
            continue

        # Sessions are already ordered by date (from the query)
        first_best = sessions_list[0].best_lap_time_s
        latest_best = sessions_list[-1].best_lap_time_s
        assert first_best is not None and latest_best is not None  # noqa: S101

        n = len(sessions_list)
        total_improvement = latest_best - first_best  # negative = faster
        improvement_rate = total_improvement / n

        entries.append(
            ProgressEntry(
                rank=0,  # placeholder, assigned after sorting
                user_name=user_names[user_id],
                improvement_rate_s=round(improvement_rate, 4),
                n_sessions=n,
                best_lap_first=round(first_best, 3),
                best_lap_latest=round(latest_best, 3),
                total_improvement_s=round(total_improvement, 3),
            )
        )

    # Sort by improvement rate (most negative = most improved = rank 1)
    entries.sort(key=lambda e: e.improvement_rate_s)

    # Assign ranks
    for i, entry in enumerate(entries):
        entry.rank = i + 1

    # Find requesting user's rank and percentile
    your_rank: int | None = None
    your_percentile: float | None = None
    if entries:
        for entry in entries:
            # Match by user_id via the name lookup
            if (
                current_user.user_id in user_names
                and entry.user_name == user_names[current_user.user_id]
            ):
                your_rank = entry.rank
                # percentile: 0 = best, 100 = worst
                your_percentile = round((entry.rank - 1) / len(entries) * 100, 1)
                break

    return ProgressLeaderboardResponse(
        track_name=track,
        entries=entries,
        your_rank=your_rank,
        your_percentile=your_percentile,
    )

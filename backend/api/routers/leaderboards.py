"""Corner leaderboard endpoints -- King of the Corner."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.db.models import User
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.leaderboard import (
    KingsResponse,
    LeaderboardResponse,
    OptInRequest,
    OptInResponse,
)
from backend.api.services.leaderboard_store import (
    get_corner_leaderboard,
    get_kings,
)

router = APIRouter()


@router.get("/{track}/corners", response_model=LeaderboardResponse)
async def corner_leaderboard(
    track: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    corner: Annotated[int, Query(description="Corner number", ge=1)],
    limit: Annotated[int, Query(description="Max entries", ge=1, le=50)] = 10,
) -> LeaderboardResponse:
    """Get per-corner rankings for a track."""
    entries = await get_corner_leaderboard(db, track, corner, limit=limit)
    return LeaderboardResponse(
        track_name=track,
        corner_number=corner,
        entries=entries,
    )


@router.get("/{track}/kings", response_model=KingsResponse)
async def corner_kings(
    track: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KingsResponse:
    """Get current kings for all corners on a track."""
    kings = await get_kings(db, track)
    return KingsResponse(track_name=track, kings=kings)


@router.post("/opt-in", response_model=OptInResponse)
async def toggle_opt_in(
    body: OptInRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OptInResponse:
    """Toggle leaderboard opt-in for the authenticated user."""
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.leaderboard_opt_in = body.opt_in
    await db.flush()

    return OptInResponse(leaderboard_opt_in=user.leaderboard_opt_in)

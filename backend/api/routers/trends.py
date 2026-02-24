"""Cross-session trend endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db
from backend.api.schemas.trends import MilestoneResponse, TrendAnalysisResponse

router = APIRouter()


@router.get("/{track_name}", response_model=TrendAnalysisResponse)
async def get_trends(
    track_name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrendAnalysisResponse:
    """Get cross-session trend analysis for a track."""
    # TODO: Phase 1 — load snapshots, run trends.compute_trend_analysis
    raise NotImplementedError


@router.get("/{track_name}/milestones", response_model=MilestoneResponse)
async def get_milestones(
    track_name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MilestoneResponse:
    """Get milestones (PBs, breakthroughs) for a track."""
    # TODO: Phase 1 — extract milestones from trend analysis
    raise NotImplementedError

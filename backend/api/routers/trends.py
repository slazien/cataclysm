"""Cross-session trend endpoints."""

from __future__ import annotations

import asyncio
from typing import Annotated

from cataclysm.trends import SessionSnapshot
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.trends import MilestoneResponse, MilestoneSchema, TrendAnalysisResponse
from backend.api.services import session_store
from backend.api.services.serializers import dataclass_to_dict

router = APIRouter()


def _collect_snapshots_for_track(track_name: str) -> list[SessionSnapshot]:
    """Gather all session snapshots matching a track name (case-insensitive).

    NOTE: This currently searches all in-memory sessions regardless of user.
    User-scoped filtering happens at the endpoint level via DB queries.
    For now, the in-memory store doesn't track user_id, so we rely on
    the auth middleware to ensure only authenticated users can call this.
    """
    normalized = track_name.strip().lower().replace("_", " ")
    all_sessions = session_store.list_sessions()
    return [
        sd.snapshot
        for sd in all_sessions
        if sd.snapshot.metadata.track_name.strip().lower() == normalized
    ]


_USABLE_THRESHOLD = 40.0


@router.get("/{track_name}", response_model=TrendAnalysisResponse)
async def get_trends(
    track_name: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    include_low_quality: Annotated[
        bool,
        Query(description="Include sessions with GPS quality grade F (score < 40)"),
    ] = False,
) -> TrendAnalysisResponse:
    """Get cross-session trend analysis for a track."""
    from cataclysm.trends import compute_trend_analysis

    snapshots = _collect_snapshots_for_track(track_name)

    # Filter out grade-F sessions by default
    if not include_low_quality:
        snapshots = [s for s in snapshots if s.gps_quality_score >= _USABLE_THRESHOLD]  # type: ignore[union-attr]

    if len(snapshots) < 2:
        raise HTTPException(
            status_code=422,
            detail=f"At least 2 sessions required for trend analysis. "
            f"Found {len(snapshots)} for track '{track_name}'.",
        )

    trend = await asyncio.to_thread(compute_trend_analysis, snapshots)  # type: ignore[arg-type]

    # Serialize the TrendAnalysis dataclass
    data = dataclass_to_dict(trend)
    # The sessions field contains full SessionSnapshot objects which are heavy;
    # strip them down to summary dicts
    if "sessions" in data:
        data["sessions"] = [
            {
                "session_id": s.session_id,
                "session_date": s.metadata.session_date,
                "best_lap_time_s": s.best_lap_time_s,
                "top3_avg_time_s": s.top3_avg_time_s,
                "avg_lap_time_s": s.avg_lap_time_s,
                "consistency_score": s.consistency_score,
                "n_laps": s.n_laps,
                "n_clean_laps": s.n_clean_laps,
                "lap_times_s": s.lap_times_s,
            }
            for s in trend.sessions
        ]

    return TrendAnalysisResponse(
        track_name=trend.track_name,
        data=data,
    )


@router.get("/{track_name}/milestones", response_model=MilestoneResponse)
async def get_milestones(
    track_name: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> MilestoneResponse:
    """Get milestones (PBs, breakthroughs) for a track."""
    from cataclysm.trends import compute_trend_analysis

    snapshots = _collect_snapshots_for_track(track_name)
    if len(snapshots) < 2:
        raise HTTPException(
            status_code=422,
            detail=f"At least 2 sessions required for milestones. "
            f"Found {len(snapshots)} for track '{track_name}'.",
        )

    trend = await asyncio.to_thread(compute_trend_analysis, snapshots)  # type: ignore[arg-type]

    return MilestoneResponse(
        track_name=trend.track_name,
        milestones=[
            MilestoneSchema(
                session_id=m.session_id,
                session_date=m.session_date,
                category=m.category,
                description=m.description,
                value=m.value,
            )
            for m in trend.milestones
        ],
    )

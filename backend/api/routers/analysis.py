"""Analysis endpoints: corners, consistency, grip, gains, delta, linked charts."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db
from backend.api.schemas.analysis import (
    AllLapsCornerResponse,
    ConsistencyResponse,
    CornerResponse,
    DeltaResponse,
    GainsResponse,
    GripResponse,
    IdealLapResponse,
    LinkedChartResponse,
)

router = APIRouter()


@router.get("/{session_id}/corners", response_model=CornerResponse)
async def get_corners(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CornerResponse:
    """Detect corners on the best lap and return KPIs."""
    # TODO: Phase 1 — load session, run corners.detect_corners on best lap
    raise NotImplementedError


@router.get(
    "/{session_id}/corners/all-laps",
    response_model=AllLapsCornerResponse,
)
async def get_all_laps_corners(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AllLapsCornerResponse:
    """Corner KPIs for every lap in the session."""
    # TODO: Phase 1 — extract corners for all laps using best-lap reference
    raise NotImplementedError


@router.get("/{session_id}/consistency", response_model=ConsistencyResponse)
async def get_consistency(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConsistencyResponse:
    """Compute session consistency metrics."""
    # TODO: Phase 1 — run consistency.compute_session_consistency
    raise NotImplementedError


@router.get("/{session_id}/grip", response_model=GripResponse)
async def get_grip(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GripResponse:
    """Estimate grip limits from multi-lap telemetry."""
    # TODO: Phase 1 — run grip.estimate_grip_limit
    raise NotImplementedError


@router.get("/{session_id}/gains", response_model=GainsResponse)
async def get_gains(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GainsResponse:
    """Compute three-tier gain estimates (consistency, composite, theoretical)."""
    # TODO: Phase 1 — run gains.estimate_gains
    raise NotImplementedError


@router.get("/{session_id}/ideal-lap", response_model=IdealLapResponse)
async def get_ideal_lap(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IdealLapResponse:
    """Reconstruct ideal lap from best segments across all clean laps."""
    # TODO: Phase 1 — run gains.reconstruct_ideal_lap
    raise NotImplementedError


@router.get("/{session_id}/delta", response_model=DeltaResponse)
async def get_delta(
    session_id: str,
    ref: Annotated[int, Query(description="Reference lap number")],
    comp: Annotated[int, Query(description="Comparison lap number")],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeltaResponse:
    """Compute delta-T between two laps at each distance point."""
    # TODO: Phase 1 — run delta.compute_delta
    raise NotImplementedError


@router.get(
    "/{session_id}/charts/linked",
    response_model=LinkedChartResponse,
)
async def get_linked_chart_data(
    session_id: str,
    laps: Annotated[
        list[int],
        Query(description="Lap numbers to include in linked charts"),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LinkedChartResponse:
    """Bundle telemetry data for synchronized linked charts."""
    # TODO: Phase 1 — serialize resampled laps into columnar format
    raise NotImplementedError

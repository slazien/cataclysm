"""Analysis endpoints: corners, consistency, grip, gains, delta, linked charts, sectors."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.analysis import (
    AllLapsCornerResponse,
    ConsistencyResponse,
    CornerResponse,
    CornerSchema,
    DegradationEventSchema,
    DegradationResponse,
    DeltaResponse,
    GainsResponse,
    GPSQualityResponse,
    GripResponse,
    IdealLapResponse,
    LapSectorSplitsSchema,
    LinkedChartResponse,
    OptimalProfileResponse,
    SectorResponse,
    SectorSplitSchema,
    VehicleParamsSchema,
)
from backend.api.services import session_store
from backend.api.services.pipeline import get_ideal_lap_data, get_optimal_profile_data
from backend.api.services.serializers import dataclass_to_dict

router = APIRouter()

MPS_TO_MPH = 2.23694


def _corner_to_schema(c: Any) -> CornerSchema:
    """Convert a cataclysm Corner dataclass to a CornerSchema."""
    return CornerSchema(
        number=c.number,
        entry_distance_m=c.entry_distance_m,
        exit_distance_m=c.exit_distance_m,
        apex_distance_m=c.apex_distance_m,
        min_speed_mph=round(c.min_speed_mps * MPS_TO_MPH, 2),
        brake_point_m=c.brake_point_m,
        peak_brake_g=c.peak_brake_g,
        throttle_commit_m=c.throttle_commit_m,
        apex_type=c.apex_type,
    )


def _get_session_or_404(session_id: str) -> Any:
    """Retrieve session data or raise 404."""
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return sd


@router.get("/{session_id}/corners", response_model=CornerResponse)
async def get_corners(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CornerResponse:
    """Return corners detected on the best lap."""
    sd = _get_session_or_404(session_id)
    return CornerResponse(
        session_id=session_id,
        lap_number=sd.processed.best_lap,
        corners=[_corner_to_schema(c) for c in sd.corners],
    )


@router.get(
    "/{session_id}/corners/all-laps",
    response_model=AllLapsCornerResponse,
)
async def get_all_laps_corners(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AllLapsCornerResponse:
    """Corner KPIs for every lap in the session."""
    sd = _get_session_or_404(session_id)
    laps: dict[str, list[CornerSchema]] = {
        str(lap_num): [_corner_to_schema(c) for c in corners]
        for lap_num, corners in sd.all_lap_corners.items()
    }
    return AllLapsCornerResponse(session_id=session_id, laps=laps)


@router.get("/{session_id}/consistency", response_model=ConsistencyResponse)
async def get_consistency(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ConsistencyResponse:
    """Compute session consistency metrics."""
    sd = _get_session_or_404(session_id)
    if sd.consistency is None:
        raise HTTPException(
            status_code=404,
            detail=f"Consistency data not available for session {session_id}",
        )
    data = dataclass_to_dict(sd.consistency)
    return ConsistencyResponse(session_id=session_id, data=data)


@router.get("/{session_id}/grip", response_model=GripResponse)
async def get_grip(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> GripResponse:
    """Estimate grip limits from multi-lap telemetry."""
    sd = _get_session_or_404(session_id)
    if sd.grip is None:
        raise HTTPException(
            status_code=404,
            detail=f"Grip data not available for session {session_id}",
        )
    data = dataclass_to_dict(sd.grip)
    return GripResponse(session_id=session_id, data=data)


@router.get("/{session_id}/gps-quality", response_model=GPSQualityResponse)
async def get_gps_quality(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> GPSQualityResponse:
    """Return GPS quality assessment for a session."""
    sd = _get_session_or_404(session_id)
    if sd.gps_quality is None:
        raise HTTPException(
            status_code=404,
            detail=f"GPS quality data not available for session {session_id}",
        )
    data = dataclass_to_dict(sd.gps_quality)
    return GPSQualityResponse(session_id=session_id, data=data)


@router.get("/{session_id}/gains", response_model=GainsResponse)
async def get_gains(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> GainsResponse:
    """Compute three-tier gain estimates (consistency, composite, theoretical)."""
    sd = _get_session_or_404(session_id)
    if sd.gains is None:
        raise HTTPException(
            status_code=404,
            detail=f"Gains data not available for session {session_id}",
        )
    data = dataclass_to_dict(sd.gains)
    return GainsResponse(session_id=session_id, data=data)


@router.get("/{session_id}/ideal-lap", response_model=IdealLapResponse)
async def get_ideal_lap(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> IdealLapResponse:
    """Reconstruct ideal lap from best segments across all clean laps."""
    sd = _get_session_or_404(session_id)
    if len(sd.coaching_laps) < 2:
        raise HTTPException(
            status_code=422,
            detail="At least 2 clean laps required for ideal lap reconstruction",
        )
    result = await get_ideal_lap_data(sd)
    return IdealLapResponse(
        session_id=session_id,
        distance_m=result["distance_m"],  # type: ignore[arg-type]
        speed_mph=result["speed_mph"],  # type: ignore[arg-type]
        segment_sources=result["segment_sources"],  # type: ignore[arg-type]
    )


@router.get("/{session_id}/optimal-profile", response_model=OptimalProfileResponse)
async def get_optimal_profile(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> OptimalProfileResponse:
    """Compute the physics-optimal velocity profile for the track.

    Uses track curvature derived from the best lap and the friction-circle
    velocity solver.  If equipment is assigned to the session, the tire grip
    parameters are used; otherwise default vehicle parameters apply.
    """
    sd = _get_session_or_404(session_id)
    result = await get_optimal_profile_data(sd)
    vp = result["vehicle_params"]
    assert isinstance(vp, dict)
    return OptimalProfileResponse(
        session_id=session_id,
        distance_m=result["distance_m"],  # type: ignore[arg-type]
        optimal_speed_mph=result["optimal_speed_mph"],  # type: ignore[arg-type]
        max_cornering_speed_mph=result["max_cornering_speed_mph"],  # type: ignore[arg-type]
        brake_points=result["brake_points"],  # type: ignore[arg-type]
        throttle_points=result["throttle_points"],  # type: ignore[arg-type]
        lap_time_s=result["lap_time_s"],  # type: ignore[arg-type]
        vehicle_params=VehicleParamsSchema(**vp),
        equipment_profile_id=result.get("equipment_profile_id"),  # type: ignore[arg-type]
    )


@router.get("/{session_id}/delta", response_model=DeltaResponse)
async def get_delta(
    session_id: str,
    ref: Annotated[int, Query(description="Reference lap number")],
    comp: Annotated[int, Query(description="Comparison lap number")],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> DeltaResponse:
    """Compute delta-T between two laps at each distance point."""
    sd = _get_session_or_404(session_id)

    resampled = sd.processed.resampled_laps
    if ref not in resampled:
        raise HTTPException(status_code=404, detail=f"Reference lap {ref} not found")
    if comp not in resampled:
        raise HTTPException(status_code=404, detail=f"Comparison lap {comp} not found")

    from cataclysm.delta import compute_delta

    delta_result = await asyncio.to_thread(
        compute_delta, resampled[ref], resampled[comp], sd.corners
    )

    return DeltaResponse(
        session_id=session_id,
        ref_lap=ref,
        comp_lap=comp,
        distance_m=delta_result.distance_m.tolist(),
        delta_s=delta_result.delta_time_s.tolist(),
        total_delta_s=delta_result.total_delta_s,
    )


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
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> LinkedChartResponse:
    """Bundle telemetry data for synchronized linked charts."""
    sd = _get_session_or_404(session_id)
    resampled = sd.processed.resampled_laps

    # Validate requested laps exist
    for lap_num in laps:
        if lap_num not in resampled:
            raise HTTPException(status_code=404, detail=f"Lap {lap_num} not found")

    # Use the best lap's distance grid as reference
    ref_df = resampled[sd.processed.best_lap]
    distance_m: list[float] = ref_df["lap_distance_m"].tolist()

    speed_traces: dict[str, list[float]] = {}
    lateral_g_traces: dict[str, list[float]] = {}
    longitudinal_g_traces: dict[str, list[float]] = {}
    heading_traces: dict[str, list[float]] = {}

    for lap_num in laps:
        df = resampled[lap_num]
        key = str(lap_num)
        speed_traces[key] = (df["speed_mps"] * MPS_TO_MPH).tolist()
        lateral_g_traces[key] = df["lateral_g"].tolist()
        longitudinal_g_traces[key] = df["longitudinal_g"].tolist()
        heading_traces[key] = df["heading_deg"].tolist()

    return LinkedChartResponse(
        session_id=session_id,
        laps=laps,
        distance_m=distance_m,
        speed_traces=speed_traces,
        lateral_g_traces=lateral_g_traces,
        longitudinal_g_traces=longitudinal_g_traces,
        heading_traces=heading_traces,
    )


@router.get("/{session_id}/sectors", response_model=SectorResponse)
async def get_sectors(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> SectorResponse:
    """Compute per-lap sector splits with personal bests and composite time."""
    sd = _get_session_or_404(session_id)
    if len(sd.coaching_laps) < 1:
        raise HTTPException(
            status_code=422,
            detail="At least 1 clean lap required for sector analysis",
        )

    from cataclysm.sectors import compute_sector_analysis

    analysis = await asyncio.to_thread(
        compute_sector_analysis,
        sd.processed.resampled_laps,
        sd.corners,
        sd.coaching_laps,
        sd.processed.best_lap,
    )

    segments_dicts = [
        {
            "name": seg.name,
            "entry_distance_m": seg.entry_distance_m,
            "exit_distance_m": seg.exit_distance_m,
            "is_corner": seg.is_corner,
        }
        for seg in analysis.segments
    ]

    lap_splits = [
        LapSectorSplitsSchema(
            lap_number=ls.lap_number,
            total_time_s=ls.total_time_s,
            splits=[
                SectorSplitSchema(
                    sector_name=s.sector_name,
                    time_s=s.time_s,
                    is_personal_best=s.is_personal_best,
                )
                for s in ls.splits
            ],
        )
        for ls in analysis.lap_splits
    ]

    return SectorResponse(
        session_id=session_id,
        segments=segments_dicts,
        lap_splits=lap_splits,
        best_sector_times=analysis.best_sector_times,
        best_sector_laps=analysis.best_sector_laps,
        composite_time_s=analysis.composite_time_s,
    )


@router.get("/{session_id}/mini-sectors")
async def get_mini_sectors(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    n_sectors: int = Query(default=20, ge=3, le=100),
    lap: int | None = Query(default=None),
) -> dict[str, Any]:
    """Return equal-distance mini-sector analysis with per-lap timing."""
    from cataclysm.mini_sectors import compute_mini_sectors

    sd = _get_session_or_404(session_id)
    resampled_laps = sd.processed.resampled_laps
    clean_laps = sd.coaching_laps
    best_lap = sd.processed.best_lap

    analysis = await asyncio.to_thread(
        compute_mini_sectors,
        resampled_laps,
        clean_laps,
        best_lap,
        n_sectors,
    )

    # If a specific lap is requested, return only that lap's data
    lap_filter = [lap] if lap is not None else list(analysis.lap_data.keys())

    return {
        "session_id": session_id,
        "n_sectors": analysis.n_sectors,
        "sectors": [
            {
                "index": s.index,
                "entry_distance_m": s.entry_distance_m,
                "exit_distance_m": s.exit_distance_m,
                "gps_points": s.gps_points,
            }
            for s in analysis.sectors
        ],
        "best_sector_times_s": analysis.best_sector_times_s,
        "best_sector_laps": analysis.best_sector_laps,
        "lap_data": {
            str(ln): {
                "lap_number": ld.lap_number,
                "sector_times_s": ld.sector_times_s,
                "deltas_s": ld.deltas_s,
                "classifications": ld.classifications,
            }
            for ln, ld in analysis.lap_data.items()
            if ln in lap_filter
        },
    }


@router.get("/{session_id}/degradation", response_model=DegradationResponse)
async def get_degradation(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> DegradationResponse:
    """Detect brake fade and tire degradation across the session."""
    sd = _get_session_or_404(session_id)

    from cataclysm.degradation import detect_degradation

    analysis = await asyncio.to_thread(detect_degradation, sd.all_lap_corners, sd.anomalous_laps)

    return DegradationResponse(
        session_id=session_id,
        events=[
            DegradationEventSchema(
                corner_number=e.corner_number,
                metric=e.metric,
                start_lap=e.start_lap,
                end_lap=e.end_lap,
                slope=e.slope,
                r_squared=e.r_squared,
                severity=e.severity,
                description=e.description,
                values=e.values,
                lap_numbers=e.lap_numbers,
            )
            for e in analysis.events
        ],
        has_brake_fade=analysis.has_brake_fade,
        has_tire_degradation=analysis.has_tire_degradation,
    )

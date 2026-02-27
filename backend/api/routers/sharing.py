"""Session sharing endpoints: create share links, upload to share, view comparison."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.db.database import get_db
from backend.api.db.models import ShareComparisonReport, SharedSession
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.sharing import (
    ShareComparisonResponse,
    ShareCreateRequest,
    ShareCreateResponse,
    ShareMetadata,
)
from backend.api.services.comparison import compare_sessions as run_comparison
from backend.api.services.pipeline import process_upload
from backend.api.services.session_store import get_session

logger = logging.getLogger(__name__)

router = APIRouter()

# Share links expire after 7 days
SHARE_EXPIRY_DAYS = 7


@router.post("/create", response_model=ShareCreateResponse)
async def create_share_link(
    body: ShareCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShareCreateResponse:
    """Create a shareable link for a session so a friend can upload and compare."""
    sd = get_session(body.session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {body.session_id} not found")

    token = str(uuid.uuid4())
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=SHARE_EXPIRY_DAYS)

    shared = SharedSession(
        token=token,
        user_id=current_user.user_id,
        session_id=body.session_id,
        track_name=sd.snapshot.metadata.track_name,
        expires_at=expires_at,
    )
    db.add(shared)
    await db.flush()

    return ShareCreateResponse(
        token=token,
        share_url=f"/share/{token}",
        track_name=sd.snapshot.metadata.track_name,
        expires_at=expires_at.isoformat(),
    )


@router.get("/{token}", response_model=ShareMetadata)
async def get_share_metadata(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShareMetadata:
    """Get public metadata for a share link (no auth required)."""
    result = await db.execute(
        select(SharedSession)
        .where(SharedSession.token == token)
        .options(selectinload(SharedSession.user))
    )
    shared = result.scalar_one_or_none()
    if shared is None:
        raise HTTPException(status_code=404, detail="Share link not found")

    now = datetime.now(UTC)
    is_expired = (
        shared.expires_at.replace(tzinfo=UTC) < now
        if shared.expires_at.tzinfo is None
        else shared.expires_at < now
    )

    # Get inviter name from eagerly-loaded user
    inviter_name = "A driver"
    if shared.user:
        inviter_name = shared.user.name or shared.user.email

    # Get best lap time from in-memory session
    best_lap: float | None = None
    sd = get_session(shared.session_id)
    if sd is not None:
        best_lap = sd.snapshot.best_lap_time_s

    return ShareMetadata(
        token=token,
        track_name=shared.track_name,
        inviter_name=inviter_name,
        best_lap_time_s=best_lap,
        created_at=shared.created_at.isoformat() if shared.created_at else "",
        expires_at=shared.expires_at.isoformat() if shared.expires_at else "",
        is_expired=is_expired,
    )


@router.post("/{token}/upload", response_model=ShareComparisonResponse)
async def upload_to_share(
    token: str,
    files: list[UploadFile],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShareComparisonResponse:
    """Upload a CSV to a share link and get a comparison result (no auth required)."""
    result = await db.execute(select(SharedSession).where(SharedSession.token == token))
    shared = result.scalar_one_or_none()
    if shared is None:
        raise HTTPException(status_code=404, detail="Share link not found")

    now = datetime.now(UTC)
    expires_at_aware = (
        shared.expires_at.replace(tzinfo=UTC)
        if shared.expires_at.tzinfo is None
        else shared.expires_at
    )
    if expires_at_aware < now:
        raise HTTPException(status_code=410, detail="Share link has expired")

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Process the first uploaded file
    f = files[0]
    if not f.filename:
        raise HTTPException(status_code=400, detail="File has no name")

    file_bytes = await f.read()
    upload_result = await process_upload(file_bytes, f.filename)
    challenger_sid = str(upload_result["session_id"])

    # Get both sessions from memory
    sd_a = get_session(shared.session_id)
    if sd_a is None:
        raise HTTPException(
            status_code=404,
            detail="Original session no longer available. It may have been deleted.",
        )

    sd_b = get_session(challenger_sid)
    if sd_b is None:
        raise HTTPException(status_code=500, detail="Failed to process uploaded session")

    # Run comparison
    comparison = await run_comparison(sd_a, sd_b)

    # Persist comparison report
    report = ShareComparisonReport(
        share_token=token,
        challenger_session_id=challenger_sid,
        report_json=comparison,
    )
    db.add(report)
    await db.flush()

    return ShareComparisonResponse(
        token=token,
        session_a_id=comparison["session_a_id"],
        session_b_id=comparison["session_b_id"],
        session_a_track=comparison["session_a_track"],
        session_b_track=comparison["session_b_track"],
        session_a_best_lap=comparison["session_a_best_lap"],
        session_b_best_lap=comparison["session_b_best_lap"],
        delta_s=comparison["delta_s"],
        distance_m=comparison["distance_m"],
        delta_time_s=comparison["delta_time_s"],
        corner_deltas=comparison["corner_deltas"],
    )


@router.get("/{token}/comparison", response_model=ShareComparisonResponse)
async def get_share_comparison(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShareComparisonResponse:
    """Get the most recent comparison result for a share link (no auth required)."""
    result = await db.execute(select(SharedSession).where(SharedSession.token == token))
    shared = result.scalar_one_or_none()
    if shared is None:
        raise HTTPException(status_code=404, detail="Share link not found")

    # Get the most recent comparison report
    report_result = await db.execute(
        select(ShareComparisonReport)
        .where(ShareComparisonReport.share_token == token)
        .order_by(ShareComparisonReport.created_at.desc())
        .limit(1)
    )
    report = report_result.scalar_one_or_none()
    if report is None or report.report_json is None:
        raise HTTPException(status_code=404, detail="No comparison available yet")

    data = report.report_json
    return ShareComparisonResponse(
        token=token,
        session_a_id=data.get("session_a_id", ""),
        session_b_id=data.get("session_b_id", ""),
        session_a_track=data.get("session_a_track", ""),
        session_b_track=data.get("session_b_track", ""),
        session_a_best_lap=data.get("session_a_best_lap"),
        session_b_best_lap=data.get("session_b_best_lap"),
        delta_s=data.get("delta_s", 0.0),
        distance_m=data.get("distance_m", []),
        delta_time_s=data.get("delta_time_s", []),
        corner_deltas=data.get("corner_deltas", []),
    )

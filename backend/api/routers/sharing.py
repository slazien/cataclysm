"""Session sharing endpoints: create share links, upload to share, view comparison."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.config import Settings
from backend.api.db.database import get_db
from backend.api.db.models import ShareComparisonReport, SharedSession
from backend.api.dependencies import AuthenticatedUser, get_current_user, get_settings
from backend.api.rate_limit import limiter
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

# Haiku model used for AI comparison narrative
_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_HAIKU_MAX_TOKENS = 1024

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
    settings: Annotated[Settings, Depends(get_settings)],
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

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if f.size is not None and f.size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb}MB limit",
        )
    file_bytes = await f.read()
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb}MB limit",
        )
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
        speed_traces=comparison.get("speed_traces"),
        skill_dimensions=comparison.get("skill_dimensions"),
        ai_verdict=comparison.get("ai_verdict"),
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
        speed_traces=data.get("speed_traces"),
        skill_dimensions=data.get("skill_dimensions"),
        ai_verdict=data.get("ai_verdict"),
    )


# ---------------------------------------------------------------------------
# AI comparison narrative
# ---------------------------------------------------------------------------


class AiComparisonResponse(BaseModel):
    """Response for the AI comparison narrative endpoint."""

    ai_comparison_text: str


def _build_comparison_prompt(data: dict[str, object]) -> str:
    """Build a prompt for Haiku from comparison data."""
    raw_a = data.get("session_a_best_lap", 0)
    raw_b = data.get("session_b_best_lap", 0)
    session_a_best = float(raw_a) if raw_a else 0.0  # type: ignore[arg-type]
    session_b_best = float(raw_b) if raw_b else 0.0  # type: ignore[arg-type]
    corner_deltas = data.get("corner_deltas", [])

    lines = [
        "You are a motorsport driving coach comparing two drivers' laps.",
        "Write a 3-4 paragraph analysis suitable for a shared comparison page.",
        "Be specific about corner numbers and time differences.",
        "Use an encouraging but honest tone.",
        "",
        f"Driver A best lap: {session_a_best:.3f}s",
        f"Driver B best lap: {session_b_best:.3f}s",
        f"Overall delta: {session_a_best - session_b_best:+.3f}s",
        "",
        "Corner-by-corner deltas:",
    ]

    if isinstance(corner_deltas, list):
        for cd in corner_deltas:
            if not isinstance(cd, dict):
                continue
            corner_num = cd.get("corner_number", "?")
            speed_diff = float(cd.get("speed_diff_mph", 0) or 0)
            faster = "A faster" if speed_diff > 0 else "B faster"
            lines.append(f"  Turn {corner_num}: {abs(speed_diff):.1f} mph ({faster})")

    lines.append("")
    lines.append(
        "Write a concise comparison narrative (3-4 paragraphs). "
        "Highlight the biggest differences and where each driver excels."
    )
    return "\n".join(lines)


async def _call_haiku_comparison(prompt: str) -> str:
    """Call Claude Haiku to generate a comparison narrative.

    Uses the synchronous Anthropic client in a thread to avoid blocking
    the event loop, matching the pattern in cataclysm.coaching.
    """
    import asyncio

    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return (
            "AI comparison is unavailable (no API key configured). "
            "Please check your ANTHROPIC_API_KEY environment variable."
        )

    client = anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=60.0)

    def _call() -> str:
        msg = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=_HAIKU_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text  # type: ignore[union-attr]

    return await asyncio.to_thread(_call)


async def _get_or_generate_ai_comparison(
    report: ShareComparisonReport,
    db: AsyncSession,
) -> str:
    """Return cached AI comparison text, or generate and persist it."""
    # Treat empty string as cache miss (failed prior generation)
    if report.ai_comparison_text is not None and report.ai_comparison_text != "":
        return report.ai_comparison_text

    comparison_data = report.report_json or {}
    prompt = _build_comparison_prompt(comparison_data)
    text = await _call_haiku_comparison(prompt)

    # Cache on the report row
    report.ai_comparison_text = text
    db.add(report)
    await db.flush()

    return text


@router.post("/{token}/ai-comparison", response_model=AiComparisonResponse)
@limiter.limit("5/minute")
async def generate_ai_comparison(
    request: Request,
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiComparisonResponse:
    """Generate (or return cached) AI comparison narrative for a share link.

    No auth required — this is a public share endpoint.
    """
    # Verify the share token exists
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

    text = await _get_or_generate_ai_comparison(report, db)
    return AiComparisonResponse(ai_comparison_text=text)

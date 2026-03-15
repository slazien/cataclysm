"""Coaching endpoints: report generation, PDF export, and WebSocket follow-up chat."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
from datetime import UTC, datetime
from typing import Annotated

import cataclysm.topic_guardrail as topic_guardrail
from cataclysm.causal_chains import compute_causal_analysis
from cataclysm.coaching import CoachingReport, CornerGrade
from cataclysm.corners_gained import CornersGainedResult
from cataclysm.driver_archetypes import ArchetypeResult, detect_archetype
from cataclysm.flow_lap import FlowLapResult
from cataclysm.optimal_comparison import CornerOpportunity, OptimalComparisonResult
from cataclysm.pdf_report import ReportContent, generate_pdf
from cataclysm.skill_detection import SkillAssessment, detect_skill_level
from cataclysm.topic_guardrail import (
    INPUT_TOO_LONG_RESPONSE,
    OFF_TOPIC_RESPONSE,
)
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.dependencies import (
    AuthenticatedUser,
    authenticate_websocket,
    get_current_user,
    get_user_or_anon,
)
from backend.api.rate_limit import limiter
from backend.api.schemas.coaching import (
    ChatRequest,
    CoachingReportResponse,
    CornerGradeSchema,
    FollowUpMessage,
    PriorityCornerSchema,
    ReportRequest,
    SkillLevel,
)
from backend.api.services import equipment_store, session_store
from backend.api.services.coaching_store import (
    MAX_DAILY_REGENS,
    clear_coaching_report,
    get_any_coaching_report,
    get_coaching_context,
    get_coaching_report,
    get_estimated_duration_s,
    get_generation_started_at,
    get_regen_remaining,
    is_generating,
    mark_generating,
    record_generation_duration,
    record_regeneration,
    store_coaching_context,
    store_coaching_report,
    unmark_generating,
)
from backend.api.services.db_session_store import get_session_for_user_with_db_sync
from backend.api.services.pipeline import get_optimal_comparison_data
from backend.api.services.session_store import SessionData
from backend.api.services.track_corners import ensure_corners_current

logger = logging.getLogger(__name__)


def _reconstruct_optimal_comparison(raw: dict[str, object]) -> OptimalComparisonResult | None:
    """Rebuild an ``OptimalComparisonResult`` from the serialised dict.

    ``get_optimal_comparison_data`` returns a JSON-safe dict.  The coaching
    prompt formatter only needs scalar fields and ``CornerOpportunity`` items,
    so the numpy arrays (``speed_delta_mps``, ``distance_m``) are set to empty.
    Returns ``None`` when the comparison is flagged invalid.
    """
    import numpy as np

    if not raw.get("is_valid", True):
        return None

    opps: list[CornerOpportunity] = []
    corner_opps = raw.get("corner_opportunities") or []
    if not isinstance(corner_opps, list):
        corner_opps = []
    for item in corner_opps:
        if not isinstance(item, dict):
            continue
        opps.append(
            CornerOpportunity(
                corner_number=int(item.get("corner_number", 0)),
                actual_min_speed_mps=float(item.get("actual_min_speed_mph", 0)) / 2.23694,
                optimal_min_speed_mps=float(item.get("optimal_min_speed_mph", 0)) / 2.23694,
                speed_gap_mps=float(item.get("speed_gap_mph", 0)) / 2.23694,
                speed_gap_mph=float(item.get("speed_gap_mph", 0)),
                actual_brake_point_m=None,
                optimal_brake_point_m=None,
                brake_gap_m=(
                    float(item["brake_gap_m"]) if item.get("brake_gap_m") is not None else None
                ),
                throttle_gap_m=(
                    float(item["throttle_gap_m"])
                    if item.get("throttle_gap_m") is not None
                    else None
                ),
                time_cost_s=float(item.get("time_cost_s", 0)),
                exit_straight_time_cost_s=float(item.get("exit_straight_time_cost_s", 0)),
            )
        )

    return OptimalComparisonResult(
        corner_opportunities=opps,
        actual_lap_time_s=float(raw.get("actual_lap_time_s", 0)),  # type: ignore[arg-type]
        optimal_lap_time_s=float(raw.get("optimal_lap_time_s", 0)),  # type: ignore[arg-type]
        total_gap_s=float(raw.get("total_gap_s", 0)),  # type: ignore[arg-type]
        speed_delta_mps=np.empty(0),
        distance_m=np.empty(0),
        is_valid=True,
        invalid_reasons=[],
    )


router = APIRouter()


def classify_topic(question: str) -> topic_guardrail.TopicClassification:
    """Proxy to topic guardrail classifier.

    Kept as a local wrapper so tests can patch either
    `backend.api.routers.coaching.classify_topic` or
    `cataclysm.topic_guardrail.classify_topic`.
    """
    return topic_guardrail.classify_topic(question)


def _generating_response(
    session_id: str,
    skill_level: str,
    remaining: int,
) -> CoachingReportResponse:
    """Build a standard 'generating' response with timing info."""
    started = get_generation_started_at(session_id, skill_level)
    return CoachingReportResponse(
        session_id=session_id,
        status="generating",
        regen_remaining=remaining,
        regen_max=MAX_DAILY_REGENS,
        generation_started_at=started.isoformat() if started else None,
        generation_estimated_s=get_estimated_duration_s(),
    )


_ABSOLUTE_PRIORITY_TIME_CAP_S = 3.0

# Track background coaching tasks to prevent GC collection and enable error logging
_background_tasks: set[asyncio.Task[None]] = set()


@router.get("/validation/quality")
async def get_coaching_validation_quality(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, object]:
    """Return coaching validation quality aggregates for authenticated users."""
    del current_user  # Auth gate only
    from cataclysm.coaching import _get_validator

    return _get_validator().dashboard


def _parse_priority_corner_number(value: object) -> int:
    """Coerce AI-emitted corner identifiers into a safe integer."""
    try:
        return int(str(value))
    except (ValueError, TypeError):
        return 0


def _sanitize_priority_time_cost(
    value: object,
    *,
    corner_num: int,
    per_corner_caps: dict[int, float],
    session_cap_s: float | None,
) -> float:
    """Bound AI-provided time estimates to session-derived opportunity caps."""
    try:
        time_cost = float(str(value))
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(time_cost) or time_cost <= 0:
        return 0.0

    capped = min(time_cost, _ABSOLUTE_PRIORITY_TIME_CAP_S)
    if session_cap_s is not None:
        capped = min(capped, session_cap_s)
    corner_cap = per_corner_caps.get(corner_num)
    if corner_cap is not None:
        capped = min(capped, corner_cap)
    return round(max(capped, 0.0), 3)


def _track_task(task: asyncio.Task[None]) -> None:
    """Add a background task to the tracked set with a done callback for cleanup."""
    _background_tasks.add(task)

    def _on_done(t: asyncio.Task[None]) -> None:
        _background_tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.error("Background coaching task failed: %s", exc, exc_info=exc)

    task.add_done_callback(_on_done)


async def trigger_auto_coaching(
    session_id: str, sd: SessionData, skill_level: SkillLevel = "intermediate"
) -> None:
    """Fire-and-forget coaching generation for a newly uploaded session.

    Silently skips if a report already exists or is currently generating.
    Called from the upload endpoint so coaching is ready when the user opens
    the session.
    """
    if is_generating(session_id, skill_level):
        return
    existing = await get_coaching_report(session_id, skill_level)
    if existing is not None:
        # Skip if report exists (including errors — errors are retried lazily
        # when the user views the session via GET /report, not on startup).
        return

    mark_generating(session_id, skill_level)
    _track_task(asyncio.create_task(_run_generation(session_id, sd, skill_level)))


@router.post("/{session_id}/report", response_model=CoachingReportResponse)
@limiter.limit("20/hour")
async def generate_report(
    request: Request,
    session_id: str,
    body: ReportRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CoachingReportResponse:
    """Trigger AI coaching report generation for a session.

    Returns immediately with status="generating". The report is built in a
    background task; poll GET /{session_id}/report until status is "ready".
    """
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    await ensure_corners_current(sd)

    remaining = get_regen_remaining(current_user.user_id)

    # If already generating, return current status
    if is_generating(session_id, body.skill_level):
        return _generating_response(session_id, body.skill_level, remaining)

    # Force regeneration: check daily limit, then clear existing report
    if body.force:
        if remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail="Daily regeneration limit reached. Try again tomorrow.",
            )
        after = record_regeneration(current_user.user_id)
        remaining = after if after >= 0 else 0
        await clear_coaching_report(session_id, body.skill_level)
    else:
        # If report already exists and succeeded, return it.
        # If it errored, clear it so the user can retry.
        existing = await get_coaching_report(session_id, body.skill_level)
        if existing is not None:
            if existing.status != "error":
                existing.regen_remaining = remaining
                existing.regen_max = MAX_DAILY_REGENS
                return existing
            await clear_coaching_report(session_id, body.skill_level)

    mark_generating(session_id, body.skill_level)

    # Background task with tracking to prevent GC collection
    _track_task(asyncio.create_task(_run_generation(session_id, sd, body.skill_level)))

    return _generating_response(session_id, body.skill_level, remaining)


# Limit concurrent coaching API calls to avoid rate-limit storms.
_coaching_semaphore = asyncio.Semaphore(3)

# Max retries for rate-limit (429) errors.
_MAX_RETRIES = 3


async def _run_generation(
    session_id: str,
    sd: SessionData,
    skill_level: str,
) -> None:
    """Background task that generates the coaching report."""
    logger.info("Coaching generation STARTED for %s (skill=%s)", session_id, skill_level)
    try:
        from cataclysm.coaching import generate_coaching_report
        from cataclysm.corner_analysis import compute_corner_analysis
        from cataclysm.equipment import EquipmentProfile, SessionConditions

        layout = sd.layout  # Use the pipeline's layout (includes DB corner overrides)
        landmarks = layout.landmarks if layout else []

        coaching_summaries = [
            s for s in sd.processed.lap_summaries if s.lap_number in sd.coaching_laps
        ]

        # Look up equipment context for the session
        equipment_profile: EquipmentProfile | None = None
        conditions: SessionConditions | None = None
        se = equipment_store.get_session_equipment(session_id)
        if se is not None:
            equipment_profile = equipment_store.get_profile(se.profile_id)
            conditions = se.conditions

        weather = sd.weather

        # -----------------------------------------------------------------
        # Batch 1: Independent pre-computes — run in parallel
        # -----------------------------------------------------------------
        # Prepare flow lap inputs synchronously (cheap list comprehensions)
        _flow_lap_times: list[float] | None = None
        _flow_per_lap_speeds: dict[int, list[float]] = {}
        _flow_best_speeds: list[float] = []
        if sd.all_lap_corners and coaching_summaries:
            from cataclysm.constants import MPS_TO_MPH

            _flow_lap_times = [s.lap_time_s for s in coaching_summaries]
            for lap_num, corners in sd.all_lap_corners.items():
                _flow_per_lap_speeds[lap_num] = [c.min_speed_mps * MPS_TO_MPH for c in corners]
            if _flow_per_lap_speeds:
                n_corners = len(next(iter(_flow_per_lap_speeds.values())))
                _flow_best_speeds = [
                    max(
                        _flow_per_lap_speeds[ln][ci]
                        for ln in _flow_per_lap_speeds
                        if ci < len(_flow_per_lap_speeds[ln])
                    )
                    for ci in range(n_corners)
                ]

        async def _compute_flow() -> FlowLapResult | None:
            if _flow_lap_times is None:
                return None
            from cataclysm.flow_lap import detect_flow_laps

            return await asyncio.to_thread(
                detect_flow_laps,
                _flow_lap_times,
                _flow_per_lap_speeds,
                _flow_best_speeds,
            )

        corner_analysis, causal_analysis, flow_laps = await asyncio.gather(
            asyncio.to_thread(
                compute_corner_analysis,
                sd.all_lap_corners,
                sd.gains,
                sd.consistency.corner_consistency if sd.consistency else None,
                landmarks or None,
                sd.processed.best_lap,
            ),
            asyncio.to_thread(
                compute_causal_analysis,
                sd.all_lap_corners,
                sd.anomalous_laps,
            ),
            _compute_flow(),
        )

        # -----------------------------------------------------------------
        # Batch 2: Depends on corner_analysis — run in parallel
        # -----------------------------------------------------------------
        async def _compute_archetype() -> ArchetypeResult | None:
            if not corner_analysis:
                return None
            return await asyncio.to_thread(
                detect_archetype,
                corner_analysis,
                sd.all_lap_corners,
            )

        async def _compute_skill() -> SkillAssessment | None:
            if not corner_analysis:
                return None
            return await asyncio.to_thread(
                detect_skill_level,
                corner_analysis,
                sd.consistency.lap_consistency if sd.consistency else None,
                skill_level,
            )

        async def _compute_corners_gained() -> CornersGainedResult | None:
            if not corner_analysis or not sd.gains:
                return None
            from cataclysm.corners_gained import compute_corners_gained

            best_lap_s = min(s.lap_time_s for s in coaching_summaries)
            target_s = sd.gains.theoretical.theoretical_time_s
            return await asyncio.to_thread(
                compute_corners_gained,
                corner_analysis,
                target_s,
                best_lap_s,
            )

        async def _compute_optimal() -> OptimalComparisonResult | None:
            try:
                raw = await get_optimal_comparison_data(sd)
                return _reconstruct_optimal_comparison(raw)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to compute optimal comparison for coaching sid=%s",
                    session_id,
                    exc_info=True,
                )
                return None

        archetype, skill_assessment, corners_gained, optimal_comparison = await asyncio.gather(
            _compute_archetype(),
            _compute_skill(),
            _compute_corners_gained(),
            _compute_optimal(),
        )

        # Look up driver's historical best at this track
        historical_best_s: float | None = None
        if sd.user_id:
            track_name = sd.parsed.metadata.track_name
            same_track_sessions = [
                s
                for s in session_store.list_sessions()
                if s.user_id == sd.user_id
                and s.parsed.metadata.track_name == track_name
                and s.session_id != session_id
                and s.processed.lap_summaries
            ]
            if same_track_sessions:
                historical_best_s = min(
                    min(ls.lap_time_s for ls in s.processed.lap_summaries)
                    for s in same_track_sessions
                )

        # Semaphore + retry with backoff for rate-limit errors
        logger.info("Coaching generation AWAITING semaphore for %s", session_id)
        async with _coaching_semaphore:
            logger.info("Coaching generation ACQUIRED semaphore for %s", session_id)
            last_exc: Exception | None = None
            for attempt in range(_MAX_RETRIES):
                try:
                    report = await asyncio.to_thread(
                        generate_coaching_report,
                        coaching_summaries,
                        sd.all_lap_corners,
                        sd.parsed.metadata.track_name,
                        gains=sd.gains,
                        skill_level=skill_level,
                        landmarks=landmarks or None,
                        optimal_comparison=optimal_comparison,
                        corner_analysis=corner_analysis,
                        causal_analysis=causal_analysis,
                        archetype=archetype,
                        skill_assessment=skill_assessment,
                        equipment_profile=equipment_profile,
                        conditions=conditions,
                        weather=weather,
                        corners_gained=corners_gained,
                        flow_laps=flow_laps,
                        line_profiles=sd.corner_line_profiles,
                        track_layout=layout,
                        historical_best_s=historical_best_s,
                    )
                    # Treat JSON parse failures as retryable errors
                    if "Could not parse" in (report.summary or ""):
                        logger.warning(
                            "Parse failure for %s, retry %d/%d",
                            session_id,
                            attempt + 1,
                            _MAX_RETRIES,
                        )
                        last_exc = ValueError(report.summary)
                        await asyncio.sleep(5 * (attempt + 1))
                        continue
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    # Only retry on Anthropic rate-limit (429) errors
                    import anthropic

                    if isinstance(exc, anthropic.RateLimitError):
                        wait = 30 * (attempt + 1)
                        logger.warning(
                            "Rate limited for %s, retry %d/%d in %ds",
                            session_id,
                            attempt + 1,
                            _MAX_RETRIES,
                            wait,
                        )
                        await asyncio.sleep(wait)
                    else:
                        raise
            else:
                raise last_exc  # type: ignore[misc]

        priority_corners = []
        per_corner_caps = (
            {
                detail.corner_number: max(detail.total_gain_s, 0.0)
                for detail in corners_gained.per_corner
            }
            if corners_gained is not None
            else {}
        )
        session_cap_s = (
            max(corners_gained.total_gap_s, 0.0)
            if corners_gained is not None
            else max(sd.gains.theoretical.gain_s, 0.0)
            if sd.gains is not None
            else None
        )
        for pc in report.priority_corners:
            corner_num = _parse_priority_corner_number(pc.get("corner", 0))
            priority_corners.append(
                PriorityCornerSchema(
                    corner=corner_num,
                    time_cost_s=_sanitize_priority_time_cost(
                        pc.get("time_cost_s", 0),
                        corner_num=corner_num,
                        per_corner_caps=per_corner_caps,
                        session_cap_s=session_cap_s,
                    ),
                    issue=str(pc.get("issue", "")),
                    tip=str(pc.get("tip", "")),
                )
            )
        priority_corners.sort(key=lambda pc: (-pc.time_cost_s, pc.corner))

        corner_grades = [
            CornerGradeSchema(
                corner=g.corner,
                braking=g.braking,
                trail_braking=g.trail_braking,
                min_speed=g.min_speed,
                throttle=g.throttle,
                notes=g.notes,
                braking_reason=g.braking_reason,
                trail_braking_reason=g.trail_braking_reason,
                min_speed_reason=g.min_speed_reason,
                throttle_reason=g.throttle_reason,
            )
            for g in report.corner_grades
        ]

        response = CoachingReportResponse(
            session_id=session_id,
            status="ready",
            skill_level=skill_level,
            summary=report.summary,
            primary_focus=report.primary_focus,
            priority_corners=priority_corners,
            corner_grades=corner_grades,
            patterns=report.patterns,
            drills=report.drills,
            validation_failed=report.validation_failed,
            validation_violations=report.validation_violations,
        )

        await store_coaching_report(session_id, response, skill_level)
        logger.info("Coaching generation COMPLETED for %s", session_id)
    except Exception:  # noqa: BLE001 — intentionally broad for background task resilience
        logger.exception("Failed to generate coaching report for %s", session_id)
        await store_coaching_report(
            session_id,
            CoachingReportResponse(
                session_id=session_id,
                status="error",
                summary="AI coaching is temporarily unavailable. Please retry in a few minutes.",
            ),
            skill_level,
        )
    finally:
        started = get_generation_started_at(session_id, skill_level)
        if started is not None:
            duration_s = (datetime.now(UTC) - started).total_seconds()
            record_generation_duration(duration_s)
        unmark_generating(session_id, skill_level)


@router.get("/{session_id}/report", response_model=CoachingReportResponse)
async def get_report(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skill_level: SkillLevel = "intermediate",
) -> CoachingReportResponse:
    """Get the coaching report for a session.

    Returns the stored report, a "generating" status if in progress,
    or 404 if no report has been generated or requested.
    """
    # Verify session ownership before returning coaching data
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    await ensure_corners_current(sd)

    remaining = get_regen_remaining(current_user.user_id)

    report = await get_coaching_report(session_id, skill_level)
    if report is not None:
        # Error/unparseable reports should not be served — clear them and return
        # 404 so the frontend's useAutoReport decides whether to re-trigger.
        # IMPORTANT: do NOT fall through to auto-trigger below — that causes
        # infinite regeneration loops on page refresh after a failed generation.
        is_parse_failure = "Could not parse" in (report.summary or "")
        if report.status == "error" or is_parse_failure:
            await clear_coaching_report(session_id, skill_level)
            raise HTTPException(status_code=404, detail="Report cleared after error")
        else:
            # Filter out hallucinated corners beyond the actual corner count.
            num_corners = len(next(iter(sd.all_lap_corners.values()), []))
            if num_corners > 0:
                valid = set(range(1, num_corners + 1))
                if report.corner_grades:
                    report.corner_grades = [g for g in report.corner_grades if g.corner in valid]
                if report.priority_corners:
                    report.priority_corners = [
                        pc for pc in report.priority_corners if pc.corner in valid
                    ]
            report.regen_remaining = remaining
            report.regen_max = MAX_DAILY_REGENS
            return report

    if is_generating(session_id, skill_level):
        return _generating_response(session_id, skill_level, remaining)

    # No report exists and nothing is generating — return 404.
    # The frontend's useAutoReport will POST to trigger generation.
    raise HTTPException(status_code=404, detail="No coaching report found")


def _build_report_content(
    sd: SessionData,
    coaching_response: CoachingReportResponse,
) -> ReportContent:
    """Convert stored session data + coaching response into ReportContent for PDF generation."""
    snapshot = sd.snapshot
    track_name = snapshot.metadata.track_name
    session_date = snapshot.metadata.session_date
    best_lap_number = sd.processed.best_lap
    best_lap_time_s = snapshot.best_lap_time_s
    n_laps = snapshot.n_laps

    # Convert schema objects back to domain dataclass instances
    corner_grades = [
        CornerGrade(
            corner=g.corner,
            braking=g.braking,
            trail_braking=g.trail_braking,
            min_speed=g.min_speed,
            throttle=g.throttle,
            notes=g.notes,
        )
        for g in coaching_response.corner_grades
    ]

    priority_corners: list[dict[str, object]] = [
        {
            "corner": pc.corner,
            "time_cost_s": pc.time_cost_s,
            "issue": pc.issue,
            "tip": pc.tip,
        }
        for pc in coaching_response.priority_corners
    ]

    report = CoachingReport(
        summary=coaching_response.summary or "",
        priority_corners=priority_corners,
        corner_grades=corner_grades,
        patterns=coaching_response.patterns,
        primary_focus=coaching_response.primary_focus,
        drills=coaching_response.drills,
        raw_response="",
        validation_failed=coaching_response.validation_failed,
        validation_violations=coaching_response.validation_violations,
    )

    return ReportContent(
        track_name=track_name,
        session_date=session_date,
        best_lap_number=best_lap_number,
        best_lap_time_s=best_lap_time_s,
        n_laps=n_laps,
        summaries=sd.processed.lap_summaries,
        report=report,
    )


@router.get("/{session_id}/report/pdf")
async def download_pdf_report(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Download the coaching report as a PDF file.

    Requires both a processed session and a completed coaching report.
    """
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    await ensure_corners_current(sd)

    coaching_response = await get_any_coaching_report(session_id)
    if coaching_response is None or coaching_response.status != "ready":
        raise HTTPException(
            status_code=404,
            detail=f"No completed coaching report found for session {session_id}",
        )

    content = _build_report_content(sd, coaching_response)
    pdf_bytes = await asyncio.to_thread(generate_pdf, content)

    short_id = session_id[:8]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="coaching-report-{short_id}.pdf"'},
    )


@router.post("/{session_id}/chat", response_model=FollowUpMessage)
async def coaching_chat_http(
    session_id: str,
    body: ChatRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FollowUpMessage:
    """HTTP POST endpoint for follow-up coaching conversation.

    This replaces the WebSocket endpoint for environments where WebSocket
    proxying is not available (e.g. Next.js rewrites).
    """
    sd = await get_session_for_user_with_db_sync(db, session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    await ensure_corners_current(sd)

    report_response = await get_any_coaching_report(session_id)
    if report_response is None:
        raise HTTPException(
            status_code=404,
            detail="No coaching report found. Generate a report first.",
        )

    question = body.content.strip()
    if not question:
        return FollowUpMessage(
            role="assistant",
            content="Please ask a question about your driving.",
        )

    from cataclysm.coaching import CoachingContext, ask_followup
    from cataclysm.coaching import CoachingReport as DomainReport

    # Layer 1: Off-topic pre-screen
    classification = await asyncio.to_thread(classify_topic, question)
    if not classification.on_topic:
        content = (
            INPUT_TOO_LONG_RESPONSE if classification.source == "too_long" else OFF_TOPIC_RESPONSE
        )
        return FollowUpMessage(role="assistant", content=content)

    # Retrieve or create conversation context
    ctx = await get_coaching_context(session_id)
    if ctx is None:
        ctx = CoachingContext()
        await store_coaching_context(session_id, ctx)

    coaching_report = DomainReport(
        summary=report_response.summary or "",
        priority_corners=[
            {"corner": pc.corner, "time_cost_s": pc.time_cost_s, "issue": pc.issue, "tip": pc.tip}
            for pc in report_response.priority_corners
        ],
        corner_grades=[],
        patterns=report_response.patterns,
        primary_focus=report_response.primary_focus,
        drills=report_response.drills,
        raw_response=report_response.summary or "",
    )

    answer = await asyncio.to_thread(
        ask_followup,
        ctx,
        question,
        coaching_report,
        all_lap_corners=sd.all_lap_corners,
        skill_level=report_response.skill_level,
        gains=sd.gains,
        weather=sd.weather,
    )

    await store_coaching_context(session_id, ctx)
    return FollowUpMessage(role="assistant", content=answer)


@router.websocket("/{session_id}/chat")
async def coaching_chat(
    websocket: WebSocket,
    session_id: str,
) -> None:
    """WebSocket endpoint for follow-up coaching conversation.

    Protocol:
    - Client sends JSON: {"content": "question text"}
    - Server responds with JSON: {"role": "assistant", "content": "answer"}

    Authentication is required via session cookies (same cookies that
    NextAuth.js sets for HTTP requests).
    """
    user = await authenticate_websocket(websocket)
    if user is None:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    await websocket.accept()

    sd = session_store.get_session(session_id)
    if sd is None:
        await websocket.send_json(
            FollowUpMessage(
                role="assistant",
                content="Session not found. Please upload a session first.",
            ).model_dump()
        )
        await websocket.close()
        return
    await ensure_corners_current(sd)

    report_response = await get_any_coaching_report(session_id)
    if report_response is None:
        await websocket.send_json(
            FollowUpMessage(
                role="assistant",
                content="No coaching report found. Generate a report first.",
            ).model_dump()
        )
        await websocket.close()
        return

    from cataclysm.coaching import CoachingContext, CoachingReport, ask_followup

    # Retrieve or create conversation context
    ctx = await get_coaching_context(session_id)
    if ctx is None:
        ctx = CoachingContext()
        await store_coaching_context(session_id, ctx)

    # Build a CoachingReport object for ask_followup
    coaching_report = CoachingReport(
        summary=report_response.summary or "",
        priority_corners=[
            {"corner": pc.corner, "time_cost_s": pc.time_cost_s, "issue": pc.issue, "tip": pc.tip}
            for pc in report_response.priority_corners
        ],
        corner_grades=[],
        patterns=report_response.patterns,
        primary_focus=report_response.primary_focus,
        drills=report_response.drills,
        raw_response=report_response.summary or "",
    )

    try:
        while True:
            data = await websocket.receive_json()
            question = data.get("content", "")

            if not question.strip():
                await websocket.send_json(
                    FollowUpMessage(
                        role="assistant",
                        content="Please ask a question about your driving.",
                    ).model_dump()
                )
                continue

            # Layer 1: Off-topic pre-screen (length + jailbreak + Haiku)
            classification = await asyncio.to_thread(classify_topic, question)
            if not classification.on_topic:
                content = (
                    INPUT_TOO_LONG_RESPONSE
                    if classification.source == "too_long"
                    else OFF_TOPIC_RESPONSE
                )
                await websocket.send_json(
                    FollowUpMessage(role="assistant", content=content).model_dump()
                )
                continue

            answer = await asyncio.to_thread(
                ask_followup,
                ctx,
                question,
                coaching_report,
                all_lap_corners=sd.all_lap_corners,
                skill_level=report_response.skill_level,
                gains=sd.gains,
                weather=sd.weather,
            )

            await store_coaching_context(session_id, ctx)

            response = FollowUpMessage(role="assistant", content=answer)
            await websocket.send_json(response.model_dump())
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 — intentionally broad for WebSocket error boundary
        logger.exception("Error in coaching chat for session %s", session_id)
        with contextlib.suppress(Exception):  # noqa: BLE001
            await websocket.close(code=1011, reason="Internal server error")

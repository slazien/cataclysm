"""Coaching endpoints: report generation, PDF export, and WebSocket follow-up chat."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Annotated

from cataclysm.causal_chains import compute_causal_analysis
from cataclysm.coaching import CoachingReport, CornerGrade
from cataclysm.driver_archetypes import detect_archetype
from cataclysm.pdf_report import ReportContent, generate_pdf
from cataclysm.skill_detection import detect_skill_level
from cataclysm.topic_guardrail import (
    INPUT_TOO_LONG_RESPONSE,
    OFF_TOPIC_RESPONSE,
    classify_topic,
)
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from backend.api.dependencies import (
    AuthenticatedUser,
    authenticate_websocket,
    get_current_user,
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
    get_regen_remaining,
    is_generating,
    mark_generating,
    record_regeneration,
    store_coaching_context,
    store_coaching_report,
    unmark_generating,
)
from backend.api.services.session_store import SessionData

logger = logging.getLogger(__name__)

router = APIRouter()

# Track background coaching tasks to prevent GC collection and enable error logging
_background_tasks: set[asyncio.Task[None]] = set()


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
) -> CoachingReportResponse:
    """Trigger AI coaching report generation for a session.

    Returns immediately with status="generating". The report is built in a
    background task; poll GET /{session_id}/report until status is "ready".
    """
    sd = session_store.get_session_for_user(session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    remaining = get_regen_remaining(current_user.user_id)

    # If already generating, return current status
    if is_generating(session_id, body.skill_level):
        return CoachingReportResponse(
            session_id=session_id,
            status="generating",
            regen_remaining=remaining,
            regen_max=MAX_DAILY_REGENS,
        )

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

    return CoachingReportResponse(
        session_id=session_id,
        status="generating",
        regen_remaining=remaining,
        regen_max=MAX_DAILY_REGENS,
    )


# Limit concurrent coaching API calls to avoid rate-limit storms.
_coaching_semaphore = asyncio.Semaphore(2)

# Max retries for rate-limit (429) errors.
_MAX_RETRIES = 3


async def _run_generation(
    session_id: str,
    sd: SessionData,
    skill_level: str,
) -> None:
    """Background task that generates the coaching report."""
    try:
        from cataclysm.coaching import generate_coaching_report
        from cataclysm.corner_analysis import compute_corner_analysis
        from cataclysm.equipment import EquipmentProfile, SessionConditions
        from cataclysm.track_match import detect_track_or_lookup

        layout = detect_track_or_lookup(sd.parsed.data, sd.parsed.metadata.track_name)
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

        # Pre-compute corner analysis so the LLM gets stats, not raw numbers
        corner_analysis = await asyncio.to_thread(
            compute_corner_analysis,
            sd.all_lap_corners,
            sd.gains,
            sd.consistency.corner_consistency if sd.consistency else None,
            landmarks or None,
            sd.processed.best_lap,
        )

        # Compute inter-corner causal chains
        causal_analysis = await asyncio.to_thread(
            compute_causal_analysis,
            sd.all_lap_corners,
            sd.anomalous_laps,
        )

        # Detect driver archetype and auto-assess skill level
        archetype = (
            await asyncio.to_thread(detect_archetype, corner_analysis, sd.all_lap_corners)
            if corner_analysis
            else None
        )
        skill_assessment = (
            await asyncio.to_thread(
                detect_skill_level,
                corner_analysis,
                sd.consistency.lap_consistency if sd.consistency else None,
                skill_level,
            )
            if corner_analysis
            else None
        )

        # Corners Gained decomposition (gap to target by corner/technique)
        # Use theoretical best as the target — it represents the driver's own
        # potential assembled from their best micro-sectors.
        corners_gained = None
        if corner_analysis and sd.gains:
            from cataclysm.corners_gained import compute_corners_gained

            best_lap_s = min(s.lap_time_s for s in coaching_summaries)
            target_s = sd.gains.theoretical.theoretical_time_s
            corners_gained = await asyncio.to_thread(
                compute_corners_gained,
                corner_analysis,
                target_s,
                best_lap_s,
            )

        # Flow lap detection (peak-performance laps)
        flow_laps = None
        if sd.all_lap_corners and coaching_summaries:
            from cataclysm.constants import MPS_TO_MPH
            from cataclysm.flow_lap import detect_flow_laps

            lap_times = [s.lap_time_s for s in coaching_summaries]
            per_lap_speeds: dict[int, list[float]] = {}
            best_speeds: list[float] = []
            for lap_num, corners in sd.all_lap_corners.items():
                per_lap_speeds[lap_num] = [c.min_speed_mps * MPS_TO_MPH for c in corners]
            if per_lap_speeds:
                n_corners = len(next(iter(per_lap_speeds.values())))
                best_speeds = [
                    max(
                        per_lap_speeds[ln][ci]
                        for ln in per_lap_speeds
                        if ci < len(per_lap_speeds[ln])
                    )
                    for ci in range(n_corners)
                ]
            flow_laps = await asyncio.to_thread(
                detect_flow_laps, lap_times, per_lap_speeds, best_speeds
            )

        # Semaphore + retry with backoff for rate-limit errors
        async with _coaching_semaphore:
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
                        corner_analysis=corner_analysis,
                        causal_analysis=causal_analysis,
                        archetype=archetype,
                        skill_assessment=skill_assessment,
                        equipment_profile=equipment_profile,
                        conditions=conditions,
                        weather=weather,
                        corners_gained=corners_gained,
                        flow_laps=flow_laps,
                        track_layout=layout,
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
        for pc in report.priority_corners:
            try:
                corner_num = int(pc.get("corner", 0))  # type: ignore[call-overload]
            except (ValueError, TypeError):
                corner_num = 0  # AI returned non-numeric (e.g. "Entire Session")
            priority_corners.append(
                PriorityCornerSchema(
                    corner=corner_num,
                    time_cost_s=float(pc.get("time_cost_s", 0) or 0),  # type: ignore[arg-type]
                    issue=str(pc.get("issue", "")),
                    tip=str(pc.get("tip", "")),
                )
            )

        corner_grades = [
            CornerGradeSchema(
                corner=g.corner,
                braking=g.braking,
                trail_braking=g.trail_braking,
                min_speed=g.min_speed,
                throttle=g.throttle,
                notes=g.notes,
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
    except Exception:  # noqa: BLE001 — intentionally broad for background task resilience
        logger.exception("Failed to generate coaching report for %s", session_id)
        await store_coaching_report(
            session_id,
            CoachingReportResponse(
                session_id=session_id,
                status="error",
                summary="AI coaching is temporarily unavailable. Please retry in a few minutes.",
            ),
        )
    finally:
        unmark_generating(session_id, skill_level)


@router.get("/{session_id}/report", response_model=CoachingReportResponse)
async def get_report(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    skill_level: SkillLevel = "intermediate",
) -> CoachingReportResponse:
    """Get the coaching report for a session.

    Returns the stored report, a "generating" status if in progress,
    or 404 if no report has been generated or requested.
    """
    # Verify session ownership before returning coaching data
    sd = session_store.get_session_for_user(session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    remaining = get_regen_remaining(current_user.user_id)

    report = await get_coaching_report(session_id, skill_level)
    if report is not None:
        # Error/unparseable reports should not be served — clear them so the
        # frontend sees a 404 and auto-triggers a fresh generation attempt.
        is_parse_failure = "Could not parse" in (report.summary or "")
        if report.status == "error" or is_parse_failure:
            await clear_coaching_report(session_id, skill_level)
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
        return CoachingReportResponse(
            session_id=session_id,
            status="generating",
            regen_remaining=remaining,
            regen_max=MAX_DAILY_REGENS,
        )

    # Auto-trigger generation instead of returning 404 — the frontend's
    # auto-trigger POST doesn't always fire reliably after error clearing.
    mark_generating(session_id, skill_level)
    task = asyncio.create_task(_run_generation(session_id, sd, skill_level))
    _track_task(task)
    return CoachingReportResponse(
        session_id=session_id,
        status="generating",
        regen_remaining=remaining,
        regen_max=MAX_DAILY_REGENS,
    )


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
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> Response:
    """Download the coaching report as a PDF file.

    Requires both a processed session and a completed coaching report.
    """
    sd = session_store.get_session_for_user(session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

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
) -> FollowUpMessage:
    """HTTP POST endpoint for follow-up coaching conversation.

    This replaces the WebSocket endpoint for environments where WebSocket
    proxying is not available (e.g. Next.js rewrites).
    """
    sd = session_store.get_session_for_user(session_id, current_user.user_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

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
    from cataclysm.topic_guardrail import classify_topic

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

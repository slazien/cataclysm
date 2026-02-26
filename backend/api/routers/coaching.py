"""Coaching endpoints: report generation, PDF export, and WebSocket follow-up chat."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Annotated

from cataclysm.coaching import CoachingReport, CornerGrade
from cataclysm.pdf_report import ReportContent, generate_pdf
from cataclysm.topic_guardrail import (
    INPUT_TOO_LONG_RESPONSE,
    OFF_TOPIC_RESPONSE,
    classify_topic,
)
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from backend.api.dependencies import (
    AuthenticatedUser,
    authenticate_websocket,
    get_current_user,
)
from backend.api.schemas.coaching import (
    CoachingReportResponse,
    CornerGradeSchema,
    FollowUpMessage,
    PriorityCornerSchema,
    ReportRequest,
)
from backend.api.services import equipment_store, session_store
from backend.api.services.coaching_store import (
    clear_coaching_data,
    get_coaching_context,
    get_coaching_report,
    is_generating,
    mark_generating,
    store_coaching_context,
    store_coaching_report,
    unmark_generating,
)
from backend.api.services.session_store import SessionData

logger = logging.getLogger(__name__)

router = APIRouter()


async def trigger_auto_coaching(session_id: str, sd: SessionData) -> None:
    """Fire-and-forget coaching generation for a newly uploaded session.

    Silently skips if a report already exists or is currently generating.
    Called from the upload endpoint so coaching is ready when the user opens
    the session.
    """
    if is_generating(session_id):
        return
    if await get_coaching_report(session_id) is not None:
        return

    mark_generating(session_id)
    asyncio.create_task(_run_generation(session_id, sd, "intermediate"))


@router.post("/{session_id}/report", response_model=CoachingReportResponse)
async def generate_report(
    session_id: str,
    body: ReportRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CoachingReportResponse:
    """Trigger AI coaching report generation for a session.

    Returns immediately with status="generating". The report is built in a
    background task; poll GET /{session_id}/report until status is "ready".
    """
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # If already generating, return current status
    if is_generating(session_id):
        return CoachingReportResponse(session_id=session_id, status="generating")

    # If report already exists and succeeded, return it.
    # If it errored, clear it so the user can retry.
    existing = await get_coaching_report(session_id)
    if existing is not None:
        if existing.status != "error":
            return existing
        await clear_coaching_data(session_id)

    mark_generating(session_id)

    # Fire-and-forget background task
    asyncio.create_task(_run_generation(session_id, sd, body.skill_level))

    return CoachingReportResponse(session_id=session_id, status="generating")


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

        report = await asyncio.to_thread(
            generate_coaching_report,
            coaching_summaries,
            sd.all_lap_corners,
            sd.parsed.metadata.track_name,
            gains=sd.gains,
            skill_level=skill_level,
            landmarks=landmarks or None,
            corner_analysis=corner_analysis,
            equipment_profile=equipment_profile,
            conditions=conditions,
            weather=weather,
        )

        priority_corners = [
            PriorityCornerSchema(
                corner=int(pc.get("corner", 0)),  # type: ignore[call-overload]
                time_cost_s=float(pc.get("time_cost_s", 0)),  # type: ignore[arg-type]
                issue=str(pc.get("issue", "")),
                tip=str(pc.get("tip", "")),
            )
            for pc in report.priority_corners
        ]

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
            summary=report.summary,
            priority_corners=priority_corners,
            corner_grades=corner_grades,
            patterns=report.patterns,
            drills=report.drills,
            validation_failed=report.validation_failed,
            validation_violations=report.validation_violations,
        )

        await store_coaching_report(session_id, response, skill_level)
    except Exception:
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
        unmark_generating(session_id)


@router.get("/{session_id}/report", response_model=CoachingReportResponse)
async def get_report(
    session_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CoachingReportResponse:
    """Get the coaching report for a session.

    Returns the stored report, a "generating" status if in progress,
    or 404 if no report has been generated or requested.
    """
    report = await get_coaching_report(session_id)
    if report is not None:
        return report

    if is_generating(session_id):
        return CoachingReportResponse(session_id=session_id, status="generating")

    raise HTTPException(
        status_code=404,
        detail=f"No coaching report found for session {session_id}",
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
    sd = session_store.get_session(session_id)
    if sd is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    coaching_response = await get_coaching_report(session_id)
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

    report_response = await get_coaching_report(session_id)
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
                skill_level="intermediate",
                gains=sd.gains,
                weather=sd.weather,
            )

            await store_coaching_context(session_id, ctx)

            response = FollowUpMessage(role="assistant", content=answer)
            await websocket.send_json(response.model_dump())
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Error in coaching chat for session %s", session_id)
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="Internal server error")

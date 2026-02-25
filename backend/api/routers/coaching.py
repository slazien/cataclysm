"""Coaching endpoints: report generation and WebSocket follow-up chat."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.api.schemas.coaching import (
    CoachingReportResponse,
    CornerGradeSchema,
    FollowUpMessage,
    PriorityCornerSchema,
    ReportRequest,
)
from backend.api.services import session_store
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


@router.post("/{session_id}/report", response_model=CoachingReportResponse)
async def generate_report(
    session_id: str,
    body: ReportRequest,
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
    existing = get_coaching_report(session_id)
    if existing is not None:
        if existing.status != "error":
            return existing
        clear_coaching_data(session_id)

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
        from cataclysm.track_match import detect_track_or_lookup

        layout = detect_track_or_lookup(sd.parsed.data, sd.parsed.metadata.track_name)
        landmarks = layout.landmarks if layout else []

        coaching_summaries = [
            s for s in sd.processed.lap_summaries if s.lap_number in sd.coaching_laps
        ]

        report = await asyncio.to_thread(
            generate_coaching_report,
            coaching_summaries,
            sd.all_lap_corners,
            sd.parsed.metadata.track_name,
            gains=sd.gains,
            skill_level=skill_level,
            landmarks=landmarks or None,
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
        )

        store_coaching_report(session_id, response)
    except Exception:
        logger.exception("Failed to generate coaching report for %s", session_id)
        store_coaching_report(
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
) -> CoachingReportResponse:
    """Get the coaching report for a session.

    Returns the stored report, a "generating" status if in progress,
    or 404 if no report has been generated or requested.
    """
    report = get_coaching_report(session_id)
    if report is not None:
        return report

    if is_generating(session_id):
        return CoachingReportResponse(session_id=session_id, status="generating")

    raise HTTPException(
        status_code=404,
        detail=f"No coaching report found for session {session_id}",
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
    """
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

    report_response = get_coaching_report(session_id)
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
    ctx = get_coaching_context(session_id)
    if ctx is None:
        ctx = CoachingContext()
        store_coaching_context(session_id, ctx)

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

            answer = await asyncio.to_thread(
                ask_followup,
                ctx,
                question,
                coaching_report,
                all_lap_corners=sd.all_lap_corners,
                skill_level="intermediate",
                gains=sd.gains,
            )

            store_coaching_context(session_id, ctx)

            response = FollowUpMessage(role="assistant", content=answer)
            await websocket.send_json(response.model_dump())
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Error in coaching chat for session %s", session_id)
        with contextlib.suppress(Exception):
            await websocket.close(code=1011, reason="Internal server error")

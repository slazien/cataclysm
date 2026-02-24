"""Coaching endpoints: report generation and WebSocket follow-up chat."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api.schemas.coaching import (
    CoachingReportResponse,
    FollowUpMessage,
    ReportRequest,
)

router = APIRouter()


@router.post("/{session_id}/report", response_model=CoachingReportResponse)
async def generate_report(
    session_id: str,
    body: ReportRequest,
) -> CoachingReportResponse:
    """Trigger AI coaching report generation for a session.

    Returns 202 if generation is kicked off asynchronously, or the full
    report if it completes quickly.
    """
    # TODO: Phase 2 -- run coaching.generate_coaching_report in background task
    return CoachingReportResponse(
        session_id=session_id,
        status="generating",
    )


@router.get("/{session_id}/report", response_model=CoachingReportResponse)
async def get_report(
    session_id: str,
) -> CoachingReportResponse:
    """Get the coaching report for a session.

    Returns 202 with status='generating' if the report is still being created.
    """
    # TODO: Phase 2 -- fetch report from store, return 202 if not yet ready
    return CoachingReportResponse(
        session_id=session_id,
        status="generating",
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
    try:
        while True:
            data = await websocket.receive_json()
            question = data.get("content", "")

            # TODO: Phase 2 -- call coaching.ask_followup with conversation context
            response = FollowUpMessage(
                role="assistant",
                content=f"Follow-up chat not yet implemented. You asked: {question}",
            )
            await websocket.send_json(response.model_dump())
    except WebSocketDisconnect:
        pass

"""Coaching endpoints: report generation and WebSocket follow-up chat."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CoachingReportResponse:
    """Trigger AI coaching report generation for a session.

    Returns 202 if generation is kicked off asynchronously, or the full
    report if it completes quickly.
    """
    # TODO: Phase 1 — run coaching.generate_coaching_report in background task
    return CoachingReportResponse(
        session_id=session_id,
        status="generating",
    )


@router.get("/{session_id}/report", response_model=CoachingReportResponse)
async def get_report(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CoachingReportResponse:
    """Get the coaching report for a session.

    Returns 202 with status='generating' if the report is still being created.
    """
    # TODO: Phase 1 — fetch report from DB, return 202 if not yet ready
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

            # TODO: Phase 1 — call coaching.ask_followup with conversation context
            response = FollowUpMessage(
                role="assistant",
                content=f"Follow-up chat not yet implemented. You asked: {question}",
            )
            await websocket.send_json(response.model_dump())
    except WebSocketDisconnect:
        pass

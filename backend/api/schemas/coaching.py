"""Pydantic schemas for coaching endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class CornerGradeSchema(BaseModel):
    """Per-corner technique grades from the AI coach."""

    corner: int
    braking: str
    trail_braking: str
    min_speed: str
    throttle: str
    notes: str


class PriorityCornerSchema(BaseModel):
    """A priority corner identified by the AI coach."""

    corner: int
    time_cost_s: float
    issue: str
    tip: str


class CoachingReportResponse(BaseModel):
    """AI-generated coaching report."""

    session_id: str
    status: str  # "ready", "generating", "error"
    summary: str | None = None
    priority_corners: list[PriorityCornerSchema] = []
    corner_grades: list[CornerGradeSchema] = []
    patterns: list[str] = []
    drills: list[str] = []
    validation_failed: bool = False
    validation_violations: list[str] = []


class ReportRequest(BaseModel):
    """Request body for triggering report generation."""

    skill_level: str = "intermediate"


class FollowUpMessage(BaseModel):
    """A single message in the coaching follow-up chat."""

    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request body for the HTTP chat endpoint."""

    content: str
    context: dict[str, object] = {}

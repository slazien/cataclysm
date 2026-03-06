"""Pydantic schemas for coaching endpoints."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SkillLevel = Literal["novice", "intermediate", "advanced"]


class CornerGradeSchema(BaseModel):
    """Per-corner technique grades from the AI coach."""

    corner: int
    braking: str
    trail_braking: str
    min_speed: str
    throttle: str
    notes: str
    braking_reason: str = ""
    trail_braking_reason: str = ""
    min_speed_reason: str = ""
    throttle_reason: str = ""


class PriorityCornerSchema(BaseModel):
    """A priority corner identified by the AI coach."""

    corner: int
    time_cost_s: float = Field(default=0.0, ge=0.0)
    issue: str
    tip: str

    @field_validator("time_cost_s", mode="before")
    @classmethod
    def clamp_time_cost_s(cls, value: object) -> float:
        """Keep user-facing time estimates finite and non-negative."""
        try:
            parsed = float(str(value))
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(parsed) or parsed < 0:
            return 0.0
        return parsed


class CoachingReportResponse(BaseModel):
    """AI-generated coaching report."""

    session_id: str
    status: str  # "ready", "generating", "error"
    skill_level: str = "intermediate"
    summary: str | None = None
    primary_focus: str = ""
    priority_corners: list[PriorityCornerSchema] = Field(default_factory=list)
    corner_grades: list[CornerGradeSchema] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    drills: list[str] = Field(default_factory=list)
    validation_failed: bool = False
    validation_violations: list[str] = Field(default_factory=list)
    regen_remaining: int | None = None
    regen_max: int | None = None
    generation_started_at: str | None = None  # ISO timestamp when generation started
    generation_estimated_s: float | None = None  # estimated total duration in seconds


class ReportRequest(BaseModel):
    """Request body for triggering report generation."""

    skill_level: SkillLevel = "intermediate"
    force: bool = False


class FollowUpMessage(BaseModel):
    """A single message in the coaching follow-up chat."""

    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request body for the HTTP chat endpoint."""

    content: str
    context: dict[str, object] = Field(default_factory=dict)

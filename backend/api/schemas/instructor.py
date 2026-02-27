"""Pydantic schemas for instructor endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class StudentSummary(BaseModel):
    """Summary of a linked student."""

    student_id: str
    name: str
    email: str
    avatar_url: str | None = None
    linked_at: str | None = None
    recent_flags: list[str] = []


class StudentListResponse(BaseModel):
    """Response for listing students."""

    students: list[StudentSummary]


class InviteResponse(BaseModel):
    """Response after creating an invite code."""

    invite_code: str


class AcceptInviteRequest(BaseModel):
    """Request to accept an invite."""

    code: str


class FlagSchema(BaseModel):
    """A student flag."""

    id: int
    flag_type: str
    description: str
    session_id: str | None = None
    auto_generated: bool = True
    created_at: str | None = None


class FlagListResponse(BaseModel):
    """Response for listing flags."""

    flags: list[FlagSchema]


class CreateFlagRequest(BaseModel):
    """Request to create a manual flag."""

    session_id: str | None = None
    flag_type: str
    description: str


class SessionWithFlags(BaseModel):
    """A session with its flags."""

    session_id: str
    track_name: str
    session_date: str | None = None
    best_lap_time_s: float | None = None
    consistency_score: float | None = None
    n_laps: int | None = None
    flags: list[FlagSchema] = []


class StudentSessionsResponse(BaseModel):
    """Response for listing a student's sessions."""

    sessions: list[SessionWithFlags]

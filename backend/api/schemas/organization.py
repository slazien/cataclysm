"""Pydantic schemas for organization (HPDE org/club) endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class OrgCreate(BaseModel):
    """Request to create an organization."""

    name: str
    slug: str
    logo_url: str | None = None
    brand_color: str | None = None


class OrgUpdate(BaseModel):
    """Request to update an organization."""

    name: str | None = None
    logo_url: str | None = None
    brand_color: str | None = None


class OrgSummary(BaseModel):
    """Summary of an organization."""

    id: str
    name: str
    slug: str
    logo_url: str | None = None
    brand_color: str | None = None
    member_count: int = 0


class OrgListResponse(BaseModel):
    """Response for listing organizations."""

    organizations: list[OrgSummary]


class MemberSchema(BaseModel):
    """An org membership entry."""

    user_id: str
    name: str
    email: str
    role: str
    run_group: str | None = None
    joined_at: str | None = None


class MemberListResponse(BaseModel):
    """Response for listing org members."""

    members: list[MemberSchema]


class AddMemberRequest(BaseModel):
    """Request to add a member to an organization."""

    user_id: str
    role: str = "student"
    run_group: str | None = None


class EventCreate(BaseModel):
    """Request to create an event."""

    name: str
    track_name: str
    event_date: str
    run_groups: list[str] | None = None


class EventSchema(BaseModel):
    """An organization event."""

    id: str
    org_id: str
    name: str
    track_name: str
    event_date: str
    run_groups: list[str] | None = None


class EventListResponse(BaseModel):
    """Response for listing events."""

    events: list[EventSchema]

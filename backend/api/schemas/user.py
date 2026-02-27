"""Pydantic schemas for user endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserSchema(BaseModel):
    """Public user representation returned by /api/auth/me."""

    id: str
    email: str
    name: str
    avatar_url: str | None = None
    skill_level: str = "intermediate"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserUpdateSchema(BaseModel):
    """Partial update payload for PATCH /api/auth/me."""

    skill_level: str | None = None

"""Pydantic schemas for the stickies API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

StickyTone = Literal["amber", "sky", "mint", "rose", "violet", "peach"]
StickyViewScope = Literal["report", "deep-dive", "progress", "debrief", "global"]


class StickyCreate(BaseModel):
    """Request body for creating a sticky note."""

    pos_x: float = Field(..., ge=0.0, le=1.0)
    pos_y: float = Field(..., ge=0.0, le=1.0)
    content: str = Field("", max_length=2000)
    tone: StickyTone = "amber"
    collapsed: bool = True
    view_scope: StickyViewScope = "global"


class StickyUpdate(BaseModel):
    """Request body for updating a sticky (partial)."""

    pos_x: float | None = Field(None, ge=0.0, le=1.0)
    pos_y: float | None = Field(None, ge=0.0, le=1.0)
    content: str | None = Field(None, max_length=2000)
    tone: StickyTone | None = None
    collapsed: bool | None = None
    view_scope: StickyViewScope | None = None


class StickyResponse(BaseModel):
    """A sticky note returned from the API."""

    id: str
    user_id: str
    pos_x: float
    pos_y: float
    content: str
    tone: str
    collapsed: bool
    view_scope: str
    created_at: str
    updated_at: str


class StickiesList(BaseModel):
    """List of stickies for the current user."""

    items: list[StickyResponse]
    total: int

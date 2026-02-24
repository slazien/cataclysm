"""Pydantic schemas for cross-session trend endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TrendAnalysisResponse(BaseModel):
    """Cross-session trend data for a single track (serialized dataclass)."""

    track_name: str
    data: dict[str, Any]


class MilestoneSchema(BaseModel):
    """A notable achievement detected across sessions."""

    session_id: str
    session_date: str
    category: str
    description: str
    value: float


class MilestoneResponse(BaseModel):
    """List of milestones for a track."""

    track_name: str
    milestones: list[MilestoneSchema]

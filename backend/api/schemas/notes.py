"""Pydantic schemas for the notes API."""

from __future__ import annotations

from pydantic import BaseModel, Field

_VALID_ANCHOR_TYPES = frozenset({"corner", "lap", "chart", "coaching", "metric"})
_VALID_COLORS = frozenset({"yellow", "blue", "green", "pink", "purple"})


class NoteCreate(BaseModel):
    """Request body for creating a note."""

    session_id: str | None = None
    anchor_type: str | None = None
    anchor_id: str | None = None
    anchor_meta: dict[str, object] | None = None
    content: str = Field(..., min_length=1, max_length=10_000)
    is_pinned: bool = False
    color: str | None = None

    def model_post_init(self, __context: object) -> None:
        """Validate anchor_type and color values."""
        if self.anchor_type is not None and self.anchor_type not in _VALID_ANCHOR_TYPES:
            msg = f"anchor_type must be one of {sorted(_VALID_ANCHOR_TYPES)}"
            raise ValueError(msg)
        if self.color is not None and self.color not in _VALID_COLORS:
            msg = f"color must be one of {sorted(_VALID_COLORS)}"
            raise ValueError(msg)


class NoteUpdate(BaseModel):
    """Request body for updating a note (partial)."""

    content: str | None = Field(None, min_length=1, max_length=10_000)
    is_pinned: bool | None = None
    color: str | None = None
    anchor_type: str | None = None
    anchor_id: str | None = None
    anchor_meta: dict[str, object] | None = None

    def model_post_init(self, __context: object) -> None:
        """Validate anchor_type and color values when provided."""
        if self.anchor_type is not None and self.anchor_type not in _VALID_ANCHOR_TYPES:
            msg = f"anchor_type must be one of {sorted(_VALID_ANCHOR_TYPES)}"
            raise ValueError(msg)
        if self.color is not None and self.color not in _VALID_COLORS:
            msg = f"color must be one of {sorted(_VALID_COLORS)}"
            raise ValueError(msg)


class NoteResponse(BaseModel):
    """A note returned from the API."""

    id: str
    user_id: str
    session_id: str | None
    anchor_type: str | None
    anchor_id: str | None
    anchor_meta: dict[str, object] | None
    content: str
    is_pinned: bool
    color: str | None
    created_at: str
    updated_at: str


class NotesList(BaseModel):
    """Paginated list of notes."""

    items: list[NoteResponse]
    total: int

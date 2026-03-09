"""Notes CRUD endpoints for session stickies and global notepad."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.db.models import NoteDB
from backend.api.db.models import Session as SessionModel
from backend.api.dependencies import AuthenticatedUser, get_current_user, get_user_or_anon
from backend.api.schemas.notes import NoteCreate, NoteResponse, NotesList, NoteUpdate

router = APIRouter()
_logger = logging.getLogger(__name__)

_MAX_NOTES_PER_USER = 500


def _to_response(note: NoteDB) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        user_id=note.user_id,
        session_id=note.session_id,
        anchor_type=note.anchor_type,
        anchor_id=note.anchor_id,
        anchor_meta=note.anchor_meta,
        content=note.content,
        is_pinned=note.is_pinned,
        color=note.color,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


@router.post("", status_code=201)
async def create_note(
    body: NoteCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NoteResponse:
    """Create a new note."""
    # Check note limit — use SQL COUNT (not load-all)
    count_q = (
        select(func.count())
        .select_from(NoteDB)
        .where(
            NoteDB.user_id == current_user.user_id,
        )
    )
    count = (await db.execute(count_q)).scalar_one()
    if count >= _MAX_NOTES_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum {_MAX_NOTES_PER_USER} notes per user",
        )

    # Verify session ownership if session_id provided
    if body.session_id:
        session = await db.get(SessionModel, body.session_id)
        if session is None or session.user_id != current_user.user_id:
            raise HTTPException(status_code=404, detail="Session not found")

    note = NoteDB(
        id=str(uuid.uuid4()),
        user_id=current_user.user_id,
        session_id=body.session_id,
        anchor_type=body.anchor_type,
        anchor_id=body.anchor_id,
        anchor_meta=body.anchor_meta,  # type: ignore[arg-type]
        content=body.content,
        is_pinned=body.is_pinned,
        color=body.color,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    _logger.info(
        "Note created: id=%s user=%s session=%s",
        note.id,
        current_user.user_id,
        note.session_id,
    )
    return _to_response(note)


@router.get("")
async def list_notes(
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
    session_id: str | None = Query(None, description="Filter by session ID"),
    global_only: bool = Query(False, description="Only return global (non-session) notes"),
    anchor_type: str | None = Query(None, description="Filter by anchor type"),
) -> NotesList:
    """List notes for the current user, optionally filtered."""
    if current_user.user_id == "anon":
        return NotesList(items=[], total=0)
    q = select(NoteDB).where(NoteDB.user_id == current_user.user_id)

    if session_id is not None:
        q = q.where(NoteDB.session_id == session_id)
    elif global_only:
        q = q.where(NoteDB.session_id.is_(None))

    if anchor_type is not None:
        q = q.where(NoteDB.anchor_type == anchor_type)

    q = q.order_by(NoteDB.is_pinned.desc(), NoteDB.updated_at.desc())

    result = await db.execute(q)
    notes = result.scalars().all()

    return NotesList(
        items=[_to_response(n) for n in notes],
        total=len(notes),
    )


@router.get("/{note_id}")
async def get_note(
    note_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NoteResponse:
    """Get a single note by ID."""
    note = await db.get(NoteDB, note_id)
    if note is None or note.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Note not found")
    return _to_response(note)


@router.patch("/{note_id}")
async def update_note(
    note_id: str,
    body: NoteUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NoteResponse:
    """Update a note (partial update)."""
    note = await db.get(NoteDB, note_id)
    if note is None or note.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Note not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)

    await db.commit()
    await db.refresh(note)
    return _to_response(note)


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a note."""
    note = await db.get(NoteDB, note_id)
    if note is None or note.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Note not found")

    await db.delete(note)
    await db.commit()
    _logger.info("Note deleted: id=%s user=%s", note_id, current_user.user_id)

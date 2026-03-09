"""Stickies CRUD endpoints for placeable sticky notes."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.db.models import StickyDB
from backend.api.dependencies import AuthenticatedUser, get_current_user, get_user_or_anon
from backend.api.schemas.stickies import (
    StickiesList,
    StickyCreate,
    StickyResponse,
    StickyUpdate,
    StickyViewScope,
)

router = APIRouter()
_logger = logging.getLogger(__name__)

_MAX_STICKIES_PER_USER = 50


def _to_response(sticky: StickyDB) -> StickyResponse:
    return StickyResponse(
        id=sticky.id,
        user_id=sticky.user_id,
        pos_x=sticky.pos_x,
        pos_y=sticky.pos_y,
        content=sticky.content,
        tone=sticky.tone,
        collapsed=sticky.collapsed,
        view_scope=sticky.view_scope,
        created_at=sticky.created_at.isoformat(),
        updated_at=sticky.updated_at.isoformat(),
    )


@router.post("", status_code=201)
async def create_sticky(
    body: StickyCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StickyResponse:
    """Create a new sticky note."""
    count_q = (
        select(func.count()).select_from(StickyDB).where(StickyDB.user_id == current_user.user_id)
    )
    count = (await db.execute(count_q)).scalar_one()
    if count >= _MAX_STICKIES_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum {_MAX_STICKIES_PER_USER} stickies per user",
        )

    sticky = StickyDB(
        id=str(uuid.uuid4()),
        user_id=current_user.user_id,
        pos_x=body.pos_x,
        pos_y=body.pos_y,
        content=body.content,
        tone=body.tone,
        collapsed=body.collapsed,
        view_scope=body.view_scope,
    )
    db.add(sticky)
    await db.commit()
    await db.refresh(sticky)
    _logger.info("Sticky created: id=%s user=%s", sticky.id, current_user.user_id)
    return _to_response(sticky)


@router.get("")
async def list_stickies(
    current_user: Annotated[AuthenticatedUser, Depends(get_user_or_anon)],
    db: Annotated[AsyncSession, Depends(get_db)],
    view_scope: Annotated[StickyViewScope | None, Query(description="Filter by view scope")] = None,
) -> StickiesList:
    """List stickies for the current user."""
    if current_user.user_id == "anon":
        return StickiesList(items=[], total=0)
    q = select(StickyDB).where(StickyDB.user_id == current_user.user_id)

    if view_scope is not None:
        q = q.where(StickyDB.view_scope == view_scope)

    q = q.order_by(StickyDB.updated_at.desc())
    result = await db.execute(q)
    stickies = result.scalars().all()

    return StickiesList(
        items=[_to_response(s) for s in stickies],
        total=len(stickies),
    )


@router.patch("/{sticky_id}")
async def update_sticky(
    sticky_id: str,
    body: StickyUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StickyResponse:
    """Update a sticky (partial update)."""
    sticky = await db.get(StickyDB, sticky_id)
    if sticky is None or sticky.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Sticky not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sticky, field, value)

    await db.commit()
    await db.refresh(sticky)
    return _to_response(sticky)


@router.delete("/{sticky_id}", status_code=204)
async def delete_sticky(
    sticky_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a sticky note."""
    sticky = await db.get(StickyDB, sticky_id)
    if sticky is None or sticky.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Sticky not found")

    await db.delete(sticky)
    await db.commit()
    _logger.info("Sticky deleted: id=%s user=%s", sticky_id, current_user.user_id)

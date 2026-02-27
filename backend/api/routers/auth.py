"""Auth router — user profile endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.db.models import User
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.user import UserSchema, UserUpdateSchema

router = APIRouter()


@router.get("/me", response_model=UserSchema)
async def get_me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Return the current user profile, creating it on first login (upsert)."""
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            id=current_user.user_id,
            email=current_user.email,
            name=current_user.name,
            avatar_url=current_user.picture,
        )
        db.add(user)
        await db.flush()
    else:
        # Update mutable fields from the latest JWT claims
        user.name = current_user.name
        user.email = current_user.email
        if current_user.picture is not None:
            user.avatar_url = current_user.picture

    return user


_VALID_SKILL_LEVELS = {"novice", "intermediate", "advanced"}


@router.patch("/me", response_model=UserSchema)
async def update_me(
    body: UserUpdateSchema,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Update the current user's profile (e.g. skill_level)."""
    from fastapi import HTTPException

    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.skill_level is not None:
        if body.skill_level not in _VALID_SKILL_LEVELS:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid skill_level. Must be one of: {', '.join(sorted(_VALID_SKILL_LEVELS))}",
            )
        user.skill_level = body.skill_level

    return user

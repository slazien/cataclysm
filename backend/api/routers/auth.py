"""Auth router — user profile endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.db.models import User
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.user import UserSchema

router = APIRouter()


@router.get("/me", response_model=UserSchema)
async def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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

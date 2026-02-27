"""Season Wrapped / Year in Review endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.wrapped import WrappedResponse
from backend.api.services.wrapped import compute_wrapped

router = APIRouter()


@router.get("/{year}", response_model=WrappedResponse)
async def get_wrapped(
    year: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> WrappedResponse:
    """Get annual personalized recap for a given year."""
    result = await compute_wrapped(year)
    return WrappedResponse(**result)

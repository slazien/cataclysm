"""Instructor dashboard endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.database import get_db
from backend.api.db.models import InstructorStudent, User
from backend.api.dependencies import AuthenticatedUser, get_current_user
from backend.api.schemas.instructor import (
    CreateFlagRequest,
    FlagListResponse,
    FlagSchema,
    InviteResponse,
    SessionWithFlags,
    StudentListResponse,
    StudentSessionsResponse,
    StudentSummary,
)
from backend.api.services.instructor_store import (
    accept_invite,
    add_manual_flag,
    create_invite,
    get_student_flags,
    get_student_sessions,
    get_students,
    remove_student,
)

router = APIRouter()


async def _require_instructor(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> str:
    """Verify the current user has instructor role. Returns user_id."""
    user = await db.get(User, current_user.user_id)
    if user is None or getattr(user, "role", "driver") != "instructor":
        raise HTTPException(status_code=403, detail="Instructor role required")
    return current_user.user_id


@router.get("/students", response_model=StudentListResponse)
async def list_students(
    instructor_id: Annotated[str, Depends(_require_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudentListResponse:
    """List all linked students for the current instructor."""
    rows = await get_students(db, instructor_id)
    return StudentListResponse(
        students=[StudentSummary(**r) for r in rows],  # type: ignore[arg-type]
    )


@router.post("/invite", response_model=InviteResponse)
async def generate_invite(
    instructor_id: Annotated[str, Depends(_require_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InviteResponse:
    """Generate an invite code for a student."""
    code = await create_invite(db, instructor_id)
    await db.commit()
    return InviteResponse(invite_code=code)


@router.post("/accept/{code}")
async def accept_invite_code(
    code: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Student accepts an invite code to link with an instructor."""
    success = await accept_invite(db, current_user.user_id, code)
    if not success:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")
    await db.commit()
    return {"status": "linked"}


@router.delete("/students/{student_id}")
async def unlink_student(
    student_id: str,
    instructor_id: Annotated[str, Depends(_require_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Remove an instructor-student link."""
    success = await remove_student(db, instructor_id, student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student link not found")
    await db.commit()
    return {"status": "removed"}


@router.get("/students/{student_id}/sessions", response_model=StudentSessionsResponse)
async def student_sessions(
    student_id: str,
    instructor_id: Annotated[str, Depends(_require_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudentSessionsResponse:
    """Get a student's sessions with flags."""
    # Verify the student is linked to this instructor
    result = await db.execute(
        select(InstructorStudent).where(
            InstructorStudent.instructor_id == instructor_id,
            InstructorStudent.student_id == student_id,
            InstructorStudent.status == "active",
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Student not linked")

    rows = await get_student_sessions(db, student_id)
    return StudentSessionsResponse(
        sessions=[SessionWithFlags(**r) for r in rows],  # type: ignore[arg-type]
    )


@router.get("/students/{student_id}/flags", response_model=FlagListResponse)
async def student_flags(
    student_id: str,
    instructor_id: Annotated[str, Depends(_require_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FlagListResponse:
    """Get flags for a student."""
    rows = await get_student_flags(db, student_id)
    return FlagListResponse(
        flags=[FlagSchema(**r) for r in rows],  # type: ignore[arg-type]
    )


@router.post("/students/{student_id}/flags", response_model=FlagSchema)
async def create_flag(
    student_id: str,
    body: CreateFlagRequest,
    instructor_id: Annotated[str, Depends(_require_instructor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FlagSchema:
    """Create a manual flag for a student."""
    valid_types = {"attention", "safety", "improvement", "praise"}
    if body.flag_type not in valid_types:
        raise HTTPException(status_code=422, detail=f"flag_type must be one of {valid_types}")

    flag_id = await add_manual_flag(
        db, student_id, body.session_id, body.flag_type, body.description
    )
    await db.commit()
    return FlagSchema(
        id=flag_id,
        flag_type=body.flag_type,
        description=body.description,
        session_id=body.session_id,
        auto_generated=False,
    )

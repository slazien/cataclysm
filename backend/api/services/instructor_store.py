"""Instructor dashboard business logic.

Manages student links, invite codes, and flag queries.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import InstructorStudent, Session, StudentFlag, User

logger = logging.getLogger(__name__)


def _generate_invite_code() -> str:
    """Generate a short URL-safe invite code."""
    return secrets.token_urlsafe(8)


async def get_students(db: AsyncSession, instructor_id: str) -> list[dict[str, object]]:
    """List all linked students for an instructor."""
    result = await db.execute(
        select(InstructorStudent, User)
        .join(User, InstructorStudent.student_id == User.id)
        .where(
            InstructorStudent.instructor_id == instructor_id,
            InstructorStudent.status == "active",
        )
    )
    rows = result.all()

    students: list[dict[str, object]] = []
    for row in rows:
        link: InstructorStudent = row[0]  # type: ignore[assignment]
        user: User = row[1]  # type: ignore[assignment]

        # Count flags for this student
        flag_result = await db.execute(
            select(StudentFlag.flag_type)
            .where(StudentFlag.student_id == user.id)
            .order_by(StudentFlag.created_at.desc())
            .limit(20)
        )
        recent_flags = [r[0] for r in flag_result.all()]

        students.append(
            {
                "student_id": user.id,
                "name": user.name,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "linked_at": link.created_at.isoformat() if link.created_at else None,
                "recent_flags": recent_flags,
            }
        )

    return students


async def create_invite(db: AsyncSession, instructor_id: str) -> str:
    """Generate an invite code for a student to link with this instructor."""
    code = _generate_invite_code()
    db.add(
        InstructorStudent(
            instructor_id=instructor_id,
            student_id="",  # placeholder until accepted
            invite_code=code,
            status="pending",
            created_at=datetime.now(UTC),
        )
    )
    await db.flush()
    return code


async def accept_invite(db: AsyncSession, student_id: str, code: str) -> bool:
    """Student accepts an invite code, linking to the instructor."""
    result = await db.execute(
        select(InstructorStudent).where(
            InstructorStudent.invite_code == code,
            InstructorStudent.status == "pending",
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        return False

    link.student_id = student_id
    link.status = "active"
    link.invite_code = None  # one-time use
    await db.flush()
    return True


async def remove_student(db: AsyncSession, instructor_id: str, student_id: str) -> bool:
    """Remove an instructor-student link."""
    result = await db.execute(
        select(InstructorStudent).where(
            InstructorStudent.instructor_id == instructor_id,
            InstructorStudent.student_id == student_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        return False

    link.status = "removed"
    await db.flush()
    return True


async def get_student_sessions(
    db: AsyncSession, student_id: str, limit: int = 20
) -> list[dict[str, object]]:
    """Get recent sessions for a student with flag counts."""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == student_id)
        .order_by(Session.session_date.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()

    session_list: list[dict[str, object]] = []
    for s in sessions:
        # Get flags for this session
        flag_result = await db.execute(
            select(StudentFlag).where(StudentFlag.session_id == s.session_id)
        )
        flags = [
            {
                "id": f.id,
                "flag_type": f.flag_type,
                "description": f.description,
                "auto_generated": f.auto_generated,
            }
            for f in flag_result.scalars().all()
        ]

        session_list.append(
            {
                "session_id": s.session_id,
                "track_name": s.track_name,
                "session_date": s.session_date.isoformat() if s.session_date else None,
                "best_lap_time_s": s.best_lap_time_s,
                "consistency_score": s.consistency_score,
                "n_laps": s.n_laps,
                "flags": flags,
            }
        )

    return session_list


async def get_student_flags(
    db: AsyncSession, student_id: str, limit: int = 50
) -> list[dict[str, object]]:
    """Get flags for a student."""
    result = await db.execute(
        select(StudentFlag)
        .where(StudentFlag.student_id == student_id)
        .order_by(StudentFlag.created_at.desc())
        .limit(limit)
    )
    flags = result.scalars().all()

    return [
        {
            "id": f.id,
            "flag_type": f.flag_type,
            "description": f.description,
            "session_id": f.session_id,
            "auto_generated": f.auto_generated,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in flags
    ]


async def add_manual_flag(
    db: AsyncSession,
    student_id: str,
    session_id: str | None,
    flag_type: str,
    description: str,
) -> int:
    """Instructor manually adds a flag for a student."""
    flag = StudentFlag(
        student_id=student_id,
        session_id=session_id,
        flag_type=flag_type,
        description=description,
        auto_generated=False,
        created_at=datetime.now(UTC),
    )
    db.add(flag)
    await db.flush()
    return int(flag.id)

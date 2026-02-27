"""Auto-flagging engine for instructor dashboard.

Evaluates session data and coaching reports to generate student flags.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import CoachingReport, Session, StudentFlag

logger = logging.getLogger(__name__)

# Flag criteria thresholds
ATTENTION_CONSISTENCY_THRESHOLD = 50
SAFETY_BRAKE_FADE_CHECK = True
IMPROVEMENT_PB_CHECK = True
PRAISE_MIN_GRADE = "B"

_PASSING_GRADES = {"A+", "A", "A-", "B+", "B"}


async def auto_flag_session(
    db: AsyncSession,
    student_id: str,
    session_id: str,
) -> list[str]:
    """Evaluate a session and generate auto-flags for the student.

    Returns list of flag types generated.
    """
    generated: list[str] = []

    # Get session data
    session = await db.get(Session, session_id)
    if session is None:
        return generated

    # Check attention: low consistency score
    if (
        session.consistency_score is not None
        and session.consistency_score < ATTENTION_CONSISTENCY_THRESHOLD
    ):
        db.add(
            StudentFlag(
                student_id=student_id,
                session_id=session_id,
                flag_type="attention",
                description=f"Low consistency score: {session.consistency_score:.0f}",
                auto_generated=True,
                created_at=datetime.now(UTC),
            )
        )
        generated.append("attention")

    # Check improvement: is this a PB?
    result = await db.execute(
        select(Session.best_lap_time_s)
        .where(
            Session.user_id == student_id,
            Session.track_name == session.track_name,
            Session.session_id != session_id,
            Session.best_lap_time_s.isnot(None),
        )
        .order_by(Session.best_lap_time_s.asc())
        .limit(1)
    )
    prev_best = result.scalar()
    if session.best_lap_time_s is not None and (
        prev_best is None or session.best_lap_time_s < prev_best
    ):
        desc = "New personal best!"
        if prev_best is not None:
            delta = prev_best - session.best_lap_time_s
            desc = f"New PB! {delta:.3f}s faster than previous best"
        db.add(
            StudentFlag(
                student_id=student_id,
                session_id=session_id,
                flag_type="improvement",
                description=desc,
                auto_generated=True,
                created_at=datetime.now(UTC),
            )
        )
        generated.append("improvement")

    # Check coaching report for praise / safety
    report_result = await db.execute(
        select(CoachingReport.report_json)
        .where(CoachingReport.session_id == session_id)
        .order_by(CoachingReport.created_at.desc())
        .limit(1)
    )
    report_json = report_result.scalar()
    if report_json:
        corner_grades = report_json.get("corner_grades", [])

        # Praise: all corner grades B or above
        if corner_grades and all(
            cg.get("braking", "C") in _PASSING_GRADES
            and cg.get("trail_braking", "C") in _PASSING_GRADES
            for cg in corner_grades
        ):
            db.add(
                StudentFlag(
                    student_id=student_id,
                    session_id=session_id,
                    flag_type="praise",
                    description="All corner grades B or above — excellent driving!",
                    auto_generated=True,
                    created_at=datetime.now(UTC),
                )
            )
            generated.append("praise")

        # Safety: check for patterns suggesting issues
        patterns = report_json.get("patterns", [])
        for pattern in patterns:
            if isinstance(pattern, str) and any(
                kw in pattern.lower() for kw in ["brake fade", "overdriving", "spin", "off-track"]
            ):
                db.add(
                    StudentFlag(
                        student_id=student_id,
                        session_id=session_id,
                        flag_type="safety",
                        description=f"Safety concern detected: {pattern}",
                        auto_generated=True,
                        created_at=datetime.now(UTC),
                    )
                )
                generated.append("safety")
                break

    if generated:
        await db.flush()
        logger.info("Auto-flagged session %s for student %s: %s", session_id, student_id, generated)

    return generated

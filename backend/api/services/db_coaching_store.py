"""DB-backed coaching persistence for reports and chat contexts.

Uses the CoachingReport and CoachingContext ORM models to persist
coaching data to PostgreSQL, surviving container restarts on Railway.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import CoachingContext as CoachingContextModel
from backend.api.db.models import CoachingReport as CoachingReportModel
from backend.api.schemas.coaching import CoachingReportResponse

logger = logging.getLogger(__name__)


async def upsert_coaching_report_db(
    db: AsyncSession,
    session_id: str,
    report: CoachingReportResponse,
    skill_level: str,
) -> None:
    """Insert or update a coaching report row for the given session."""
    result = await db.execute(
        select(CoachingReportModel).where(CoachingReportModel.session_id == session_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.report_json = report.model_dump()
        existing.skill_level = skill_level
    else:
        db.add(
            CoachingReportModel(
                session_id=session_id,
                skill_level=skill_level,
                report_json=report.model_dump(),
            )
        )
    await db.flush()


async def get_coaching_report_db(
    db: AsyncSession,
    session_id: str,
) -> CoachingReportResponse | None:
    """Load a coaching report from DB, or None if not found."""
    result = await db.execute(
        select(CoachingReportModel).where(CoachingReportModel.session_id == session_id)
    )
    row = result.scalar_one_or_none()
    if row is None or row.report_json is None:
        return None
    return CoachingReportResponse.model_validate(row.report_json)


async def upsert_coaching_context_db(
    db: AsyncSession,
    session_id: str,
    messages: list[dict[str, str]],
) -> None:
    """Insert or update the coaching chat context for the given session."""
    result = await db.execute(
        select(CoachingContextModel).where(CoachingContextModel.session_id == session_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.messages_json = messages  # type: ignore[assignment]
    else:
        db.add(
            CoachingContextModel(
                session_id=session_id,
                messages_json=messages,  # type: ignore[arg-type]
            )
        )
    await db.flush()


async def get_coaching_context_db(
    db: AsyncSession,
    session_id: str,
) -> list[dict[str, str]] | None:
    """Load coaching chat messages from DB, or None if not found."""
    result = await db.execute(
        select(CoachingContextModel).where(CoachingContextModel.session_id == session_id)
    )
    row = result.scalar_one_or_none()
    if row is None or row.messages_json is None:
        return None
    return row.messages_json  # type: ignore[return-value]


async def delete_coaching_data_db(
    db: AsyncSession,
    session_id: str,
) -> None:
    """Delete coaching report and context rows for a session."""
    await db.execute(
        delete(CoachingReportModel).where(CoachingReportModel.session_id == session_id)
    )
    await db.execute(
        delete(CoachingContextModel).where(CoachingContextModel.session_id == session_id)
    )
    await db.flush()

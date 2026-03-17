"""DB persistence for LapTagStore: load/save lap tags to PostgreSQL."""

from __future__ import annotations

import logging

from cataclysm.lap_tags import LapTagStore
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.db.models import LapTag

logger = logging.getLogger(__name__)


async def load_lap_tags(db: AsyncSession, session_id: str) -> LapTagStore:
    """Load all lap tags for a session from DB into a LapTagStore.

    Returns an empty LapTagStore if the session has no tags.
    """
    result = await db.execute(select(LapTag).where(LapTag.session_id == session_id))
    rows = result.scalars().all()
    store = LapTagStore()
    for row in rows:
        store.add_tag(row.lap_number, row.tag)
    return store


async def save_lap_tags(db: AsyncSession, session_id: str, store: LapTagStore) -> None:
    """Replace all lap tags for a session in DB with current store state.

    Uses delete-all + recreate pattern (not upsert) for simplicity.
    """
    await db.execute(delete(LapTag).where(LapTag.session_id == session_id))
    for lap_number, tags in store.tags.items():
        for tag in tags:
            db.add(LapTag(session_id=session_id, lap_number=lap_number, tag=tag))
    await db.commit()

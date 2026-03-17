"""Tests for lap_tag_store: DB load/save round-trip."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from cataclysm.lap_tags import LapTagStore
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.services.lap_tag_store import load_lap_tags, save_lap_tags
from backend.tests.conftest import _test_session_factory


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh async session from the test factory."""
    async with _test_session_factory() as session:
        yield session


class TestLapTagStore:
    @pytest.mark.asyncio
    async def test_save_and_load_round_trip(self, db_session: AsyncSession) -> None:
        """Save a store with multiple laps/tags; load it back; verify identical."""
        store = LapTagStore()
        store.add_tag(1, "traffic")
        store.add_tag(1, "rain")
        store.add_tag(3, "off-line")
        store.add_tag(7, "clean")

        await save_lap_tags(db_session, "sess-rt", store)

        loaded = await load_lap_tags(db_session, "sess-rt")
        assert loaded.get_tags(1) == {"traffic", "rain"}
        assert loaded.get_tags(3) == {"off-line"}
        assert loaded.get_tags(7) == {"clean"}
        assert loaded.get_tags(99) == set()  # lap not in store

    @pytest.mark.asyncio
    async def test_save_replaces_existing(self, db_session: AsyncSession) -> None:
        """Save once, save again with different tags; verify old tags gone."""
        first = LapTagStore()
        first.add_tag(2, "traffic")
        first.add_tag(4, "rain")
        await save_lap_tags(db_session, "sess-replace", first)

        second = LapTagStore()
        second.add_tag(2, "clean")
        second.add_tag(5, "cold-tires")
        await save_lap_tags(db_session, "sess-replace", second)

        loaded = await load_lap_tags(db_session, "sess-replace")
        # Old tags gone
        assert "traffic" not in loaded.get_tags(2)
        assert loaded.get_tags(4) == set()
        # New tags present
        assert loaded.get_tags(2) == {"clean"}
        assert loaded.get_tags(5) == {"cold-tires"}

    @pytest.mark.asyncio
    async def test_load_empty_session(self, db_session: AsyncSession) -> None:
        """Load from a session_id that has no tags returns empty LapTagStore."""
        loaded = await load_lap_tags(db_session, "sess-nonexistent")
        assert loaded.tags == {}
        assert loaded.all_tags() == set()

"""Extended tests for various backend services — covers uncovered lines.

Targets:
  - pipeline.py: invalidate_physics_cache, invalidate_profile_cache, LRU eviction
  - db_session_store.py: ensure_user_exists (new user, update existing)
  - session_store.py: sync_user_id (lines 150-156), claim_session failure (line 202)
  - db_coaching_store.py: upsert update branch (lines 36-37), get_any returns None
  - comparison.py: _normalize_track_name, _best_lap_distance_m None path (lines 59-62)
  - equipment_store.py: sync_user_id, get_default_profile, delete_session_equipment
  - coaching_store.py: get_any_coaching_report DB fallback (lines 118-119)
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from backend.api.db.models import Session as SessionModel
from backend.api.db.models import User as UserModel
from backend.api.dependencies import AuthenticatedUser
from backend.api.schemas.coaching import CoachingReportResponse
from backend.api.services import pipeline
from backend.api.services.coaching_store import (
    clear_all_coaching,
)
from backend.api.services.comparison import _normalize_track_name, validate_session_comparison
from backend.api.services.session_store import claim_session, sync_user_id
from backend.tests.conftest import _TEST_USER, _test_session_factory

# ---------------------------------------------------------------------------
# pipeline.py — cache invalidation
# ---------------------------------------------------------------------------


class TestPipelineCache:
    """Tests for physics cache invalidation functions."""

    def setup_method(self) -> None:
        """Clear the physics cache before each test."""
        pipeline._physics_cache.clear()

    def test_set_and_get_physics_cached(self) -> None:
        """_set_physics_cached stores and _get_physics_cached retrieves."""
        pipeline._set_physics_cached("sess1", "optimal", {"result": 42})
        result = pipeline._get_physics_cached("sess1", "optimal")
        assert result == {"result": 42}

    def test_get_physics_cached_returns_none_when_empty(self) -> None:
        """_get_physics_cached returns None when no entry exists."""
        result = pipeline._get_physics_cached("nonexistent", "endpoint")
        assert result is None

    def test_get_physics_cached_returns_none_after_expiry(self) -> None:
        """_get_physics_cached returns None when entry is past TTL."""
        cache_key = ("sess-expired:endpoint", None)
        pipeline._physics_cache[cache_key] = (
            {"data": 1},
            time.time() - pipeline.PHYSICS_CACHE_TTL_S - 1,
        )
        result = pipeline._get_physics_cached("sess-expired", "endpoint")
        assert result is None

    def test_invalidate_physics_cache_removes_session_entries(self) -> None:
        """invalidate_physics_cache clears all entries for a session."""
        pipeline._set_physics_cached("sess-abc", "optimal", {"x": 1})
        pipeline._set_physics_cached("sess-abc", "ideal", {"y": 2})
        pipeline._set_physics_cached("sess-xyz", "optimal", {"z": 3})

        pipeline.invalidate_physics_cache("sess-abc")
        assert pipeline._get_physics_cached("sess-abc", "optimal") is None
        assert pipeline._get_physics_cached("sess-abc", "ideal") is None
        # Other session's cache should be intact
        assert pipeline._get_physics_cached("sess-xyz", "optimal") == {"z": 3}

    def test_invalidate_physics_cache_no_op_when_empty(self) -> None:
        """invalidate_physics_cache on unknown session does not raise."""
        pipeline.invalidate_physics_cache("no-such-session")  # should not raise

    @pytest.mark.asyncio
    @patch("backend.api.services.pipeline.db_invalidate_profile", new_callable=AsyncMock)
    async def test_invalidate_profile_cache_removes_profile_entries(
        self, mock_db_inv: AsyncMock
    ) -> None:
        """invalidate_profile_cache clears all entries using a specific profile."""
        # Manually insert cache entries with a profile id
        pipeline._physics_cache[("sess1:optimal", "profile-abc")] = ({"r": 1}, time.time())
        pipeline._physics_cache[("sess2:optimal", "profile-abc")] = ({"r": 2}, time.time())
        pipeline._physics_cache[("sess3:optimal", "profile-xyz")] = ({"r": 3}, time.time())

        await pipeline.invalidate_profile_cache("profile-abc")

        assert ("sess1:optimal", "profile-abc") not in pipeline._physics_cache
        assert ("sess2:optimal", "profile-abc") not in pipeline._physics_cache
        # Unrelated profile entry should remain
        assert ("sess3:optimal", "profile-xyz") in pipeline._physics_cache
        mock_db_inv.assert_awaited_once_with("profile-abc")

    def test_lru_eviction_when_cache_exceeds_max_entries(self) -> None:
        """LRU eviction removes the oldest entry when cache exceeds max size."""
        # Fill cache to just over the limit
        for i in range(pipeline.PHYSICS_CACHE_MAX_ENTRIES):
            pipeline._physics_cache[(f"sess{i}:ep", None)] = ({"v": i}, time.time() - i)

        # Insert one more entry — should trigger eviction
        pipeline._set_physics_cached("new-sess", "endpoint", {"v": 999})

        # Total should not exceed max + 1 (the set happens before eviction check)
        assert len(pipeline._physics_cache) <= pipeline.PHYSICS_CACHE_MAX_ENTRIES


# ---------------------------------------------------------------------------
# db_session_store.py — ensure_user_exists
# ---------------------------------------------------------------------------


class TestEnsureUserExists:
    """Tests for db_session_store.ensure_user_exists."""

    @pytest.mark.asyncio
    async def test_updates_existing_user_name(self) -> None:
        """ensure_user_exists updates name/avatar when user already exists by ID."""
        from backend.api.services.db_session_store import ensure_user_exists

        user = AuthenticatedUser(
            user_id=_TEST_USER.user_id,
            email=_TEST_USER.email,
            name="Updated Name",
            picture="http://example.com/pic.jpg",
        )
        async with _test_session_factory() as db:
            await ensure_user_exists(db, user)
            await db.commit()

            result = await db.execute(select(UserModel).where(UserModel.id == _TEST_USER.user_id))
            row = result.scalar_one()
            assert row.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_creates_new_user(self) -> None:
        """ensure_user_exists creates a new User row for a brand new user."""
        from backend.api.services.db_session_store import ensure_user_exists

        new_user = AuthenticatedUser(
            user_id="brand-new-user-001",
            email="new@example.com",
            name="New Driver",
        )
        async with _test_session_factory() as db:
            await ensure_user_exists(db, new_user)
            await db.commit()

            result = await db.execute(select(UserModel).where(UserModel.id == "brand-new-user-001"))
            row = result.scalar_one_or_none()
            assert row is not None
            assert row.email == "new@example.com"


# ---------------------------------------------------------------------------
# session_store.py — sync_user_id and claim_session
# ---------------------------------------------------------------------------


class TestSessionStoreSyncUserId:
    """Tests for session_store.sync_user_id."""

    def test_sync_user_id_updates_matching_sessions(self) -> None:
        """sync_user_id updates user_id on all sessions owned by old_id."""
        from backend.api.services.session_store import _store

        # Create a mock SessionData
        mock_sd = MagicMock()
        mock_sd.user_id = "old-user-id"
        _store["test-sync-session"] = mock_sd

        sync_user_id("old-user-id", "new-user-id")
        assert mock_sd.user_id == "new-user-id"

        del _store["test-sync-session"]

    def test_sync_user_id_no_match_is_no_op(self) -> None:
        """sync_user_id with no matching sessions does not raise."""
        sync_user_id("unknown-old-id", "some-new-id")  # should not raise

    def test_claim_session_fails_when_not_anonymous(self) -> None:
        """claim_session returns False when the session is not anonymous (line 202)."""
        from backend.api.services.session_store import _store

        mock_sd = MagicMock()
        mock_sd.is_anonymous = False
        _store["not-anon-session"] = mock_sd

        result = claim_session("not-anon-session", "user-trying-to-claim")
        assert result is False

        del _store["not-anon-session"]


# ---------------------------------------------------------------------------
# db_coaching_store.py — upsert update branch and get_any returns None
# ---------------------------------------------------------------------------


async def _seed_session_row(session_id: str, user_id: str = _TEST_USER.user_id) -> None:
    """Seed a minimal session row so coaching_report FK constraints pass."""
    async with _test_session_factory() as db:
        # Check if already exists
        existing = await db.get(SessionModel, session_id)
        if existing is None:
            db.add(
                SessionModel(
                    session_id=session_id,
                    user_id=user_id,
                    track_name="Test Track",
                    session_date=datetime.now(UTC),
                    file_key=session_id,
                    n_laps=3,
                )
            )
            await db.commit()


class TestDbCoachingStore:
    """Tests for db_coaching_store functions."""

    @pytest.mark.asyncio
    async def test_upsert_coaching_report_updates_existing(self) -> None:
        """upsert_coaching_report_db updates existing row (lines 36-37)."""
        from backend.api.services.db_coaching_store import (
            get_coaching_report_db,
            upsert_coaching_report_db,
        )

        session_id = "db-upsert-test"
        await _seed_session_row(session_id)

        report_v1 = CoachingReportResponse(
            session_id=session_id,
            status="ready",
            skill_level="intermediate",
            summary="Version 1",
        )
        report_v2 = CoachingReportResponse(
            session_id=session_id,
            status="ready",
            skill_level="intermediate",
            summary="Version 2",
        )

        async with _test_session_factory() as db:
            await upsert_coaching_report_db(db, session_id, report_v1, "intermediate")
            await db.commit()

        async with _test_session_factory() as db:
            await upsert_coaching_report_db(db, session_id, report_v2, "intermediate")
            await db.commit()

        async with _test_session_factory() as db:
            result = await get_coaching_report_db(db, session_id)
            assert result is not None
            assert result.summary == "Version 2"

    @pytest.mark.asyncio
    async def test_get_any_coaching_report_db_returns_none_when_empty(self) -> None:
        """get_any_coaching_report_db returns None when no reports exist."""
        from backend.api.services.db_coaching_store import get_any_coaching_report_db

        async with _test_session_factory() as db:
            result = await get_any_coaching_report_db(db, "nonexistent-session-xxx")
        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_coaching_context_updates_existing(self) -> None:
        """upsert_coaching_context_db updates existing context row."""
        from backend.api.services.db_coaching_store import (
            get_coaching_context_db,
            upsert_coaching_context_db,
        )

        session_id = "ctx-upsert-test"
        await _seed_session_row(session_id)

        messages_v1 = [{"role": "user", "content": "Hello"}]
        messages_v2 = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]

        async with _test_session_factory() as db:
            await upsert_coaching_context_db(db, session_id, messages_v1)
            await db.commit()

        async with _test_session_factory() as db:
            await upsert_coaching_context_db(db, session_id, messages_v2)
            await db.commit()

        async with _test_session_factory() as db:
            result = await get_coaching_context_db(db, session_id)
            assert result is not None
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_delete_coaching_data_db(self) -> None:
        """delete_coaching_data_db removes both report and context."""
        from backend.api.services.db_coaching_store import (
            delete_coaching_data_db,
            get_any_coaching_report_db,
            upsert_coaching_report_db,
        )

        session_id = "db-delete-test"
        await _seed_session_row(session_id)

        report = CoachingReportResponse(
            session_id=session_id,
            status="ready",
            skill_level="intermediate",
            summary="Will be deleted",
        )
        async with _test_session_factory() as db:
            await upsert_coaching_report_db(db, session_id, report, "intermediate")
            await db.commit()

        async with _test_session_factory() as db:
            await delete_coaching_data_db(db, session_id)
            await db.commit()

        async with _test_session_factory() as db:
            result = await get_any_coaching_report_db(db, session_id)
        assert result is None


# ---------------------------------------------------------------------------
# comparison.py — helper functions
# ---------------------------------------------------------------------------


class TestComparisonHelpers:
    """Tests for comparison service helper functions."""

    def test_normalize_track_name_empty(self) -> None:
        """_normalize_track_name returns '' for empty/None input (line 50)."""
        assert _normalize_track_name("") == ""
        assert _normalize_track_name(None) == ""

    def test_normalize_track_name_strips_special_chars(self) -> None:
        """_normalize_track_name strips non-alphanumeric chars and lowercases."""
        result = _normalize_track_name("Barber Motorsports Park!")
        assert result == "barber motorsports park"

    def test_validate_session_comparison_same_session(self) -> None:
        """validate_session_comparison allows comparing same session to itself."""
        mock_sd = MagicMock()
        mock_sd.session_id = "same-session"
        # Should not raise
        validate_session_comparison(mock_sd, mock_sd)

    def test_validate_session_comparison_different_tracks_raises(self) -> None:
        """validate_session_comparison raises 400 for different track names."""
        from fastapi import HTTPException

        sd_a = MagicMock()
        sd_a.session_id = "sess-a"
        sd_a.snapshot.metadata.track_name = "Barber Motorsports Park"

        sd_b = MagicMock()
        sd_b.session_id = "sess-b"
        sd_b.snapshot.metadata.track_name = "Road Atlanta"

        with pytest.raises(HTTPException) as exc_info:
            validate_session_comparison(sd_a, sd_b)
        assert exc_info.value.status_code == 400

    def test_best_lap_distance_m_fallback_to_df(self) -> None:
        """_best_lap_distance_m uses df when no matching lap_summary (lines 59-62)."""
        import pandas as pd

        from backend.api.services.comparison import _best_lap_distance_m

        mock_sd = MagicMock()
        mock_sd.processed.best_lap = 5
        mock_sd.processed.lap_summaries = []  # No matching summary

        # Create a df with lap_distance_m column
        df = pd.DataFrame({"lap_distance_m": [100.0, 200.0, 300.0]})
        mock_sd.processed.resampled_laps = {5: df}

        result = _best_lap_distance_m(mock_sd)
        assert result == 300.0

    def test_best_lap_distance_m_returns_none_when_no_df(self) -> None:
        """_best_lap_distance_m returns None when df is missing."""
        from backend.api.services.comparison import _best_lap_distance_m

        mock_sd = MagicMock()
        mock_sd.processed.best_lap = 5
        mock_sd.processed.lap_summaries = []
        mock_sd.processed.resampled_laps = {}  # No df for lap 5

        result = _best_lap_distance_m(mock_sd)
        assert result is None


# ---------------------------------------------------------------------------
# equipment_store.py — uncovered service paths
# ---------------------------------------------------------------------------


class TestEquipmentStoreMissingPaths:
    """Cover uncovered lines in equipment_store service."""

    def setup_method(self) -> None:
        """Clear equipment store state before each test."""
        from backend.api.services import equipment_store

        equipment_store._profiles.clear()
        equipment_store._profile_owners.clear()
        equipment_store._session_equipment.clear()

    def test_sync_user_id_updates_profile_ownership(self) -> None:
        """sync_user_id updates profile owners from old_id to new_id (lines 328-330)."""
        from backend.api.services import equipment_store

        equipment_store._profile_owners["prof-1"] = "old-user"
        equipment_store._profile_owners["prof-2"] = "old-user"
        equipment_store._profile_owners["prof-3"] = "other-user"

        equipment_store.sync_user_id("old-user", "new-user")

        assert equipment_store._profile_owners["prof-1"] == "new-user"
        assert equipment_store._profile_owners["prof-2"] == "new-user"
        assert equipment_store._profile_owners["prof-3"] == "other-user"

    def test_get_default_profile_returns_none_when_no_default(self) -> None:
        """get_default_profile returns None when user has no default profile."""
        from backend.api.services import equipment_store

        result = equipment_store.get_default_profile("user-with-no-profiles")
        assert result is None

    def test_delete_session_equipment_returns_false_when_missing(self) -> None:
        """delete_session_equipment returns False when session not in store."""
        from backend.api.services import equipment_store

        result = equipment_store.delete_session_equipment("nonexistent-session")
        assert result is False

    def test_list_profiles_for_user_empty_when_none(self) -> None:
        """list_profiles_for_user returns [] when user has no profiles."""
        from backend.api.services import equipment_store

        result = equipment_store.list_profiles_for_user("no-profiles-user")
        assert result == []

    def test_load_persisted_profiles_no_dir_returns_zero(self) -> None:
        """load_persisted_profiles returns 0 when dir is None (line 401)."""
        from backend.api.services import equipment_store

        original = equipment_store._equipment_dir
        equipment_store._equipment_dir = None
        try:
            count = equipment_store.load_persisted_profiles()
            assert count == 0
        finally:
            equipment_store._equipment_dir = original

    def test_load_persisted_session_equipment_no_dir_returns_zero(self) -> None:
        """load_persisted_session_equipment returns 0 when dir is None."""
        from backend.api.services import equipment_store

        original = equipment_store._equipment_dir
        equipment_store._equipment_dir = None
        try:
            count = equipment_store.load_persisted_session_equipment()
            assert count == 0
        finally:
            equipment_store._equipment_dir = original


# ---------------------------------------------------------------------------
# coaching_store.py — DB fallback paths
# ---------------------------------------------------------------------------


class TestCoachingStoreDbFallback:
    """Tests for coaching_store DB fallback paths (lines 118-119)."""

    @pytest.mark.asyncio
    async def test_get_any_coaching_report_returns_none_when_db_has_error(self) -> None:
        """get_any_coaching_report returns None when DB raises SQLAlchemyError."""
        from sqlalchemy.exc import SQLAlchemyError

        from backend.api.services.coaching_store import get_any_coaching_report

        clear_all_coaching()

        with patch(
            "backend.api.services.coaching_store.async_session_factory",
            side_effect=SQLAlchemyError("DB error"),
        ):
            result = await get_any_coaching_report("never-stored-session")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_coaching_report_db_fallback_on_cache_miss(self) -> None:
        """get_coaching_report falls back to DB when not in memory cache."""
        from backend.api.services.coaching_store import get_coaching_report

        clear_all_coaching()

        # Patch DB to return a report
        mock_report = CoachingReportResponse(
            session_id="db-fallback-sess",
            status="ready",
            skill_level="intermediate",
            summary="DB stored",
        )

        with patch(
            "backend.api.services.coaching_store.get_coaching_report_db",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            result = await get_coaching_report("db-fallback-sess", "intermediate")
        assert result is not None
        assert result.summary == "DB stored"

        clear_all_coaching()

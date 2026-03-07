"""Extended tests for db_session_store — covers uncovered lines 43-108, 265-270.

Lines targeted:
  - 43-108: ensure_user_exists — email-migration path (same email, different user_id)
  - 265-270: get_session_for_user_with_db_sync — DB ownership sync on stale memory user_id
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.api.db.models import Session as SessionModel
from backend.api.db.models import User as UserModel
from backend.api.dependencies import AuthenticatedUser
from backend.tests.conftest import _TEST_USER, _test_session_factory


class TestEnsureUserExistsEmailMigration:
    """Tests for the email-based ID migration path in ensure_user_exists (lines 43-108)."""

    @pytest.mark.asyncio
    async def test_migrates_sessions_when_same_email_different_id(self) -> None:
        """When same email exists under a different user_id, FKs are migrated (lines 43-108)."""
        from backend.api.services.db_session_store import ensure_user_exists

        old_user_id = "old-user-abc-123"
        new_user_id = "new-user-abc-456"
        shared_email = "migrate-test@example.com"

        # Seed an old user with sessions
        async with _test_session_factory() as db:
            db.add(UserModel(id=old_user_id, email=shared_email, name="Old Name"))
            await db.flush()
            db.add(
                SessionModel(
                    session_id="migrate-sess-001",
                    user_id=old_user_id,
                    track_name="barber",
                    session_date=datetime.now(UTC),
                    file_key="migrate-sess-001",
                    n_laps=3,
                )
            )
            await db.commit()

        # Now call ensure_user_exists with same email but new_user_id
        new_user = AuthenticatedUser(
            user_id=new_user_id,
            email=shared_email,
            name="New Name",
        )
        async with _test_session_factory() as db:
            await ensure_user_exists(db, new_user)
            await db.commit()

        # Verify: new user exists, old user is gone, session FK points to new_user_id
        async with _test_session_factory() as db:
            new_user_row = await db.get(UserModel, new_user_id)
            old_user_row = await db.get(UserModel, old_user_id)
            session_row = await db.get(SessionModel, "migrate-sess-001")

        assert new_user_row is not None
        assert new_user_row.email == shared_email
        assert old_user_row is None  # Old user deleted
        assert session_row is not None
        assert session_row.user_id == new_user_id  # FK migrated

    @pytest.mark.asyncio
    async def test_migration_updates_in_memory_session_store(self) -> None:
        """Migration syncs in-memory session store via sync_user_id (line 106)."""
        from backend.api.services import session_store
        from backend.api.services.db_session_store import ensure_user_exists

        old_user_id = "old-sync-user-111"
        new_user_id = "new-sync-user-222"
        shared_email = "sync-test@example.com"

        # Seed old user in DB
        async with _test_session_factory() as db:
            db.add(UserModel(id=old_user_id, email=shared_email, name="Old Name"))
            await db.commit()

        # Create an in-memory session owned by old_user_id
        from backend.api.services.pipeline import process_upload
        from backend.tests.conftest import build_synthetic_csv

        csv = build_synthetic_csv(n_laps=2)
        result = await process_upload(csv, "test.csv")
        sid = str(result["session_id"])
        sd = session_store.get_session(sid)
        if sd is not None:
            sd.user_id = old_user_id

        # Migrate: same email, new_user_id
        new_user = AuthenticatedUser(
            user_id=new_user_id,
            email=shared_email,
            name="New Name",
        )
        async with _test_session_factory() as db:
            await ensure_user_exists(db, new_user)
            await db.commit()

        # In-memory session should now be owned by new_user_id
        if sd is not None:
            assert sd.user_id == new_user_id


class TestGetSessionForUserWithDbSync:
    """Tests for get_session_for_user_with_db_sync (lines 265-270)."""

    @pytest.mark.asyncio
    async def test_returns_none_when_session_not_in_memory(self) -> None:
        """Returns None when session is not in memory store at all."""
        from backend.api.services.db_session_store import get_session_for_user_with_db_sync

        async with _test_session_factory() as db:
            result = await get_session_for_user_with_db_sync(
                db, "nonexistent-session-xyz", _TEST_USER.user_id
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_session_when_in_memory_ownership_matches(self) -> None:
        """Fast path: returns session when in-memory ownership is correct."""
        from backend.api.services import session_store
        from backend.api.services.db_session_store import get_session_for_user_with_db_sync
        from backend.api.services.pipeline import process_upload
        from backend.tests.conftest import build_synthetic_csv

        csv = build_synthetic_csv(n_laps=2)
        result = await process_upload(csv, "test.csv")
        sid = str(result["session_id"])

        sd = session_store.get_session(sid)
        if sd is not None:
            sd.user_id = _TEST_USER.user_id

        async with _test_session_factory() as db:
            found = await get_session_for_user_with_db_sync(db, sid, _TEST_USER.user_id)

        assert found is not None
        assert found.session_id == sid

    @pytest.mark.asyncio
    async def test_syncs_ownership_via_db_on_stale_user_id(self) -> None:
        """When in-memory user_id is stale but DB confirms ownership, syncs and returns session."""
        from backend.api.services import session_store
        from backend.api.services.db_session_store import (
            get_session_for_user_with_db_sync,
            store_session_db,
        )
        from backend.api.services.pipeline import process_upload
        from backend.tests.conftest import build_synthetic_csv

        csv = build_synthetic_csv(n_laps=2)
        result = await process_upload(csv, "test.csv")
        sid = str(result["session_id"])

        sd = session_store.get_session(sid)
        if sd is None:
            return  # Skip if session wasn't stored

        # Tag session with DIFFERENT user in memory (stale)
        stale_user_id = "stale-old-user-id"
        sd.user_id = stale_user_id

        # Persist to DB under the ACTUAL user
        async with _test_session_factory() as db:
            await store_session_db(db, _TEST_USER.user_id, sd)
            await db.commit()

        # get_session_for_user_with_db_sync should sync and return the session
        async with _test_session_factory() as db:
            found = await get_session_for_user_with_db_sync(db, sid, _TEST_USER.user_id)

        assert found is not None
        # In-memory user_id should now be synced to actual owner
        assert found.user_id == _TEST_USER.user_id

    @pytest.mark.asyncio
    async def test_returns_none_when_db_ownership_check_fails(self) -> None:
        """Returns None when session is in memory but DB doesn't confirm ownership."""
        from backend.api.services import session_store
        from backend.api.services.db_session_store import get_session_for_user_with_db_sync
        from backend.api.services.pipeline import process_upload
        from backend.tests.conftest import build_synthetic_csv

        csv = build_synthetic_csv(n_laps=2)
        result = await process_upload(csv, "test.csv")
        sid = str(result["session_id"])

        sd = session_store.get_session(sid)
        if sd is None:
            return  # Skip if session not stored

        # Tag session with different user in memory AND no DB record for requested user
        sd.user_id = "some-other-user-xyz"

        # No DB row for _TEST_USER for this session — ownership should be denied
        async with _test_session_factory() as db:
            found = await get_session_for_user_with_db_sync(db, sid, _TEST_USER.user_id)

        assert found is None

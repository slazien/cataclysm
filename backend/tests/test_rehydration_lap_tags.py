"""Tests that persisted lap tags are loaded into SessionData during rehydration.

Verifies that after ``_reload_sessions_from_db()`` runs, any lap tags already
stored in the DB are reflected in ``sd.lap_tags`` and that ``coaching_laps``
has been recalculated to exclude laps tagged with exclusion tags (e.g. "traffic").
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from backend.api.services import session_store
from backend.tests.conftest import _test_session_factory, build_synthetic_csv

_NOW = datetime(2026, 3, 16, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _upload_via_pipeline(csv_bytes: bytes) -> str:
    """Run process_upload directly (no HTTP) and return the session_id."""
    from backend.api.services.pipeline import process_upload

    result = await process_upload(csv_bytes, "test.csv")
    return str(result["session_id"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rehydration_loads_lap_tags_from_db() -> None:
    """Tags persisted in DB before rehydration appear in sd.lap_tags after reload."""
    from backend.api.db.models import (
        LapTag,
    )
    from backend.api.db.models import (
        Session as SessionModel,
    )
    from backend.api.db.models import (
        SessionFile as SessionFileModel,
    )
    from backend.api.main import _reload_sessions_from_db

    # 1. Upload a session to get a valid SessionData with known laps
    csv_bytes = build_synthetic_csv(n_laps=4)
    session_id = await _upload_via_pipeline(csv_bytes)

    sd = session_store.get_session(session_id)
    assert sd is not None
    all_laps = sorted(sd.processed.resampled_laps.keys())
    assert len(all_laps) >= 2, "Need at least 2 laps for this test"

    # Pick a lap to tag (not the first/last to avoid in/out ambiguity)
    target_lap = all_laps[1] if len(all_laps) > 2 else all_laps[0]

    # 2. Persist the session file + metadata rows and a tag row into the test DB
    async with _test_session_factory() as db:
        db.add(
            SessionFileModel(
                session_id=session_id,
                filename="test.csv",
                csv_bytes=csv_bytes,
            )
        )
        db.add(
            SessionModel(
                session_id=session_id,
                user_id="test-user-123",
                track_name="Test Circuit",
                session_date=_NOW,
                file_key=session_id,
            )
        )
        db.add(
            LapTag(
                session_id=session_id,
                lap_number=target_lap,
                tag="traffic",
            )
        )
        await db.commit()

    # 3. Clear in-memory store to simulate a backend restart
    session_store.clear_all()
    assert session_store.get_session(session_id) is None

    # 4. Patch async_session_factory in main to use the test DB
    with patch(
        "backend.api.db.database.async_session_factory",
        _test_session_factory,
    ):
        n = await _reload_sessions_from_db()

    assert n >= 1, "Expected at least one session to be reloaded"

    # 5. Verify lap tags were loaded
    sd_reloaded = session_store.get_session(session_id)
    assert sd_reloaded is not None, "Session should be in memory after rehydration"

    assert "traffic" in sd_reloaded.lap_tags.get_tags(target_lap), (
        f"Lap {target_lap} should have 'traffic' tag after rehydration; "
        f"got tags: {sd_reloaded.lap_tags.tags}"
    )


@pytest.mark.asyncio
async def test_rehydration_recalculates_coaching_laps_for_excluded_tags() -> None:
    """After rehydration, coaching_laps excludes laps that have exclusion tags in DB."""
    from backend.api.db.models import (
        LapTag,
    )
    from backend.api.db.models import (
        Session as SessionModel,
    )
    from backend.api.db.models import (
        SessionFile as SessionFileModel,
    )
    from backend.api.main import _reload_sessions_from_db

    csv_bytes = build_synthetic_csv(n_laps=4)
    session_id = await _upload_via_pipeline(csv_bytes)

    sd = session_store.get_session(session_id)
    assert sd is not None
    original_coaching_laps = list(sd.coaching_laps)
    assert original_coaching_laps, "Need coaching laps for this test"

    # Tag the first coaching lap as traffic
    target_lap = original_coaching_laps[0]

    async with _test_session_factory() as db:
        db.add(
            SessionFileModel(
                session_id=session_id,
                filename="test.csv",
                csv_bytes=csv_bytes,
            )
        )
        db.add(
            SessionModel(
                session_id=session_id,
                user_id="test-user-123",
                track_name="Test Circuit",
                session_date=_NOW,
                file_key=session_id,
            )
        )
        db.add(
            LapTag(
                session_id=session_id,
                lap_number=target_lap,
                tag="traffic",
            )
        )
        await db.commit()

    session_store.clear_all()

    with patch(
        "backend.api.db.database.async_session_factory",
        _test_session_factory,
    ):
        await _reload_sessions_from_db()

    sd_reloaded = session_store.get_session(session_id)
    assert sd_reloaded is not None

    assert target_lap not in sd_reloaded.coaching_laps, (
        f"Lap {target_lap} tagged 'traffic' should be excluded from coaching_laps after "
        f"rehydration; coaching_laps={sd_reloaded.coaching_laps}"
    )


@pytest.mark.asyncio
async def test_rehydration_no_tags_leaves_coaching_laps_unchanged() -> None:
    """Rehydration with no tags in DB leaves coaching_laps identical to a fresh upload."""
    from backend.api.db.models import Session as SessionModel
    from backend.api.db.models import SessionFile as SessionFileModel
    from backend.api.main import _reload_sessions_from_db

    csv_bytes = build_synthetic_csv(n_laps=4)
    session_id = await _upload_via_pipeline(csv_bytes)

    sd = session_store.get_session(session_id)
    assert sd is not None
    coaching_laps_before = list(sd.coaching_laps)

    async with _test_session_factory() as db:
        db.add(
            SessionFileModel(
                session_id=session_id,
                filename="test.csv",
                csv_bytes=csv_bytes,
            )
        )
        db.add(
            SessionModel(
                session_id=session_id,
                user_id="test-user-123",
                track_name="Test Circuit",
                session_date=_NOW,
                file_key=session_id,
            )
        )
        await db.commit()

    session_store.clear_all()

    with patch(
        "backend.api.db.database.async_session_factory",
        _test_session_factory,
    ):
        await _reload_sessions_from_db()

    sd_reloaded = session_store.get_session(session_id)
    assert sd_reloaded is not None
    assert sd_reloaded.coaching_laps == coaching_laps_before, (
        "coaching_laps should be unchanged when no tags are persisted"
    )
    # lap_tags store should be empty
    assert not sd_reloaded.lap_tags.tags, "lap_tags should be empty when no tags are in DB"

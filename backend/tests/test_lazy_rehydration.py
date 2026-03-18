"""Tests for lazy rehydration on session cache miss.

Verifies that evicted sessions are transparently re-processed from
DB-stored CSV bytes when accessed via the API.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from backend.api.services import session_store
from backend.api.services.session_store import (
    _REHYDRATION_FAILURES,
    _REHYDRATION_LOCKS,
)
from backend.tests.conftest import build_synthetic_csv

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _clear_rehydration_state() -> None:
    """Reset rehydration locks and failure cache between tests."""
    _REHYDRATION_LOCKS.clear()
    _REHYDRATION_FAILURES.clear()


async def _upload_and_get_sid(client: AsyncClient) -> str:
    """Upload a synthetic CSV and return the session_id."""
    csv_bytes = build_synthetic_csv(n_laps=3, track_name="Rehydration Test")
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    sids = data["session_ids"]
    assert len(sids) == 1
    return sids[0]


async def test_evicted_session_rehydrates_on_access(client: AsyncClient) -> None:
    """Upload a session, evict it from memory, then GET → should 200 via rehydration."""
    sid = await _upload_and_get_sid(client)

    # Verify it's accessible
    resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200

    # Evict from in-memory store
    session_store.delete_session(sid)
    assert session_store.get_session(sid) is None

    # Access again — should rehydrate from DB
    resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == sid

    # Verify it's back in memory
    sd = session_store.get_session(sid)
    assert sd is not None
    assert sd.session_id == sid


async def test_rehydrated_session_preserves_original_id(client: AsyncClient) -> None:
    """Session ID must match the original after rehydration."""
    sid = await _upload_and_get_sid(client)

    # Evict and rehydrate
    session_store.delete_session(sid)
    resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200

    sd = session_store.get_session(sid)
    assert sd is not None
    assert sd.session_id == sid
    assert sd.snapshot.session_id == sid


async def test_truly_missing_session_still_404s(client: AsyncClient) -> None:
    """A session that was never uploaded should still 404."""
    resp = await client.get("/api/sessions/nonexistent-session-id")
    assert resp.status_code == 404


async def test_negative_cache_prevents_repeated_rehydration(
    client: AsyncClient,
) -> None:
    """After a rehydration failure, the negative cache should prevent retries."""
    sid = await _upload_and_get_sid(client)

    # Evict from memory
    session_store.delete_session(sid)

    # Poison the negative cache
    import time

    _REHYDRATION_FAILURES[sid] = time.time()

    # Should 404 because negative cache blocks rehydration
    resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 404

    # Clear negative cache → should succeed now
    _REHYDRATION_FAILURES.pop(sid)
    resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200


async def test_rehydrated_session_has_user_id(client: AsyncClient) -> None:
    """Rehydrated session should have the correct user_id from DB metadata."""
    sid = await _upload_and_get_sid(client)

    # Evict and rehydrate
    session_store.delete_session(sid)
    resp = await client.get(f"/api/sessions/{sid}")
    assert resp.status_code == 200

    sd = session_store.get_session(sid)
    assert sd is not None
    # The test conftest authenticates as "test-user-123"
    assert sd.user_id == "test-user-123"


async def test_concurrent_rehydration_deduplicates(client: AsyncClient) -> None:
    """Multiple concurrent requests for the same evicted session should not
    trigger parallel reprocessing (singleflight via per-session lock)."""
    sid = await _upload_and_get_sid(client)
    session_store.delete_session(sid)

    # Fire 5 concurrent requests
    tasks = [client.get(f"/api/sessions/{sid}") for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # All should succeed
    for resp in results:
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sid

    # Session should be in memory exactly once
    sd = session_store.get_session(sid)
    assert sd is not None
    assert sd.session_id == sid

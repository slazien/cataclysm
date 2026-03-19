"""Tests for the demo session feature."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from backend.api.services.demo_session import DEMO_SESSION_ID, DEMO_USER_ID, is_demo_session
from backend.api.services.session_store import (
    SessionData,
    _evict_oldest,
    _store,
)

# ── Constants ────────────────────────────────────────────────────────


def test_demo_session_id_is_deterministic() -> None:
    assert DEMO_SESSION_ID == "barber_motorsports_p_20260222_b101ba9c"


def test_demo_user_id() -> None:
    assert DEMO_USER_ID == "__demo__"


def test_is_demo_session_positive() -> None:
    assert is_demo_session(DEMO_SESSION_ID) is True


def test_is_demo_session_negative() -> None:
    assert is_demo_session("some_other_session_id") is False


# ── API endpoint ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_demo_endpoint_unavailable(client: AsyncClient) -> None:
    """When demo session is not loaded, endpoint reports unavailable."""
    resp = await client.get("/api/sessions/demo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["session_id"] is None


@pytest.mark.asyncio
async def test_demo_endpoint_available(
    client: AsyncClient,
    synthetic_csv_bytes: bytes,
) -> None:
    """When demo session is in memory, endpoint reports available."""
    from backend.api.services.pipeline import process_upload

    # Process a session and manually set the ID to the demo ID
    result = await process_upload(synthetic_csv_bytes, "test.csv")
    sid = str(result["session_id"])
    sd = _store.get(sid)
    assert sd is not None

    # Move under demo ID
    _store.pop(sid)
    sd.session_id = DEMO_SESSION_ID
    sd.user_id = DEMO_USER_ID
    _store[DEMO_SESSION_ID] = sd

    resp = await client.get("/api/sessions/demo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["session_id"] == DEMO_SESSION_ID


# ── Deletion guard ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_demo_session_not_deletable(client: AsyncClient) -> None:
    """DELETE on demo session returns 403."""
    resp = await client.delete(f"/api/sessions/{DEMO_SESSION_ID}")
    assert resp.status_code == 403
    assert "Demo session" in resp.json()["detail"]


# ── Claim guard ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_demo_session_not_claimable(client: AsyncClient) -> None:
    """POST /claim on demo session returns 400."""
    resp = await client.post(
        "/api/sessions/claim",
        json={"session_id": DEMO_SESSION_ID},
    )
    assert resp.status_code == 400
    assert "Demo session" in resp.json()["detail"]


# ── Eviction guard ──────────────────────────────────────────────────


def test_demo_session_survives_eviction(synthetic_csv_bytes: bytes) -> None:
    """Demo session is protected from LRU eviction."""
    # Clear store and set max to 2
    _store.clear()

    # Create a fake demo SessionData
    from cataclysm.trends import SessionSnapshot

    demo_sd = SessionData(
        session_id=DEMO_SESSION_ID,
        snapshot=SessionSnapshot.__new__(SessionSnapshot),
        parsed=None,  # type: ignore[arg-type]
        processed=None,  # type: ignore[arg-type]
        corners=[],
        all_lap_corners={},
        user_id=DEMO_USER_ID,
    )
    _store[DEMO_SESSION_ID] = demo_sd

    # Fill store to trigger eviction
    with patch("backend.api.services.session_store.MAX_SESSIONS", 2):
        for i in range(5):
            other_sd = SessionData(
                session_id=f"other_{i}",
                snapshot=SessionSnapshot.__new__(SessionSnapshot),
                parsed=None,  # type: ignore[arg-type]
                processed=None,  # type: ignore[arg-type]
                corners=[],
                all_lap_corners={},
            )
            _store[f"other_{i}"] = other_sd
            _evict_oldest()

    # Demo session must survive
    assert DEMO_SESSION_ID in _store


# ── Access control ──────────────────────────────────────────────────


def test_demo_session_accessible_by_any_user() -> None:
    """Demo session is readable by any user_id."""
    from backend.api.services.session_store import get_session_for_user

    _store.clear()

    from cataclysm.trends import SessionSnapshot

    demo_sd = SessionData(
        session_id=DEMO_SESSION_ID,
        snapshot=SessionSnapshot.__new__(SessionSnapshot),
        parsed=None,  # type: ignore[arg-type]
        processed=None,  # type: ignore[arg-type]
        corners=[],
        all_lap_corners={},
        user_id=DEMO_USER_ID,
        is_anonymous=False,
    )
    _store[DEMO_SESSION_ID] = demo_sd

    # Any user can read it
    assert get_session_for_user(DEMO_SESSION_ID, "random-user-123") is demo_sd
    assert get_session_for_user(DEMO_SESSION_ID, "anon") is demo_sd


# ── List filtering ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_demo_session_excluded_from_list(client: AsyncClient) -> None:
    """Demo session does not appear in the user's session list."""
    from cataclysm.trends import SessionSnapshot

    _store.clear()
    demo_sd = SessionData(
        session_id=DEMO_SESSION_ID,
        snapshot=SessionSnapshot.__new__(SessionSnapshot),
        parsed=None,  # type: ignore[arg-type]
        processed=None,  # type: ignore[arg-type]
        corners=[],
        all_lap_corners={},
        user_id=DEMO_USER_ID,
    )
    _store[DEMO_SESSION_ID] = demo_sd

    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    items = resp.json()["items"]
    demo_ids = [s["session_id"] for s in items if s["session_id"] == DEMO_SESSION_ID]
    assert len(demo_ids) == 0

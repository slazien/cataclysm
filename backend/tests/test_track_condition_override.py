"""Tests for PATCH /sessions/{id}/track-condition manual override endpoint.

Verifies:
- Setting a manual condition marks track_condition_is_manual=True.
- Clearing (condition=null) resets the manual flag.
- Invalid condition values return 422.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from cataclysm.equipment import SessionConditions, TrackCondition
from httpx import AsyncClient

from backend.api.services import session_store
from backend.tests.conftest import build_synthetic_csv

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _upload(client: AsyncClient, n_laps: int = 3) -> str:
    """Upload a synthetic session and return its session_id."""
    csv_bytes = build_synthetic_csv(n_laps=n_laps)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["session_ids"][0])


def _inject_weather(session_id: str) -> None:
    """Inject mock weather data into the in-memory session store."""
    sd = session_store.get_session(session_id)
    assert sd is not None, f"Session {session_id} not in store"
    sd.weather = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=25.0,
        humidity_pct=40.0,
        weather_source="open-meteo",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_track_condition_sets_override(client: AsyncClient) -> None:
    """PATCH with condition='wet' sets condition and marks is_manual=True."""
    session_id = await _upload(client)
    _inject_weather(session_id)

    resp = await client.patch(
        f"/api/sessions/{session_id}/track-condition",
        json={"condition": "wet"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["track_condition"] == "wet"
    assert data["track_condition_is_manual"] is True

    # Verify in-memory state
    sd = session_store.get_session(session_id)
    assert sd is not None
    assert sd.weather is not None
    assert sd.weather.track_condition == TrackCondition.WET
    assert sd.weather.track_condition_is_manual is True


@pytest.mark.asyncio
async def test_patch_track_condition_clear_override(
    client: AsyncClient,
) -> None:
    """PATCH with condition=null clears the manual flag."""
    session_id = await _upload(client)
    _inject_weather(session_id)

    # First, set a manual override
    resp = await client.patch(
        f"/api/sessions/{session_id}/track-condition",
        json={"condition": "damp"},
    )
    assert resp.status_code == 200
    assert resp.json()["track_condition_is_manual"] is True

    # Now clear it — mock _auto_fetch_weather to avoid real API calls
    with patch(
        "backend.api.routers.sessions._auto_fetch_weather",
        new_callable=AsyncMock,
    ):
        resp2 = await client.patch(
            f"/api/sessions/{session_id}/track-condition",
            json={"condition": None},
        )
    assert resp2.status_code == 200, resp2.text
    data = resp2.json()
    assert data["track_condition_is_manual"] is False


@pytest.mark.asyncio
async def test_patch_track_condition_invalid_value(
    client: AsyncClient,
) -> None:
    """PATCH with an invalid condition value returns 422."""
    session_id = await _upload(client)
    _inject_weather(session_id)

    resp = await client.patch(
        f"/api/sessions/{session_id}/track-condition",
        json={"condition": "snowy"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_track_condition_no_weather_returns_409(
    client: AsyncClient,
) -> None:
    """PATCH on a session with no weather data returns 409."""
    session_id = await _upload(client)
    # Don't inject weather — sd.weather is None

    resp = await client.patch(
        f"/api/sessions/{session_id}/track-condition",
        json={"condition": "wet"},
    )
    assert resp.status_code == 409

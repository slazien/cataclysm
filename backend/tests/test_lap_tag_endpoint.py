"""Integration tests for the lap-tag endpoints (PUT/GET /laps/{n}/tags).

Verifies:
- After PUT tags with "traffic", GET /laps shows is_clean=False for that lap.
- After PUT tags with "traffic", coaching_laps on the SessionData no longer includes it.
- After clearing tags (PUT with []), the lap becomes clean again.
- Physics and coaching caches are invalidated on tag change.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.api.services import session_store
from backend.tests.conftest import build_synthetic_csv


@pytest.fixture(autouse=True)
def _mock_save_lap_tags() -> None:  # type: ignore[misc]
    """Prevent real DB writes — tests run without a live PostgreSQL instance."""
    with patch(
        "backend.api.routers.sessions.save_lap_tags",
        new_callable=AsyncMock,
    ):
        yield  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _upload(client: AsyncClient, n_laps: int = 4) -> str:
    """Upload a synthetic session and return its session_id."""
    csv_bytes = build_synthetic_csv(n_laps=n_laps)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", csv_bytes, "text/csv"))],
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["session_ids"][0])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_tag_makes_lap_not_clean(client: AsyncClient) -> None:
    """PUT traffic tag → GET /laps shows is_clean=False for that lap."""
    session_id = await _upload(client)

    # Find a clean lap first
    laps_resp = await client.get(f"/api/sessions/{session_id}/laps")
    assert laps_resp.status_code == 200
    laps_before = laps_resp.json()
    clean_laps = [lap for lap in laps_before if lap["is_clean"]]
    assert clean_laps, "Need at least one clean lap to tag"

    target_lap = clean_laps[0]["lap_number"]

    # Tag it as traffic
    put_resp = await client.put(
        f"/api/sessions/{session_id}/laps/{target_lap}/tags",
        json=["traffic"],
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["tags"] == ["traffic"]

    # Verify is_clean is now False for that lap
    laps_after = (await client.get(f"/api/sessions/{session_id}/laps")).json()
    tagged = next(lap for lap in laps_after if lap["lap_number"] == target_lap)
    assert tagged["is_clean"] is False


@pytest.mark.asyncio
async def test_put_tag_removes_lap_from_coaching_laps(client: AsyncClient) -> None:
    """PUT traffic tag → coaching_laps on SessionData no longer includes that lap."""
    session_id = await _upload(client, n_laps=4)

    sd = session_store.get_session(session_id)
    assert sd is not None
    original_coaching_laps = list(sd.coaching_laps)
    assert original_coaching_laps, "Need coaching laps to test exclusion"

    # Pick the first coaching lap that is NOT the best lap
    # (best lap re-inclusion would override the user exclusion — but our
    # recalculate_coaching_laps respects user tags even for best lap)
    target_lap = original_coaching_laps[0]

    put_resp = await client.put(
        f"/api/sessions/{session_id}/laps/{target_lap}/tags",
        json=["traffic"],
    )
    assert put_resp.status_code == 200

    # Read fresh from store
    sd_after = session_store.get_session(session_id)
    assert sd_after is not None
    assert target_lap not in sd_after.coaching_laps, (
        f"Lap {target_lap} should have been removed from coaching_laps after traffic tag, "
        f"got: {sd_after.coaching_laps}"
    )


@pytest.mark.asyncio
async def test_clear_tags_restores_lap_to_clean(client: AsyncClient) -> None:
    """PUT [] after tagging → lap becomes clean again."""
    session_id = await _upload(client)

    laps = (await client.get(f"/api/sessions/{session_id}/laps")).json()
    clean_laps = [lap for lap in laps if lap["is_clean"]]
    assert clean_laps
    target_lap = clean_laps[0]["lap_number"]

    # Tag it
    await client.put(
        f"/api/sessions/{session_id}/laps/{target_lap}/tags",
        json=["traffic"],
    )
    tagged = next(
        lap
        for lap in (await client.get(f"/api/sessions/{session_id}/laps")).json()
        if lap["lap_number"] == target_lap
    )
    assert tagged["is_clean"] is False

    # Clear tags
    clear_resp = await client.put(
        f"/api/sessions/{session_id}/laps/{target_lap}/tags",
        json=[],
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["tags"] == []

    laps_final = (await client.get(f"/api/sessions/{session_id}/laps")).json()
    restored = next(lap for lap in laps_final if lap["lap_number"] == target_lap)
    assert restored["is_clean"] is True


@pytest.mark.asyncio
async def test_put_tag_invalidates_physics_and_coaching_cache(client: AsyncClient) -> None:
    """PUT tag calls invalidate_physics_cache and clear_coaching_data."""
    session_id = await _upload(client)

    sd = session_store.get_session(session_id)
    assert sd is not None
    laps = list(sd.processed.resampled_laps.keys())
    assert laps

    with (
        patch("backend.api.routers.sessions.invalidate_physics_cache") as mock_physics,
        patch(
            "backend.api.routers.sessions.clear_coaching_data",
            new_callable=AsyncMock,
        ) as mock_coaching,
    ):
        resp = await client.put(
            f"/api/sessions/{session_id}/laps/{laps[0]}/tags",
            json=["traffic"],
        )
        assert resp.status_code == 200
        mock_physics.assert_called_once_with(session_id)
        mock_coaching.assert_awaited_once_with(session_id)


@pytest.mark.asyncio
async def test_put_tag_404_unknown_session(client: AsyncClient) -> None:
    """PUT tag on non-existent session returns 404."""
    resp = await client.put(
        "/api/sessions/no-such-session/laps/1/tags",
        json=["traffic"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_put_tag_404_unknown_lap(client: AsyncClient) -> None:
    """PUT tag on non-existent lap returns 404."""
    session_id = await _upload(client)
    resp = await client.put(
        f"/api/sessions/{session_id}/laps/9999/tags",
        json=["traffic"],
    )
    assert resp.status_code == 404

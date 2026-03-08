"""Extended tests for equipment router — covers uncovered lines.

Targets:
  - Vehicle endpoint error paths (404 when not found)
  - weather_lookup with None result
  - weather_lookup with valid result
  - get_session_equipment when profile no longer exists (orphaned FK)
  - Profile ownership check (wrong user gets 404)
  - ensure_single_default path in create/update
  - Session equipment with conditions
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.api.services import equipment_store
from backend.tests.conftest import _TEST_USER, build_synthetic_csv

# ---------------------------------------------------------------------------
# Valid tire payload — compound_category and mu_source must match the domain enums
# ---------------------------------------------------------------------------

_TIRE_PAYLOAD = {
    "model": "RE-71RS",
    "compound_category": "r_comp",
    "size": "245/40R17",
    "treadwear_rating": 200,
    "estimated_mu": 1.12,
    "mu_source": "curated_table",
    "mu_confidence": "high",
}

_PROFILE_PAYLOAD = {
    "name": "Test Profile",
    "tires": _TIRE_PAYLOAD,
    "is_default": False,
}

_PROFILE_PAYLOAD_DEFAULT = {
    "name": "Default Profile",
    "tires": _TIRE_PAYLOAD,
    "is_default": True,
}


async def _upload_session(client: AsyncClient, n_laps: int = 3) -> str:
    """Upload a synthetic session and return the session_id."""
    csv = build_synthetic_csv(n_laps=n_laps)
    resp = await client.post(
        "/api/sessions/upload",
        files=[("files", ("test.csv", csv, "text/csv"))],
    )
    assert resp.status_code == 200
    return str(resp.json()["session_ids"][0])


class TestVehicleEndpoints:
    """Tests for vehicle search, models, and spec endpoints."""

    @pytest.mark.asyncio
    async def test_get_vehicle_makes_returns_list(self, client: AsyncClient) -> None:
        """GET /api/equipment/vehicles/makes returns a list of makes."""
        resp = await client.get("/api/equipment/vehicles/makes")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_search_vehicles_no_query_returns_all(self, client: AsyncClient) -> None:
        """GET /api/equipment/vehicles/search with no q returns all vehicles."""
        resp = await client.get("/api/equipment/vehicles/search")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_search_vehicles_with_query(self, client: AsyncClient) -> None:
        """GET /api/equipment/vehicles/search?q=... returns matching vehicles."""
        resp = await client.get("/api/equipment/vehicles/search?q=porsche")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_vehicle_models(self, client: AsyncClient) -> None:
        """GET /api/equipment/vehicles/{make}/models returns models list."""
        resp = await client.get("/api/equipment/vehicles/Porsche/models")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_vehicle_spec_not_found_returns_404(self, client: AsyncClient) -> None:
        """GET /api/equipment/vehicles/{make}/{model} with unknown vehicle returns 404."""
        resp = await client.get("/api/equipment/vehicles/NonExistentMake/NoSuchModel")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_vehicle_spec_with_generation(self, client: AsyncClient) -> None:
        """GET /api/equipment/vehicles/{make}/{model}?generation=... 404 on no match."""
        resp = await client.get(
            "/api/equipment/vehicles/NonExistentMake/NoSuchModel?generation=Gen1"
        )
        assert resp.status_code == 404
        # Detail should include generation in message
        assert "gen1" in resp.json()["detail"].lower()


class TestWeatherLookup:
    """Tests for POST /api/equipment/weather/lookup."""

    @pytest.mark.asyncio
    async def test_weather_lookup_unavailable_returns_none(self, client: AsyncClient) -> None:
        """When weather data is unavailable, returns conditions=None."""
        with patch(
            "cataclysm.weather_client.lookup_weather",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await client.post(
                "/api/equipment/weather/lookup",
                json={"lat": 33.0, "lon": -86.0, "session_date": "2026-03-01", "hour": 12},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conditions"] is None
        assert "unavailable" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_weather_lookup_with_result(self, client: AsyncClient) -> None:
        """When weather data is available, returns conditions dict."""
        from cataclysm.equipment import SessionConditions, TrackCondition

        mock_conditions = SessionConditions(
            track_condition=TrackCondition.DRY,
            ambient_temp_c=22.5,
            humidity_pct=60.0,
            wind_speed_kmh=10.0,
            precipitation_mm=0.0,
            weather_source="open-meteo",
        )
        with patch(
            "cataclysm.weather_client.lookup_weather",
            new_callable=AsyncMock,
            return_value=mock_conditions,
        ):
            resp = await client.post(
                "/api/equipment/weather/lookup",
                json={"lat": 33.0, "lon": -86.0, "session_date": "2026-03-01"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conditions"] is not None
        assert data["conditions"]["track_condition"] == "dry"
        assert data["conditions"]["ambient_temp_c"] == 22.5


class TestProfileCrud:
    """Tests for profile CRUD — 404 and default enforcement paths."""

    @pytest.fixture(autouse=True)
    def _cleanup_profiles(self) -> Generator[None, None, None]:
        """Clear equipment store state after each test."""
        yield
        equipment_store._profiles.clear()
        equipment_store._profile_owners.clear()
        equipment_store._session_equipment.clear()

    @pytest.mark.asyncio
    async def test_create_profile_returns_201(self, client: AsyncClient) -> None:
        """POST /api/equipment/profiles creates a profile and returns 201."""
        with patch(
            "backend.api.services.equipment_store.db_persist_profile",
            new_callable=AsyncMock,
        ):
            resp = await client.post("/api/equipment/profiles", json=_PROFILE_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Profile"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_default_profile_unsets_others(self, client: AsyncClient) -> None:
        """Creating a default profile calls ensure_single_default (lines 477-482)."""
        with patch(
            "backend.api.services.equipment_store.db_persist_profile",
            new_callable=AsyncMock,
        ):
            # Create first default
            resp1 = await client.post("/api/equipment/profiles", json=_PROFILE_PAYLOAD_DEFAULT)
            assert resp1.status_code == 201
            # Create second default — should unset the first
            resp2 = await client.post("/api/equipment/profiles", json=_PROFILE_PAYLOAD_DEFAULT)
            assert resp2.status_code == 201
        # Only the second should now be default (first was unset)
        profiles = equipment_store.list_profiles_for_user(_TEST_USER.user_id)
        defaults = [p for p in profiles if p.is_default]
        assert len(defaults) == 1

    @pytest.mark.asyncio
    async def test_get_profile_wrong_user_returns_404(self, client: AsyncClient) -> None:
        """GET /api/equipment/profiles/{id} for another user's profile returns 404."""
        with patch(
            "backend.api.services.equipment_store.db_persist_profile",
            new_callable=AsyncMock,
        ):
            create_resp = await client.post("/api/equipment/profiles", json=_PROFILE_PAYLOAD)
        assert create_resp.status_code == 201
        profile_id = create_resp.json()["id"]

        # Assign the profile to a different user
        equipment_store.set_profile_owner(profile_id, "some-other-user")

        resp = await client.get(f"/api/equipment/profiles/{profile_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_profile_not_found_returns_404(self, client: AsyncClient) -> None:
        """GET /api/equipment/profiles/{id} for nonexistent profile returns 404."""
        resp = await client.get("/api/equipment/profiles/nonexistent-profile-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_profile_not_found_returns_404(self, client: AsyncClient) -> None:
        """PATCH /api/equipment/profiles/{id} for nonexistent profile returns 404."""
        resp = await client.patch(
            "/api/equipment/profiles/nonexistent-id",
            json=_PROFILE_PAYLOAD,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_profile_wrong_user_returns_404(self, client: AsyncClient) -> None:
        """PATCH /api/equipment/profiles/{id} for another user's profile returns 404."""
        with patch(
            "backend.api.services.equipment_store.db_persist_profile",
            new_callable=AsyncMock,
        ):
            create_resp = await client.post("/api/equipment/profiles", json=_PROFILE_PAYLOAD)
        assert create_resp.status_code == 201
        profile_id = create_resp.json()["id"]
        equipment_store.set_profile_owner(profile_id, "other-user")

        resp = await client.patch(
            f"/api/equipment/profiles/{profile_id}",
            json=_PROFILE_PAYLOAD,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_default_profile_calls_ensure_single_default(
        self, client: AsyncClient
    ) -> None:
        """PATCH with is_default=True calls ensure_single_default (lines 541-547)."""
        with patch(
            "backend.api.services.equipment_store.db_persist_profile",
            new_callable=AsyncMock,
        ):
            create_resp = await client.post("/api/equipment/profiles", json=_PROFILE_PAYLOAD)
            assert create_resp.status_code == 201
            profile_id = create_resp.json()["id"]
            # Update to set as default
            update_payload = dict(_PROFILE_PAYLOAD)
            update_payload["is_default"] = True
            resp = await client.patch(
                f"/api/equipment/profiles/{profile_id}",
                json=update_payload,
            )
        assert resp.status_code == 200
        assert resp.json()["is_default"] is True

    @pytest.mark.asyncio
    async def test_delete_profile_wrong_user_returns_404(self, client: AsyncClient) -> None:
        """DELETE /api/equipment/profiles/{id} for another user's profile returns 404."""
        with patch(
            "backend.api.services.equipment_store.db_persist_profile",
            new_callable=AsyncMock,
        ):
            create_resp = await client.post("/api/equipment/profiles", json=_PROFILE_PAYLOAD)
        assert create_resp.status_code == 201
        profile_id = create_resp.json()["id"]
        equipment_store.set_profile_owner(profile_id, "other-user")

        resp = await client.delete(f"/api/equipment/profiles/{profile_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_profile_not_found_returns_404(self, client: AsyncClient) -> None:
        """DELETE /api/equipment/profiles/{id} for nonexistent profile returns 404."""
        resp = await client.delete("/api/equipment/profiles/nonexistent-id")
        assert resp.status_code == 404


class TestSessionEquipment:
    """Tests for PUT/GET /{session_id}/equipment."""

    @pytest.fixture(autouse=True)
    def _cleanup(self) -> Generator[None, None, None]:
        """Clear equipment store state after each test."""
        yield
        equipment_store._profiles.clear()
        equipment_store._profile_owners.clear()
        equipment_store._session_equipment.clear()

    @pytest.mark.asyncio
    async def test_set_equipment_session_not_found_returns_404(self, client: AsyncClient) -> None:
        """PUT /{session_id}/equipment for nonexistent session returns 404."""
        with patch(
            "backend.api.services.equipment_store.db_persist_profile",
            new_callable=AsyncMock,
        ):
            profile_resp = await client.post("/api/equipment/profiles", json=_PROFILE_PAYLOAD)
        assert profile_resp.status_code == 201
        profile_id = profile_resp.json()["id"]

        resp = await client.put(
            "/api/equipment/nonexistent-session/equipment",
            json={"profile_id": profile_id},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_set_equipment_profile_not_found_returns_404(self, client: AsyncClient) -> None:
        """PUT /{session_id}/equipment with nonexistent profile returns 404."""
        sid = await _upload_session(client)
        resp = await client.put(
            f"/api/equipment/{sid}/equipment",
            json={"profile_id": "nonexistent-profile"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_equipment_no_assignment_returns_404(self, client: AsyncClient) -> None:
        """GET /{session_id}/equipment when no equipment assigned returns 404."""
        sid = await _upload_session(client)
        resp = await client.get(f"/api/equipment/{sid}/equipment")
        assert resp.status_code == 404
        assert "no equipment" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_equipment_orphaned_profile_returns_404(self, client: AsyncClient) -> None:
        """GET /{session_id}/equipment when profile no longer exists returns 404."""
        sid = await _upload_session(client)
        # Manually inject a SessionEquipment with a profile that doesn't exist
        from cataclysm.equipment import SessionEquipment

        se = SessionEquipment(session_id=sid, profile_id="deleted-profile")
        equipment_store._session_equipment[sid] = se

        resp = await client.get(f"/api/equipment/{sid}/equipment")
        assert resp.status_code == 404
        assert "no longer exists" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_set_equipment_with_conditions(self, client: AsyncClient) -> None:
        """PUT /{session_id}/equipment with conditions sets track_condition."""
        sid = await _upload_session(client)

        with (
            patch(
                "backend.api.services.equipment_store.db_persist_profile",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.api.services.equipment_store.db_persist_session_equipment",
                new_callable=AsyncMock,
            ),
        ):
            profile_resp = await client.post("/api/equipment/profiles", json=_PROFILE_PAYLOAD)
            assert profile_resp.status_code == 201
            profile_id = profile_resp.json()["id"]

            resp = await client.put(
                f"/api/equipment/{sid}/equipment",
                json={
                    "profile_id": profile_id,
                    "conditions": {
                        "track_condition": "wet",
                        "ambient_temp_c": 15.0,
                    },
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conditions"]["track_condition"] == "wet"


class TestReferenceEndpoints:
    """Tests for tire sizes and brake fluids reference endpoints."""

    @pytest.mark.asyncio
    async def test_get_reference_tire_sizes(self, client: AsyncClient) -> None:
        """GET /api/equipment/reference/tire-sizes returns a list."""
        resp = await client.get("/api/equipment/reference/tire-sizes")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_reference_brake_fluids(self, client: AsyncClient) -> None:
        """GET /api/equipment/reference/brake-fluids returns a list."""
        resp = await client.get("/api/equipment/reference/brake-fluids")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestTireBrakeSearch:
    """Tests for tire and brake pad search endpoints."""

    @pytest.mark.asyncio
    async def test_search_tires_no_query(self, client: AsyncClient) -> None:
        """GET /api/equipment/tires/search with no query lists all."""
        resp = await client.get("/api/equipment/tires/search")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_search_tires_with_query(self, client: AsyncClient) -> None:
        """GET /api/equipment/tires/search?q=... filters results."""
        resp = await client.get("/api/equipment/tires/search?q=re71")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_search_brake_pads_no_query(self, client: AsyncClient) -> None:
        """GET /api/equipment/brakes/search with no query lists all."""
        resp = await client.get("/api/equipment/brakes/search")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

"""Integration tests for the equipment router (backend/api/routers/equipment.py).

All tests use the conftest ``client`` fixture (httpx.AsyncClient) wired to the
FastAPI app, and the ``_test_db`` / ``_mock_auth`` autouse fixtures for SQLite
isolation and auth bypass.  The ``async_session_factory`` used by
``equipment_store`` is patched to route through the test SQLite engine so that
profile and session-equipment DB persistence calls succeed without a live
PostgreSQL server.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.api.services import equipment_store
from backend.tests.conftest import _test_session_factory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_equipment_db() -> Generator[None, None, None]:
    """Route equipment_store DB calls through the test SQLite session factory.

    equipment_store lazy-imports ``async_session_factory`` from
    ``backend.api.db.database`` inside each async helper, so patching the
    module-level name is sufficient.
    """
    with patch(
        "backend.api.db.database.async_session_factory",
        _test_session_factory,
    ):
        yield


@pytest.fixture(autouse=True)
def _clear_equipment() -> Generator[None, None, None]:
    """Clear in-memory equipment stores before and after every test."""
    equipment_store.clear_all_equipment()
    yield
    equipment_store.clear_all_equipment()


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_TIRE: dict[str, object] = {
    "model": "Bridgestone RE-71RS",
    "compound_category": "super_200tw",
    "size": "255/40R17",
    "treadwear_rating": 200,
    "estimated_mu": 1.10,
    "mu_source": "curated_table",
    "mu_confidence": "Track test aggregate",
}

SAMPLE_TIRE_MINIMAL: dict[str, object] = {
    "model": "Test Tire",
    "compound_category": "street",
    "size": "255/40R17",
    "treadwear_rating": 200,
    "estimated_mu": 1.0,
    "mu_source": "manufacturer_spec",
    "mu_confidence": "low",
    "brand": "TestBrand",
}

SAMPLE_PROFILE: dict[str, object] = {"name": "Track Day Setup", "tires": SAMPLE_TIRE}

SAMPLE_PROFILE_MINIMAL: dict[str, object] = {
    "name": "Test Profile",
    "tires": SAMPLE_TIRE_MINIMAL,
}

SAMPLE_BRAKES: dict[str, object] = {
    "compound": "Ferodo DS2500",
    "rotor_type": "slotted",
    "pad_temp_range": "200-600C",
    "fluid_type": "Motul RBF 660",
}

SAMPLE_SUSPENSION: dict[str, object] = {
    "type": "coilover",
    "front_spring_rate": "700 lb/in",
    "rear_spring_rate": "500 lb/in",
    "front_camber_deg": -2.5,
    "rear_camber_deg": -1.8,
    "front_toe": "0 mm",
    "rear_toe": "2 mm in",
    "front_rebound": 8,
    "front_compression": 5,
    "rear_rebound": 7,
    "rear_compression": 4,
    "sway_bar_front": "stiff",
    "sway_bar_rear": "medium",
}

FULL_PROFILE: dict[str, object] = {
    "name": "Full Race Setup",
    "tires": SAMPLE_TIRE,
    "brakes": SAMPLE_BRAKES,
    "suspension": SAMPLE_SUSPENSION,
    "notes": "Spa configuration",
}


# ---------------------------------------------------------------------------
# Helper: upload a session and return its session_id
# ---------------------------------------------------------------------------


async def _upload_session(client: AsyncClient) -> str:
    from backend.tests.conftest import build_synthetic_csv

    csv_bytes = build_synthetic_csv()
    resp = await client.post(
        "/api/sessions/upload",
        files={"files": ("test.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["session_ids"][0])


# ---------------------------------------------------------------------------
# GET /tires/search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tire_search_no_query_returns_all(client: AsyncClient) -> None:
    """Omitting the ``q`` parameter returns all curated tires."""
    resp = await client.get("/api/equipment/tires/search")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Each item must have the required TireSpecSchema fields
    first = data[0]
    assert "model" in first
    assert "compound_category" in first
    assert "estimated_mu" in first
    assert "mu_source" in first


@pytest.mark.asyncio
async def test_tire_search_empty_q_returns_all(client: AsyncClient) -> None:
    """Empty ``q`` query param returns all curated tires."""
    resp = await client.get("/api/equipment/tires/search", params={"q": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_tire_search_known_model(client: AsyncClient) -> None:
    """Searching for a known model returns matching results."""
    resp = await client.get("/api/equipment/tires/search", params={"q": "RE-71RS"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "RE-71RS" in data[0]["model"]
    assert data[0]["mu_source"] == "curated_table"


@pytest.mark.asyncio
async def test_tire_search_no_match_returns_empty_list(client: AsyncClient) -> None:
    """Query that matches nothing returns an empty list."""
    resp = await client.get("/api/equipment/tires/search", params={"q": "ZZZnonexistent9999"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_tire_search_by_brand(client: AsyncClient) -> None:
    """Searching by brand returns tires with that brand."""
    resp = await client.get("/api/equipment/tires/search", params={"q": "Michelin"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(t["brand"] == "Michelin" for t in data)


@pytest.mark.asyncio
async def test_tire_search_single_char_query(client: AsyncClient) -> None:
    """Single-character query still executes without error."""
    resp = await client.get("/api/equipment/tires/search", params={"q": "B"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# GET /brakes/search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brakes_search_no_query_returns_all(client: AsyncClient) -> None:
    """Omitting the ``q`` parameter returns all curated brake pads."""
    resp = await client.get("/api/equipment/brakes/search")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    first = data[0]
    assert "model" in first
    assert "brand" in first
    assert "category" in first
    assert "temp_range" in first
    assert "initial_bite" in first
    assert "notes" in first


@pytest.mark.asyncio
async def test_brakes_search_empty_q_returns_all(client: AsyncClient) -> None:
    """Empty ``q`` query param returns all curated brake pads."""
    resp = await client.get("/api/equipment/brakes/search", params={"q": ""})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_brakes_search_known_brand(client: AsyncClient) -> None:
    """Searching by a known brand returns matching brake pads."""
    resp = await client.get("/api/equipment/brakes/search", params={"q": "Hawk"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["brand"] == "Hawk"


@pytest.mark.asyncio
async def test_brakes_search_no_match_returns_empty_list(client: AsyncClient) -> None:
    """Query that matches nothing returns an empty list."""
    resp = await client.get("/api/equipment/brakes/search", params={"q": "ZZZnonexistent9999"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_brakes_search_single_char_query(client: AsyncClient) -> None:
    """Single-character query still executes without error."""
    resp = await client.get("/api/equipment/brakes/search", params={"q": "F"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# GET /reference/tire-sizes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reference_tire_sizes_returns_list(client: AsyncClient) -> None:
    """Returns a non-empty list of tire size strings."""
    resp = await client.get("/api/equipment/reference/tire-sizes")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 10


@pytest.mark.asyncio
async def test_reference_tire_sizes_contains_known_sizes(client: AsyncClient) -> None:
    """Common track day sizes appear in the reference list."""
    resp = await client.get("/api/equipment/reference/tire-sizes")
    assert resp.status_code == 200
    data = resp.json()
    assert "255/40R17" in data
    assert "245/40R18" in data


@pytest.mark.asyncio
async def test_reference_tire_sizes_items_are_strings(client: AsyncClient) -> None:
    """All returned tire sizes are non-empty strings."""
    resp = await client.get("/api/equipment/reference/tire-sizes")
    assert resp.status_code == 200
    for size in resp.json():
        assert isinstance(size, str)
        assert len(size) > 0


# ---------------------------------------------------------------------------
# GET /reference/brake-fluids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reference_brake_fluids_returns_list(client: AsyncClient) -> None:
    """Returns a non-empty list of brake fluid strings."""
    resp = await client.get("/api/equipment/reference/brake-fluids")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 5


@pytest.mark.asyncio
async def test_reference_brake_fluids_contains_known_fluids(client: AsyncClient) -> None:
    """Common brake fluids appear in the reference list."""
    resp = await client.get("/api/equipment/reference/brake-fluids")
    assert resp.status_code == 200
    data = resp.json()
    assert "DOT 4" in data
    assert "Motul RBF 600" in data
    assert "Castrol SRF" in data


@pytest.mark.asyncio
async def test_reference_brake_fluids_items_are_strings(client: AsyncClient) -> None:
    """All returned brake fluid entries are non-empty strings."""
    resp = await client.get("/api/equipment/reference/brake-fluids")
    assert resp.status_code == 200
    for fluid in resp.json():
        assert isinstance(fluid, str)
        assert len(fluid) > 0


# ---------------------------------------------------------------------------
# POST /weather/lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weather_lookup_returns_conditions(client: AsyncClient) -> None:
    """Successful weather lookup returns track conditions object."""
    from cataclysm.equipment import SessionConditions, TrackCondition

    mock_result = SessionConditions(
        track_condition=TrackCondition.DRY,
        ambient_temp_c=25.0,
        humidity_pct=60.0,
        wind_speed_kmh=15.0,
        wind_direction_deg=180.0,
        precipitation_mm=0.0,
        weather_source="open-meteo",
    )
    with patch("cataclysm.weather_client.lookup_weather", AsyncMock(return_value=mock_result)):
        resp = await client.post(
            "/api/equipment/weather/lookup",
            json={"lat": 33.53, "lon": -86.62, "session_date": "2025-02-15"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "conditions" in data
    cond = data["conditions"]
    assert cond["track_condition"] == "dry"
    assert cond["ambient_temp_c"] == 25.0
    assert cond["humidity_pct"] == 60.0
    assert cond["wind_speed_kmh"] == 15.0
    assert cond["precipitation_mm"] == 0.0
    assert cond["weather_source"] == "open-meteo"


@pytest.mark.asyncio
async def test_weather_lookup_unavailable_returns_null_conditions(client: AsyncClient) -> None:
    """When weather client returns None, response has conditions=null and a message."""
    with patch("cataclysm.weather_client.lookup_weather", AsyncMock(return_value=None)):
        resp = await client.post(
            "/api/equipment/weather/lookup",
            json={"lat": 33.53, "lon": -86.62, "session_date": "2025-02-15"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["conditions"] is None
    assert data["message"] == "Weather data unavailable"


@pytest.mark.asyncio
async def test_weather_lookup_custom_hour_passed_correctly(client: AsyncClient) -> None:
    """The ``hour`` field in the request is forwarded to the weather client."""
    from cataclysm.equipment import SessionConditions, TrackCondition

    mock_result = SessionConditions(
        track_condition=TrackCondition.WET,
        ambient_temp_c=18.0,
        humidity_pct=90.0,
        precipitation_mm=5.2,
        weather_source="open-meteo",
    )
    mock_fn = AsyncMock(return_value=mock_result)
    with patch("cataclysm.weather_client.lookup_weather", mock_fn):
        resp = await client.post(
            "/api/equipment/weather/lookup",
            json={"lat": 33.53, "lon": -86.62, "session_date": "2025-02-15", "hour": 9},
        )
    assert resp.status_code == 200
    # Verify the datetime sent to lookup_weather has hour=9
    passed_dt = mock_fn.call_args[0][2]
    assert passed_dt.hour == 9
    assert resp.json()["conditions"]["track_condition"] == "wet"


@pytest.mark.asyncio
async def test_weather_lookup_wet_conditions_all_fields(client: AsyncClient) -> None:
    """Wet conditions response includes all fields that the endpoint maps.

    Note: the weather_lookup endpoint deliberately omits ``track_temp_c`` from
    the SessionConditionsSchema constructor, so that field will always be null
    in the response even when set on the domain object.
    """
    from cataclysm.equipment import SessionConditions, TrackCondition

    mock_result = SessionConditions(
        track_condition=TrackCondition.WET,
        ambient_temp_c=12.0,
        track_temp_c=15.0,  # populated on domain, but not forwarded by endpoint
        humidity_pct=95.0,
        wind_speed_kmh=30.0,
        wind_direction_deg=270.0,
        precipitation_mm=8.5,
        weather_source="open-meteo",
    )
    with patch("cataclysm.weather_client.lookup_weather", AsyncMock(return_value=mock_result)):
        resp = await client.post(
            "/api/equipment/weather/lookup",
            json={"lat": 51.5, "lon": -1.75, "session_date": "2025-08-10"},
        )
    assert resp.status_code == 200
    cond = resp.json()["conditions"]
    assert cond["track_condition"] == "wet"
    # track_temp_c is not forwarded by the weather_lookup endpoint
    assert cond["track_temp_c"] is None
    assert cond["wind_direction_deg"] == 270.0
    assert cond["precipitation_mm"] == 8.5
    assert cond["humidity_pct"] == 95.0
    assert cond["wind_speed_kmh"] == 30.0


# ---------------------------------------------------------------------------
# POST /profiles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_profile_minimal(client: AsyncClient) -> None:
    """Creating a profile with only required fields succeeds."""
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE_MINIMAL)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Profile"
    assert data["id"].startswith("eq_")
    assert data["tires"]["model"] == "Test Tire"
    assert data["brakes"] is None
    assert data["suspension"] is None
    assert data["notes"] is None


@pytest.mark.asyncio
async def test_create_profile_returns_201(client: AsyncClient) -> None:
    """Profile creation returns HTTP 201."""
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_profile_id_format(client: AsyncClient) -> None:
    """Created profile ID starts with 'eq_' and is 15 chars total."""
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    data = resp.json()
    # eq_ prefix + 12 hex chars = 15
    assert data["id"].startswith("eq_")
    assert len(data["id"]) == 15


@pytest.mark.asyncio
async def test_create_profile_tire_fields_round_trip(client: AsyncClient) -> None:
    """All tire spec fields survive the create → response round-trip."""
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    assert resp.status_code == 201
    t = resp.json()["tires"]
    assert t["model"] == "Bridgestone RE-71RS"
    assert t["compound_category"] == "super_200tw"
    assert t["size"] == "255/40R17"
    assert t["treadwear_rating"] == 200
    assert t["estimated_mu"] == 1.10
    assert t["mu_source"] == "curated_table"
    assert t["mu_confidence"] == "Track test aggregate"


@pytest.mark.asyncio
async def test_create_profile_with_brakes(client: AsyncClient) -> None:
    """Profile with brake spec persists all brake fields."""
    payload = {"name": "Brake Setup", "tires": SAMPLE_TIRE, "brakes": SAMPLE_BRAKES}
    resp = await client.post("/api/equipment/profiles", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    b = data["brakes"]
    assert b["compound"] == "Ferodo DS2500"
    assert b["rotor_type"] == "slotted"
    assert b["pad_temp_range"] == "200-600C"
    assert b["fluid_type"] == "Motul RBF 660"
    assert data["suspension"] is None


@pytest.mark.asyncio
async def test_create_profile_with_suspension(client: AsyncClient) -> None:
    """Profile with suspension spec persists all suspension fields."""
    payload = {
        "name": "Suspension Setup",
        "tires": SAMPLE_TIRE,
        "suspension": SAMPLE_SUSPENSION,
    }
    resp = await client.post("/api/equipment/profiles", json=payload)
    assert resp.status_code == 201
    s = resp.json()["suspension"]
    assert s["type"] == "coilover"
    assert s["front_camber_deg"] == -2.5
    assert s["rear_camber_deg"] == -1.8
    assert s["front_rebound"] == 8
    assert s["front_compression"] == 5
    assert s["rear_rebound"] == 7
    assert s["rear_compression"] == 4
    assert s["sway_bar_front"] == "stiff"
    assert s["sway_bar_rear"] == "medium"


@pytest.mark.asyncio
async def test_create_full_profile(client: AsyncClient) -> None:
    """Full profile with all optional fields round-trips correctly."""
    resp = await client.post("/api/equipment/profiles", json=FULL_PROFILE)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Full Race Setup"
    assert data["notes"] == "Spa configuration"
    assert data["brakes"]["compound"] == "Ferodo DS2500"
    assert data["suspension"]["type"] == "coilover"


@pytest.mark.asyncio
async def test_create_profile_with_notes(client: AsyncClient) -> None:
    """Profile with notes field persists the notes."""
    payload = {
        "name": "Noted Setup",
        "tires": SAMPLE_TIRE,
        "notes": "For wet conditions only",
    }
    resp = await client.post("/api/equipment/profiles", json=payload)
    assert resp.status_code == 201
    assert resp.json()["notes"] == "For wet conditions only"


@pytest.mark.asyncio
async def test_create_profile_empty_name_rejected(client: AsyncClient) -> None:
    """Profile with empty name is rejected with 422."""
    payload = {"name": "", "tires": SAMPLE_TIRE}
    resp = await client.post("/api/equipment/profiles", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_profile_missing_tires_rejected(client: AsyncClient) -> None:
    """Profile without tires field is rejected with 422."""
    resp = await client.post("/api/equipment/profiles", json={"name": "No Tires"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /profiles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_profiles_empty(client: AsyncClient) -> None:
    """Listing profiles when none exist returns empty list with total=0."""
    resp = await client.get("/api/equipment/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_profiles_after_create(client: AsyncClient) -> None:
    """Profile appears in list after creation."""
    await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    resp = await client.get("/api/equipment/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Track Day Setup"


@pytest.mark.asyncio
async def test_list_profiles_multiple(client: AsyncClient) -> None:
    """Multiple profiles all appear in the list."""
    await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    await client.post(
        "/api/equipment/profiles",
        json={"name": "Second Setup", "tires": SAMPLE_TIRE},
    )
    resp = await client.get("/api/equipment/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    names = {item["name"] for item in data["items"]}
    assert "Track Day Setup" in names
    assert "Second Setup" in names


@pytest.mark.asyncio
async def test_list_profiles_sorted_by_name(client: AsyncClient) -> None:
    """Profiles are returned in alphabetical order by name."""
    for name in ["Zeta Setup", "Alpha Setup", "Mu Setup"]:
        await client.post(
            "/api/equipment/profiles",
            json={"name": name, "tires": SAMPLE_TIRE},
        )
    resp = await client.get("/api/equipment/profiles")
    names = [item["name"] for item in resp.json()["items"]]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# GET /profiles/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_profile_by_id(client: AsyncClient) -> None:
    """GET by ID returns the correct profile."""
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    resp = await client.get(f"/api/equipment/profiles/{profile_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == profile_id
    assert data["name"] == "Track Day Setup"
    assert data["tires"]["model"] == "Bridgestone RE-71RS"


@pytest.mark.asyncio
async def test_get_profile_not_found_returns_404(client: AsyncClient) -> None:
    """GET with a nonexistent ID returns 404."""
    resp = await client.get("/api/equipment/profiles/eq_doesnotexist00")
    assert resp.status_code == 404
    assert "eq_doesnotexist00" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_profile_full_round_trip(client: AsyncClient) -> None:
    """GET returns full profile including brakes and suspension."""
    create_resp = await client.post("/api/equipment/profiles", json=FULL_PROFILE)
    profile_id = create_resp.json()["id"]

    resp = await client.get(f"/api/equipment/profiles/{profile_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["notes"] == "Spa configuration"
    assert data["brakes"]["compound"] == "Ferodo DS2500"
    assert data["suspension"]["type"] == "coilover"


# ---------------------------------------------------------------------------
# PATCH /profiles/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_profile_name(client: AsyncClient) -> None:
    """PATCH updates the profile name."""
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    updated = {"name": "Renamed Setup", "tires": SAMPLE_TIRE}
    resp = await client.patch(f"/api/equipment/profiles/{profile_id}", json=updated)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Renamed Setup"
    assert data["id"] == profile_id


@pytest.mark.asyncio
async def test_update_profile_adds_brakes(client: AsyncClient) -> None:
    """PATCH can add brakes to a profile that previously had none."""
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    updated = {"name": "Track Day Setup", "tires": SAMPLE_TIRE, "brakes": SAMPLE_BRAKES}
    resp = await client.patch(f"/api/equipment/profiles/{profile_id}", json=updated)
    assert resp.status_code == 200
    assert resp.json()["brakes"]["compound"] == "Ferodo DS2500"


@pytest.mark.asyncio
async def test_update_profile_adds_notes(client: AsyncClient) -> None:
    """PATCH can add notes to an existing profile."""
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    updated = {"name": "Track Day Setup", "tires": SAMPLE_TIRE, "notes": "Added notes"}
    resp = await client.patch(f"/api/equipment/profiles/{profile_id}", json=updated)
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Added notes"


@pytest.mark.asyncio
async def test_update_profile_not_found_returns_404(client: AsyncClient) -> None:
    """PATCH on a nonexistent profile returns 404."""
    resp = await client.patch(
        "/api/equipment/profiles/eq_doesnotexist00",
        json=SAMPLE_PROFILE,
    )
    assert resp.status_code == 404
    assert "eq_doesnotexist00" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_profile_id_unchanged(client: AsyncClient) -> None:
    """PATCH never changes the profile ID."""
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    original_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/equipment/profiles/{original_id}",
        json={"name": "New Name", "tires": SAMPLE_TIRE},
    )
    assert resp.json()["id"] == original_id


# ---------------------------------------------------------------------------
# DELETE /profiles/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_profile_success(client: AsyncClient) -> None:
    """Deleting an existing profile returns 200 with a message."""
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/equipment/profiles/{profile_id}")
    assert resp.status_code == 200
    assert profile_id in resp.json()["message"]


@pytest.mark.asyncio
async def test_delete_profile_then_get_404(client: AsyncClient) -> None:
    """Deleted profile is no longer accessible via GET."""
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    await client.delete(f"/api/equipment/profiles/{profile_id}")

    resp = await client.get(f"/api/equipment/profiles/{profile_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_profile_removed_from_list(client: AsyncClient) -> None:
    """Deleted profile no longer appears in GET /profiles."""
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]
    await client.post(
        "/api/equipment/profiles",
        json={"name": "Second Setup", "tires": SAMPLE_TIRE},
    )

    await client.delete(f"/api/equipment/profiles/{profile_id}")

    list_resp = await client.get("/api/equipment/profiles")
    data = list_resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Second Setup"


@pytest.mark.asyncio
async def test_delete_profile_not_found_returns_404(client: AsyncClient) -> None:
    """Deleting a nonexistent profile returns 404."""
    resp = await client.delete("/api/equipment/profiles/eq_doesnotexist00")
    assert resp.status_code == 404
    assert "eq_doesnotexist00" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_profile_twice_returns_404(client: AsyncClient) -> None:
    """Deleting an already-deleted profile returns 404 on the second call."""
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    await client.delete(f"/api/equipment/profiles/{profile_id}")
    resp = await client.delete(f"/api/equipment/profiles/{profile_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /{session_id}/equipment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_session_equipment_success(client: AsyncClient) -> None:
    """Assigning an equipment profile to a session returns full assignment."""
    session_id = await _upload_session(client)

    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["profile_id"] == profile_id
    assert data["profile_name"] == "Track Day Setup"
    assert data["tires"]["model"] == "Bridgestone RE-71RS"
    assert data["overrides"] == {}


@pytest.mark.asyncio
async def test_set_session_equipment_with_conditions(client: AsyncClient) -> None:
    """Assigning equipment with conditions persists and returns conditions."""
    session_id = await _upload_session(client)
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    conditions = {
        "track_condition": "dry",
        "ambient_temp_c": 28.0,
        "humidity_pct": 55.0,
        "wind_speed_kmh": 10.0,
    }
    resp = await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id, "conditions": conditions},
    )
    assert resp.status_code == 200
    cond = resp.json()["conditions"]
    assert cond["track_condition"] == "dry"
    assert cond["ambient_temp_c"] == 28.0
    assert cond["humidity_pct"] == 55.0


@pytest.mark.asyncio
async def test_set_session_equipment_with_overrides(client: AsyncClient) -> None:
    """Assigning equipment with overrides dict persists them."""
    session_id = await _upload_session(client)
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    overrides = {"pressure_psi": 32.5, "age_sessions": 3}
    resp = await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id, "overrides": overrides},
    )
    assert resp.status_code == 200
    assert resp.json()["overrides"]["pressure_psi"] == 32.5
    assert resp.json()["overrides"]["age_sessions"] == 3


@pytest.mark.asyncio
async def test_set_session_equipment_invalid_session_404(client: AsyncClient) -> None:
    """Assigning equipment to a nonexistent session returns 404."""
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    resp = await client.put(
        "/api/equipment/nonexistent-session-id/equipment",
        json={"profile_id": profile_id},
    )
    assert resp.status_code == 404
    assert "nonexistent-session-id" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_set_session_equipment_invalid_profile_404(client: AsyncClient) -> None:
    """Assigning a nonexistent profile to a session returns 404."""
    session_id = await _upload_session(client)

    resp = await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": "eq_doesnotexist00"},
    )
    assert resp.status_code == 404
    assert "eq_doesnotexist00" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_set_session_equipment_with_full_profile(client: AsyncClient) -> None:
    """Assignment with a full profile (brakes + suspension) returns all component specs."""
    session_id = await _upload_session(client)
    create_resp = await client.post("/api/equipment/profiles", json=FULL_PROFILE)
    profile_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["brakes"]["compound"] == "Ferodo DS2500"
    assert data["suspension"]["type"] == "coilover"


@pytest.mark.asyncio
async def test_set_session_equipment_reassignment(client: AsyncClient) -> None:
    """Re-assigning a different profile to a session overwrites the previous one."""
    session_id = await _upload_session(client)

    resp1 = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    resp2 = await client.post(
        "/api/equipment/profiles",
        json={"name": "New Setup", "tires": SAMPLE_TIRE},
    )
    profile_id_1 = resp1.json()["id"]
    profile_id_2 = resp2.json()["id"]

    await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id_1},
    )
    put_resp = await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id_2},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["profile_id"] == profile_id_2
    assert put_resp.json()["profile_name"] == "New Setup"


# ---------------------------------------------------------------------------
# GET /{session_id}/equipment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_session_equipment_success(client: AsyncClient) -> None:
    """GET returns the assigned equipment for a session."""
    session_id = await _upload_session(client)
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id},
    )

    resp = await client.get(f"/api/equipment/{session_id}/equipment")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["profile_id"] == profile_id
    assert data["profile_name"] == "Track Day Setup"
    assert data["tires"]["model"] == "Bridgestone RE-71RS"


@pytest.mark.asyncio
async def test_get_session_equipment_no_assignment_returns_404(client: AsyncClient) -> None:
    """GET for a session with no equipment assignment returns 404."""
    session_id = await _upload_session(client)
    resp = await client.get(f"/api/equipment/{session_id}/equipment")
    assert resp.status_code == 404
    assert session_id in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_session_equipment_unknown_session_returns_404(client: AsyncClient) -> None:
    """GET for an entirely unknown session_id returns 404."""
    resp = await client.get("/api/equipment/totally-unknown-session/equipment")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_session_equipment_dangling_profile_returns_404(client: AsyncClient) -> None:
    """GET returns 404 when the referenced profile has been deleted."""
    session_id = await _upload_session(client)
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id},
    )
    # Delete the profile after assigning it — creates a dangling reference
    await client.delete(f"/api/equipment/profiles/{profile_id}")

    resp = await client.get(f"/api/equipment/{session_id}/equipment")
    assert resp.status_code == 404
    assert profile_id in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_session_equipment_includes_conditions(client: AsyncClient) -> None:
    """GET returns conditions when they were set at assignment time."""
    session_id = await _upload_session(client)
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    conditions = {"track_condition": "wet", "ambient_temp_c": 15.0, "precipitation_mm": 3.0}
    await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id, "conditions": conditions},
    )

    resp = await client.get(f"/api/equipment/{session_id}/equipment")
    assert resp.status_code == 200
    cond = resp.json()["conditions"]
    assert cond["track_condition"] == "wet"
    assert cond["ambient_temp_c"] == 15.0
    assert cond["precipitation_mm"] == 3.0


@pytest.mark.asyncio
async def test_get_session_equipment_no_conditions_is_null(client: AsyncClient) -> None:
    """GET returns null conditions when none were set at assignment time."""
    session_id = await _upload_session(client)
    create_resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = create_resp.json()["id"]

    await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id},
    )

    resp = await client.get(f"/api/equipment/{session_id}/equipment")
    assert resp.status_code == 200
    assert resp.json()["conditions"] is None


# ---------------------------------------------------------------------------
# Conversion helper unit tests
# ---------------------------------------------------------------------------


def test_schema_to_tire_and_back() -> None:
    """_schema_to_tire / _tire_to_schema are inverse operations."""
    from backend.api.routers.equipment import _schema_to_tire, _tire_to_schema
    from backend.api.schemas.equipment import TireSpecSchema

    schema = TireSpecSchema(
        model="Yokohama ADVAN A052",
        compound_category="super_200tw",
        size="245/45R17",
        treadwear_rating=200,
        estimated_mu=1.15,
        mu_source="curated_table",
        mu_confidence="Track test aggregate",
        pressure_psi=36.0,
        brand="Yokohama",
        age_sessions=5,
    )
    domain = _schema_to_tire(schema)
    assert domain.model == "Yokohama ADVAN A052"
    assert domain.pressure_psi == 36.0
    assert domain.age_sessions == 5

    roundtrip = _tire_to_schema(domain)
    assert roundtrip.model == schema.model
    assert roundtrip.compound_category == schema.compound_category
    assert roundtrip.size == schema.size
    assert roundtrip.pressure_psi == schema.pressure_psi
    assert roundtrip.brand == schema.brand
    assert roundtrip.age_sessions == schema.age_sessions


def test_schema_to_tire_optional_fields_none() -> None:
    """_schema_to_tire handles optional fields being None."""
    from backend.api.routers.equipment import _schema_to_tire
    from backend.api.schemas.equipment import TireSpecSchema

    schema = TireSpecSchema(
        model="Generic",
        compound_category="street",
        size="205/55R16",
        estimated_mu=0.9,
        mu_source="manufacturer_spec",
        mu_confidence="low",
    )
    domain = _schema_to_tire(schema)
    assert domain.treadwear_rating is None
    assert domain.pressure_psi is None
    assert domain.brand is None
    assert domain.age_sessions is None


def test_schema_to_brakes_and_back() -> None:
    """_schema_to_brakes / _brakes_to_schema are inverse operations."""
    from backend.api.routers.equipment import _brakes_to_schema, _schema_to_brakes
    from backend.api.schemas.equipment import BrakeSpecSchema

    schema = BrakeSpecSchema(
        compound="Ferodo DS2500",
        rotor_type="drilled",
        pad_temp_range="150-500C",
        fluid_type="Castrol SRF",
    )
    domain = _schema_to_brakes(schema)
    assert domain.compound == "Ferodo DS2500"
    assert domain.fluid_type == "Castrol SRF"

    roundtrip = _brakes_to_schema(domain)
    assert roundtrip.compound == schema.compound
    assert roundtrip.rotor_type == schema.rotor_type
    assert roundtrip.pad_temp_range == schema.pad_temp_range
    assert roundtrip.fluid_type == schema.fluid_type


def test_schema_to_brakes_all_none() -> None:
    """_schema_to_brakes handles all-None BrakeSpecSchema."""
    from backend.api.routers.equipment import _schema_to_brakes
    from backend.api.schemas.equipment import BrakeSpecSchema

    domain = _schema_to_brakes(BrakeSpecSchema())
    assert domain.compound is None
    assert domain.rotor_type is None
    assert domain.pad_temp_range is None
    assert domain.fluid_type is None


def test_schema_to_suspension_and_back() -> None:
    """_schema_to_suspension / _suspension_to_schema are inverse operations."""
    from backend.api.routers.equipment import _schema_to_suspension, _suspension_to_schema
    from backend.api.schemas.equipment import SuspensionSpecSchema

    schema = SuspensionSpecSchema(
        type="coilover",
        front_spring_rate="700 lb/in",
        rear_spring_rate="500 lb/in",
        front_camber_deg=-2.5,
        rear_camber_deg=-1.8,
        front_toe="0 mm",
        rear_toe="2 mm in",
        front_rebound=8,
        front_compression=5,
        rear_rebound=7,
        rear_compression=4,
        sway_bar_front="stiff",
        sway_bar_rear="medium",
    )
    domain = _schema_to_suspension(schema)
    assert domain.type == "coilover"
    assert domain.front_camber_deg == -2.5
    assert domain.front_rebound == 8

    roundtrip = _suspension_to_schema(domain)
    assert roundtrip.type == schema.type
    assert roundtrip.front_camber_deg == schema.front_camber_deg
    assert roundtrip.rear_camber_deg == schema.rear_camber_deg
    assert roundtrip.front_rebound == schema.front_rebound
    assert roundtrip.sway_bar_front == schema.sway_bar_front


def test_schema_to_suspension_all_none() -> None:
    """_schema_to_suspension handles all-None SuspensionSpecSchema."""
    from backend.api.routers.equipment import _schema_to_suspension
    from backend.api.schemas.equipment import SuspensionSpecSchema

    domain = _schema_to_suspension(SuspensionSpecSchema())
    assert domain.type is None
    assert domain.front_camber_deg is None
    assert domain.front_rebound is None


def test_profile_to_response_minimal() -> None:
    """_profile_to_response maps an EquipmentProfile without optional fields."""
    from cataclysm.equipment import EquipmentProfile, MuSource, TireCompoundCategory, TireSpec

    from backend.api.routers.equipment import _profile_to_response

    tire = TireSpec(
        model="Generic Street",
        compound_category=TireCompoundCategory.STREET,
        size="205/55R16",
        treadwear_rating=None,
        estimated_mu=0.9,
        mu_source=MuSource.MANUFACTURER_SPEC,
        mu_confidence="low",
    )
    profile = EquipmentProfile(id="eq_abc123", name="Minimal", tires=tire)
    resp = _profile_to_response(profile)

    assert resp.id == "eq_abc123"
    assert resp.name == "Minimal"
    assert resp.tires.model == "Generic Street"
    assert resp.brakes is None
    assert resp.suspension is None
    assert resp.notes is None


def test_profile_to_response_with_brakes_and_suspension() -> None:
    """_profile_to_response maps optional brakes and suspension fields."""
    from cataclysm.equipment import (
        BrakeSpec,
        EquipmentProfile,
        MuSource,
        SuspensionSpec,
        TireCompoundCategory,
        TireSpec,
    )

    from backend.api.routers.equipment import _profile_to_response

    tire = TireSpec(
        model="RE-71RS",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="255/40R17",
        treadwear_rating=200,
        estimated_mu=1.10,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="high",
    )
    brakes = BrakeSpec(compound="Hawk DTC-60", fluid_type="Castrol SRF")
    susp = SuspensionSpec(type="coilover", front_camber_deg=-3.0)
    profile = EquipmentProfile(
        id="eq_full",
        name="Full Setup",
        tires=tire,
        brakes=brakes,
        suspension=susp,
        notes="Race notes",
    )
    resp = _profile_to_response(profile)

    assert resp.brakes is not None
    assert resp.brakes.compound == "Hawk DTC-60"
    assert resp.brakes.fluid_type == "Castrol SRF"
    assert resp.suspension is not None
    assert resp.suspension.type == "coilover"
    assert resp.suspension.front_camber_deg == -3.0
    assert resp.notes == "Race notes"


def test_conditions_to_schema_all_fields() -> None:
    """_conditions_to_schema maps all SessionConditions fields correctly."""
    from cataclysm.equipment import SessionConditions, TrackCondition

    from backend.api.routers.equipment import _conditions_to_schema

    conditions = SessionConditions(
        track_condition=TrackCondition.WET,
        ambient_temp_c=12.0,
        track_temp_c=14.0,
        humidity_pct=95.0,
        wind_speed_kmh=25.0,
        wind_direction_deg=270.0,
        precipitation_mm=7.5,
        weather_source="open-meteo",
    )
    schema = _conditions_to_schema(conditions)

    assert schema.track_condition == "wet"
    assert schema.ambient_temp_c == 12.0
    assert schema.track_temp_c == 14.0
    assert schema.humidity_pct == 95.0
    assert schema.wind_speed_kmh == 25.0
    assert schema.wind_direction_deg == 270.0
    assert schema.precipitation_mm == 7.5
    assert schema.weather_source == "open-meteo"


def test_conditions_to_schema_minimal() -> None:
    """_conditions_to_schema handles a minimal SessionConditions (all optional fields None)."""
    from cataclysm.equipment import SessionConditions, TrackCondition

    from backend.api.routers.equipment import _conditions_to_schema

    conditions = SessionConditions(track_condition=TrackCondition.DRY)
    schema = _conditions_to_schema(conditions)

    assert schema.track_condition == "dry"
    assert schema.ambient_temp_c is None
    assert schema.track_temp_c is None
    assert schema.humidity_pct is None
    assert schema.precipitation_mm is None
    assert schema.weather_source is None

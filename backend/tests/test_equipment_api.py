"""Tests for equipment API endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.api.services import equipment_store
from backend.api.services.session_store import clear_all as clear_all_sessions


@pytest.fixture(autouse=True)
def _disable_auto_coaching() -> Generator[None, None, None]:
    """Disable auto-coaching on upload in equipment tests."""
    with patch("backend.api.routers.sessions.trigger_auto_coaching"):
        yield


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    equipment_store.clear_all_equipment()
    clear_all_sessions()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    equipment_store.clear_all_equipment()
    clear_all_sessions()


SAMPLE_TIRE: dict[str, object] = {
    "model": "Bridgestone RE-71RS",
    "compound_category": "super_200tw",
    "size": "255/40R17",
    "treadwear_rating": 200,
    "estimated_mu": 1.10,
    "mu_source": "curated_table",
    "mu_confidence": "Track test aggregate",
}

SAMPLE_PROFILE: dict[str, object] = {"name": "Track Day Setup", "tires": SAMPLE_TIRE}

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


@pytest.mark.asyncio
async def test_create_and_get_profile(client: AsyncClient) -> None:
    """POST create a profile, then GET it by ID and verify fields."""
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Track Day Setup"
    assert data["id"].startswith("eq_")
    assert data["tires"]["model"] == "Bridgestone RE-71RS"
    assert data["tires"]["estimated_mu"] == 1.10

    profile_id = data["id"]
    resp2 = await client.get(f"/api/equipment/profiles/{profile_id}")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["id"] == profile_id
    assert data2["name"] == "Track Day Setup"
    assert data2["tires"]["compound_category"] == "super_200tw"


@pytest.mark.asyncio
async def test_list_profiles(client: AsyncClient) -> None:
    """Create one profile, list all, verify total=1."""
    await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    resp = await client.get("/api/equipment/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Track Day Setup"


@pytest.mark.asyncio
async def test_delete_profile(client: AsyncClient) -> None:
    """Create, delete, then verify 404 on GET."""
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = resp.json()["id"]

    del_resp = await client.delete(f"/api/equipment/profiles/{profile_id}")
    assert del_resp.status_code == 200

    get_resp = await client.get(f"/api/equipment/profiles/{profile_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_missing_profile_404(client: AsyncClient) -> None:
    """GET a nonexistent profile returns 404."""
    resp = await client.get("/api/equipment/profiles/eq_nonexistent99")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_profile_with_brakes_and_suspension(client: AsyncClient) -> None:
    """Create a full profile with brakes and suspension, verify all fields."""
    full_profile: dict[str, object] = {
        "name": "Full Race Setup",
        "tires": SAMPLE_TIRE,
        "brakes": SAMPLE_BRAKES,
        "suspension": SAMPLE_SUSPENSION,
        "notes": "Spa configuration",
    }
    resp = await client.post("/api/equipment/profiles", json=full_profile)
    assert resp.status_code == 201
    data = resp.json()

    assert data["name"] == "Full Race Setup"
    assert data["notes"] == "Spa configuration"

    assert data["brakes"]["compound"] == "Ferodo DS2500"
    assert data["brakes"]["rotor_type"] == "slotted"
    assert data["brakes"]["fluid_type"] == "Motul RBF 660"

    assert data["suspension"]["type"] == "coilover"
    assert data["suspension"]["front_camber_deg"] == -2.5
    assert data["suspension"]["front_rebound"] == 8
    assert data["suspension"]["sway_bar_front"] == "stiff"


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient) -> None:
    """PATCH an existing profile updates its fields."""
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = resp.json()["id"]

    updated: dict[str, object] = {
        "name": "Updated Setup",
        "tires": SAMPLE_TIRE,
        "notes": "Changed name",
    }
    patch_resp = await client.patch(f"/api/equipment/profiles/{profile_id}", json=updated)
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["name"] == "Updated Setup"
    assert data["notes"] == "Changed name"
    assert data["id"] == profile_id


@pytest.mark.asyncio
async def test_update_missing_profile_404(client: AsyncClient) -> None:
    """PATCH a nonexistent profile returns 404."""
    resp = await client.patch("/api/equipment/profiles/eq_nonexistent99", json=SAMPLE_PROFILE)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_missing_profile_404(client: AsyncClient) -> None:
    """DELETE a nonexistent profile returns 404."""
    resp = await client.delete("/api/equipment/profiles/eq_nonexistent99")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_session_list_includes_equipment(client: AsyncClient) -> None:
    """After assigning equipment, session list shows tire info."""
    from backend.tests.conftest import build_synthetic_csv

    csv_bytes = build_synthetic_csv()
    files = {"files": ("test.csv", csv_bytes, "text/csv")}
    resp = await client.post("/api/sessions/upload", files=files)
    assert resp.status_code == 200
    session_id = resp.json()["session_ids"][0]

    # Create profile + assign to session
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = resp.json()["id"]
    await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id},
    )

    # Verify session list includes equipment
    resp = await client.get("/api/sessions")
    items = resp.json()["items"]
    match = [s for s in items if s["session_id"] == session_id]
    assert len(match) == 1
    assert match[0]["tire_model"] == "Bridgestone RE-71RS"
    assert match[0]["compound_category"] == "super_200tw"
    assert match[0]["equipment_profile_name"] == "Track Day Setup"


@pytest.mark.asyncio
async def test_single_session_includes_equipment(client: AsyncClient) -> None:
    """After assigning equipment, single session endpoint shows tire info."""
    from backend.tests.conftest import build_synthetic_csv

    csv_bytes = build_synthetic_csv()
    files = {"files": ("test.csv", csv_bytes, "text/csv")}
    resp = await client.post("/api/sessions/upload", files=files)
    assert resp.status_code == 200
    session_id = resp.json()["session_ids"][0]

    # Create profile + assign to session
    resp = await client.post("/api/equipment/profiles", json=SAMPLE_PROFILE)
    profile_id = resp.json()["id"]
    await client.put(
        f"/api/equipment/{session_id}/equipment",
        json={"profile_id": profile_id},
    )

    # Verify single session endpoint includes equipment
    resp = await client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tire_model"] == "Bridgestone RE-71RS"
    assert data["compound_category"] == "super_200tw"
    assert data["equipment_profile_name"] == "Track Day Setup"


@pytest.mark.asyncio
async def test_session_without_equipment_has_null_fields(client: AsyncClient) -> None:
    """Session without equipment assignment has null tire fields."""
    from backend.tests.conftest import build_synthetic_csv

    csv_bytes = build_synthetic_csv()
    files = {"files": ("test.csv", csv_bytes, "text/csv")}
    resp = await client.post("/api/sessions/upload", files=files)
    assert resp.status_code == 200
    session_id = resp.json()["session_ids"][0]

    resp = await client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tire_model"] is None
    assert data["compound_category"] is None
    assert data["equipment_profile_name"] is None


# ---------------------------------------------------------------------------
# Tire search
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Weather lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weather_lookup(client: AsyncClient) -> None:
    """POST /weather/lookup with mocked weather client returns conditions."""
    with patch("cataclysm.weather_client.lookup_weather") as mock_weather:
        from cataclysm.equipment import SessionConditions, TrackCondition

        mock_weather.return_value = SessionConditions(
            track_condition=TrackCondition.DRY,
            ambient_temp_c=25.0,
            humidity_pct=60.0,
            wind_speed_kmh=15.0,
            wind_direction_deg=180.0,
            precipitation_mm=0.0,
            weather_source="open-meteo",
        )
        resp = await client.post(
            "/api/equipment/weather/lookup",
            json={"lat": 33.53, "lon": -86.62, "session_date": "2025-02-15"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conditions"]["ambient_temp_c"] == 25.0
        assert data["conditions"]["track_condition"] == "dry"
        assert data["conditions"]["humidity_pct"] == 60.0
        assert data["conditions"]["weather_source"] == "open-meteo"


@pytest.mark.asyncio
async def test_weather_lookup_unavailable(client: AsyncClient) -> None:
    """POST /weather/lookup when API fails returns conditions=None."""
    with patch("cataclysm.weather_client.lookup_weather") as mock_weather:
        mock_weather.return_value = None
        resp = await client.post(
            "/api/equipment/weather/lookup",
            json={"lat": 33.53, "lon": -86.62, "session_date": "2025-02-15"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conditions"] is None
        assert data["message"] == "Weather data unavailable"


@pytest.mark.asyncio
async def test_weather_lookup_custom_hour(client: AsyncClient) -> None:
    """POST /weather/lookup with custom hour passes correct datetime."""
    with patch("cataclysm.weather_client.lookup_weather") as mock_weather:
        from cataclysm.equipment import SessionConditions, TrackCondition

        mock_weather.return_value = SessionConditions(
            track_condition=TrackCondition.WET,
            ambient_temp_c=18.0,
            humidity_pct=90.0,
            wind_speed_kmh=25.0,
            precipitation_mm=5.2,
            weather_source="open-meteo",
        )
        resp = await client.post(
            "/api/equipment/weather/lookup",
            json={
                "lat": 33.53,
                "lon": -86.62,
                "session_date": "2025-02-15",
                "hour": 9,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conditions"]["track_condition"] == "wet"
        assert data["conditions"]["precipitation_mm"] == 5.2

        # Verify the datetime passed to lookup_weather had hour=9
        call_args = mock_weather.call_args
        passed_dt = call_args[0][2]  # third positional arg
        assert passed_dt.hour == 9


@pytest.mark.asyncio
async def test_tire_search(client: AsyncClient) -> None:
    """Search for a known tire model returns matching results."""
    resp = await client.get("/api/equipment/tires/search", params={"q": "RE-71RS"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "RE-71RS" in data[0]["model"]
    assert data[0]["mu_source"] == "curated_table"


@pytest.mark.asyncio
async def test_tire_search_short_query(client: AsyncClient) -> None:
    """Query shorter than 2 characters returns empty list."""
    resp = await client.get("/api/equipment/tires/search", params={"q": "R"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_tire_search_empty_query(client: AsyncClient) -> None:
    """Empty query returns empty list."""
    resp = await client.get("/api/equipment/tires/search", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_tire_search_no_match(client: AsyncClient) -> None:
    """Query with no matches returns empty list."""
    resp = await client.get("/api/equipment/tires/search", params={"q": "ZZZnonexistent"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_tire_search_by_brand(client: AsyncClient) -> None:
    """Search by brand name returns matching tires."""
    resp = await client.get("/api/equipment/tires/search", params={"q": "Michelin"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["brand"] == "Michelin"


# ---------------------------------------------------------------------------
# Brake pad search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brake_pad_search(client: AsyncClient) -> None:
    """Search for a known brake pad model returns matching results."""
    resp = await client.get("/api/equipment/brakes/search", params={"q": "Hawk"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["brand"] == "Hawk"
    assert "model" in data[0]
    assert "category" in data[0]
    assert "temp_range" in data[0]
    assert "initial_bite" in data[0]


@pytest.mark.asyncio
async def test_brake_pad_search_short_query(client: AsyncClient) -> None:
    """Query shorter than 2 characters returns empty list."""
    resp = await client.get("/api/equipment/brakes/search", params={"q": "H"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_brake_pad_search_empty(client: AsyncClient) -> None:
    """Empty query returns empty list."""
    resp = await client.get("/api/equipment/brakes/search", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_brake_pad_search_no_match(client: AsyncClient) -> None:
    """Query with no matches returns empty."""
    resp = await client.get("/api/equipment/brakes/search", params={"q": "ZZZnonexistent"})
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reference_tire_sizes(client: AsyncClient) -> None:
    """GET /reference/tire-sizes returns a list with known sizes."""
    resp = await client.get("/api/equipment/reference/tire-sizes")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 10
    assert "255/40R17" in data
    assert "245/40R18" in data


@pytest.mark.asyncio
async def test_reference_brake_fluids(client: AsyncClient) -> None:
    """GET /reference/brake-fluids returns a list with known fluids."""
    resp = await client.get("/api/equipment/reference/brake-fluids")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    assert "DOT 4" in data
    assert "Motul RBF 600" in data
    assert "Castrol SRF" in data

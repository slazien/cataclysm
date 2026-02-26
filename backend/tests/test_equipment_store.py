"""Tests for the equipment store module."""

from __future__ import annotations

import tempfile

import pytest
from cataclysm.equipment import (
    BrakeSpec,
    EquipmentProfile,
    MuSource,
    SessionConditions,
    SessionEquipment,
    SuspensionSpec,
    TireCompoundCategory,
    TireSpec,
    TrackCondition,
)

from backend.api.services import equipment_store

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_store() -> None:
    """Clear all equipment data before each test."""
    equipment_store.clear_all_equipment()


def _make_tire_spec(**overrides: object) -> TireSpec:
    """Create a TireSpec with sensible defaults, applying *overrides*."""
    defaults: dict[str, object] = {
        "model": "Pilot Sport 4S",
        "compound_category": TireCompoundCategory.SUPER_200TW,
        "size": "255/35ZR18",
        "treadwear_rating": 300,
        "estimated_mu": 1.10,
        "mu_source": MuSource.FORMULA_ESTIMATE,
        "mu_confidence": "medium",
        "pressure_psi": 34.0,
        "brand": "Michelin",
        "age_sessions": 5,
    }
    defaults.update(overrides)
    return TireSpec(**defaults)  # type: ignore[arg-type]


def _make_profile(
    profile_id: str = "prof-1",
    name: str = "Street Setup",
    *,
    brakes: BrakeSpec | None = None,
    suspension: SuspensionSpec | None = None,
    notes: str | None = None,
) -> EquipmentProfile:
    return EquipmentProfile(
        id=profile_id,
        name=name,
        tires=_make_tire_spec(),
        brakes=brakes,
        suspension=suspension,
        notes=notes,
    )


def _make_session_equipment(
    session_id: str = "sess-1",
    profile_id: str = "prof-1",
    *,
    overrides: dict[str, object] | None = None,
    conditions: SessionConditions | None = None,
) -> SessionEquipment:
    return SessionEquipment(
        session_id=session_id,
        profile_id=profile_id,
        overrides=overrides or {},
        conditions=conditions,
    )


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------


class TestProfileCRUD:
    """Profile store / get / list / delete operations."""

    def test_store_and_get_profile(self) -> None:
        profile = _make_profile()
        equipment_store.store_profile(profile)
        result = equipment_store.get_profile("prof-1")

        assert result is not None
        assert result.id == "prof-1"
        assert result.name == "Street Setup"
        assert result.tires.model == "Pilot Sport 4S"
        assert result.tires.compound_category == TireCompoundCategory.SUPER_200TW
        assert result.tires.estimated_mu == pytest.approx(1.10)

    def test_get_missing_profile_returns_none(self) -> None:
        assert equipment_store.get_profile("does-not-exist") is None

    def test_list_profiles_sorted_by_name(self) -> None:
        equipment_store.store_profile(_make_profile("p1", "Zeta Config"))
        equipment_store.store_profile(_make_profile("p2", "Alpha Config"))
        equipment_store.store_profile(_make_profile("p3", "Mid Config"))

        result = equipment_store.list_profiles()
        names = [p.name for p in result]
        assert names == ["Alpha Config", "Mid Config", "Zeta Config"]

    def test_list_profiles_empty(self) -> None:
        assert equipment_store.list_profiles() == []

    def test_delete_profile(self) -> None:
        equipment_store.store_profile(_make_profile())
        assert equipment_store.delete_profile("prof-1") is True
        assert equipment_store.get_profile("prof-1") is None

    def test_delete_missing_profile_returns_false(self) -> None:
        assert equipment_store.delete_profile("nope") is False

    def test_update_profile_same_id(self) -> None:
        equipment_store.store_profile(_make_profile("p1", "Original"))
        equipment_store.store_profile(_make_profile("p1", "Updated"))

        result = equipment_store.get_profile("p1")
        assert result is not None
        assert result.name == "Updated"
        assert len(equipment_store.list_profiles()) == 1

    def test_profile_with_brakes_and_suspension(self) -> None:
        brakes = BrakeSpec(
            compound="Ferodo DS2500",
            rotor_type="slotted",
            pad_temp_range="200-600C",
            fluid_type="DOT 5.1",
        )
        suspension = SuspensionSpec(
            type="coilover",
            front_spring_rate="10k",
            rear_spring_rate="8k",
            front_camber_deg=-2.5,
            rear_camber_deg=-1.8,
            front_toe="0mm",
            rear_toe="2mm",
            front_rebound=8,
            front_compression=6,
            rear_rebound=7,
            rear_compression=5,
            sway_bar_front="medium",
            sway_bar_rear="soft",
        )
        profile = _make_profile(brakes=brakes, suspension=suspension, notes="Race day setup")
        equipment_store.store_profile(profile)

        result = equipment_store.get_profile("prof-1")
        assert result is not None
        assert result.brakes is not None
        assert result.brakes.compound == "Ferodo DS2500"
        assert result.suspension is not None
        assert result.suspension.front_camber_deg == pytest.approx(-2.5)
        assert result.notes == "Race day setup"

    def test_profile_with_none_optional_fields(self) -> None:
        """Profiles with None brakes/suspension/notes roundtrip correctly."""
        profile = _make_profile(brakes=None, suspension=None, notes=None)
        equipment_store.store_profile(profile)

        result = equipment_store.get_profile("prof-1")
        assert result is not None
        assert result.brakes is None
        assert result.suspension is None
        assert result.notes is None


# ---------------------------------------------------------------------------
# Session Equipment CRUD
# ---------------------------------------------------------------------------


class TestSessionEquipmentCRUD:
    """Session equipment store / get / delete operations."""

    def test_store_and_get_session_equipment(self) -> None:
        se = _make_session_equipment()
        equipment_store.store_session_equipment(se)
        result = equipment_store.get_session_equipment("sess-1")

        assert result is not None
        assert result.session_id == "sess-1"
        assert result.profile_id == "prof-1"

    def test_get_missing_session_equipment_returns_none(self) -> None:
        assert equipment_store.get_session_equipment("missing") is None

    def test_delete_session_equipment(self) -> None:
        equipment_store.store_session_equipment(_make_session_equipment())
        assert equipment_store.delete_session_equipment("sess-1") is True
        assert equipment_store.get_session_equipment("sess-1") is None

    def test_delete_missing_session_equipment_returns_false(self) -> None:
        assert equipment_store.delete_session_equipment("nope") is False

    def test_override_fields(self) -> None:
        se = _make_session_equipment(overrides={"pressure_psi": 32.0, "compound": "RE-71RS"})
        equipment_store.store_session_equipment(se)
        result = equipment_store.get_session_equipment("sess-1")

        assert result is not None
        assert result.overrides["pressure_psi"] == 32.0
        assert result.overrides["compound"] == "RE-71RS"

    def test_session_conditions_roundtrip(self) -> None:
        conditions = SessionConditions(
            track_condition=TrackCondition.DAMP,
            ambient_temp_c=22.5,
            track_temp_c=35.0,
            humidity_pct=65.0,
            wind_speed_kmh=12.0,
            wind_direction_deg=180.0,
            precipitation_mm=0.5,
            weather_source="local_station",
        )
        se = _make_session_equipment(conditions=conditions)
        equipment_store.store_session_equipment(se)

        result = equipment_store.get_session_equipment("sess-1")
        assert result is not None
        assert result.conditions is not None
        assert result.conditions.track_condition == TrackCondition.DAMP
        assert result.conditions.ambient_temp_c == pytest.approx(22.5)
        assert result.conditions.precipitation_mm == pytest.approx(0.5)
        assert result.conditions.weather_source == "local_station"

    def test_update_session_equipment(self) -> None:
        """Storing session equipment for the same session_id overwrites."""
        equipment_store.store_session_equipment(_make_session_equipment(profile_id="old-profile"))
        equipment_store.store_session_equipment(_make_session_equipment(profile_id="new-profile"))
        result = equipment_store.get_session_equipment("sess-1")
        assert result is not None
        assert result.profile_id == "new-profile"


# ---------------------------------------------------------------------------
# Disk Persistence
# ---------------------------------------------------------------------------


class TestDiskPersistence:
    """Persist to disk, clear memory, reload, and verify."""

    def test_profile_persist_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            equipment_store.init_equipment_dir(tmpdir)

            brakes = BrakeSpec(compound="Hawk DTC-60")
            profile = _make_profile(brakes=brakes, notes="persisted")
            equipment_store.store_profile(profile)

            # Clear memory
            equipment_store.clear_all_equipment()
            assert equipment_store.get_profile("prof-1") is None

            # Reload from disk
            count = equipment_store.load_persisted_profiles()
            assert count == 1

            result = equipment_store.get_profile("prof-1")
            assert result is not None
            assert result.name == "Street Setup"
            assert result.brakes is not None
            assert result.brakes.compound == "Hawk DTC-60"
            assert result.notes == "persisted"
            assert result.tires.compound_category == TireCompoundCategory.SUPER_200TW
            assert result.tires.mu_source == MuSource.FORMULA_ESTIMATE

    def test_session_equipment_persist_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            equipment_store.init_equipment_dir(tmpdir)

            conditions = SessionConditions(
                track_condition=TrackCondition.WET,
                ambient_temp_c=18.0,
            )
            se = _make_session_equipment(
                overrides={"pressure_psi": 30.0},
                conditions=conditions,
            )
            equipment_store.store_session_equipment(se)

            equipment_store.clear_all_equipment()
            assert equipment_store.get_session_equipment("sess-1") is None

            count = equipment_store.load_persisted_session_equipment()
            assert count == 1

            result = equipment_store.get_session_equipment("sess-1")
            assert result is not None
            assert result.overrides["pressure_psi"] == 30.0
            assert result.conditions is not None
            assert result.conditions.track_condition == TrackCondition.WET
            assert result.conditions.ambient_temp_c == pytest.approx(18.0)

    def test_delete_removes_disk_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            equipment_store.init_equipment_dir(tmpdir)
            equipment_store.store_profile(_make_profile())
            equipment_store.delete_profile("prof-1")

            # Clear and try to reload — nothing should come back
            equipment_store.clear_all_equipment()
            count = equipment_store.load_persisted_profiles()
            assert count == 0

    def test_load_with_no_dir_returns_zero(self) -> None:
        """Loading without init_equipment_dir returns 0."""
        # _equipment_dir is None by default after clear
        # We need to reset it manually for this test
        equipment_store._equipment_dir = None  # noqa: SLF001
        assert equipment_store.load_persisted_profiles() == 0
        assert equipment_store.load_persisted_session_equipment() == 0

    def test_multiple_profiles_persist_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            equipment_store.init_equipment_dir(tmpdir)

            equipment_store.store_profile(_make_profile("p1", "Setup A"))
            equipment_store.store_profile(_make_profile("p2", "Setup B"))
            equipment_store.store_profile(_make_profile("p3", "Setup C"))

            equipment_store.clear_all_equipment()
            count = equipment_store.load_persisted_profiles()
            assert count == 3
            assert len(equipment_store.list_profiles()) == 3

    def test_full_profile_roundtrip_with_suspension(self) -> None:
        """A fully populated profile survives serialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            equipment_store.init_equipment_dir(tmpdir)

            suspension = SuspensionSpec(
                type="coilover",
                front_spring_rate="12k",
                rear_spring_rate="10k",
                front_camber_deg=-3.0,
                rear_camber_deg=-2.0,
                front_toe="-1mm",
                rear_toe="1mm",
                front_rebound=10,
                front_compression=7,
                rear_rebound=9,
                rear_compression=6,
                sway_bar_front="stiff",
                sway_bar_rear="medium",
            )
            profile = _make_profile(
                brakes=BrakeSpec(
                    compound="Pagid RSC1",
                    rotor_type="drilled",
                    pad_temp_range="300-700C",
                    fluid_type="Motul RBF 660",
                ),
                suspension=suspension,
                notes="Full race spec",
            )
            equipment_store.store_profile(profile)

            equipment_store.clear_all_equipment()
            equipment_store.load_persisted_profiles()

            result = equipment_store.get_profile("prof-1")
            assert result is not None
            assert result.suspension is not None
            assert result.suspension.front_camber_deg == pytest.approx(-3.0)
            assert result.suspension.rear_compression == 6
            assert result.suspension.sway_bar_front == "stiff"
            assert result.brakes is not None
            assert result.brakes.fluid_type == "Motul RBF 660"
            assert result.notes == "Full race spec"


# ---------------------------------------------------------------------------
# clear_all_equipment
# ---------------------------------------------------------------------------


class TestClearAll:
    """Verify clear_all_equipment empties both stores."""

    def test_clear_all(self) -> None:
        equipment_store.store_profile(_make_profile())
        equipment_store.store_session_equipment(_make_session_equipment())

        equipment_store.clear_all_equipment()

        assert equipment_store.get_profile("prof-1") is None
        assert equipment_store.get_session_equipment("sess-1") is None
        assert equipment_store.list_profiles() == []

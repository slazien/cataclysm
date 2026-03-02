"""Tests for the equipment store module."""

from __future__ import annotations

import tempfile
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# Disk persistence: delete persisted session equipment — line 100-101
# ---------------------------------------------------------------------------


class TestDeletePersistedSessionEquipment:
    """Verify _delete_persisted_session_equipment removes session files from disk."""

    def test_delete_removes_session_equipment_disk_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            equipment_store.init_equipment_dir(tmpdir)

            se = _make_session_equipment()
            equipment_store.store_session_equipment(se)

            # Confirm the file exists on disk
            from pathlib import Path

            disk_file = Path(tmpdir) / "sessions" / "sess-1.json"
            assert disk_file.exists()

            # Delete and verify the file is gone
            equipment_store.delete_session_equipment("sess-1")
            assert not disk_file.exists()

    def test_delete_persisted_session_noop_when_no_dir(self) -> None:
        """_delete_persisted_session_equipment is a no-op when _equipment_dir is None."""
        equipment_store._equipment_dir = None  # noqa: SLF001
        # Should not raise
        equipment_store._delete_persisted_session_equipment("sess-x")  # noqa: SLF001


# ---------------------------------------------------------------------------
# _opt_int with non-int value — line 126
# ---------------------------------------------------------------------------


class TestOptInt:
    """Edge cases for the _opt_int deserialization helper."""

    def test_opt_int_returns_none_for_none(self) -> None:
        result = equipment_store._opt_int({"key": None}, "key")  # noqa: SLF001
        assert result is None

    def test_opt_int_returns_int_when_int_value(self) -> None:
        result = equipment_store._opt_int({"key": 5}, "key")  # noqa: SLF001
        assert result == 5

    def test_opt_int_converts_string_to_int(self) -> None:
        """Line 126: when value is not int, it converts via int(str(v))."""
        result = equipment_store._opt_int({"key": "42"}, "key")  # noqa: SLF001
        assert result == 42

    def test_opt_int_float_raises_value_error(self) -> None:
        """float values hit the int(str(v)) path which raises ValueError for non-integer floats."""
        with pytest.raises(ValueError):
            equipment_store._opt_int({"key": 3.7}, "key")  # noqa: SLF001

    def test_opt_int_missing_key_returns_none(self) -> None:
        result = equipment_store._opt_int({}, "missing")  # noqa: SLF001
        assert result is None


# ---------------------------------------------------------------------------
# load_persisted_profiles — corrupt file (lines 308-309)
# ---------------------------------------------------------------------------


class TestLoadPersistedProfilesCorrupt:
    """Corrupt JSON files are skipped gracefully."""

    def test_corrupt_profile_file_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path

            equipment_store.init_equipment_dir(tmpdir)

            # Write a valid profile
            equipment_store.store_profile(_make_profile("p-good", "Good Profile"))

            # Write a corrupt JSON file directly
            corrupt_path = Path(tmpdir) / "profiles" / "corrupt.json"
            corrupt_path.write_text("{not valid json", encoding="utf-8")

            # Write another valid profile
            equipment_store.store_profile(_make_profile("p-good2", "Another Good Profile"))

            equipment_store.clear_all_equipment()
            count = equipment_store.load_persisted_profiles()

            # Only the 2 valid profiles should load; corrupt one is skipped
            assert count == 2
            assert equipment_store.get_profile("p-good") is not None
            assert equipment_store.get_profile("p-good2") is not None

    def test_profile_file_with_missing_required_key_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            import json as _json
            from pathlib import Path

            equipment_store.init_equipment_dir(tmpdir)

            # Write a JSON that is valid JSON but missing required 'tires' key
            bad_path = Path(tmpdir) / "profiles" / "bad-schema.json"
            bad_path.write_text(_json.dumps({"id": "x", "name": "bad"}), encoding="utf-8")

            equipment_store.clear_all_equipment()
            count = equipment_store.load_persisted_profiles()
            assert count == 0


# ---------------------------------------------------------------------------
# load_persisted_session_equipment — corrupt file (lines 328-329)
# ---------------------------------------------------------------------------


class TestLoadPersistedSessionEquipmentCorrupt:
    """Corrupt session equipment JSON files are skipped gracefully."""

    def test_corrupt_session_file_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path

            equipment_store.init_equipment_dir(tmpdir)

            # Write a valid session equipment entry
            se = _make_session_equipment("sess-valid")
            equipment_store.store_session_equipment(se)

            # Write a corrupt file
            corrupt_path = Path(tmpdir) / "sessions" / "corrupt.json"
            corrupt_path.write_text("{not json", encoding="utf-8")

            equipment_store.clear_all_equipment()
            count = equipment_store.load_persisted_session_equipment()

            assert count == 1
            assert equipment_store.get_session_equipment("sess-valid") is not None

    def test_session_file_with_missing_required_key_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            import json as _json
            from pathlib import Path

            equipment_store.init_equipment_dir(tmpdir)

            bad_path = Path(tmpdir) / "sessions" / "bad.json"
            bad_path.write_text(_json.dumps({"session_id": "x"}), encoding="utf-8")

            equipment_store.clear_all_equipment()
            count = equipment_store.load_persisted_session_equipment()
            assert count == 0


# ---------------------------------------------------------------------------
# db_persist_profile — lines 354-369
# ---------------------------------------------------------------------------


class TestDbPersistProfile:
    """db_persist_profile writes to DB; SQLAlchemy errors are swallowed."""

    @pytest.mark.asyncio
    async def test_db_persist_profile_success(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from backend.api.db.models import EquipmentProfileDB

        profile = _make_profile("db-prof-1", "DB Profile")

        mock_db = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            await equipment_store.db_persist_profile(profile, user_id="user-1")

        mock_db.merge.assert_called_once()
        call_arg = mock_db.merge.call_args[0][0]
        assert isinstance(call_arg, EquipmentProfileDB)
        assert call_arg.id == "db-prof-1"
        assert call_arg.name == "DB Profile"
        assert call_arg.user_id == "user-1"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_persist_profile_swallows_sqlalchemy_error(self) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        profile = _make_profile()

        with patch(
            "backend.api.db.database.async_session_factory",
            side_effect=SQLAlchemyError("DB connection refused"),
        ):
            # Should not raise
            await equipment_store.db_persist_profile(profile)

    @pytest.mark.asyncio
    async def test_db_persist_profile_no_user_id(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        profile = _make_profile("no-user-prof")

        mock_db = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            await equipment_store.db_persist_profile(profile, user_id=None)

        call_arg = mock_db.merge.call_args[0][0]
        assert call_arg.user_id is None


# ---------------------------------------------------------------------------
# db_delete_profile — lines 374-384
# ---------------------------------------------------------------------------


class TestDbDeleteProfile:
    """db_delete_profile executes DELETE in DB; errors are swallowed."""

    @pytest.mark.asyncio
    async def test_db_delete_profile_success(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_db = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            await equipment_store.db_delete_profile("prof-to-delete")

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_delete_profile_swallows_sqlalchemy_error(self) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        with patch(
            "backend.api.db.database.async_session_factory",
            side_effect=SQLAlchemyError("connection lost"),
        ):
            # Should not raise
            await equipment_store.db_delete_profile("prof-xyz")


# ---------------------------------------------------------------------------
# db_persist_session_equipment — lines 389-407
# ---------------------------------------------------------------------------


class TestDbPersistSessionEquipment:
    """db_persist_session_equipment writes to DB; errors are swallowed."""

    @pytest.mark.asyncio
    async def test_db_persist_session_equipment_success(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from backend.api.db.models import SessionEquipmentDB

        se = _make_session_equipment("sess-db-1", "prof-db-1")

        mock_db = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            await equipment_store.db_persist_session_equipment(se)

        mock_db.merge.assert_called_once()
        call_arg = mock_db.merge.call_args[0][0]
        assert isinstance(call_arg, SessionEquipmentDB)
        assert call_arg.session_id == "sess-db-1"
        assert call_arg.profile_id == "prof-db-1"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_persist_session_equipment_swallows_sqlalchemy_error(self) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        se = _make_session_equipment()

        with patch(
            "backend.api.db.database.async_session_factory",
            side_effect=SQLAlchemyError("timeout"),
        ):
            await equipment_store.db_persist_session_equipment(se)


# ---------------------------------------------------------------------------
# db_delete_session_equipment — lines 412-428
# ---------------------------------------------------------------------------


class TestDbDeleteSessionEquipment:
    """db_delete_session_equipment executes DELETE in DB; errors are swallowed."""

    @pytest.mark.asyncio
    async def test_db_delete_session_equipment_success(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_db = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            await equipment_store.db_delete_session_equipment("sess-del")

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_delete_session_equipment_swallows_sqlalchemy_error(self) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        with patch(
            "backend.api.db.database.async_session_factory",
            side_effect=SQLAlchemyError("DB unavailable"),
        ):
            await equipment_store.db_delete_session_equipment("sess-err")


# ---------------------------------------------------------------------------
# load_equipment_from_db — lines 436-480
# ---------------------------------------------------------------------------


class TestLoadEquipmentFromDb:
    """load_equipment_from_db loads profiles and session equipment from DB."""

    @pytest.mark.asyncio
    async def test_load_equipment_from_db_empty(self) -> None:
        """Empty DB returns (0, 0)."""
        from unittest.mock import AsyncMock, MagicMock

        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [empty_result, empty_result]
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            n_profiles, n_assignments = await equipment_store.load_equipment_from_db()

        assert n_profiles == 0
        assert n_assignments == 0

    @pytest.mark.asyncio
    async def test_load_equipment_from_db_loads_profiles(self) -> None:
        """load_equipment_from_db populates _profiles from DB rows."""
        from dataclasses import asdict
        from unittest.mock import AsyncMock, MagicMock

        profile = _make_profile("db-loaded-1", "Loaded Profile")
        profile_row = MagicMock()
        profile_row.id = profile.id
        profile_row.profile_json = asdict(profile)

        mock_db = AsyncMock()
        # First execute call returns profile rows, second returns empty SE rows
        mock_db.execute.side_effect = [
            MagicMock(**{"scalars.return_value.all.return_value": [profile_row]}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        equipment_store.clear_all_equipment()

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            n_profiles, n_assignments = await equipment_store.load_equipment_from_db()

        assert n_profiles == 1
        assert n_assignments == 0
        assert equipment_store.get_profile("db-loaded-1") is not None
        assert equipment_store.get_profile("db-loaded-1").name == "Loaded Profile"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_load_equipment_from_db_loads_session_equipment(self) -> None:
        """load_equipment_from_db populates _session_equipment from DB rows."""
        from dataclasses import asdict
        from unittest.mock import AsyncMock, MagicMock

        se = _make_session_equipment("sess-db-load", "prof-db")
        se_row = MagicMock()
        se_row.session_id = se.session_id
        se_row.assignment_json = asdict(se)

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            MagicMock(**{"scalars.return_value.all.return_value": []}),
            MagicMock(**{"scalars.return_value.all.return_value": [se_row]}),
        ]
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        equipment_store.clear_all_equipment()

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            n_profiles, n_assignments = await equipment_store.load_equipment_from_db()

        assert n_profiles == 0
        assert n_assignments == 1
        assert equipment_store.get_session_equipment("sess-db-load") is not None

    @pytest.mark.asyncio
    async def test_load_equipment_from_db_skips_null_profile_json(self) -> None:
        """Rows with null profile_json are silently skipped."""
        from unittest.mock import AsyncMock, MagicMock

        null_row = MagicMock()
        null_row.id = "null-prof"
        null_row.profile_json = None

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            MagicMock(**{"scalars.return_value.all.return_value": [null_row]}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        equipment_store.clear_all_equipment()

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            n_profiles, _ = await equipment_store.load_equipment_from_db()

        assert n_profiles == 0

    @pytest.mark.asyncio
    async def test_load_equipment_from_db_skips_null_assignment_json(self) -> None:
        """Rows with null assignment_json are silently skipped."""
        from unittest.mock import AsyncMock, MagicMock

        null_row = MagicMock()
        null_row.session_id = "null-sess"
        null_row.assignment_json = None

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            MagicMock(**{"scalars.return_value.all.return_value": []}),
            MagicMock(**{"scalars.return_value.all.return_value": [null_row]}),
        ]
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        equipment_store.clear_all_equipment()

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            _, n_assignments = await equipment_store.load_equipment_from_db()

        assert n_assignments == 0

    @pytest.mark.asyncio
    async def test_load_equipment_from_db_swallows_sqlalchemy_error(self) -> None:
        """SQLAlchemy errors during DB load are swallowed and return (0, 0)."""
        from sqlalchemy.exc import SQLAlchemyError

        with patch(
            "backend.api.db.database.async_session_factory",
            side_effect=SQLAlchemyError("Connection pool exhausted"),
        ):
            n_profiles, n_assignments = await equipment_store.load_equipment_from_db()

        assert n_profiles == 0
        assert n_assignments == 0

    @pytest.mark.asyncio
    async def test_load_equipment_from_db_skips_bad_profile_deserialization(
        self,
    ) -> None:
        """Rows with malformed profile_json are skipped individually."""
        from unittest.mock import AsyncMock, MagicMock

        bad_row = MagicMock()
        bad_row.id = "bad-profile"
        bad_row.profile_json = {"id": "bad", "name": "bad"}  # missing 'tires'

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            MagicMock(**{"scalars.return_value.all.return_value": [bad_row]}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
        ]
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        equipment_store.clear_all_equipment()

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            n_profiles, _ = await equipment_store.load_equipment_from_db()

        assert n_profiles == 0

    @pytest.mark.asyncio
    async def test_load_equipment_from_db_skips_bad_session_equipment_deserialization(
        self,
    ) -> None:
        """Rows with malformed assignment_json are skipped individually."""
        from unittest.mock import AsyncMock, MagicMock

        bad_row = MagicMock()
        bad_row.session_id = "bad-sess"
        bad_row.assignment_json = {"session_id": "x"}  # missing 'profile_id'

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            MagicMock(**{"scalars.return_value.all.return_value": []}),
            MagicMock(**{"scalars.return_value.all.return_value": [bad_row]}),
        ]
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        equipment_store.clear_all_equipment()

        with patch(
            "backend.api.db.database.async_session_factory",
            return_value=mock_cm,
        ):
            _, n_assignments = await equipment_store.load_equipment_from_db()

        assert n_assignments == 0

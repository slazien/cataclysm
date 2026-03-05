"""Tests for the curated vehicle database module."""

from __future__ import annotations

import pytest

from cataclysm.vehicle_db import (
    VEHICLE_DATABASE,
    VehicleSpec,
    find_vehicle,
    get_vehicle_by_slug,
    list_all_vehicles,
    list_makes,
    list_models,
    search_vehicles,
)

# ---------------------------------------------------------------------------
# TestVehicleSpec
# ---------------------------------------------------------------------------


class TestVehicleSpec:
    """Tests for the VehicleSpec dataclass."""

    def test_frozen(self) -> None:
        """VehicleSpec should be immutable."""
        spec = get_vehicle_by_slug("mazda_miata_nd")
        assert spec is not None
        with pytest.raises(AttributeError):
            spec.weight_kg = 999.0  # type: ignore[misc]

    def test_year_range_is_tuple(self) -> None:
        spec = get_vehicle_by_slug("mazda_miata_nd")
        assert spec is not None
        assert isinstance(spec.year_range, tuple)
        assert len(spec.year_range) == 2
        assert spec.year_range[0] <= spec.year_range[1]

    def test_all_vehicles_have_valid_drivetrain(self) -> None:
        valid_drivetrains = {"RWD", "FWD", "AWD"}
        for slug, spec in VEHICLE_DATABASE.items():
            assert spec.drivetrain in valid_drivetrains, (
                f"{slug}: invalid drivetrain '{spec.drivetrain}'"
            )

    def test_all_vehicles_have_positive_weight(self) -> None:
        for slug, spec in VEHICLE_DATABASE.items():
            assert spec.weight_kg > 0, f"{slug}: weight must be positive"

    def test_all_vehicles_have_positive_hp(self) -> None:
        for slug, spec in VEHICLE_DATABASE.items():
            assert spec.hp > 0, f"{slug}: hp must be positive"

    def test_all_vehicles_have_positive_torque(self) -> None:
        for slug, spec in VEHICLE_DATABASE.items():
            assert spec.torque_nm > 0, f"{slug}: torque must be positive"

    def test_all_vehicles_have_valid_cg_height(self) -> None:
        """CG height should be between 0.3 and 0.7 m for street cars."""
        for slug, spec in VEHICLE_DATABASE.items():
            assert 0.3 <= spec.cg_height_m <= 0.7, (
                f"{slug}: CG height {spec.cg_height_m} out of range"
            )

    def test_all_vehicles_have_valid_weight_distribution(self) -> None:
        """Weight distribution should be between 30% and 70% front."""
        for slug, spec in VEHICLE_DATABASE.items():
            assert 30.0 <= spec.weight_dist_front_pct <= 70.0, (
                f"{slug}: weight dist {spec.weight_dist_front_pct}% out of range"
            )

    def test_all_vehicles_have_valid_wheelbase(self) -> None:
        """Wheelbase should be between 2.0 and 3.5 m for road cars."""
        for slug, spec in VEHICLE_DATABASE.items():
            assert 2.0 <= spec.wheelbase_m <= 3.5, (
                f"{slug}: wheelbase {spec.wheelbase_m} out of range"
            )

    def test_all_vehicles_have_valid_track_width(self) -> None:
        """Track width should be between 1.3 and 1.8 m."""
        for slug, spec in VEHICLE_DATABASE.items():
            assert 1.3 <= spec.track_width_front_m <= 1.8, (
                f"{slug}: front track {spec.track_width_front_m} out of range"
            )
            assert 1.3 <= spec.track_width_rear_m <= 1.8, (
                f"{slug}: rear track {spec.track_width_rear_m} out of range"
            )

    def test_all_vehicles_have_reasonable_cd_a(self) -> None:
        """CdA values should be 0 (unknown) or between 0.4 and 1.0 m^2."""
        for slug, spec in VEHICLE_DATABASE.items():
            if spec.cd_a > 0:
                assert 0.4 <= spec.cd_a <= 1.0, f"{slug}: cd_a={spec.cd_a} out of range"

    def test_all_vehicles_have_cd_a_populated(self) -> None:
        """All vehicles in the database should have cd_a > 0 (fully populated)."""
        for slug, spec in VEHICLE_DATABASE.items():
            assert spec.cd_a > 0, f"{slug}: cd_a not populated"

    def test_database_has_at_least_40_entries(self) -> None:
        assert len(VEHICLE_DATABASE) >= 40


# ---------------------------------------------------------------------------
# TestFindVehicle
# ---------------------------------------------------------------------------


class TestFindVehicle:
    """Tests for find_vehicle()."""

    def test_find_exact_match(self) -> None:
        result = find_vehicle("Mazda", "Miata", "ND")
        assert result is not None
        assert result.make == "Mazda"
        assert result.model == "Miata"
        assert result.generation == "ND"

    def test_find_case_insensitive(self) -> None:
        result = find_vehicle("mazda", "miata", "nd")
        assert result is not None
        assert result.make == "Mazda"
        assert result.model == "Miata"

    def test_find_without_generation(self) -> None:
        result = find_vehicle("Mazda", "Miata")
        assert result is not None
        assert result.make == "Mazda"

    def test_find_nonexistent_returns_none(self) -> None:
        assert find_vehicle("Ferrari", "F40") is None

    def test_find_wrong_generation_returns_none(self) -> None:
        assert find_vehicle("Mazda", "Miata", "ZZ") is None

    def test_find_corvette_c8(self) -> None:
        result = find_vehicle("Chevrolet", "Corvette", "C8")
        assert result is not None
        assert result.hp == 490
        assert result.drivetrain == "RWD"
        assert result.weight_dist_front_pct == 40.0

    def test_find_civic_type_r(self) -> None:
        result = find_vehicle("Honda", "Civic Type R", "FK8")
        assert result is not None
        assert result.drivetrain == "FWD"
        assert result.has_aero is True

    def test_find_wrx_sti(self) -> None:
        result = find_vehicle("Subaru", "WRX STI", "VA")
        assert result is not None
        assert result.drivetrain == "AWD"


# ---------------------------------------------------------------------------
# TestSearchVehicles
# ---------------------------------------------------------------------------


class TestSearchVehicles:
    """Tests for search_vehicles()."""

    def test_search_by_make(self) -> None:
        results = search_vehicles("BMW")
        assert len(results) >= 3
        # All BMW-make cars should appear; notes matches (e.g. Supra) are OK too
        bmw_count = sum(1 for r in results if r.make == "BMW")
        assert bmw_count >= 3

    def test_search_by_model(self) -> None:
        results = search_vehicles("Miata")
        assert len(results) >= 4
        assert all(r.model == "Miata" for r in results)

    def test_search_by_generation(self) -> None:
        results = search_vehicles("ND")
        assert len(results) >= 1
        assert any(r.generation == "ND" for r in results)

    def test_search_case_insensitive(self) -> None:
        results = search_vehicles("corvette")
        assert len(results) >= 4

    def test_search_empty_query_returns_empty(self) -> None:
        assert search_vehicles("") == []

    def test_search_no_match(self) -> None:
        assert search_vehicles("nonexistent_vehicle_xyz") == []

    def test_search_respects_limit(self) -> None:
        results = search_vehicles("a", limit=3)
        assert len(results) <= 3

    def test_search_in_notes(self) -> None:
        """Should match against the notes field too."""
        results = search_vehicles("turbo")
        assert len(results) >= 5  # Many cars have turbo in notes


# ---------------------------------------------------------------------------
# TestListMakes
# ---------------------------------------------------------------------------


class TestListMakes:
    """Tests for list_makes()."""

    def test_returns_sorted_list(self) -> None:
        makes = list_makes()
        assert makes == sorted(makes)

    def test_contains_expected_makes(self) -> None:
        makes = list_makes()
        for expected in ["BMW", "Honda", "Mazda", "Porsche", "Toyota"]:
            assert expected in makes, f"Expected {expected} in makes"

    def test_no_duplicates(self) -> None:
        makes = list_makes()
        assert len(makes) == len(set(makes))


# ---------------------------------------------------------------------------
# TestListModels
# ---------------------------------------------------------------------------


class TestListModels:
    """Tests for list_models()."""

    def test_list_mazda_models(self) -> None:
        models = list_models("Mazda")
        assert "Miata" in models
        assert "MazdaSpeed3" in models

    def test_list_bmw_models(self) -> None:
        models = list_models("BMW")
        assert "M3" in models
        assert "M2" in models

    def test_case_insensitive(self) -> None:
        models = list_models("mazda")
        assert "Miata" in models

    def test_unknown_make_returns_empty(self) -> None:
        assert list_models("Unknown") == []

    def test_returns_sorted(self) -> None:
        models = list_models("BMW")
        assert models == sorted(models)

    def test_no_duplicates(self) -> None:
        models = list_models("Honda")
        assert len(models) == len(set(models))


# ---------------------------------------------------------------------------
# TestGetVehicleBySlug
# ---------------------------------------------------------------------------


class TestGetVehicleBySlug:
    """Tests for get_vehicle_by_slug()."""

    def test_known_slug(self) -> None:
        spec = get_vehicle_by_slug("mazda_miata_nd")
        assert spec is not None
        assert spec.model == "Miata"
        assert spec.generation == "ND"

    def test_unknown_slug_returns_none(self) -> None:
        assert get_vehicle_by_slug("unknown_vehicle_xyz") is None

    def test_empty_slug_returns_none(self) -> None:
        assert get_vehicle_by_slug("") is None


# ---------------------------------------------------------------------------
# TestListAllVehicles
# ---------------------------------------------------------------------------


class TestListAllVehicles:
    """Tests for list_all_vehicles()."""

    def test_returns_all_vehicles(self) -> None:
        all_vehicles = list_all_vehicles()
        assert len(all_vehicles) == len(VEHICLE_DATABASE)

    def test_sorted_by_make_model_generation(self) -> None:
        all_vehicles = list_all_vehicles()
        keys = [(v.make, v.model, v.generation) for v in all_vehicles]
        assert keys == sorted(keys)

    def test_all_are_vehicle_spec(self) -> None:
        all_vehicles = list_all_vehicles()
        assert all(isinstance(v, VehicleSpec) for v in all_vehicles)


# ---------------------------------------------------------------------------
# TestSpecificVehicleData
# ---------------------------------------------------------------------------


class TestSpecificVehicleData:
    """Spot-check specific vehicle data for accuracy."""

    def test_miata_nd_specs(self) -> None:
        spec = get_vehicle_by_slug("mazda_miata_nd")
        assert spec is not None
        assert spec.weight_kg == 1058
        assert spec.hp == 181
        assert spec.wheelbase_m == 2.310
        assert spec.drivetrain == "RWD"

    def test_corvette_c8_mid_engine(self) -> None:
        spec = get_vehicle_by_slug("chevrolet_corvette_c8")
        assert spec is not None
        assert spec.weight_dist_front_pct == 40.0  # mid-engine = rear-biased

    def test_lotus_elise_lightweight(self) -> None:
        spec = get_vehicle_by_slug("lotus_elise_s2")
        assert spec is not None
        assert spec.weight_kg < 900  # Ultra-lightweight

    def test_gt3_has_aero(self) -> None:
        spec = get_vehicle_by_slug("porsche_911_gt3_992")
        assert spec is not None
        assert spec.has_aero is True

    def test_miata_no_aero(self) -> None:
        spec = get_vehicle_by_slug("mazda_miata_na")
        assert spec is not None
        assert spec.has_aero is False

    def test_wrx_sti_awd(self) -> None:
        spec = get_vehicle_by_slug("subaru_wrx_sti_va")
        assert spec is not None
        assert spec.drivetrain == "AWD"

    def test_gti_fwd(self) -> None:
        spec = get_vehicle_by_slug("volkswagen_gti_mk7")
        assert spec is not None
        assert spec.drivetrain == "FWD"

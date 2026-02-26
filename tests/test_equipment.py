"""Tests for cataclysm.equipment module."""

from __future__ import annotations

import pytest

from cataclysm.equipment import (
    _BRAKE_EFFICIENCY,
    _CATEGORY_ACCEL_G,
    CATEGORY_MU_DEFAULTS,
    BrakeSpec,
    EquipmentProfile,
    MuSource,
    SessionConditions,
    SessionEquipment,
    SuspensionSpec,
    TireCompoundCategory,
    TireSpec,
    TrackCondition,
    equipment_to_vehicle_params,
    estimate_mu_from_treadwear,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_tire() -> TireSpec:
    """A representative street-performance tire."""
    return TireSpec(
        model="Pilot Sport 4S",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="255/35ZR18",
        treadwear_rating=300,
        estimated_mu=estimate_mu_from_treadwear(300),
        mu_source=MuSource.FORMULA_ESTIMATE,
        mu_confidence="medium",
        pressure_psi=34.0,
        brand="Michelin",
        age_sessions=3,
    )


@pytest.fixture()
def sample_brakes() -> BrakeSpec:
    return BrakeSpec(
        compound="ferro-carbon",
        rotor_type="slotted",
        pad_temp_range="200-650C",
        fluid_type="DOT 5.1",
    )


@pytest.fixture()
def sample_suspension() -> SuspensionSpec:
    return SuspensionSpec(
        type="coilover",
        front_spring_rate="10k",
        rear_spring_rate="8k",
        front_camber_deg=-2.5,
        rear_camber_deg=-1.8,
        front_toe="0mm",
        rear_toe="1mm in",
        front_rebound=8,
        front_compression=5,
        rear_rebound=7,
        rear_compression=4,
        sway_bar_front="adjustable",
        sway_bar_rear="stock",
    )


# ---------------------------------------------------------------------------
# TestTireSpec
# ---------------------------------------------------------------------------


class TestTireSpec:
    """Tests for TireSpec creation and tire-related enums."""

    def test_create_basic_tire(self, sample_tire: TireSpec) -> None:
        assert sample_tire.model == "Pilot Sport 4S"
        assert sample_tire.compound_category == TireCompoundCategory.SUPER_200TW
        assert sample_tire.size == "255/35ZR18"
        assert sample_tire.treadwear_rating == 300
        assert sample_tire.mu_source == MuSource.FORMULA_ESTIMATE
        assert sample_tire.mu_confidence == "medium"
        assert sample_tire.pressure_psi == 34.0
        assert sample_tire.brand == "Michelin"
        assert sample_tire.age_sessions == 3

    def test_tire_optional_fields_default_none(self) -> None:
        tire = TireSpec(
            model="NT01",
            compound_category=TireCompoundCategory.R_COMPOUND,
            size="245/40R17",
            treadwear_rating=60,
            estimated_mu=1.35,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="high",
        )
        assert tire.pressure_psi is None
        assert tire.brand is None
        assert tire.age_sessions is None

    def test_all_compound_categories_exist(self) -> None:
        expected = {
            "street",
            "endurance_200tw",
            "super_200tw",
            "100tw",
            "r_comp",
            "slick",
        }
        actual = {c.value for c in TireCompoundCategory}
        assert actual == expected

    def test_all_mu_source_values(self) -> None:
        expected = {
            "formula_estimate",
            "curated_table",
            "manufacturer_spec",
            "user_override",
        }
        actual = {s.value for s in MuSource}
        assert actual == expected

    def test_compound_category_is_str_enum(self) -> None:
        """str Enums can be used directly as strings."""
        assert TireCompoundCategory.STREET == "street"
        assert isinstance(TireCompoundCategory.SLICK, str)

    def test_mu_source_is_str_enum(self) -> None:
        assert MuSource.FORMULA_ESTIMATE == "formula_estimate"
        assert isinstance(MuSource.USER_OVERRIDE, str)


# ---------------------------------------------------------------------------
# TestEquipmentProfile
# ---------------------------------------------------------------------------


class TestEquipmentProfile:
    """Tests for EquipmentProfile with varying completeness."""

    def test_minimal_profile_tires_only(self, sample_tire: TireSpec) -> None:
        profile = EquipmentProfile(
            id="prof-001",
            name="Street setup",
            tires=sample_tire,
        )
        assert profile.id == "prof-001"
        assert profile.name == "Street setup"
        assert profile.tires is sample_tire
        assert profile.brakes is None
        assert profile.suspension is None
        assert profile.notes is None

    def test_full_profile(
        self,
        sample_tire: TireSpec,
        sample_brakes: BrakeSpec,
        sample_suspension: SuspensionSpec,
    ) -> None:
        profile = EquipmentProfile(
            id="prof-002",
            name="Full track setup",
            tires=sample_tire,
            brakes=sample_brakes,
            suspension=sample_suspension,
            notes="Aggressive alignment for Barber",
        )
        assert profile.brakes is sample_brakes
        assert profile.suspension is sample_suspension
        assert profile.notes == "Aggressive alignment for Barber"

    def test_brake_spec_all_optional(self) -> None:
        brakes = BrakeSpec()
        assert brakes.compound is None
        assert brakes.rotor_type is None
        assert brakes.pad_temp_range is None
        assert brakes.fluid_type is None

    def test_suspension_spec_all_optional(self) -> None:
        susp = SuspensionSpec()
        assert susp.type is None
        assert susp.front_spring_rate is None
        assert susp.rear_spring_rate is None
        assert susp.front_camber_deg is None
        assert susp.rear_camber_deg is None
        assert susp.front_toe is None
        assert susp.rear_toe is None
        assert susp.front_rebound is None
        assert susp.front_compression is None
        assert susp.rear_rebound is None
        assert susp.rear_compression is None
        assert susp.sway_bar_front is None
        assert susp.sway_bar_rear is None


# ---------------------------------------------------------------------------
# TestEstimateMuFromTreadwear
# ---------------------------------------------------------------------------


class TestEstimateMuFromTreadwear:
    """Tests for the HPWizard mu estimation formula."""

    def test_tw_200_gives_expected_value(self) -> None:
        mu = estimate_mu_from_treadwear(200)
        # 2.25 / 200^0.15 ≈ 1.016
        assert mu == pytest.approx(1.016, abs=0.01)

    def test_lower_tw_gives_higher_mu(self) -> None:
        mu_100 = estimate_mu_from_treadwear(100)
        mu_200 = estimate_mu_from_treadwear(200)
        mu_400 = estimate_mu_from_treadwear(400)
        assert mu_100 > mu_200 > mu_400

    def test_higher_tw_gives_lower_mu(self) -> None:
        mu_500 = estimate_mu_from_treadwear(500)
        mu_600 = estimate_mu_from_treadwear(600)
        assert mu_500 > mu_600

    def test_zero_treadwear_returns_fallback(self) -> None:
        assert estimate_mu_from_treadwear(0) == 1.0

    def test_negative_treadwear_returns_fallback(self) -> None:
        assert estimate_mu_from_treadwear(-50) == 1.0

    def test_very_low_tw_gives_high_mu(self) -> None:
        """Extreme soft compound (TW=40) should produce mu > 1.2."""
        mu = estimate_mu_from_treadwear(40)
        assert mu > 1.2

    def test_very_high_tw_gives_low_mu(self) -> None:
        """Long-life tire (TW=700) should produce mu < 0.85."""
        mu = estimate_mu_from_treadwear(700)
        assert mu < 0.85

    def test_formula_exact_value(self) -> None:
        """Verify the formula matches 2.25 / TW^0.15 exactly."""
        tw = 250
        expected = 2.25 / (250**0.15)
        assert estimate_mu_from_treadwear(tw) == pytest.approx(expected, rel=1e-10)


# ---------------------------------------------------------------------------
# TestCategoryMuDefaults
# ---------------------------------------------------------------------------


class TestCategoryMuDefaults:
    """Tests for the CATEGORY_MU_DEFAULTS lookup table."""

    def test_all_categories_have_defaults(self) -> None:
        for cat in TireCompoundCategory:
            assert cat in CATEGORY_MU_DEFAULTS, f"Missing default mu for {cat}"

    def test_defaults_increase_monotonically(self) -> None:
        """Grip levels should increase from street to slick."""
        ordered = [
            TireCompoundCategory.STREET,
            TireCompoundCategory.ENDURANCE_200TW,
            TireCompoundCategory.SUPER_200TW,
            TireCompoundCategory.TW_100,
            TireCompoundCategory.R_COMPOUND,
            TireCompoundCategory.SLICK,
        ]
        values = [CATEGORY_MU_DEFAULTS[c] for c in ordered]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1], (
                f"{ordered[i].value} ({values[i]}) should be less than "
                f"{ordered[i + 1].value} ({values[i + 1]})"
            )

    def test_street_mu_value(self) -> None:
        assert CATEGORY_MU_DEFAULTS[TireCompoundCategory.STREET] == 0.85

    def test_slick_mu_value(self) -> None:
        assert CATEGORY_MU_DEFAULTS[TireCompoundCategory.SLICK] == 1.50

    def test_no_extra_categories(self) -> None:
        """Defaults should not contain keys outside the enum."""
        assert set(CATEGORY_MU_DEFAULTS.keys()) == set(TireCompoundCategory)


# ---------------------------------------------------------------------------
# TestTrackCondition
# ---------------------------------------------------------------------------


class TestTrackCondition:
    """Tests for TrackCondition enum."""

    def test_all_values(self) -> None:
        assert {c.value for c in TrackCondition} == {"dry", "damp", "wet"}

    def test_is_str_enum(self) -> None:
        assert TrackCondition.DRY == "dry"


# ---------------------------------------------------------------------------
# TestSessionConditions
# ---------------------------------------------------------------------------


class TestSessionConditions:
    """Tests for SessionConditions dataclass."""

    def test_defaults(self) -> None:
        cond = SessionConditions()
        assert cond.track_condition == TrackCondition.DRY
        assert cond.ambient_temp_c is None
        assert cond.track_temp_c is None
        assert cond.humidity_pct is None
        assert cond.wind_speed_kmh is None
        assert cond.wind_direction_deg is None
        assert cond.precipitation_mm is None
        assert cond.weather_source is None

    def test_full_conditions(self) -> None:
        cond = SessionConditions(
            track_condition=TrackCondition.DAMP,
            ambient_temp_c=22.5,
            track_temp_c=35.0,
            humidity_pct=65.0,
            wind_speed_kmh=12.0,
            wind_direction_deg=180.0,
            precipitation_mm=0.5,
            weather_source="weather_api",
        )
        assert cond.track_condition == TrackCondition.DAMP
        assert cond.ambient_temp_c == 22.5
        assert cond.precipitation_mm == 0.5


# ---------------------------------------------------------------------------
# TestSessionEquipment
# ---------------------------------------------------------------------------


class TestSessionEquipment:
    """Tests for SessionEquipment dataclass."""

    def test_minimal(self) -> None:
        se = SessionEquipment(session_id="sess-001", profile_id="prof-001")
        assert se.session_id == "sess-001"
        assert se.profile_id == "prof-001"
        assert se.overrides == {}
        assert se.conditions is None

    def test_with_overrides_and_conditions(self) -> None:
        cond = SessionConditions(track_condition=TrackCondition.WET)
        se = SessionEquipment(
            session_id="sess-002",
            profile_id="prof-001",
            overrides={"pressure_psi": 32.0},
            conditions=cond,
        )
        assert se.overrides == {"pressure_psi": 32.0}
        assert se.conditions is not None
        assert se.conditions.track_condition == TrackCondition.WET

    def test_overrides_default_is_independent(self) -> None:
        """Each instance should get its own dict, not a shared mutable default."""
        se1 = SessionEquipment(session_id="s1", profile_id="p1")
        se2 = SessionEquipment(session_id="s2", profile_id="p1")
        se1.overrides["key"] = "value"
        assert "key" not in se2.overrides


# ---------------------------------------------------------------------------
# TestCategoryAccelG
# ---------------------------------------------------------------------------


class TestCategoryAccelG:
    """Tests for the _CATEGORY_ACCEL_G lookup table."""

    def test_all_categories_have_accel_values(self) -> None:
        for cat in TireCompoundCategory:
            assert cat in _CATEGORY_ACCEL_G, f"Missing accel G for {cat}"

    def test_accel_values_increase_monotonically(self) -> None:
        """Higher-grip categories should allow slightly more acceleration."""
        ordered = [
            TireCompoundCategory.STREET,
            TireCompoundCategory.ENDURANCE_200TW,
            TireCompoundCategory.SUPER_200TW,
            TireCompoundCategory.TW_100,
            TireCompoundCategory.R_COMPOUND,
            TireCompoundCategory.SLICK,
        ]
        values = [_CATEGORY_ACCEL_G[c] for c in ordered]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1]

    def test_no_extra_categories(self) -> None:
        assert set(_CATEGORY_ACCEL_G.keys()) == set(TireCompoundCategory)


# ---------------------------------------------------------------------------
# TestEquipmentToVehicleParams
# ---------------------------------------------------------------------------


class TestEquipmentToVehicleParams:
    """Tests for equipment_to_vehicle_params mapping."""

    def test_basic_mapping(self) -> None:
        """Tire mu maps correctly to VehicleParams."""
        tire = TireSpec(
            model="Test",
            compound_category=TireCompoundCategory.SUPER_200TW,
            size="255/40R17",
            treadwear_rating=200,
            estimated_mu=1.10,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="test",
        )
        profile = EquipmentProfile(id="p1", name="Test", tires=tire)
        params = equipment_to_vehicle_params(profile)
        assert params.mu == 1.10
        assert params.max_lateral_g == 1.10
        assert params.max_accel_g == 0.55  # SUPER_200TW
        assert abs(params.max_decel_g - 1.10 * _BRAKE_EFFICIENCY) < 1e-6

    def test_street_tire(self) -> None:
        """Street tire category maps to lowest accel G."""
        tire = TireSpec(
            model="Street",
            compound_category=TireCompoundCategory.STREET,
            size="225/45R17",
            treadwear_rating=400,
            estimated_mu=0.85,
            mu_source=MuSource.FORMULA_ESTIMATE,
            mu_confidence="test",
        )
        profile = EquipmentProfile(id="p2", name="Street", tires=tire)
        params = equipment_to_vehicle_params(profile)
        assert params.mu == 0.85
        assert params.max_accel_g == 0.40  # STREET

    def test_r_compound_higher_decel(self) -> None:
        """R-compound with high mu should produce max_decel_g above 1.0."""
        tire = TireSpec(
            model="R7",
            compound_category=TireCompoundCategory.R_COMPOUND,
            size="275/35R18",
            treadwear_rating=40,
            estimated_mu=1.35,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="test",
        )
        profile = EquipmentProfile(id="p3", name="Race", tires=tire)
        params = equipment_to_vehicle_params(profile)
        assert params.max_decel_g > 1.0
        assert params.max_accel_g == 0.65  # R_COMPOUND

    def test_slick_tire(self) -> None:
        """Slick category should yield highest accel G."""
        tire = TireSpec(
            model="Slick",
            compound_category=TireCompoundCategory.SLICK,
            size="280/680R18",
            treadwear_rating=None,
            estimated_mu=1.50,
            mu_source=MuSource.MANUFACTURER_SPEC,
            mu_confidence="high",
        )
        profile = EquipmentProfile(id="p4", name="Full Race", tires=tire)
        params = equipment_to_vehicle_params(profile)
        assert params.mu == 1.50
        assert params.max_lateral_g == 1.50
        assert params.max_accel_g == 0.70  # SLICK
        assert params.max_decel_g == pytest.approx(1.50 * _BRAKE_EFFICIENCY)
        assert params.top_speed_mps == 80.0

    def test_top_speed_always_80(self) -> None:
        """top_speed_mps should always be 80 regardless of equipment."""
        tire = TireSpec(
            model="Any",
            compound_category=TireCompoundCategory.ENDURANCE_200TW,
            size="225/45R17",
            treadwear_rating=200,
            estimated_mu=1.00,
            mu_source=MuSource.FORMULA_ESTIMATE,
            mu_confidence="test",
        )
        profile = EquipmentProfile(id="p5", name="Any", tires=tire)
        params = equipment_to_vehicle_params(profile)
        assert params.top_speed_mps == 80.0

    def test_all_categories_produce_valid_params(self) -> None:
        """Every tire compound category should produce a valid VehicleParams."""
        for cat in TireCompoundCategory:
            mu = CATEGORY_MU_DEFAULTS[cat]
            tire = TireSpec(
                model="Test",
                compound_category=cat,
                size="255/40R17",
                treadwear_rating=200,
                estimated_mu=mu,
                mu_source=MuSource.CURATED_TABLE,
                mu_confidence="test",
            )
            profile = EquipmentProfile(id=f"p-{cat}", name=f"Test {cat}", tires=tire)
            params = equipment_to_vehicle_params(profile)
            assert params.mu == mu
            assert params.max_lateral_g == mu
            assert params.max_accel_g == _CATEGORY_ACCEL_G[cat]
            assert params.max_decel_g == pytest.approx(mu * _BRAKE_EFFICIENCY)
            assert params.top_speed_mps == 80.0

    def test_returns_vehicle_params_type(self) -> None:
        """Return type should be VehicleParams from velocity_profile module."""
        from cataclysm.velocity_profile import VehicleParams

        tire = TireSpec(
            model="Test",
            compound_category=TireCompoundCategory.TW_100,
            size="255/40R17",
            treadwear_rating=100,
            estimated_mu=1.20,
            mu_source=MuSource.CURATED_TABLE,
            mu_confidence="test",
        )
        profile = EquipmentProfile(id="p6", name="Test", tires=tire)
        params = equipment_to_vehicle_params(profile)
        assert isinstance(params, VehicleParams)

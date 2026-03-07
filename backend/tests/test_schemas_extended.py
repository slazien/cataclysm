"""Extended tests for schemas — covers uncovered lines.

Targets:
  - schemas/equipment.py: validate_year_range validator (lines 20-26)
  - schemas/equipment.py: validate_override_keys validator (lines 123-128)
  - schemas/coaching.py: clamp_time_cost_s validator on PriorityCornerSchema (lines 42-43)
  - db/database.py: get_db generator (lines 34-40)
  - api/dependencies.py: get_optional_user exception branch (lines 193-198)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# schemas/equipment.py validators
# ---------------------------------------------------------------------------


class TestVehicleSpecSchemaValidator:
    """Tests for VehicleSpecSchema.validate_year_range."""

    def _make_vehicle(self, year_range: list[int]) -> dict:
        return {
            "make": "Porsche",
            "model": "911",
            "generation": "992",
            "year_range": year_range,
            "weight_kg": 1450.0,
            "wheelbase_m": 2.45,
            "track_width_front_m": 1.53,
            "track_width_rear_m": 1.58,
            "cg_height_m": 0.46,
            "weight_dist_front_pct": 38.0,
            "drivetrain": "RWD",
            "hp": 450,
            "torque_nm": 530,
            "has_aero": False,
        }

    def test_valid_year_range(self) -> None:
        """year_range with 2 ascending values passes validation."""
        from backend.api.schemas.equipment import VehicleSpecSchema

        data = self._make_vehicle([2019, 2025])
        schema = VehicleSpecSchema(**data)
        assert schema.year_range == [2019, 2025]

    def test_year_range_wrong_length_raises(self) -> None:
        """year_range with only 1 element raises ValidationError (line 21-22)."""
        from backend.api.schemas.equipment import VehicleSpecSchema

        data = self._make_vehicle([2020])
        with pytest.raises(ValidationError) as exc_info:
            VehicleSpecSchema(**data)
        assert "year_range must contain exactly 2" in str(exc_info.value)

    def test_year_range_reversed_raises(self) -> None:
        """year_range where start > end raises ValidationError (lines 23-25)."""
        from backend.api.schemas.equipment import VehicleSpecSchema

        data = self._make_vehicle([2025, 2019])
        with pytest.raises(ValidationError) as exc_info:
            VehicleSpecSchema(**data)
        assert "start must be" in str(exc_info.value)

    def test_year_range_equal_start_end_passes(self) -> None:
        """year_range [2020, 2020] is valid (start == end is allowed)."""
        from backend.api.schemas.equipment import VehicleSpecSchema

        data = self._make_vehicle([2020, 2020])
        schema = VehicleSpecSchema(**data)
        assert schema.year_range == [2020, 2020]

    def test_year_range_too_many_elements_raises(self) -> None:
        """year_range with 3 elements raises ValidationError."""
        from backend.api.schemas.equipment import VehicleSpecSchema

        data = self._make_vehicle([2019, 2022, 2025])
        with pytest.raises(ValidationError):
            VehicleSpecSchema(**data)


# mu_confidence is a str field in TireSpecSchema
_TIRE_PAYLOAD = {
    "model": "RE-71RS",
    "compound_category": "r_compound",
    "size": "245/40R17",
    "estimated_mu": 1.12,
    "mu_source": "curated",
    "mu_confidence": "high",
}


class TestEquipmentProfileCreateValidator:
    """Tests for EquipmentProfileCreate.validate_override_keys."""

    def test_valid_override_keys_pass(self) -> None:
        """vehicle_overrides with only allowed keys passes validation."""
        from backend.api.schemas.equipment import EquipmentProfileCreate

        profile = EquipmentProfileCreate(
            name="Test",
            tires=_TIRE_PAYLOAD,
            vehicle_overrides={"hp": 400.0, "weight_kg": 1500.0},
        )
        assert profile.vehicle_overrides["hp"] == 400.0

    def test_invalid_override_key_raises(self) -> None:
        """vehicle_overrides with unknown key raises ValidationError (lines 123-128)."""
        from backend.api.schemas.equipment import EquipmentProfileCreate

        with pytest.raises(ValidationError) as exc_info:
            EquipmentProfileCreate(
                name="Test",
                tires=_TIRE_PAYLOAD,
                vehicle_overrides={"invalid_field": 42.0},
            )
        assert "invalid vehicle_overrides keys" in str(exc_info.value).lower()

    def test_multiple_invalid_keys_raises(self) -> None:
        """Multiple unknown keys are all reported in the error."""
        from backend.api.schemas.equipment import EquipmentProfileCreate

        with pytest.raises(ValidationError) as exc_info:
            EquipmentProfileCreate(
                name="Test",
                tires=_TIRE_PAYLOAD,
                vehicle_overrides={"bad_key1": 1.0, "bad_key2": 2.0},
            )
        error_str = str(exc_info.value)
        assert "bad_key" in error_str

    def test_empty_overrides_passes(self) -> None:
        """Empty vehicle_overrides dict is valid."""
        from backend.api.schemas.equipment import EquipmentProfileCreate

        profile = EquipmentProfileCreate(
            name="Test",
            tires=_TIRE_PAYLOAD,
            vehicle_overrides={},
        )
        assert profile.vehicle_overrides == {}


# ---------------------------------------------------------------------------
# schemas/coaching.py — PriorityCornerSchema.clamp_time_cost_s validator
# ---------------------------------------------------------------------------


class TestPriorityCornerSchemaClampTimeCostS:
    """Tests for PriorityCornerSchema.clamp_time_cost_s validator (lines 42-43)."""

    def _make_priority_corner(self, time_cost_s: object) -> dict:
        return {
            "corner": 3,
            "time_cost_s": time_cost_s,
            "issue": "Late braking",
            "tip": "Brake earlier",
        }

    def test_valid_positive_value_is_passed_through(self) -> None:
        """A valid positive float value passes through unchanged."""
        from backend.api.schemas.coaching import PriorityCornerSchema

        corner = PriorityCornerSchema(**self._make_priority_corner(1.5))
        assert corner.time_cost_s == 1.5

    def test_negative_value_is_clamped_to_zero(self) -> None:
        """A negative float value is clamped to 0.0 (line 44-45)."""
        from backend.api.schemas.coaching import PriorityCornerSchema

        corner = PriorityCornerSchema(**self._make_priority_corner(-1.0))
        assert corner.time_cost_s == 0.0

    def test_infinity_is_clamped_to_zero(self) -> None:
        """math.inf value is clamped to 0.0."""
        import math

        from backend.api.schemas.coaching import PriorityCornerSchema

        corner = PriorityCornerSchema(**self._make_priority_corner(math.inf))
        assert corner.time_cost_s == 0.0

    def test_nan_is_clamped_to_zero(self) -> None:
        """NaN is treated as not finite and returns 0.0."""
        import math

        from backend.api.schemas.coaching import PriorityCornerSchema

        corner = PriorityCornerSchema(**self._make_priority_corner(math.nan))
        assert corner.time_cost_s == 0.0

    def test_unparseable_string_returns_zero(self) -> None:
        """A non-numeric string falls into the except branch and returns 0.0 (line 43)."""
        from backend.api.schemas.coaching import PriorityCornerSchema

        corner = PriorityCornerSchema(**self._make_priority_corner("not-a-number"))
        assert corner.time_cost_s == 0.0

    def test_zero_value_passes(self) -> None:
        """Zero is valid (non-negative finite float)."""
        from backend.api.schemas.coaching import PriorityCornerSchema

        corner = PriorityCornerSchema(**self._make_priority_corner(0.0))
        assert corner.time_cost_s == 0.0


# ---------------------------------------------------------------------------
# db/database.py — get_db generator rollback path
# ---------------------------------------------------------------------------


class TestGetDbGenerator:
    """Tests for the get_db async generator (lines 34-40)."""

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self) -> None:
        """get_db yields an AsyncSession (line 36)."""
        from sqlalchemy.ext.asyncio import AsyncSession

        from backend.api.db.database import get_db

        gen = get_db()
        session = await gen.__anext__()
        try:
            assert isinstance(session, AsyncSession)
        finally:
            import contextlib

            with contextlib.suppress(StopAsyncIteration):
                await gen.aclose()

    @pytest.mark.asyncio
    async def test_get_db_rollback_on_exception(self) -> None:
        """get_db rolls back the session when an exception is raised (lines 38-40)."""
        from backend.api.db.database import get_db

        gen = get_db()
        session = await gen.__anext__()
        assert session is not None

        # Simulate an exception in the handler — generator re-raises after rollback
        import contextlib

        with contextlib.suppress(ValueError):
            await gen.athrow(ValueError("simulated error"))


# ---------------------------------------------------------------------------
# api/dependencies.py — get_optional_user exception branch
# ---------------------------------------------------------------------------


class TestGetOptionalUser:
    """Tests for dependencies.get_optional_user (lines 193-198)."""

    def test_get_optional_user_returns_none_when_no_token(self) -> None:
        """get_optional_user returns None when get_current_user raises 401 (lines 197-198)."""
        from backend.api.config import Settings
        from backend.api.dependencies import get_optional_user

        settings = Settings()
        settings.dev_auth_bypass = False
        settings.nextauth_secret = None
        # No authorization, no cookie, no test header → should raise inside → return None
        result = get_optional_user(
            settings=settings,
            authorization=None,
            session_token=None,
            secure_session_token=None,
            x_test_user_id=None,
        )
        assert result is None

    def test_get_optional_user_returns_user_when_dev_bypass(self) -> None:
        """get_optional_user returns AuthenticatedUser when DEV_AUTH_BYPASS is enabled."""
        import os
        from unittest.mock import patch

        from backend.api.config import Settings
        from backend.api.dependencies import get_optional_user

        settings = Settings()
        settings.dev_auth_bypass = True
        settings.nextauth_secret = None

        # Ensure RAILWAY_ENVIRONMENT is not set
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("RAILWAY_ENVIRONMENT", None)
            result = get_optional_user(
                settings=settings,
                authorization=None,
                session_token=None,
                secure_session_token=None,
                x_test_user_id=None,
            )
        # With dev_auth_bypass and no RAILWAY_ENVIRONMENT, returns a dev user
        assert result is not None

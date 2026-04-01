"""Tests for the stable_target parameter on get_optimal_profile_data."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

if "pymap3d" not in sys.modules:
    sys.modules["pymap3d"] = types.SimpleNamespace(
        geodetic2enu=lambda lat, lon, alt, lat0, lon0, alt0: (
            lat * 0,
            lon * 0,
            alt * 0,
        ),
    )

from backend.api.services import pipeline
from backend.api.services.pipeline import _physics_cache
from backend.api.services.session_store import SessionData
from cataclysm.curvature import CurvatureResult
from cataclysm.velocity_profile import OptimalProfile, VehicleParams

BASE_MU = 1.10
CALIBRATED_MU = 1.25


@pytest.fixture(autouse=True)
def _clear_physics_cache() -> None:
    """Ensure each test starts with a clean physics cache."""
    _physics_cache.clear()


def _make_lap() -> pd.DataFrame:
    n = 10
    return pd.DataFrame(
        {
            "lap_distance_m": np.arange(n, dtype=float) * 0.7,
            "speed_mps": np.full(n, 30.0),
            "lap_time_s": np.arange(n, dtype=float) * (0.7 / 30.0),
            "lateral_g": np.full(n, 1.0),
            "longitudinal_g": np.zeros(n),
            "lat": np.linspace(33.0, 33.001, n),
            "lon": np.linspace(-86.0, -86.001, n),
        }
    )


def _make_session_data() -> SessionData:
    processed = MagicMock()
    processed.best_lap = 1
    processed.resampled_laps = {
        1: _make_lap(),
        2: _make_lap(),
    }

    snapshot = MagicMock()
    snapshot.metadata = MagicMock(
        track_name="Test Track",
        session_date="2026-03-31",
    )

    return SessionData(
        session_id="sess-stable",
        snapshot=snapshot,
        parsed=MagicMock(),
        processed=processed,
        corners=[],
        all_lap_corners={},
        coaching_laps=[1, 2],
    )


def _make_curvature_result() -> CurvatureResult:
    distance = np.linspace(0.0, 6.3, 10)
    zeros = np.zeros(10, dtype=float)
    return CurvatureResult(
        distance_m=distance,
        curvature=zeros,
        abs_curvature=zeros,
        heading_rad=zeros,
        x_smooth=zeros,
        y_smooth=zeros,
    )


def _base_vehicle_params() -> VehicleParams:
    return VehicleParams(
        mu=BASE_MU,
        max_accel_g=0.5,
        max_decel_g=1.0,
        max_lateral_g=BASE_MU,
    )


def _make_optimal(params: VehicleParams | None) -> OptimalProfile:
    distance = np.linspace(0.0, 6.3, 10)
    speed = np.full(10, 30.0)
    return OptimalProfile(
        distance_m=distance,
        optimal_speed_mps=speed,
        curvature=np.zeros(10),
        max_cornering_speed_mps=speed,
        optimal_brake_points=[],
        optimal_throttle_points=[],
        lap_time_s=float(np.sum(0.7 / speed)),
        vehicle_params=params or _base_vehicle_params(),
    )


@pytest.mark.asyncio
async def test_stable_target_skips_calibration_and_sweep() -> None:
    """stable_target=True must NOT call _calibrate_sync or solver_based_sweep."""
    sd = _make_session_data()

    with (
        patch.object(
            pipeline,
            "_try_lidar_elevation",
            AsyncMock(return_value=None),
        ),
        patch.object(
            pipeline,
            "compute_curvature",
            return_value=_make_curvature_result(),
        ),
        patch.object(
            pipeline,
            "resolve_vehicle_params",
            return_value=_base_vehicle_params(),
        ),
        patch.object(
            pipeline,
            "calibrate_grip_from_telemetry",
            side_effect=AssertionError("calibration must not be called in stable mode"),
        ),
        patch.object(
            pipeline,
            "compute_optimal_profile",
            side_effect=lambda *a, **kw: _make_optimal(kw.get("params")),
        ) as mock_solver,
    ):
        result = await pipeline.get_optimal_profile_data(sd, stable_target=True)

    # The solver should have been called with the base vehicle params
    params_used = mock_solver.call_args.kwargs["params"]
    assert params_used is not None
    assert abs(params_used.mu - BASE_MU) < 1e-6, f"Expected base mu={BASE_MU}, got {params_used.mu}"
    # calibrated_mu in the result should reflect the base mu, not calibrated
    assert result["calibrated_mu"] == f"{BASE_MU:.2f}"


@pytest.mark.asyncio
async def test_default_mode_calls_calibration() -> None:
    """stable_target=False (default) must call grip calibration."""
    sd = _make_session_data()
    calibration_called = False

    def fake_calibrate(lat_g: np.ndarray, lon_g: np.ndarray) -> MagicMock:
        nonlocal calibration_called
        calibration_called = True
        grip = MagicMock()
        grip.max_lateral_g = CALIBRATED_MU
        grip.max_brake_g = 1.0
        grip.max_accel_g = 0.5
        grip.confidence = "high"
        return grip

    with (
        patch.object(
            pipeline,
            "_try_lidar_elevation",
            AsyncMock(return_value=None),
        ),
        patch.object(
            pipeline,
            "compute_curvature",
            return_value=_make_curvature_result(),
        ),
        patch.object(
            pipeline,
            "resolve_vehicle_params",
            return_value=_base_vehicle_params(),
        ),
        patch.object(
            pipeline,
            "calibrate_grip_from_telemetry",
            side_effect=fake_calibrate,
        ),
        patch.object(
            pipeline,
            "apply_calibration_to_params",
            side_effect=lambda base, grip, mu_cap=None: VehicleParams(
                mu=CALIBRATED_MU,
                max_accel_g=base.max_accel_g,
                max_decel_g=base.max_decel_g,
                max_lateral_g=CALIBRATED_MU,
            ),
        ),
        patch.object(
            pipeline,
            "compute_optimal_profile",
            side_effect=lambda *a, **kw: _make_optimal(kw.get("params")),
        ) as mock_solver,
    ):
        result = await pipeline.get_optimal_profile_data(sd)

    assert calibration_called, "Calibration should be called in default mode"
    params_used = mock_solver.call_args.kwargs["params"]
    assert params_used is not None
    assert abs(params_used.mu - CALIBRATED_MU) < 1e-6, (
        f"Expected calibrated mu={CALIBRATED_MU}, got {params_used.mu}"
    )
    assert result["calibrated_mu"] == f"{CALIBRATED_MU:.2f}"


@pytest.mark.asyncio
async def test_stable_target_uses_separate_cache_key() -> None:
    """Stable and default modes must not share cache entries."""
    sd = _make_session_data()

    with (
        patch.object(
            pipeline,
            "_try_lidar_elevation",
            AsyncMock(return_value=None),
        ),
        patch.object(
            pipeline,
            "compute_curvature",
            return_value=_make_curvature_result(),
        ),
        patch.object(
            pipeline,
            "resolve_vehicle_params",
            return_value=_base_vehicle_params(),
        ),
        patch.object(
            pipeline,
            "calibrate_grip_from_telemetry",
            return_value=None,
        ),
        patch.object(
            pipeline,
            "compute_optimal_profile",
            side_effect=lambda *a, **kw: _make_optimal(kw.get("params")),
        ) as mock_solver,
    ):
        # First call: stable mode
        await pipeline.get_optimal_profile_data(sd, stable_target=True)
        assert mock_solver.call_count == 1

        # Second call: default mode — must NOT be served from stable cache
        await pipeline.get_optimal_profile_data(sd, stable_target=False)
        assert mock_solver.call_count == 2, "Default mode should not hit the stable cache"

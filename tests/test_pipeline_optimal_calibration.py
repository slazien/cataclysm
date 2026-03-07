"""Tests for optimal-profile calibration independence in the pipeline."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

if "pymap3d" not in sys.modules:
    sys.modules["pymap3d"] = types.SimpleNamespace(
        geodetic2enu=lambda lat, lon, alt, lat0, lon0, alt0: (lat * 0, lon * 0, alt * 0),
    )

from backend.api.services import pipeline
from backend.api.services.pipeline import _physics_cache
from backend.api.services.session_store import SessionData
from cataclysm.curvature import CurvatureResult
from cataclysm.grip_calibration import CalibratedGrip
from cataclysm.optimal_comparison import OptimalComparisonResult
from cataclysm.velocity_profile import OptimalProfile, VehicleParams


@pytest.fixture(autouse=True)
def _clear_physics_cache() -> None:
    """Ensure each test starts with a clean physics cache."""
    _physics_cache.clear()


def _make_lap(lat_g: list[float], lon_g: list[float]) -> pd.DataFrame:
    n = len(lat_g)
    return pd.DataFrame(
        {
            "lap_distance_m": np.arange(n, dtype=float) * 0.7,
            "speed_mps": np.full(n, 30.0),
            "lap_time_s": np.arange(n, dtype=float) * (0.7 / 30.0),
            "lateral_g": np.array(lat_g, dtype=float),
            "longitudinal_g": np.array(lon_g, dtype=float),
            "lat": np.linspace(33.0, 33.001, n),
            "lon": np.linspace(-86.0, -86.001, n),
        }
    )


def _make_session_data(coaching_laps: list[int], best_lap: int) -> SessionData:
    processed = MagicMock()
    processed.best_lap = best_lap
    processed.resampled_laps = {
        1: _make_lap([1.0, 1.1], [0.1, 0.0]),
        2: _make_lap([9.0, 9.1], [9.0, 9.1]),  # target lap: obviously distinct
        3: _make_lap([1.2, 1.3], [0.0, -0.1]),
    }

    snapshot = MagicMock()
    snapshot.metadata = MagicMock(track_name="Test Track", session_date="2026-03-05")

    return SessionData(
        session_id="sess-1",
        snapshot=snapshot,
        parsed=MagicMock(),
        processed=processed,
        corners=[],
        all_lap_corners={},
        coaching_laps=coaching_laps,
    )


def _make_curvature_result() -> CurvatureResult:
    distance = np.array([0.0, 0.7], dtype=float)
    zeros = np.zeros(2, dtype=float)
    return CurvatureResult(
        distance_m=distance,
        curvature=zeros,
        abs_curvature=zeros,
        heading_rad=zeros,
        x_smooth=zeros,
        y_smooth=zeros,
    )


def _make_optimal(params: VehicleParams | None) -> OptimalProfile:
    distance = np.array([0.0, 0.7], dtype=float)
    speed = np.full(2, 30.0)
    return OptimalProfile(
        distance_m=distance,
        optimal_speed_mps=speed,
        curvature=np.zeros(2),
        max_cornering_speed_mps=speed,
        optimal_brake_points=[],
        optimal_throttle_points=[],
        lap_time_s=float(np.sum(0.7 / speed)),
        vehicle_params=params
        or VehicleParams(mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0),
    )


@pytest.mark.asyncio
async def test_optimal_profile_calibrates_from_independent_laps_only() -> None:
    """Best-lap telemetry should not self-calibrate its own benchmark."""
    session_data = _make_session_data(coaching_laps=[1, 2, 3], best_lap=2)
    captured: dict[str, np.ndarray] = {}

    def fake_calibrate(lat_g: np.ndarray, lon_g: np.ndarray) -> CalibratedGrip:
        captured["lat"] = lat_g.copy()
        captured["lon"] = lon_g.copy()
        return CalibratedGrip(
            max_lateral_g=1.2,
            max_brake_g=1.0,
            max_accel_g=0.5,
            point_count=len(lat_g),
            confidence="high",
        )

    with (
        patch.object(pipeline, "_try_lidar_elevation", AsyncMock(return_value=None)),
        patch.object(pipeline, "compute_curvature", return_value=_make_curvature_result()),
        patch.object(pipeline, "resolve_vehicle_params", return_value=None),
        patch.object(pipeline, "calibrate_grip_from_telemetry", side_effect=fake_calibrate),
        patch.object(
            pipeline,
            "compute_optimal_profile",
            side_effect=lambda *args, **kwargs: _make_optimal(kwargs.get("params")),
        ),
    ):
        await pipeline.get_optimal_profile_data(session_data)

    np.testing.assert_allclose(captured["lat"], np.array([1.0, 1.1, 1.2, 1.3]))
    np.testing.assert_allclose(captured["lon"], np.array([0.1, 0.0, 0.0, -0.1]))


@pytest.mark.asyncio
async def test_optimal_profile_skips_calibration_without_independent_laps() -> None:
    """A single target lap should use defaults/equipment, not self-calibration."""
    session_data = _make_session_data(coaching_laps=[2], best_lap=2)

    with (
        patch.object(pipeline, "_try_lidar_elevation", AsyncMock(return_value=None)),
        patch.object(pipeline, "compute_curvature", return_value=_make_curvature_result()),
        patch.object(pipeline, "resolve_vehicle_params", return_value=None),
        patch.object(
            pipeline,
            "calibrate_grip_from_telemetry",
            side_effect=AssertionError("independent laps required for calibration"),
        ),
        patch.object(
            pipeline,
            "compute_optimal_profile",
            side_effect=lambda *args, **kwargs: _make_optimal(kwargs.get("params")),
        ) as mock_optimal,
    ):
        await pipeline.get_optimal_profile_data(session_data)

    params = mock_optimal.call_args.kwargs["params"]
    assert params is None


@pytest.mark.asyncio
async def test_optimal_comparison_uses_independent_calibration_and_returns_validity() -> None:
    """Comparison path should use independent laps and surface validity metadata."""
    session_data = _make_session_data(coaching_laps=[1, 2, 3], best_lap=2)
    captured: dict[str, np.ndarray] = {}

    def fake_calibrate(lat_g: np.ndarray, lon_g: np.ndarray) -> CalibratedGrip:
        captured["lat"] = lat_g.copy()
        captured["lon"] = lon_g.copy()
        return CalibratedGrip(
            max_lateral_g=1.2,
            max_brake_g=1.0,
            max_accel_g=0.5,
            point_count=len(lat_g),
            confidence="high",
        )

    fake_result = OptimalComparisonResult(
        corner_opportunities=[],
        actual_lap_time_s=10.0,
        optimal_lap_time_s=11.0,
        total_gap_s=-1.0,
        speed_delta_mps=np.zeros(2),
        distance_m=np.array([0.0, 0.7]),
        is_valid=False,
        invalid_reasons=["aggregate_optimal_slower_than_actual"],
    )

    with (
        patch.object(pipeline, "_try_lidar_elevation", AsyncMock(return_value=None)),
        patch.object(pipeline, "compute_curvature", return_value=_make_curvature_result()),
        patch.object(pipeline, "resolve_vehicle_params", return_value=None),
        patch.object(pipeline, "calibrate_grip_from_telemetry", side_effect=fake_calibrate),
        patch.object(
            pipeline,
            "compute_optimal_profile",
            side_effect=lambda *args, **kwargs: _make_optimal(kwargs.get("params")),
        ),
        patch.object(pipeline, "compare_with_optimal", return_value=fake_result),
    ):
        result = await pipeline.get_optimal_comparison_data(session_data)

    np.testing.assert_allclose(captured["lat"], np.array([1.0, 1.1, 1.2, 1.3]))
    np.testing.assert_allclose(captured["lon"], np.array([0.1, 0.0, 0.0, -0.1]))
    assert result["is_valid"] is False
    assert result["invalid_reasons"] == ["aggregate_optimal_slower_than_actual"]

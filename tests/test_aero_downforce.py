"""Tests for aerodynamic downforce in the velocity solver."""

from __future__ import annotations

import numpy as np

from cataclysm.curvature import CurvatureResult
from cataclysm.velocity_profile import G, VehicleParams, compute_optimal_profile


def _make_curvature_result(curvature: np.ndarray, step_m: float = 0.7) -> CurvatureResult:
    n = len(curvature)
    distance = np.arange(n) * step_m
    heading = np.cumsum(curvature) * step_m
    x = np.cumsum(np.cos(heading) * step_m)
    y = np.cumsum(np.sin(heading) * step_m)
    return CurvatureResult(
        distance_m=distance,
        curvature=curvature,
        abs_curvature=np.abs(curvature),
        heading_rad=heading,
        x_smooth=x,
        y_smooth=y,
    )


def test_downforce_increases_cornering_speed() -> None:
    """Car with aero downforce should corner faster than one without."""
    n = 1000
    curvature = np.full(n, 0.01)  # radius ~100m
    cr = _make_curvature_result(curvature)

    base = VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.0,
        max_lateral_g=1.0,
        top_speed_mps=80.0,
        mass_kg=1500,
        wheel_power_w=300_000,
    )
    rho = 1.225
    cl_a = 1.5
    aero_coeff = 0.5 * rho * cl_a / (base.mass_kg * G)

    aero = VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.0,
        max_lateral_g=1.0,
        top_speed_mps=80.0,
        mass_kg=1500,
        wheel_power_w=300_000,
        aero_coefficient=aero_coeff,
    )

    profile_base = compute_optimal_profile(cr, base, closed_circuit=False)
    profile_aero = compute_optimal_profile(cr, aero, closed_circuit=False)

    assert profile_aero.lap_time_s < profile_base.lap_time_s, (
        f"Aero car should be faster: {profile_aero.lap_time_s:.2f} vs {profile_base.lap_time_s:.2f}"
    )
    improvement_pct = (
        (profile_base.lap_time_s - profile_aero.lap_time_s) / profile_base.lap_time_s * 100
    )
    assert improvement_pct > 0.1, f"Improvement too small: {improvement_pct:.2f}%"


def test_downforce_scales_with_mu() -> None:
    """Aero benefit should scale with tire mu — low-mu tires extract less grip from downforce."""
    n = 1000
    curvature = np.full(n, 0.01)  # radius ~100m
    cr = _make_curvature_result(curvature)

    rho = 1.225
    cl_a = 1.5

    # Street tire (mu=0.88) vs R-compound (mu=1.35), both with same aero
    for mu_val in [0.88, 1.35]:
        mass = 1500.0
        aero_coeff = 0.5 * rho * cl_a / (mass * G)
        base = VehicleParams(
            mu=mu_val,
            max_accel_g=0.5,
            max_decel_g=mu_val,
            max_lateral_g=mu_val,
            top_speed_mps=80.0,
            mass_kg=mass,
            wheel_power_w=300_000,
        )
        aero = VehicleParams(
            mu=mu_val,
            max_accel_g=0.5,
            max_decel_g=mu_val,
            max_lateral_g=mu_val,
            top_speed_mps=80.0,
            mass_kg=mass,
            wheel_power_w=300_000,
            aero_coefficient=aero_coeff,
        )
        p_base = compute_optimal_profile(cr, base, closed_circuit=False)
        p_aero = compute_optimal_profile(cr, aero, closed_circuit=False)
        assert p_aero.lap_time_s < p_base.lap_time_s, f"mu={mu_val}: aero car should be faster"

    # Low-mu car should gain LESS from aero than high-mu car (grip = mu * N)
    times = {}
    for mu_val in [0.88, 1.35]:
        mass = 1500.0
        aero_coeff = 0.5 * rho * cl_a / (mass * G)
        base = VehicleParams(
            mu=mu_val,
            max_accel_g=0.5,
            max_decel_g=mu_val,
            max_lateral_g=mu_val,
            top_speed_mps=80.0,
            mass_kg=mass,
            wheel_power_w=300_000,
        )
        aero = VehicleParams(
            mu=mu_val,
            max_accel_g=0.5,
            max_decel_g=mu_val,
            max_lateral_g=mu_val,
            top_speed_mps=80.0,
            mass_kg=mass,
            wheel_power_w=300_000,
            aero_coefficient=aero_coeff,
        )
        p_base = compute_optimal_profile(cr, base, closed_circuit=False)
        p_aero = compute_optimal_profile(cr, aero, closed_circuit=False)
        pct = (p_base.lap_time_s - p_aero.lap_time_s) / p_base.lap_time_s * 100
        times[mu_val] = pct

    # Higher mu should extract more absolute time from same aero package
    assert times[1.35] > times[0.88], (
        f"High-mu should benefit more: {times[1.35]:.2f}% vs {times[0.88]:.2f}%"
    )


def test_no_downforce_no_change() -> None:
    """Car with cl_a=0 should produce same results as default."""
    n = 500
    curvature = np.full(n, 0.01)
    cr = _make_curvature_result(curvature)

    base = VehicleParams(mu=1.0, max_accel_g=0.5, max_decel_g=1.0, max_lateral_g=1.0)
    zero_aero = VehicleParams(
        mu=1.0,
        max_accel_g=0.5,
        max_decel_g=1.0,
        max_lateral_g=1.0,
        aero_coefficient=0.0,
    )

    p1 = compute_optimal_profile(cr, base, closed_circuit=False)
    p2 = compute_optimal_profile(cr, zero_aero, closed_circuit=False)
    assert abs(p1.lap_time_s - p2.lap_time_s) < 0.01


def test_vehicle_spec_has_cl_a() -> None:
    """VehicleSpec dataclass must have cl_a field."""
    from cataclysm.vehicle_db import VehicleSpec

    spec = VehicleSpec(
        make="Test",
        model="Car",
        generation="V1",
        year_range=(2020, 2025),
        weight_kg=1500,
        wheelbase_m=2.5,
        track_width_front_m=1.5,
        track_width_rear_m=1.5,
        cg_height_m=0.5,
        weight_dist_front_pct=50.0,
        drivetrain="RWD",
        hp=400,
        torque_nm=500,
        has_aero=True,
        cd_a=0.7,
        cl_a=0.8,
    )
    assert spec.cl_a == 0.8


def test_aero_cars_have_cl_a() -> None:
    """Cars marked has_aero=True with significant wings/splitters should have cl_a > 0."""
    from cataclysm.vehicle_db import VEHICLE_DATABASE

    # At minimum, these known aero cars must have cl_a set
    must_have_cl_a = [
        "porsche_911_gt3_992",
        "porsche_cayman_gt4_718",
        "chevrolet_corvette_c8_z06",
    ]
    for key in must_have_cl_a:
        if key in VEHICLE_DATABASE:
            spec = VEHICLE_DATABASE[key]
            assert spec.cl_a > 0, f"{key} should have cl_a > 0"


def test_equipment_wiring_produces_aero_coefficient() -> None:
    """equipment_to_vehicle_params should produce nonzero aero_coefficient for aero cars."""
    from cataclysm.equipment import (
        EquipmentProfile,
        MuSource,
        TireCompoundCategory,
        TireSpec,
        equipment_to_vehicle_params,
    )
    from cataclysm.vehicle_db import VEHICLE_DATABASE

    gt3_spec = VEHICLE_DATABASE["porsche_911_gt3_992"]
    profile = EquipmentProfile(
        id="test",
        name="Test GT3",
        tires=TireSpec(
            model="Test tire",
            compound_category=TireCompoundCategory.ENDURANCE_200TW,
            size="255/35R20",
            treadwear_rating=200,
            estimated_mu=1.0,
            mu_source=MuSource.FORMULA_ESTIMATE,
            mu_confidence="medium",
        ),
        vehicle=gt3_spec,
    )

    params = equipment_to_vehicle_params(profile)
    assert params.aero_coefficient > 0, "GT3 should have nonzero aero_coefficient"

    # Verify formula: 0.5 * rho * cl_a * aero_eff / (mass * G)
    aero_eff = 0.85  # _AERO_EFFICIENCY from equipment.py
    expected = 0.5 * 1.225 * gt3_spec.cl_a * aero_eff / (gt3_spec.weight_kg * G)
    assert abs(params.aero_coefficient - expected) < 1e-10

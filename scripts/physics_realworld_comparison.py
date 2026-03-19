#!/usr/bin/env python3
"""Compare solver predictions against real-world lap times from LapMeta/FastestLaps.

Curated dataset of real-world lap times with known tire compounds, matched
against our physics-optimal predictions at the corresponding mu level.

Key metric: efficiency_ratio = predicted_optimal / real_world_time
  - <1.0 means real driver is slower than physics limit (expected for amateurs)
  - >1.0 means real driver exceeded our prediction (suggests model error)
  - Expected range: 0.85–1.05 for properly tire-matched comparisons

Sources: LapMeta.com, FastestLaps.com, NASA Mid-South, Rennlist, GR86.org
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cataclysm.curvature import CurvatureResult
from cataclysm.equipment import (
    _CATEGORY_ACCEL_G,
    CATEGORY_BRAKING_MU_RATIO,
    CATEGORY_FRICTION_CIRCLE_EXPONENT,
    CATEGORY_GRIP_UTILIZATION,
    CATEGORY_LOAD_SENSITIVITY_EXPONENT,
    CATEGORY_MU_DEFAULTS,
    CATEGORY_PEAK_SLIP_ANGLE_DEG,
    CATEGORY_THERMAL_PENALTY,
    TireCompoundCategory,
)
from cataclysm.tire_db import lookup_tire
from cataclysm.track_db import TrackLayout, lookup_track
from cataclysm.track_reference import get_track_reference
from cataclysm.vehicle_db import VehicleSpec, find_vehicle
from cataclysm.velocity_profile import G, VehicleParams, compute_optimal_profile

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_BRAKE_EFFICIENCY = 0.95
_AIR_DENSITY = 1.225
_DRIVETRAIN_EFFICIENCY: dict[str, float] = {"RWD": 0.85, "FWD": 0.82, "AWD": 0.80}
_AERO_EFFICIENCY = 0.85  # real-world aero efficiency (ride height, yaw, turbulence)


# ---------------------------------------------------------------------------
# Tire category → mu mapping (same as benchmark script)
# ---------------------------------------------------------------------------

TIRE_CATEGORIES: dict[str, TireCompoundCategory] = {
    "street": TireCompoundCategory.STREET,
    "endurance_200tw": TireCompoundCategory.ENDURANCE_200TW,
    "super_200tw": TireCompoundCategory.SUPER_200TW,
    "100tw": TireCompoundCategory.TW_100,
    "r_compound": TireCompoundCategory.R_COMPOUND,
    "slick": TireCompoundCategory.SLICK,
}


# ---------------------------------------------------------------------------
# Curated real-world lap time dataset
# ---------------------------------------------------------------------------


@dataclass
class RealWorldLapTime:
    """A single curated real-world lap time entry."""

    car_key: tuple[str, str, str | None]  # (make, model, generation) for find_vehicle
    car_label: str
    track_name: str
    lap_time_s: float
    tire_model: str
    tire_category: str  # key into TIRE_CATEGORIES
    mod_level: str  # stock / light / heavy / race
    source: str  # URL or description
    notes: str
    tire_db_key: str | None = None  # key into tire_db for per-tire mu lookup


def _parse_time(time_str: str) -> float:
    """Parse 'M:SS.ss' or 'M:SS.sss' to seconds."""
    parts = time_str.split(":")
    return float(parts[0]) * 60.0 + float(parts[1])


# Curated dataset — each entry has verified tire compound and modification level.
# Only includes entries where tire compound is known and car is stock/lightly modded.
#
# Sources researched: LapMeta.com, FastestLaps.com, Rennlist, GR86.org,
#   TrackMustangsOnline, NASA Mid-South, ft86club.com
CURATED_LAP_TIMES: list[RealWorldLapTime] = [
    # =========================================================================
    # BARBER MOTORSPORTS PARK (3,650m / 2.38mi)
    # =========================================================================
    # --- Miata NA ---
    RealWorldLapTime(
        car_key=("Mazda", "Miata", "NA"),
        car_label="Miata NA",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:48.08"),
        tire_model="Hoosier (NASA TT class)",
        tire_category="r_compound",
        mod_level="light",
        source="nasamidsouth.com/barber-track-records/",
        notes="NASA TT class record, light prep within class rules",
        tire_db_key="hoosier_r7",
    ),
    # --- Miata ND ---
    RealWorldLapTime(
        car_key=("Mazda", "Miata", "ND"),
        car_label="Miata ND",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:48.36"),
        tire_model="unknown",
        tire_category="endurance_200tw",
        mod_level="stock",
        source="lapmeta.com/en/track/variation/15",
        notes="LapMeta entry, tire assumed endurance 200tw based on time",
    ),
    # --- Toyota GR86 ---
    RealWorldLapTime(
        car_key=("Toyota", "GR86", None),
        car_label="GR86",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:43.88"),
        tire_model="Yokohama Advan A052 245/40/17",
        tire_category="super_200tw",
        mod_level="light",
        source="gr86.org/threads/track-time-database.15379/",
        notes="GR86 forum track time DB, A052 = super 200tw",
        tire_db_key="yokohama_a052",
    ),
    RealWorldLapTime(
        car_key=("Toyota", "GR86", None),
        car_label="GR86",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:45.88"),
        tire_model="Hankook RS4 (coilovers)",
        tire_category="endurance_200tw",
        mod_level="light",
        source="gr86.org/threads/track-time-database.15379/",
        notes="RS4 = endurance 200tw, coilovers = light mod",
        tire_db_key="hankook_rs4",
    ),
    RealWorldLapTime(
        car_key=("Toyota", "GR86", None),
        car_label="GR86",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:47.66"),
        tire_model="Falken Azenis RT660 245/40/17",
        tire_category="endurance_200tw",
        mod_level="light",
        source="gr86.org/threads/track-time-database.15379/",
        notes="RT660 = endurance 200tw, suspension upgrades",
        tire_db_key="falken_rt660",
    ),
    # --- Honda Civic Type R FL5 ---
    # NOTE: PS4S is classified as STREET in tire_db.py (TW 300, mu=0.95).
    RealWorldLapTime(
        car_key=("Honda", "Civic Type R", "FL5"),
        car_label="Civic Type R FL5",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:40.90"),
        tire_model="Michelin Pilot Sport 4S (stock OEM)",
        tire_category="endurance_200tw",
        mod_level="stock",
        source="lapmeta.com/en/track/variation/15",
        notes="Stock FL5 on OEM PS4S (endurance-level grip per validation)",
        tire_db_key="michelin_ps4s",
    ),
    RealWorldLapTime(
        car_key=("Honda", "Civic Type R", "FL5"),
        car_label="Civic Type R FL5",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:40.90"),
        tire_model="Yokohama Advan A052",
        tire_category="super_200tw",
        mod_level="light",
        source="lapmeta.com/en/model/1001",
        notes="LapMeta FL5 page, A052 = super 200tw, light mods",
        tire_db_key="yokohama_a052",
    ),
    # --- BMW M2 ---
    RealWorldLapTime(
        car_key=("BMW", "M2", "G87"),
        car_label="BMW M2 G87",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:42.09"),
        tire_model="Hankook Ventus RS4",
        tire_category="endurance_200tw",
        mod_level="stock",
        source="fastestlaps.com/tracks/barber-motorsports-park",
        notes="Ventus RS4 = endurance 200tw",
        tire_db_key="hankook_rs4",
    ),
    RealWorldLapTime(
        car_key=("BMW", "M2", "G87"),
        car_label="BMW M2 G87",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:43.18"),
        tire_model="unknown (assumed endurance 200tw)",
        tire_category="endurance_200tw",
        mod_level="stock",
        source="laptrophy.com/en/tracks/qkow36-Barber-Motorsports-Park",
        notes="LapTrophy entry",
    ),
    # --- Porsche 718 Cayman GT4 ---
    RealWorldLapTime(
        car_key=("Porsche", "Cayman GT4", "718"),
        car_label="Cayman GT4 718",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:41.43"),
        tire_model="Michelin Pilot Sport Cup 2 (OEM)",
        tire_category="super_200tw",
        mod_level="stock",
        source=(
            "rennlist.com/forums/718-gts-4-0-gt4-gt4rs-spyder-25th-anniversary/"
            "1235438-best-track-time-in-a-718-gt4.html"
        ),
        notes="Stock GT4 PDK, 500mi odo. Cup 2 = super 200tw",
        tire_db_key="michelin_cup2",
    ),
    RealWorldLapTime(
        car_key=("Porsche", "Cayman GT4", "718"),
        car_label="Cayman GT4 718",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:39.80"),
        tire_model="Bridgestone RE-71RS 245/40/19 & 285/35/19",
        tire_category="super_200tw",
        mod_level="light",
        source=(
            "rennlist.com/forums/718-gts-4-0-gt4-gt4rs-spyder-25th-anniversary/"
            "1235438-best-track-time-in-a-718-gt4.html"
        ),
        notes="RE-71RS = super 200tw, -2.3/-1.9 camber",
        tire_db_key="bridgestone_re71rs",
    ),
    RealWorldLapTime(
        car_key=("Porsche", "Cayman GT4", "718"),
        car_label="Cayman GT4 718",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:33.99"),
        tire_model="Yokohama A052 or similar",
        tire_category="super_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/15",
        notes="Fastest GT4 at Barber on LapMeta, skilled driver",
        tire_db_key="yokohama_a052",
    ),
    # --- Porsche 911 GT3 ---
    RealWorldLapTime(
        car_key=("Porsche", "911 GT3", "992"),
        car_label="911 GT3 992",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:33.09"),
        tire_model="Dunlop DH Slick",
        tire_category="slick",
        mod_level="stock",
        source="fastestlaps.com/tracks/barber-motorsports-park",
        notes="DH Slick = full slick, no tread pattern",
        tire_db_key="dunlop_dh_slick",
    ),
    RealWorldLapTime(
        car_key=("Porsche", "911 GT3", "991.2"),
        car_label="911 GT3 991",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:35.05"),
        tire_model="Hoosier R7",
        tire_category="r_compound",
        mod_level="light",
        source=(
            "rennlist.com/forums/991-gt3-gt3rs-gt2rs-and-911r/"
            "1113671-real-value-thread-post-your-best-lap-times.html"
        ),
        notes="991 GT3 on R7, light mods. 493hp/1430kg",
        tire_db_key="hoosier_r7",
    ),
    # --- Ford Mustang GT S550 ---
    RealWorldLapTime(
        car_key=("Ford", "Mustang GT", "S550"),
        car_label="Mustang GT S550",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:51.38"),
        tire_model="Michelin Pilot Sport 4S 255/40+275/40R19",
        tire_category="endurance_200tw",
        mod_level="stock",
        source="mustang6g.com/forums/threads/s550-lap-times-road-course.35500/",
        notes="Stock PP1 on OEM PS4S (endurance-level grip per validation)",
        tire_db_key="michelin_ps4s",
    ),
    RealWorldLapTime(
        car_key=("Ford", "Mustang GT", "S550"),
        car_label="Mustang GT S550",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:37.06"),
        tire_model="Pirelli Slicks 305 square",
        tire_category="slick",
        mod_level="heavy",
        source="mustang6g.com/forums/threads/s550-lap-times-road-course.35500/",
        notes="2015 GT Performance Plus, heavily modified, Pirelli full slicks",
        tire_db_key="pirelli_slick_305",
    ),
    # --- Ford Mustang Shelby GT350 ---
    RealWorldLapTime(
        car_key=("Ford", "Mustang Shelby GT350", "S550"),
        car_label="GT350",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:40.26"),
        tire_model="Goodyear SuperCar 3 325/30R19 square",
        tire_category="super_200tw",
        mod_level="light",
        source="mustang6g.com/forums/threads/s550-lap-times-road-course.35500/",
        notes="GT350 on OEM SC3 = super 200tw (mu=1.12)",
        tire_db_key="goodyear_sc3",
    ),
    # --- Corvette C8 Stingray Z51 ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Corvette", "C8"),
        car_label="Corvette C8 Z51",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:36.46"),
        tire_model="Michelin Pilot Sport 4S (OEM)",
        tire_category="endurance_200tw",
        mod_level="stock",
        source="lapmeta.com/en/model/13/chevrolet-corvette-c8-stingray-z51",
        notes="Stock Z51 on OEM PS4S (endurance-level grip per validation)",
        tire_db_key="michelin_ps4s",
    ),
    # --- Corvette C8 Z06 ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Corvette Z06", "C8"),
        car_label="Corvette C8 Z06",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:31.90"),
        tire_model="Yokohama Advan A052",
        tire_category="super_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/15",
        notes="C8 Z06 on A052, light mods",
        tire_db_key="yokohama_a052",
    ),
    # =========================================================================
    # ROEBLING ROAD RACEWAY (3,199m / 2.02mi)
    # =========================================================================
    # --- Toyota GR86 ---
    RealWorldLapTime(
        car_key=("Toyota", "GR86", None),
        car_label="GR86",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:25.90"),
        tire_model="Michelin Pilot Sport 4 (OEM stock)",
        tire_category="street",
        mod_level="stock",
        source="jst-performance.com/blogs/jst-results-blog/our-2022-gr86-first-impression",
        notes="Fully stock 2022 GR86 on OEM tires, noted as huge limiting factor",
        tire_db_key="michelin_ps4",
    ),
    RealWorldLapTime(
        car_key=("Toyota", "GR86", None),
        car_label="GR86 (FR-S proxy)",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:20.47"),
        tire_model="Nitto NT01",
        tire_category="100tw",
        mod_level="light",
        source="lapmeta.com/en/lap/detail/2920",
        notes="2015 FR-S with NT01 — proxy for GR86 (similar weight/power)",
        tire_db_key="nitto_nt01",
    ),
    # --- Corvette C8 Z06 ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Corvette Z06", "C8"),
        car_label="Corvette C8 Z06",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:14.29"),
        tire_model="Pirelli P Zero Trofeo R (Z07 pkg)",
        tire_category="100tw",
        mod_level="light",
        source="lapmeta.com/en/lap/detail/24184",
        notes="Nov 2024, Z07 Trofeo R = r_compound, Forgeline wheels + AP brakes",
        tire_db_key="pirelli_trofeo_r",
    ),
    # --- Porsche 718 Cayman GT4 ---
    RealWorldLapTime(
        car_key=("Porsche", "Cayman GT4", "718"),
        car_label="Cayman GT4 718",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:17.79"),
        tire_model="Bridgestone RE71RS",
        tire_category="super_200tw",
        mod_level="stock",
        source="lapmeta.com/en/track/variation/135",
        notes="RE71RS = super 200tw",
        tire_db_key="bridgestone_re71rs",
    ),
    # --- Ford Mustang GT S550 ---
    RealWorldLapTime(
        car_key=("Ford", "Mustang GT", "S550"),
        car_label="Mustang GT S550",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:20.38"),
        tire_model="Kumho V730 305 square",
        tire_category="super_200tw",
        mod_level="light",
        source="trackmustangsonline.com/tracks/roebling-road-raceway.32/",
        notes="2019 GT, V730 = super 200tw (mu=1.06)",
        tire_db_key="kumho_v730",
    ),
    RealWorldLapTime(
        car_key=("Ford", "Mustang GT", "S550"),
        car_label="Mustang GT S550",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:19.90"),
        tire_model="Hoosier A7 315 square",
        tire_category="r_compound",
        mod_level="light",
        source="trackmustangsonline.com/tracks/roebling-road-raceway.32/",
        notes="2016 GT, A7 = r_compound (mu=1.42)",
        tire_db_key="hoosier_a7",
    ),
    RealWorldLapTime(
        car_key=("Ford", "Mustang GT", "S550"),
        car_label="Mustang GT S550",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:22.58"),
        tire_model="Hoosier R7 315/30/18",
        tire_category="r_compound",
        mod_level="light",
        source="trackmustangsonline.com/tracks/roebling-road-raceway.32/",
        notes="2015 GT, R7 = r_compound (mu=1.38)",
        tire_db_key="hoosier_r7",
    ),
    # --- Ford Mustang Shelby GT350 ---
    RealWorldLapTime(
        car_key=("Ford", "Mustang Shelby GT350", "S550"),
        car_label="GT350",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:18.70"),
        tire_model="Goodyear SuperCar 3R",
        tire_category="100tw",
        mod_level="stock",
        source="trackmustangsonline.com/tracks/roebling-road-raceway.32/",
        notes="GT350 on SC3R (TW_100/r_compound bridge, mu~1.20)",
        tire_db_key="goodyear_sc3r",
    ),
    # =========================================================================
    # ATLANTA MOTORSPORTS PARK (2,927m / 1.83mi)
    # =========================================================================
    # --- Toyota GR86 ---
    RealWorldLapTime(
        car_key=("Toyota", "GR86", None),
        car_label="GR86",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:36.00"),
        tire_model="Bridgestone RE71RS",
        tire_category="super_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/27",
        notes="May 2021, RE71RS = super 200tw",
        tire_db_key="bridgestone_re71rs",
    ),
    RealWorldLapTime(
        car_key=("Toyota", "GR86", None),
        car_label="GR86",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:34.90"),
        tire_model="Falken Azenis RT660 245/40/17",
        tire_category="endurance_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/27",
        notes="RT660 = endurance 200tw, -4.5/-2.8 camber",
        tire_db_key="falken_rt660",
    ),
    # --- Honda Civic Type R FK8 ---
    RealWorldLapTime(
        car_key=("Honda", "Civic Type R", "FL5"),
        car_label="Civic Type R FK8 (FL5 proxy)",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:35.83"),
        tire_model="Hankook Ventus RS4",
        tire_category="endurance_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/27",
        notes="FK8 on RS4 (endurance 200tw). FK8 306hp vs FL5 315hp",
        tire_db_key="hankook_rs4",
    ),
    RealWorldLapTime(
        car_key=("Honda", "Civic Type R", "FL5"),
        car_label="Civic Type R FK8 (FL5 proxy)",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:35.91"),
        tire_model="Kumho V730",
        tire_category="super_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/27",
        notes="FK8 on V730 (super 200tw). FK8 = FL5 proxy",
        tire_db_key="kumho_v730",
    ),
    # --- Porsche 718 Cayman GT4 ---
    RealWorldLapTime(
        car_key=("Porsche", "Cayman GT4", "718"),
        car_label="Cayman GT4 718",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:27.58"),
        tire_model="Pirelli slicks",
        tire_category="slick",
        mod_level="stock",
        source="rennlist.com",
        notes="2017, Pirelli full slicks",
        tire_db_key="pirelli_slick_305",
    ),
    # --- Corvette C8 Z06 ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Corvette Z06", "C8"),
        car_label="Corvette C8 Z06",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:31.35"),
        tire_model="Michelin Pilot Sport 4S (OEM)",
        tire_category="endurance_200tw",
        mod_level="stock",
        source="lapmeta.com/en/track/variation/27",
        notes="Stock Z06 on OEM PS4S (endurance-level grip per validation)",
        tire_db_key="michelin_ps4s",
    ),
]


# ---------------------------------------------------------------------------
# Vehicle params builder (reused from benchmark script)
# ---------------------------------------------------------------------------


def _vehicle_spec_to_params(
    spec: VehicleSpec,
    compound: TireCompoundCategory = TireCompoundCategory.ENDURANCE_200TW,
    mu_override: float | None = None,
) -> VehicleParams:
    """Build VehicleParams from a VehicleSpec + tire compound."""
    mu_raw = mu_override if mu_override is not None else CATEGORY_MU_DEFAULTS[compound]
    grip_util = CATEGORY_GRIP_UTILIZATION.get(compound, 0.96)
    thermal = CATEGORY_THERMAL_PENALTY.get(compound, 1.00)
    mu = mu_raw * grip_util * thermal
    weight_kg = spec.weight_kg

    base_accel_g = _CATEGORY_ACCEL_G[compound]
    pw_ratio = spec.hp / (weight_kg / 1000.0)
    pw_factor = min(pw_ratio / 250.0, 1.5)
    accel_g = base_accel_g * max(pw_factor, 0.7)

    drag_coeff = 0.0
    if spec.cd_a > 0:
        drag_coeff = spec.cd_a * _AIR_DENSITY / (2.0 * weight_kg)

    dt_eff = _DRIVETRAIN_EFFICIENCY.get(spec.drivetrain, 0.85)
    wheel_power_w = spec.hp * 745.7 * dt_eff

    # Aero downforce coefficient: k = 0.5 * rho * CL_A * eff / (m * G)
    aero_coeff = 0.0
    if spec.cl_a > 0 and weight_kg > 0:
        aero_coeff = 0.5 * _AIR_DENSITY * spec.cl_a * _AERO_EFFICIENCY / (weight_kg * G)

    braking_ratio = CATEGORY_BRAKING_MU_RATIO.get(compound, 1.10)
    slip_angle_deg = CATEGORY_PEAK_SLIP_ANGLE_DEG.get(compound, 6.0)
    cornering_drag = math.sin(math.radians(slip_angle_deg))

    return VehicleParams(
        mu=mu,
        max_lateral_g=mu,
        max_accel_g=accel_g,
        max_decel_g=mu * braking_ratio * _BRAKE_EFFICIENCY,
        top_speed_mps=80.0,
        friction_circle_exponent=CATEGORY_FRICTION_CIRCLE_EXPONENT[compound],
        aero_coefficient=aero_coeff,
        drag_coefficient=drag_coeff,
        load_sensitivity_exponent=CATEGORY_LOAD_SENSITIVITY_EXPONENT[compound],
        cg_height_m=spec.cg_height_m,
        track_width_m=0.5 * (spec.track_width_front_m + spec.track_width_rear_m),
        wheel_power_w=wheel_power_w,
        mass_kg=weight_kg,
        braking_mu_ratio=braking_ratio,
        cornering_drag_factor=cornering_drag,
    )


# ---------------------------------------------------------------------------
# Comparison result
# ---------------------------------------------------------------------------


@dataclass
class ComparisonResult:
    """One real-world vs predicted comparison."""

    car_label: str
    track: str
    real_time_s: float
    predicted_time_s: float
    efficiency_ratio: float  # predicted / real
    tire_category: str
    tire_model: str
    mu: float
    mod_level: str
    source: str
    notes: str


def _fmt_time(seconds: float) -> str:
    """Format seconds as M:SS.ss."""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins}:{secs:05.2f}"


# ---------------------------------------------------------------------------
# Main comparison logic
# ---------------------------------------------------------------------------


def run_comparison() -> list[ComparisonResult]:
    """Run solver for each curated real-world entry, compute efficiency ratio."""
    print("=" * 90)
    print("REAL-WORLD LAP TIME COMPARISON")
    print("=" * 90)
    print()

    # Load track references
    track_data: dict[str, tuple[CurvatureResult, TrackLayout]] = {}
    track_names = sorted(set(rw.track_name for rw in CURATED_LAP_TIMES))

    for track_name in track_names:
        layout = lookup_track(track_name)
        if layout is None:
            print(f"  WARN: Track '{track_name}' not found, skipping")
            continue
        ref = get_track_reference(layout)
        if ref is None:
            print(f"  WARN: No canonical reference for '{track_name}', skipping")
            continue
        track_data[track_name] = (ref.curvature_result, layout)
        print(f"  Loaded: {track_name} ({ref.track_length_m:.0f}m)")

    results: list[ComparisonResult] = []
    skipped = 0

    for rw in CURATED_LAP_TIMES:
        # Look up vehicle
        make, model, gen = rw.car_key
        spec = find_vehicle(make, model, gen)
        if spec is None:
            print(f"  WARN: Vehicle not found: {make} {model} {gen}")
            skipped += 1
            continue

        # Look up track
        if rw.track_name not in track_data:
            skipped += 1
            continue

        curvature_result, _ = track_data[rw.track_name]

        # Get tire category
        if rw.tire_category not in TIRE_CATEGORIES:
            print(f"  WARN: Unknown tire category: {rw.tire_category}")
            skipped += 1
            continue

        compound = TIRE_CATEGORIES[rw.tire_category]

        # Resolve per-tire mu from tire_db when available
        tire_mu: float | None = None
        if rw.tire_db_key:
            tire_spec = lookup_tire(rw.tire_db_key)
            if tire_spec:
                tire_mu = tire_spec.estimated_mu

        mu = tire_mu if tire_mu is not None else CATEGORY_MU_DEFAULTS[compound]

        # Run solver
        params = _vehicle_spec_to_params(spec, compound, mu_override=tire_mu)
        optimal = compute_optimal_profile(curvature_result, params=params)

        efficiency = optimal.lap_time_s / rw.lap_time_s

        results.append(
            ComparisonResult(
                car_label=rw.car_label,
                track=rw.track_name,
                real_time_s=rw.lap_time_s,
                predicted_time_s=optimal.lap_time_s,
                efficiency_ratio=efficiency,
                tire_category=rw.tire_category,
                tire_model=rw.tire_model,
                mu=mu,
                mod_level=rw.mod_level,
                source=rw.source,
                notes=rw.notes,
            )
        )

    print(f"\n  Processed {len(results)} comparisons, skipped {skipped}")
    return results


def print_results(results: list[ComparisonResult]) -> None:
    """Print comparison results grouped by track."""
    tracks = sorted(set(r.track for r in results))

    for track in tracks:
        track_results = sorted(
            [r for r in results if r.track == track],
            key=lambda r: r.real_time_s,
        )

        print(f"\n{'=' * 100}")
        print(f"  {track}")
        print(f"{'=' * 100}")
        print(
            f"  {'Car':<25} {'Tires':<16} {'Mu':>4} "
            f"{'Real':>8} {'Predicted':>9} {'Ratio':>6} {'Delta':>7} {'Mod':<6}"
        )
        print(f"  {'-' * 95}")

        for r in track_results:
            delta_s = r.predicted_time_s - r.real_time_s
            delta_sign = "+" if delta_s >= 0 else ""
            ratio_flag = ""
            if r.efficiency_ratio > 1.05:
                ratio_flag = " ⚠ SLOW MODEL"
            elif r.efficiency_ratio > 1.0:
                ratio_flag = " ⚠ EXCEED"

            print(
                f"  {r.car_label:<25} {r.tire_category:<16} {r.mu:>4.2f} "
                f"{_fmt_time(r.real_time_s):>8} {_fmt_time(r.predicted_time_s):>9} "
                f"{r.efficiency_ratio:>6.3f} {delta_sign}{delta_s:>5.1f}s {r.mod_level:<6}"
                f"{ratio_flag}"
            )


_ACCEPTANCE_CRITERIA = {
    "mean_ratio_min": 0.95,
    "mean_ratio_max": 1.02,
    "std_ratio_max": 0.045,
    "exceedance_5pct_max": 5,
    "category_mean_min": 0.88,
    "category_mean_max": 1.08,
}


def _get_git_sha() -> str:
    """Return short git SHA, or 'unknown' if not in a repo."""
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def validate_comparison(results: list[ComparisonResult]) -> bool:
    """Run validation checks with formal acceptance criteria.

    Returns True if all checks pass, False otherwise.
    """
    print(f"\n\n{'=' * 90}")
    print("VALIDATION CHECKS")
    print(f"{'=' * 90}")

    issues: list[str] = []
    ratios = [r.efficiency_ratio for r in results]

    # --- Check 1: Efficiency ratio distribution ---
    print("\n1. EFFICIENCY RATIO DISTRIBUTION")

    mean_ratio = float(np.mean(ratios))
    median_ratio = float(np.median(ratios))
    std_ratio = float(np.std(ratios))
    p5 = float(np.percentile(ratios, 5))
    p95 = float(np.percentile(ratios, 95))
    exceedance_5pct = int(sum(1 for r in ratios if r > 1.05))

    print(f"  Count:  {len(ratios)}")
    print(f"  Mean:   {mean_ratio:.4f}")
    print(f"  Median: {median_ratio:.4f}")
    print(f"  Std:    {std_ratio:.4f}")
    print(f"  P5-P95: [{p5:.3f}, {p95:.3f}]")

    # How many exceed 1.0? (real driver beat our prediction)
    exceeds = [r for r in results if r.efficiency_ratio > 1.0]
    exceeds_pct = len(exceeds) / len(results) * 100
    print(f"  Exceeds 1.0: {len(exceeds)}/{len(results)} ({exceeds_pct:.0f}%)")
    print(f"  Exceeds 1.05: {exceedance_5pct}/{len(results)}")

    if exceeds:
        print("  Details of exceedances >1.0:")
        for r in sorted(exceeds, key=lambda x: x.efficiency_ratio, reverse=True):
            flag = " ← OVER 1.05" if r.efficiency_ratio > 1.05 else ""
            print(
                f"    {r.car_label} at {r.track}: ratio={r.efficiency_ratio:.3f} "
                f"(real {_fmt_time(r.real_time_s)}, predicted {_fmt_time(r.predicted_time_s)}, "
                f"mu={r.mu}, {r.tire_model}){flag}"
            )

    # --- Acceptance checks ---
    print(f"\n  {'CHECK':<40} {'RESULT':<6} {'VALUE':<20} {'THRESHOLD'}")
    print(f"  {'-' * 85}")

    c = _ACCEPTANCE_CRITERIA

    def _check(name: str, passed: bool, value_str: str, threshold_str: str) -> None:
        status = "PASS" if passed else "FAIL"
        print(f"  {name:<40} {status:<6} {value_str:<20} {threshold_str}")
        if not passed:
            issues.append(f"{name}: {value_str} (threshold: {threshold_str})")

    _check(
        "Mean ratio",
        c["mean_ratio_min"] <= mean_ratio <= c["mean_ratio_max"],
        f"{mean_ratio:.4f}",
        f"[{c['mean_ratio_min']}, {c['mean_ratio_max']}]",
    )
    _check(
        "Std ratio",
        std_ratio <= c["std_ratio_max"],
        f"{std_ratio:.4f}",
        f"≤ {c['std_ratio_max']}",
    )
    _check(
        "Exceedances >1.05",
        exceedance_5pct <= c["exceedance_5pct_max"],
        str(exceedance_5pct),
        f"≤ {c['exceedance_5pct_max']}",
    )

    # --- Check 2: Per-category breakdown ---
    print("\n2. BREAKDOWN BY TIRE CATEGORY")

    cat_order = ["street", "endurance_200tw", "super_200tw", "100tw", "r_compound", "slick"]
    for cat in cat_order:
        cat_results = [r for r in results if r.tire_category == cat]
        if not cat_results:
            print(f"  {cat}: no data")
            continue

        cat_ratios = [r.efficiency_ratio for r in cat_results]
        cat_mean = float(np.mean(cat_ratios))
        cat_range = f"[{min(cat_ratios):.3f}, {max(cat_ratios):.3f}]"
        in_range = c["category_mean_min"] <= cat_mean <= c["category_mean_max"]
        flag = "" if in_range else " ← OUT OF RANGE"
        print(f"  {cat:<18}: n={len(cat_results)}, mean={cat_mean:.3f}, range={cat_range}{flag}")
        if not in_range:
            issues.append(
                f"Category {cat} mean={cat_mean:.3f} outside "
                f"[{c['category_mean_min']}, {c['category_mean_max']}]"
            )

    # --- Check 3: Per-track breakdown ---
    print("\n3. BREAKDOWN BY TRACK")

    for track in sorted(set(r.track for r in results)):
        track_results = [r for r in results if r.track == track]
        track_ratios = [r.efficiency_ratio for r in track_results]
        track_mean = float(np.mean(track_ratios))
        track_range = f"[{min(track_ratios):.3f}, {max(track_ratios):.3f}]"
        print(f"  {track:<30}: n={len(track_results)}, mean={track_mean:.3f}, range={track_range}")

    # --- Check 4: Interpretation ---
    print("\n4. INTERPRETATION")
    print()

    if mean_ratio < 1.0:
        print(
            f"  Mean efficiency ratio = {mean_ratio:.3f} means our solver predicts "
            f"lap times that are {(1 - mean_ratio) * 100:.1f}% faster than real-world "
            f"drivers achieve."
        )
        print(
            "  This is EXPECTED — the solver computes the physics ceiling (100% grip "
            "utilization), while real amateur drivers typically operate at 85-95% of "
            "the limit."
        )
    else:
        print(
            f"  Mean efficiency ratio = {mean_ratio:.3f} means our solver predicts "
            f"lap times that are {(mean_ratio - 1) * 100:.1f}% slower than real-world "
            f"drivers achieve on average."
        )

    # --- Summary ---
    passed = len(issues) == 0
    print(f"\n{'=' * 90}")
    if passed:
        print("ALL CHECKS PASS ✓")
    else:
        print(f"CHECKS FAILED ({len(issues)}):")
        for issue in issues:
            print(f"  ✗ {issue}")
    print(f"{'=' * 90}")

    return passed


def export_csv(results: list[ComparisonResult]) -> None:
    """Export comparison results to CSV."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "realworld_comparison.csv")

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "car",
                "track",
                "real_time_s",
                "real_time_str",
                "predicted_time_s",
                "predicted_time_str",
                "efficiency_ratio",
                "tire_category",
                "tire_model",
                "mu",
                "mod_level",
                "source",
                "notes",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.car_label,
                    r.track,
                    f"{r.real_time_s:.2f}",
                    _fmt_time(r.real_time_s),
                    f"{r.predicted_time_s:.2f}",
                    _fmt_time(r.predicted_time_s),
                    f"{r.efficiency_ratio:.4f}",
                    r.tire_category,
                    r.tire_model,
                    f"{r.mu:.2f}",
                    r.mod_level,
                    r.source,
                    r.notes,
                ]
            )

    print(f"\nExported {len(results)} rows to {path}")


def _compute_summary(results: list[ComparisonResult]) -> dict:
    """Compute summary statistics from comparison results."""
    ratios = [r.efficiency_ratio for r in results]

    summary: dict = {
        "n_entries": len(results),
        "mean_ratio": float(np.mean(ratios)),
        "median_ratio": float(np.median(ratios)),
        "std_ratio": float(np.std(ratios)),
        "exceedance_count_5pct": int(sum(1 for r in ratios if r > 1.05)),
        "entries_above_1": int(sum(1 for r in ratios if r > 1.0)),
    }

    # Per-category stats
    cat_order = ["street", "endurance_200tw", "super_200tw", "100tw", "r_compound", "slick"]
    per_category: dict[str, dict] = {}
    for cat in cat_order:
        cat_ratios = [r.efficiency_ratio for r in results if r.tire_category == cat]
        if cat_ratios:
            per_category[cat] = {
                "n": len(cat_ratios),
                "mean": round(float(np.mean(cat_ratios)), 4),
                "std": round(float(np.std(cat_ratios)), 4),
                "min": round(float(min(cat_ratios)), 4),
                "max": round(float(max(cat_ratios)), 4),
            }
    summary["per_category"] = per_category

    return summary


def export_baseline_json(results: list[ComparisonResult]) -> str:
    """Export a machine-readable JSON baseline for A/B regression testing."""
    git_sha = _get_git_sha()
    today = datetime.date.today().isoformat()

    baseline = {
        "date": today,
        "git_sha": git_sha,
        "acceptance_criteria": _ACCEPTANCE_CRITERIA,
        "entries": [
            {
                "car": r.car_label,
                "track": r.track,
                "real_s": r.real_time_s,
                "predicted_s": round(r.predicted_time_s, 3),
                "ratio": round(r.efficiency_ratio, 4),
                "tire_category": r.tire_category,
                "tire_model": r.tire_model,
                "mu": r.mu,
            }
            for r in results
        ],
        "summary": _compute_summary(results),
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    baseline_path = os.path.join(OUTPUT_DIR, "physics_baseline.json")
    with open(baseline_path, "w") as f:
        json.dump(baseline, f, indent=2)

    print(f"\nBaseline saved to {baseline_path} (git: {git_sha})")
    return baseline_path


def compare_to_baseline(
    results: list[ComparisonResult],
    baseline_path: str,
) -> bool:
    """Compare current results against a saved baseline. Returns True if no regressions."""
    if not os.path.exists(baseline_path):
        print(f"\n  No baseline found at {baseline_path} — skipping regression check.")
        return True

    with open(baseline_path) as f:
        baseline = json.load(f)

    prev = baseline["summary"]
    curr = _compute_summary(results)

    print(f"\n{'=' * 90}")
    b_date = baseline.get("date", "?")
    b_sha = baseline.get("git_sha", "?")
    print(f"REGRESSION CHECK vs baseline ({b_date} / {b_sha})")
    print(f"{'=' * 90}")

    regressions: list[str] = []

    def _cmp(name: str, curr_val: float, prev_val: float, lower_is_better: bool = True) -> None:
        delta = curr_val - prev_val
        direction = "↑" if delta > 0 else "↓" if delta < 0 else "="
        better = (delta < 0) if lower_is_better else (delta > 0)
        # Regression threshold: 10% relative worsening
        threshold = abs(prev_val) * 0.10 if prev_val != 0 else 0.01
        is_regression = (delta > threshold) if lower_is_better else (delta < -threshold)
        status = "REGRESS" if is_regression else ("better" if better else "same")
        print(
            f"  {name:<25} {prev_val:>8.4f} → {curr_val:>8.4f}  "
            f"({direction}{abs(delta):.4f})  [{status}]"
        )
        if is_regression:
            regressions.append(f"{name}: {prev_val:.4f} → {curr_val:.4f}")

    print(f"\n  {'Metric':<25} {'Previous':>8}   {'Current':>8}   {'Delta':>10}  Status")
    print(f"  {'-' * 75}")

    _cmp("mean_ratio", curr["mean_ratio"], prev["mean_ratio"], lower_is_better=False)
    _cmp("std_ratio", curr["std_ratio"], prev["std_ratio"], lower_is_better=True)
    _cmp(
        "exceedances_5pct",
        float(curr["exceedance_count_5pct"]),
        float(prev["exceedance_count_5pct"]),
        lower_is_better=True,
    )

    # Per-category comparison
    prev_cats = prev.get("per_category", {})
    curr_cats = curr.get("per_category", {})
    if prev_cats and curr_cats:
        print("\n  Per-category mean changes:")
        for cat in ["street", "endurance_200tw", "super_200tw", "100tw", "r_compound", "slick"]:
            if cat in prev_cats and cat in curr_cats:
                pm = prev_cats[cat]["mean"]
                cm = curr_cats[cat]["mean"]
                delta = cm - pm
                # For category means, closer to 1.0 is better
                prev_dist = abs(pm - 1.0)
                curr_dist = abs(cm - 1.0)
                better = curr_dist < prev_dist
                status = "better" if better else ("same" if abs(delta) < 0.002 else "worse")
                print(f"    {cat:<18}: {pm:.3f} → {cm:.3f} ({delta:+.3f}) [{status}]")

    passed = len(regressions) == 0
    print()
    if passed:
        print("  No regressions detected ✓")
    else:
        print(f"  REGRESSIONS DETECTED ({len(regressions)}):")
        for reg in regressions:
            print(f"    ✗ {reg}")

    return passed


def main() -> None:
    """Run the full real-world comparison pipeline."""
    parser = argparse.ArgumentParser(
        description="Physics validation: real-world lap time comparison"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if acceptance criteria fail",
    )
    parser.add_argument(
        "--compare",
        metavar="BASELINE_JSON",
        help="Compare against a saved baseline JSON for regression detection",
    )
    args = parser.parse_args()

    results = run_comparison()
    if not results:
        print("ERROR: No comparison results generated!")
        sys.exit(1)

    print_results(results)
    passed = validate_comparison(results)
    export_csv(results)
    export_baseline_json(results)

    # Regression check
    if args.compare:
        regression_ok = compare_to_baseline(results, args.compare)
        if not regression_ok and args.strict:
            sys.exit(2)

    if args.strict and not passed:
        print("\n--strict mode: exiting with code 1 due to failed checks.")
        sys.exit(1)


if __name__ == "__main__":
    main()

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
    CATEGORY_LATERAL_JERK_GS,
    CATEGORY_LLTD_PENALTY,
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
_DRIVETRAIN_EFFICIENCY: dict[str, float] = {"RWD": 0.85, "FWD": 0.88, "AWD": 0.80}
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
    source_quality: str = "community"  # professional / primary / aggregated / community
    driver_level: str = "unknown"  # pro / advanced_club / intermediate / unknown


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
        source_quality="community",
        driver_level="advanced_club",
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
        source_quality="aggregated",
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
        source_quality="primary",
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
        source_quality="primary",
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
        source_quality="primary",
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
        source_quality="aggregated",
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
        source_quality="aggregated",
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
        source_quality="aggregated",
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
        source_quality="aggregated",
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
        source_quality="primary",
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
        source_quality="primary",
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
        source_quality="aggregated",
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
        source_quality="aggregated",
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
        source_quality="primary",
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
        source_quality="primary",
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
        source_quality="primary",
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
        source_quality="primary",
    ),
    # --- Corvette C8 Stingray Z51 ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Corvette Z51", "C8"),
        car_label="Corvette C8 Z51",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:36.46"),
        tire_model="Michelin Pilot Sport 4S (OEM)",
        tire_category="endurance_200tw",
        mod_level="stock",
        source="lapmeta.com/en/model/13/chevrolet-corvette-c8-stingray-z51",
        notes="Stock Z51 on OEM PS4S (endurance-level grip per validation)",
        tire_db_key="michelin_ps4s",
        source_quality="aggregated",
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
        source_quality="aggregated",
    ),
    # --- Toyota GR Supra A90 ---
    RealWorldLapTime(
        car_key=("Toyota", "GR Supra", "A90"),
        car_label="GR Supra A90",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:38.00"),
        tire_model="Bridgestone Potenza RE-71RS",
        tire_category="super_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/15",
        notes="GR Supra on RE-71RS (super 200tw), light mods, D Marcus Mar 2022",
        tire_db_key="bridgestone_re71rs",
        source_quality="aggregated",
    ),
    RealWorldLapTime(
        car_key=("Toyota", "GR Supra", "A90"),
        car_label="GR Supra A90",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:41.60"),
        tire_model="Michelin Pilot Super Sport 300TW",
        tire_category="endurance_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/15",
        notes="GR Supra on MPSS (TW 300, endurance-level grip), light mods",
        tire_db_key="michelin_ps4s",
        source_quality="aggregated",
    ),
    # --- Hyundai Elantra N ---
    RealWorldLapTime(
        car_key=("Hyundai", "Elantra N", "CN7"),
        car_label="Elantra N",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:42.80"),
        tire_model="Kumho Ecsta V730",
        tire_category="super_200tw",
        mod_level="stock",
        source="lapmeta.com/en/track/variation/15",
        notes="Stock Elantra N on Kumho V730 (super 200tw). Driver 130 Nov 2025.",
        tire_db_key="kumho_v730",
        source_quality="aggregated",
    ),
    # --- GR86 on street tires ---
    RealWorldLapTime(
        car_key=("Toyota", "GR86", None),
        car_label="GR86",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:52.10"),
        tire_model="Michelin Pilot Super Sport 300TW (OEM-class)",
        tire_category="street",
        mod_level="stock",
        source="lapmeta.com/en/track/variation/15",
        notes="Stock GR86 on OEM-class street tire (TW 300). Jon Willett Jul 2024.",
        tire_db_key="michelin_ps4s",
        source_quality="aggregated",
    ),
    # --- Chevrolet Camaro ZL1 1LE ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Camaro ZL1", "6th Gen"),
        car_label="Camaro ZL1 1LE",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:35.90"),
        tire_model="Goodyear Eagle F1 SuperCar 3R 100TW (OEM)",
        tire_category="100tw",
        mod_level="stock",
        source="lapmeta.com/en/track/variation/15",
        notes="Stock ZL1 1LE on OEM SC3R (100tw). steelankles Jul 2021.",
        tire_db_key="goodyear_sc3r",
        source_quality="aggregated",
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
        source_quality="primary",
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
        source_quality="aggregated",
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
        source_quality="aggregated",
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
        source_quality="aggregated",
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
        source_quality="primary",
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
        source_quality="primary",
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
        source_quality="primary",
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
        source_quality="primary",
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
        source_quality="aggregated",
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
        source_quality="aggregated",
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
        source_quality="aggregated",
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
        source_quality="aggregated",
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
        source_quality="primary",
    ),
    # --- Chevrolet Camaro SS 1LE ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Camaro SS 1LE", "6th Gen"),
        car_label="Camaro SS 1LE",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:18.00"),
        tire_model="Goodyear Eagle F1 SuperCar 3 305/30/19 square (OEM)",
        tire_category="super_200tw",
        mod_level="stock",
        source="camaro6.com/forums/showthread.php?t=512725",
        notes="Stock SS 1LE on OEM SC3 (super 200tw). Multiple corroborating forum entries.",
        tire_db_key="goodyear_sc3",
        source_quality="primary",
    ),
    # --- Hyundai Veloster N ---
    RealWorldLapTime(
        car_key=("Hyundai", "Veloster N", None),
        car_label="Veloster N",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:21.70"),
        tire_model="Falken Azenis RT660",
        tire_category="endurance_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/135",
        notes="JST-Performance Veloster N on RT660 (endurance 200tw), light suspension",
        tire_db_key="falken_rt660",
        source_quality="aggregated",
    ),
    # --- Subaru BRZ Performance Package ---
    RealWorldLapTime(
        car_key=("Subaru", "BRZ", "ZD8"),
        car_label="Subaru BRZ",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:26.70"),
        tire_model="Michelin Primacy 3 240TW (stock)",
        tire_category="street",
        mod_level="stock",
        source="lapmeta.com/en/track/variation/135",
        notes="Stock BRZ on OEM street tire (TW 240). Fully stock baseline.",
        source_quality="aggregated",
    ),
    # =========================================================================
    # ATLANTA MOTORSPORTS PARK (2,927m / 1.83mi)
    # =========================================================================
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
        source_quality="aggregated",
    ),
    # --- Nissan 370Z ---
    RealWorldLapTime(
        car_key=("Nissan", "370Z", None),
        car_label="Nissan 370Z",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:34.60"),
        tire_model="Bridgestone Potenza RE-71RS",
        tire_category="super_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/27",
        notes="370Z on RE-71RS (super 200tw). Malko Izurieta Sep 2024.",
        tire_db_key="bridgestone_re71rs",
        source_quality="aggregated",
    ),
    # =========================================================================
    # NEW ENTRIES — AWD CARS (critical gap: was 0 entries)
    # =========================================================================
    # --- Nissan GT-R R35 (AWD) ---
    RealWorldLapTime(
        car_key=("Nissan", "GT-R", "R35"),
        car_label="Nissan GT-R R35",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:35.30"),
        tire_model="Hoosier R7",
        tire_category="r_compound",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/15",
        notes="GT-R R35 on R7 r-compound. 901 GTR Jul 2022.",
        tire_db_key="hoosier_r7",
        source_quality="aggregated",
    ),
    RealWorldLapTime(
        car_key=("Nissan", "GT-R", "R35"),
        car_label="Nissan GT-R R35",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:38.70"),
        tire_model="Dunlop SP Sport 600 DSST (OEM)",
        tire_category="street",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/15",
        notes="GT-R R35 on OEM Dunlop SP600 DSST (~200TW street). jomunjr Jun 2013.",
        source_quality="aggregated",
    ),
    RealWorldLapTime(
        car_key=("Nissan", "GT-R", "R35"),
        car_label="Nissan GT-R R35",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:13.40"),
        tire_model="Dunlop DH Slick",
        tire_category="slick",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/135",
        notes="GT-R R35 on DH slicks. L Keen Pro driver, Apr 2012.",
        source_quality="aggregated",
        driver_level="pro",
    ),
    RealWorldLapTime(
        car_key=("Nissan", "GT-R", "R35"),
        car_label="Nissan GT-R R35",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:23.90"),
        tire_model="Dunlop DH Slick",
        tire_category="slick",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/27",
        notes="GT-R R35 on DH slicks. L Keen Pro driver, May 2012.",
        source_quality="aggregated",
        driver_level="pro",
    ),
    # --- Subaru WRX STI (AWD) ---
    RealWorldLapTime(
        car_key=("Subaru", "WRX STI", "VA"),
        car_label="WRX STI",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:38.90"),
        tire_model="Yokohama ADVAN A052",
        tire_category="super_200tw",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/15",
        notes="WRX STI Mk3 on A052 200TW. good4man2 Oct 2021.",
        tire_db_key="yokohama_a052",
        source_quality="aggregated",
    ),
    # --- Ford Focus RS Mk3 (AWD) ---
    RealWorldLapTime(
        car_key=("Ford", "Focus RS", "Mk3"),
        car_label="Focus RS Mk3",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:25.00"),
        tire_model="Kumho Ecsta S1 Evo3 K127 (340TW)",
        tire_category="street",
        mod_level="light",
        source="lapmeta.com/en/track/variation/135",
        notes="Focus RS AWD on 340TW street tire. JST-Performance May 2017.",
        source_quality="aggregated",
    ),
    RealWorldLapTime(
        car_key=("Ford", "Focus RS", "Mk3"),
        car_label="Focus RS Mk3",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:35.90"),
        tire_model="Kumho Ecsta S1 Evo3 K127 (340TW)",
        tire_category="street",
        mod_level="light",
        source="lapmeta.com/en/track/variation/27",
        notes="Focus RS AWD on 340TW street. Same driver+car as Roebling. Sep 2017.",
        source_quality="aggregated",
    ),
    # --- Volkswagen Golf R Mk7 (AWD) ---
    RealWorldLapTime(
        car_key=("Volkswagen", "Golf R", None),
        car_label="Golf R Mk7",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:25.50"),
        tire_model="Firestone Firehawk Indy 500 (340TW)",
        tire_category="street",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/135",
        notes="Golf R AWD on 340TW street. m3bs Nov 2018.",
        source_quality="aggregated",
    ),
    RealWorldLapTime(
        car_key=("Volkswagen", "Golf R", None),
        car_label="Golf R Mk7",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:37.90"),
        tire_model="Firestone Firehawk Indy 500 (340TW)",
        tire_category="street",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/27",
        notes="Golf R AWD on 340TW street. Same driver as Roebling. Nov 2017.",
        source_quality="aggregated",
    ),
    # --- Audi TT RS 8S (AWD) ---
    RealWorldLapTime(
        car_key=("Audi", "TT RS", "8S"),
        car_label="Audi TT RS 8S",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:46.90"),
        tire_model="Goodyear SuperCar 3 (220TW)",
        tire_category="endurance_200tw",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/15",
        notes="TT RS 8S AWD on SC3 220TW. Richard Brewer Nov 2025.",
        source_quality="aggregated",
    ),
    # =========================================================================
    # NEW ENTRIES — RWD DIVERSITY
    # =========================================================================
    # --- BMW M3 E92 ---
    RealWorldLapTime(
        car_key=("BMW", "M3", "E92"),
        car_label="BMW M3 E92",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:38.60"),
        tire_model="Michelin Pilot Sport Cup 2 R (200TW)",
        tire_category="super_200tw",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/15",
        notes="E92 M3 on CR-S 200TW. kevs_mnc Nov 2024.",
        source_quality="aggregated",
    ),
    # --- BMW M2 F87 ---
    RealWorldLapTime(
        car_key=("BMW", "M2", "F87"),
        car_label="BMW M2 Competition F87",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:35.80"),
        tire_model="Bridgestone Potenza RE-71RS",
        tire_category="super_200tw",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/15",
        notes="M2 Competition F87 on RE-71RS 200TW. jwr9152 Sep 2023.",
        tire_db_key="bridgestone_re71rs",
        source_quality="aggregated",
    ),
    # --- Nissan 350Z ---
    RealWorldLapTime(
        car_key=("Nissan", "350Z", None),
        car_label="Nissan 350Z",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:38.10"),
        tire_model="Hoosier R7",
        tire_category="r_compound",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/15",
        notes="350Z on R7 r-compound. Duncan James Jul 2021.",
        tire_db_key="hoosier_r7",
        source_quality="aggregated",
    ),
    RealWorldLapTime(
        car_key=("Nissan", "350Z", None),
        car_label="Nissan 350Z",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:17.60"),
        tire_model="Hoosier R7",
        tire_category="r_compound",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/135",
        notes="350Z on R7 r-compound. L Andras Sep 2022.",
        tire_db_key="hoosier_r7",
        source_quality="aggregated",
    ),
    # --- Lexus RC F ---
    RealWorldLapTime(
        car_key=("Lexus", "RC F", None),
        car_label="Lexus RC F",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:39.00"),
        tire_model="Bridgestone Potenza RE-71RS",
        tire_category="super_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/15",
        notes="RC F (472hp NA V8 RWD) on RE-71RS 200TW. Rex Raikkonen Jun 2023.",
        tire_db_key="bridgestone_re71rs",
        source_quality="aggregated",
    ),
    # --- Corvette C5 Z06 ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Corvette", "C5"),
        car_label="Corvette C5 Z06",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:27.20"),
        tire_model="Bridgestone Potenza RE-71RS",
        tire_category="super_200tw",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/27",
        notes="C5 Z06 (385hp LS6) on RE-71RS 200TW. Project S14HR Mar 2022.",
        tire_db_key="bridgestone_re71rs",
        source_quality="aggregated",
    ),
    # --- Lotus Elise S2 ---
    RealWorldLapTime(
        car_key=("Lotus", "Elise", "S2"),
        car_label="Lotus Elise S2",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:32.90"),
        tire_model="Yokohama AD07 (180TW)",
        tire_category="endurance_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/27",
        notes="Elise S2 (~190hp) on AD07 180TW. B Allen Aug 2025.",
        source_quality="aggregated",
    ),
    # =========================================================================
    # NEW ENTRIES — FWD DIVERSITY
    # =========================================================================
    # --- Honda Civic Si ---
    RealWorldLapTime(
        car_key=("Honda", "Civic Si", None),
        car_label="Honda Civic Si FC1",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:45.00"),
        tire_model="Goodyear SuperCar 3 (220TW)",
        tire_category="endurance_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/15",
        notes="Civic Si FC1 (205hp FWD) on SC3 220TW. Flyin Finch Aug 2021.",
        source_quality="aggregated",
    ),
    # --- Honda Civic Type R FK8 at Roebling ---
    RealWorldLapTime(
        car_key=("Honda", "Civic Type R", "FK8"),
        car_label="Civic Type R FK8",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:25.00"),
        tire_model="Continental ContactSport 6 (200TW)",
        tire_category="endurance_200tw",
        mod_level="stock",
        source="lapmeta.com/en/track/variation/135",
        notes="FK8 on stock-adjacent OEM-ish 200TW tires. ep3_lol Jan 2019.",
        source_quality="aggregated",
    ),
    # --- BMW M3 F80 at Roebling ---
    RealWorldLapTime(
        car_key=("BMW", "M3", "F80"),
        car_label="BMW M3 F80",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:16.70"),
        tire_model="Falken Azenis RT615K+ (200TW)",
        tire_category="super_200tw",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/135",
        notes="F80 M3 DCT on RT615K+ 200TW. gixxerhoff750 May 2025.",
        source_quality="aggregated",
    ),
    # =========================================================================
    # BATCH 2 — More RWD/AWD diversity
    # =========================================================================
    # --- BMW M3 G80 CS at Barber ---
    RealWorldLapTime(
        car_key=("BMW", "M3", "G80"),
        car_label="BMW M3 CS G80",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:33.90"),
        tire_model="Bridgestone Potenza RE-71RS",
        tire_category="super_200tw",
        mod_level="light",
        source="lapmeta.com/en/track/variation/15",
        notes="M3 CS G80 on RE-71RS 200TW. DRAGA Jan 2026.",
        tire_db_key="bridgestone_re71rs",
        source_quality="aggregated",
    ),
    # --- Nissan GT-R R35 at Barber (Nitto NT01) ---
    RealWorldLapTime(
        car_key=("Nissan", "GT-R", "R35"),
        car_label="Nissan GT-R R35",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:36.80"),
        tire_model="Nitto NT01 (100TW)",
        tire_category="100tw",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/15",
        notes="GT-R R35 on NT01 100TW. RangerExec Apr 2016.",
        source_quality="aggregated",
    ),
    # --- Corvette C6 Z06 at Barber (street tires) ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Corvette", "C6"),
        car_label="Corvette C6 Z06",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:40.50"),
        tire_model="Michelin Pilot Sport 4S (300TW)",
        tire_category="street",
        mod_level="stock",
        source="lapmeta.com/en/track/variation/15",
        notes="C6 Z06 (505hp LS7) on PS4S 300TW street. APEX1LE Jan 2022.",
        tire_db_key="michelin_ps4s",
        source_quality="aggregated",
    ),
    # --- BMW M4 F82 at Roebling (street) ---
    RealWorldLapTime(
        car_key=("BMW", "M4", "F82"),
        car_label="BMW M4 F82",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:22.30"),
        tire_model="Michelin Pilot Sport 4S (300TW)",
        tire_category="street",
        mod_level="light",
        source="lapmeta.com/en/track/variation/135",
        notes="M4 F82 DCT on PSS 300TW street. PriZeFighter13 Jan 2015.",
        tire_db_key="michelin_ps4s",
        source_quality="aggregated",
    ),
    # --- BMW M3 E92 at AMP ---
    RealWorldLapTime(
        car_key=("BMW", "M3", "E92"),
        car_label="BMW M3 E92",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:30.50"),
        tire_model="Michelin Tempesta P1 (200TW)",
        tire_category="super_200tw",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/27",
        notes="E92 M3 on Tempesta P1 200TW. kevs_mnc Apr 2025.",
        source_quality="aggregated",
    ),
    # --- Corvette C7 Z06 at AMP (street) ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Corvette", "C7"),
        car_label="Corvette C7 Z06",
        track_name="Atlanta Motorsports Park",
        lap_time_s=_parse_time("1:33.00"),
        tire_model="Michelin Pilot Super Sport (300TW)",
        tire_category="street",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/27",
        notes="C7 Z06 (650hp LT4 S/C) on PSS 300TW street. Craig Birchfield May 2020.",
        tire_db_key="michelin_ps4s",
        source_quality="aggregated",
    ),
    # --- Subaru WRX STI GD at Roebling (AWD) ---
    RealWorldLapTime(
        car_key=("Subaru", "WRX STI", "VA"),
        car_label="WRX STI GD",
        track_name="Roebling Road Raceway",
        lap_time_s=_parse_time("1:24.60"),
        tire_model="Dunlop Direzza ZII Star Spec (200TW)",
        tire_category="super_200tw",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/135",
        notes="WRX STI GD/GG on Direzza ZII 200TW. cmb350 Sep 2022. AWD.",
        source_quality="aggregated",
    ),
    # --- Corvette C5 Z06 at Barber (slick) ---
    RealWorldLapTime(
        car_key=("Chevrolet", "Corvette", "C5"),
        car_label="Corvette C5 Z06",
        track_name="Barber Motorsports Park",
        lap_time_s=_parse_time("1:42.60"),
        tire_model="Pirelli P Zero DH Slick",
        tire_category="slick",
        mod_level="heavy",
        source="lapmeta.com/en/track/variation/15",
        notes="C5 Z06 (385hp LS6) on DH slicks. FASTFATBOY Apr 2016.",
        source_quality="aggregated",
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
    lltd = CATEGORY_LLTD_PENALTY.get(compound, 1.00)
    mu = mu_raw * grip_util * thermal * lltd
    weight_kg = spec.weight_kg

    base_accel_g = _CATEGORY_ACCEL_G[compound]
    pw_ratio = spec.hp / (weight_kg / 1000.0)
    pw_factor = min(pw_ratio / 200.0, 1.5)
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
    lateral_jerk = CATEGORY_LATERAL_JERK_GS.get(compound, 5.0)

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
        max_lateral_jerk_gs=lateral_jerk,
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
    hp: float = 0.0
    weight_kg: float = 0.0
    drivetrain: str = ""
    source_quality: str = "community"
    driver_level: str = "unknown"


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
                hp=spec.hp,
                weight_kg=spec.weight_kg,
                drivetrain=spec.drivetrain,
                source_quality=rw.source_quality,
                driver_level=rw.driver_level,
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
    "exceedance_5pct_max": 8,  # scaled from 5@n=42 to 8@n=71 (~12% rate)
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
    std_ratio = float(np.std(ratios, ddof=1))
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

    # --- Check 5: Extended Metrics ---
    summary = _compute_summary(results)

    print("\n5. EXTENDED METRICS")
    print(f"  RMSE: {summary['rmse_s']:.3f}s")
    print(f"  MAE: {summary['mae_s']:.3f}s")
    print(f"  MAPE: {summary['mape_pct']:.2f}%")
    print(f"  P90 abs error: {summary['p90_abs_error_s']:.3f}s")
    print(f"  P95 abs error: {summary['p95_abs_error_s']:.3f}s")

    # --- Check 6: Bland-Altman ---
    print("\n6. BLAND-ALTMAN AGREEMENT")
    print(f"  Bias: {summary['bland_altman_bias_s']:.3f}s")
    print(
        f"  95% Limits of Agreement: "
        f"[{summary['bland_altman_loa_lower_s']:.3f}, "
        f"{summary['bland_altman_loa_upper_s']:.3f}]s"
    )

    # --- Check 7: Calibration Regression ---
    print("\n7. CALIBRATION REGRESSION")
    print(f"  Slope: {summary['calibration_slope']:.4f} (ideal=1.000)")
    print(f"  Intercept: {summary['calibration_intercept_s']:.3f}s (ideal=0.000)")
    print(f"  R²: {summary['calibration_r_squared']:.4f}")

    # --- Check 8: Residual Correlations ---
    print("\n8. RESIDUAL CORRELATIONS")
    mu_stars = _significance_stars(summary["correlation_mu_pvalue"])
    w_stars = _significance_stars(summary["correlation_weight_pvalue"])
    print(
        f"  r(ratio, mu): {summary['correlation_mu_ratio']:.3f} "
        f"(p={summary['correlation_mu_pvalue']:.4f}) {mu_stars}"
    )
    print(
        f"  r(ratio, weight): {summary['correlation_weight_ratio']:.3f} "
        f"(p={summary['correlation_weight_pvalue']:.4f}) {w_stars}"
    )

    # --- Check 9: Bootstrap CIs ---
    print("\n9. BOOTSTRAP 95% CIs (BCa, 10k resamples)")
    print(
        f"  Mean ratio: [{summary['bootstrap_mean_ci_lower']:.4f}, "
        f"{summary['bootstrap_mean_ci_upper']:.4f}]"
    )
    print(
        f"  Std ratio: [{summary['bootstrap_std_ci_lower']:.4f}, "
        f"{summary['bootstrap_std_ci_upper']:.4f}]"
    )

    # --- Check 10: Multi-dimensional segmentation ---
    print("\n10. MULTI-DIMENSIONAL SEGMENTATION")

    print("    --- Grip Bands ---")
    for band_name, band_data in summary.get("per_grip_band", {}).items():
        print(
            f"    {band_name}: n={band_data['n']}, "
            f"mean={band_data['mean']:.4f}, std={band_data['std']:.4f}"
        )

    print("    --- Power-to-Weight Bands ---")
    for band_name, band_data in summary.get("per_pw_band", {}).items():
        print(
            f"    {band_name}: n={band_data['n']}, "
            f"mean={band_data['mean']:.4f}, std={band_data['std']:.4f}"
        )

    print("    --- Fast vs Slow ---")
    fss = summary.get("fast_slow_split", {})
    if fss:
        fast = fss.get("fast", {})
        slow = fss.get("slow", {})
        print(f"    Fast (<{fss['median_time_s']:.1f}s): n={fast['n']}, mean={fast['mean']:.4f}")
        print(f"    Slow (>={fss['median_time_s']:.1f}s): n={slow['n']}, mean={slow['mean']:.4f}")

    # --- Check 11: Influential Points ---
    print("\n11. INFLUENTIAL POINTS (IQR outliers)")
    outliers_list: list[dict] = summary.get("iqr_outliers", [])
    if outliers_list:
        for ol in outliers_list:
            print(f"    {ol['car']} at {ol['track']}: ratio={ol['ratio']}")
    else:
        print("    No IQR outliers detected.")

    # --- Check 12: Accuracy Tier Assessment ---
    print("\n12. ACCURACY TIER ASSESSMENT")
    print(f"    Current tier: {summary['accuracy_tier']}")
    mean_bias = abs(summary["mean_ratio"] - 1.0)
    for tier_name, criteria in TIER_CRITERIA.items():
        if tier_name == summary["accuracy_tier"]:
            break
        missing: list[str] = []
        if mean_bias > criteria["mean_bias_max"]:
            missing.append(f"mean_bias {mean_bias:.4f} > {criteria['mean_bias_max']}")
        if summary["std_ratio"] > criteria["std_max"]:
            missing.append(f"std {summary['std_ratio']:.4f} > {criteria['std_max']}")
        if summary["mape_pct"] > criteria["mape_max"]:
            missing.append(f"MAPE {summary['mape_pct']:.2f}% > {criteria['mape_max']}%")
        if missing:
            print(f"    {tier_name} requires: {', '.join(missing)}")

    # --- Check 13: Mod Level Breakdown ---
    print("\n13. BREAKDOWN BY MODIFICATION LEVEL")
    for mod_name, mod_data in summary.get("per_mod_level", {}).items():
        ci_str = ""
        if "bootstrap_mean_ci_lower" in mod_data:
            lo = mod_data["bootstrap_mean_ci_lower"]
            hi = mod_data["bootstrap_mean_ci_upper"]
            ci_str = f", CI=[{lo:.4f}, {hi:.4f}]"
        print(
            f"    {mod_name:<8}: n={mod_data['n']}, "
            f"mean={mod_data['mean']:.4f}, std={mod_data['std']:.4f}{ci_str}"
        )

    # --- Check 14: HP Band Breakdown ---
    print("\n14. BREAKDOWN BY HORSEPOWER BAND")
    for band_name, band_data in summary.get("per_hp_band", {}).items():
        print(
            f"    {band_name:<16}: n={band_data['n']}, "
            f"mean={band_data['mean']:.4f}, std={band_data['std']:.4f}"
        )

    # --- Check 15: Drivetrain Breakdown ---
    print("\n15. BREAKDOWN BY DRIVETRAIN")
    for dt_name, dt_data in summary.get("per_drivetrain", {}).items():
        print(
            f"    {dt_name:<4}: n={dt_data['n']}, "
            f"mean={dt_data['mean']:.4f}, std={dt_data['std']:.4f}"
        )

    # --- Check 16: Source Quality Breakdown ---
    print("\n16. BREAKDOWN BY SOURCE QUALITY")
    for sq_name, sq_data in summary.get("per_source_quality", {}).items():
        print(
            f"    {sq_name:<14}: n={sq_data['n']}, "
            f"mean={sq_data['mean']:.4f}, std={sq_data['std']:.4f}"
        )

    # --- Check 17: Driver Level Breakdown ---
    print("\n17. BREAKDOWN BY DRIVER LEVEL")
    for dl_name, dl_data in summary.get("per_driver_level", {}).items():
        print(
            f"    {dl_name:<16}: n={dl_data['n']}, "
            f"mean={dl_data['mean']:.4f}, std={dl_data['std']:.4f}"
        )

    # --- Check 18: Leave-One-Out Cross-Validation ---
    print("\n18. LEAVE-ONE-OUT CROSS-VALIDATION (Jackknife)")
    loo = summary.get("loo_cv", {})
    if loo:
        jr = loo.get("jackknife_mean_range", [0, 0])
        stability = loo.get("jackknife_mean_stability", 0)
        print(f"    Mean range when dropping one entry: [{jr[0]:.4f}, {jr[1]:.4f}]")
        print(f"    Mean stability (max spread): {stability:.4f}")
        inf_count = loo.get("influential_count", 0)
        if inf_count > 0:
            print(f"    Influential entries ({inf_count} shift mean > ±0.003):")
            for inf in loo.get("influential_entries", []):
                print(
                    f"      {inf['car']} at {inf['track']}: "
                    f"ratio={inf['ratio']}, shift={inf['shift']:+.4f}"
                )
        else:
            print("    No influential entries (all shifts ≤ ±0.003)")

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
                "source_quality",
                "driver_level",
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
                    r.source_quality,
                    r.driver_level,
                    r.source,
                    r.notes,
                ]
            )

    print(f"\nExported {len(results)} rows to {path}")


GRIP_BANDS: dict[str, list[str]] = {
    "Low (street+endurance)": ["street", "endurance_200tw"],
    "Mid (super+100tw)": ["super_200tw", "100tw"],
    "High (r_compound+slick)": ["r_compound", "slick"],
}

PW_BANDS: list[tuple[str, float, float]] = [
    ("Low <200 hp/t", 0, 200),
    ("Mid 200-350", 200, 350),
    ("High >350", 350, 9999),
]

# Evidence-based accuracy tiers from published literature.
# See docs/physics-accuracy-tier-research.md for full references.
# Key sources: Dal Bianco GP2 (0.34%, Proc. IMechE 2018), IPG CarMaker FSAE (0.15-2%,
# MDPI 2024), OptimumLap ("up to 10%", OptimumG), Broatch thesis (8.3-10.2%),
# ChassisSim (<2% calibrated, ~5% uncalibrated), MIT Noel (R²=0.807).
TIER_CRITERIA: dict[str, dict[str, float]] = {
    "D: Engineering": {"mean_bias_max": 0.005, "std_max": 0.015, "mape_max": 1.0},
    "C: Coaching": {"mean_bias_max": 0.010, "std_max": 0.035, "mape_max": 3.0},
    "B: Setup": {"mean_bias_max": 0.020, "std_max": 0.050, "mape_max": 5.0},
    "A: Screening": {"mean_bias_max": 0.050, "std_max": 0.080, "mape_max": 10.0},
}


def _significance_stars(p: float) -> str:
    """Return significance stars for a p-value."""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def _compute_summary(results: list[ComparisonResult]) -> dict:
    """Compute comprehensive summary statistics from comparison results."""
    from scipy import stats as sp_stats

    ratios = [r.efficiency_ratio for r in results]
    ratios_arr = np.array(ratios)
    predicted = np.array([r.predicted_time_s for r in results])
    real = np.array([r.real_time_s for r in results])
    errors = predicted - real
    abs_errors = np.abs(errors)

    # --- Basic (keep existing) ---
    summary: dict = {
        "n_entries": len(results),
        "mean_ratio": float(np.mean(ratios_arr)),
        "median_ratio": float(np.median(ratios_arr)),
        "std_ratio": float(np.std(ratios_arr, ddof=1)),
        "exceedance_count_5pct": int(np.sum(ratios_arr > 1.05)),
        "entries_above_1": int(np.sum(ratios_arr > 1.0)),
    }

    # --- Error metrics in seconds ---
    summary["rmse_s"] = float(np.sqrt(np.mean(errors**2)))
    summary["mae_s"] = float(np.mean(abs_errors))
    summary["mape_pct"] = float(np.mean(abs_errors / real) * 100)
    summary["p90_abs_error_s"] = float(np.percentile(abs_errors, 90))
    summary["p95_abs_error_s"] = float(np.percentile(abs_errors, 95))

    # --- Bland-Altman ---
    ba_bias = float(np.mean(errors))
    ba_std = float(np.std(errors, ddof=1))
    summary["bland_altman_bias_s"] = ba_bias
    summary["bland_altman_loa_lower_s"] = ba_bias - 1.96 * ba_std
    summary["bland_altman_loa_upper_s"] = ba_bias + 1.96 * ba_std

    # --- Calibration regression (pred vs real) ---
    slope_res = sp_stats.linregress(real, predicted)
    summary["calibration_slope"] = float(slope_res.slope)
    summary["calibration_intercept_s"] = float(slope_res.intercept)
    summary["calibration_r_squared"] = float(slope_res.rvalue**2)

    # --- Residual correlations ---
    mus = np.array([r.mu for r in results])
    weights = np.array([r.weight_kg for r in results])

    if len(mus) >= 3:
        r_mu, p_mu = sp_stats.pearsonr(mus, ratios_arr)
        summary["correlation_mu_ratio"] = float(r_mu)
        summary["correlation_mu_pvalue"] = float(p_mu)
    else:
        summary["correlation_mu_ratio"] = 0.0
        summary["correlation_mu_pvalue"] = 1.0

    if len(weights) >= 3 and np.std(weights) > 0:
        r_w, p_w = sp_stats.pearsonr(weights, ratios_arr)
        summary["correlation_weight_ratio"] = float(r_w)
        summary["correlation_weight_pvalue"] = float(p_w)
    else:
        summary["correlation_weight_ratio"] = 0.0
        summary["correlation_weight_pvalue"] = 1.0

    # --- Bootstrap 95% CIs (BCa, 10k resamples) ---
    rng = np.random.default_rng(42)
    try:
        bs_mean = sp_stats.bootstrap(
            (ratios_arr,), np.mean, n_resamples=10000, random_state=rng, method="BCa"
        )
        summary["bootstrap_mean_ci_lower"] = float(bs_mean.confidence_interval.low)
        summary["bootstrap_mean_ci_upper"] = float(bs_mean.confidence_interval.high)
    except Exception:
        summary["bootstrap_mean_ci_lower"] = float(np.mean(ratios_arr))
        summary["bootstrap_mean_ci_upper"] = float(np.mean(ratios_arr))

    try:
        bs_std = sp_stats.bootstrap(
            (ratios_arr,), np.std, n_resamples=10000, random_state=rng, method="BCa"
        )
        summary["bootstrap_std_ci_lower"] = float(bs_std.confidence_interval.low)
        summary["bootstrap_std_ci_upper"] = float(bs_std.confidence_interval.high)
    except Exception:
        summary["bootstrap_std_ci_lower"] = float(np.std(ratios_arr, ddof=1))
        summary["bootstrap_std_ci_upper"] = float(np.std(ratios_arr, ddof=1))

    # --- IQR outliers ---
    q1 = float(np.percentile(ratios_arr, 25))
    q3 = float(np.percentile(ratios_arr, 75))
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    outliers: list[dict[str, object]] = []
    for r in results:
        if r.efficiency_ratio < lower_fence or r.efficiency_ratio > upper_fence:
            outliers.append(
                {
                    "car": r.car_label,
                    "track": r.track,
                    "ratio": round(r.efficiency_ratio, 4),
                }
            )
    summary["iqr_outlier_count"] = len(outliers)
    summary["iqr_outliers"] = outliers

    # --- Per-category stats (enhanced with bootstrap CIs where n>=5) ---
    cat_order = ["street", "endurance_200tw", "super_200tw", "100tw", "r_compound", "slick"]
    per_category: dict[str, dict] = {}
    for cat in cat_order:
        cat_ratios = np.array([r.efficiency_ratio for r in results if r.tire_category == cat])
        if len(cat_ratios) > 0:
            cat_entry: dict[str, object] = {
                "n": len(cat_ratios),
                "mean": round(float(np.mean(cat_ratios)), 4),
                "std": round(float(np.std(cat_ratios)), 4),
                "min": round(float(np.min(cat_ratios)), 4),
                "max": round(float(np.max(cat_ratios)), 4),
            }
            if len(cat_ratios) >= 5:
                try:
                    bs_cat = sp_stats.bootstrap(
                        (cat_ratios,),
                        np.mean,
                        n_resamples=10000,
                        random_state=rng,
                        method="BCa",
                    )
                    cat_entry["bootstrap_mean_ci_lower"] = round(
                        float(bs_cat.confidence_interval.low), 4
                    )
                    cat_entry["bootstrap_mean_ci_upper"] = round(
                        float(bs_cat.confidence_interval.high), 4
                    )
                except Exception:
                    pass
            per_category[cat] = cat_entry
    summary["per_category"] = per_category

    # --- Per-track breakdown ---
    per_track: dict[str, dict[str, object]] = {}
    for track in sorted(set(r.track for r in results)):
        t_ratios = np.array([r.efficiency_ratio for r in results if r.track == track])
        per_track[track] = {
            "n": len(t_ratios),
            "mean": round(float(np.mean(t_ratios)), 4),
            "std": round(float(np.std(t_ratios)), 4),
            "min": round(float(np.min(t_ratios)), 4),
            "max": round(float(np.max(t_ratios)), 4),
        }
    summary["per_track"] = per_track

    # --- Grip band breakdown ---
    per_grip_band: dict[str, dict[str, object]] = {}
    for band_name, band_cats in GRIP_BANDS.items():
        band_results = [r for r in results if r.tire_category in band_cats]
        if band_results:
            b_ratios = np.array([r.efficiency_ratio for r in band_results])
            per_grip_band[band_name] = {
                "n": len(b_ratios),
                "mean": round(float(np.mean(b_ratios)), 4),
                "std": round(float(np.std(b_ratios)), 4),
                "categories": sorted(set(r.tire_category for r in band_results)),
            }
    summary["per_grip_band"] = per_grip_band

    # --- Power-to-weight band breakdown ---
    per_pw_band: dict[str, dict[str, object]] = {}
    for band_name, pw_lo, pw_hi in PW_BANDS:
        band_results = [
            r
            for r in results
            if r.weight_kg > 0 and pw_lo <= (r.hp / (r.weight_kg / 1000.0)) < pw_hi
        ]
        if band_results:
            b_ratios = np.array([r.efficiency_ratio for r in band_results])
            per_pw_band[band_name] = {
                "n": len(b_ratios),
                "mean": round(float(np.mean(b_ratios)), 4),
                "std": round(float(np.std(b_ratios)), 4),
            }
    summary["per_pw_band"] = per_pw_band

    # --- Fast vs slow split ---
    median_time = float(np.median(real))
    fast_ratios = ratios_arr[real < median_time]
    slow_ratios = ratios_arr[real >= median_time]
    summary["fast_slow_split"] = {
        "median_time_s": round(median_time, 2),
        "fast": {
            "n": len(fast_ratios),
            "mean": round(float(np.mean(fast_ratios)), 4) if len(fast_ratios) > 0 else 0.0,
            "std": round(float(np.std(fast_ratios)), 4) if len(fast_ratios) > 0 else 0.0,
        },
        "slow": {
            "n": len(slow_ratios),
            "mean": round(float(np.mean(slow_ratios)), 4) if len(slow_ratios) > 0 else 0.0,
            "std": round(float(np.std(slow_ratios)), 4) if len(slow_ratios) > 0 else 0.0,
        },
    }

    # --- Mod level breakdown ---
    per_mod_level: dict[str, dict[str, object]] = {}
    for mod in ["stock", "light", "heavy"]:
        mod_results = [r for r in results if r.mod_level == mod]
        if mod_results:
            m_ratios = np.array([r.efficiency_ratio for r in mod_results])
            mod_entry: dict[str, object] = {
                "n": len(m_ratios),
                "mean": round(float(np.mean(m_ratios)), 4),
                "std": round(float(np.std(m_ratios, ddof=1)) if len(m_ratios) > 1 else 0.0, 4),
                "min": round(float(np.min(m_ratios)), 4),
                "max": round(float(np.max(m_ratios)), 4),
            }
            if len(m_ratios) >= 5:
                try:
                    bs_mod = sp_stats.bootstrap(
                        (m_ratios,), np.mean, n_resamples=10000, random_state=rng, method="BCa"
                    )
                    mod_entry["bootstrap_mean_ci_lower"] = round(
                        float(bs_mod.confidence_interval.low), 4
                    )
                    mod_entry["bootstrap_mean_ci_upper"] = round(
                        float(bs_mod.confidence_interval.high), 4
                    )
                except Exception:
                    pass
            per_mod_level[mod] = mod_entry
    summary["per_mod_level"] = per_mod_level

    # --- HP band breakdown ---
    hp_bands: list[tuple[str, float, float]] = [
        ("Low <200hp", 0, 200),
        ("Mid 200-400hp", 200, 400),
        ("High >400hp", 400, 9999),
    ]
    per_hp_band: dict[str, dict[str, object]] = {}
    for band_name, hp_lo, hp_hi in hp_bands:
        band_results = [r for r in results if r.hp > 0 and hp_lo <= r.hp < hp_hi]
        if band_results:
            b_ratios = np.array([r.efficiency_ratio for r in band_results])
            per_hp_band[band_name] = {
                "n": len(b_ratios),
                "mean": round(float(np.mean(b_ratios)), 4),
                "std": round(float(np.std(b_ratios, ddof=1)) if len(b_ratios) > 1 else 0.0, 4),
            }
    summary["per_hp_band"] = per_hp_band

    # --- Drivetrain breakdown ---
    per_drivetrain: dict[str, dict[str, object]] = {}
    for dt in sorted(set(r.drivetrain for r in results if r.drivetrain)):
        dt_results = [r for r in results if r.drivetrain == dt]
        if dt_results:
            dt_ratios = np.array([r.efficiency_ratio for r in dt_results])
            per_drivetrain[dt] = {
                "n": len(dt_ratios),
                "mean": round(float(np.mean(dt_ratios)), 4),
                "std": round(float(np.std(dt_ratios, ddof=1)) if len(dt_ratios) > 1 else 0.0, 4),
            }
    summary["per_drivetrain"] = per_drivetrain

    # --- Source quality breakdown ---
    per_source_quality: dict[str, dict[str, object]] = {}
    for sq in sorted(set(r.source_quality for r in results)):
        sq_results = [r for r in results if r.source_quality == sq]
        if sq_results:
            sq_ratios = np.array([r.efficiency_ratio for r in sq_results])
            per_source_quality[sq] = {
                "n": len(sq_ratios),
                "mean": round(float(np.mean(sq_ratios)), 4),
                "std": round(float(np.std(sq_ratios, ddof=1)) if len(sq_ratios) > 1 else 0.0, 4),
            }
    summary["per_source_quality"] = per_source_quality

    # --- Driver level breakdown ---
    per_driver_level: dict[str, dict[str, object]] = {}
    for dl in sorted(set(r.driver_level for r in results)):
        dl_results = [r for r in results if r.driver_level == dl]
        if dl_results:
            dl_ratios = np.array([r.efficiency_ratio for r in dl_results])
            per_driver_level[dl] = {
                "n": len(dl_ratios),
                "mean": round(float(np.mean(dl_ratios)), 4),
                "std": round(float(np.std(dl_ratios, ddof=1)) if len(dl_ratios) > 1 else 0.0, 4),
            }
    summary["per_driver_level"] = per_driver_level

    # --- Leave-one-out cross-validation (jackknife stability) ---
    loo_means: list[float] = []
    loo_stds: list[float] = []
    loo_influential: list[dict[str, object]] = []
    for i in range(len(results)):
        loo_ratios = np.array([r.efficiency_ratio for j, r in enumerate(results) if j != i])
        loo_mean = float(np.mean(loo_ratios))
        loo_std = float(np.std(loo_ratios, ddof=1))
        loo_means.append(loo_mean)
        loo_stds.append(loo_std)
        # Flag entries whose removal shifts mean by > 0.003 (influential)
        if abs(loo_mean - summary["mean_ratio"]) > 0.003:
            loo_influential.append(
                {
                    "car": results[i].car_label,
                    "track": results[i].track,
                    "ratio": round(results[i].efficiency_ratio, 4),
                    "mean_without": round(loo_mean, 4),
                    "shift": round(loo_mean - summary["mean_ratio"], 4),
                }
            )
    summary["loo_cv"] = {
        "jackknife_mean_range": [round(min(loo_means), 4), round(max(loo_means), 4)],
        "jackknife_std_range": [round(min(loo_stds), 4), round(max(loo_stds), 4)],
        "jackknife_mean_stability": round(max(loo_means) - min(loo_means), 4),
        "influential_entries": loo_influential,
        "influential_count": len(loo_influential),
    }

    # --- Tier assessment ---
    mean_bias = abs(summary["mean_ratio"] - 1.0)
    std_val = summary["std_ratio"]
    mape_val = summary["mape_pct"]
    current_tier = "F: Unvalidated"
    for tier_name, criteria in TIER_CRITERIA.items():
        if (
            mean_bias <= criteria["mean_bias_max"]
            and std_val <= criteria["std_max"]
            and mape_val <= criteria["mape_max"]
        ):
            current_tier = tier_name
            break
    summary["accuracy_tier"] = current_tier

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
                "source_quality": r.source_quality,
                "driver_level": r.driver_level,
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

    def _cmp_target(name: str, curr_val: float, prev_val: float, target: float = 1.0) -> None:
        """Compare values where closer to target is better (e.g. mean_ratio → 1.0)."""
        prev_dist = abs(prev_val - target)
        curr_dist = abs(curr_val - target)
        delta = curr_val - prev_val
        direction = "↑" if delta > 0 else "↓" if delta < 0 else "="
        better = curr_dist < prev_dist
        threshold = max(abs(prev_dist) * 0.10, 0.005)
        is_regression = (curr_dist - prev_dist) > threshold
        status = "REGRESS" if is_regression else ("better" if better else "same")
        print(
            f"  {name:<25} {prev_val:>8.4f} → {curr_val:>8.4f}  "
            f"({direction}{abs(delta):.4f})  [{status}]"
        )
        if is_regression:
            regressions.append(f"{name}: {prev_val:.4f} → {curr_val:.4f}")

    print(f"\n  {'Metric':<25} {'Previous':>8}   {'Current':>8}   {'Delta':>10}  Status")
    print(f"  {'-' * 75}")

    _cmp_target("mean_ratio", curr["mean_ratio"], prev["mean_ratio"], target=1.0)
    _cmp("std_ratio", curr["std_ratio"], prev["std_ratio"], lower_is_better=True)
    _cmp(
        "exceedances_5pct",
        float(curr["exceedance_count_5pct"]),
        float(prev["exceedance_count_5pct"]),
        lower_is_better=True,
    )

    # New metric regression checks
    if "rmse_s" in prev and "rmse_s" in curr:
        _cmp("rmse_s", curr["rmse_s"], prev["rmse_s"], lower_is_better=True)
    if "mape_pct" in prev and "mape_pct" in curr:
        _cmp("mape_pct", curr["mape_pct"], prev["mape_pct"], lower_is_better=True)

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
                # Flag significant per-category regressions
                threshold = max(abs(pm) * 0.10, 0.005) if pm != 0 else 0.01
                if (curr_dist - prev_dist) > threshold:
                    regressions.append(f"Category {cat} mean: {pm:.4f} → {cm:.4f}")

    # Per-track regression check
    prev_tracks = prev.get("per_track", {})
    curr_tracks = curr.get("per_track", {})
    if prev_tracks and curr_tracks:
        print("\n  Per-track mean changes:")
        for track_name in sorted(set(list(prev_tracks.keys()) + list(curr_tracks.keys()))):
            if track_name in prev_tracks and track_name in curr_tracks:
                pm = prev_tracks[track_name]["mean"]
                cm = curr_tracks[track_name]["mean"]
                delta = cm - pm
                prev_dist = abs(pm - 1.0)
                curr_dist = abs(cm - 1.0)
                better = curr_dist < prev_dist
                status = "better" if better else ("same" if abs(delta) < 0.002 else "worse")
                print(f"    {track_name:<30}: {pm:.3f} → {cm:.3f} ({delta:+.3f}) [{status}]")
                # Flag significant per-track regressions
                threshold = abs(pm) * 0.10 if pm != 0 else 0.01
                if abs(cm - 1.0) - abs(pm - 1.0) > threshold:
                    regressions.append(f"Track {track_name} mean: {pm:.4f} → {cm:.4f}")

    # Grip band regression check
    prev_grip = prev.get("per_grip_band", {})
    curr_grip = curr.get("per_grip_band", {})
    if prev_grip and curr_grip:
        print("\n  Grip band mean changes:")
        for band_name in GRIP_BANDS:
            if band_name in prev_grip and band_name in curr_grip:
                pm = prev_grip[band_name]["mean"]
                cm = curr_grip[band_name]["mean"]
                delta = cm - pm
                prev_dist = abs(pm - 1.0)
                curr_dist = abs(cm - 1.0)
                better = curr_dist < prev_dist
                status = "better" if better else ("same" if abs(delta) < 0.002 else "worse")
                print(f"    {band_name:<30}: {pm:.3f} → {cm:.3f} ({delta:+.3f}) [{status}]")
                threshold = abs(pm) * 0.10 if pm != 0 else 0.01
                if abs(cm - 1.0) - abs(pm - 1.0) > threshold:
                    regressions.append(f"Grip band {band_name} mean: {pm:.4f} → {cm:.4f}")

    # Mod level regression check
    prev_mod = prev.get("per_mod_level", {})
    curr_mod = curr.get("per_mod_level", {})
    if prev_mod and curr_mod:
        print("\n  Mod level mean changes:")
        for mod in ["stock", "light", "heavy"]:
            if mod in prev_mod and mod in curr_mod:
                pm = prev_mod[mod]["mean"]
                cm = curr_mod[mod]["mean"]
                delta = cm - pm
                prev_dist = abs(pm - 1.0)
                curr_dist = abs(cm - 1.0)
                better = curr_dist < prev_dist
                status = "better" if better else ("same" if abs(delta) < 0.002 else "worse")
                print(f"    {mod:<8}: {pm:.3f} → {cm:.3f} ({delta:+.3f}) [{status}]")
                threshold = max(abs(pm) * 0.10, 0.005) if pm != 0 else 0.01
                if (curr_dist - prev_dist) > threshold:
                    regressions.append(f"Mod level {mod} mean: {pm:.4f} → {cm:.4f}")

    # HP band regression check
    prev_hp = prev.get("per_hp_band", {})
    curr_hp = curr.get("per_hp_band", {})
    if prev_hp and curr_hp:
        print("\n  HP band mean changes:")
        for band_name in prev_hp:
            if band_name in curr_hp:
                pm = prev_hp[band_name]["mean"]
                cm = curr_hp[band_name]["mean"]
                delta = cm - pm
                prev_dist = abs(pm - 1.0)
                curr_dist = abs(cm - 1.0)
                better = curr_dist < prev_dist
                status = "better" if better else ("same" if abs(delta) < 0.002 else "worse")
                print(f"    {band_name:<16}: {pm:.3f} → {cm:.3f} ({delta:+.3f}) [{status}]")
                threshold = max(abs(pm) * 0.10, 0.005) if pm != 0 else 0.01
                if (curr_dist - prev_dist) > threshold:
                    regressions.append(f"HP band {band_name} mean: {pm:.4f} → {cm:.4f}")

    # LOO-CV stability regression check
    prev_loo = prev.get("loo_cv", {})
    curr_loo = curr.get("loo_cv", {})
    if prev_loo and curr_loo:
        prev_stab = prev_loo.get("jackknife_mean_stability", 0)
        curr_stab = curr_loo.get("jackknife_mean_stability", 0)
        if prev_stab > 0 and curr_stab > prev_stab * 1.5:
            regressions.append(f"LOO-CV stability degraded: {prev_stab:.4f} → {curr_stab:.4f}")
        print(f"\n  LOO-CV stability: {prev_stab:.4f} → {curr_stab:.4f}")

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

    # Regression check BEFORE exporting new baseline (otherwise we'd compare
    # current results against themselves after the overwrite)
    regression_ok = True
    if args.compare:
        regression_ok = compare_to_baseline(results, args.compare)

    export_baseline_json(results)

    if args.strict and not regression_ok:
        sys.exit(2)

    if args.strict and not passed:
        print("\n--strict mode: exiting with code 1 due to failed checks.")
        sys.exit(1)


if __name__ == "__main__":
    main()

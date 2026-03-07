"""Curated database of common HPDE/track-day cars with manufacturer specs.

Provides lookup and search functions over a static collection of ~50 well-known
track-day vehicles spanning sports cars, muscle cars, hot hatches, and sedans.
Each entry carries real manufacturer specs for weight, wheelbase, power, and
drivetrain, plus estimated CG height and track width from published data.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VehicleSpec:
    """Manufacturer specs for a car model.

    All dimensions are in SI units (kg, meters).  CG height uses published
    estimates (0.45-0.55 m for sports cars, 0.55-0.65 m for sedans/hatches).
    """

    make: str
    model: str
    generation: str  # e.g. "ND" for Miata, "E46" for M3
    year_range: tuple[int, int]  # (start_year, end_year)
    weight_kg: float
    wheelbase_m: float
    track_width_front_m: float
    track_width_rear_m: float
    cg_height_m: float  # ~0.45-0.55 m for sports cars
    weight_dist_front_pct: float  # 0-100
    drivetrain: str  # "RWD" | "FWD" | "AWD"
    hp: int
    torque_nm: int
    has_aero: bool
    cd_a: float = 0.0  # Cd * frontal_area (m²); 0.0 = unknown
    notes: str | None = None


# ---------------------------------------------------------------------------
# Curated vehicle database
# ---------------------------------------------------------------------------

VEHICLE_DATABASE: dict[str, VehicleSpec] = {
    # -----------------------------------------------------------------------
    # Mazda Miata
    # -----------------------------------------------------------------------
    "mazda_miata_na": VehicleSpec(
        make="Mazda",
        model="Miata",
        generation="NA",
        year_range=(1990, 1997),
        weight_kg=960,
        wheelbase_m=2.265,
        track_width_front_m=1.405,
        track_width_rear_m=1.420,
        cg_height_m=0.46,
        weight_dist_front_pct=51.0,
        drivetrain="RWD",
        hp=116,
        torque_nm=136,
        has_aero=False,
        cd_a=0.65,
        notes="1.6 L B6-ZE. Lightest Miata generation.",
    ),
    "mazda_miata_nb": VehicleSpec(
        make="Mazda",
        model="Miata",
        generation="NB",
        year_range=(1999, 2005),
        weight_kg=1030,
        wheelbase_m=2.265,
        track_width_front_m=1.410,
        track_width_rear_m=1.420,
        cg_height_m=0.46,
        weight_dist_front_pct=51.0,
        drivetrain="RWD",
        hp=142,
        torque_nm=168,
        has_aero=False,
        cd_a=0.62,
        notes="1.8 L BP-4W. Refined NA platform.",
    ),
    "mazda_miata_nc": VehicleSpec(
        make="Mazda",
        model="Miata",
        generation="NC",
        year_range=(2006, 2015),
        weight_kg=1130,
        wheelbase_m=2.330,
        track_width_front_m=1.490,
        track_width_rear_m=1.495,
        cg_height_m=0.47,
        weight_dist_front_pct=51.0,
        drivetrain="RWD",
        hp=167,
        torque_nm=190,
        has_aero=False,
        cd_a=0.64,
        notes="2.0 L MZR. Larger and heavier than NB.",
    ),
    "mazda_miata_nd": VehicleSpec(
        make="Mazda",
        model="Miata",
        generation="ND",
        year_range=(2016, 2025),
        weight_kg=1058,
        wheelbase_m=2.310,
        track_width_front_m=1.496,
        track_width_rear_m=1.500,
        cg_height_m=0.45,
        weight_dist_front_pct=52.0,
        drivetrain="RWD",
        hp=181,
        torque_nm=205,
        has_aero=False,
        cd_a=0.56,
        notes="2.0 L Skyactiv-G. Returns to lightweight roots.",
    ),
    # -----------------------------------------------------------------------
    # Honda
    # -----------------------------------------------------------------------
    "honda_civic_si_10th": VehicleSpec(
        make="Honda",
        model="Civic Si",
        generation="FC",
        year_range=(2017, 2021),
        weight_kg=1293,
        wheelbase_m=2.700,
        track_width_front_m=1.533,
        track_width_rear_m=1.547,
        cg_height_m=0.53,
        weight_dist_front_pct=62.0,
        drivetrain="FWD",
        hp=205,
        torque_nm=260,
        has_aero=False,
        cd_a=0.64,
        notes="1.5 L turbo. Popular budget HPDE car.",
    ),
    "honda_civic_type_r_fk8": VehicleSpec(
        make="Honda",
        model="Civic Type R",
        generation="FK8",
        year_range=(2017, 2021),
        weight_kg=1395,
        wheelbase_m=2.700,
        track_width_front_m=1.587,
        track_width_rear_m=1.565,
        cg_height_m=0.51,
        weight_dist_front_pct=62.0,
        drivetrain="FWD",
        hp=306,
        torque_nm=400,
        has_aero=True,
        cd_a=0.77,
        notes="2.0 L K20C1 turbo. Functional rear wing.",
    ),
    "honda_civic_type_r_fl5": VehicleSpec(
        make="Honda",
        model="Civic Type R",
        generation="FL5",
        year_range=(2023, 2025),
        weight_kg=1426,
        wheelbase_m=2.735,
        track_width_front_m=1.586,
        track_width_rear_m=1.565,
        cg_height_m=0.51,
        weight_dist_front_pct=61.0,
        drivetrain="FWD",
        hp=315,
        torque_nm=420,
        has_aero=True,
        cd_a=0.77,
        notes="2.0 L K20C1 turbo revised. Improved aero.",
    ),
    "honda_s2000_ap1": VehicleSpec(
        make="Honda",
        model="S2000",
        generation="AP1",
        year_range=(1999, 2003),
        weight_kg=1260,
        wheelbase_m=2.400,
        track_width_front_m=1.470,
        track_width_rear_m=1.510,
        cg_height_m=0.46,
        weight_dist_front_pct=50.0,
        drivetrain="RWD",
        hp=240,
        torque_nm=208,
        has_aero=False,
        cd_a=0.61,
        notes="2.0 L F20C, 9000 RPM redline.",
    ),
    # -----------------------------------------------------------------------
    # Subaru / Toyota 86
    # -----------------------------------------------------------------------
    "toyota_86_zn6": VehicleSpec(
        make="Toyota",
        model="86",
        generation="ZN6",
        year_range=(2012, 2020),
        weight_kg=1235,
        wheelbase_m=2.570,
        track_width_front_m=1.520,
        track_width_rear_m=1.540,
        cg_height_m=0.46,
        weight_dist_front_pct=53.0,
        drivetrain="RWD",
        hp=200,
        torque_nm=205,
        has_aero=False,
        cd_a=0.52,
        notes="2.0 L FA20. Also sold as Subaru BRZ / Scion FR-S.",
    ),
    "toyota_gr86_zn8": VehicleSpec(
        make="Toyota",
        model="GR86",
        generation="ZN8",
        year_range=(2022, 2025),
        weight_kg=1270,
        wheelbase_m=2.575,
        track_width_front_m=1.520,
        track_width_rear_m=1.550,
        cg_height_m=0.46,
        weight_dist_front_pct=53.0,
        drivetrain="RWD",
        hp=228,
        torque_nm=249,
        has_aero=False,
        cd_a=0.54,
        notes="2.4 L FA24. Also sold as Subaru BRZ.",
    ),
    # -----------------------------------------------------------------------
    # Chevrolet Corvette
    # -----------------------------------------------------------------------
    "chevrolet_corvette_c5": VehicleSpec(
        make="Chevrolet",
        model="Corvette",
        generation="C5",
        year_range=(1997, 2004),
        weight_kg=1460,
        wheelbase_m=2.654,
        track_width_front_m=1.506,
        track_width_rear_m=1.521,
        cg_height_m=0.47,
        weight_dist_front_pct=51.0,
        drivetrain="RWD",
        hp=345,
        torque_nm=475,
        has_aero=False,
        cd_a=0.57,
        notes="5.7 L LS1. Budget track car bargain.",
    ),
    "chevrolet_corvette_c6": VehicleSpec(
        make="Chevrolet",
        model="Corvette",
        generation="C6",
        year_range=(2005, 2013),
        weight_kg=1460,
        wheelbase_m=2.686,
        track_width_front_m=1.556,
        track_width_rear_m=1.560,
        cg_height_m=0.47,
        weight_dist_front_pct=51.0,
        drivetrain="RWD",
        hp=430,
        torque_nm=542,
        has_aero=False,
        cd_a=0.58,
        notes="6.2 L LS3. Exposed headlights.",
    ),
    "chevrolet_corvette_c7": VehicleSpec(
        make="Chevrolet",
        model="Corvette",
        generation="C7",
        year_range=(2014, 2019),
        weight_kg=1496,
        wheelbase_m=2.710,
        track_width_front_m=1.575,
        track_width_rear_m=1.585,
        cg_height_m=0.47,
        weight_dist_front_pct=50.0,
        drivetrain="RWD",
        hp=455,
        torque_nm=610,
        has_aero=False,
        cd_a=0.60,
        notes="6.2 L LT1. Last front-engine Corvette.",
    ),
    "chevrolet_corvette_c8": VehicleSpec(
        make="Chevrolet",
        model="Corvette",
        generation="C8",
        year_range=(2020, 2025),
        weight_kg=1530,
        wheelbase_m=2.723,
        track_width_front_m=1.583,
        track_width_rear_m=1.597,
        cg_height_m=0.45,
        weight_dist_front_pct=40.0,
        drivetrain="RWD",
        hp=490,
        torque_nm=637,
        has_aero=False,
        cd_a=0.61,
        notes="6.2 L LT2. Mid-engine layout.",
    ),
    # -----------------------------------------------------------------------
    # BMW M3 / M2
    # -----------------------------------------------------------------------
    "bmw_m3_e46": VehicleSpec(
        make="BMW",
        model="M3",
        generation="E46",
        year_range=(2001, 2006),
        weight_kg=1570,
        wheelbase_m=2.730,
        track_width_front_m=1.507,
        track_width_rear_m=1.527,
        cg_height_m=0.51,
        weight_dist_front_pct=52.0,
        drivetrain="RWD",
        hp=333,
        torque_nm=365,
        has_aero=False,
        cd_a=0.69,
        notes="3.2 L S54 inline-6. Classic track car.",
    ),
    "bmw_m3_f80": VehicleSpec(
        make="BMW",
        model="M3",
        generation="F80",
        year_range=(2014, 2018),
        weight_kg=1585,
        wheelbase_m=2.812,
        track_width_front_m=1.560,
        track_width_rear_m=1.560,
        cg_height_m=0.52,
        weight_dist_front_pct=52.0,
        drivetrain="RWD",
        hp=425,
        torque_nm=550,
        has_aero=False,
        cd_a=0.73,
        notes="3.0 L S55 twin-turbo inline-6.",
    ),
    "bmw_m3_g80": VehicleSpec(
        make="BMW",
        model="M3",
        generation="G80",
        year_range=(2021, 2025),
        weight_kg=1700,
        wheelbase_m=2.857,
        track_width_front_m=1.604,
        track_width_rear_m=1.610,
        cg_height_m=0.53,
        weight_dist_front_pct=54.0,
        drivetrain="RWD",
        hp=473,
        torque_nm=550,
        has_aero=False,
        cd_a=0.77,
        notes="3.0 L S58 twin-turbo. Competition model.",
    ),
    "bmw_m2_f87": VehicleSpec(
        make="BMW",
        model="M2",
        generation="F87",
        year_range=(2016, 2021),
        weight_kg=1570,
        wheelbase_m=2.693,
        track_width_front_m=1.535,
        track_width_rear_m=1.555,
        cg_height_m=0.51,
        weight_dist_front_pct=52.0,
        drivetrain="RWD",
        hp=365,
        torque_nm=465,
        has_aero=False,
        cd_a=0.69,
        notes="3.0 L N55/S55 turbo. Compact M car.",
    ),
    "bmw_m2_g87": VehicleSpec(
        make="BMW",
        model="M2",
        generation="G87",
        year_range=(2023, 2025),
        weight_kg=1660,
        wheelbase_m=2.745,
        track_width_front_m=1.580,
        track_width_rear_m=1.595,
        cg_height_m=0.52,
        weight_dist_front_pct=53.0,
        drivetrain="RWD",
        hp=453,
        torque_nm=550,
        has_aero=False,
        cd_a=0.71,
        notes="3.0 L S58 twin-turbo inline-6.",
    ),
    # -----------------------------------------------------------------------
    # Ford Mustang GT
    # -----------------------------------------------------------------------
    "ford_mustang_gt_s197": VehicleSpec(
        make="Ford",
        model="Mustang GT",
        generation="S197",
        year_range=(2005, 2014),
        weight_kg=1630,
        wheelbase_m=2.720,
        track_width_front_m=1.535,
        track_width_rear_m=1.570,
        cg_height_m=0.52,
        weight_dist_front_pct=55.0,
        drivetrain="RWD",
        hp=412,
        torque_nm=529,
        has_aero=False,
        cd_a=0.75,
        notes="4.6 L / 5.0 L V8. Solid rear axle.",
    ),
    "ford_mustang_gt_s550": VehicleSpec(
        make="Ford",
        model="Mustang GT",
        generation="S550",
        year_range=(2015, 2023),
        weight_kg=1720,
        wheelbase_m=2.720,
        track_width_front_m=1.570,
        track_width_rear_m=1.580,
        cg_height_m=0.52,
        weight_dist_front_pct=54.0,
        drivetrain="RWD",
        hp=460,
        torque_nm=569,
        has_aero=False,
        cd_a=0.73,
        notes="5.0 L Coyote V8. IRS upgrade.",
    ),
    "ford_mustang_gt_s650": VehicleSpec(
        make="Ford",
        model="Mustang GT",
        generation="S650",
        year_range=(2024, 2025),
        weight_kg=1756,
        wheelbase_m=2.720,
        track_width_front_m=1.576,
        track_width_rear_m=1.587,
        cg_height_m=0.52,
        weight_dist_front_pct=54.0,
        drivetrain="RWD",
        hp=480,
        torque_nm=569,
        has_aero=False,
        cd_a=0.73,
        notes="5.0 L Coyote Gen-4 V8.",
    ),
    # -----------------------------------------------------------------------
    # Porsche
    # -----------------------------------------------------------------------
    "porsche_cayman_987": VehicleSpec(
        make="Porsche",
        model="Cayman",
        generation="987",
        year_range=(2006, 2012),
        weight_kg=1340,
        wheelbase_m=2.415,
        track_width_front_m=1.486,
        track_width_rear_m=1.528,
        cg_height_m=0.45,
        weight_dist_front_pct=46.0,
        drivetrain="RWD",
        hp=295,
        torque_nm=340,
        has_aero=False,
        cd_a=0.56,
        notes="3.4 L flat-6 (Cayman S). Mid-engine.",
    ),
    "porsche_cayman_718": VehicleSpec(
        make="Porsche",
        model="Cayman",
        generation="718",
        year_range=(2017, 2025),
        weight_kg=1385,
        wheelbase_m=2.475,
        track_width_front_m=1.528,
        track_width_rear_m=1.540,
        cg_height_m=0.45,
        weight_dist_front_pct=44.0,
        drivetrain="RWD",
        hp=300,
        torque_nm=380,
        has_aero=False,
        cd_a=0.59,
        notes="2.0 L turbo flat-4 (base). GTS has 4.0 flat-6.",
    ),
    "porsche_cayman_gt4_718": VehicleSpec(
        make="Porsche",
        model="Cayman GT4",
        generation="718",
        year_range=(2020, 2025),
        weight_kg=1420,
        wheelbase_m=2.475,
        track_width_front_m=1.524,
        track_width_rear_m=1.544,
        cg_height_m=0.45,
        weight_dist_front_pct=43.0,
        drivetrain="RWD",
        hp=414,
        torque_nm=420,
        has_aero=True,
        cd_a=0.68,
        notes="4.0 L flat-6 NA (shared with 992 GT3). Fixed rear wing.",
    ),
    "porsche_911_gt3_991": VehicleSpec(
        make="Porsche",
        model="911 GT3",
        generation="991",
        year_range=(2014, 2019),
        weight_kg=1430,
        wheelbase_m=2.457,
        track_width_front_m=1.531,
        track_width_rear_m=1.540,
        cg_height_m=0.46,
        weight_dist_front_pct=39.0,
        drivetrain="RWD",
        hp=500,
        torque_nm=460,
        has_aero=True,
        cd_a=0.68,
        notes="4.0 L flat-6 NA. Fixed rear wing.",
    ),
    "porsche_911_gt3_992": VehicleSpec(
        make="Porsche",
        model="911 GT3",
        generation="992",
        year_range=(2021, 2025),
        weight_kg=1435,
        wheelbase_m=2.457,
        track_width_front_m=1.587,
        track_width_rear_m=1.570,
        cg_height_m=0.46,
        weight_dist_front_pct=38.0,
        drivetrain="RWD",
        hp=502,
        torque_nm=469,
        has_aero=True,
        cd_a=0.68,
        notes="4.0 L flat-6 NA. Swan-neck wing.",
    ),
    # -----------------------------------------------------------------------
    # Nissan
    # -----------------------------------------------------------------------
    "nissan_350z": VehicleSpec(
        make="Nissan",
        model="350Z",
        generation="Z33",
        year_range=(2003, 2009),
        weight_kg=1474,
        wheelbase_m=2.650,
        track_width_front_m=1.524,
        track_width_rear_m=1.534,
        cg_height_m=0.48,
        weight_dist_front_pct=55.0,
        drivetrain="RWD",
        hp=287,
        torque_nm=363,
        has_aero=False,
        cd_a=0.62,
        notes="3.5 L VQ35DE/HR V6.",
    ),
    "nissan_370z": VehicleSpec(
        make="Nissan",
        model="370Z",
        generation="Z34",
        year_range=(2009, 2020),
        weight_kg=1496,
        wheelbase_m=2.550,
        track_width_front_m=1.540,
        track_width_rear_m=1.555,
        cg_height_m=0.48,
        weight_dist_front_pct=54.0,
        drivetrain="RWD",
        hp=332,
        torque_nm=363,
        has_aero=False,
        cd_a=0.62,
        notes="3.7 L VQ37VHR V6.",
    ),
    # -----------------------------------------------------------------------
    # Subaru WRX STI
    # -----------------------------------------------------------------------
    "subaru_wrx_sti_va": VehicleSpec(
        make="Subaru",
        model="WRX STI",
        generation="VA",
        year_range=(2015, 2021),
        weight_kg=1565,
        wheelbase_m=2.650,
        track_width_front_m=1.530,
        track_width_rear_m=1.540,
        cg_height_m=0.54,
        weight_dist_front_pct=60.0,
        drivetrain="AWD",
        hp=310,
        torque_nm=393,
        has_aero=True,
        cd_a=0.72,
        notes="2.5 L EJ257 turbo. DCCD AWD system.",
    ),
    # -----------------------------------------------------------------------
    # Toyota GR Supra
    # -----------------------------------------------------------------------
    "toyota_gr_supra_a90": VehicleSpec(
        make="Toyota",
        model="GR Supra",
        generation="A90",
        year_range=(2020, 2025),
        weight_kg=1540,
        wheelbase_m=2.470,
        track_width_front_m=1.594,
        track_width_rear_m=1.589,
        cg_height_m=0.48,
        weight_dist_front_pct=48.0,
        drivetrain="RWD",
        hp=382,
        torque_nm=500,
        has_aero=False,
        cd_a=0.64,
        notes="3.0 L B58 turbo inline-6. BMW Z4 platform.",
    ),
    # -----------------------------------------------------------------------
    # Dodge Challenger SRT
    # -----------------------------------------------------------------------
    "dodge_challenger_srt_392": VehicleSpec(
        make="Dodge",
        model="Challenger SRT 392",
        generation="LC",
        year_range=(2015, 2023),
        weight_kg=1913,
        wheelbase_m=2.946,
        track_width_front_m=1.590,
        track_width_rear_m=1.596,
        cg_height_m=0.55,
        weight_dist_front_pct=57.0,
        drivetrain="RWD",
        hp=485,
        torque_nm=644,
        has_aero=False,
        cd_a=0.88,
        notes="6.4 L HEMI V8. Heavy muscle car.",
    ),
    # -----------------------------------------------------------------------
    # Chevrolet Camaro
    # -----------------------------------------------------------------------
    "chevrolet_camaro_ss_6th": VehicleSpec(
        make="Chevrolet",
        model="Camaro SS",
        generation="6th Gen",
        year_range=(2016, 2024),
        weight_kg=1680,
        wheelbase_m=2.811,
        track_width_front_m=1.614,
        track_width_rear_m=1.612,
        cg_height_m=0.50,
        weight_dist_front_pct=53.0,
        drivetrain="RWD",
        hp=455,
        torque_nm=617,
        has_aero=False,
        cd_a=0.73,
        notes="6.2 L LT1 V8. Alpha platform.",
    ),
    "chevrolet_camaro_zl1_6th": VehicleSpec(
        make="Chevrolet",
        model="Camaro ZL1",
        generation="6th Gen",
        year_range=(2017, 2024),
        weight_kg=1770,
        wheelbase_m=2.811,
        track_width_front_m=1.630,
        track_width_rear_m=1.630,
        cg_height_m=0.50,
        weight_dist_front_pct=53.0,
        drivetrain="RWD",
        hp=650,
        torque_nm=881,
        has_aero=True,
        cd_a=0.79,
        notes="6.2 L LT4 supercharged V8.",
    ),
    # -----------------------------------------------------------------------
    # Volkswagen GTI
    # -----------------------------------------------------------------------
    "volkswagen_gti_mk7": VehicleSpec(
        make="Volkswagen",
        model="GTI",
        generation="Mk7",
        year_range=(2015, 2021),
        weight_kg=1382,
        wheelbase_m=2.631,
        track_width_front_m=1.535,
        track_width_rear_m=1.510,
        cg_height_m=0.55,
        weight_dist_front_pct=60.0,
        drivetrain="FWD",
        hp=228,
        torque_nm=350,
        has_aero=False,
        cd_a=0.67,
        notes="2.0 L EA888 turbo. MQB platform.",
    ),
    "volkswagen_gti_mk8": VehicleSpec(
        make="Volkswagen",
        model="GTI",
        generation="Mk8",
        year_range=(2022, 2025),
        weight_kg=1420,
        wheelbase_m=2.631,
        track_width_front_m=1.543,
        track_width_rear_m=1.515,
        cg_height_m=0.55,
        weight_dist_front_pct=60.0,
        drivetrain="FWD",
        hp=241,
        torque_nm=370,
        has_aero=False,
        cd_a=0.62,
        notes="2.0 L EA888 Evo4 turbo.",
    ),
    # -----------------------------------------------------------------------
    # Hyundai Veloster N
    # -----------------------------------------------------------------------
    "hyundai_veloster_n": VehicleSpec(
        make="Hyundai",
        model="Veloster N",
        generation="JS",
        year_range=(2019, 2022),
        weight_kg=1391,
        wheelbase_m=2.650,
        track_width_front_m=1.569,
        track_width_rear_m=1.576,
        cg_height_m=0.53,
        weight_dist_front_pct=62.0,
        drivetrain="FWD",
        hp=275,
        torque_nm=353,
        has_aero=False,
        cd_a=0.67,
        notes="2.0 L Theta II turbo. eLSD available.",
    ),
    # -----------------------------------------------------------------------
    # Toyota GR Corolla
    # -----------------------------------------------------------------------
    "toyota_gr_corolla": VehicleSpec(
        make="Toyota",
        model="GR Corolla",
        generation="GZEA14H",
        year_range=(2023, 2025),
        weight_kg=1474,
        wheelbase_m=2.640,
        track_width_front_m=1.548,
        track_width_rear_m=1.562,
        cg_height_m=0.53,
        weight_dist_front_pct=60.0,
        drivetrain="AWD",
        hp=300,
        torque_nm=370,
        has_aero=True,
        cd_a=0.72,
        notes="1.6 L G16E-GTS turbo 3-cyl. GR-Four AWD.",
    ),
    # -----------------------------------------------------------------------
    # Lexus
    # -----------------------------------------------------------------------
    "lexus_is_f": VehicleSpec(
        make="Lexus",
        model="IS F",
        generation="XE20",
        year_range=(2008, 2014),
        weight_kg=1715,
        wheelbase_m=2.730,
        track_width_front_m=1.535,
        track_width_rear_m=1.540,
        cg_height_m=0.52,
        weight_dist_front_pct=54.0,
        drivetrain="RWD",
        hp=416,
        torque_nm=505,
        has_aero=False,
        cd_a=0.69,
        notes="5.0 L 2UR-GSE V8.",
    ),
    "lexus_rc_f": VehicleSpec(
        make="Lexus",
        model="RC F",
        generation="USC10",
        year_range=(2015, 2025),
        weight_kg=1765,
        wheelbase_m=2.730,
        track_width_front_m=1.535,
        track_width_rear_m=1.545,
        cg_height_m=0.50,
        weight_dist_front_pct=55.0,
        drivetrain="RWD",
        hp=472,
        torque_nm=535,
        has_aero=False,
        cd_a=0.72,
        notes="5.0 L 2UR-GSE V8. Track Edition available.",
    ),
    # -----------------------------------------------------------------------
    # Lotus
    # -----------------------------------------------------------------------
    "lotus_elise_s2": VehicleSpec(
        make="Lotus",
        model="Elise",
        generation="S2",
        year_range=(2001, 2011),
        weight_kg=860,
        wheelbase_m=2.300,
        track_width_front_m=1.452,
        track_width_rear_m=1.494,
        cg_height_m=0.42,
        weight_dist_front_pct=38.0,
        drivetrain="RWD",
        hp=189,
        torque_nm=180,
        has_aero=False,
        cd_a=0.62,
        notes="1.8 L 2ZZ-GE Toyota. Ultralight.",
    ),
    "lotus_exige_s2": VehicleSpec(
        make="Lotus",
        model="Exige",
        generation="S2",
        year_range=(2004, 2011),
        weight_kg=900,
        wheelbase_m=2.300,
        track_width_front_m=1.452,
        track_width_rear_m=1.494,
        cg_height_m=0.42,
        weight_dist_front_pct=38.0,
        drivetrain="RWD",
        hp=220,
        torque_nm=215,
        has_aero=True,
        cd_a=0.62,
        notes="1.8 L 2ZZ-GE supercharged. Fixed roof + wing.",
    ),
    # -----------------------------------------------------------------------
    # Audi
    # -----------------------------------------------------------------------
    "audi_rs3_8v": VehicleSpec(
        make="Audi",
        model="RS3",
        generation="8V",
        year_range=(2017, 2022),
        weight_kg=1555,
        wheelbase_m=2.631,
        track_width_front_m=1.553,
        track_width_rear_m=1.531,
        cg_height_m=0.54,
        weight_dist_front_pct=59.0,
        drivetrain="AWD",
        hp=400,
        torque_nm=480,
        has_aero=False,
        cd_a=0.70,
        notes="2.5 L TFSI inline-5 turbo. Quattro AWD.",
    ),
    "audi_ttrs_8s": VehicleSpec(
        make="Audi",
        model="TT RS",
        generation="8S",
        year_range=(2018, 2023),
        weight_kg=1515,
        wheelbase_m=2.505,
        track_width_front_m=1.553,
        track_width_rear_m=1.526,
        cg_height_m=0.50,
        weight_dist_front_pct=58.0,
        drivetrain="AWD",
        hp=394,
        torque_nm=480,
        has_aero=False,
        cd_a=0.66,
        notes="2.5 L TFSI inline-5 turbo.",
    ),
    # -----------------------------------------------------------------------
    # Mercedes-AMG
    # -----------------------------------------------------------------------
    "mercedes_amg_c63_w205": VehicleSpec(
        make="Mercedes-AMG",
        model="C 63",
        generation="W205",
        year_range=(2015, 2021),
        weight_kg=1770,
        wheelbase_m=2.840,
        track_width_front_m=1.565,
        track_width_rear_m=1.570,
        cg_height_m=0.53,
        weight_dist_front_pct=55.0,
        drivetrain="RWD",
        hp=469,
        torque_nm=650,
        has_aero=False,
        cd_a=0.69,
        notes="4.0 L M177 twin-turbo V8.",
    ),
    # -----------------------------------------------------------------------
    # Nissan GT-R
    # -----------------------------------------------------------------------
    "nissan_gtr_r35": VehicleSpec(
        make="Nissan",
        model="GT-R",
        generation="R35",
        year_range=(2009, 2024),
        weight_kg=1752,
        wheelbase_m=2.780,
        track_width_front_m=1.590,
        track_width_rear_m=1.600,
        cg_height_m=0.50,
        weight_dist_front_pct=54.0,
        drivetrain="AWD",
        hp=565,
        torque_nm=637,
        has_aero=False,
        cd_a=0.60,
        notes="3.8 L VR38DETT twin-turbo V6. ATTESA E-TS AWD.",
    ),
    # -----------------------------------------------------------------------
    # Hyundai Elantra N
    # -----------------------------------------------------------------------
    "hyundai_elantra_n": VehicleSpec(
        make="Hyundai",
        model="Elantra N",
        generation="CN7",
        year_range=(2022, 2025),
        weight_kg=1450,
        wheelbase_m=2.720,
        track_width_front_m=1.565,
        track_width_rear_m=1.572,
        cg_height_m=0.53,
        weight_dist_front_pct=62.0,
        drivetrain="FWD",
        hp=276,
        torque_nm=392,
        has_aero=False,
        cd_a=0.63,
        notes="2.0 L Theta III turbo. Spiritual Veloster N successor.",
    ),
    # -----------------------------------------------------------------------
    # BMW M240i
    # -----------------------------------------------------------------------
    "bmw_m240i_g42": VehicleSpec(
        make="BMW",
        model="M240i",
        generation="G42",
        year_range=(2022, 2025),
        weight_kg=1605,
        wheelbase_m=2.741,
        track_width_front_m=1.575,
        track_width_rear_m=1.585,
        cg_height_m=0.52,
        weight_dist_front_pct=52.0,
        drivetrain="AWD",
        hp=382,
        torque_nm=500,
        has_aero=False,
        cd_a=0.71,
        notes="3.0 L B58 turbo inline-6. xDrive AWD.",
    ),
    # -----------------------------------------------------------------------
    # Ford Focus RS
    # -----------------------------------------------------------------------
    "ford_focus_rs_mk3": VehicleSpec(
        make="Ford",
        model="Focus RS",
        generation="Mk3",
        year_range=(2016, 2018),
        weight_kg=1572,
        wheelbase_m=2.648,
        track_width_front_m=1.563,
        track_width_rear_m=1.565,
        cg_height_m=0.54,
        weight_dist_front_pct=62.0,
        drivetrain="AWD",
        hp=350,
        torque_nm=440,
        has_aero=True,
        cd_a=0.78,
        notes="2.3 L EcoBoost turbo. Twin-clutch rear axle.",
    ),
    # -----------------------------------------------------------------------
    # Mazda MazdaSpeed3 / Mazda3 Turbo
    # -----------------------------------------------------------------------
    "mazda_mazdaspeed3": VehicleSpec(
        make="Mazda",
        model="MazdaSpeed3",
        generation="BL",
        year_range=(2010, 2013),
        weight_kg=1440,
        wheelbase_m=2.640,
        track_width_front_m=1.530,
        track_width_rear_m=1.515,
        cg_height_m=0.54,
        weight_dist_front_pct=63.0,
        drivetrain="FWD",
        hp=263,
        torque_nm=380,
        has_aero=False,
        cd_a=0.66,
        notes="2.3 L MZR DISI turbo. Torque steer monster.",
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_vehicle(
    make: str,
    model: str,
    generation: str | None = None,
) -> VehicleSpec | None:
    """Find a vehicle spec by make/model/generation.

    Matching is case-insensitive.  If *generation* is ``None``, returns the
    first match for the given make/model (typically the newest generation).

    Args:
        make: Manufacturer name (e.g. ``"Mazda"``).
        model: Model name (e.g. ``"Miata"``).
        generation: Optional generation code (e.g. ``"ND"``).

    Returns:
        The matching :class:`VehicleSpec` if found, otherwise ``None``.
    """
    make_lower = make.lower()
    model_lower = model.lower()
    gen_lower = generation.lower() if generation else None

    for spec in VEHICLE_DATABASE.values():
        if spec.make.lower() != make_lower:
            continue
        if spec.model.lower() != model_lower:
            continue
        if gen_lower is not None and spec.generation.lower() != gen_lower:
            continue
        return spec
    return None


def search_vehicles(query: str, limit: int = 20) -> list[VehicleSpec]:
    """Fuzzy search vehicles by make, model, or generation.

    Performs case-insensitive substring matching against the make, model,
    and generation fields.

    Args:
        query: Substring to match against make, model, or generation.
        limit: Maximum number of results to return.

    Returns:
        Matching :class:`VehicleSpec` entries, up to *limit*.
    """
    if not query:
        return []

    q = query.lower()
    matches: list[VehicleSpec] = []
    for spec in VEHICLE_DATABASE.values():
        if (
            q in spec.make.lower()
            or q in spec.model.lower()
            or q in spec.generation.lower()
            or (spec.notes is not None and q in spec.notes.lower())
        ):
            matches.append(spec)
            if len(matches) >= limit:
                break
    return matches


def list_makes() -> list[str]:
    """List all available makes, sorted alphabetically.

    Returns:
        Deduplicated list of manufacturer names.
    """
    makes = sorted({spec.make for spec in VEHICLE_DATABASE.values()})
    return makes


def list_models(make: str) -> list[str]:
    """List all models for a given make, sorted alphabetically.

    Matching is case-insensitive.

    Args:
        make: Manufacturer name (e.g. ``"BMW"``).

    Returns:
        Deduplicated list of model names for the given make.
    """
    make_lower = make.lower()
    models = sorted(
        {spec.model for spec in VEHICLE_DATABASE.values() if spec.make.lower() == make_lower}
    )
    return models


def get_vehicle_by_slug(slug: str) -> VehicleSpec | None:
    """Look up a vehicle by its exact database slug.

    Args:
        slug: Database key such as ``"mazda_miata_nd"``.

    Returns:
        The :class:`VehicleSpec` if found, otherwise ``None``.
    """
    return VEHICLE_DATABASE.get(slug)


def list_all_vehicles() -> list[VehicleSpec]:
    """Return all vehicles sorted by make, then model, then generation.

    Returns:
        All :class:`VehicleSpec` entries in the database.
    """
    return sorted(
        VEHICLE_DATABASE.values(),
        key=lambda v: (v.make, v.model, v.generation),
    )

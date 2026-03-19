"""Curated database of common track-day tires with estimated grip coefficients.

Provides lookup and search functions over a static collection of well-known
tire models spanning street, 200-treadwear, 100-treadwear, and R-compound
categories.  Each entry carries a hand-curated mu estimate sourced from
community data, GRM track tests, Tire Rack tests, and manufacturer specs.

Mu values are anchored to three well-established reference points:
  - Bridgestone RE-71RS:  1.12 (Super 200TW reference)
  - Hankook Ventus RS4:   1.00 (Endurance 200TW reference)
  - Hoosier R7:           1.38 (R-compound reference)

Other tires are placed relative to these anchors using GRM back-to-back
lap time comparisons and community consensus.  Sources:
  - Grassroots Motorsports track tire buyer's guide (2025)
  - GRM 200TW tire tests (RE-71RS vs RT660, Continental Force vs RS4)
  - Tire Rack extreme performance summer tire tests
  - HPWizard treadwear-to-mu formula as sanity check
"""

from __future__ import annotations

from cataclysm.equipment import MuSource, TireCompoundCategory, TireSpec

# ---------------------------------------------------------------------------
# Curated tire database
#
# Categories follow the GRM classification:
#   SUPER_200TW     — 200TW max-grip (GRM "Super 200s")
#   ENDURANCE_200TW — 200TW longevity focus (GRM "Endurance 200s")
#   TW_100          — 100TW semi-slicks
#   R_COMPOUND      — DOT R-compound race tires
#   STREET          — Street performance / UHP / budget track
# ---------------------------------------------------------------------------

_CURATED_TIRES: dict[str, TireSpec] = {
    # =======================================================================
    # SUPER 200TW — Maximum Grip
    # =======================================================================
    "bridgestone_re71rs": TireSpec(
        model="Bridgestone Potenza RE-71RS",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.12,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM reference tire, Tire Rack test data + community",
        brand="Bridgestone",
    ),
    "bridgestone_re71rz": TireSpec(
        model="Bridgestone Potenza RE-71RZ",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.13,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="RE-71RS successor, GRM: 'livelier on track'",
        brand="Bridgestone",
    ),
    "bridgestone_potenza_race": TireSpec(
        model="Bridgestone Potenza Race",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.10,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'consistent, high-quality laps'",
        brand="Bridgestone",
    ),
    "yokohama_a052": TireSpec(
        model="Yokohama Advan A052",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.13,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: near-RE-71RS grip, community consensus",
        brand="Yokohama",
    ),
    "bfg_rival_s": TireSpec(
        model="BFGoodrich g-Force Rival S 1.5",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.10,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM Super 200, competitive grip with longer life",
        brand="BFGoodrich",
    ),
    "falken_rt660_plus": TireSpec(
        model="Falken Azenis RT660+",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.08,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM Super 200, ~1.3s behind RE-71RS at Harris Hill",
        brand="Falken",
    ),
    "nankang_crs_v2": TireSpec(
        model="Nankang Sportnex CR-S V2",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.08,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'remarkably consistent'",
        brand="Nankang",
    ),
    "kumho_v730": TireSpec(
        model="Kumho Ecsta V730",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.06,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: drivability/consistency focus, lower peak grip",
        brand="Kumho",
    ),
    "goodyear_sc3": TireSpec(
        model="Goodyear Eagle F1 SuperCar 3",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=240,
        estimated_mu=1.12,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'grip. Lots of it.' Premium tier",
        brand="Goodyear",
    ),
    "michelin_cup2_connect": TireSpec(
        model="Michelin Pilot Sport Cup 2 Connect",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=240,
        estimated_mu=1.10,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: OE on fastest sports cars, premium compound",
        brand="Michelin",
    ),
    "nexen_nfera_sport_r": TireSpec(
        model="Nexen N'Fera Sport R",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.08,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'very quick tire off the line'",
        brand="Nexen",
    ),
    "maxxis_vr2": TireSpec(
        model="Maxxis Victra VR2",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.06,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: newer entry, performance under evaluation",
        brand="Maxxis",
    ),
    "toyo_r1r": TireSpec(
        model="Toyo Proxes R1R",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.04,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'long in the tooth, but still viable', older design",
        brand="Toyo",
    ),
    "vitour_x01r": TireSpec(
        model="Vitour Tempesta P1 X-01R",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.10,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'turns on quicker', less tolerant to heat",
        brand="Vitour",
    ),
    "vitour_p01r": TireSpec(
        model="Vitour Tempesta P1 P-01R",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.08,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'quick to turn on', abundant grip",
        brand="Vitour",
    ),
    # =======================================================================
    # ENDURANCE 200TW — Longevity Focus
    # =======================================================================
    "hankook_rs4": TireSpec(
        model="Hankook Ventus RS4",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.00,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'gold standard' endurance 200TW reference",
        brand="Hankook",
    ),
    "continental_force": TireSpec(
        model="Continental ExtremeContact Force",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.05,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'clear half-second over Hankook' at Harris Hill",
        brand="Continental",
    ),
    "continental_ecs02": TireSpec(
        model="Continental ExtremeContact Sport 02",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.02,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'can match PS4S for grip', endurance focus",
        brand="Continental",
    ),
    "yokohama_ad09": TireSpec(
        model="Yokohama Advan Neova AD09",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.03,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: no performance loss over long runs",
        brand="Yokohama",
    ),
    "falken_rt660": TireSpec(
        model="Falken Azenis RT660",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.05,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM test: ~1.3s behind RE-71RS, good longevity",
        brand="Falken",
    ),
    "bfg_rival_plus": TireSpec(
        model="BFGoodrich g-Force Rival +",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=0.98,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'forgiving to drive on track', endurance focus",
        brand="BFGoodrich",
    ),
    "maxxis_vr1": TireSpec(
        model="Maxxis Victra VR-1",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=0.98,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'super-responsive performance', endurance",
        brand="Maxxis",
    ),
    "vitour_enzo": TireSpec(
        model="Vitour Tempesta Enzo V-01R",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.03,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'superior single-lap pace' for endurance",
        brand="Vitour",
    ),
    # =======================================================================
    # STREET — Premium street sport & budget UHP
    # =======================================================================
    "michelin_ps4s": TireSpec(
        model="Michelin Pilot Sport 4S",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=300,
        estimated_mu=1.00,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Validation-calibrated: 4 track entries all point to mu≈1.00. "
        "TW 300 but performs at endurance 200TW level per GRM/ECS02 comparison",
        brand="Michelin",
    ),
    "continental_esc": TireSpec(
        model="Continental ExtremeContact Sport",
        compound_category=TireCompoundCategory.STREET,
        size="varies",
        treadwear_rating=340,
        estimated_mu=0.92,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Street-sport comparison data",
        brand="Continental",
    ),
    "michelin_ps5": TireSpec(
        model="Michelin Pilot Sport 5",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=300,
        estimated_mu=0.97,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="PS4S successor, similar grip class. Endurance-level on track",
        brand="Michelin",
    ),
    "falken_rt615k_plus": TireSpec(
        model="Falken Azenis RT615K+",
        compound_category=TireCompoundCategory.STREET,
        size="varies",
        treadwear_rating=260,
        estimated_mu=0.88,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM budget UHP: 'blends dry and wet'",
        brand="Falken",
    ),
    "bfg_phenom": TireSpec(
        model="BFGoodrich g-Force Phenom T/A",
        compound_category=TireCompoundCategory.STREET,
        size="varies",
        treadwear_rating=280,
        estimated_mu=0.87,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM budget UHP: 'lively response'",
        brand="BFGoodrich",
    ),
    "firestone_indy500": TireSpec(
        model="Firestone Firehawk Indy 500",
        compound_category=TireCompoundCategory.STREET,
        size="varies",
        treadwear_rating=280,
        estimated_mu=0.86,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM budget UHP: 'well-mannered'",
        brand="Firestone",
    ),
    "kenda_vezda_uhp": TireSpec(
        model="Kenda Vezda UHP Max+ KR20A",
        compound_category=TireCompoundCategory.STREET,
        size="varies",
        treadwear_rating=300,
        estimated_mu=0.85,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM budget UHP: entry-level track",
        brand="Kenda",
    ),
    # =======================================================================
    # 100TW — Semi-slick
    # =======================================================================
    "toyo_r888r": TireSpec(
        model="Toyo Proxes R888R",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=100,
        estimated_mu=1.22,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'optimized for dry use only', 100TW baseline",
        brand="Toyo",
    ),
    "nankang_ar1": TireSpec(
        model="Nankang AR-1",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=80,
        estimated_mu=1.25,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Budget semi-slick community data, 80TW",
        brand="Nankang",
    ),
    "nitto_nt01": TireSpec(
        model="Nitto NT01",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=100,
        estimated_mu=1.20,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'repeat that trick lap after lap', consistent",
        brand="Nitto",
    ),
    "toyo_proxes_rr": TireSpec(
        model="Toyo Proxes RR",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=40,
        estimated_mu=1.28,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 40TW, 'performs on par with 100TW competitors'",
        brand="Toyo",
    ),
    "toyo_proxes_r": TireSpec(
        model="Toyo Proxes R",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=100,
        estimated_mu=1.18,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'comparable to the Bridgestone RE-71RS'",
        brand="Toyo",
    ),
    "toyo_proxes_ra1": TireSpec(
        model="Toyo Proxes RA1",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=100,
        estimated_mu=1.18,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: tread depth sensitive, 100TW endurance",
        brand="Toyo",
    ),
    "maxxis_rc1": TireSpec(
        model="Maxxis Victra RC-1",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=100,
        estimated_mu=1.22,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'improved grip and longevity'",
        brand="Maxxis",
    ),
    # =======================================================================
    # SPECIALIZED DOT TRACK — Between 200TW and R-compound
    # =======================================================================
    "goodyear_sc3r": TireSpec(
        model="Goodyear Eagle F1 SuperCar 3R",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.20,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'magic, simply magic', bridge 200TW/R-comp",
        brand="Goodyear",
    ),
    "pirelli_trofeo_r": TireSpec(
        model="Pirelli P Zero Trofeo R",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.18,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'on pace with Goodyear SC3R'",
        brand="Pirelli",
    ),
    "hoosier_trackattack_pro": TireSpec(
        model="Hoosier TrackAttack Pro",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.18,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: competes with SC3R tier",
        brand="Hoosier",
    ),
    "vitour_sonic": TireSpec(
        model="Vitour Tempesta Sonic",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.15,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'comes alive under heavy loading'",
        brand="Vitour",
    ),
    # =======================================================================
    # SUPER 200TW — OEM Performance (non-DOT-200 but grippier than Connect)
    # =======================================================================
    "michelin_cup2": TireSpec(
        model="Michelin Pilot Sport Cup 2",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=240,
        estimated_mu=1.15,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="OEM on GT4, grippier than Cup 2 Connect (1.10)",
        brand="Michelin",
    ),
    # =======================================================================
    # STREET — Additional OEM tires
    # =======================================================================
    "michelin_ps4": TireSpec(
        model="Michelin Pilot Sport 4",
        compound_category=TireCompoundCategory.STREET,
        size="varies",
        treadwear_rating=300,
        estimated_mu=0.88,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="OEM on GR86, entry street-sport tire, lower grip than PS4S",
        brand="Michelin",
    ),
    # =======================================================================
    # R-COMPOUND — DOT race tires
    # =======================================================================
    "hoosier_r7": TireSpec(
        model="Hoosier R7",
        compound_category=TireCompoundCategory.R_COMPOUND,
        size="varies",
        treadwear_rating=40,
        estimated_mu=1.38,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="R-compound reference, road-race endurance compound",
        brand="Hoosier",
    ),
    "hoosier_a7": TireSpec(
        model="Hoosier A7",
        compound_category=TireCompoundCategory.R_COMPOUND,
        size="varies",
        treadwear_rating=40,
        estimated_mu=1.42,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Softer compound than R7, sprint/autocross optimized",
        brand="Hoosier",
    ),
    "hoosier_r8": TireSpec(
        model="Hoosier TrackAttack Race R8",
        compound_category=TireCompoundCategory.R_COMPOUND,
        size="varies",
        treadwear_rating=40,
        estimated_mu=1.35,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'easy to drive, highly consistent'",
        brand="Hoosier",
    ),
    "hoosier_a8": TireSpec(
        model="Hoosier TrackAttack Race A8",
        compound_category=TireCompoundCategory.R_COMPOUND,
        size="varies",
        treadwear_rating=40,
        estimated_mu=1.40,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: softer compound, 'required more setup work'",
        brand="Hoosier",
    ),
    "yokohama_a055": TireSpec(
        model="Yokohama Advan A055",
        compound_category=TireCompoundCategory.R_COMPOUND,
        size="varies",
        treadwear_rating=40,
        estimated_mu=1.38,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'very responsive with full grip'",
        brand="Yokohama",
    ),
    "goodyear_eagle_rs": TireSpec(
        model="Goodyear Eagle RS",
        compound_category=TireCompoundCategory.R_COMPOUND,
        size="varies",
        treadwear_rating=40,
        estimated_mu=1.40,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="GRM: 'fastest in the first one or two sessions'",
        brand="Goodyear",
    ),
    # =======================================================================
    # SLICK — Full slicks (non-DOT, no tread pattern)
    # =======================================================================
    "dunlop_dh_slick": TireSpec(
        model="Dunlop DH Slick",
        compound_category=TireCompoundCategory.SLICK,
        size="varies",
        treadwear_rating=0,
        estimated_mu=1.40,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Full slick, track-day compound. Validation-calibrated from 1.45",
        brand="Dunlop",
    ),
    "pirelli_slick_305": TireSpec(
        model="Pirelli Slick 305",
        compound_category=TireCompoundCategory.SLICK,
        size="305 square",
        treadwear_rating=0,
        estimated_mu=1.40,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Full race slick, GT/endurance fitment",
        brand="Pirelli",
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def search_curated_tires(query: str, limit: int = 10) -> list[TireSpec]:
    """Search curated tires by case-insensitive substring on model and brand.

    Args:
        query: Substring to match against model name and brand.
        limit: Maximum number of results to return.

    Returns:
        Matching :class:`TireSpec` entries, up to *limit*.
    """
    if not query:
        return []

    q = query.lower()
    matches: list[TireSpec] = []
    for tire in _CURATED_TIRES.values():
        model_match = q in tire.model.lower()
        brand_match = tire.brand is not None and q in tire.brand.lower()
        if model_match or brand_match:
            matches.append(tire)
            if len(matches) >= limit:
                break
    return matches


def get_curated_tire(slug: str) -> TireSpec | None:
    """Look up a curated tire by its exact slug identifier.

    Args:
        slug: Database key such as ``"bridgestone_re71rs"``.

    Returns:
        The :class:`TireSpec` if found, otherwise ``None``.
    """
    return _CURATED_TIRES.get(slug)


# Convenience alias used by validation scripts
lookup_tire = get_curated_tire


def list_all_curated_tires() -> list[TireSpec]:
    """Return all curated tires sorted alphabetically by model name."""
    return sorted(_CURATED_TIRES.values(), key=lambda t: t.model)


# ---------------------------------------------------------------------------
# Common tire sizes — expanded to cover most track-day fitments
# from 15" Miata/GR86 to 19" performance car sizes
# ---------------------------------------------------------------------------

COMMON_TIRE_SIZES: list[str] = [
    # 15" — Miata, small sports cars
    "195/50R15",
    "195/55R15",
    "205/50R15",
    "225/45R15",
    # 16" — GR86, BRZ, Civic, S2000
    "195/55R16",
    "205/45R16",
    "205/50R16",
    "205/55R16",
    "215/45R16",
    "225/45R16",
    "225/50R16",
    # 17" — GR86, Mustang, Camaro, WRX, Evo, GTI
    "205/40R17",
    "215/40R17",
    "215/45R17",
    "225/40R17",
    "225/45R17",
    "235/40R17",
    "235/45R17",
    "245/35R17",
    "245/40R17",
    "255/35R17",
    "255/40R17",
    "265/35R17",
    "265/40R17",
    "275/35R17",
    "275/40R17",
    "285/35R17",
    "295/35R17",
    # 18" — Corvette, 911, M3, Cayman, Supra
    "225/40R18",
    "225/45R18",
    "235/35R18",
    "235/40R18",
    "245/35R18",
    "245/40R18",
    "255/35R18",
    "255/40R18",
    "265/35R18",
    "265/40R18",
    "275/30R18",
    "275/35R18",
    "285/30R18",
    "285/35R18",
    "295/25R18",
    "295/30R18",
    "305/30R18",
    "315/30R18",
    "325/30R18",
    # 19" — GT3, AMG GT, Viper, GT500
    "235/35R19",
    "245/30R19",
    "245/35R19",
    "255/30R19",
    "255/35R19",
    "265/30R19",
    "265/35R19",
    "275/30R19",
    "275/35R19",
    "285/30R19",
    "285/35R19",
    "295/25R19",
    "295/30R19",
    "305/25R19",
    "305/30R19",
    "315/30R19",
    "325/30R19",
    # 20" — large performance sedans, GT cars
    "245/30R20",
    "255/30R20",
    "265/30R20",
    "275/30R20",
    "285/25R20",
    "285/30R20",
    "295/25R20",
    "295/30R20",
    "305/25R20",
    "305/30R20",
    "315/30R20",
    "325/25R20",
]


def list_common_tire_sizes() -> list[str]:
    """Return the list of common track-day tire sizes."""
    return list(COMMON_TIRE_SIZES)

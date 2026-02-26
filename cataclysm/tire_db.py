"""Curated database of common track-day tires with estimated grip coefficients.

Provides lookup and search functions over a static collection of well-known
tire models spanning street, 200-treadwear, 100-treadwear, and R-compound
categories.  Each entry carries a hand-curated mu estimate sourced from
community data, tire-rack tests, and manufacturer specs.
"""

from __future__ import annotations

from cataclysm.equipment import MuSource, TireCompoundCategory, TireSpec

# ---------------------------------------------------------------------------
# Curated tire database
# ---------------------------------------------------------------------------

_CURATED_TIRES: dict[str, TireSpec] = {
    "bridgestone_re71rs": TireSpec(
        model="Bridgestone Potenza RE-71RS",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.12,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Tire Rack test data + community",
        brand="Bridgestone",
    ),
    "hankook_rs4": TireSpec(
        model="Hankook Ventus RS4",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.00,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Endurance 200TW",
        brand="Hankook",
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
    "yokohama_ad09": TireSpec(
        model="Yokohama Advan Apex V601",
        compound_category=TireCompoundCategory.SUPER_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.10,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Close to RE-71RS grip",
        brand="Yokohama",
    ),
    "toyo_r888r": TireSpec(
        model="Toyo Proxes R888R",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=100,
        estimated_mu=1.22,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="100TW semi-slick track data",
        brand="Toyo",
    ),
    "nankang_ar1": TireSpec(
        model="Nankang AR-1",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=80,
        estimated_mu=1.25,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Budget semi-slick community",
        brand="Nankang",
    ),
    "hoosier_r7": TireSpec(
        model="Hoosier R7",
        compound_category=TireCompoundCategory.R_COMPOUND,
        size="varies",
        treadwear_rating=40,
        estimated_mu=1.38,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="R-compound race data",
        brand="Hoosier",
    ),
    "falken_rt660": TireSpec(
        model="Falken Azenis RT660",
        compound_category=TireCompoundCategory.ENDURANCE_200TW,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.02,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Balanced grip/longevity",
        brand="Falken",
    ),
    "michelin_ps4s": TireSpec(
        model="Michelin Pilot Sport 4S",
        compound_category=TireCompoundCategory.STREET,
        size="varies",
        treadwear_rating=300,
        estimated_mu=0.95,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Premium street sport",
        brand="Michelin",
    ),
    "bfg_rival_s": TireSpec(
        model="BFGoodrich g-Force Rival S 1.5",
        compound_category=TireCompoundCategory.TW_100,
        size="varies",
        treadwear_rating=200,
        estimated_mu=1.15,
        mu_source=MuSource.CURATED_TABLE,
        mu_confidence="Autocross/track 200TW",
        brand="BFGoodrich",
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


def list_all_curated_tires() -> list[TireSpec]:
    """Return all curated tires sorted alphabetically by model name."""
    return sorted(_CURATED_TIRES.values(), key=lambda t: t.model)

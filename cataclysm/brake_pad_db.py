"""Curated database of common brake pad compounds for track days.

Provides lookup and search functions over a static collection of well-known
brake pad models spanning street, street-track, track, and race categories.
Each entry carries heat range and initial bite characteristics.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrakePadSpec:
    """Specification for a curated brake pad compound."""

    model: str
    brand: str
    category: str  # "street" | "street-track" | "track" | "race"
    temp_range: str
    initial_bite: str  # "low" | "medium" | "high"
    notes: str


# ---------------------------------------------------------------------------
# Curated brake pad database
# ---------------------------------------------------------------------------

_CURATED_BRAKE_PADS: dict[str, BrakePadSpec] = {
    "hawk_hps": BrakePadSpec(
        model="Hawk HPS",
        brand="Hawk",
        category="street",
        temp_range="100-900°F",
        initial_bite="medium",
        notes="Good street pad with mild track capability",
    ),
    "hawk_hp_plus": BrakePadSpec(
        model="Hawk HP+",
        brand="Hawk",
        category="street-track",
        temp_range="150-1100°F",
        initial_bite="medium",
        notes="Dual-purpose street/track pad, popular HPDE choice",
    ),
    "hawk_dtc60": BrakePadSpec(
        model="Hawk DTC-60",
        brand="Hawk",
        category="track",
        temp_range="400-1200°F",
        initial_bite="high",
        notes="Dedicated track pad with strong initial bite",
    ),
    "hawk_dtc70": BrakePadSpec(
        model="Hawk DTC-70",
        brand="Hawk",
        category="race",
        temp_range="500-1400°F",
        initial_bite="high",
        notes="Endurance race pad, needs heat to work",
    ),
    "ferodo_ds2500": BrakePadSpec(
        model="Ferodo DS2500",
        brand="Ferodo",
        category="street-track",
        temp_range="200-900°F",
        initial_bite="high",
        notes="Excellent street/track pad with strong cold bite",
    ),
    "ferodo_ds1_11": BrakePadSpec(
        model="Ferodo DS1.11",
        brand="Ferodo",
        category="track",
        temp_range="400-1200°F",
        initial_bite="medium",
        notes="Smooth modulation track pad, easy on rotors",
    ),
    "ferodo_dsuno": BrakePadSpec(
        model="Ferodo DSUNO",
        brand="Ferodo",
        category="race",
        temp_range="400-1400°F",
        initial_bite="high",
        notes="Top-tier race pad for sprint and endurance",
    ),
    "ebc_yellow": BrakePadSpec(
        model="EBC Yellowstuff",
        brand="EBC",
        category="street-track",
        temp_range="200-900°F",
        initial_bite="medium",
        notes="Budget-friendly street/track pad",
    ),
    "ebc_blue": BrakePadSpec(
        model="EBC Bluestuff NDX",
        brand="EBC",
        category="track",
        temp_range="400-1100°F",
        initial_bite="medium",
        notes="Track-focused pad with progressive feel",
    ),
    "ebc_rp1": BrakePadSpec(
        model="EBC RP-1",
        brand="EBC",
        category="race",
        temp_range="500-1200°F",
        initial_bite="high",
        notes="Full race compound, minimal street use",
    ),
    "carbotech_xp10": BrakePadSpec(
        model="Carbotech XP10",
        brand="Carbotech",
        category="track",
        temp_range="300-1100°F",
        initial_bite="high",
        notes="Aggressive track pad with flat torque curve",
    ),
    "carbotech_xp12": BrakePadSpec(
        model="Carbotech XP12",
        brand="Carbotech",
        category="race",
        temp_range="500-1300°F",
        initial_bite="high",
        notes="Race compound for sprint events",
    ),
}

# ---------------------------------------------------------------------------
# Common brake fluids
# ---------------------------------------------------------------------------

COMMON_BRAKE_FLUIDS: list[str] = [
    "DOT 3",
    "DOT 4",
    "DOT 5.1",
    "Motul RBF 600",
    "Motul RBF 660",
    "Castrol SRF",
    "ATE TYP 200",
    "Brembo HTC 64T",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def search_curated_brake_pads(query: str, limit: int = 10) -> list[BrakePadSpec]:
    """Search curated brake pads by case-insensitive substring on model and brand.

    Args:
        query: Substring to match against model name and brand.
        limit: Maximum number of results to return.

    Returns:
        Matching :class:`BrakePadSpec` entries, up to *limit*.
    """
    if not query:
        return []

    q = query.lower()
    matches: list[BrakePadSpec] = []
    for pad in _CURATED_BRAKE_PADS.values():
        model_match = q in pad.model.lower()
        brand_match = q in pad.brand.lower()
        if model_match or brand_match:
            matches.append(pad)
            if len(matches) >= limit:
                break
    return matches


def get_curated_brake_pad(slug: str) -> BrakePadSpec | None:
    """Look up a curated brake pad by its exact slug identifier.

    Args:
        slug: Database key such as ``"hawk_dtc60"``.

    Returns:
        The :class:`BrakePadSpec` if found, otherwise ``None``.
    """
    return _CURATED_BRAKE_PADS.get(slug)


def list_all_curated_brake_pads() -> list[BrakePadSpec]:
    """Return all curated brake pads sorted alphabetically by model name."""
    return sorted(_CURATED_BRAKE_PADS.values(), key=lambda p: p.model)

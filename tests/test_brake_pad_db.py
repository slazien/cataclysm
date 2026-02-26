"""Tests for the curated brake pad database."""

from __future__ import annotations

from cataclysm.brake_pad_db import (
    COMMON_BRAKE_FLUIDS,
    BrakePadSpec,
    get_curated_brake_pad,
    list_all_curated_brake_pads,
    search_curated_brake_pads,
)

VALID_CATEGORIES = {"street", "street-track", "track", "race"}
VALID_BITES = {"low", "medium", "high"}


def test_search_by_brand_hawk() -> None:
    """Search 'hawk' returns all Hawk entries."""
    results = search_curated_brake_pads("hawk")
    assert len(results) >= 4
    assert all(r.brand == "Hawk" for r in results)


def test_search_by_brand_ferodo() -> None:
    """Search 'ferodo' returns Ferodo entries."""
    results = search_curated_brake_pads("ferodo")
    assert len(results) >= 3
    assert all(r.brand == "Ferodo" for r in results)


def test_search_by_model_substring() -> None:
    """Search 'ds2500' returns Ferodo DS2500."""
    results = search_curated_brake_pads("ds2500")
    assert len(results) == 1
    assert results[0].model == "Ferodo DS2500"
    assert results[0].brand == "Ferodo"


def test_search_empty_query_returns_empty() -> None:
    """Empty query returns no results."""
    assert search_curated_brake_pads("") == []


def test_search_short_query_still_works() -> None:
    """Short query with actual matches returns results."""
    # 'EB' should match EBC brand
    results = search_curated_brake_pads("EB")
    assert len(results) >= 1


def test_search_no_match_returns_empty() -> None:
    """Query with no matches returns empty list."""
    assert search_curated_brake_pads("ZZZnonexistent") == []


def test_search_case_insensitive() -> None:
    """Search is case-insensitive."""
    results_lower = search_curated_brake_pads("hawk")
    results_upper = search_curated_brake_pads("HAWK")
    assert len(results_lower) == len(results_upper)


def test_search_respects_limit() -> None:
    """Search respects the limit parameter."""
    results = search_curated_brake_pads("a", limit=2)
    assert len(results) <= 2


def test_get_curated_brake_pad_existing() -> None:
    """Get by exact slug returns correct pad."""
    pad = get_curated_brake_pad("hawk_dtc60")
    assert pad is not None
    assert pad.model == "Hawk DTC-60"
    assert pad.brand == "Hawk"
    assert pad.category == "track"
    assert pad.initial_bite == "high"


def test_get_curated_brake_pad_nonexistent() -> None:
    """Get with unknown slug returns None."""
    assert get_curated_brake_pad("nonexistent_pad") is None


def test_list_all_returns_12() -> None:
    """List all returns exactly 12 curated pads."""
    all_pads = list_all_curated_brake_pads()
    assert len(all_pads) == 12


def test_list_all_sorted_by_model() -> None:
    """List all is sorted alphabetically by model name."""
    all_pads = list_all_curated_brake_pads()
    models = [p.model for p in all_pads]
    assert models == sorted(models)


def test_all_pads_are_brake_pad_spec() -> None:
    """All entries are BrakePadSpec instances."""
    for pad in list_all_curated_brake_pads():
        assert isinstance(pad, BrakePadSpec)


def test_all_categories_valid() -> None:
    """All pads have valid category values."""
    for pad in list_all_curated_brake_pads():
        assert pad.category in VALID_CATEGORIES, f"{pad.model} has invalid category {pad.category}"


def test_all_initial_bite_valid() -> None:
    """All pads have valid initial_bite values."""
    for pad in list_all_curated_brake_pads():
        assert pad.initial_bite in VALID_BITES, f"{pad.model} has invalid bite {pad.initial_bite}"


def test_all_pads_have_temp_range() -> None:
    """All pads have non-empty temp_range."""
    for pad in list_all_curated_brake_pads():
        assert pad.temp_range, f"{pad.model} missing temp_range"


def test_all_pads_have_notes() -> None:
    """All pads have non-empty notes."""
    for pad in list_all_curated_brake_pads():
        assert pad.notes, f"{pad.model} missing notes"


def test_common_brake_fluids() -> None:
    """Common brake fluids list has expected entries."""
    assert len(COMMON_BRAKE_FLUIDS) >= 5
    assert "DOT 4" in COMMON_BRAKE_FLUIDS
    assert "Motul RBF 600" in COMMON_BRAKE_FLUIDS
    assert "Castrol SRF" in COMMON_BRAKE_FLUIDS

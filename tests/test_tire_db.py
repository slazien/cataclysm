"""Tests for the curated tire database module."""

from __future__ import annotations

from cataclysm.tire_db import (
    get_curated_tire,
    list_all_curated_tires,
    search_curated_tires,
)


class TestSearchCuratedTires:
    """Tests for search_curated_tires()."""

    def test_search_by_model_exact(self) -> None:
        results = search_curated_tires("RE-71RS")
        assert len(results) == 1
        assert "RE-71RS" in results[0].model

    def test_search_case_insensitive(self) -> None:
        results = search_curated_tires("re-71rs")
        assert len(results) == 1
        assert "RE-71RS" in results[0].model

    def test_search_by_brand(self) -> None:
        results = search_curated_tires("Bridgestone")
        assert len(results) >= 1
        assert all(t.brand == "Bridgestone" for t in results)

    def test_search_by_brand_case_insensitive(self) -> None:
        results = search_curated_tires("bridgestone")
        assert len(results) >= 1
        assert results[0].brand == "Bridgestone"

    def test_search_partial_model(self) -> None:
        results = search_curated_tires("Pilot Sport")
        assert len(results) == 1
        assert results[0].brand == "Michelin"

    def test_search_no_match(self) -> None:
        results = search_curated_tires("NonexistentTire9999")
        assert results == []

    def test_search_empty_query(self) -> None:
        results = search_curated_tires("")
        assert results == []

    def test_search_respects_limit(self) -> None:
        # "o" appears in many tire models/brands (Toyo, Yokohama, Hoosier, etc.)
        results = search_curated_tires("o", limit=2)
        assert len(results) <= 2

    def test_search_multiple_matches(self) -> None:
        # "200" appears in multiple model names or treadwear descriptions
        # but we search model+brand text, not treadwear integers
        # Use a broad substring that hits multiple entries
        results = search_curated_tires("an")  # Hankook, Nankang, Continental
        assert len(results) >= 2


class TestGetCuratedTire:
    """Tests for get_curated_tire()."""

    def test_get_known_tire(self) -> None:
        tire = get_curated_tire("bridgestone_re71rs")
        assert tire is not None
        assert tire.model == "Bridgestone Potenza RE-71RS"
        assert tire.estimated_mu == 1.12
        assert tire.brand == "Bridgestone"

    def test_get_another_known_tire(self) -> None:
        tire = get_curated_tire("hoosier_r7")
        assert tire is not None
        assert tire.model == "Hoosier R7"
        assert tire.estimated_mu == 1.38

    def test_get_unknown_slug_returns_none(self) -> None:
        assert get_curated_tire("unknown_slug_xyz") is None

    def test_get_empty_slug_returns_none(self) -> None:
        assert get_curated_tire("") is None


class TestListAllCuratedTires:
    """Tests for list_all_curated_tires()."""

    def test_returns_all_tires(self) -> None:
        all_tires = list_all_curated_tires()
        assert len(all_tires) == 10

    def test_sorted_by_model(self) -> None:
        all_tires = list_all_curated_tires()
        models = [t.model for t in all_tires]
        assert models == sorted(models)

    def test_all_have_curated_source(self) -> None:
        from cataclysm.equipment import MuSource

        all_tires = list_all_curated_tires()
        assert all(t.mu_source == MuSource.CURATED_TABLE for t in all_tires)

    def test_all_have_brand(self) -> None:
        all_tires = list_all_curated_tires()
        assert all(t.brand is not None for t in all_tires)

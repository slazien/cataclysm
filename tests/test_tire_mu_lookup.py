"""Tests for per-tire mu lookup in validation pipeline."""

from __future__ import annotations

from cataclysm.tire_db import lookup_tire


def test_validation_tires_exist_in_db() -> None:
    """Every tire used in the 33-entry validation must be findable."""
    required_keys = [
        "hoosier_r7",
        "yokohama_a052",
        "hankook_rs4",
        "falken_rt660",
        "michelin_ps4s",
        "michelin_cup2",
        "bridgestone_re71rs",
        "dunlop_dh_slick",
        "pirelli_slick_305",
        "goodyear_sc3",
        "nitto_nt01",
        "pirelli_trofeo_r",
        "kumho_v730",
        "hoosier_a7",
        "goodyear_sc3r",
        "michelin_ps4",
    ]
    for key in required_keys:
        tire = lookup_tire(key)
        assert tire is not None, f"Missing tire_db key: {key}"
        assert tire.estimated_mu > 0, f"Zero mu for {key}"


def test_per_tire_mu_differs_from_category() -> None:
    """Per-tire mu should differ from category defaults for at least some tires."""
    from cataclysm.equipment import CATEGORY_MU_DEFAULTS

    tire = lookup_tire("michelin_ps4s")
    assert tire is not None
    cat_mu = CATEGORY_MU_DEFAULTS[tire.compound_category]
    assert tire.estimated_mu != cat_mu, "PS4S mu should differ from category default"

    tire2 = lookup_tire("hoosier_a7")
    assert tire2 is not None
    cat_mu2 = CATEGORY_MU_DEFAULTS[tire2.compound_category]
    assert tire2.estimated_mu != cat_mu2, "A7 mu should differ from category default"

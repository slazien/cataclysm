"""Tests for deterministic coaching content validation."""

from __future__ import annotations

from cataclysm.coaching_content_validator import (
    find_forbidden_composites,
    find_orphan_numbers,
    validate_coaching_content,
)


def test_known_bad_mph_of_available_grip_is_caught() -> None:
    text = "Your best lap shows excellent speed utilization at 95.7 mph of available grip."
    hits = find_forbidden_composites(text)
    assert "mph of available grip" in " ".join(hits).lower()


def test_known_bad_g_of_speed_is_caught() -> None:
    text = "You found 1.2G of speed at the apex."
    hits = find_forbidden_composites(text)
    assert any("g of speed" in hit.lower() for hit in hits)


def test_known_bad_speed_utilization_at_number_is_caught() -> None:
    text = "Great speed utilization at 95.7 entering T5."
    hits = find_forbidden_composites(text)
    assert any("speed utilization at 9" in hit.lower() for hit in hits)


def test_known_good_min_speed_phrase_passes() -> None:
    text = "T5 minimum speed was 95.7 mph on your best lap."
    result = validate_coaching_content(text)
    assert result.passed is True
    assert result.forbidden_composites == []


def test_known_good_peak_brake_g_phrase_passes() -> None:
    text = "Peak braking reached 1.2G before turn-in."
    result = validate_coaching_content(text)
    assert result.passed is True
    assert result.forbidden_composites == []


def test_known_good_speed_gap_phrase_passes() -> None:
    text = "Exit speed gap is 3.2 mph to optimal."
    result = validate_coaching_content(text)
    assert result.passed is True
    assert result.forbidden_composites == []


def test_orphan_detection_flags_unknown_numbers_as_warnings() -> None:
    text = "Exit speed gap is 7.9 mph and brake point moved by 12m."
    orphans = find_orphan_numbers(text, input_values={3.2, 50.0, 99.0})
    assert "7.9 mph" in orphans
    assert "12m" in orphans

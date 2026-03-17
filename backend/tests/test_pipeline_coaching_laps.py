"""Tests for recalculate_coaching_laps() in pipeline.py."""

from __future__ import annotations

from cataclysm.lap_tags import LapTagStore

from backend.api.services.pipeline import recalculate_coaching_laps


def _make_tags(**lap_tags: list[str]) -> LapTagStore:
    """Helper: build a LapTagStore from keyword args {lap_num: [tags]}."""
    store = LapTagStore()
    for lap_str, tags in lap_tags.items():
        lap_num = int(lap_str)
        for tag in tags:
            store.add_tag(lap_num, tag)
    return store


# ---------------------------------------------------------------------------
# Basic exclusion tests
# ---------------------------------------------------------------------------


def test_excludes_tagged_traffic_lap() -> None:
    """A lap tagged 'traffic' must be removed from coaching laps."""
    all_laps = [1, 2, 3, 4, 5]
    anomalous: set[int] = set()
    in_out: set[int] = {1, 5}
    best_lap = 3
    tags = _make_tags(**{"2": ["traffic"]})

    result = recalculate_coaching_laps(all_laps, anomalous, in_out, best_lap, tags)

    assert 2 not in result
    assert result == [3, 4]


def test_best_lap_excluded_by_tag_stays_excluded() -> None:
    """User intent overrides best-lap re-inclusion rule.

    Even though best_lap is excluded only as in/out (not anomalous),
    a user-applied tag keeps it out.
    """
    all_laps = [1, 2, 3, 4, 5]
    anomalous: set[int] = set()
    # Lap 1 is both in_out AND user-tagged as traffic
    in_out: set[int] = {1, 5}
    best_lap = 1
    tags = _make_tags(**{"1": ["traffic"]})

    result = recalculate_coaching_laps(all_laps, anomalous, in_out, best_lap, tags)

    assert 1 not in result
    assert result == [2, 3, 4]


def test_no_tags_same_as_original() -> None:
    """Empty LapTagStore must reproduce the original pipeline behavior exactly."""
    all_laps = [1, 2, 3, 4, 5]
    anomalous: set[int] = set()
    in_out: set[int] = {1, 5}
    best_lap = 3
    tags = LapTagStore()

    result = recalculate_coaching_laps(all_laps, anomalous, in_out, best_lap, tags)

    assert result == [2, 3, 4]


def test_best_lap_included_when_in_out_but_not_tagged() -> None:
    """Best lap excluded only by in/out (not anomalous, not user-tagged) must be re-included."""
    all_laps = [1, 2, 3, 4, 5]
    anomalous: set[int] = set()
    in_out: set[int] = {1, 5}
    best_lap = 5  # last lap is the best — should be re-included
    tags = LapTagStore()

    result = recalculate_coaching_laps(all_laps, anomalous, in_out, best_lap, tags)

    assert 5 in result
    assert result == [2, 3, 4, 5]


def test_all_laps_excluded_returns_empty() -> None:
    """Edge case: every lap is either anomalous, in/out, or user-tagged — returns empty list."""
    all_laps = [1, 2, 3]
    anomalous: set[int] = {2}  # lap 2 anomalous
    in_out: set[int] = {1, 3}  # laps 1+3 are in/out
    best_lap = 2  # best lap is anomalous — NOT re-included
    tags = LapTagStore()

    result = recalculate_coaching_laps(all_laps, anomalous, in_out, best_lap, tags)

    assert result == []


# ---------------------------------------------------------------------------
# Tag-type coverage
# ---------------------------------------------------------------------------


def test_off_line_tag_excludes_lap() -> None:
    """'off-line' is in EXCLUDE_FROM_COACHING — must remove the lap."""
    all_laps = [1, 2, 3, 4, 5]
    anomalous: set[int] = set()
    in_out: set[int] = {1, 5}
    best_lap = 3
    tags = _make_tags(**{"3": ["off-line"]})

    result = recalculate_coaching_laps(all_laps, anomalous, in_out, best_lap, tags)

    assert 3 not in result
    assert result == [2, 4]


def test_clean_tag_does_not_exclude_lap() -> None:
    """'clean' tag is not in EXCLUDE_FROM_COACHING — must NOT remove the lap."""
    all_laps = [1, 2, 3, 4, 5]
    anomalous: set[int] = set()
    in_out: set[int] = {1, 5}
    best_lap = 3
    tags = _make_tags(**{"3": ["clean"]})

    result = recalculate_coaching_laps(all_laps, anomalous, in_out, best_lap, tags)

    assert 3 in result
    assert result == [2, 3, 4]


def test_result_is_sorted() -> None:
    """Output must always be a sorted list regardless of insertion order."""
    all_laps = [1, 2, 3, 4, 5]
    anomalous: set[int] = set()
    in_out: set[int] = {5}  # only one in/out to keep best_lap re-inclusion path
    best_lap = 5
    tags = LapTagStore()

    result = recalculate_coaching_laps(all_laps, anomalous, in_out, best_lap, tags)

    assert result == sorted(result)
    assert 5 in result

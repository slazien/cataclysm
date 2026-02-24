"""Tests for the lap_tags module."""

from __future__ import annotations

from cataclysm.engine import LapSummary
from cataclysm.lap_tags import (
    EXCLUDE_FROM_COACHING,
    PREDEFINED_TAGS,
    LapTagStore,
    filter_laps_by_tags,
)


class TestLapTagStore:
    """Tests for the LapTagStore dataclass."""

    def test_add_tag(self) -> None:
        store = LapTagStore()
        store.add_tag(1, "clean")
        assert "clean" in store.get_tags(1)

    def test_add_multiple_tags(self) -> None:
        store = LapTagStore()
        store.add_tag(1, "clean")
        store.add_tag(1, "rain")
        assert store.get_tags(1) == {"clean", "rain"}

    def test_add_duplicate_tag(self) -> None:
        store = LapTagStore()
        store.add_tag(1, "clean")
        store.add_tag(1, "clean")
        assert store.get_tags(1) == {"clean"}

    def test_remove_tag(self) -> None:
        store = LapTagStore()
        store.add_tag(1, "clean")
        store.add_tag(1, "rain")
        store.remove_tag(1, "clean")
        assert store.get_tags(1) == {"rain"}

    def test_remove_nonexistent_tag(self) -> None:
        """Removing a tag that doesn't exist should not raise."""
        store = LapTagStore()
        store.add_tag(1, "clean")
        store.remove_tag(1, "traffic")  # not present, should not raise
        assert store.get_tags(1) == {"clean"}

    def test_remove_tag_unknown_lap(self) -> None:
        """Removing a tag from a lap that has no tags should not raise."""
        store = LapTagStore()
        store.remove_tag(99, "clean")  # lap 99 never tagged

    def test_get_tags_unknown_lap(self) -> None:
        store = LapTagStore()
        assert store.get_tags(42) == set()

    def test_get_tags_returns_copy(self) -> None:
        """Mutating the returned set should not affect the store."""
        store = LapTagStore()
        store.add_tag(1, "clean")
        tags = store.get_tags(1)
        tags.add("rain")
        assert store.get_tags(1) == {"clean"}

    def test_laps_with_tag(self) -> None:
        store = LapTagStore()
        store.add_tag(1, "clean")
        store.add_tag(2, "traffic")
        store.add_tag(3, "clean")
        store.add_tag(3, "rain")
        assert store.laps_with_tag("clean") == {1, 3}

    def test_laps_with_tag_none_found(self) -> None:
        store = LapTagStore()
        store.add_tag(1, "clean")
        assert store.laps_with_tag("traffic") == set()

    def test_excluded_laps_default(self) -> None:
        """Laps with EXCLUDE_FROM_COACHING tags are excluded by default."""
        store = LapTagStore()
        store.add_tag(1, "clean")
        store.add_tag(2, "traffic")
        store.add_tag(3, "off-line")
        store.add_tag(4, "rain")
        excluded = store.excluded_laps()
        assert excluded == {2, 3}

    def test_excluded_laps_custom(self) -> None:
        store = LapTagStore()
        store.add_tag(1, "rain")
        store.add_tag(2, "clean")
        store.add_tag(3, "rain")
        excluded = store.excluded_laps({"rain"})
        assert excluded == {1, 3}

    def test_excluded_laps_empty_store(self) -> None:
        store = LapTagStore()
        assert store.excluded_laps() == set()

    def test_excluded_laps_no_matches(self) -> None:
        store = LapTagStore()
        store.add_tag(1, "clean")
        store.add_tag(2, "rain")
        assert store.excluded_laps() == set()

    def test_all_tags(self) -> None:
        store = LapTagStore()
        store.add_tag(1, "clean")
        store.add_tag(2, "traffic")
        store.add_tag(3, "clean")
        store.add_tag(3, "rain")
        assert store.all_tags() == {"clean", "traffic", "rain"}

    def test_all_tags_empty_store(self) -> None:
        store = LapTagStore()
        assert store.all_tags() == set()


class TestFilterLapsByTags:
    """Tests for the filter_laps_by_tags helper."""

    def test_filter_excludes_tagged_laps(self) -> None:
        store = LapTagStore()
        store.add_tag(2, "traffic")
        store.add_tag(4, "experimental")
        result = filter_laps_by_tags([1, 2, 3, 4, 5], store)
        assert result == [1, 3, 5]

    def test_filter_no_exclusions(self) -> None:
        """All laps pass through when no exclusion tags are present."""
        store = LapTagStore()
        store.add_tag(1, "clean")
        store.add_tag(2, "rain")
        result = filter_laps_by_tags([1, 2, 3], store)
        assert result == [1, 2, 3]

    def test_filter_custom_exclude_tags(self) -> None:
        store = LapTagStore()
        store.add_tag(1, "rain")
        store.add_tag(3, "rain")
        result = filter_laps_by_tags([1, 2, 3], store, exclude_tags={"rain"})
        assert result == [2]

    def test_filter_empty_store(self) -> None:
        store = LapTagStore()
        result = filter_laps_by_tags([1, 2, 3], store)
        assert result == [1, 2, 3]

    def test_filter_preserves_order(self) -> None:
        store = LapTagStore()
        store.add_tag(3, "traffic")
        result = filter_laps_by_tags([5, 3, 1, 4, 2], store)
        assert result == [5, 1, 4, 2]


class TestPredefinedTags:
    """Tests for module-level constants."""

    def test_predefined_tags_are_strings(self) -> None:
        assert all(isinstance(t, str) for t in PREDEFINED_TAGS)

    def test_predefined_tags_not_empty(self) -> None:
        assert len(PREDEFINED_TAGS) > 0

    def test_exclude_tags_are_subset_of_predefined(self) -> None:
        assert set(PREDEFINED_TAGS) >= EXCLUDE_FROM_COACHING

    def test_exclude_from_coaching_contents(self) -> None:
        assert "traffic" in EXCLUDE_FROM_COACHING
        assert "off-line" in EXCLUDE_FROM_COACHING
        assert "experimental" in EXCLUDE_FROM_COACHING
        assert "cold-tires" in EXCLUDE_FROM_COACHING
        assert "clean" not in EXCLUDE_FROM_COACHING
        assert "rain" not in EXCLUDE_FROM_COACHING


class TestLapSummaryTagsField:
    """Tests for the tags field added to LapSummary."""

    def test_default_tags_empty(self) -> None:
        summary = LapSummary(
            lap_number=1,
            lap_time_s=90.0,
            lap_distance_m=3000.0,
            max_speed_mps=60.0,
        )
        assert summary.tags == set()

    def test_tags_backward_compat(self) -> None:
        """Creating LapSummary without tags kwarg should work (empty set)."""
        summary = LapSummary(
            lap_number=1,
            lap_time_s=90.0,
            lap_distance_m=3000.0,
            max_speed_mps=60.0,
        )
        assert isinstance(summary.tags, set)

    def test_tags_with_values(self) -> None:
        summary = LapSummary(
            lap_number=1,
            lap_time_s=90.0,
            lap_distance_m=3000.0,
            max_speed_mps=60.0,
            tags={"clean", "rain"},
        )
        assert summary.tags == {"clean", "rain"}

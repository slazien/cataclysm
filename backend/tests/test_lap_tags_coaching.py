"""Verify coaching excludes user-tagged laps.

These tests confirm the full wiring from LapTagStore → recalculate_coaching_laps()
→ coaching router filter.  They complement the lower-level tests in
test_pipeline_coaching_laps.py and the HTTP integration tests in
test_lap_tag_endpoint.py.
"""

from __future__ import annotations

import inspect

from cataclysm.lap_tags import LapTagStore

from backend.api.services.pipeline import recalculate_coaching_laps


class TestCoachingExcludesTaggedLaps:
    def test_tagged_lap_excluded_from_coaching_summaries(self) -> None:
        """Coaching report should not receive summaries for tagged laps."""
        # Setup: all_laps 1-5, tag lap 3 as traffic
        tags = LapTagStore()
        tags.add_tag(3, "traffic")

        coaching_laps = recalculate_coaching_laps(
            all_laps=[1, 2, 3, 4, 5],
            anomalous=set(),
            in_out={1, 5},
            best_lap=2,
            tags=tags,
        )

        # Verify lap 3 is excluded
        assert 3 not in coaching_laps
        # The coaching endpoint filters summaries by coaching_laps,
        # so lap 3's data will never reach the LLM
        assert coaching_laps == [2, 4]

    def test_removing_tag_restores_lap(self) -> None:
        """After removing a tag, the lap should be back in coaching_laps."""
        tags = LapTagStore()
        tags.add_tag(3, "traffic")

        # With tag
        cl1 = recalculate_coaching_laps(
            all_laps=[1, 2, 3, 4, 5],
            anomalous=set(),
            in_out={1, 5},
            best_lap=2,
            tags=tags,
        )
        assert 3 not in cl1

        # Remove tag
        tags.remove_tag(3, "traffic")
        cl2 = recalculate_coaching_laps(
            all_laps=[1, 2, 3, 4, 5],
            anomalous=set(),
            in_out={1, 5},
            best_lap=2,
            tags=tags,
        )
        assert 3 in cl2

    def test_all_coaching_laps_tagged_leaves_empty(self) -> None:
        """If all non-anomalous, non-in/out laps are tagged, coaching_laps is empty."""
        tags = LapTagStore()
        tags.add_tag(2, "traffic")
        tags.add_tag(3, "traffic")
        tags.add_tag(4, "off-line")

        coaching_laps = recalculate_coaching_laps(
            all_laps=[1, 2, 3, 4, 5],
            anomalous=set(),
            in_out={1, 5},
            best_lap=2,
            tags=tags,
        )
        assert coaching_laps == []

    def test_coaching_router_filters_by_coaching_laps(self) -> None:
        """Verify coaching.py filters summaries by sd.coaching_laps.

        This is a code-inspection test — it greps the source to confirm
        the filter exists, preventing silent regression if someone changes it.
        """
        from backend.api.routers import coaching as coaching_module

        source = inspect.getsource(coaching_module)
        assert "if s.lap_number in sd.coaching_laps" in source

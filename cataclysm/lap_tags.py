"""Lap tagging: predefined and custom tag management."""

from __future__ import annotations

from dataclasses import dataclass, field

PREDEFINED_TAGS: list[str] = [
    "clean",
    "traffic",
    "off-line",
    "experimental",
    "rain",
    "cold-tires",
]

# Tags that should exclude laps from coaching by default
EXCLUDE_FROM_COACHING: set[str] = {"traffic", "off-line", "experimental", "cold-tires"}


@dataclass
class LapTagStore:
    """Session-scoped tag storage. Maps lap_number -> set of tags."""

    tags: dict[int, set[str]] = field(default_factory=dict)

    def add_tag(self, lap_number: int, tag: str) -> None:
        """Add a tag to a lap."""
        self.tags.setdefault(lap_number, set()).add(tag)

    def remove_tag(self, lap_number: int, tag: str) -> None:
        """Remove a tag from a lap. No error if tag not present."""
        if lap_number in self.tags:
            self.tags[lap_number].discard(tag)

    def get_tags(self, lap_number: int) -> set[str]:
        """Get all tags for a lap (returns a copy)."""
        return self.tags.get(lap_number, set()).copy()

    def laps_with_tag(self, tag: str) -> set[int]:
        """Return all lap numbers that have a given tag."""
        return {num for num, tags in self.tags.items() if tag in tags}

    def excluded_laps(self, exclude_tags: set[str] | None = None) -> set[int]:
        """Return lap numbers that have any of the exclude_tags.

        Defaults to EXCLUDE_FROM_COACHING if not specified.
        """
        if exclude_tags is None:
            exclude_tags = EXCLUDE_FROM_COACHING
        return {num for num, tags in self.tags.items() if tags & exclude_tags}

    def all_tags(self) -> set[str]:
        """Return all unique tags across all laps."""
        result: set[str] = set()
        for tags in self.tags.values():
            result |= tags
        return result


def filter_laps_by_tags(
    all_laps: list[int],
    tag_store: LapTagStore,
    exclude_tags: set[str] | None = None,
) -> list[int]:
    """Return laps that don't have any of the specified exclude tags."""
    excluded = tag_store.excluded_laps(exclude_tags)
    return [n for n in all_laps if n not in excluded]

"""Linked corner detection and compound section metrics.

Detects when adjacent corners are "linked" (the car never reaches straight-line
speed between them) and computes compound section metrics.  This fixes
misleading per-corner metrics for chicanes, esses, and other multi-apex
complexes where the driver never fully accelerates between apexes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cataclysm.corners import Corner

# Fraction of max straight speed below which two corners are considered linked.
DEFAULT_LINK_THRESHOLD = 0.95


@dataclass
class CornerGroup:
    """A group of linked corners that form a compound section."""

    group_id: int
    corner_numbers: list[int] = field(default_factory=list)
    section_entry_idx: int = 0
    section_exit_idx: int = 0
    curvature_variation_index: float = 0.0  # CVI for complexity classification


@dataclass
class LinkedCornerResult:
    """Result of linked corner detection."""

    groups: list[CornerGroup] = field(default_factory=list)
    corner_to_group: dict[int, int] = field(default_factory=dict)


def _find_v_max_straight(
    optimal_speed: np.ndarray,
    distance_m: np.ndarray,
    corners: list[Corner],
) -> float:
    """Find maximum speed on the longest straight segment.

    A "straight" is any gap outside corner zones: before the first corner,
    between consecutive corners, and after the last corner.  The longest
    such gap (by index span) is used as the reference for v_max_straight.

    If no corners or only one corner exist, the global max speed is returned.
    """
    if len(corners) < 2:
        return float(np.max(optimal_speed)) if len(optimal_speed) > 0 else 0.0

    # Sort corners by entry distance to ensure correct ordering
    sorted_corners = sorted(corners, key=lambda c: c.entry_distance_m)

    # Build list of straight segments: before first, between, and after last
    straights: list[tuple[int, int]] = []

    # Segment before first corner
    first_entry_idx = int(np.searchsorted(distance_m, sorted_corners[0].entry_distance_m))
    first_entry_idx = min(first_entry_idx, len(distance_m) - 1)
    if first_entry_idx > 0:
        straights.append((0, first_entry_idx))

    # Segments between consecutive corners
    for i in range(len(sorted_corners) - 1):
        exit_dist = sorted_corners[i].exit_distance_m
        entry_dist = sorted_corners[i + 1].entry_distance_m

        if entry_dist <= exit_dist:
            continue  # overlapping corners, no straight between them

        exit_idx = int(np.searchsorted(distance_m, exit_dist))
        entry_idx = int(np.searchsorted(distance_m, entry_dist))

        exit_idx = min(exit_idx, len(distance_m) - 1)
        entry_idx = min(entry_idx, len(distance_m) - 1)

        if entry_idx > exit_idx:
            straights.append((exit_idx, entry_idx))

    # Segment after last corner
    last_exit_idx = int(np.searchsorted(distance_m, sorted_corners[-1].exit_distance_m))
    last_exit_idx = min(last_exit_idx, len(distance_m) - 1)
    if last_exit_idx < len(distance_m) - 1:
        straights.append((last_exit_idx, len(distance_m)))

    if not straights:
        return float(np.max(optimal_speed)) if len(optimal_speed) > 0 else 0.0

    # Find the longest straight by index span
    longest = max(straights, key=lambda s: s[1] - s[0])
    segment = optimal_speed[longest[0] : longest[1]]

    if len(segment) == 0:
        return float(np.max(optimal_speed))

    return float(np.max(segment))


def detect_linked_corners(
    corners: list[Corner],
    optimal_speed: np.ndarray,
    distance_m: np.ndarray,
    *,
    link_threshold: float = DEFAULT_LINK_THRESHOLD,
) -> LinkedCornerResult:
    """Detect linked corner groups from the velocity profile.

    Two corners are linked if the maximum speed between them is less than
    ``link_threshold * v_max_straight``, where ``v_max_straight`` is the
    maximum speed on the longest straight segment.

    Parameters
    ----------
    corners:
        List of detected Corner objects.
    optimal_speed:
        Speed array (m/s) aligned with ``distance_m``.
    distance_m:
        Distance array (m) aligned with ``optimal_speed``.
    link_threshold:
        Fraction of ``v_max_straight`` below which corners are linked.

    Returns
    -------
    LinkedCornerResult with groups and corner-to-group mapping.
    """
    if len(corners) < 2:
        return LinkedCornerResult()

    v_max_straight = _find_v_max_straight(optimal_speed, distance_m, corners)

    if v_max_straight <= 0:
        return LinkedCornerResult()

    speed_threshold = link_threshold * v_max_straight

    # Sort corners by entry distance
    sorted_corners = sorted(corners, key=lambda c: c.entry_distance_m)

    # Determine which adjacent pairs are linked
    linked_pairs: list[bool] = []
    for i in range(len(sorted_corners) - 1):
        exit_dist = sorted_corners[i].exit_distance_m
        entry_dist = sorted_corners[i + 1].entry_distance_m

        if entry_dist <= exit_dist:
            # Overlapping corners — they are definitely linked
            linked_pairs.append(True)
            continue

        exit_idx = int(np.searchsorted(distance_m, exit_dist))
        entry_idx = int(np.searchsorted(distance_m, entry_dist))

        exit_idx = min(exit_idx, len(optimal_speed) - 1)
        entry_idx = min(entry_idx, len(optimal_speed) - 1)

        if entry_idx <= exit_idx:
            linked_pairs.append(True)
            continue

        between_speed = optimal_speed[exit_idx:entry_idx]
        if len(between_speed) == 0:
            linked_pairs.append(True)
            continue

        max_speed_between = float(np.max(between_speed))
        linked_pairs.append(max_speed_between < speed_threshold)

    # Chain linked pairs into groups
    groups: list[CornerGroup] = []
    corner_to_group: dict[int, int] = {}
    group_id = 0

    i = 0
    while i < len(sorted_corners):
        # Start a potential group at corner i
        chain_end = i
        while chain_end < len(linked_pairs) and linked_pairs[chain_end]:
            chain_end += 1

        if chain_end > i:
            # We have a linked chain from i to chain_end (inclusive)
            group_id += 1
            group_corners = sorted_corners[i : chain_end + 1]
            corner_nums = [c.number for c in group_corners]

            # Section boundaries
            entry_dist = group_corners[0].entry_distance_m
            exit_dist = group_corners[-1].exit_distance_m

            section_entry_idx = int(np.searchsorted(distance_m, entry_dist))
            section_exit_idx = int(np.searchsorted(distance_m, exit_dist))
            section_entry_idx = min(section_entry_idx, len(distance_m) - 1)
            section_exit_idx = min(section_exit_idx, len(distance_m) - 1)

            groups.append(
                CornerGroup(
                    group_id=group_id,
                    corner_numbers=corner_nums,
                    section_entry_idx=section_entry_idx,
                    section_exit_idx=section_exit_idx,
                    curvature_variation_index=0.0,  # computed separately
                )
            )

            for num in corner_nums:
                corner_to_group[num] = group_id

            i = chain_end + 1
        else:
            # Isolated corner, not part of any group
            i += 1

    return LinkedCornerResult(groups=groups, corner_to_group=corner_to_group)


def compute_curvature_variation_index(
    curvature: np.ndarray,
    entry_idx: int,
    exit_idx: int,
) -> float:
    """Compute the Curvature Variation Index (CVI) for a section.

    CVI = std(curvature) / mean(|curvature|) within the section.

    High CVI (> 1.0) indicates a complex section (chicane, esses) where
    curvature alternates direction.  Low CVI (< 0.5) indicates a simple
    arc with relatively uniform curvature.

    Parameters
    ----------
    curvature:
        Signed curvature array (1/m).
    entry_idx:
        Start index of the section (inclusive).
    exit_idx:
        End index of the section (exclusive).

    Returns
    -------
    CVI value (non-negative float).  Returns 0.0 if the section is too
    short or mean absolute curvature is zero.
    """
    section = curvature[entry_idx:exit_idx]

    if len(section) < 2:
        return 0.0

    mean_abs = float(np.mean(np.abs(section)))

    if mean_abs < 1e-12:
        return 0.0

    std = float(np.std(section))
    return std / mean_abs

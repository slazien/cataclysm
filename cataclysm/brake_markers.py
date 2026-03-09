"""Auto-compute brake board landmarks from corner positions.

For each braking corner, places 3-board (300m), 2-board (200m), and 1-board
(100m) markers before the estimated corner entry point.  Corners that are
flat-out or kinks are skipped since they don't require braking.
"""

from __future__ import annotations

from cataclysm.landmarks import Landmark, LandmarkType
from cataclysm.track_db import OfficialCorner

# Distances (meters) before corner entry for each brake board
_BOARD_OFFSETS_M: list[tuple[int, float]] = [
    (3, 300.0),
    (2, 200.0),
    (1, 100.0),
]

# Simplified entry offset: apex minus this many meters
_ENTRY_OFFSET_M = 50.0


def compute_brake_markers(
    corners: list[OfficialCorner],
    track_length_m: float,
) -> list[Landmark]:
    """Generate brake board landmarks for braking corners.

    For each corner that requires braking (not flat, not kink), places
    3-board, 2-board, and 1-board markers at 300m, 200m, and 100m before
    the estimated corner entry.  Corner entry is approximated as
    ``apex_distance - 50m``.

    Markers wrap around the lap start for corners near the beginning of
    the track.  Markers that would collide (negative distance without
    wrap-around possibility) are skipped.

    Parameters
    ----------
    corners:
        Official corner definitions for the track.
    track_length_m:
        Total lap distance in meters.

    Returns
    -------
    List of Landmark objects with ``landmark_type=LandmarkType.brake_board``.
    """
    if track_length_m <= 0:
        return []

    markers: list[Landmark] = []

    for corner in corners:
        # Skip flat-out corners and kinks — no braking required
        if corner.character == "flat" or corner.corner_type == "kink":
            continue

        apex_distance_m = corner.fraction * track_length_m
        entry_distance_m = apex_distance_m - _ENTRY_OFFSET_M

        for board_num, offset_m in _BOARD_OFFSETS_M:
            raw_distance = entry_distance_m - offset_m

            # Wrap around for corners near lap start
            marker_distance = raw_distance % track_length_m

            markers.append(
                Landmark(
                    name=f"{corner.name} {board_num} board",
                    distance_m=round(marker_distance, 1),
                    landmark_type=LandmarkType.brake_board,
                )
            )

    return markers

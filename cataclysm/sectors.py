"""Sector time analysis: per-lap splits, personal bests, and composite time.

Reuses ``gains.build_segments`` and ``gains.compute_segment_times`` for the
heavy lifting — this module adds the analysis/presentation layer on top.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from cataclysm.corners import Corner
from cataclysm.gains import SegmentDefinition, build_segments, compute_segment_times


@dataclass
class SectorSplit:
    """One sector's time for a single lap."""

    sector_name: str
    time_s: float
    is_personal_best: bool = False


@dataclass
class LapSectorSplits:
    """All sector splits for a single lap."""

    lap_number: int
    total_time_s: float
    splits: list[SectorSplit]


@dataclass
class SectorAnalysis:
    """Complete sector analysis across all clean laps."""

    segments: list[SegmentDefinition]
    lap_splits: list[LapSectorSplits]
    best_sector_times: dict[str, float]
    best_sector_laps: dict[str, int]
    composite_time_s: float


def compute_sector_analysis(
    resampled_laps: dict[int, pd.DataFrame],
    corners: list[Corner],
    clean_laps: list[int],
    best_lap: int,
) -> SectorAnalysis:
    """Compute per-lap sector splits with personal best identification.

    Parameters
    ----------
    resampled_laps:
        Dict of lap_number -> resampled DataFrame (0.7m intervals).
    corners:
        Detected corners from the reference lap.
    clean_laps:
        Lap numbers considered clean (non-anomalous).
    best_lap:
        The fastest lap number (used for track length reference).

    Returns
    -------
    SectorAnalysis with per-lap splits and composite time.
    """
    best_lap_df = resampled_laps[best_lap]
    track_length_m = float(best_lap_df["lap_distance_m"].iloc[-1])

    segments = build_segments(corners, track_length_m)
    seg_times = compute_segment_times(resampled_laps, segments, clean_laps)

    # Find best time and lap for each segment
    best_sector_times: dict[str, float] = {}
    best_sector_laps: dict[str, int] = {}
    for seg in segments:
        times = seg_times.get(seg.name, {})
        if times:
            best_lap_num = min(times, key=lambda k: times[k])
            best_sector_times[seg.name] = times[best_lap_num]
            best_sector_laps[seg.name] = best_lap_num

    # Build per-lap splits
    lap_splits: list[LapSectorSplits] = []
    for lap_num in clean_laps:
        splits: list[SectorSplit] = []
        total = 0.0
        for seg in segments:
            times = seg_times.get(seg.name, {})
            t = times.get(lap_num, 0.0)
            is_pb = seg.name in best_sector_times and best_sector_laps.get(seg.name) == lap_num
            splits.append(
                SectorSplit(sector_name=seg.name, time_s=round(t, 4), is_personal_best=is_pb)
            )
            total += t
        lap_splits.append(
            LapSectorSplits(
                lap_number=lap_num,
                total_time_s=round(total, 4),
                splits=splits,
            )
        )

    composite_time = sum(best_sector_times.values())

    return SectorAnalysis(
        segments=segments,
        lap_splits=lap_splits,
        best_sector_times={k: round(v, 4) for k, v in best_sector_times.items()},
        best_sector_laps=best_sector_laps,
        composite_time_s=round(composite_time, 4),
    )

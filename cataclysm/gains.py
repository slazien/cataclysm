"""Deterministic time-gain estimation at three tiers: consistency, composite, theoretical."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from cataclysm.corners import Corner
from cataclysm.engine import LapSummary


@dataclass
class SegmentDefinition:
    """A segment of the track: either a corner or a straight between corners."""

    name: str  # "T5" or "S3-4"
    entry_distance_m: float
    exit_distance_m: float
    is_corner: bool


@dataclass
class SegmentGain:
    """Time gain potential for a single segment."""

    segment: SegmentDefinition
    best_time_s: float
    avg_time_s: float
    gain_s: float
    best_lap: int
    lap_times_s: dict[int, float] = field(default_factory=dict)


@dataclass
class ConsistencyGainResult:
    """Layer 1: gain from matching personal best in every segment."""

    segment_gains: list[SegmentGain]
    total_gain_s: float
    avg_lap_time_s: float
    best_lap_time_s: float


@dataclass
class CompositeGainResult:
    """Layer 2: gain from a composite best-of-all-segments lap."""

    segment_gains: list[SegmentGain]
    composite_time_s: float
    best_lap_time_s: float
    gain_s: float


@dataclass
class TheoreticalBestResult:
    """Layer 3: gain from theoretical best via micro-sectors."""

    sector_size_m: float
    n_sectors: int
    theoretical_time_s: float
    best_lap_time_s: float
    gain_s: float


@dataclass
class PhysicsGapResult:
    """Layer 4: gap between theoretical best and physics-optimal."""

    optimal_lap_time_s: float
    composite_time_s: float
    gap_s: float  # composite - optimal (positive = room to improve technique)


@dataclass
class GainEstimate:
    """Orchestrated gain result across all three tiers."""

    consistency: ConsistencyGainResult
    composite: CompositeGainResult
    theoretical: TheoreticalBestResult
    clean_lap_numbers: list[int]
    best_lap_number: int
    physics_gap: PhysicsGapResult | None = None


def build_segments(
    corners: list[Corner],
    track_length_m: float,
) -> list[SegmentDefinition]:
    """Build alternating straight/corner segments covering the full track.

    Corners are named "T{n}" and straights "S{prev}-{next}" where prev/next are
    the adjacent corner numbers (e.g. "S0-1" before T1, "S3-fin" after last corner).
    """
    if not corners:
        return [
            SegmentDefinition(
                name="S0-fin",
                entry_distance_m=0.0,
                exit_distance_m=track_length_m,
                is_corner=False,
            )
        ]

    segments: list[SegmentDefinition] = []
    sorted_corners = sorted(corners, key=lambda c: c.entry_distance_m)
    cursor = 0.0

    for i, corner in enumerate(sorted_corners):
        # Straight before this corner (skip if zero-length)
        if corner.entry_distance_m > cursor + 1e-6:
            straight_name = f"S{i}-{i + 1}"
            segments.append(
                SegmentDefinition(
                    name=straight_name,
                    entry_distance_m=cursor,
                    exit_distance_m=corner.entry_distance_m,
                    is_corner=False,
                )
            )
        # Corner segment
        segments.append(
            SegmentDefinition(
                name=f"T{corner.number}",
                entry_distance_m=corner.entry_distance_m,
                exit_distance_m=corner.exit_distance_m,
                is_corner=True,
            )
        )
        cursor = corner.exit_distance_m

    # Final straight after last corner
    if cursor < track_length_m - 1e-6:
        last_num = len(sorted_corners)
        segments.append(
            SegmentDefinition(
                name=f"S{last_num}-fin",
                entry_distance_m=cursor,
                exit_distance_m=track_length_m,
                is_corner=False,
            )
        )

    return segments


def compute_segment_times(
    resampled_laps: dict[int, pd.DataFrame],
    segments: list[SegmentDefinition],
    clean_laps: list[int],
) -> dict[str, dict[int, float]]:
    """Compute elapsed time for each segment on each clean lap.

    Uses np.interp to precisely interpolate lap_time_s at segment boundaries.
    """
    result: dict[str, dict[int, float]] = {}
    for seg in segments:
        seg_times: dict[int, float] = {}
        for lap_num in clean_laps:
            if lap_num not in resampled_laps:
                continue
            lap_df = resampled_laps[lap_num]
            dist = lap_df["lap_distance_m"].to_numpy()
            time = lap_df["lap_time_s"].to_numpy()

            entry_time = float(np.interp(seg.entry_distance_m, dist, time))
            exit_time = float(np.interp(seg.exit_distance_m, dist, time))

            seg_time = exit_time - entry_time
            seg_times[lap_num] = max(0.0, seg_time)

        result[seg.name] = seg_times

    return result


def compute_consistency_gain(
    segment_times: dict[str, dict[int, float]],
    segments: list[SegmentDefinition],
    summaries: list[LapSummary],
    clean_laps: list[int],
) -> ConsistencyGainResult:
    """Layer 1: gain from matching personal best in every segment.

    For each segment, gain = mean(times) - min(times). Total gain is the sum.
    """
    clean_summaries = [s for s in summaries if s.lap_number in clean_laps]
    avg_lap_time = float(np.mean([s.lap_time_s for s in clean_summaries]))
    best_lap_time = float(min(s.lap_time_s for s in clean_summaries))

    segment_gains: list[SegmentGain] = []
    total_gain = 0.0

    for seg in segments:
        times = segment_times.get(seg.name, {})
        if not times:
            continue
        time_values = list(times.values())
        best_t = min(time_values)
        avg_t = float(np.mean(time_values))
        gain = avg_t - best_t
        best_lap_num = min(
            (lap for lap, t in times.items() if t == best_t),
        )
        segment_gains.append(
            SegmentGain(
                segment=seg,
                best_time_s=round(best_t, 4),
                avg_time_s=round(avg_t, 4),
                gain_s=round(gain, 4),
                best_lap=best_lap_num,
                lap_times_s=times,
            )
        )
        total_gain += gain

    return ConsistencyGainResult(
        segment_gains=segment_gains,
        total_gain_s=round(total_gain, 4),
        avg_lap_time_s=round(avg_lap_time, 4),
        best_lap_time_s=round(best_lap_time, 4),
    )


def compute_composite_gain(
    segment_times: dict[str, dict[int, float]],
    segments: list[SegmentDefinition],
    best_lap_time_s: float,
) -> CompositeGainResult:
    """Layer 2: composite lap from best segment times.

    For each segment, pick the fastest time across all laps. The composite
    time is the sum of all segment bests. Gain = best_lap_time - composite_time.
    """
    segment_gains: list[SegmentGain] = []
    composite_time = 0.0

    for seg in segments:
        times = segment_times.get(seg.name, {})
        if not times:
            continue
        time_values = list(times.values())
        best_t = min(time_values)
        best_lap_num = min(
            (lap for lap, t in times.items() if t == best_t),
        )
        avg_t = float(np.mean(time_values))
        gain = avg_t - best_t

        segment_gains.append(
            SegmentGain(
                segment=seg,
                best_time_s=round(best_t, 4),
                avg_time_s=round(avg_t, 4),
                gain_s=round(gain, 4),
                best_lap=best_lap_num,
                lap_times_s=times,
            )
        )
        composite_time += best_t

    total_gain = max(0.0, best_lap_time_s - composite_time)

    return CompositeGainResult(
        segment_gains=segment_gains,
        composite_time_s=round(composite_time, 4),
        best_lap_time_s=round(best_lap_time_s, 4),
        gain_s=round(total_gain, 4),
    )


def compute_theoretical_best(
    resampled_laps: dict[int, pd.DataFrame],
    clean_laps: list[int],
    best_lap_time_s: float,
    sector_size_m: float = 10.0,
) -> TheoreticalBestResult:
    """Layer 3: theoretical best via micro-sectors.

    Split the track into sectors of ``sector_size_m``. For each sector on each
    clean lap, compute elapsed time. Take the minimum per sector across all laps.
    Sum of all best sector times = theoretical best.
    """
    # Determine track length from the longest clean lap distance
    max_dist = 0.0
    for lap_num in clean_laps:
        if lap_num in resampled_laps:
            d = float(resampled_laps[lap_num]["lap_distance_m"].iloc[-1])
            max_dist = max(max_dist, d)

    if max_dist < sector_size_m:
        return TheoreticalBestResult(
            sector_size_m=sector_size_m,
            n_sectors=0,
            theoretical_time_s=best_lap_time_s,
            best_lap_time_s=round(best_lap_time_s, 4),
            gain_s=0.0,
        )

    sector_boundaries = np.arange(0, max_dist, sector_size_m)
    # Always include the track end as the final boundary
    if sector_boundaries[-1] < max_dist - 1e-6:
        sector_boundaries = np.append(sector_boundaries, max_dist)

    n_sectors = len(sector_boundaries) - 1

    # Interpolate time at each boundary for each clean lap
    boundary_times: dict[int, np.ndarray] = {}
    for lap_num in clean_laps:
        if lap_num not in resampled_laps:
            continue
        lap_df = resampled_laps[lap_num]
        dist = lap_df["lap_distance_m"].to_numpy()
        time = lap_df["lap_time_s"].to_numpy()
        interp_times = np.interp(sector_boundaries, dist, time)
        boundary_times[lap_num] = interp_times

    if not boundary_times:
        return TheoreticalBestResult(
            sector_size_m=sector_size_m,
            n_sectors=n_sectors,
            theoretical_time_s=best_lap_time_s,
            best_lap_time_s=round(best_lap_time_s, 4),
            gain_s=0.0,
        )

    # For each micro-sector, find the minimum elapsed time
    all_boundary_arrays = np.array(list(boundary_times.values()))
    # Sector times: diff between consecutive boundaries per lap
    sector_times_per_lap = np.diff(all_boundary_arrays, axis=1)
    # Best time per micro-sector
    best_sector_times = np.min(sector_times_per_lap, axis=0)
    theoretical_time = float(np.sum(best_sector_times))

    gain = max(0.0, best_lap_time_s - theoretical_time)

    return TheoreticalBestResult(
        sector_size_m=sector_size_m,
        n_sectors=n_sectors,
        theoretical_time_s=round(theoretical_time, 4),
        best_lap_time_s=round(best_lap_time_s, 4),
        gain_s=round(gain, 4),
    )


def estimate_gains(
    resampled_laps: dict[int, pd.DataFrame],
    corners: list[Corner],
    summaries: list[LapSummary],
    clean_laps: list[int],
    best_lap: int,
    optimal_lap_time_s: float | None = None,
) -> GainEstimate:
    """Orchestrate all three gain tiers.

    Parameters
    ----------
    resampled_laps:
        Dict of lap_number -> resampled DataFrame (0.7m intervals).
    corners:
        Detected corners from the reference lap.
    summaries:
        Lap summaries for all laps in the session.
    clean_laps:
        Lap numbers considered clean (non-anomalous).
    best_lap:
        The fastest lap number.
    optimal_lap_time_s:
        If provided, compute a Layer 4 physics gap result comparing the
        composite time against the physics-optimal lap time.

    Returns
    -------
    GainEstimate with consistency, composite, and theoretical results.

    Raises
    ------
    ValueError
        If fewer than 2 clean laps are provided.
    """
    if len(clean_laps) < 2:
        msg = "At least 2 clean laps required for gain estimation."
        raise ValueError(msg)

    # Track length from the best lap
    best_lap_df = resampled_laps[best_lap]
    track_length_m = float(best_lap_df["lap_distance_m"].iloc[-1])

    # Best lap time from summaries
    clean_summaries = [s for s in summaries if s.lap_number in clean_laps]
    best_lap_time_s = float(min(s.lap_time_s for s in clean_summaries))

    segments = build_segments(corners, track_length_m)
    seg_times = compute_segment_times(resampled_laps, segments, clean_laps)

    consistency = compute_consistency_gain(seg_times, segments, summaries, clean_laps)
    composite = compute_composite_gain(seg_times, segments, best_lap_time_s)
    theoretical = compute_theoretical_best(resampled_laps, clean_laps, best_lap_time_s)

    physics_gap: PhysicsGapResult | None = None
    if optimal_lap_time_s is not None:
        physics_gap = PhysicsGapResult(
            optimal_lap_time_s=round(optimal_lap_time_s, 4),
            composite_time_s=round(composite.composite_time_s, 4),
            gap_s=round(max(0.0, composite.composite_time_s - optimal_lap_time_s), 4),
        )

    return GainEstimate(
        consistency=consistency,
        composite=composite,
        theoretical=theoretical,
        clean_lap_numbers=sorted(clean_laps),
        best_lap_number=best_lap,
        physics_gap=physics_gap,
    )


@dataclass
class IdealLap:
    """A composite 'ideal' lap stitched from best segments across all clean laps."""

    distance_m: np.ndarray
    speed_mps: np.ndarray
    segment_sources: list[tuple[str, int]]  # (segment_name, source_lap_number)


def reconstruct_ideal_lap(
    resampled_laps: dict[int, pd.DataFrame],
    segments: list[SegmentDefinition],
    segment_times: dict[str, dict[int, float]],
    clean_laps: list[int],
    best_lap: int,
) -> IdealLap:
    """Reconstruct a composite ideal lap by stitching best-speed segments.

    For each segment, picks the lap with the fastest time through that segment
    and uses its speed trace. The result is a continuous speed-vs-distance trace
    representing the driver's theoretical best performance.

    Parameters
    ----------
    resampled_laps:
        Dict of lap_number -> resampled DataFrame (0.7m intervals).
    segments:
        Ordered list of track segments (corners + straights).
    segment_times:
        Per-segment elapsed times per lap (from compute_segment_times).
    clean_laps:
        Lap numbers considered clean.
    best_lap:
        The fastest overall lap number (used as distance grid reference).

    Returns
    -------
    IdealLap with stitched speed trace and source lap for each segment.
    """
    ref_df = resampled_laps[best_lap]
    ref_distance = ref_df["lap_distance_m"].to_numpy()

    ideal_speed = np.zeros_like(ref_distance, dtype=float)
    segment_sources: list[tuple[str, int]] = []

    for seg in segments:
        times = segment_times.get(seg.name, {})
        source_lap = best_lap if not times else min(times, key=lambda k: times[k])

        segment_sources.append((seg.name, source_lap))

        # Get the source lap's speed data
        if source_lap not in resampled_laps:
            source_lap = best_lap
        source_df = resampled_laps[source_lap]
        source_dist = source_df["lap_distance_m"].to_numpy()
        source_speed = source_df["speed_mps"].to_numpy()

        # Find indices in the reference distance grid for this segment
        mask = (ref_distance >= seg.entry_distance_m) & (ref_distance <= seg.exit_distance_m)

        if not mask.any():
            continue

        # Interpolate source lap speed onto reference distance grid
        interp_speed = np.interp(ref_distance[mask], source_dist, source_speed)
        ideal_speed[mask] = interp_speed

    return IdealLap(
        distance_m=ref_distance,
        speed_mps=ideal_speed,
        segment_sources=segment_sources,
    )

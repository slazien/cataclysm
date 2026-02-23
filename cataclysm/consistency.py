"""Session consistency metrics: lap, corner, and track-position."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from cataclysm.corners import Corner
from cataclysm.engine import LapSummary

MPS_TO_MPH = 2.23694


@dataclass
class LapConsistency:
    """Lap-to-lap timing consistency metrics."""

    std_dev_s: float
    spread_s: float
    mean_abs_consecutive_delta_s: float
    max_consecutive_delta_s: float
    consistency_score: float  # 0-100
    lap_numbers: list[int]
    lap_times_s: list[float]
    consecutive_deltas_s: list[float]


@dataclass
class CornerConsistencyEntry:
    """Consistency metrics for a single corner across laps."""

    corner_number: int
    min_speed_std_mph: float
    min_speed_range_mph: float
    brake_point_std_m: float | None
    throttle_commit_std_m: float | None
    consistency_score: float  # 0-100
    lap_numbers: list[int]
    min_speeds_mph: list[float]


@dataclass
class TrackPositionConsistency:
    """Speed consistency at every distance point around the track."""

    distance_m: np.ndarray
    speed_std_mph: np.ndarray
    speed_mean_mph: np.ndarray
    speed_median_mph: np.ndarray
    n_laps: int
    lat: np.ndarray
    lon: np.ndarray


@dataclass
class SessionConsistency:
    """Aggregated consistency metrics for an entire session."""

    lap_consistency: LapConsistency
    corner_consistency: list[CornerConsistencyEntry]
    track_position: TrackPositionConsistency


def compute_lap_consistency(
    summaries: list[LapSummary],
    anomalous_laps: set[int],
) -> LapConsistency:
    """Compute lap-to-lap timing consistency.

    Filters out anomalous laps, then scores consistency using exponential
    decay on normalised choppiness, spread, and max-jump metrics.
    """
    clean = sorted(
        [s for s in summaries if s.lap_number not in anomalous_laps],
        key=lambda s: s.lap_number,
    )
    lap_numbers = [s.lap_number for s in clean]
    lap_times = [s.lap_time_s for s in clean]

    if len(clean) < 2:
        return LapConsistency(
            std_dev_s=0.0,
            spread_s=0.0,
            mean_abs_consecutive_delta_s=0.0,
            max_consecutive_delta_s=0.0,
            consistency_score=100.0,
            lap_numbers=lap_numbers,
            lap_times_s=lap_times,
            consecutive_deltas_s=[],
        )

    times = np.array(lap_times)
    std_dev_s = float(np.std(times))
    spread_s = float(np.max(times) - np.min(times))

    consecutive_deltas = [abs(lap_times[i + 1] - lap_times[i]) for i in range(len(lap_times) - 1)]
    mean_abs_consecutive_delta_s = float(np.mean(consecutive_deltas))
    max_consecutive_delta_s = float(np.max(consecutive_deltas))

    mean_time = float(np.mean(times))
    choppiness_norm = mean_abs_consecutive_delta_s / mean_time
    spread_norm = spread_s / mean_time
    jump_norm = max_consecutive_delta_s / mean_time

    choppiness_score = float(np.exp(-10.0 * choppiness_norm)) * 100.0
    spread_score = float(np.exp(-8.0 * spread_norm)) * 100.0
    jump_score = float(np.exp(-8.0 * jump_norm)) * 100.0

    raw = 0.4 * choppiness_score + 0.3 * spread_score + 0.3 * jump_score
    score = round(float(np.clip(raw, 0.0, 100.0)), 1)

    return LapConsistency(
        std_dev_s=std_dev_s,
        spread_s=spread_s,
        mean_abs_consecutive_delta_s=mean_abs_consecutive_delta_s,
        max_consecutive_delta_s=max_consecutive_delta_s,
        consistency_score=score,
        lap_numbers=lap_numbers,
        lap_times_s=lap_times,
        consecutive_deltas_s=consecutive_deltas,
    )


def compute_corner_consistency(
    all_lap_corners: dict[int, list[Corner]],
    anomalous_laps: set[int],
) -> list[CornerConsistencyEntry]:
    """Compute per-corner consistency across clean laps.

    For each corner number, gathers min-speed, brake-point, and
    throttle-commit data across laps and scores via exponential decay.
    """
    clean_laps = {
        lap_num: corners
        for lap_num, corners in all_lap_corners.items()
        if lap_num not in anomalous_laps
    }

    if not clean_laps:
        return []

    all_numbers = [c.number for corners in clean_laps.values() for c in corners]
    if not all_numbers:
        return []

    max_corner = max(all_numbers)

    entries: list[CornerConsistencyEntry] = []
    for cn in range(1, max_corner + 1):
        min_speeds_mps: list[float] = []
        brake_points: list[float] = []
        throttle_commits: list[float] = []
        lap_nums: list[int] = []

        for lap_num in sorted(clean_laps):
            corners = clean_laps[lap_num]
            match = [c for c in corners if c.number == cn]
            if not match:
                continue
            corner = match[0]
            lap_nums.append(lap_num)
            min_speeds_mps.append(corner.min_speed_mps)
            if corner.brake_point_m is not None:
                brake_points.append(corner.brake_point_m)
            if corner.throttle_commit_m is not None:
                throttle_commits.append(corner.throttle_commit_m)

        speeds_mph = [s * MPS_TO_MPH for s in min_speeds_mps]

        if len(speeds_mph) < 2:
            entries.append(
                CornerConsistencyEntry(
                    corner_number=cn,
                    min_speed_std_mph=0.0,
                    min_speed_range_mph=0.0,
                    brake_point_std_m=None,
                    throttle_commit_std_m=None,
                    consistency_score=100.0,
                    lap_numbers=lap_nums,
                    min_speeds_mph=speeds_mph,
                )
            )
            continue

        speed_arr = np.array(speeds_mph)
        min_speed_std = float(np.std(speed_arr))
        min_speed_range = float(np.max(speed_arr) - np.min(speed_arr))

        brake_std: float | None = None
        if brake_points:
            brake_std = float(np.std(brake_points))

        throttle_std: float | None = None
        if throttle_commits:
            throttle_std = float(np.std(throttle_commits))

        # Score components
        speed_score = float(np.exp(-0.3 * min_speed_std)) * 100.0
        brake_score = float(np.exp(-0.05 * brake_std)) * 100.0 if brake_std is not None else 100.0
        throttle_score = (
            float(np.exp(-0.05 * throttle_std)) * 100.0 if throttle_std is not None else 100.0
        )

        raw = 0.5 * speed_score + 0.25 * brake_score + 0.25 * throttle_score
        score = round(float(np.clip(raw, 0.0, 100.0)), 1)

        entries.append(
            CornerConsistencyEntry(
                corner_number=cn,
                min_speed_std_mph=min_speed_std,
                min_speed_range_mph=min_speed_range,
                brake_point_std_m=brake_std,
                throttle_commit_std_m=throttle_std,
                consistency_score=score,
                lap_numbers=lap_nums,
                min_speeds_mph=speeds_mph,
            )
        )

    return entries


def compute_track_position_consistency(
    resampled_laps: dict[int, pd.DataFrame],
    ref_lap: int,
    anomalous_laps: set[int],
) -> TrackPositionConsistency:
    """Compute speed std/mean at every distance point around the track.

    Uses the reference lap's distance grid, lat, and lon arrays.  Each
    clean lap's speed is interpolated onto that grid before statistics
    are computed.
    """
    ref_df = resampled_laps[ref_lap]
    ref_distance = ref_df["lap_distance_m"].to_numpy()
    ref_lat = ref_df["lat"].to_numpy()
    ref_lon = ref_df["lon"].to_numpy()

    clean_keys = [k for k in resampled_laps if k not in anomalous_laps]

    speed_arrays: list[np.ndarray] = []
    for lap_num in clean_keys:
        lap_df = resampled_laps[lap_num]
        lap_dist = lap_df["lap_distance_m"].to_numpy()
        lap_speed = lap_df["speed_mps"].to_numpy()
        interp_speed = np.interp(ref_distance, lap_dist, lap_speed)
        speed_arrays.append(interp_speed)

    stacked = np.vstack(speed_arrays)
    speed_std = np.std(stacked, axis=0) * MPS_TO_MPH
    speed_mean = np.mean(stacked, axis=0) * MPS_TO_MPH
    speed_median = np.median(stacked, axis=0) * MPS_TO_MPH

    return TrackPositionConsistency(
        distance_m=ref_distance,
        speed_std_mph=speed_std,
        speed_mean_mph=speed_mean,
        speed_median_mph=speed_median,
        n_laps=len(clean_keys),
        lat=ref_lat,
        lon=ref_lon,
    )


def compute_session_consistency(
    summaries: list[LapSummary],
    all_lap_corners: dict[int, list[Corner]],
    resampled_laps: dict[int, pd.DataFrame],
    ref_lap: int,
    anomalous_laps: set[int],
) -> SessionConsistency:
    """Compute all consistency metrics for a session."""
    return SessionConsistency(
        lap_consistency=compute_lap_consistency(summaries, anomalous_laps),
        corner_consistency=compute_corner_consistency(all_lap_corners, anomalous_laps),
        track_position=compute_track_position_consistency(resampled_laps, ref_lap, anomalous_laps),
    )

"""Core distance-domain engine: lap splitting, resampling, and lap summaries."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

RESAMPLE_STEP_M = 0.7
MIN_LAP_FRACTION = 0.80  # discard laps shorter than 80% of median


@dataclass
class LapSummary:
    """Summary statistics for a single lap."""

    lap_number: int
    lap_time_s: float
    lap_distance_m: float
    max_speed_mps: float


@dataclass
class ProcessedSession:
    """Fully processed session with resampled laps."""

    lap_summaries: list[LapSummary]
    resampled_laps: dict[int, pd.DataFrame]
    best_lap: int


def _split_laps(df: pd.DataFrame) -> dict[int, pd.DataFrame]:
    """Split session DataFrame into per-lap DataFrames using RaceChrono lap_number."""
    valid = df[df["lap_number"].notna()].copy()
    if valid.empty:
        return {}

    valid["lap_number"] = valid["lap_number"].astype(int)
    laps: dict[int, pd.DataFrame] = {}
    for lap_num, group in valid.groupby("lap_number"):
        lap_df = group.copy().reset_index(drop=True)
        if len(lap_df) < 10:
            continue
        laps[int(lap_num)] = lap_df

    return laps


def _compute_lap_distance(lap_df: pd.DataFrame) -> pd.DataFrame:
    """Add a lap_distance_m column (distance from S/F for this lap)."""
    lap_df = lap_df.copy()
    start_dist = lap_df["distance_m"].iloc[0]
    lap_df["lap_distance_m"] = lap_df["distance_m"] - start_dist
    return lap_df


def _compute_lap_time(lap_df: pd.DataFrame) -> pd.DataFrame:
    """Add a lap_time_s column (time from lap start)."""
    lap_df = lap_df.copy()
    start_time = lap_df["elapsed_time"].iloc[0]
    lap_df["lap_time_s"] = lap_df["elapsed_time"] - start_time
    return lap_df


def _resample_lap(lap_df: pd.DataFrame, step_m: float = RESAMPLE_STEP_M) -> pd.DataFrame:
    """Resample a lap at uniform distance intervals.

    Interpolates all channels onto a grid of `step_m` spacing.
    Heading is unwrapped before interpolation to handle 360/0 boundary.
    """
    dist = lap_df["lap_distance_m"].to_numpy()
    max_dist = dist[-1]

    if max_dist < step_m * 10:
        return pd.DataFrame()

    new_dist = np.arange(0, max_dist, step_m)
    result: dict[str, np.ndarray] = {"lap_distance_m": new_dist}

    # Channels to interpolate linearly
    linear_channels = [
        "lap_time_s",
        "speed_mps",
        "lat",
        "lon",
        "altitude_m",
        "lateral_g",
        "longitudinal_g",
        "yaw_rate_dps",
        "x_acc_g",
        "y_acc_g",
        "z_acc_g",
    ]

    for ch in linear_channels:
        if ch not in lap_df.columns:
            continue
        vals = lap_df[ch].to_numpy().astype(float)
        f = interp1d(dist, vals, kind="linear", bounds_error=False, fill_value="extrapolate")
        result[ch] = f(new_dist)

    # Heading: unwrap before interpolation to handle 360/0 discontinuity
    if "heading_deg" in lap_df.columns:
        heading_rad = np.radians(lap_df["heading_deg"].to_numpy().astype(float))
        heading_unwrapped = np.unwrap(heading_rad)
        f_head = interp1d(
            dist, heading_unwrapped, kind="linear", bounds_error=False, fill_value="extrapolate"
        )
        heading_interp = f_head(new_dist)
        result["heading_deg"] = np.degrees(heading_interp) % 360

    return pd.DataFrame(result)


def _filter_short_laps(
    laps: dict[int, pd.DataFrame],
) -> dict[int, pd.DataFrame]:
    """Remove laps shorter than MIN_LAP_FRACTION of the median distance."""
    if len(laps) < 2:
        return laps

    distances = [lap_df["lap_distance_m"].iloc[-1] for lap_df in laps.values()]
    median_dist = float(np.median(distances))
    threshold = median_dist * MIN_LAP_FRACTION

    return {
        num: df
        for num, df in laps.items()
        if df["lap_distance_m"].iloc[-1] >= threshold
    }


def process_session(df: pd.DataFrame) -> ProcessedSession:
    """Process a parsed session DataFrame into resampled, aligned laps.

    Parameters
    ----------
    df:
        DataFrame from ParsedSession.data

    Returns
    -------
    ProcessedSession with lap summaries, resampled laps, and best lap number.
    """
    raw_laps = _split_laps(df)
    if not raw_laps:
        msg = "No laps found in session data. Check that RaceChrono recorded lap numbers."
        raise ValueError(msg)

    # Add per-lap distance and time columns
    prepared: dict[int, pd.DataFrame] = {}
    for num, lap_df in raw_laps.items():
        lap_df = _compute_lap_distance(lap_df)
        lap_df = _compute_lap_time(lap_df)
        prepared[num] = lap_df

    # Filter short laps (out-lap, in-lap, aborted)
    prepared = _filter_short_laps(prepared)
    if not prepared:
        msg = "All laps were filtered out (too short). Check session data."
        raise ValueError(msg)

    # Resample
    resampled: dict[int, pd.DataFrame] = {}
    for num, lap_df in prepared.items():
        resampled_df = _resample_lap(lap_df)
        if not resampled_df.empty:
            resampled[num] = resampled_df

    if not resampled:
        msg = "No laps could be resampled. Check session data quality."
        raise ValueError(msg)

    # Compute summaries
    summaries: list[LapSummary] = []
    for num, lap_df in prepared.items():
        if num not in resampled:
            continue
        lap_time = lap_df["lap_time_s"].iloc[-1]
        lap_dist = lap_df["lap_distance_m"].iloc[-1]
        max_speed = float(lap_df["speed_mps"].max())
        summaries.append(
            LapSummary(
                lap_number=num,
                lap_time_s=round(lap_time, 3),
                lap_distance_m=round(lap_dist, 1),
                max_speed_mps=round(max_speed, 2),
            )
        )

    summaries.sort(key=lambda s: s.lap_time_s)
    best_lap = summaries[0].lap_number

    return ProcessedSession(
        lap_summaries=summaries,
        resampled_laps=resampled,
        best_lap=best_lap,
    )

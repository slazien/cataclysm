"""Equal-distance mini-sector analysis with per-lap timing and classification."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class MiniSector:
    """A single equal-distance sector of the track."""

    index: int
    entry_distance_m: float
    exit_distance_m: float
    gps_points: list[tuple[float, float]]  # (lat, lon) polyline


@dataclass
class MiniSectorLapData:
    """Per-lap timing data across all mini-sectors."""

    lap_number: int
    sector_times_s: list[float]
    deltas_s: list[float]  # vs best sector time (negative = faster)
    classifications: list[str]  # "pb" | "faster" | "slower" | "neutral"


@dataclass
class MiniSectorAnalysis:
    """Complete mini-sector analysis for a session."""

    sectors: list[MiniSector]
    best_sector_times_s: list[float]
    best_sector_laps: list[int]
    lap_data: dict[int, MiniSectorLapData]
    n_sectors: int


def compute_mini_sectors(
    resampled_laps: dict[int, pd.DataFrame],
    clean_laps: list[int],
    best_lap: int,
    n_sectors: int = 20,
) -> MiniSectorAnalysis:
    """Divide track into N equal-distance sectors and compute per-lap timings.

    Parameters
    ----------
    resampled_laps : dict mapping lap_number → DataFrame with lap_distance_m, lap_time_s, lat, lon
    clean_laps : list of valid lap numbers to analyze
    best_lap : overall best lap number (for GPS extraction)
    n_sectors : number of equal sectors

    Returns
    -------
    MiniSectorAnalysis with per-sector GPS, timing, and classification data.
    """
    if not clean_laps or best_lap not in resampled_laps:
        return MiniSectorAnalysis(
            sectors=[],
            best_sector_times_s=[],
            best_sector_laps=[],
            lap_data={},
            n_sectors=n_sectors,
        )

    ref_df = resampled_laps[best_lap]
    track_length = float(ref_df["lap_distance_m"].iloc[-1])
    if track_length <= 0:
        return MiniSectorAnalysis(
            sectors=[],
            best_sector_times_s=[],
            best_sector_laps=[],
            lap_data={},
            n_sectors=n_sectors,
        )

    # Sector boundaries at equal distance intervals
    boundaries = np.linspace(0, track_length, n_sectors + 1)

    # Extract GPS polyline per sector from best lap
    sectors: list[MiniSector] = []
    for i in range(n_sectors):
        entry = boundaries[i]
        exit_ = boundaries[i + 1]
        mask = (ref_df["lap_distance_m"] >= entry) & (ref_df["lap_distance_m"] <= exit_)
        sector_df = ref_df[mask]
        gps_points: list[tuple[float, float]] = []
        if "lat" in sector_df.columns and "lon" in sector_df.columns:
            gps_points = list(
                zip(sector_df["lat"].tolist(), sector_df["lon"].tolist(), strict=False)
            )
        sectors.append(
            MiniSector(
                index=i,
                entry_distance_m=float(entry),
                exit_distance_m=float(exit_),
                gps_points=gps_points,
            )
        )

    # Compute sector times per lap using interpolation
    best_sector_times: list[float] = [float("inf")] * n_sectors
    best_sector_laps: list[int] = [0] * n_sectors
    lap_sector_times: dict[int, list[float]] = {}

    for lap_num in clean_laps:
        if lap_num not in resampled_laps:
            continue
        df = resampled_laps[lap_num]
        dist = df["lap_distance_m"].to_numpy()
        time = df["lap_time_s"].to_numpy()

        # Interpolate time at each boundary
        boundary_times = np.interp(boundaries, dist, time)
        sector_times = [float(boundary_times[i + 1] - boundary_times[i]) for i in range(n_sectors)]
        lap_sector_times[lap_num] = sector_times

        # Track best per sector
        for i, st in enumerate(sector_times):
            if st < best_sector_times[i]:
                best_sector_times[i] = st
                best_sector_laps[i] = lap_num

    # Build per-lap data with deltas and classifications
    lap_data: dict[int, MiniSectorLapData] = {}
    for lap_num, sector_times in lap_sector_times.items():
        deltas = [sector_times[i] - best_sector_times[i] for i in range(n_sectors)]
        # Classify: pb if this lap has the best time, faster if below avg, else slower
        avg_sector = [
            np.mean([lap_sector_times[ln][i] for ln in lap_sector_times]) for i in range(n_sectors)
        ]
        classifications: list[str] = []
        for i in range(n_sectors):
            if abs(deltas[i]) < 0.001:
                classifications.append("pb")
            elif sector_times[i] < avg_sector[i]:
                classifications.append("faster")
            else:
                classifications.append("slower")

        lap_data[lap_num] = MiniSectorLapData(
            lap_number=lap_num,
            sector_times_s=sector_times,
            deltas_s=deltas,
            classifications=classifications,
        )

    return MiniSectorAnalysis(
        sectors=sectors,
        best_sector_times_s=best_sector_times,
        best_sector_laps=best_sector_laps,
        lap_data=lap_data,
        n_sectors=n_sectors,
    )

"""Parse RaceChrono CSV v3 exports into normalized telemetry DataFrames."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

# RaceChrono CSV v3 column positions (0-indexed). Names are duplicated in the
# header row, so we must use positional indexing.
_COL_MAP: dict[int, str] = {
    0: "timestamp",
    2: "lap_number",
    3: "elapsed_time",
    4: "distance_m",
    5: "accuracy_m",
    6: "altitude_m",
    7: "heading_deg",
    11: "lat",
    12: "lon",
    13: "satellites",
    14: "speed_mps",
    17: "lateral_g",
    19: "longitudinal_g",
    22: "x_acc_g",
    23: "y_acc_g",
    24: "z_acc_g",
    28: "yaw_rate_dps",
}

METADATA_LINES = 8  # lines 1-8 (1-indexed) are key-value metadata
HEADER_ROWS = 3  # column names, units, data-source tags
SKIP_ROWS = METADATA_LINES + 1 + HEADER_ROWS  # +1 for the blank line 9

# Quality filters
MAX_ACCURACY_M = 2.0
MIN_SATELLITES = 6


@dataclass
class SessionMetadata:
    """Metadata extracted from the RaceChrono CSV header."""

    track_name: str
    session_date: str
    racechrono_version: str


@dataclass
class ParsedSession:
    """A fully parsed and quality-filtered telemetry session."""

    metadata: SessionMetadata
    data: pd.DataFrame


def _parse_metadata(lines: list[str]) -> SessionMetadata:
    """Extract session metadata from the first 8 lines of a RaceChrono CSV."""
    version = ""
    track_name = ""
    session_date = ""

    version_match = re.search(r"RaceChrono (v[\d.]+)", lines[0])
    if version_match:
        version = version_match.group(1)

    for line in lines[1:METADATA_LINES]:
        stripped = line.strip()
        if stripped.startswith("Track name,"):
            track_name = stripped.split(",", 1)[1].strip().strip('"')
        elif stripped.startswith("Created,"):
            parts = stripped.split(",", 2)
            session_date = parts[1].strip().strip('"')
            if len(parts) > 2:
                session_date += " " + parts[2].strip().strip('"')

    return SessionMetadata(
        track_name=track_name,
        session_date=session_date,
        racechrono_version=version,
    )


def parse_racechrono_csv(source: str | io.IOBase) -> ParsedSession:
    """Parse a RaceChrono CSV v3 file.

    Parameters
    ----------
    source:
        File path or file-like object containing the CSV data.

    Returns
    -------
    ParsedSession with metadata and a quality-filtered DataFrame.
    """
    # Read raw lines for metadata
    head_lines: list[str] = []
    if isinstance(source, str):
        with open(source) as fh:
            head_lines = [next(fh) for _ in range(METADATA_LINES)]
    else:
        pos = source.tell() if hasattr(source, "tell") else 0
        for _ in range(METADATA_LINES):
            raw_line = source.readline()
            decoded = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else str(raw_line)
            head_lines.append(decoded)
        if hasattr(source, "seek"):
            source.seek(pos)

    metadata = _parse_metadata(head_lines)

    # Read data rows -- skip metadata + blank line + 3 header rows
    df = pd.read_csv(
        source,  # type: ignore[arg-type]
        skiprows=SKIP_ROWS,
        header=None,
        low_memory=False,
    )

    # Select and rename only the columns we need
    max_col = max(_COL_MAP.keys())
    if len(df.columns) <= max_col:
        msg = (
            f"CSV has {len(df.columns)} columns but expected at least {max_col + 1}. "
            "Is this a RaceChrono CSV v3 export?"
        )
        raise ValueError(msg)

    df = df[list(_COL_MAP.keys())].rename(columns=_COL_MAP)

    # Coerce numeric types (lap_number may be empty for out-lap)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows missing critical fields
    critical = ["timestamp", "elapsed_time", "lat", "lon", "speed_mps", "distance_m"]
    df = df.dropna(subset=critical)

    # Quality filter
    df = df[df["accuracy_m"] <= MAX_ACCURACY_M]
    df = df[df["satellites"] >= MIN_SATELLITES]

    # Fill missing non-critical IMU fields with 0
    imu_cols = ["lateral_g", "longitudinal_g", "x_acc_g", "y_acc_g", "z_acc_g", "yaw_rate_dps"]
    for col in imu_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0.0)

    df = df.reset_index(drop=True)

    # Sanity: ensure sorted by elapsed_time
    df = df.sort_values("elapsed_time").reset_index(drop=True)

    # Speed sanity: clamp negative values
    df["speed_mps"] = np.maximum(df["speed_mps"].to_numpy(), 0.0)

    return ParsedSession(metadata=metadata, data=df)

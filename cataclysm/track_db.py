"""Track database with official corner positions for known circuits.

For known tracks, corners are placed at fixed fractions of total lap distance
derived from track maps and telemetry analysis.  This bypasses heading-rate
detection entirely, giving exact official corner numbering with zero ambiguity.

For unknown tracks, heading-rate detection with sequential numbering is
used instead (see corners.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from cataclysm.corners import Corner
from cataclysm.landmarks import Landmark, LandmarkType


@dataclass(frozen=True)
class OfficialCorner:
    """An official corner definition for a known track."""

    number: int  # Official corner number (e.g., 1 for T1)
    name: str  # Corner name (e.g., "Charlotte's Web")
    fraction: float  # Apex position as fraction of total lap distance (0.0–1.0)
    lat: float | None = None  # GPS latitude of apex
    lon: float | None = None  # GPS longitude of apex
    character: str | None = None  # "flat" | "lift" | "brake" | None (auto-detect)
    # Coaching knowledge fields
    direction: str | None = None  # "left" | "right"
    corner_type: str | None = None  # "hairpin" | "sweeper" | "chicane" | "kink" | "esses"
    elevation_trend: str | None = None  # "uphill" | "downhill" | "flat" | "crest" | "compression"
    camber: str | None = None  # "positive" | "negative" | "off-camber"
    blind: bool = False  # Blind apex or exit
    coaching_notes: str | None = None  # 1-2 sentence instructor tip


@dataclass(frozen=True)
class TrackLayout:
    """Official layout definition for a known track."""

    name: str
    corners: list[OfficialCorner]
    landmarks: list[Landmark] = field(default_factory=list)
    center_lat: float | None = None
    center_lon: float | None = None
    country: str = ""
    length_m: float | None = None
    elevation_range_m: float | None = None  # max - min altitude across track


# ---------------------------------------------------------------------------
# Known track layouts
# ---------------------------------------------------------------------------
# Fractions are apex positions expressed as % of total lap distance, derived
# from speed-trace analysis of actual session data cross-referenced with the
# Porsche Track Experience corner-by-corner guide.
#
# Sources:
#   - Porsche Driving Experience Birmingham corner guide (T1–T16)
#   - Speed minimums from RaceChrono session data at Barber
#   - racetrackdriving.com track guide

# ---------------------------------------------------------------------------
# Barber Motorsports Park visual landmarks
# ---------------------------------------------------------------------------
# Verified against Google Maps satellite imagery (2026-02) using GPS-to-track-
# distance projection from real telemetry data (5233 GPS points, 3662.4m lap).
# Supplemented with onboard video and public track guides:
#   - racetrackdriving.com Barber guide
#   - NA-Motorsports / Chris Ingle corner-by-corner notes
#   - Wikipedia / BhamWiki facility documentation
#
# Distances derived by projecting satellite-identified GPS coordinates onto the
# actual telemetry track line.  Most landmarks have <15m projection error.

_BARBER_LANDMARKS: list[Landmark] = [
    # --- Start/Finish area ---
    Landmark("S/F gantry", 0.0, LandmarkType.structure, description="Timing gantry"),
    Landmark("pit buildings", 29.0, LandmarkType.structure, description="Garages on left"),
    Landmark("T1 100m board", 85.0, LandmarkType.brake_board),
    # --- T1-T4 Carousel & Hilltop ---
    Landmark("pit exit merge", 299.0, LandmarkType.road, description="Short merge from left"),
    Landmark("T2 outside barrier", 396.0, LandmarkType.barrier),
    Landmark("T4 hilltop crest", 676.0, LandmarkType.natural, description="Blind crest"),
    # --- T5 Charlotte's Web braking zone ---
    Landmark("T5 3 board", 904.0, LandmarkType.brake_board),
    Landmark("T5 2 board", 957.0, LandmarkType.brake_board),
    Landmark("T5 1 board", 1000.0, LandmarkType.brake_board),
    Landmark("T5 gravel trap", 1108.0, LandmarkType.barrier),
    # --- T6-T7 Transition ---
    Landmark("T6 downhill crest", 1201.0, LandmarkType.natural),
    # --- T7-T9 Museum / Corkscrew ---
    Landmark("pedestrian bridge", 1480.0, LandmarkType.structure, description="Span near T7"),
    Landmark(
        "museum building",
        1704.0,
        LandmarkType.structure,
        description="Barber Museum on right",
    ),
    Landmark("T9 compression", 1794.0, LandmarkType.natural, description="Bottom of corkscrew"),
    # --- T10-T11 Esses ---
    Landmark("T10 banked entry", 2121.0, LandmarkType.natural),
    Landmark("T11 exit curb", 2258.0, LandmarkType.curbing),
    # --- T12-T14 Rollercoaster ---
    Landmark("Coca-Cola sign", 2634.0, LandmarkType.sign, description="Visible on left"),
    Landmark("T12 outside barrier", 2672.0, LandmarkType.barrier),
    Landmark("T13 crest", 2757.0, LandmarkType.natural, description="Car goes light"),
    Landmark("T14 apex curb", 2967.0, LandmarkType.curbing),
    # --- T15-T16 Final complex ---
    Landmark("T15 apex curb", 3186.0, LandmarkType.curbing, description="Blind apex"),
    Landmark("T16 late apex curb", 3296.0, LandmarkType.curbing),
    # --- Return to start ---
    Landmark("pit entry", 3550.0, LandmarkType.road),
]


BARBER_MOTORSPORTS_PARK = TrackLayout(
    name="Barber Motorsports Park",
    landmarks=_BARBER_LANDMARKS,
    center_lat=33.5302,
    center_lon=-86.6215,
    country="US",
    length_m=3662.4,
    elevation_range_m=60.0,
    corners=[
        OfficialCorner(
            1,
            "Fast Downhill Left",
            0.05,
            direction="left",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            coaching_notes=(
                "Heavy braking from top speed. Downhill increases stopping distance. "
                "Late apex to set up T2."
            ),
        ),
        OfficialCorner(
            2,
            "Uphill Right",
            0.10,
            direction="right",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes="Uphill helps braking. Carry speed — exit sets up T3 climb.",
        ),
        OfficialCorner(
            3,
            "Uphill Crest",
            0.15,
            direction="left",
            corner_type="kink",
            elevation_trend="crest",
            camber="positive",
            coaching_notes="Car goes light over the crest. Smooth inputs — don't upset the car.",
        ),
        OfficialCorner(
            4,
            "Hilltop Right",
            0.20,
            direction="right",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            coaching_notes=(
                "Downhill exit into long straight to T5. Sacrifice entry for strong exit."
            ),
        ),
        OfficialCorner(
            5,
            "Charlotte's Web",
            0.30,
            direction="right",
            corner_type="hairpin",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Key overtaking spot. Use brake boards. Very late apex — corner tightens at exit."
            ),
        ),
        OfficialCorner(
            6,
            "Downhill Left Kink",
            0.34,
            character="flat",
            direction="left",
            corner_type="kink",
            elevation_trend="downhill",
            coaching_notes="Flat out. Smooth steering — downhill transition to corkscrew.",
        ),
        OfficialCorner(
            7,
            "Corkscrew Entry",
            0.40,
            direction="left",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            coaching_notes="Downhill entry — braking distance is longer. Trail brake to rotate.",
        ),
        OfficialCorner(
            8,
            "Corkscrew Mid",
            0.44,
            direction="right",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            coaching_notes="Steep downhill. Stay patient on throttle — car is still descending.",
        ),
        OfficialCorner(
            9,
            "Corkscrew Exit",
            0.49,
            direction="left",
            corner_type="sweeper",
            elevation_trend="compression",
            coaching_notes="Compression at bottom loads the car. Use the grip to accelerate hard.",
        ),
        OfficialCorner(
            10,
            "Esses Left",
            0.58,
            character="flat",
            direction="left",
            corner_type="esses",
            elevation_trend="flat",
            coaching_notes="Flat out or brief lift. Smooth transition to T11.",
        ),
        OfficialCorner(
            11,
            "Esses Right",
            0.62,
            character="lift",
            direction="right",
            corner_type="esses",
            elevation_trend="flat",
            coaching_notes="Brief lift, not heavy braking. Smooth weight transfer left to right.",
        ),
        OfficialCorner(
            12,
            "Rollercoaster Entry",
            0.73,
            direction="right",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="off-camber",
            blind=True,
            coaching_notes=(
                "Significant downhill, car goes light over crest. Blind entry "
                "— commit to reference points."
            ),
        ),
        OfficialCorner(
            13,
            "Rollercoaster Mid",
            0.76,
            character="flat",
            direction="left",
            corner_type="kink",
            elevation_trend="crest",
            coaching_notes="Car crests and goes light. Stay smooth — don't lift abruptly.",
        ),
        OfficialCorner(
            14,
            "Rollercoaster Exit",
            0.81,
            direction="right",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes="Uphill exit adds grip. Get on power early for the run to T15.",
        ),
        OfficialCorner(
            15,
            "Blind Apex Right",
            0.87,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            blind=True,
            coaching_notes="Blind apex. Don't overdrive — exit speed sets up T16.",
        ),
        OfficialCorner(
            16,
            "Final Left",
            0.90,
            direction="left",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Exit speed onto main straight is critical. Sacrifice entry for strong exit."
            ),
        ),
    ],
)

# ---------------------------------------------------------------------------
# Atlanta Motorsports Park visual landmarks
# ---------------------------------------------------------------------------
# Verification:
#   - GPS centroid from real telemetry: (34.4349, -84.1781)
#   - Median lap distance (10 laps): 2935.0m
#   - Elevation range (GPS altitude): ~30m (404–434m ASL)
#   - Distances below projected from best-lap GPS onto satellite imagery
#   - Session: session_20251214_155803_amp_full_v3.csv (best lap #6)

_AMP_LANDMARKS: list[Landmark] = [
    # --- Start/Finish area ---
    Landmark("S/F gantry", 0.0, LandmarkType.structure, description="Timing gantry"),
    Landmark("pit entry", 59.0, LandmarkType.road, description="Pit lane entry on right"),
    # --- T1 Downhill Hairpin ---
    Landmark("T1 brake board", 104.0, LandmarkType.brake_board),
    # --- T3-T4 Carousel complex ---
    Landmark("carousel apex curb", 591.0, LandmarkType.curbing, description="T4 apex"),
    Landmark("hilltop crest", 645.0, LandmarkType.natural, description="Highest point on track"),
    # --- T5 Downhill Hairpin with brake boards ---
    Landmark("T5 3 board", 910.0, LandmarkType.brake_board, description="300m to T5"),
    Landmark("T5 2 board", 945.0, LandmarkType.brake_board, description="200m to T5"),
    Landmark("T5 1 board", 981.0, LandmarkType.brake_board, description="100m to T5"),
    Landmark("T5 gravel trap", 1067.0, LandmarkType.barrier, description="Runoff on outside"),
    # --- Back straight ---
    Landmark("pit exit merge", 1214.0, LandmarkType.road, description="Pit merge on left"),
    # --- Bridge section ---
    Landmark("T9 apex curb", 1633.0, LandmarkType.curbing),
    Landmark("pedestrian bridge", 1665.0, LandmarkType.structure, description="Overhead bridge"),
    # --- T10-T11 ---
    Landmark("T10 brake board", 1796.0, LandmarkType.brake_board),
    Landmark("The Dip compression", 1889.0, LandmarkType.natural, description="Compression dip"),
    # --- Eau Rouge complex ---
    Landmark("Eau Rouge entry curb", 2044.0, LandmarkType.curbing),
    Landmark("Eau Rouge crest", 2090.0, LandmarkType.natural, description="Crest of Eau Rouge"),
    # --- Final section ---
    Landmark("T16 apex curb", 2759.0, LandmarkType.curbing),
    Landmark("victory lane", 2840.0, LandmarkType.structure, description="Near front straight"),
]

ATLANTA_MOTORSPORTS_PARK = TrackLayout(
    name="Atlanta Motorsports Park",
    landmarks=_AMP_LANDMARKS,
    center_lat=34.4349,
    center_lon=-84.1781,
    country="US",
    length_m=2935.0,
    elevation_range_m=30.0,
    corners=[
        OfficialCorner(
            1,
            "Downhill Hairpin",
            0.059,
            direction="right",
            corner_type="hairpin",
            elevation_trend="downhill",
            camber="off-camber",
            coaching_notes=(
                "Most dangerous turn on track. Heavy braking from top speed into "
                "downhill off-camber right. Don't overdrive — grip drops fast."
            ),
        ),
        OfficialCorner(
            2,
            "Blind Left",
            0.180,
            character="lift",
            direction="left",
            corner_type="kink",
            elevation_trend="uphill",
            camber="positive",
            blind=True,
            coaching_notes="Completely blind minor left. Brief lift at most. Trust the line.",
        ),
        OfficialCorner(
            3,
            "Carousel Entry",
            0.206,
            direction="right",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes="Entry to the carousel complex. Braking while climbing — uphill helps.",
        ),
        OfficialCorner(
            4,
            "The Carousel",
            0.237,
            direction="right",
            corner_type="sweeper",
            elevation_trend="crest",
            camber="positive",
            coaching_notes=(
                "Long constant-radius right. Single steering angle — more throttle "
                "pushes you wide, less throttle tightens the line."
            ),
        ),
        OfficialCorner(
            5,
            "Downhill Hairpin",
            0.353,
            direction="left",
            corner_type="hairpin",
            elevation_trend="downhill",
            camber="off-camber",
            blind=True,
            coaching_notes=(
                "Blind braking zone with countdown boards (3, 2, 1). "
                "Downhill increases stopping distance. Commit to brake markers."
            ),
        ),
        OfficialCorner(
            6,
            "Uphill Right Kink",
            0.373,
            character="lift",
            direction="right",
            corner_type="kink",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes="Quick direction change exiting T5. Brief lift, not heavy braking.",
        ),
        OfficialCorner(
            7,
            "Back Straight Entry",
            0.498,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Second hardest corner behind T3. Slowest point on track — "
                "leads onto the long back straight. Sacrifice entry for exit speed."
            ),
        ),
        OfficialCorner(
            8,
            "Right Kink",
            0.508,
            character="flat",
            direction="right",
            corner_type="kink",
            elevation_trend="flat",
            camber="positive",
            coaching_notes="Flat out. Continuation of T7 arc onto back straight.",
        ),
        OfficialCorner(
            9,
            "Downhill Left Sweeper",
            0.559,
            direction="left",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            coaching_notes="Long sweeping left, downhill. Smooth steering — don't upset the car.",
        ),
        OfficialCorner(
            10,
            "Hard Left Uphill",
            0.610,
            direction="left",
            corner_type="hairpin",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes=(
                "Common section for early turn-in. Delay entry — uphill adds grip. "
                "Positive camber rewards patience."
            ),
        ),
        OfficialCorner(
            11,
            "The Dip",
            0.643,
            direction="right",
            corner_type="sweeper",
            elevation_trend="compression",
            coaching_notes=(
                "Car compresses through the dip, giving extra grip. "
                "Trust the grip and begin accelerating through the compression."
            ),
        ),
        OfficialCorner(
            12,
            "Downhill Left Kink",
            0.661,
            character="lift",
            direction="left",
            corner_type="kink",
            elevation_trend="downhill",
            coaching_notes="Quick left, downhill. Brief lift — transition into Eau Rouge complex.",
        ),
        OfficialCorner(
            13,
            "Eau Rouge Entry",
            0.712,
            character="flat",
            direction="left",
            corner_type="esses",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes=(
                "Start of the Eau Rouge tribute. Flat out — do NOT lift. "
                "Uphill entry, smooth steering through the esses."
            ),
        ),
        OfficialCorner(
            14,
            "Eau Rouge Mid",
            0.814,
            character="flat",
            direction="right",
            corner_type="esses",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Long on-ramp style sweeper — continue accelerating. "
                "Balance throttle through multiple direction changes."
            ),
        ),
        OfficialCorner(
            15,
            "Eau Rouge Exit",
            0.898,
            character="flat",
            direction="left",
            corner_type="esses",
            elevation_trend="flat",
            camber="positive",
            coaching_notes="Exit of Eau Rouge complex. Stay flat, smooth transition to T16.",
        ),
        OfficialCorner(
            16,
            "Final Right",
            0.949,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            blind=True,
            coaching_notes=(
                "Blind quick right before start/finish. Keep your line and hit your marks. "
                "Exit speed onto the main straight is critical."
            ),
        ),
    ],
)

# Registry of known tracks — keys are normalized (lowercased, stripped).
_TRACK_REGISTRY: dict[str, TrackLayout] = {
    "barber motorsports park": BARBER_MOTORSPORTS_PARK,
    "atlanta motorsports park": ATLANTA_MOTORSPORTS_PARK,
    "amp full": ATLANTA_MOTORSPORTS_PARK,
}


def _normalize_name(name: str) -> str:
    """Normalize a track name for lookup."""
    return name.strip().lower()


def lookup_track(track_name: str) -> TrackLayout | None:
    """Look up a known track layout by name.

    Returns None if the track is not in the database.
    """
    return _TRACK_REGISTRY.get(_normalize_name(track_name))


def get_all_tracks() -> list[TrackLayout]:
    """Return all known track layouts."""
    return list(_TRACK_REGISTRY.values())


# ---------------------------------------------------------------------------
# Default corner zone margin
# ---------------------------------------------------------------------------
_ZONE_MARGIN_M = 50.0  # entry/exit margin for first/last corners


def locate_official_corners(
    lap_df: pd.DataFrame,
    layout: TrackLayout,
) -> list[Corner]:
    """Build Corner skeletons at official positions along a lap.

    Each official corner's apex is placed at ``fraction * lap_distance``.
    Entry/exit boundaries are midpoints between adjacent corners.

    The returned Corner objects have placeholder KPI values — pass them to
    ``extract_corner_kpis_for_lap`` to fill in real KPIs.

    Parameters
    ----------
    lap_df:
        Resampled lap DataFrame with a lap_distance_m column.
    layout:
        Official track layout with corner fractions.

    Returns
    -------
    List of Corner skeletons sorted by distance, with official numbers.
    """
    max_dist = float(lap_df["lap_distance_m"].iloc[-1])

    # Sort corners by position on track, keeping the full OfficialCorner reference
    sorted_corners = sorted(layout.corners, key=lambda c: c.fraction)
    apex_positions = [(c, c.fraction * max_dist) for c in sorted_corners]

    # Build skeleton corners with entry/exit at midpoints
    skeletons: list[Corner] = []
    for i, (oc, apex_m) in enumerate(apex_positions):
        if i == 0:
            entry_m = max(0.0, apex_m - _ZONE_MARGIN_M)
        else:
            entry_m = (apex_positions[i - 1][1] + apex_m) / 2

        if i == len(apex_positions) - 1:
            exit_m = min(max_dist, apex_m + _ZONE_MARGIN_M)
        else:
            exit_m = (apex_m + apex_positions[i + 1][1]) / 2

        skeletons.append(
            Corner(
                number=oc.number,
                entry_distance_m=round(entry_m, 1),
                exit_distance_m=round(exit_m, 1),
                apex_distance_m=round(apex_m, 1),
                min_speed_mps=0.0,
                brake_point_m=None,
                peak_brake_g=None,
                throttle_commit_m=None,
                apex_type="mid",
                character=oc.character,
                direction=oc.direction,
                corner_type_hint=oc.corner_type,
                elevation_trend=oc.elevation_trend,
                camber=oc.camber,
                blind=oc.blind,
                coaching_notes=oc.coaching_notes,
            )
        )

    return skeletons

"""Track database with official corner positions for known circuits.

For known tracks, corners are placed at fixed fractions of total lap distance
derived from track maps and telemetry analysis.  This bypasses heading-rate
detection entirely, giving exact official corner numbering with zero ambiguity.

For unknown tracks, heading-rate detection with sequential numbering is
used instead (see corners.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
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
    elevation_range_m=24.0,
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
    # --- T6 Countdown Hairpin with brake boards ---
    Landmark("T6 3 board", 910.0, LandmarkType.brake_board, description="300m to T6"),
    Landmark("T6 2 board", 945.0, LandmarkType.brake_board, description="200m to T6"),
    Landmark("T6 1 board", 981.0, LandmarkType.brake_board, description="100m to T6"),
    Landmark("T6 gravel trap", 1067.0, LandmarkType.barrier, description="Runoff on outside"),
    # --- Back straight ---
    Landmark("pit exit merge", 1214.0, LandmarkType.road, description="Pit merge on left"),
    # --- Bridge section ---
    Landmark("T9 apex curb", 1633.0, LandmarkType.curbing),
    Landmark("pedestrian bridge", 1665.0, LandmarkType.structure, description="Overhead bridge"),
    # --- T10-T11 ---
    Landmark("T10 brake board", 1796.0, LandmarkType.brake_board),
    Landmark("The Dip compression", 1889.0, LandmarkType.natural, description="Compression dip"),
    # --- Eau Rouge complex (T13-T15) ---
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
        # --- Fractions verified against telemetry curvature peaks (2926m track) ---
        # --- Directions from curvature sign: positive = LEFT, negative = RIGHT ---
        OfficialCorner(
            1,
            "Downhill Hairpin",
            0.058,
            direction="left",
            corner_type="hairpin",
            elevation_trend="downhill",
            camber="off-camber",
            coaching_notes=(
                "Most dangerous turn on track. Heavy braking from top speed into "
                "downhill off-camber left. Don't overdrive — grip drops fast."
            ),
        ),
        OfficialCorner(
            2,
            "Uphill Left",
            0.139,
            character="lift",
            direction="left",
            corner_type="kink",
            elevation_trend="uphill",
            camber="positive",
            blind=True,
            coaching_notes="Blind minor left, climbing. Brief lift at most. Trust the line.",
        ),
        OfficialCorner(
            3,
            "Uphill Right",
            0.176,
            direction="right",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes="Right-hand bend approaching the Carousel. Trail-brake into entry.",
        ),
        OfficialCorner(
            4,
            "The Carousel",
            0.237,
            direction="left",
            corner_type="sweeper",
            elevation_trend="crest",
            camber="positive",
            coaching_notes=(
                "Long constant-radius left. Single steering angle — more throttle "
                "pushes you wide, less throttle tightens the line."
            ),
        ),
        OfficialCorner(
            5,
            "Descent Right",
            0.297,
            character="lift",
            direction="right",
            corner_type="kink",
            elevation_trend="downhill",
            coaching_notes="Right-hand bend on the descent from the Carousel. Brief lift.",
        ),
        OfficialCorner(
            6,
            "Countdown Hairpin",
            0.373,
            direction="right",
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
            7,
            "Chicane Right",
            0.448,
            direction="right",
            corner_type="kink",
            elevation_trend="flat",
            coaching_notes=(
                "Right entry of the chicane. Set up wide for a quick "
                "direction change into the left of T8."
            ),
        ),
        OfficialCorner(
            8,
            "Chicane Left",
            0.508,
            direction="left",
            corner_type="sweeper",
            elevation_trend="flat",
            coaching_notes=(
                "Left exit of the chicane onto the back straight. "
                "Sacrifice T7 entry for T8 exit speed — biggest laptime opportunity."
            ),
        ),
        OfficialCorner(
            9,
            "Bridge Right",
            0.554,
            direction="right",
            corner_type="sweeper",
            elevation_trend="downhill",
            coaching_notes="Right sweeper near the pedestrian bridge. Smooth and committed.",
        ),
        OfficialCorner(
            10,
            "The Dip",
            0.608,
            direction="right",
            corner_type="hairpin",
            elevation_trend="compression",
            coaching_notes=(
                "Car compresses through the dip, giving extra grip. "
                "Trust the grip — the compression rewards commitment."
            ),
        ),
        OfficialCorner(
            11,
            "Dip Exit Left",
            0.638,
            direction="left",
            corner_type="sweeper",
            elevation_trend="uphill",
            coaching_notes=(
                "Sharp left exiting the dip. Uphill adds grip. Begin accelerating through the exit."
            ),
        ),
        OfficialCorner(
            12,
            "Downhill Left Kink",
            0.650,
            character="lift",
            direction="left",
            corner_type="kink",
            elevation_trend="downhill",
            coaching_notes="Quick left, downhill. Brief lift — transition into Eau Rouge complex.",
        ),
        OfficialCorner(
            13,
            "Eau Rouge Approach",
            0.690,
            character="flat",
            direction="left",
            corner_type="sweeper",
            elevation_trend="downhill",
            coaching_notes="Beginning of the Eau Rouge tribute. Flat out — do NOT lift.",
        ),
        OfficialCorner(
            14,
            "Eau Rouge Entry",
            0.712,
            character="flat",
            direction="left",
            corner_type="esses",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes=(
                "Main Eau Rouge sweep. Flat out — uphill entry, smooth steering through the esses."
            ),
        ),
        OfficialCorner(
            15,
            "Eau Rouge Mid",
            0.814,
            character="flat",
            direction="left",
            corner_type="esses",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Long on-ramp style sweeper — continue accelerating. "
                "Balance throttle through the gentle left."
            ),
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

# ---------------------------------------------------------------------------
# Roebling Road Raceway visual landmarks
# ---------------------------------------------------------------------------
# Corner numbering consensus (5 sources compared, all agree on 9-turn layout):
#   - Official Roebling Road track map: 9 turns, T7 = RIGHT (loop apex)
#   - SVRA Roebling Road map: 9 turns, T7 = RIGHT (loop apex)
#   - racingcircuits.info map: 9 turns, T7 = RIGHT
#   - racetrackdriving.com guide: 9 turns (but their T7 text describes a left kink
#     AFTER the loop — numbering offset from official; use map, not prose)
#   - na-motorsports.com: 10 turns (splits T5/T6 differently) — noted, not used
#
# Direction fixes (2026-03-02), verified against racingcircuits.info map and
#   GPS heading analysis (T5→T6→T7→T8 trace confirms loop traversal direction):
#   T4: RIGHT→LEFT. "Tricky Entry Right"→"Tricky Entry Left".
#       Physical corner is the leftward bulge between T3 sweeper and T5.
#   T5: LEFT→RIGHT, name "The Hairpin"→"Slow Right". No source uses "The
#       Hairpin". racetrackdriving.com: "the slowest turn"; na-motorsports:
#       "Left 120°" (different numbering); Paddock Pal: "most difficult turn".
#       Car turns RIGHT here to head east toward the big loop.
#   T6: RIGHT→LEFT. "Downhill Right"→"Downhill Left".
#       Entry to the big loop — car turns LEFT from heading SE to heading N.
#   T7: LEFT→RIGHT. "Uphill Left"→"Uphill Right".
#       Apex of the big loop — car reverses from heading N to heading SE.
#   Root cause: algorithm-derived heading-rate signs were trusted over visual
#   source comparison. Heading-rate analysis gets the sign wrong at complex
#   curves where approach curvature differs from the main arc.
#
# Fraction corrections (2026-03-02): labels placed at VISUAL CENTER of each
#   Fractions placed at corner APEX positions, matched visually against the
#   racingcircuits.info reference map (/mnt/d/Downloads/roebling_right.png).
#   Each fraction's GPS lat/lon was cross-referenced against the map layout
#   to verify physical position: T1 bottom-left, T2 top of hairpin,
#   T3 center-left kink, T4 upper-center hairpin apex, T5 center-right turn,
#   T6 big loop entry, T7 big loop apex, T8 loop exit, T9 bottom-right sweeper.
#   Previous fractions had T4-T6 shifted ~1 position early, confirmed by user.
#   Directions verified via heading rate and yaw_rate_dps sign convention.
#   Analysis: scripts/analyze_roebling.py on best lap #8 (10m interval GPS trace).
#
# Verification:
#   - GPS centroid from real telemetry: (32.1682, -81.3218)
#   - Median lap distance (44 laps across 8 sessions): 3200.4m
#   - Elevation range (GPS altitude): ~8m (10–18m ASL) — essentially flat
#   - Session: session_20260111_075431_roebling_road_v3.csv (best lap #8)

_ROEBLING_LANDMARKS: list[Landmark] = [
    # --- Start/Finish area ---
    Landmark("S/F gantry", 0.0, LandmarkType.structure, description="Timing gantry"),
    # --- T1-T2 braking zone ---
    Landmark("T1 turn-in curb", 440.0, LandmarkType.curbing, description="Right side entry"),
    Landmark("T2 exit curb", 810.0, LandmarkType.curbing, description="Usable exit curbing"),
    # --- T4 braking zone ---
    Landmark(
        "T4 braking reference",
        1340.0,
        LandmarkType.curbing,
        description="Reference for brake point into T4 hairpin",
    ),
    # --- T5 area ---
    Landmark("T5 downhill section", 1740.0, LandmarkType.natural, description="Track drops"),
    # --- T7 exit ---
    Landmark("T7 uphill exit", 2250.0, LandmarkType.natural, description="Track climbs back"),
    # --- T8-T9 complex ---
    Landmark("T9 exit curb", 2720.0, LandmarkType.curbing, description="Dips in exit curb"),
    # --- Return to start ---
    Landmark("pit entry", 3050.0, LandmarkType.road, description="Pit lane entry on right"),
]

ROEBLING_ROAD_RACEWAY = TrackLayout(
    name="Roebling Road Raceway",
    landmarks=_ROEBLING_LANDMARKS,
    center_lat=32.1682,
    center_lon=-81.3218,
    country="US",
    length_m=3200.4,
    elevation_range_m=8.0,
    corners=[
        OfficialCorner(
            1,
            "Decreasing Radius Right",
            0.166,
            lat=32.168315,
            lon=-81.328243,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Heavy braking from top speed. Decreasing radius — don't turn in early. "
                "Trail-brake to rotate and find the late apex."
            ),
        ),
        OfficialCorner(
            2,
            "Blind Right",
            0.247,
            lat=32.170062,
            lon=-81.327829,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            blind=True,
            coaching_notes=(
                "Blind apex at the top of the T1-T2 hairpin. Commit to reference points. "
                "Late apex and use full exit curbing."
            ),
        ),
        OfficialCorner(
            3,
            "Fast Left Kink",
            0.341,
            lat=32.168672,
            lon=-81.325200,
            character="flat",
            direction="left",
            corner_type="kink",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Fast left kink after T2 exit. Resist the temptation to lift — "
                "carry speed and trust grip."
            ),
        ),
        OfficialCorner(
            4,
            "Tight Right Hairpin",
            0.460,
            lat=32.169808,
            lon=-81.321811,
            direction="right",
            corner_type="hairpin",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes=(
                "Tight right hairpin at the top of the hill. Heavy braking from 85 mph. "
                "Late apex, slow hands, use all the track on exit heading downhill to T5."
            ),
        ),
        OfficialCorner(
            5,
            "Tight Left",
            0.563,
            lat=32.167811,
            lon=-81.319517,
            direction="left",
            corner_type="hairpin",
            elevation_trend="downhill",
            camber="positive",
            coaching_notes=(
                "Tight left at the bottom of the S-curve. Speed drops to ~55 mph. "
                "Late apex, rotate the car, get on power early for the run to T6."
            ),
        ),
        OfficialCorner(
            6,
            "Loop Entry Right",
            0.635,
            lat=32.169467,
            lon=-81.318641,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Entry to the big right-hand loop (T6-T7). Trail-brake to set the car "
                "and commit to the long right arc. Don't overdrive the entry."
            ),
        ),
        OfficialCorner(
            7,
            "Loop Apex Right",
            0.695,
            lat=32.170306,
            lon=-81.317527,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Apex of the big loop. Constant radius — maintain steady throttle. "
                "Don't let the car drift wide. Use the exit curb."
            ),
        ),
        OfficialCorner(
            8,
            "Long Right Sweeper",
            0.794,
            lat=32.167509,
            lon=-81.316742,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Long right sweeper heading back toward the home straight. "
                "Flat out for lower-power cars, brief lift for fast cars."
            ),
        ),
        OfficialCorner(
            9,
            "Right Sweeper Exit",
            0.851,
            lat=32.166307,
            lon=-81.317900,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Exit of the T8-T9 sweeper complex onto the front straight. "
                "Exit speed is critical — carry momentum for the long straight."
            ),
        ),
    ],
)

# Registry of known tracks — keys are normalized (lowercased, stripped).
_TRACK_REGISTRY: dict[str, TrackLayout] = {
    "barber motorsports park": BARBER_MOTORSPORTS_PARK,
    "atlanta motorsports park": ATLANTA_MOTORSPORTS_PARK,
    "amp full": ATLANTA_MOTORSPORTS_PARK,
    "roebling road": ROEBLING_ROAD_RACEWAY,
    "roebling road raceway": ROEBLING_ROAD_RACEWAY,
}


def _normalize_name(name: str) -> str:
    """Normalize a track name for lookup."""
    return name.strip().lower()


# Weight multipliers by corner_type.  Slow corners (hairpins) have a larger
# speed delta, so a 1 mph exit-speed error costs more time there than at a
# fast kink.  Based on YourDataDriven analysis: dt/dv = -distance/v², so
# slow corners are disproportionately time-sensitive.
_CORNER_TYPE_SEVERITY: dict[str, float] = {
    "hairpin": 3.0,
    "sweeper": 1.5,
    "chicane": 2.0,
    "kink": 0.5,
    "esses": 0.4,
}
_DEFAULT_SEVERITY = 1.0

# Minimum gap (meters) to the next corner for a corner to qualify as "key."
_KEY_CORNER_MIN_GAP_M = 100.0


def _effective_gap_m(
    idx: int,
    sorted_corners: list[OfficialCorner],
    track_len: float,
) -> float:
    """Gap from corner *idx* to the next braking corner.

    Flat-out corners (character="flat") are taken at full throttle and don't
    interrupt the acceleration zone, so we skip over them.  Lift corners
    still require steering and brief deceleration, so they DO count as the
    end of a "straight."
    """
    n = len(sorted_corners)
    cur_frac = sorted_corners[idx].fraction
    # Walk forward, skipping only flat-out corners
    for step in range(1, n):
        j = (idx + step) % n
        nxt = sorted_corners[j]
        if nxt.character == "flat":
            continue
        # Found the next non-flat corner
        nxt_frac = nxt.fraction
        if nxt_frac > cur_frac:
            return (nxt_frac - cur_frac) * track_len
        # Wrapped around
        return (1.0 - cur_frac + nxt_frac) * track_len
    # All other corners are flat — entire track is a "straight"
    return track_len


def get_key_corners(layout: TrackLayout) -> list[tuple[OfficialCorner, float]]:
    """Identify the most important corners for lap time.

    Uses a composite score that combines straight length after the corner
    (Type A factor) with corner severity (speed-delta proxy from corner_type).
    Flat-out and lift corners are excluded since they have minimal technique
    element.  When computing the gap, flat-out and lift corners are skipped
    so the effective "straight" extends to the next real braking corner.

    Returns up to 5 results sorted by composite score descending.
    The second element of each tuple is the effective straight length after
    the corner in meters.
    """
    track_len = layout.length_m or 0.0
    if track_len <= 0 or len(layout.corners) < 2:
        return []

    # (corner, gap_m, score)
    candidates: list[tuple[OfficialCorner, float, float]] = []
    sorted_corners = sorted(layout.corners, key=lambda c: c.fraction)
    for i, c in enumerate(sorted_corners):
        # Skip flat-out and lift corners — no meaningful braking/technique
        if c.character in ("flat", "lift"):
            continue

        gap_m = _effective_gap_m(i, sorted_corners, track_len)
        if gap_m > _KEY_CORNER_MIN_GAP_M:
            severity = _CORNER_TYPE_SEVERITY.get(c.corner_type or "", _DEFAULT_SEVERITY)
            score = gap_m * severity
            candidates.append((c, gap_m, score))

    candidates.sort(key=lambda x: x[2], reverse=True)
    return [(c, gap_m) for c, gap_m, _score in candidates[:5]]


def get_peculiarities(layout: TrackLayout) -> list[tuple[OfficialCorner, str]]:
    """Corners with blind, off-camber, crest, or compression characteristics."""
    result: list[tuple[OfficialCorner, str]] = []
    for c in layout.corners:
        if c.blind:
            result.append((c, "blind apex/exit"))
        if c.camber in ("off-camber", "negative"):
            result.append((c, f"{c.camber} camber"))
        if c.elevation_trend in ("crest", "compression"):
            result.append((c, c.elevation_trend))
    return result


def lookup_track(track_name: str) -> TrackLayout | None:
    """Look up a known track layout by name.

    Returns None if the track is not in the database.
    """
    return _TRACK_REGISTRY.get(_normalize_name(track_name))


def get_all_tracks() -> list[TrackLayout]:
    """Return all known track layouts (deduplicated)."""
    seen: set[int] = set()
    result: list[TrackLayout] = []
    for layout in _TRACK_REGISTRY.values():
        if id(layout) not in seen:
            seen.add(id(layout))
            result.append(layout)
    return result


# ---------------------------------------------------------------------------
# Default corner zone margin
# ---------------------------------------------------------------------------
_ZONE_MARGIN_M = 50.0  # entry/exit margin for first/last corners


def _find_zone_boundaries(
    smoothed_rate: np.ndarray,
    apex_idx: int,
    threshold: float,
    max_len: int,
) -> tuple[int, int]:
    """Walk outward from *apex_idx* until heading rate drops below *threshold*.

    Returns (entry_idx, exit_idx) — the indices where the corner zone begins
    and ends based on actual track geometry.
    """
    # Walk backward from apex to find entry
    entry_idx = apex_idx
    for j in range(apex_idx - 1, -1, -1):
        if smoothed_rate[j] < threshold:
            entry_idx = j + 1
            break
    else:
        entry_idx = 0

    # Walk forward from apex to find exit
    exit_idx = apex_idx
    for j in range(apex_idx + 1, max_len):
        if smoothed_rate[j] < threshold:
            exit_idx = j
            break
    else:
        exit_idx = max_len - 1

    return entry_idx, exit_idx


def locate_official_corners(
    lap_df: pd.DataFrame,
    layout: TrackLayout,
) -> list[Corner]:
    """Build Corner skeletons at official positions along a lap.

    Each official corner's apex is placed at ``fraction * lap_distance``.
    Entry/exit boundaries are found by walking outward from the apex along
    the smoothed heading-rate signal until it drops below the detection
    threshold (same criterion as auto-detection).  Zones are then clamped
    to midpoints between adjacent apexes so they never overlap.

    The returned Corner objects have placeholder KPI values — pass them to
    ``extract_corner_kpis_for_lap`` to fill in real KPIs.
    """
    max_dist = float(lap_df["lap_distance_m"].iloc[-1])
    distance = lap_df["lap_distance_m"].to_numpy()

    # Compute smoothed heading rate if heading data is available
    has_heading = "heading_deg" in lap_df.columns
    smoothed_rate: np.ndarray | None = None
    if has_heading:
        from cataclysm.corners import HEADING_RATE_THRESHOLD, SMOOTHING_WINDOW_M

        step_m = float(np.median(np.diff(distance))) if len(distance) > 1 else 0.7
        heading = lap_df["heading_deg"].to_numpy()
        diff = np.diff(heading)
        diff = (diff + 180) % 360 - 180
        rate = diff / step_m
        rate = np.append(rate, rate[-1])
        window_pts = max(2, int(SMOOTHING_WINDOW_M / step_m))
        kernel = np.ones(window_pts) / window_pts
        smoothed_rate = np.convolve(np.abs(rate), kernel, mode="same")

    # Sort corners by position on track
    sorted_corners = sorted(layout.corners, key=lambda c: c.fraction)
    apex_positions = [(c, c.fraction * max_dist) for c in sorted_corners]

    # For each apex, find geometry-based entry/exit, then clamp to midpoints
    skeletons: list[Corner] = []
    for i, (oc, apex_m) in enumerate(apex_positions):
        # Midpoint clamps so zones never overlap with neighbours
        if i == 0:
            midpoint_before = max(0.0, apex_m - _ZONE_MARGIN_M)
        else:
            midpoint_before = (apex_positions[i - 1][1] + apex_m) / 2

        if i == len(apex_positions) - 1:
            midpoint_after = min(max_dist, apex_m + _ZONE_MARGIN_M)
        else:
            midpoint_after = (apex_m + apex_positions[i + 1][1]) / 2

        if smoothed_rate is not None:
            # Curvature-aware: walk outward from apex until heading rate drops
            apex_idx = int(np.searchsorted(distance, apex_m))
            apex_idx = min(apex_idx, len(distance) - 1)
            geo_entry_idx, geo_exit_idx = _find_zone_boundaries(
                smoothed_rate,
                apex_idx,
                HEADING_RATE_THRESHOLD,
                len(distance),
            )
            geo_entry_m = float(distance[geo_entry_idx])
            geo_exit_m = float(distance[geo_exit_idx])
            entry_m = max(geo_entry_m, midpoint_before)
            exit_m = min(geo_exit_m, midpoint_after)
        else:
            # Fallback: midpoints only (no heading data)
            entry_m = midpoint_before
            exit_m = midpoint_after

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
                name=oc.name,
            )
        )

    return skeletons

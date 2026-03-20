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
    # --- Final Carousel (T13-T15) ---
    Landmark("T13 entry curb", 2044.0, LandmarkType.curbing),
    Landmark(
        "T14 carousel crest", 2090.0, LandmarkType.natural, description="Crest of final carousel"
    ),
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
                "Biggest mistake opportunity on the lap. Downhill braking zone — "
                "grip drops as the track falls away. Late apex to set up the long "
                "run to T3. Turn-in reference: end of the curve on your right. "
                "The track levels out at the exit — use that compression to finish."
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
            coaching_notes=(
                "Right-hand bend wrapping into the Carousel climb. Two-stage curbs: "
                "use the outer black-and-blue curb, NOT the inner solid blue. "
                "Trail-brake through T2 into T3."
            ),
        ),
        OfficialCorner(
            4,
            "The Carousel",
            0.237,
            direction="left",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes=(
                "Long left — cut distance along the inside curb. Uphill entry gives "
                "free braking and extra grip, so charge in. Mid-corner the track "
                "levels out and understeer kicks in — maintenance throttle, stay "
                "tight. Late apex at the end of the curbing to set up T5."
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
            coaching_notes=(
                "Non-event if T4 exit is good. Drops downhill significantly — "
                "left side comes up fast. Creates acceleration zone T5→T6 braking."
            ),
        ),
        OfficialCorner(
            6,
            "Countdown Hairpin",
            0.373,
            direction="right",
            corner_type="hairpin",
            elevation_trend="uphill",
            camber="positive",
            blind=True,
            coaching_notes=(
                "Inverse of T1 — uphill braking gives grip so you can charge the "
                "entry. But grip disappears as the track levels out at the exit: "
                "FWD understeers, RWD kicks the rear. Late apex, use all paved "
                "runoff on the left at exit. Countdown boards (3, 2, 1) for reference."
            ),
        ),
        OfficialCorner(
            7,
            "Positioning Right",
            0.448,
            direction="right",
            corner_type="kink",
            elevation_trend="flat",
            coaching_notes=(
                "T7-8-9 is effectively a straight — car placement is everything. "
                "After T6 exit, stay left over the crest, then cross to the right "
                "to be parallel with the T8 apex. This sets up a straight braking "
                "zone to T10."
            ),
        ),
        OfficialCorner(
            8,
            "Positioning Left",
            0.508,
            direction="left",
            corner_type="kink",
            elevation_trend="flat",
            coaching_notes=(
                "Continuation of the positioning straight. End up parallel to the "
                "right side by here. Lazy placement through this section costs time "
                "at T10 — especially with high horsepower."
            ),
        ),
        OfficialCorner(
            9,
            "Bridge Right",
            0.554,
            direction="right",
            corner_type="sweeper",
            elevation_trend="downhill",
            coaching_notes=(
                "Right sweeper near the pedestrian bridge. Quick transition — "
                "braking for T10 happens very fast after this."
            ),
        ),
        OfficialCorner(
            10,
            "Downhill Right",
            0.608,
            direction="right",
            corner_type="sweeper",
            elevation_trend="downhill",
            coaching_notes=(
                "Not much of a corner but the downhill pushes the car wide. "
                "Light brake pressure, turn in early, roll speed through. "
                "Momentum matters more here than hard braking."
            ),
        ),
        OfficialCorner(
            11,
            "The Dip",
            0.638,
            direction="left",
            corner_type="sweeper",
            elevation_trend="compression",
            coaching_notes=(
                "Massive elevation drop into a compression that catches the car. "
                "Get left early after T10 — the later you cross, the less time to "
                "set up. Charge in hard: the compression at the apex hooks the car "
                "around. Braking reference: end of the access road on the left."
            ),
        ),
        OfficialCorner(
            12,
            "Blind Uphill Left",
            0.650,
            direction="left",
            corner_type="sweeper",
            elevation_trend="uphill",
            blind=True,
            coaching_notes=(
                "Most challenging corner to figure out — completely blind, heading "
                "straight uphill. Late apex, then draw a straight line from T12 "
                "apex to T13 apex. Muscle memory corner — reference the end of the "
                "tire wall at the crest before turning left for T13."
            ),
        ),
        OfficialCorner(
            13,
            "Final Carousel Entry",
            0.690,
            direction="left",
            corner_type="sweeper",
            elevation_trend="downhill",
            coaching_notes=(
                "Start of the long final carousel. Cut distance along the inside "
                "curb. At the exit the track levels out with a compression — "
                "that's the heavy acceleration point. Be patient with placement."
            ),
        ),
        OfficialCorner(
            14,
            "Final Carousel Crest",
            0.712,
            character="flat",
            direction="left",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            coaching_notes=(
                "Three-lane trick: from inside lane, let the car track to middle "
                "or outside, then draw a smooth arc back to the inside lane by "
                "the crest here at T14. Accelerate through."
            ),
        ),
        OfficialCorner(
            15,
            "Final Carousel Exit",
            0.814,
            character="flat",
            direction="left",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            coaching_notes=(
                "Track levels out — you can finally see the exit. Let the car wash "
                "to the middle lane, then get back to the inside/left before T16. "
                "Ending up on the left here is the most important part of the "
                "entire carousel."
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
                "Fastest section of the track (100+ mph). Blind but less is more — "
                "10-15° of steering lock max. Turn in when the access road on your "
                "left ends. Look for the flag stand on the right to draw a straight "
                "line through. Exit speed onto the main straight is critical."
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
# Direction verification (2026-03-18): all 9 directions confirmed correct
#   against 8-lap averaged telemetry curvature data (0.7m resolution).
#   Positive curvature = LEFT, negative = RIGHT. No discrepancies.
#
# Metadata validation (2026-03-18): camber, elevation, type, and coaching
#   notes validated against 10+ professional sources (racetrackdriving.com,
#   Condor Speed Shop, Paddock Pal, Blayze, APEX Pro video, Lap of the World
#   video, FLC PCA guide, Paradigm Shift Racing, OpenTrack, Jon Krolewicz PDF).
#   Key corrections: T4/T6 off-camber (was positive), T6 downhill / T7 uphill
#   (only meaningful elevation on circuit), T3 kink→sweeper, T4 hairpin→sweeper,
#   T5 coaching rewritten (patience not early power per APEX Pro coach).
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
        description="Reference for brake point into T4",
    ),
    # --- T5 area ---
    Landmark("T5 slow hairpin", 1740.0, LandmarkType.curbing, description="Slowest corner"),
    # --- T6-T7 elevation ---
    Landmark("T6 downhill entry", 2050.0, LandmarkType.natural, description="Track drops"),
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
            camber="flat",
            coaching_notes=(
                "Entry-speed corner — heavy braking from top speed on diagonal line "
                "from far left. Decreasing radius tightens mid-corner; don't turn in "
                "early. Trail-brake to rotate. Slightly off-camber as radius tightens."
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
            camber="flat",
            blind=True,
            coaching_notes=(
                "Blind apex — commit to consistent reference points. Trail-brake to "
                "help the front end bite into the turn. Late apex, use full exit "
                "curbing. Usable curbing especially helpful in wet."
            ),
        ),
        OfficialCorner(
            3,
            "Fast Left Sweeper",
            0.341,
            lat=32.168672,
            lon=-81.325200,
            character="flat",
            direction="left",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="flat",
            coaching_notes=(
                "One of the two fastest corners on the circuit. Set a single arc from "
                "outside entry to inside apex. Resist the urge to brake — the car "
                "carries far more speed than it feels. Left tire on curb at apex."
            ),
        ),
        OfficialCorner(
            4,
            "Technical Right",
            0.460,
            lat=32.169808,
            lon=-81.321811,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="off-camber",
            coaching_notes=(
                "Slippery entry — gets more off-camber the deeper you go. Hard braking "
                "to 3rd, trail-brake to rotate. Approach as an exit-speed corner: "
                "conservatively late apex, two wheels on apex curbing, early power out."
            ),
        ),
        OfficialCorner(
            5,
            "Slow Left Hairpin",
            0.563,
            lat=32.167811,
            lon=-81.319517,
            direction="left",
            corner_type="hairpin",
            elevation_trend="flat",
            camber="flat",
            coaching_notes=(
                "Slowest corner on the circuit (~180° change). Double apex — use the "
                "first apex to set the angle for the second. BE PATIENT with throttle: "
                "let the chassis settle, then go straight to FULL throttle. Partial "
                "throttle mid-corner unsettles the car. Grip level dramatically "
                "changes the line (R-comp vs street tires)."
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
            elevation_trend="downhill",
            camber="off-camber",
            coaching_notes=(
                "Only meaningful elevation drop on the circuit. Off-camber and "
                "slippery — don't turn in too deep or the rear breaks loose. Late "
                "apex is critical: T6 and T7 are linked. If T6 is done right, T7 is "
                "a non-event. Get on throttle and STAY on it through T7 exit."
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
            elevation_trend="uphill",
            camber="positive",
            coaching_notes=(
                "Uphill compensates for T6 drop — loads the front, forgiving corner. "
                "If T6 was right, carry speed through on throttle. Late-apex character; "
                "rumble strips on inside curb confirm correct line. Upshift on exit."
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
            camber="flat",
            coaching_notes=(
                "T8-T9 are driven as a single sweeping arc. Set a gentle arc from "
                "left to right. Flat out for lower-power cars; higher-power may need "
                "a brief lift entering. Progressive throttle to keep the car planted."
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
            camber="flat",
            coaching_notes=(
                "One of the two fastest corners — and the ONLY wall on the circuit. "
                "Apex reference: grass opening before pit lane entrance. Keep right "
                "side near pit-entry curbing. Exit speed onto the 3200 ft straight is "
                "critical. If traction breaks, straighten immediately — don't fight it."
            ),
        ),
    ],
)

# ---------------------------------------------------------------------------
# WeatherTech Raceway Laguna Seca
# ---------------------------------------------------------------------------
# Sources:
#   - Allen Berg Racing Schools corner-by-corner guide
#   - NASA Speed News "One Lap Around" Laguna Seca
#   - Trackpedia turn-by-turn guide
#   - DIY Sim Studio track guide
#   - WeatherTech Raceway official track information
#   - Track reference: OSM centerline (3601m, 268 nodes / 9 ways)

LAGUNA_SECA = TrackLayout(
    name="WeatherTech Raceway Laguna Seca",
    center_lat=36.584,
    center_lon=-121.753,
    country="US",
    length_m=3602.0,
    elevation_range_m=55.0,  # ~180 ft, primarily from Corkscrew drop
    corners=[
        OfficialCorner(
            number=1,
            name="Turn 1",
            fraction=0.040,
            direction="left",
            corner_type="kink",
            elevation_trend="crest",
            camber="positive",
            blind=True,
            coaching_notes=(
                "Flat-out or near-flat-out over a blind crest; the car goes light "
                "making the rear unsettled. Apex mid-corner and aim right to set up "
                "the brake zone for T2."
            ),
        ),
        OfficialCorner(
            number=2,
            name="Andretti Hairpin",
            fraction=0.105,
            direction="left",
            corner_type="hairpin",
            elevation_trend="flat",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Double-apex left hairpin at the end of the fastest section — prime "
                "overtaking zone under heavy braking. Hit the first apex then let "
                "the car drift out before turning back for the second apex."
            ),
        ),
        OfficialCorner(
            number=3,
            name="Turn 3",
            fraction=0.205,
            direction="right",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="off-camber",
            blind=False,
            coaching_notes=(
                "Harder than it looks — mid-corner speed is where lap time is made. "
                "Avoid braking too late which kills rotation; commit to a confident "
                "entry and get back to throttle immediately after the apex."
            ),
        ),
        OfficialCorner(
            number=4,
            name="Turn 4",
            fraction=0.265,
            direction="right",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Faster than it appears — can be flat or near-flat depending on the "
                "car. Use a light touch of the inside kerb and focus on a clean exit."
            ),
        ),
        OfficialCorner(
            number=5,
            name="Turn 5",
            fraction=0.340,
            direction="left",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Long, tightening left-hander — carry more speed than instinct says, "
                "as slight uphill and positive camber add grip. Exit goes off-camber, "
                "so manage throttle progressively to avoid being pushed wide."
            ),
        ),
        OfficialCorner(
            number=6,
            name="Turn 6",
            fraction=0.440,
            direction="left",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            blind=True,
            coaching_notes=(
                "One of the most demanding corners — fast, blind, and uphill. Commit "
                "fully to turn-in reference; use the inside kerb to rotate, then get "
                "back to power early for maximum speed onto the Rahal Straight."
            ),
        ),
        OfficialCorner(
            number=7,
            name="Turn 7",
            fraction=0.540,
            direction="right",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Braking zone and entry to the Corkscrew complex — brake firmly "
                "uphill in a straight line before turning right. Position the car "
                "on the left on exit to set up the plunge into T8."
            ),
        ),
        OfficialCorner(
            number=8,
            name="Corkscrew",
            fraction=0.615,
            direction="left",
            corner_type="chicane",
            elevation_trend="downhill",
            camber="negative",
            blind=True,
            coaching_notes=(
                "The most famous corner in American motorsport — a blind left-right "
                "chicane dropping 18m in 140m of track. Brake hard in a straight "
                "line, trust your reference points as the world drops away."
            ),
        ),
        OfficialCorner(
            number=9,
            name="Corkscrew Exit",
            fraction=0.640,
            direction="right",
            corner_type="chicane",
            elevation_trend="downhill",
            camber="negative",
            blind=False,
            coaching_notes=(
                "Right-hand exit at the steepest gradient — the car is still falling "
                "steeply, so avoid aggressive inputs. Get straight as quickly as "
                "possible to maximize exit speed toward Rainey Curve."
            ),
        ),
        OfficialCorner(
            number=10,
            name="Rainey Curve",
            fraction=0.730,
            direction="left",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Fast, flowing downhill sweeper named after Wayne Rainey — one of "
                "the highest-speed corners. Brake only enough to allow rotation and "
                "use the camber; manage throttle as banking fades on exit."
            ),
        ),
        OfficialCorner(
            number=11,
            name="Turn 10",
            fraction=0.820,
            direction="right",
            corner_type="sweeper",
            elevation_trend="compression",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Fast right-hander dropping into a well-cambered bowl — the car "
                "loads up heavily gaining speed through the apex. Clip it and "
                "track out fully, then reposition left for the final hairpin."
            ),
        ),
        OfficialCorner(
            number=12,
            name="Turn 11",
            fraction=0.905,
            direction="left",
            corner_type="hairpin",
            elevation_trend="flat",
            camber="positive",
            blind=False,
            coaching_notes=(
                "The most important corner on the circuit — slowest point leading "
                "onto the long front straight. Delay turn-in, trail-brake to rotate, "
                "and prioritize a square exit at full throttle."
            ),
        ),
    ],
)

# ---------------------------------------------------------------------------
# Michelin Raceway Road Atlanta
# ---------------------------------------------------------------------------
# Sources:
#   - iRacing official track page (turn-by-turn descriptions)
#   - racingcircuits.info historical circuit documentation
#   - NASA Southeast driving guides
#   - Track reference: OSM centerline (4090m, 3 ways / 230 nodes)

ROAD_ATLANTA = TrackLayout(
    name="Michelin Raceway Road Atlanta",
    center_lat=34.145,
    center_lon=-83.815,
    country="US",
    length_m=4088.0,
    elevation_range_m=23.0,  # ~75 ft
    corners=[
        OfficialCorner(
            number=1,
            name="Uphill Sweeper",
            fraction=0.050,
            direction="right",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Fast uphill right-hand sweeper at start. Track rises through "
                "the corner adding grip — carry maximum speed and commit early."
            ),
        ),
        OfficialCorner(
            number=2,
            name="Crest Left",
            fraction=0.095,
            direction="left",
            corner_type="sweeper",
            elevation_trend="crest",
            camber="off-camber",
            blind=True,
            coaching_notes=(
                "Left-hander cresting a hill — car goes light over the top. "
                "Use a late turn-in and smooth inputs; the off-camber exit "
                "punishes an early apex."
            ),
        ),
        OfficialCorner(
            number=3,
            name="The Esses Entry",
            fraction=0.140,
            direction="right",
            corner_type="esses",
            elevation_trend="downhill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Entry to the Esses — downhill right-hander beginning the "
                "descent. Set up wide left and take a geometric line to link "
                "into T4."
            ),
        ),
        OfficialCorner(
            number=4,
            name="The Esses Exit",
            fraction=0.175,
            direction="left",
            corner_type="esses",
            elevation_trend="uphill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Uphill left-hand exit of the Esses. Use the elevation change "
                "to help rotate the car and get on power early."
            ),
        ),
        OfficialCorner(
            number=5,
            name="Downhill Kink",
            fraction=0.215,
            direction="right",
            corner_type="kink",
            elevation_trend="downhill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Brief right-hand kink on the short downhill straight before "
                "T6. Flat or near-flat in most cars — position for the hard "
                "braking zone at T6."
            ),
        ),
        OfficialCorner(
            number=6,
            name="Banked Fast Right",
            fraction=0.255,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Banked 90-degree right at high speed. The positive banking "
                "loads the outside tires — carry more speed than feels "
                "comfortable and trust the camber."
            ),
        ),
        OfficialCorner(
            number=7,
            name="Hairpin",
            fraction=0.315,
            direction="left",
            corner_type="hairpin",
            elevation_trend="flat",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Slowest corner on circuit — key overtaking zone. Hard braking "
                "required; use a very late apex to maximize exit speed onto the "
                "long back straight."
            ),
        ),
        OfficialCorner(
            number=8,
            name="Back Straight Chicane Entry",
            fraction=0.530,
            direction="right",
            corner_type="chicane",
            elevation_trend="crest",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Right-hand entry to the chicane mid-back-straight. The track "
                "crests here — stay composed and set up left for the hard left "
                "of T9."
            ),
        ),
        OfficialCorner(
            number=9,
            name="Back Straight Chicane Exit",
            fraction=0.575,
            direction="left",
            corner_type="chicane",
            elevation_trend="downhill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Sharp left completing the chicane; replaced the old 'Dip' in "
                "1996. Track falls away on exit — early throttle causes "
                "understeer."
            ),
        ),
        OfficialCorner(
            number=10,
            name="Bridge Approach",
            fraction=0.720,
            direction="right",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Sweeping right before the bridge complex. Uphill approach "
                "compresses suspension — use the extra grip to carry good "
                "entry speed and position for T11."
            ),
        ),
        OfficialCorner(
            number=11,
            name="Bridge Turn",
            fraction=0.790,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            blind=True,
            coaching_notes=(
                "The iconic thread-the-needle turn under the bridge — blind "
                "apex and tight walls demand precise placement. Commit to your "
                "reference point early."
            ),
        ),
        OfficialCorner(
            number=12,
            name="Roller Coaster",
            fraction=0.910,
            direction="right",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Fast downhill sweeper onto the pit straight — most critical "
                "corner for lap time. Trail-brake to rotate and get on power "
                "before the apex to maximize exit speed."
            ),
        ),
    ],
)

# ---------------------------------------------------------------------------
# Virginia International Raceway — Full Course (5263 m / 3.27 mi, 17 turns)
# ---------------------------------------------------------------------------
# Sources:
#   - Paddock-Pal / racetrackdriving.com VIR Full turn-by-turn (Oleg Pudeyev)
#   - flat6motorsports.com in-depth VIR track visit
#   - na-motorsports.com Hot Lap VIR Full Course guide
#   - Blayze.io VIR coaching articles (Turn 1, Oak Tree, Hog Pen)
#   - NNJR-PCA VIR Turn-by-Turn 2019 PDF
#   - TrackTitan iRacing VIR Full Course guide
#   - Track reference: OSM centerline (5262m, 17 ways / 246 nodes)
# Note: Fractions estimated from layout geometry; refine with telemetry.

VIR_FULL_COURSE = TrackLayout(
    name="Virginia International Raceway",
    center_lat=36.567,
    center_lon=-79.206,
    country="US",
    length_m=5263.0,
    elevation_range_m=40.0,  # ~130 ft (per flat6motorsports)
    corners=[
        OfficialCorner(
            number=1,
            name="Horseshoe",
            fraction=0.04,
            direction="right",
            corner_type="hairpin",
            elevation_trend="flat",
            camber="positive",
            blind=False,
            coaching_notes=(
                "180° right hairpin at the end of the front straight — trail "
                "brake deep and use a late apex to maximize exit speed onto "
                "the short chute to T2."
            ),
        ),
        OfficialCorner(
            number=2,
            name="Right Kink",
            fraction=0.09,
            direction="right",
            corner_type="kink",
            elevation_trend="flat",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Fast kink linking T1 exit to T3 approach — stay right and "
                "hit the apex for position. Line is dictated by the setup "
                "required for T3."
            ),
        ),
        OfficialCorner(
            number=3,
            name="NASCAR Bend",
            fraction=0.14,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Faster than it looks after the 2014 repave. Nail the apex; "
                "named for the 1966 Trans-Am incident. Two lines work: "
                "straight-line brake or smooth arc."
            ),
        ),
        OfficialCorner(
            number=4,
            name="Left Hook",
            fraction=0.19,
            direction="left",
            corner_type="hairpin",
            elevation_trend="flat",
            camber="negative",
            blind=False,
            coaching_notes=(
                "Slow 90° left — use a very late apex to avoid running wide, "
                "because T5 Snake entry begins immediately after. Exit on the "
                "left edge to set up the Snake turn-in."
            ),
        ),
        OfficialCorner(
            number=5,
            name="Snake Entry",
            fraction=0.24,
            direction="right",
            corner_type="esses",
            elevation_trend="uphill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Increasing radius allows most cars to accelerate nearly flat. "
                "Positive camber helps — going wide at the apex increases "
                "camber loss and promotes wash."
            ),
        ),
        OfficialCorner(
            number=6,
            name="Snake Exit",
            fraction=0.29,
            direction="left",
            corner_type="esses",
            elevation_trend="uphill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Should be taken at full power — adjust attitude in T5 to make "
                "this possible. Avoid the inside curb in T6b to preserve exit "
                "line."
            ),
        ),
        OfficialCorner(
            number=7,
            name="Climbing Esses Entry",
            fraction=0.35,
            direction="right",
            corner_type="esses",
            elevation_trend="uphill",
            camber="negative",
            blind=True,
            coaching_notes=(
                "First of VIR's signature uphill esses — crest each hill with "
                "minimal steering angle. Beginners late-apex; advanced drivers "
                "carry more speed. Avoid curbs at speed."
            ),
        ),
        OfficialCorner(
            number=8,
            name="Climbing Esses Mid",
            fraction=0.40,
            direction="right",
            corner_type="esses",
            elevation_trend="crest",
            camber="negative",
            blind=True,
            coaching_notes=(
                "Double-crest section — the only curb worth cutting is the "
                "right inside at 8a. Keep smooth inputs over blind crests; "
                "sudden steering when light causes understeer."
            ),
        ),
        OfficialCorner(
            number=9,
            name="Climbing Esses Exit",
            fraction=0.45,
            direction="right",
            corner_type="esses",
            elevation_trend="crest",
            camber="negative",
            blind=False,
            coaching_notes=(
                "More open than T8 — carry throttle. Never travel in a "
                "straight line between T9 and T10; maintain the arc to set "
                "up the wide entry to South Bend."
            ),
        ),
        OfficialCorner(
            number=10,
            name="South Bend",
            fraction=0.51,
            direction="left",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="negative",
            blind=True,
            coaching_notes=(
                "Blind cresting left that drops steeply on exit. Turn in from "
                "extreme track right; locate the apex early and immediately "
                "shift vision to the track-out point."
            ),
        ),
        OfficialCorner(
            number=11,
            name="Oak Tree Entry",
            fraction=0.57,
            direction="right",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "First element of the Oak Tree complex — brake as late as "
                "possible uphill. Trail off early so weight transfers smoothly "
                "into T12."
            ),
        ),
        OfficialCorner(
            number=12,
            name="Oak Tree",
            fraction=0.62,
            direction="left",
            corner_type="sweeper",
            elevation_trend="uphill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Most important corner for lap time — feeds the long 1219m "
                "back straight. Treat as one sweeper, not two apexes; delay "
                "final throttle until both hands can begin to open."
            ),
        ),
        OfficialCorner(
            number=13,
            name="Uphill Jog",
            fraction=0.67,
            direction="left",
            corner_type="kink",
            elevation_trend="uphill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Short uphill left leading to Roller Coaster — extremely brief "
                "braking zone. Brake late and maintain pressure uphill to T14."
            ),
        ),
        OfficialCorner(
            number=14,
            name="Roller Coaster",
            fraction=0.73,
            direction="right",
            corner_type="sweeper",
            elevation_trend="crest",
            camber="negative",
            blind=True,
            coaching_notes=(
                "VIR's Corkscrew analog — crest/blind right with steep drop on "
                "exit. Trail brake to the apex, ride the inside curb fully. "
                "Benefits greatly from trail braking."
            ),
        ),
        OfficialCorner(
            number=15,
            name="Roller Coaster Exit",
            fraction=0.77,
            direction="left",
            corner_type="sweeper",
            elevation_trend="downhill",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Downhill left with compression at the apex — accelerate as "
                "fully as possible, holding the apex slightly longer than "
                "instinct suggests."
            ),
        ),
        OfficialCorner(
            number=16,
            name="Hog Pen",
            fraction=0.85,
            direction="right",
            corner_type="sweeper",
            elevation_trend="flat",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Two-stage right-left (16a/16b). Brake in two stages; late "
                "apex 16a, minimal runout, then late apex 16b. Use all "
                "available left curb — throttle as early as possible."
            ),
        ),
        OfficialCorner(
            number=17,
            name="Hog Pen Exit",
            fraction=0.93,
            direction="right",
            corner_type="kink",
            elevation_trend="flat",
            camber="positive",
            blind=False,
            coaching_notes=(
                "Opening right beginning the front straight — critical in "
                "high-power cars. The car compresses and traction is better "
                "than expected."
            ),
        ),
    ],
)

# The Grand West Course shares the Full Course corners plus additional
# Patriot Course infield corners.  For validation purposes, use the same
# corner set — the additional corners are in the infield section which
# has minimal impact on lap time ranking.
VIR_GRAND_WEST = TrackLayout(
    name="Virginia International Raceway Grand West",
    center_lat=36.567,
    center_lon=-79.206,
    country="US",
    length_m=6598.0,
    elevation_range_m=40.0,
    corners=VIR_FULL_COURSE.corners,  # Reuse Full Course corners
)

# Registry of known tracks — keys are normalized (lowercased, stripped).
_TRACK_REGISTRY: dict[str, TrackLayout] = {
    "barber motorsports park": BARBER_MOTORSPORTS_PARK,
    "atlanta motorsports park": ATLANTA_MOTORSPORTS_PARK,
    "amp full": ATLANTA_MOTORSPORTS_PARK,
    "roebling road": ROEBLING_ROAD_RACEWAY,
    "roebling road raceway": ROEBLING_ROAD_RACEWAY,
    "laguna seca": LAGUNA_SECA,
    "weathertech raceway laguna seca": LAGUNA_SECA,
    "mazda raceway laguna seca": LAGUNA_SECA,
    "road atlanta": ROAD_ATLANTA,
    "michelin raceway road atlanta": ROAD_ATLANTA,
    "virginia international raceway": VIR_FULL_COURSE,
    "vir": VIR_FULL_COURSE,
    "vir full course": VIR_FULL_COURSE,
    "vir grand west": VIR_GRAND_WEST,
    "virginia international raceway grand west": VIR_GRAND_WEST,
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
            # Fall back to midpoints for gentle corners where heading-rate
            # walk produces a narrow zone.  A sub-2m zone maps to the same
            # index in extract_corner_kpis_for_lap → corner gets dropped.
            if (exit_m - entry_m) < 2.0:
                entry_m = midpoint_before
                exit_m = midpoint_after
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
                nominal_distance_m=round(apex_m, 1),
            )
        )

    return skeletons


# ---------------------------------------------------------------------------
# Track banking data
# ---------------------------------------------------------------------------

# Per-track banking profiles: list of (start_frac, end_frac, banking_deg).
# Fractions are 0-1 of track length. Between entries, banking linearly
# interpolates.  Sections not covered default to 0° (flat).
#
# Sources: iRacing laser scans, sim community measurements, onboard analysis.
# Conservative estimates — err toward flat when uncertain.
TRACK_BANKING: dict[str, list[tuple[float, float, float]]] = {
    # Sources: iRacing laser scan wiki (0–4° range for Barber), driver guides,
    # onboard video analysis. Conservative estimates — err toward flat.
    #
    # Format: (start_frac, end_frac, banking_deg)
    # Positive = banked toward corner center (more grip)
    # Negative = off-camber (less grip)
    "barber-motorsports-park": [
        # T1 (0.05): Fast downhill left — positively banked, iRacing confirms
        (0.03, 0.07, 3.0),
        # T2 (0.10): Uphill right — mildly banked despite off-camber reputation
        # (the off-camber feel comes from elevation change, not lateral banking)
        (0.08, 0.12, 1.5),
        # T3-T4 (0.15-0.20): Uphill crest → hilltop right — mild banking
        (0.13, 0.22, 1.5),
        # T5 (0.30): Charlotte's Web hairpin — slightly off-camber per driver reports
        (0.27, 0.33, -1.0),
        # T7-T9 (0.40-0.49): Corkscrew section — mildly banked through the drop
        (0.38, 0.51, 2.0),
        # T10-T11 (0.58-0.62): Esses — flat out, minimal banking
        (0.56, 0.64, 0.5),
        # T12-T14 (0.73-0.81): Rollercoaster — T12 off-camber, T14 banked
        (0.71, 0.74, -1.5),  # T12 off-camber
        (0.79, 0.83, 2.0),  # T14 banked uphill exit
        # T15-T16 (0.87-0.90): Final corners — positively banked
        (0.85, 0.92, 2.5),
    ],
    # Roebling Road: flat SCCA-era track, ~0° banking everywhere.
    # No iRacing data (not scanned). Community confirms essentially flat.
    # Omitted = None = flat (default behavior).
}


def get_track_banking(
    track_slug: str,
    distance_m: np.ndarray,
) -> np.ndarray | None:
    """Build a per-point banking angle array for a track.

    Returns an array of banking angles in degrees aligned to *distance_m*,
    or None if no banking data is available for the track.

    Banking is linearly interpolated between defined segments.
    """
    segments = TRACK_BANKING.get(track_slug)
    if not segments:
        return None

    total_len = float(distance_m[-1])
    banking = np.zeros(len(distance_m), dtype=np.float64)

    for start_frac, end_frac, deg in segments:
        start_m = start_frac * total_len
        end_m = end_frac * total_len
        mask = (distance_m >= start_m) & (distance_m <= end_m)
        banking[mask] = deg

    return banking

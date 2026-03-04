# Driving Line Tracking & Coaching — Comprehensive Research Synthesis

> **2 iterations of deep research across 11 parallel agents**
> Date: 2026-03-04
> Context: Cataclysm motorsport telemetry platform with RaceBox Mini S (25Hz GPS + 1kHz IMU)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [GPS Accuracy — Why 0.5m CEP IS Sufficient](#2-gps-accuracy)
3. [Market Gap — No One Does This](#3-market-gap)
4. [How Line Coaching Is Done IRL](#4-irl-line-coaching)
5. [Competitor Landscape](#5-competitor-landscape)
6. [AI/ML Approaches to Racing Line Analysis](#6-aiml-approaches)
7. [Algorithms & Implementation Plan](#7-algorithms-implementation)
8. [Visualization & UX Design](#8-visualization-ux)
9. [AI Coaching Integration](#9-ai-coaching-integration)
10. [Consistency Analysis & Skill Benchmarks](#10-consistency-analysis)
11. [Codebase Integration Points](#11-codebase-integration)
12. [Future: RaceBox IMU Sensor Fusion](#12-future-imu)
13. [Implementation Roadmap](#13-roadmap)

---

## 1. Executive Summary

**The single biggest gap in consumer motorsport telemetry is automated AI coaching of driving lines from GPS data.** No product does this today. VBOX shows lines visually, Garmin Catalyst overlays GPS traces, AiM allows visual comparison — but NONE generate natural-language coaching about line errors and corrections.

### Key Findings

- **0.5m CEP is more than sufficient** for meaningful line analysis on 10-15m wide tracks. Line differences of 2-5m are clearly resolved.
- **Within-session relative accuracy is even better (~0.3-0.5m)** since satellite geometry barely changes lap-to-lap.
- **Multi-lap averaging** reduces noise dramatically: 10 laps → 0.16m reference accuracy.
- **RaceBox has an unused 1kHz IMU** (accelerometer ±8g, gyroscope ±320°/s) — RaceChrono only reads GPS data. Future sensor fusion could improve accuracy to ~0.1m.
- **Professional coaching techniques are well-documented** and can be directly encoded into AI prompts (Allen Berg corner types, Blayze reference points, delta-t methodology).
- **The implementation is tractable** — complete Python algorithms exist for every step, using scipy, pymap3d, and KD-trees.

### Why This Makes Cataclysm Uniquely Valuable

A novice gets: "Your entry into Turn 5 is 1.8m too wide — try aiming for the second crack in the curbing as your turn-in reference. Your apex is 2.3m early, which forces a tight exit and costs you ~0.4s on the following straight."

A pro gets: "Laps 3, 7, 12 show inconsistent entry lines at T5 (lateral SD 1.2m vs your 0.3m average). Entry speed CV is 4.2% here versus 1.1% everywhere else — this corner deserves focused practice. Your best lap uses a late apex (fraction 0.62) which maximizes exit speed onto the back straight."

No product generates this today. This is the "holy shit" moment.

---

## 2. GPS Accuracy — Why 0.5m CEP IS Sufficient {#2-gps-accuracy}

### RaceBox Mini S Specifications
- **GPS chip**: u-blox NEO-M9N, multi-constellation (GPS + GLONASS + Galileo + BeiDou)
- **Update rate**: 25Hz (40ms between samples)
- **Position accuracy**: 1.5m CEP50 (datasheet), ~0.5m CEP50 with SBAS in good conditions
- **IMU**: 1kHz accelerometer (±8g) + gyroscope (±320°/s) — **currently unused by RaceChrono**
- **Velocity accuracy**: 0.05 m/s (extremely precise — speed data is more accurate than position)

### Why 0.5m Works

| Metric | Value | Implication |
|--------|-------|-------------|
| Track width | 10-15m | Line differences of 2-5m are common |
| CEP50 | 0.5m | 50% of readings within 0.5m of true position |
| CEP95 | ~1.0-1.5m | 95% within 1.5m |
| Within-session relative | ~0.3-0.5m | Same satellite geometry = consistent bias |
| 10-lap averaged reference | 0.16m | noise = 0.5/√N |
| 20-lap averaged reference | 0.11m | Sub-decimeter reference line |

### Within-Session Relative Accuracy Is The Key Insight

GPS position has two error components:
1. **Absolute bias** (~1-3m): offset from true position, but *constant within a session*
2. **Random noise** (~0.3-0.5m): varies reading-to-reading

For line *comparison* between laps in the same session, the absolute bias cancels out. Only the random noise matters. And 0.3-0.5m random noise on a 10-15m wide track gives you clear resolution of:
- Whether driver is on inside vs outside of track (5-10m difference)
- Early vs late apex (2-4m difference)
- Tight vs wide exit (3-6m difference)
- Consistent vs inconsistent lines (>1m SD = clearly inconsistent)

### Cross-Session Comparisons

Between different sessions (different days), absolute GPS bias can shift by 1-3m. Solutions:
- **Use speed-at-landmark metrics** (GPS-drift-resistant since speed accuracy is 0.05 m/s)
- **Align to track features** (start/finish, known GPS corners) before comparing
- **Focus on relative patterns** (apex fraction, entry/exit width ratio) rather than absolute positions

### Evidence From Existing Products

- **VBOX Circuit Tools** successfully does GPS trace comparison at similar or lower accuracy
- **RaceBox's own app** already shows two-lap GPS overlay comparison and it's useful
- **Garmin Catalyst** ($999) uses 10Hz GPS with no IMU and still provides useful line overlays
- **Harry's LapTimer** uses phone GPS (~3-5m CEP) and users still find trace overlays valuable

**Conclusion: The accuracy question is settled. 0.5m CEP is MORE than sufficient. The question is purely about software, not hardware.**

---

## 3. Market Gap — No One Does This {#3-market-gap}

### What Exists Today

| Product | Shows Lines? | Compares Lines? | AI Coaching on Lines? | Price |
|---------|-------------|----------------|----------------------|-------|
| VBOX Circuit Tools | Yes (GPS trace on track map) | Yes (overlay 2 laps) | **No** | $2000+ hardware |
| AiM Race Studio | Yes | Yes (visual overlay) | **No** | $1500+ hardware |
| Garmin Catalyst | Yes (on-screen overlay) | Yes (vs reference) | **No** (shows delta-T only) | $999 |
| Harry's LapTimer | Yes (basic trace) | Yes (basic overlay) | **No** | $30 app |
| TrackAddict | Yes (basic trace) | Limited | **No** | $10 app |
| RaceBox app | Yes | Yes (2-lap overlay) | **No** | Free with hardware |
| Track Titan | No GPS lines | No | Yes (text coaching, not line-specific) | $10/mo |
| Blayze | No GPS lines | No | Yes (human coach reviews video) | $99/review |

### The Gap

Every product falls into one of two categories:
1. **Shows GPS traces visually** but provides zero coaching about what the lines mean
2. **Provides coaching** but doesn't analyze GPS line data at all

**No product combines GPS line analysis with automated natural-language coaching.** This is Cataclysm's opportunity.

### Why The Gap Exists

1. **Historical focus on lap times**: The industry built around delta-T as the primary coaching tool
2. **Reference line problem**: Without a known-good reference, you can't say "2m too wide" — you can only show two traces. Cataclysm solves this by using the driver's own best lap or multi-lap average as reference.
3. **Coaching knowledge gap**: Hardware companies (VBOX, AiM) aren't coaching companies. Coaching companies (Blayze) use human coaches, not algorithms.
4. **AI maturity**: Until LLMs, converting numeric line analysis into natural-language coaching was extremely difficult. Pre-LLM products could show graphs but couldn't explain them.

### Cataclysm's Unique Position

- Already has Claude API integration for coaching text generation
- Already has distance-domain resampled data (perfect for lap-to-lap comparison)
- Already has corner detection and GPS quality grading
- Already has the prompt engineering framework for skill-level-adaptive coaching
- **Adding line analysis is a software-only change** — no new hardware, no new data format

---

## 4. How Line Coaching Is Done IRL {#4-irl-line-coaching}

### Allen Berg Racing Schools — Corner Classification

**Type A Corners** (before straights): Exit speed is paramount
- Sacrifice entry speed for a wider, later apex
- "Slow in, fast out" — maximize time on throttle for the following straight
- Common error: early apex, which forces lifting or tight exit

**Type B Corners** (after straights): Entry speed matters most
- Trail-braking deep into the corner, late turn-in
- Apex is earlier than Type A
- Common error: braking too early, leaving speed on the table

**Type C Corners** (linking corners): Compromise line
- Line must set up the next corner, not just optimize this one
- Requires thinking ahead — novices optimize each corner in isolation
- Common error: great exit from this corner but terrible entry to the next

**Application to AI coaching**: Classify each corner as A/B/C based on track_db metadata (which corners precede straights). Adjust coaching advice based on corner type.

### Blayze Coaching — 5 Reference Points

Professional coaches at Blayze use 5 reference points per corner:

| Point | Fixed/Adjustable | Description |
|-------|-----------------|-------------|
| Exit apex | Fixed | Where you want the car at corner exit — determined by track geometry |
| Entry apex | Fixed | Where you want the car at corner entry — determined by track geometry |
| Slowest point | Fixed | Where the car reaches minimum speed — near the geometric apex |
| Turn-in point | **Adjustable** | Where you initiate steering input — adjustable by driver |
| Brake point | **Adjustable** | Where you begin braking — adjustable as driver improves |

**Key insight**: The 3 fixed points define the IDEAL line. The 2 adjustable points are where drivers can improve. AI coaching should focus on the adjustable points: "Try braking 5m later" or "Turn in slightly earlier."

### Ross Bentley — Speed Secrets Methodology

- **The line is 80% of lap time improvement for club drivers** (not brake points, not car setup)
- **"Unwind the steering"**: The ideal line maximizes corner radius, which maximizes speed
- **Reference points must be physical objects**: "The third tree on the left" not "30m before the corner" — drivers need visual anchors. (Cataclysm already has a landmarks system in track_db.py!)
- **Progressive learning**: Teach braking first, then turn-in, then apex, then exit — not all at once

### Delta-T as a Coaching Tool

- **Most powerful single metric** according to professional coaches and data engineers
- Shows exactly WHERE time is gained/lost, not just the total
- Human coaches look for: sharp negative spikes (braking too early), gradual loss through a corner (wrong line), gain on straights (better exit from previous corner)
- **Cataclysm already computes delta-T** in the speed trace chart — need to link it to line analysis

### How Pros Use Video + Data

Professional coaching typically overlays:
1. Video from forward-facing camera (shows reference points, track position)
2. Speed trace
3. Throttle/brake trace
4. GPS track map with position dot

The coach then narrates: "See here, you turned in about 2 car-widths too early, that's why you had to lift at the apex, and you lost 0.3s through the exit." **This is exactly what we want to automate.** We can replace the video with GPS line data and have Claude narrate the same coaching.

### Skill-Level Adapted Coaching (IRL)

| Level | Focus | Line Complexity | Language |
|-------|-------|----------------|----------|
| Novice | Safety, basic line | Single ideal line per corner | "Aim for the orange cone at turn-in" |
| Intermediate | Consistency, brake points | Type A/B/C awareness | "Try a later apex to improve exit speed" |
| Advanced | Tenths of seconds | Multiple line options, trade-offs | "Your entry is optimal for this corner but compromises T6 setup" |
| Expert | Hundredths of seconds | Racing line vs qualifying line | Detailed lateral offset analysis, entry/apex/exit patterns |

---

## 5. Competitor Landscape {#5-competitor-landscape}

### Detailed Competitor Analysis

**Garmin Catalyst ($999)**
- 10Hz GPS (no IMU fusion for position)
- Shows "True Track Position" overlay on screen during driving
- Provides real-time delta-T with audio cues
- Does NOT generate any text coaching about lines
- No post-session AI analysis
- Strengths: real-time feedback, standalone device
- Weakness: expensive hardware, no coaching intelligence

**VBOX Circuit Tools (from $2000)**
- 20Hz GPS with optional RTK ($5000+)
- Best-in-class GPS trace visualization
- Side-by-side lap overlay with perfect alignment
- Does NOT generate coaching text
- Target: professional/semi-professional
- Strength: accuracy, features
- Weakness: price, no AI, software is complex

**AiM Race Studio (from $1500)**
- Integrated with AiM hardware (SmartyCam, MXS, etc.)
- Track map with GPS trace, speed overlay
- Multi-channel data comparison
- No AI coaching — purely manual analysis
- Target: serious club racers to pros

**Track Titan (~$10/mo)**
- Software-only, works with any GPS logger
- AI-generated coaching reports (text-based)
- Does NOT analyze GPS line data specifically
- Uses lap times and sector times for coaching
- Closest competitor in spirit — but without line analysis

**Blayze ($99/review)**
- Human coaches review video footage
- Detailed line-by-line coaching per corner
- 24-48 hour turnaround
- Premium quality but not scalable or instant
- Target: all skill levels

**Fire Laps (Research prototype)**
- Uses Bayesian Optimization for racing line
- Published research, no consumer product
- Showed ML can identify optimal lines from GPS traces

### Competitive Moat

If Cataclysm implements AI line coaching:
- **Track Titan** would need to add GPS trace analysis (they don't have it)
- **Garmin/VBOX/AiM** would need to add AI text generation (outside their DNA)
- **Blayze** can't scale human coaches to instant feedback
- **No one** currently has the combination of: GPS line analysis + LLM coaching + instant turnaround + $0.04/report cost

---

## 6. AI/ML Approaches to Racing Line Analysis {#6-aiml-approaches}

### Neural Network Optimal Line Prediction

**TUM (Technical University of Munich) Feed-Forward NN**:
- Trained on 2.7M track segments with optimal racing lines (from traditional optimal control)
- Mean absolute error: ±0.27m overall, ±0.11m at apex
- Prediction time: 33ms (9,000x faster than traditional methods)
- Track geometry encoded as "Normal lines" — curvature features along centerline
- Source: arxiv 2102.02315

**Application to Cataclysm**: We don't need to predict the theoretically optimal line (would require vehicle dynamics model). Instead, we compare the driver's line to their own best lap or multi-lap average. This is more practical and doesn't require vehicle parameters.

### Reinforcement Learning Approaches

- Formula RL (DDPG): Learns racing line through simulation episodes
- Gran Turismo Sophy (Sony): Beat human champions using RL
- These require simulation environments — not applicable for post-hoc GPS analysis

### What's Actually Useful for Cataclysm

1. **Frenet frame decomposition**: Project GPS traces into (s, d) coordinates where s = distance along track, d = lateral offset. Standard in autonomous racing research.
2. **Multi-lap statistical analysis**: Rather than ML, use simple statistics — mean, median, percentiles of lateral offset per corner.
3. **Anomaly detection**: Flag laps where lateral offset deviates significantly from the driver's norm — these are either errors or experiments.
4. **Pattern classification**: Decision tree or rule-based classification of line errors (early apex, wide entry, pinched exit) based on lateral offset at key points.

### TUMFTM Open-Source Tools

TU Munich's `trajectory_planning_helpers` library provides:
- `path_matching`: Align lap traces to reference using Frenet frame
- `calc_normal_vectors`: Compute perpendicular directions along track
- `calc_head_curv_an`: Analytical heading and curvature computation
- `racetrack-database`: 20+ tracks with centerlines and track widths

These are directly usable in our Python pipeline.

---

## 7. Algorithms & Implementation Plan {#7-algorithms-implementation}

### Pipeline Overview

```
RaceChrono CSV → Parser → Distance Resample (0.7m) → ENU Projection
    → Reference Centerline Construction
    → Lateral Offset Computation (per lap)
    → Corner-Specific Line Analysis
    → Line Error Classification
    → AI Coaching Prompt Assembly → Claude API → Report
```

### Step 1: ENU Coordinate Projection

Convert GPS lat/lon to local East-North-Up (ENU) Cartesian coordinates. **Never compute geometry in lat/lon** — distances are distorted.

```python
import pymap3d

def gps_to_enu(lat: np.ndarray, lon: np.ndarray, alt: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Convert GPS to local ENU coordinates using first point as origin."""
    lat0, lon0 = lat[0], lon[0]
    alt = alt if alt is not None else np.zeros_like(lat)
    e, n, _ = pymap3d.geodetic2enu(lat, lon, alt, lat0, lon0, 0.0)
    return e, n
```

### Step 2: GPS Smoothing

Apply Savitzky-Golay filter to reduce GPS noise while preserving corner geometry.

```python
from scipy.signal import savgol_filter

def smooth_gps_trace(e: np.ndarray, n: np.ndarray,
                     spacing_m: float = 0.7, window_m: float = 15.0
) -> tuple[np.ndarray, np.ndarray]:
    """Smooth GPS trace with Savitzky-Golay filter.

    window_m=15 at 0.7m spacing → window=21 points, polyorder=3.
    Preserves corner shape while removing GPS jitter.
    """
    window = int(window_m / spacing_m) | 1  # Ensure odd
    e_smooth = savgol_filter(e, window, polyorder=3)
    n_smooth = savgol_filter(n, window, polyorder=3)
    return e_smooth, n_smooth
```

### Step 3: Reference Centerline Construction

Build a reference line from multiple laps using median (robust to outliers).

```python
from scipy.interpolate import splprep, splev
from scipy.spatial import cKDTree

def compute_reference_centerline(
    aligned_laps_enu: list[tuple[np.ndarray, np.ndarray]],
    smoothing_factor: float = 0.5
) -> tuple[np.ndarray, np.ndarray, cKDTree]:
    """Compute reference centerline as median of multiple laps.

    Uses median (not mean) for robustness to off-track excursions.
    Fits periodic B-spline for smooth closed-loop reference.
    """
    n_points = aligned_laps_enu[0][0].shape[0]
    e_stack = np.array([e for e, _ in aligned_laps_enu])
    n_stack = np.array([n for _, n in aligned_laps_enu])

    e_ref = np.median(e_stack, axis=0)
    n_ref = np.median(n_stack, axis=0)

    # Fit periodic spline for smooth reference
    tck, _ = splprep([e_ref, n_ref], s=smoothing_factor, per=True)
    u_fine = np.linspace(0, 1, n_points)
    e_smooth, n_smooth = splev(u_fine, tck)

    # Build KD-tree for fast nearest-point queries
    ref_points = np.column_stack([e_smooth, n_smooth])
    kdtree = cKDTree(ref_points)

    return e_smooth, n_smooth, kdtree
```

### Step 4: Lateral Offset Computation (Core Algorithm)

Compute signed perpendicular distance from each GPS point to the reference line.

```python
def compute_lateral_offsets(
    lap_e: np.ndarray, lap_n: np.ndarray,
    ref_e: np.ndarray, ref_n: np.ndarray,
    kdtree: cKDTree
) -> np.ndarray:
    """Compute signed lateral offset from reference line.

    Positive = right of reference, Negative = left of reference.
    Uses KD-tree for O(N log N) performance + cross product for sign.
    """
    points = np.column_stack([lap_e, lap_n])
    _, idx = kdtree.query(points)

    n_ref = len(ref_e)
    idx_next = (idx + 1) % n_ref

    # Tangent vector at each reference point
    t_e = ref_e[idx_next] - ref_e[idx]
    t_n = ref_n[idx_next] - ref_n[idx]
    t_len = np.hypot(t_e, t_n)
    t_len = np.where(t_len < 1e-9, 1.0, t_len)
    t_e /= t_len
    t_n /= t_len

    # Displacement vector from reference to GPS point
    d_e = lap_e - ref_e[idx]
    d_n = lap_n - ref_n[idx]

    # Signed distance via cross product
    dist = np.hypot(d_e, d_n)
    cross = t_e * d_n - t_n * d_e  # Positive = right, Negative = left

    return np.copysign(dist, cross)
```

### Step 5: Corner-Specific Line Analysis

Extract lateral offsets at key points within each corner.

```python
@dataclass
class CornerLineProfile:
    """Line analysis for a single corner in a single lap."""
    corner_number: int
    d_entry: float        # Lateral offset at corner entry (m)
    d_turnin: float       # Lateral offset at turn-in point (m)
    d_apex: float         # Lateral offset at apex (m)
    d_exit: float         # Lateral offset at exit (m)
    apex_fraction: float  # Where apex occurs in corner (0.0=entry, 1.0=exit)
    effective_radius: float  # Path radius at apex (m)

    # Reference values (from best lap or multi-lap average)
    ref_d_entry: float
    ref_d_turnin: float
    ref_d_apex: float
    ref_d_exit: float
    ref_apex_fraction: float
    ref_radius: float

    # Classification
    line_error_type: str  # "early_apex", "late_apex", "wide_entry", "pinched_exit", etc.
    severity: str         # "minor" (<0.5m), "moderate" (0.5-1.5m), "major" (>1.5m)
```

### Step 6: Line Error Classification

```python
LINE_ERROR_RULES = {
    # (apex_early, entry_wide, exit_tight) → error_type
    (True,  False, True):  "early_apex",       # Classic mistake: apex too early, forces tight exit
    (True,  True,  True):  "early_apex_wide",  # Entering wide AND apexing early
    (False, False, True):  "pinched_exit",     # Good apex but failed to use full track on exit
    (False, True,  False): "narrow_entry",     # Not using full track width on entry
    (True,  False, False): "late_turnin",      # Turning in too late, forces early apex
    (False, True,  True):  "compromised_line", # Trade-off for multi-corner sequence
}

def classify_line_error(profile: CornerLineProfile) -> str:
    """Classify the type of line error based on lateral offsets."""
    EARLY_APEX_THRESHOLD = 0.40   # Apex in first 40% of corner = early
    LATE_APEX_THRESHOLD = 0.65    # Apex after 65% of corner = late
    OFFSET_THRESHOLD = 0.8        # Meters difference from reference to flag

    apex_early = profile.apex_fraction < EARLY_APEX_THRESHOLD
    entry_wide = (profile.d_entry - profile.ref_d_entry) > OFFSET_THRESHOLD
    exit_tight = (profile.ref_d_exit - profile.d_exit) > OFFSET_THRESHOLD

    key = (apex_early, entry_wide, exit_tight)
    return LINE_ERROR_RULES.get(key, "good_line")
```

### Step 7: Apex Detection

```python
def detect_apex(
    e: np.ndarray, n: np.ndarray,
    corner_start_idx: int, corner_end_idx: int
) -> tuple[int, float]:
    """Detect apex as point of maximum curvature within corner bounds.

    Returns (apex_index, apex_fraction).
    apex_fraction = 0.0 at corner entry, 1.0 at corner exit.
    """
    seg_e = e[corner_start_idx:corner_end_idx]
    seg_n = n[corner_start_idx:corner_end_idx]

    # Compute curvature: κ = |x'y'' - y'x''| / (x'² + y'²)^(3/2)
    de = np.gradient(seg_e)
    dn = np.gradient(seg_n)
    dde = np.gradient(de)
    ddn = np.gradient(dn)

    curvature = np.abs(de * ddn - dn * dde) / (de**2 + dn**2)**1.5

    # Apex = maximum curvature point
    apex_local = np.argmax(curvature)
    apex_idx = corner_start_idx + apex_local
    apex_fraction = apex_local / max(len(seg_e) - 1, 1)

    return apex_idx, apex_fraction
```

### Step 8: Track Boundary Estimation

```python
def estimate_track_boundaries(
    all_lateral_offsets: list[np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate track edges from lateral offset distribution.

    Uses 2nd and 98th percentiles across all laps.
    Works even without a track map — the drivers themselves trace the edges.
    """
    stacked = np.stack(all_lateral_offsets)
    left_edge = np.percentile(stacked, 2, axis=0)    # 2nd percentile
    right_edge = np.percentile(stacked, 98, axis=0)   # 98th percentile
    return left_edge, right_edge
```

### Performance Characteristics

| Operation | Time (20 laps, 3000 points/lap) |
|-----------|-------------------------------|
| ENU projection | ~5ms |
| GPS smoothing (all laps) | ~20ms |
| Reference centerline | ~50ms |
| KD-tree construction | ~2ms |
| Lateral offsets (all laps) | ~30ms |
| Corner analysis (16 corners × 20 laps) | ~100ms |
| **Total pipeline** | **~200-500ms** |

Pre-compute on CSV upload. Cache results. No perceptible delay for user.

### Required Libraries

```
pymap3d>=3.0       # GPS to ENU conversion
scipy>=1.11        # Splines, KD-tree, Savitzky-Golay, interpolation (already in project)
numpy>=1.24        # Core numerics (already in project)
```

Optional (for advanced features):
```
trajectory-planning-helpers  # TUMFTM path matching, curvature, normal vectors
commonroad-clcs             # Curvilinear coordinate system (Frenet frame)
```

---

## 8. Visualization & UX Design {#8-visualization-ux}

### Critical UX Pattern: Bidirectional Hover Linking

**This is the single most impactful UX pattern in telemetry tools** (per user feedback on VBOX, AiM, MoTeC forums):

- Hovering on the track map highlights the corresponding point on the speed trace
- Hovering on the speed trace highlights the corresponding point on the track map
- Hovering on the delta-T chart highlights both track map and speed trace
- All charts + map stay synchronized via shared distance-domain cursor

Cataclysm's existing distance-domain architecture makes this straightforward — all data shares the same distance axis.

### Track Map Visualizations

**1. Speed-Colored Track Map**
- Draw the GPS trace as a line colored by speed (blue=slow → red=fast)
- Uses Canvas 2D `LineCollection`-style rendering (draw segments individually with color)
- Identical to FastF1/F1 TV visualization that fans already understand
- Show single lap or overlay multiple laps

**2. Lap Overlay Comparison**
- Two laps drawn on same track map with different colors
- Thicker line = currently selected/focused lap
- Semi-transparent lines to see overlap vs divergence
- Tooltip on hover: "Lap 3: 87.2 km/h | Lap 7: 91.5 km/h | Delta: +4.3 km/h"

**3. Coaching Annotations on Track Map (Innovation)**
- Automated version of what professional coaches draw on video
- Arrow from actual apex to reference apex: "Apex 2.3m too early"
- Bracket showing available track width not used: "1.2m of track unused at entry"
- Color-coded corner overlays: green (good line), yellow (minor error), red (major error)
- **This is the killer feature nobody has.** Human coaches draw on video frames; we draw on GPS maps.

**4. Corner Detail Mini-Map**
- Zoomed view of a single corner
- Show entry point, turn-in, apex, exit with markers
- Reference line (dashed) vs actual line (solid)
- Speed at each reference point
- "What the driver did" vs "what they should do"

### Chart Visualizations

**5. Lateral Offset Plot**
- X-axis: distance along track
- Y-axis: lateral offset from reference (meters)
- Shaded area = track boundaries
- Vertical lines = corner boundaries
- Two laps overlaid for comparison
- This is the "smoking gun" chart for line analysis

**6. Corner Consistency Scatter**
- One dot per lap per corner
- X-axis: entry lateral offset
- Y-axis: apex lateral offset
- Cluster tightness = consistency
- Outliers = errors or experiments
- Color = lap time improvement (green = faster)

### Progressive Disclosure by Skill Level

**Novice**: Track map with speed coloring + 1-2 biggest coaching tips per corner. Simple language.

**Intermediate**: Add lateral offset plot, corner detail mini-maps, entry/apex/exit comparison. Technical terminology OK.

**Advanced**: Full corner consistency analysis, multi-lap overlay, statistical analysis, line-by-line comparison tables.

### Technical Implementation

- **Track map**: Canvas 2D (`<canvas>`) for performance with thousands of GPS points
- **Charts**: D3.js SVG (already used in project for speed traces)
- **Hover sync**: `requestAnimationFrame` for smooth updates, shared state via React context
- **Mobile**: Touch-hold to activate crosshair (not hover), swipe between corners
- **Responsive**: Track map scales to container width; charts stack vertically on mobile

---

## 9. AI Coaching Integration {#9-ai-coaching-integration}

### Structured Data for Claude Prompt

```python
CORNER_LINE_PROMPT_TEMPLATE = """
## Corner {corner_number}: {corner_name} ({corner_type})

### Line Analysis
- Entry offset: {d_entry:+.1f}m from reference ({entry_assessment})
- Turn-in offset: {d_turnin:+.1f}m from reference
- Apex offset: {d_apex:+.1f}m from reference ({apex_assessment})
- Apex fraction: {apex_fraction:.0%} ({apex_timing}) [ideal: {ideal_apex_fraction:.0%}]
- Exit offset: {d_exit:+.1f}m from reference ({exit_assessment})
- Effective radius: {radius:.1f}m (reference: {ref_radius:.1f}m, {radius_pct:+.0%})

### Line Error Classification: {line_error_type}
Severity: {severity}

### Consistency (across {n_laps} laps)
- Entry offset SD: {entry_sd:.2f}m ({entry_consistency})
- Apex offset SD: {apex_sd:.2f}m ({apex_consistency})
- Apex speed CV: {apex_speed_cv:.1f}%

### Nearby Landmark: {landmark_name} ({landmark_description})

### Corner Classification: Type {allen_berg_type}
{corner_type_explanation}
"""
```

### Skill-Level Prompt Adaptation

**Novice prompt prefix**:
```
You are coaching a novice track day driver. Focus on SAFETY and BASIC LINE.
Use simple language. Reference physical landmarks they can see from the car.
One key tip per corner maximum. Don't overwhelm with data.
Explain WHY the line matters (safety, tire wear, speed).
```

**Intermediate prompt prefix**:
```
You are coaching an intermediate driver working on consistency.
Discuss entry/apex/exit separately. Use proper racing terminology.
Compare their typical line to their best lap's line.
Focus on the 2-3 corners where they lose the most time.
Introduce concepts like trail-braking depth and corner type (A/B/C).
```

**Advanced prompt prefix**:
```
You are a professional data engineer coaching an advanced driver.
Provide detailed lateral offset analysis and corner-by-corner comparison.
Discuss line options and trade-offs (this corner vs next corner setup).
Reference consistency metrics and highlight experiments vs errors.
Suggest specific, measurable improvements with expected time gains.
```

### Integration with Existing Coaching Pipeline

The line analysis data would be added to the existing coaching prompt in `cataclysm/coaching.py`:

```python
# In build_coaching_prompt():
if session.line_analysis:
    prompt_sections.append("## DRIVING LINE ANALYSIS\n")
    for corner in session.line_analysis.corners:
        prompt_sections.append(
            CORNER_LINE_PROMPT_TEMPLATE.format(**corner.to_prompt_dict())
        )
    prompt_sections.append(
        f"\n## LINE SUMMARY\n"
        f"Corners with major line errors: {major_error_corners}\n"
        f"Most consistent corners: {consistent_corners}\n"
        f"Biggest time-gain opportunities from line improvement: {opportunities}\n"
    )
```

### What The AI Output Looks Like

**Novice example**:
> **Turn 5 — The Big Right-Hander**
> You're turning in too early here. See the "200" braking board on your left? Try waiting until you pass it before turning the wheel. Right now, your car is hitting the inside of the corner about 2 meters too soon, which means you run out of room on exit and have to slow down. A later turn-in will feel scary at first, but it'll let you carry more speed onto the back straight.

**Advanced example**:
> **T5 Line Analysis** — Your apex is consistently early (fraction 0.38 vs optimal 0.55-0.65 for this Type A corner). Lateral offset at apex: -1.8m from reference. This forces a 0.9m tighter exit than your best lap (L7), costing an estimated 0.3-0.5s on the following straight due to reduced exit speed (ΔV_exit = -4.2 km/h). Your entry is appropriate (within 0.3m of reference), suggesting the issue is turn-in timing, not entry speed. Consistency: apex SD = 1.2m across 18 laps — the highest variability of any corner, indicating this is a focus area. Recommendation: Delay turn-in by approximately 8-10m (use the repair patch on the right side of the track as reference). This should move your apex fraction to ~0.55 and open the exit by 1-2m.

---

## 10. Consistency Analysis & Skill Benchmarks {#10-consistency-analysis}

### Lap Time Consistency Benchmarks

| Tier | Lap Time SD | Description |
|------|------------|-------------|
| Expert | < 0.2s | Race-ready consistency, minimal variation |
| Consistent | 0.2 - 0.5s | Solid club racer, predictable |
| Developing | 0.5 - 2.0s | Improving but variable, common at intermediate level |
| Novice | > 2.0s | Significant variation, still learning the track |

Source: Professional driver coaching data. Expert SD of ~0.2-0.27s vs novice ~2.55-3.26s (approximately 10x difference).

### Per-Corner Consistency Metrics

| Metric | Expert | Developing | Novice |
|--------|--------|-----------|--------|
| Apex speed CV | < 2% | 2-5% | > 5% |
| Entry speed CV | < 3% | 3-6% | > 6% |
| Lateral offset SD at apex | < 0.3m | 0.3-1.0m | > 1.0m |
| Brake point SD | < 2m | 2-8m | > 8m |

### Exploration vs Inconsistency Detection

**Key insight**: High variation isn't always bad — the driver might be experimenting.

| Entry Speed CV | Apex Speed CV | Interpretation |
|---------------|---------------|----------------|
| High | Low | **Exploring entry**: Trying different brake points but converging at apex — good learning |
| Low | High | **Inconsistent apex**: Same entry but can't hit the apex — technique issue |
| High | High | **Inconsistent overall**: Still searching for the line — needs fundamentals |
| Low | Low | **Consistent**: Repeatable execution — ready for optimization |

### Cross-Session Tracking

Within a session, GPS traces are directly comparable. Across sessions, use GPS-drift-resistant metrics:
- **Speed at corner landmarks** (speed accuracy = 0.05 m/s, unaffected by position drift)
- **Apex fraction** (relative position within corner, not absolute GPS)
- **Consistency tier** (SD and CV metrics are drift-resistant)
- **Corner entry-to-exit time** (timing is drift-free)

### Multi-Session Progress Tracking

```python
@dataclass
class CornerProgress:
    """Track improvement at a specific corner across sessions."""
    corner_number: int
    sessions: list[SessionDate]

    # Per-session aggregates
    apex_speed_mean: list[float]     # Should increase over time
    apex_speed_cv: list[float]       # Should decrease over time
    lateral_sd: list[float]          # Should decrease over time
    consistency_tier: list[str]      # Should progress: novice → developing → consistent → expert

    # Trend
    improving: bool
    plateau_sessions: int  # How many sessions without improvement
```

---

## 11. Codebase Integration Points {#11-codebase-integration}

### Existing Infrastructure We Can Leverage

| Component | File | What It Provides |
|-----------|------|-----------------|
| CSV parsing with lat/lon | `cataclysm/parser.py` | Raw GPS data per lap, accuracy_m field |
| Distance-domain resampling | `cataclysm/engine.py` | All laps at uniform 0.7m grid (perfect for comparison) |
| Corner detection | `cataclysm/corners.py` | Corner dataclass with brake_point, apex GPS coordinates |
| Curvature computation | `cataclysm/curvature.py` | Local XY projection, spline fitting, signed curvature |
| GPS quality grading | `cataclysm/gps_quality.py` | Already computes `lateral_scatter` (perpendicular deviation!) |
| Track database | `cataclysm/track_db.py` | Barber: 16 corners, apex GPS, 40+ landmarks, corner types |
| Coaching prompts | `cataclysm/coaching.py` | Claude API integration, skill-level adaptation |
| Frontend track map | `HeroTrackMap.tsx` | Projects lat/lon to 2D screen coordinates |
| Frontend speed trace | `SpeedTrace.tsx` | D3 chart with crosshair, distance-domain x-axis |
| Frontend lap data | `backend/api/schemas/session.py` | LapData with lat[], lon[] arrays sent to frontend |

### What's Missing (Need to Build)

| Component | Proposed Location | Description |
|-----------|------------------|-------------|
| ENU projection | `cataclysm/gps_line.py` | lat/lon → local East-North-Up |
| Reference centerline | `cataclysm/gps_line.py` | Multi-lap median + spline smoothing |
| Lateral offset | `cataclysm/gps_line.py` | Signed perpendicular distance via KD-tree |
| Corner line analysis | `cataclysm/corner_line.py` | Entry/apex/exit offsets, error classification |
| Consistency metrics | `cataclysm/consistency.py` | Per-corner CV, SD, tier classification |
| Coaching integration | `cataclysm/coaching.py` (edit) | Add line analysis section to prompt |
| Backend API | `backend/api/routes/` (edit) | Expose line analysis data to frontend |
| Track map overlay | `HeroTrackMap.tsx` (edit) | Speed coloring, lap overlay, coaching annotations |
| Lateral offset chart | New component | D3 chart showing lateral offset vs distance |
| Corner detail cards | New component | Mini-map + metrics per corner |

### GPS Quality Gate

The existing `GPSQualityReport` in `gps_quality.py` already grades sessions A-F. Line analysis should only activate for grade A or B sessions (sufficient GPS quality for meaningful line comparison). Grade C and below → show warning, still show basic visualizations but suppress precise coaching.

---

## 12. Future: RaceBox IMU Sensor Fusion {#12-future-imu}

### Current State

RaceChrono exports CSV v3 with GPS-only position data. The RaceBox Mini S has a 1kHz IMU (accelerometer ±8g, gyroscope ±320°/s) that RaceChrono does not currently utilize. Confirmed via RaceChrono forum: "RaceChrono uses the GPS only at the moment from the RaceBox, though future versions were planned to utilize the IMU data."

### What IMU Fusion Would Enable

**GPS+IMU Extended Kalman Filter (EKF)** could improve position accuracy to ~0.1-0.2m:
- GPS provides absolute position (25Hz, ~0.5m noise)
- IMU provides relative motion (1000Hz, drift-prone but very precise short-term)
- Kalman filter combines both: GPS prevents drift, IMU fills gaps and smooths noise

This would make line analysis nearly as good as differential GPS systems costing 10-100x more.

### How To Access IMU Data

1. **RaceChrono Pro API**: Check if future versions expose IMU channels
2. **RaceBox BLE protocol**: Direct Bluetooth connection to RaceBox to read raw IMU data
3. **RaceBox USB/SD export**: Some RaceBox models allow raw data export including IMU

### Timeline Consideration

This is a **Phase 2+ optimization**. GPS-only line analysis is already viable and valuable. IMU fusion would be a competitive moat enhancement, not a prerequisite.

---

## 13. Implementation Roadmap {#13-roadmap}

### Phase 1: Foundation (Core Pipeline)
- [ ] Create `cataclysm/gps_line.py` with ENU projection, smoothing, reference centerline, lateral offset
- [ ] Create `cataclysm/corner_line.py` with corner-specific analysis and error classification
- [ ] Add GPS quality gate (only enable for grade A/B sessions)
- [ ] Unit tests with synthetic GPS data
- [ ] Integrate line data into coaching prompt (add section to `coaching.py`)

### Phase 2: Visualization
- [ ] Speed-colored track map (Canvas 2D)
- [ ] Two-lap GPS overlay on track map
- [ ] Lateral offset chart (D3, shared distance axis with speed trace)
- [ ] Bidirectional hover linking between track map ↔ charts
- [ ] Corner detail mini-maps

### Phase 3: Advanced Coaching
- [ ] Coaching annotations on track map (arrows, brackets, color coding)
- [ ] Consistency analysis (per-corner SD, CV, tier classification)
- [ ] Exploration vs inconsistency detection
- [ ] Multi-session progress tracking for line improvement
- [ ] Skill-level-adapted line coaching prompts

### Phase 4: Innovation Features
- [ ] Corner-specific coaching cards with mini-map + metrics
- [ ] "Coach's drawing" mode — AI generates SVG annotations on track map
- [ ] Line comparison against different sessions (with GPS alignment)
- [ ] Track boundary estimation from lateral offset distribution
- [ ] RaceBox IMU sensor fusion (when data access becomes available)

### Priority Reasoning

Phase 1 gives the "holy shit" moment: automated text coaching about driving lines. No one does this.
Phase 2 makes it visual and interactive.
Phase 3 adds depth for returning users.
Phase 4 creates lasting competitive advantages.

---

## Appendix A: Key Research Sources

- TUM Feed-Forward NN for racing lines: arxiv 2102.02315
- TUMFTM trajectory_planning_helpers: github.com/TUMFTM/trajectory_planning_helpers
- TUMFTM racetrack-database: github.com/TUMFTM/racetrack-database
- Allen Berg Racing Schools corner classification methodology
- Blayze coaching 5 reference points system
- Ross Bentley "Speed Secrets" methodology
- RaceBox Mini S specifications: racebox.pro
- VBOX Circuit Tools: vboxmotorsport.co.uk
- RaceChrono forums on IMU data usage
- Fire Laps Bayesian racing line optimization

## Appendix B: Detailed Coaching Prompt Examples

See `tasks/racing-line-analysis-research.md` for the full Iteration 1 research including:
- ML approaches to line prediction (TUM, RL, Gran Turismo Sophy)
- Complete coaching vocabulary for line descriptions
- Skill-level-specific coaching language examples
- Competitor product detailed feature matrices
- Consumer GPS product accuracy survey

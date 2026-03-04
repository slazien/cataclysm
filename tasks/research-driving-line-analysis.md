# Driving Line Tracking & Analysis — Research Synthesis

> Merged from: `racing-line-analysis-research.md`, `driving-line-tracking-research.md`, `gps_imu_fusion_research.md`
> Date: 2026-03-04
> Context: Cataclysm motorsport telemetry platform with RaceBox Mini S (25Hz GPS + 1kHz IMU)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [GPS Accuracy Analysis](#2-gps-accuracy-analysis)
3. [GPS+IMU Sensor Fusion](#3-gpsimu-sensor-fusion)
4. [Market Gap & Competitor Landscape](#4-market-gap--competitor-landscape)
5. [How Line Coaching Is Done IRL](#5-how-line-coaching-is-done-irl)
6. [AI/ML Approaches](#6-aiml-approaches)
7. [Algorithms & Implementation](#7-algorithms--implementation)
8. [Visualization & UX Design](#8-visualization--ux-design)
9. [AI Coaching Integration](#9-ai-coaching-integration)
10. [Consistency Analysis](#10-consistency-analysis)
11. [Codebase Integration Points](#11-codebase-integration-points)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Sources](#13-sources)

---

## 1. Executive Summary

**The single biggest gap in consumer motorsport telemetry is automated AI coaching of driving lines from GPS data.** No product does this today. VBOX shows lines visually, Garmin Catalyst overlays GPS traces, AiM allows visual comparison — but none generate natural-language coaching about line errors and corrections.

### Key Findings

- **0.5m CEP is more than sufficient** for meaningful line analysis on 10-15m wide tracks. Line differences of 2-5m are clearly resolved.
- **Within-session relative accuracy is even better (~0.3-0.5m)** since satellite geometry barely changes lap-to-lap.
- **Multi-lap averaging** reduces noise dramatically: 10 laps yields 0.16m reference accuracy (noise = 0.5/√N).
- **We already have IMU data** (lateral_g, longitudinal_g, 3-axis accelerometer, yaw rate) — currently unused for position improvement. GPS+IMU fusion could push to ~0.2-0.3m lateral accuracy in a future phase, but is not required for Phase 1.
- **Professional coaching techniques are well-documented** and can be directly encoded into AI prompts: Allen Berg corner types, Blayze reference points, Ross Bentley's Speed Secrets methodology.
- **The implementation is tractable** — complete Python algorithms exist for every step, using scipy, pymap3d, and KD-trees.
- **Adding line analysis is a software-only change** — no new hardware, no new data format.

### The "Holy Shit" Moment

A novice gets: "Your entry into Turn 5 is 1.8m too wide — try aiming for the second crack in the curbing as your turn-in reference. Your apex is 2.3m early, which forces a tight exit and costs you ~0.4s on the following straight."

A pro gets: "Laps 3, 7, 12 show inconsistent entry lines at T5 (lateral SD 1.2m vs your 0.3m average). Entry speed CV is 4.2% here versus 1.1% everywhere else — this corner deserves focused practice. Your best lap uses a late apex (fraction 0.62) which maximizes exit speed onto the back straight."

No product generates this today.

---

## 2. GPS Accuracy Analysis

### RaceBox Mini S Specifications

| Sensor | Spec |
|--------|------|
| GPS chip | u-blox NEO-M9N, multi-constellation (GPS, GLONASS, Galileo, BeiDou) |
| GPS update rate | 25Hz (40ms between samples) |
| GPS position accuracy | 1.5-2.0m CEP (u-blox datasheet), ~0.5m CEP50 with SBAS in good conditions |
| GPS velocity accuracy | 0.05 m/s (extremely precise — more accurate than position) |
| IMU accelerometer | ±8g range, 1kHz internal rate |
| IMU gyroscope | ±320 dps range, 0.02 dps sensitivity |
| RaceChrono export | IMU downsampled to 25Hz to match GPS rate in CSV |

RaceBox claims 10-25cm in ideal open-sky conditions with SBAS. Realistically on track, expect 0.5-1.5m position noise in good conditions.

### Why 0.5m Works for Line Analysis

| Metric | Value | Implication |
|--------|-------|-------------|
| Track width | 10-15m | Line differences of 2-5m are common |
| CEP50 | 0.5m | 50% of readings within 0.5m of true position |
| CEP95 | ~1.0-1.5m | 95% within 1.5m |
| Within-session relative | ~0.3-0.5m | Same satellite geometry = consistent bias |
| 10-lap averaged reference | 0.16m | Noise = 0.5/√N |
| 20-lap averaged reference | 0.11m | Sub-decimeter reference line |

### Within-Session Relative Accuracy Is The Key Insight

GPS position has two error components:
1. **Absolute bias** (~1-3m): offset from true position, but *constant within a session*
2. **Random noise** (~0.3-0.5m): varies reading-to-reading

For line comparison between laps in the same session, the absolute bias cancels out. Only the random noise matters. And 0.3-0.5m random noise on a 10-15m wide track gives clear resolution of:
- Whether driver is on inside vs outside of track (5-10m difference)
- Early vs late apex (2-4m difference)
- Tight vs wide exit (3-6m difference)
- Consistent vs inconsistent lines (>1m SD = clearly inconsistent)

### Cross-Session Comparisons

Between different sessions (different days), absolute GPS bias can shift by 1-3m. Solutions:
- **Use speed-at-landmark metrics** (GPS-drift-resistant since speed accuracy is 0.05 m/s)
- **Align to track features** (start/finish, known GPS corners) before comparing
- **Focus on relative patterns** (apex fraction, entry/exit width ratio) rather than absolute positions

### Evidence from Existing Products

- **VBOX Circuit Tools** successfully does GPS trace comparison at similar or lower accuracy
- **RaceBox's own app** already shows two-lap GPS overlay comparison and it's useful
- **Garmin Catalyst** ($999) uses 10Hz GPS with no IMU and still provides useful line overlays
- **Harry's LapTimer** uses phone GPS (~3-5m CEP) and users still find trace overlays valuable

**Conclusion: The accuracy question is settled. 0.5m CEP is more than sufficient. The question is purely software, not hardware.**

---

## 3. GPS+IMU Sensor Fusion

### Current State — We Already Have IMU Data

RaceChrono CSV v3 exports 6 IMU channels and Cataclysm already parses them:

| CSV Column | Field | Used For |
|-----------|-------|----------|
| 17 | `lateral_g` | G-G diagram, grip estimation, corner analysis |
| 19 | `longitudinal_g` | Brake point detection, throttle commit, corner analysis |
| 22 | `x_acc_g` | Raw accelerometer X-axis |
| 23 | `y_acc_g` | Raw accelerometer Y-axis |
| 24 | `z_acc_g` | Raw accelerometer Z-axis |
| 28 | `yaw_rate_dps` | Yaw rate from gyroscope |

The GPS lat/lon positions are NOT currently fused with IMU data — they are raw GPS positions. RaceChrono does not perform GPS+IMU sensor fusion to improve position accuracy.

### EKF Approach: CTRV Model (Recommended)

The best formulation for Cataclysm's data is the **Constant Turn Rate and Velocity (CTRV)** kinematic model:

**State vector:**
```
x = [x, y, ψ, v, ψ̇]
```
Where: `x, y` = local ENU position (m), `ψ` = heading (rad), `v` = speed (m/s), `ψ̇` = yaw rate (rad/s) — directly measured by RaceBox gyroscope.

**Measurements:**
```
z = [x_gps, y_gps, v_gps, ψ̇_imu]
```

**Why CTRV works for Cataclysm:**
- Yaw rate (`yaw_rate_dps`) is directly in the CSV — no integration needed
- Longitudinal acceleration (`longitudinal_g`) is directly available
- No magnetometer needed — heading derived from GPS course + yaw rate integration
- Simple 5-state system is tractable to implement and tune

The two-pass algorithm (forward EKF + backward RTS smoother) uses future GPS measurements to improve past position estimates — this is causally optimal for post-processing.

### Realistic Accuracy at 25Hz Matched Rate

The most important finding from fusion research: **the 0.1m target is not achievable** with 25Hz matched-rate data. When GPS and IMU run at the same rate, there is no IMU-only propagation period between GPS updates.

| Approach | Lateral Position Accuracy | Notes |
|----------|--------------------------|-------|
| Raw GPS (NEO-M9N, open sky) | 0.5–1.5m CEP | In ideal conditions on track |
| Savitzky-Golay smoothing | 0.3–0.8m | Reduces white noise, preserves features |
| EKF (CTRV, 25Hz GPS+IMU) | 0.3–0.7m | Kinematic constraints help but limited |
| EKF + RTS smoother | 0.2–0.5m | 10–50% improvement over EKF alone |
| High-rate IMU (100+ Hz) + EKF + RTS | 0.1–0.3m | Requires proper 100+ Hz IMU |
| RTK-GPS alone | 0.01–0.05m | Very expensive, requires base station |

What EKF+RTS actually provides:
- Smoother GPS tracks — reduces jitter from ~0.5m to ~0.2-0.3m RMS noise
- Better heading estimation from yaw rate integration
- Kinematically consistent trajectory (EKF enforces car can't jump sideways)
- The **RTS smoother** uses future GPS samples to smooth past position estimates

What it cannot provide:
- True 0.1m position accuracy — requires RTK-GPS or much better IMU at higher rate
- Complete elimination of GPS position noise

**Detectable line delta comparison:**

| Method | Detectable Line Delta | Lap-to-Lap Accuracy |
|--------|-----------------------|---------------------|
| Raw GPS | ~1m | ~0.5m |
| + Savitzky-Golay | ~0.5m | ~0.3m |
| + EKF (CTRV) | ~0.4m | ~0.2m |
| + EKF + RTS | ~0.3m | ~0.15-0.2m |

### EKF vs Savitzky-Golay Comparison

| Property | Savitzky-Golay | EKF + RTS |
|----------|---------------|-----------|
| Implementation effort | Low (1 function call) | High (200+ lines, tuning) |
| Position accuracy | Moderate | Moderate-Good |
| Heading quality | Poor | Good |
| Handles GPS jumps | Partially | Better |
| Uses IMU data | No | Yes |
| Physically consistent trajectory | No | Yes |
| Parameterization | Window size, polyorder | Q, R matrices (6+ params) |
| Failure mode | Smooths real features | Diverges, systematic bias |
| Improvement over raw | 30–50% noise reduction | 40–65% noise reduction |

### Practical Challenges

**IMU frame alignment (critical):** The RaceBox Mini S IMU is mounted in an unknown orientation relative to vehicle axes. Use `lateral_g` and `longitudinal_g` from RaceChrono (already transformed to vehicle frame) rather than raw xyz channels.

**Gyro bias estimation:** Estimate from stationary periods (speed < 0.5 m/s in pit lane before session). Subtract from all readings.

**Heading initialization:** GPS heading is only reliable when moving. Initialize from first GPS reading with speed > 2 m/s with ±15° uncertainty in the P matrix.

**EKF tuning:** The filter can diverge if Q (process noise) and R (measurement noise) matrices are poorly set. Start with R = sensor variance from datasheet. Monitor innovations — should be zero-mean with variance matching R.

### Recommendation: Savitzky-Golay First, EKF Later

**Phase 1 (quick win, 1-2 hours):** Apply Savitzky-Golay to GPS in ENU frame. Window=21, polyorder=3 for 25Hz data (840ms window). This handles 80% of the noise benefit with minimal implementation risk.

**Phase 2+ (when needed):** CTRV-EKF + RTS smoother using `filterpy`. Add if visual comparison shows noticeable jitter that Savitzky-Golay doesn't fix, or when you need physically consistent trajectories for replay/visualization.

**Skip EKF+RTS if:** the goal is only visual inspection, IMU alignment is uncertain, or implementation complexity doesn't justify the marginal improvement.

**Recommended library:** `filterpy` (pip install filterpy) — most mature, has `batch_filter()` + `rts_smoother()` built in, well-documented.

---

## 4. Market Gap & Competitor Landscape

### The Gap: Nobody Does AI Line Coaching

| Product | Shows Lines? | Compares Lines? | AI Coaching on Lines? | Price |
|---------|-------------|----------------|----------------------|-------|
| VBOX Circuit Tools | Yes (GPS trace on track map) | Yes (overlay 2 laps) | **No** | $2000+ hardware |
| AiM Race Studio | Yes | Yes (visual overlay) | **No** | $1500+ hardware |
| Garmin Catalyst 2 | Yes (25Hz, True Track Positioning) | Yes (vs reference) | **No** (delta-T only) | $1199 |
| Harry's LapTimer | Yes (basic trace) | Yes (basic overlay) | **No** | $30 app |
| TrackAddict | Yes (basic trace) | Limited | **No** | $10 app |
| RaceBox app | Yes | Yes (2-lap overlay) | **No** | Free with hardware |
| Track Titan | No GPS lines | No | Yes (text, not line-specific) | $10/mo |
| Blayze | No GPS lines | No | Yes (human coaches, video) | $99/review |
| Fire Laps | Yes (visual) | Yes | AI analysis (limited) | Hardware + service |
| Laptica | Yes (visual) | Yes | Claims line analysis | $TBD |

Every product falls into one of two categories:
1. **Shows GPS traces visually** but provides zero coaching about what the lines mean
2. **Provides coaching** but doesn't analyze GPS line data at all

### Why the Gap Exists

1. **Historical focus on lap times**: The industry built around delta-T as the primary coaching tool
2. **Reference line problem**: Without a known-good reference, you can't say "2m too wide" — you can only show two traces. Cataclysm solves this by using the driver's own best lap or multi-lap average as reference
3. **Coaching knowledge gap**: Hardware companies (VBOX, AiM) aren't coaching companies. Coaching companies (Blayze) use human coaches, not algorithms
4. **AI maturity**: Until LLMs, converting numeric line analysis into natural-language coaching was extremely difficult

### Competitor Deep Dives

**Garmin Catalyst 2 ($1199, released Feb 2026):**
- 25Hz multi-GNSS positioning — "most precise racing line on the track"
- True Track Positioning: accelerometers + gyroscopes + image processing + multi-GNSS
- True Optimal Lap: composite of best sections from all laps driven
- Real-time audio coaching with speed and braking cues
- Built-in camera with video composite
- Does NOT generate text coaching about line errors — still no natural language analysis

**VBOX Circuit Tools ($2000+, up to 100Hz with RTK):**
- Best-in-class GPS trace visualization with 800+ surveyed tracks
- Side-by-side lap overlay with perfect position alignment
- Center Line Deviation analysis
- Zero coaching text generated from line data

**Track Titan (~$10/mo):**
- Software-only, works with any GPS logger
- AI-generated coaching reports — closest competitor in spirit
- Does NOT analyze GPS line data specifically
- Uses lap times and sector times for coaching, not spatial line positions

**Blayze ($99/review):**
- Human coaches review video footage, provide detailed per-corner coaching
- 24-48 hour turnaround — exactly what we want to automate
- Not scalable, not instant

**Fire Laps (Hardware + service):**
- Fire Link: 10Hz GPS + LTE, auto-uploads for AI analysis
- "Easy-to-understand instructions and recommended drive lines and speeds"
- SCCA partnership/coverage
- Not validated for language quality of line coaching; visual focus

### Cataclysm's Competitive Moat

- **Track Titan** would need to add GPS trace analysis (they don't have it)
- **Garmin/VBOX/AiM** would need to add AI text generation (outside their DNA)
- **Blayze** can't scale human coaches to instant feedback
- **No one** currently has: GPS line analysis + LLM coaching + instant turnaround + ~$0.04/report cost

---

## 5. How Line Coaching Is Done IRL

### Allen Berg Racing Schools — Corner Classification

**Type A Corners** (before straights): Exit speed is paramount
- Sacrifice entry speed for a wider, later apex
- "Slow in, fast out" — maximize time on throttle for the following straight
- Common error: early apex, which forces lifting or tight exit
- AI coaching implication: prioritize exit offset and apex fraction analysis

**Type B Corners** (after straights): Entry speed matters most
- Trail-braking deep into the corner, late turn-in
- Apex is earlier than Type A
- Common error: braking too early, leaving speed on the table

**Type C Corners** (linking corners): Compromise line
- Line must set up the next corner, not just optimize this one
- Requires thinking ahead — novices optimize each corner in isolation
- Common error: great exit from this corner but terrible entry to the next

**Application to AI coaching**: Classify each corner as A/B/C using `track_db.py` metadata (which corners precede straights). Adjust coaching advice based on corner type. Always analyze corner pairs and sequences — a driver's problem in corner N may originate in corner N-1.

### Blayze Coaching — 5 Reference Points

| Point | Fixed/Adjustable | Description |
|-------|-----------------|-------------|
| Exit apex | Fixed | Where you want the car at corner exit — determined by track geometry |
| Entry apex | Fixed | Where you want the car at corner entry — determined by track geometry |
| Slowest point | Fixed | Where the car reaches minimum speed — near the geometric apex |
| Turn-in point | **Adjustable** | Where you initiate steering input — adjustable by driver |
| Brake point | **Adjustable** | Where you begin braking — adjustable as driver improves |

The 3 fixed points define the ideal line. The 2 adjustable points are where drivers can improve. AI coaching should focus on the adjustable points: "Try braking 5m later" or "Turn in slightly earlier."

### Ross Bentley — Speed Secrets Methodology

- **The line is 80% of lap time improvement for club drivers** — not brake points, not car setup
- **"Unwind the steering"**: The ideal line maximizes corner radius, which maximizes speed
- **Reference points must be physical objects**: "The third tree on the left" not "30m before the corner" — drivers need visual anchors. Cataclysm already has a landmarks system in `track_db.py`.
- **Progressive learning**: Teach braking first, then turn-in, then apex, then exit — not all at once

### F1 Data Engineer Perspective

What professional data engineers look for in line data:
1. **Steering trace smoothness**: Smooth = efficient line; jagged = corrections/mistakes
2. **MIN speed location**: Where in the corner the driver reaches minimum speed
3. **Lateral acceleration traces**: How close to grip limit through the corner
4. **Line deviation lap-to-lap**: Consistency of path through each corner
5. **Brake/throttle overlap with steering**: Quality of trail braking technique

Priority for analysis: **EXIT (most time to gain) > ENTRY > MID-CORNER** (least time spent here).

### Delta-T as a Coaching Tool

- **Most powerful single metric** according to professional coaches and data engineers
- Shows exactly where time is gained/lost, not just the total
- Human coaches look for: sharp negative spikes (braking too early), gradual loss through a corner (wrong line), gain on straights (better exit from previous corner)
- Cataclysm already computes delta-T in the speed trace chart — need to link it to line analysis

### How Pros Use Video + Data

Professional coaching overlays:
1. Video from forward-facing camera (shows reference points, track position)
2. Speed trace
3. Throttle/brake trace
4. GPS track map with position dot

The coach narrates: "See here, you turned in about 2 car-widths too early, that's why you had to lift at the apex, and you lost 0.3s through the exit." **This is exactly what we want to automate.** We replace the video with GPS line data and have Claude narrate the same coaching.

### Skill-Level Adapted Coaching

| Level | Focus | Line Complexity | Language Style |
|-------|-------|----------------|----------------|
| Novice | Safety, basic line | Single ideal line per corner | "Aim for the orange cone at turn-in" |
| Intermediate | Consistency, brake points | Type A/B/C awareness | "Try a later apex to improve exit speed" |
| Advanced | Tenths of seconds | Multiple line options, trade-offs | "Your entry is optimal but compromises T6 setup" |
| Expert | Hundredths of seconds | Racing vs qualifying line | Detailed lateral offset analysis, entry/apex/exit patterns |

**Novice common errors to address:**
- Turning in too early (impatience / fear)
- Early apex (nervousness causes premature turn-in)
- Not using full track width on exit
- Looking immediately ahead instead of through the corner
- Braking in the corner instead of before turn-in

**Intermediate progression target:**
- Introduction to trail braking
- Late apex vs geometric apex for different corner types
- Corner-linking awareness: current corner affects next corner

---

## 6. AI/ML Approaches

### TUM Feed-Forward Neural Network

**Technical University of Munich (TUM)** published the most prominent ML approach:
- Trained on 2.7 million track segments with pre-computed optimal racing lines
- Mean absolute error: ±0.27m overall, ±0.11m at corner apex
- Prediction time: 33ms (9,000x faster than traditional optimal control methods)
- Track geometry encoded as "Normal lines" — curvature features along centerline
- Uses a sliding window approach so it generalizes across circuits of different lengths
- Source: arxiv 2102.02315

**Application to Cataclysm**: We don't need to predict the theoretically optimal line (which requires a full vehicle dynamics model). Instead, we compare the driver's line to their own best lap or multi-lap average. This is more practical and doesn't require vehicle parameters.

### Reinforcement Learning — Not Applicable

- Formula RL (DDPG), Gran Turismo Sophy (Sony): these require simulation environments
- Not applicable for post-hoc GPS analysis
- Gran Turismo Sophy beat human champions using RL — but entirely in simulation

### What's Actually Useful for Cataclysm

1. **Frenet frame decomposition**: Project GPS traces into (s, d) coordinates where s = distance along track, d = lateral offset. Standard in autonomous racing research.
2. **Multi-lap statistical analysis**: Mean, median, percentiles of lateral offset per corner. No ML needed.
3. **Anomaly detection**: Flag laps where lateral offset deviates significantly from the driver's norm — either errors or experiments.
4. **Pattern classification**: Decision tree or rule-based classification of line errors (early apex, wide entry, pinched exit) based on lateral offset at key points.

### TUMFTM Open-Source Tools

TU Munich's `trajectory_planning_helpers` library provides:
- `path_matching`: Align lap traces to reference using Frenet frame
- `calc_normal_vectors`: Compute perpendicular directions along track
- `calc_head_curv_an`: Analytical heading and curvature computation
- `racetrack-database`: 20+ tracks with centerlines and track widths

These are directly usable in our Python pipeline.

---

## 7. Algorithms & Implementation

### Pipeline Overview

```
RaceChrono CSV → Parser → Distance Resample (0.7m) → ENU Projection
    → GPS Smoothing (Savitzky-Golay)
    → Reference Centerline Construction (multi-lap median)
    → Lateral Offset Computation (KD-tree, signed)
    → Corner-Specific Line Analysis (entry/apex/exit)
    → Line Error Classification
    → AI Coaching Prompt Assembly → Claude API → Report
```

### Step 1: ENU Coordinate Projection

Convert GPS lat/lon to local East-North-Up (ENU) Cartesian coordinates. **Never compute geometry in lat/lon** — distances are distorted at non-equatorial latitudes.

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

Build a reference line from multiple laps using median (robust to outliers and off-track excursions).

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

### Step 5: CornerLineProfile Dataclass

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

Pre-compute on CSV upload, cache results. No perceptible delay for the user.

### Required Libraries

```
pymap3d>=3.0       # GPS to ENU conversion (new dependency)
scipy>=1.11        # Splines, KD-tree, Savitzky-Golay (already in project)
numpy>=1.24        # Core numerics (already in project)
```

Optional for advanced features:
```
filterpy>=1.4.5                   # For EKF+RTS smoother (Phase 2+)
trajectory-planning-helpers       # TUMFTM path matching, curvature, normal vectors
```

---

## 8. Visualization & UX Design

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
- Uses Canvas 2D rendering (draw segments individually with color)
- Identical to FastF1/F1 TV visualization that fans already understand
- Show single lap or overlay multiple laps

**2. Lap Overlay Comparison**
- Two laps drawn on same track map with different colors
- Thicker line = currently selected/focused lap
- Semi-transparent lines to see overlap vs divergence
- Tooltip on hover: "Lap 3: 87.2 km/h | Lap 7: 91.5 km/h | Delta: +4.3 km/h"

**3. Coaching Annotations on Track Map (Innovation — Nobody Has This)**
- Automated version of what professional coaches draw on video
- Arrow from actual apex to reference apex: "Apex 2.3m too early"
- Bracket showing available track width not used: "1.2m of track unused at entry"
- Color-coded corner overlays: green (good line), yellow (minor error), red (major error)
- Human coaches draw on video frames; we draw on GPS maps. This is the killer feature nobody has.

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

**Novice**: Track map with speed coloring + 1-2 biggest coaching tips per corner. Simple language, physical landmark references.

**Intermediate**: Add lateral offset plot, corner detail mini-maps, entry/apex/exit comparison. Technical terminology OK.

**Advanced**: Full corner consistency analysis, multi-lap overlay, statistical analysis, line-by-line comparison tables.

### Technical Implementation

- **Track map**: Canvas 2D (`<canvas>`) for performance with thousands of GPS points
- **Charts**: D3.js SVG (already used in project for speed traces)
- **Hover sync**: `requestAnimationFrame` for smooth updates, shared state via React context
- **Mobile**: Touch-hold to activate crosshair, swipe between corners
- **Responsive**: Track map scales to container width; charts stack vertically on mobile

---

## 9. AI Coaching Integration

### Structured Prompt Template

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

### Skill-Level Prompt Prefixes

**Novice:**
```
You are coaching a novice track day driver. Focus on SAFETY and BASIC LINE.
Use simple language. Reference physical landmarks they can see from the car.
One key tip per corner maximum. Don't overwhelm with data.
Explain WHY the line matters (safety, tire wear, speed).
```

**Intermediate:**
```
You are coaching an intermediate driver working on consistency.
Discuss entry/apex/exit separately. Use proper racing terminology.
Compare their typical line to their best lap's line.
Focus on the 2-3 corners where they lose the most time.
Introduce concepts like trail-braking depth and corner type (A/B/C).
```

**Advanced:**
```
You are a professional data engineer coaching an advanced driver.
Provide detailed lateral offset analysis and corner-by-corner comparison.
Discuss line options and trade-offs (this corner vs next corner setup).
Reference consistency metrics and highlight experiments vs errors.
Suggest specific, measurable improvements with expected time gains.
```

### Integration with Existing coaching.py

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

### Example AI Output

**Novice example:**
> **Turn 5 — The Big Right-Hander**
> You're turning in too early here. See the "200" braking board on your left? Try waiting until you pass it before turning the wheel. Right now, your car is hitting the inside of the corner about 2 meters too soon, which means you run out of room on exit and have to slow down. A later turn-in will feel scary at first, but it'll let you carry more speed onto the back straight.

**Advanced example:**
> **T5 Line Analysis** — Your apex is consistently early (fraction 0.38 vs optimal 0.55-0.65 for this Type A corner). Lateral offset at apex: -1.8m from reference. This forces a 0.9m tighter exit than your best lap (L7), costing an estimated 0.3-0.5s on the following straight due to reduced exit speed (ΔV_exit = -4.2 km/h). Your entry is appropriate (within 0.3m of reference), suggesting the issue is turn-in timing, not entry speed. Consistency: apex SD = 1.2m across 18 laps — the highest variability of any corner, indicating this is a focus area. Recommendation: Delay turn-in by approximately 8-10m (use the repair patch on the right side of the track as reference). This should move your apex fraction to ~0.55 and open the exit by 1-2m.

---

## 10. Consistency Analysis

### Lap Time Consistency Benchmarks

| Tier | Lap Time SD | Description |
|------|------------|-------------|
| Expert | < 0.2s | Race-ready consistency, minimal variation |
| Consistent | 0.2 - 0.5s | Solid club racer, predictable |
| Developing | 0.5 - 2.0s | Improving but variable, common at intermediate level |
| Novice | > 2.0s | Significant variation, still learning the track |

Source: Professional driver coaching data. Expert SD ~0.2-0.27s vs novice ~2.55-3.26s (approximately 10x difference).

### Per-Corner Consistency Metrics

| Metric | Expert | Developing | Novice |
|--------|--------|-----------|--------|
| Apex speed CV | < 2% | 2-5% | > 5% |
| Entry speed CV | < 3% | 3-6% | > 6% |
| Lateral offset SD at apex | < 0.3m | 0.3-1.0m | > 1.0m |
| Brake point SD | < 2m | 2-8m | > 8m |

### Exploration vs Inconsistency Detection

High variation isn't always bad — the driver might be experimenting.

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

### Multi-Session Progress Dataclass

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

## 11. Codebase Integration Points

### Existing Infrastructure to Leverage

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

### What's Missing (To Build)

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
| EKF fusion (Phase 2+) | `cataclysm/fusion.py` | CTRV-EKF + RTS smoother |

### GPS Quality Gate

The existing `GPSQualityReport` in `gps_quality.py` already grades sessions A-F. Line analysis should only activate for grade A or B sessions. Grade C and below: show warning, still show basic visualizations but suppress precise coaching.

---

## 12. Implementation Roadmap

### Phase 1: Foundation — Core Pipeline

**New files:**
- `cataclysm/gps_line.py`: ENU projection, Savitzky-Golay smoothing, reference centerline, lateral offset computation
- `cataclysm/corner_line.py`: CornerLineProfile dataclass, corner-specific analysis, error classification

**Edits:**
- `cataclysm/coaching.py`: Add line analysis section to coaching prompt with skill-level prefixes
- `requirements.txt`: Add `pymap3d>=3.0`

**Tests:**
- `tests/test_gps_line.py`: Synthetic GPS data, verify ENU projection, lateral offset sign, edge cases
- `tests/test_corner_line.py`: Each error classification type

**Deliverable**: Claude generates natural-language coaching about driving lines. No visual changes yet. This is the "holy shit" moment.

### Phase 2: Visualization

**Frontend work:**
- Speed-colored track map (Canvas 2D)
- Two-lap GPS overlay on track map
- Lateral offset chart (D3, shared distance axis with speed trace)
- Bidirectional hover linking: track map ↔ speed trace ↔ lateral offset chart
- Corner detail mini-maps (zoomed corner view with reference vs actual)

**Backend work:**
- Expose line analysis data via API (lateral offsets per lap, corner profiles)

### Phase 3: Advanced Coaching

- Coaching annotations on track map (arrows from actual apex to reference, color-coded corners)
- Consistency analysis with per-corner tier classification
- Exploration vs inconsistency detection
- Multi-session progress tracking for line improvement
- Skill-level-adapted prompts with corner type (A/B/C) awareness

### Phase 4: Innovation Features

- Corner-specific coaching cards with mini-map + metrics
- "Coach's drawing" mode: AI generates SVG annotations on track map
- Line comparison against different sessions (with GPS alignment)
- Track boundary estimation from lateral offset distribution
- GPS+IMU sensor fusion: `cataclysm/fusion.py` with CTRV-EKF + RTS smoother using `filterpy`

### Priority Reasoning

Phase 1 gives the differentiating capability: automated text coaching about driving lines. No competitor does this. Phases 2-4 add depth, visualization, and lasting competitive advantages.

---

## 13. Sources

**Academic:**
- TUM Feed-Forward NN for racing lines: [arxiv 2102.02315](https://arxiv.org/abs/2102.02315)
- ESKF-RTS paper (2023): [PMC10099052](https://pmc.ncbi.nlm.nih.gov/articles/PMC10099052/)
- UKF GPS-IMU accuracy analysis: [arxiv 2405.08119](https://arxiv.org/html/2405.08119v1)

**Open-Source Tools:**
- TUMFTM trajectory_planning_helpers: [github.com/TUMFTM/trajectory_planning_helpers](https://github.com/TUMFTM/trajectory_planning_helpers)
- TUMFTM racetrack-database: [github.com/TUMFTM/racetrack-database](https://github.com/TUMFTM/racetrack-database)
- balzer82/Kalman — CTRV EKF Python: [github.com/balzer82/Kalman](https://github.com/balzer82/Kalman)
- filterpy documentation: [filterpy.readthedocs.io](https://filterpy.readthedocs.io/en/latest/kalman/KalmanFilter.html)
- pyins — Python INS package: [pyins.readthedocs.io](https://pyins.readthedocs.io/en/latest/)
- Kalman and Bayesian Filters in Python (free book): [github.com/rlabbe](https://github.com/rlabbe/Kalman-and-Bayesian-Filters-in-Python)

**Hardware Specifications:**
- RaceBox Mini S specifications: [racebox.pro](https://www.racebox.pro/)
- Garmin Catalyst 2 press release: [garmin.com/newsroom](https://www.garmin.com/en-US/newsroom/press-release/automotive/optimize-time-on-the-track-with-the-cutting-edge-garmin-catalyst-2/)
- VBOX Circuit Tools: [vboxmotorsport.co.uk](https://www.vboxmotorsport.co.uk/index.php/en/circuit-tools)

**Coaching Methodology:**
- Allen Berg Racing Schools corner classification methodology
- Blayze coaching 5 reference points system: [blayze.io](https://blayze.io/)
- Ross Bentley "Speed Secrets" methodology
- Paradigm Shift Racing: [paradigmshiftracing.com](https://www.paradigmshiftracing.com/racing-basics/racing-basics-1-the-basic-racing-line)
- Beyond Seat Time: [beyondseattime.com](https://www.beyondseattime.com/)
- Sim Racing Telemetry docs: [docs.simracingtelemetry.com](https://docs.simracingtelemetry.com/kb/how-to-analyze-racing-lines)

**Motorsport IMU/INS Practical Guides:**
- Obsidian Motorsport — GPS/IMU/INS for racing: [obsidianeng.com](https://obsidianeng.com/2020/12/23/gps-imu-ins-what-on-earth-even-is-that/)
- Obsidian Motorsport — Coordinate frames: [obsidianeng.com](https://obsidianeng.com/2022/11/30/coordinate-frames-and-you/)
- SBG Systems RTS smoother glossary: [sbg-systems.com](https://www.sbg-systems.com/glossary/rts-rauch-tung-striebel/)

**Competitors:**
- Track Titan: [tracktitan.io](https://www.tracktitan.io/)
- Coach Dave Delta: [coachdaveacademy.com/delta](https://coachdaveacademy.com/delta/)
- trophi.ai: [trophi.ai](https://www.trophi.ai/)
- Fire Laps: [firelaps.com](https://firelaps.com/)
- Laptica: [staging.laplogik.com](https://staging.laplogik.com/)
- RaceData AI: [racedata.ai](https://www.racedata.ai/)

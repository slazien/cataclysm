# Data Pipeline

The core engine converts time-domain GPS telemetry from RaceChrono into distance-domain data, detects corners, and generates AI coaching insights.

## Pipeline Overview

```
RaceChrono CSV v3 → parser.py → engine.py → corners.py → gains.py → coaching.py → CoachingReport
                                    ↓              ↓
                              resampled laps   corner KPIs
                              (0.7m intervals)
```

## Stage 1: CSV Parsing (`parser.py`)

Parses RaceChrono CSV v3 exports into a normalized telemetry DataFrame.

**Input**: Raw CSV file (string path or file-like object)

**RaceChrono CSV v3 Format**:
- 8-line metadata header (track name, date, version)
- 3 header rows: column names, units, sources
- Positional column indexing (columns have duplicate names)

**Quality Filters**:
- GPS accuracy must be < 2.0m (`MAX_ACCURACY_M`)
- Satellite count must be >= 6 (`MIN_SATELLITES`)
- Rows failing these filters are dropped

**Output**: `ParsedSession(metadata: SessionMetadata, data: pd.DataFrame)`

**Key columns in DataFrame**:
| Column | Unit | Description |
|--------|------|-------------|
| `timestamp` | seconds | Elapsed time |
| `lap_number` | int | Lap identifier |
| `distance_m` | meters | Cumulative distance |
| `speed_mps` | m/s | Ground speed |
| `heading_deg` | degrees | Compass heading |
| `lat`, `lon` | degrees | GPS coordinates |
| `lateral_g` | g | Lateral acceleration |
| `longitudinal_g` | g | Longitudinal acceleration |
| `accuracy_m` | meters | GPS accuracy estimate |

```python
from cataclysm.parser import parse_racechrono_csv

session = parse_racechrono_csv("session.csv")
print(session.metadata.track_name)  # "Barber Motorsports Park"
print(session.data.shape)           # (45000, 15)
```

## Stage 2: Distance-Domain Resampling (`engine.py`)

Splits parsed data into laps and resamples each to a uniform 0.7m distance grid.

**Why distance domain?** Time-domain data has variable sampling rate (GPS jitter, acceleration). Resampling to fixed distance intervals (0.7m = 25Hz at typical track speeds) makes:
- Corner detection deterministic (same distance = same track position)
- Lap comparison straightforward (align by distance, not time)
- Speed profiles directly comparable

**Process**:
1. Split DataFrame by `lap_number` transitions
2. Compute cumulative distance for each lap
3. Filter short laps (< 80% of median distance)
4. Detect anomalous laps via IQR + hard ratio (> 1.5x median time)
5. Resample each clean lap to 0.7m intervals via linear interpolation

**Constants**:
| Constant | Value | Purpose |
|----------|-------|---------|
| `RESAMPLE_STEP_M` | 0.7 | Distance between resampled points |
| `MIN_LAP_FRACTION` | 0.80 | Discard laps shorter than 80% of median |
| `MAX_LAP_TIME_RATIO` | 1.5 | Flag laps > 1.5x median time as anomalous |

**Output**: `ProcessedSession`
- `lap_summaries`: list of `LapSummary` (lap_number, lap_time_s, lap_distance_m, max_speed_mps, tags)
- `resampled_laps`: `dict[int, pd.DataFrame]` — lap_number to resampled DataFrame
- `best_lap`: int — fastest clean lap number

## Stage 3: Corner Detection (`corners.py`)

Detects corners from heading rate (change in heading per meter of distance).

**Algorithm**:
1. Compute heading rate: `d(heading) / d(distance)` at each point
2. Smooth over 20m window to reduce GPS noise
3. Find contiguous regions where |heading rate| > 1.0 deg/m
4. Merge regions within 30m of each other
5. Discard segments shorter than 15m
6. Extract KPIs for each corner

**Detection Constants**:
| Constant | Value | Purpose |
|----------|-------|---------|
| `HEADING_RATE_THRESHOLD` | 1.0 deg/m | Minimum turning rate for corner |
| `SMOOTHING_WINDOW_M` | 20.0m | Heading rate smoothing window |
| `MIN_CORNER_LENGTH_M` | 15.0m | Discard very short segments |
| `MERGE_GAP_M` | 30.0m | Merge corners within this gap |

**KPI Extraction** (per corner):

| KPI | How Computed | Search Range |
|-----|-------------|--------------|
| **Apex** | Point of minimum speed within corner | Entry to exit |
| **Apex type** | Early/mid/late based on position within corner | Fractional position |
| **Min speed** | Minimum speed_mps in corner | Entry to exit |
| **Brake point** | First point where longitudinal_g < -0.1g before corner | 150m before entry |
| **Peak brake g** | Maximum deceleration before apex | Brake point to 40% into corner |
| **Throttle commit** | Point where longitudinal_g > 0.1g sustained for 10m | Apex to exit |

**Corner dataclass** includes optional GPS coordinates, curvature, direction (left/right), elevation trends, and coaching notes when track database info is available.

## Stage 4: Lap Comparison (`delta.py`)

Computes the time difference between two resampled laps at each distance point.

**Algorithm**:
1. Align two laps by distance (both already on 0.7m grid)
2. At each distance point, compute cumulative time difference
3. Positive delta = comparison lap is slower than reference
4. Optionally compute per-corner deltas using corner boundaries

**Output**: `DeltaResult(distance_m, delta_time_s, corner_deltas, total_delta_s)`

## Stage 5: Advanced Analysis

### Time-Gain Estimation (`gains.py`)

Three-tier system for estimating potential lap time improvement:

**Tier 1 — Consistency Gain**: How much faster if every segment matched your best?
- Build segments from corners: T1, S1-2, T2, S2-3, T3, ...
- For each segment, compare average time to best time across all clean laps
- Sum of differences = total consistency gain

**Tier 2 — Composite Gain**: Ideal lap from best segments combined.
- Take the best time for each segment across all laps
- Sum = composite lap time
- Gap to best actual lap = composite gain

**Tier 3 — Theoretical Best**: Micro-sector analysis.
- Divide track into many small sectors (e.g., 50)
- Best time for each micro-sector across all laps
- Sum = theoretical best lap time

### Corner Analysis (`corner_analysis.py`)

Pre-computed per-corner statistics for coaching prompts:
- Statistical summaries (best, mean, std, range) for min speed, brake point, peak g, throttle commit
- Correlations between KPIs (e.g., later braking → lower min speed)
- Recommendations with target values and estimated time gain
- Landmark references for brake points (e.g., "brake at the 200m board")

### Consistency Metrics (`consistency.py`)

Session-wide consistency scoring:
- **Lap consistency**: Std dev, spread, consecutive deltas, choppiness (0-100 score)
- **Corner consistency**: Per-corner min speed std, brake point std, throttle commit std
- **Track position consistency**: Speed std/mean/median at each distance point across all laps

### Physics-Optimal Profile (`velocity_profile.py`)

Forward-backward velocity solver (Kapania et al. 2016):
1. Compute track curvature from GPS via spline fitting (`curvature.py`)
2. Calculate maximum cornering speed at each point: `v_max = sqrt(mu * g / curvature)`
3. Forward pass: accelerate from each point, limited by friction circle
4. Backward pass: decelerate into each corner, limited by braking capacity
5. Take minimum of forward, backward, and cornering limits
6. Result: physically optimal speed at every point on track

**Vehicle parameters** derived from equipment profile (tire compound, tread wear → friction coefficient).

## Stage 6: AI Coaching (`coaching.py`)

Assembles rich context from all analysis modules and sends to Claude API.

**Context assembly**:
1. Lap summaries (times, speeds, tags)
2. Corner KPIs for all laps (not just best)
3. Gain estimates (consistency, composite, theoretical)
4. Optimal comparison (speed gaps, brake gaps per corner)
5. Landmark references (visual brake markers)
6. Pre-computed corner statistics and correlations
7. Track-specific coaching notes from track database
8. Driving physics reference (friction circle, weight transfer, etc.)

**Model**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
- Chosen after 7-model comparison: 90-95% of Sonnet quality at 1/3 price (~$0.04/report)
- Max retries: 4, timeout: 120s

**Output**: `CoachingReport`
- `summary`: Natural language overview
- `priority_corners`: Top improvement opportunities with estimated time cost
- `corner_grades`: Per-corner grades (braking, trail braking, min speed, throttle)
- `patterns`: Identified driving patterns (e.g., "consistently late braking into T5")
- `drills`: Actionable practice exercises

**Validation**: Reports are validated against schema (grades must be valid, corners must exist). Failed validation is flagged but report is still returned.

## Track Database (`track_db.py`)

Official corner positions for known circuits, stored as fraction of lap distance:

| Track | Corners | Length | Elevation |
|-------|---------|--------|-----------|
| Barber Motorsports Park | 16 | 3,662m | 60m range |
| Atlanta Motorsports Park | 12 | 3,220m | — |

Each corner includes:
- Official number and name
- Apex position (fraction of lap distance)
- GPS coordinates
- Character (flat/lift/brake), direction (left/right)
- Corner type (hairpin/sweeper/chicane/kink)
- Elevation trend, camber, blind flag
- Coaching notes

**Track auto-detection** (`track_match.py`):
- Compute session centroid (mean lat/lon)
- Compare to known track centers via haversine distance
- Confidence decays with distance, threshold 5km
- Fallback: name matching if GPS detection fails

## Supporting Modules

| Module | Purpose |
|--------|---------|
| `mini_sectors.py` | Equal-distance sector breakdown (default 20 sectors) |
| `sectors.py` | Corner-based sector analysis with PB tracking |
| `degradation.py` | Tire/brake degradation detection across stint |
| `grip.py` | Grip analysis from g-force data |
| `gps_quality.py` | GPS accuracy assessment |
| `elevation.py` | Elevation profile extraction |
| `lap_tags.py` | Auto-tagging (outlap, cooldown, pit stop, etc.) |
| `landmarks.py` | Visual reference system (brake boards, structures) |
| `equipment.py` | Tire/brake profiles → vehicle physics parameters |
| `tire_db.py` | Curated tire database with friction coefficients |
| `trends.py` | Session-over-session trend analysis |
| `driving_physics.py` | Motorsport physics reference for coaching prompts |
| `topic_guardrail.py` | Keeps AI coaching on motorsport topics |
| `coaching_validator.py` | Validates coaching report schema |

# Cataclysm: Implementation Plan

> "Like Garmin Catalyst but cheaper and better"

AI-powered motorsport telemetry analysis and coaching platform for HPDE and time attack drivers, using RaceBox Mini 25Hz GPS data.

---

## Requirements Summary

| Requirement | Decision |
|---|---|
| Data sources | RaceBox CSV + RaceChrono CSV (both), eventually direct BT from RaceBox Mini |
| GPS frequency | 25Hz (RaceBox Mini) |
| Distance resampling | 0.7m (native 25Hz resolution match) |
| App type | Web app (FastAPI + React/Next.js) |
| Charts | D3.js (interactive) |
| AI engine | Claude API (Anthropic) |
| AI coaching style | Trophi.ai-inspired: corner-by-corner scoring, prioritized feedback, conversational |
| Voice | Voice-in, voice-out (live coaching mode) |
| Session memory | Full history — AI references past sessions for trend coaching |
| Track definition | Track database + auto-detect from GPS crossover |
| Corner detection | Auto-detect + manual override, saved per track |
| Database | PostgreSQL |
| Auth | Single user now, structured for multi-user later |
| Deployment | Local first (docker-compose) |
| Vehicle profile | Modified street car (~1.0-1.3g lateral, ~120-150mph range) |
| Racing type | HPDE / track days + time attack / club racing |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    React / Next.js Frontend              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │ Dashboard │ │ Lap View │ │ Compare  │ │ AI Coach   │ │
│  │          │ │ (D3.js)  │ │ (D3.js)  │ │ Chat+Voice │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
└─────────────┬───────────────────────────┬───────────────┘
              │ REST + WebSocket          │
┌─────────────▼───────────────────────────▼───────────────┐
│                   FastAPI Backend                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │ Ingestion    │ │ Analysis     │ │ AI Coaching      │ │
│  │ Pipeline     │ │ Engine       │ │ Service          │ │
│  │              │ │              │ │ (Claude API)     │ │
│  │ • CSV parse  │ │ • Distance   │ │ • Corner coach   │ │
│  │ • Format     │ │   domain     │ │ • Session report │ │
│  │   detect     │ │ • Delta-T    │ │ • Trend analysis │ │
│  │ • Validate   │ │ • Corner KPI │ │ • Voice I/O      │ │
│  └──────┬───────┘ └──────┬───────┘ └────────┬─────────┘ │
│         │                │                   │           │
│  ┌──────▼────────────────▼───────────────────▼─────────┐ │
│  │              PostgreSQL Database                     │ │
│  │  tracks | sessions | laps | corners | coaching_log  │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 1: Core Distance-Domain Engine (MVP)

The mathematical foundation. Everything else depends on this being correct.

### 1.1 Project Scaffolding

- **Backend**: FastAPI project with Poetry/uv for dependency management
- **Frontend**: Next.js 14+ with TypeScript, D3.js
- **Database**: PostgreSQL with SQLAlchemy ORM + Alembic migrations
- **Docker**: `docker-compose.yml` with `api`, `web`, `db` services
- **Monorepo structure**:
  ```
  cataclysm/
  ├── backend/
  │   ├── app/
  │   │   ├── api/            # FastAPI route handlers
  │   │   ├── core/           # Config, database, dependencies
  │   │   ├── models/         # SQLAlchemy ORM models
  │   │   ├── schemas/        # Pydantic request/response schemas
  │   │   ├── services/       # Business logic
  │   │   │   ├── ingestion/  # CSV parsing, format detection
  │   │   │   ├── analysis/   # Distance-domain engine
  │   │   │   ├── coaching/   # Claude AI integration
  │   │   │   └── tracks/     # Track DB, auto-detect
  │   │   └── main.py
  │   ├── tests/
  │   ├── alembic/
  │   └── pyproject.toml
  ├── frontend/
  │   ├── src/
  │   │   ├── app/            # Next.js app router pages
  │   │   ├── components/     # React components
  │   │   │   ├── charts/     # D3.js chart components
  │   │   │   ├── coaching/   # AI chat interface
  │   │   │   └── layout/     # Shell, nav, sidebar
  │   │   ├── lib/            # API client, utilities
  │   │   └── types/          # TypeScript types
  │   └── package.json
  ├── docker-compose.yml
  └── PLAN.md
  ```

### 1.2 Data Ingestion Pipeline

**Goal**: Accept both RaceBox and RaceChrono CSV formats, normalize to a common internal representation.

#### RaceChrono CSV v3 Format (VERIFIED from real export)

**Metadata header** (8 lines before data):
```
This file is created using RaceChrono v9.1.3 ( http://racechrono.com/ ).
Format,3
Session title,"Barber Motorsports Park"
Session type,Lap timing
Track name,"Barber Motorsports Park"
Driver name,
Created,21/02/2026,22:12
Note,
```

**Three header rows** (column names, units, data sources):
```
timestamp,fragment_id,lap_number,elapsed_time,distance_traveled,accuracy,altitude,bearing,device_battery_level,device_update_rate,fix_type,latitude,longitude,satellites,speed,combined_acc,device_update_rate,lateral_acc,lean_angle,longitudinal_acc,speed,device_update_rate,x_acc,y_acc,z_acc,device_update_rate,x_rate_of_rotation,y_rate_of_rotation,z_rate_of_rotation
unix time,,,s,m,m,m,deg,%,Hz,,deg,deg,sats,m/s,G,Hz,G,deg,G,m/s,Hz,G,G,G,Hz,deg/s,deg/s,deg/s
,,,,,100: gps,100: gps,100: gps,100: gps,100: gps,100: gps,100: gps,100: gps,100: gps,100: gps,calc,calc,calc,calc,calc,calc,101: acc,101: acc,101: acc,101: acc,102: gyro,102: gyro,102: gyro,102: gyro
```

**29 columns by position** (IMPORTANT: column names are duplicated — must parse by position):

| Pos | Column | Unit | Source | Description |
|-----|--------|------|--------|-------------|
| 0 | `timestamp` | unix time | — | Unix epoch with centisecond precision |
| 1 | `fragment_id` | — | — | Session fragment index |
| 2 | `lap_number` | — | — | Lap number (empty before first S/F crossing) |
| 3 | `elapsed_time` | s | — | Seconds from session start |
| 4 | `distance_traveled` | m | — | **Cumulative distance (RaceChrono pre-computes!)** |
| 5 | `accuracy` | m | gps | GPS accuracy (~0.9m typical) |
| 6 | `altitude` | m | gps | Altitude MSL |
| 7 | `bearing` | deg | gps | Heading / bearing |
| 8 | `device_battery_level` | % | gps | RaceBox battery |
| 9 | `device_update_rate` | Hz | gps | 25Hz for RaceBox Mini |
| 10 | `fix_type` | — | gps | 3 = 3D fix |
| 11 | `latitude` | deg | gps | Decimal degrees, 7 decimal places |
| 12 | `longitude` | deg | gps | Decimal degrees, 7 decimal places |
| 13 | `satellites` | sats | gps | Satellite count |
| 14 | `speed` | m/s | gps | GPS-derived speed |
| 15 | `combined_acc` | G | calc | Combined acceleration magnitude |
| 16 | `device_update_rate` | Hz | calc | Calc channel rate (20Hz) |
| 17 | `lateral_acc` | G | calc | Lateral G (GPS-derived) |
| 18 | `lean_angle` | deg | calc | 0 for cars |
| 19 | `longitudinal_acc` | G | calc | Longitudinal G (GPS-derived) |
| 20 | `speed` | m/s | calc | Calculated speed (duplicate!) |
| 21 | `device_update_rate` | Hz | acc | Accelerometer rate (25Hz) |
| 22 | `x_acc` | G | acc | Raw IMU accelerometer X |
| 23 | `y_acc` | G | acc | Raw IMU accelerometer Y |
| 24 | `z_acc` | G | acc | Raw IMU accelerometer Z (gravity ~0.97G) |
| 25 | `device_update_rate` | Hz | gyro | Gyroscope rate (25Hz) |
| 26 | `x_rate_of_rotation` | deg/s | gyro | Roll rate |
| 27 | `y_rate_of_rotation` | deg/s | gyro | Pitch rate |
| 28 | `z_rate_of_rotation` | deg/s | gyro | Yaw rate |

**Key observations from real data**:
- `distance_traveled` is pre-computed by RaceChrono — use as primary, validate with Haversine
- GPS accuracy ~0.9m (sub-meter!) — excellent for distance calculations
- Variable timestamp intervals (~10-40ms) because 25Hz GPS + 25Hz IMU are interleaved → ~50Hz effective
- `lap_number` column handles lap splitting when track is defined in RaceChrono
- Raw IMU data (x/y/z_acc, x/y/z_rate_of_rotation) available alongside GPS-derived G-forces
- `z_acc` reads ~0.97G at rest (gravity) — must subtract 1.0G for vertical accel analysis

#### RaceBox Direct CSV Format (Telemetry Overlay preset)
```
utc (ms),lat (deg),lon (deg),alt (m),speed (m/s),heading (deg),pitch angle (deg),bank (deg),accel x (m/s²),accel y (m/s²),accel z (m/s²),gyro x (deg/s),gyro y (deg/s),gyro z (deg/s)
```

**Key differences to handle**:
- RaceBox: no `distance_traveled` column — must compute via Haversine
- RaceBox: no `lap_number` column — must auto-detect laps via S/F line crossing
- RaceBox: acceleration in m/s² (divide by 9.81 for G)
- RaceBox: single timestamp format (unix ms), no elapsed_time
- RaceChrono: duplicate column names — parser must use positional indexing
- RaceChrono: metadata header (8 lines) + 3 header rows before data

**Implementation**:
1. **Format detector**: Check for "RaceChrono" in first line or "Format,3" in second line
2. **Positional parser for RaceChrono v3**: Parse by column position (not name) due to duplicates
3. **Normalize to `TelemetryFrame`**:
   ```python
   @dataclass
   class TelemetryFrame:
       timestamp: float         # unix epoch seconds
       elapsed_time: float      # seconds from session start
       lat: float               # decimal degrees
       lon: float               # decimal degrees
       speed_mps: float         # meters per second
       heading_deg: float       # degrees from north
       altitude_m: float | None
       accuracy_m: float | None # GPS accuracy
       distance_m: float | None # cumulative distance (if available from source)
       lap_number: int | None   # lap number (if available from source)
       lat_g: float | None      # lateral G (calc or derived)
       lon_g: float | None      # longitudinal G (calc or derived)
       x_acc_g: float | None    # raw IMU X
       y_acc_g: float | None    # raw IMU Y
       z_acc_g: float | None    # raw IMU Z
       yaw_rate: float | None   # gyro Z (deg/s) — most useful for corner detection
       satellites: int | None
   ```
4. **Validation**: Reject frames with accuracy > 2.0m or satellite count < 6
5. **Smoothing**: Savitzky-Golay filter on speed and position (window=7 at 25Hz = 280ms)

### 1.3 Distance Integration (The RaceChrono Math)

**Goal**: Convert time-domain GPS data to distance-domain, the foundation of all analysis.

**For RaceChrono CSV v3**: The `distance_traveled` column is pre-computed. Use it as the primary distance source. Validate by cross-checking against our own Haversine calculation (should agree within <1%).

**For RaceBox CSV (no distance column)**: Compute cumulative distance from GPS coordinates.

**Step 1: Point-to-Point Distance** (used for RaceBox CSVs and for validation)
```python
def flat_distance(lat1, lon1, lat2, lon2) -> float:
    """Fast local flat-earth distance. Accurate within ~0.1% for <10km."""
    R = 6371000
    avg_lat = radians((lat1 + lat2) / 2)
    dx = R * radians(lon2 - lon1) * cos(avg_lat)
    dy = R * radians(lat2 - lat1)
    return sqrt(dx**2 + dy**2)
```

**Step 2: Cumulative Distance Column**
```python
# For RaceChrono: use pre-computed distance
if source == 'racechrono':
    distances = frames['distance_traveled'].values  # already cumulative
else:
    # For RaceBox: compute from GPS
    distances = [0.0]
    for i in range(1, len(frames)):
        d = flat_distance(frames[i-1].lat, frames[i-1].lon,
                          frames[i].lat, frames[i].lon)
        distances.append(distances[-1] + d)
```

**Step 3: 0.7m Distance-Domain Resampling**

This is the critical step that aligns all laps for comparison.

```python
from scipy.interpolate import interp1d

RESAMPLE_STEP = 0.7  # meters, matching 25Hz native resolution

# Create interpolation functions for each channel
dist = np.array([f.cumulative_distance_m for f in frames])
time_interp = interp1d(dist, timestamps, kind='linear', fill_value='extrapolate')
speed_interp = interp1d(dist, speeds, kind='linear', fill_value='extrapolate')
lat_interp = interp1d(dist, lats, kind='linear', fill_value='extrapolate')
lon_interp = interp1d(dist, lons, kind='linear', fill_value='extrapolate')
# ... same for heading, G-forces, etc.

# Generate uniform distance grid
total_distance = dist[-1]
uniform_dist = np.arange(0, total_distance, RESAMPLE_STEP)

# Resample all channels
resampled_time = time_interp(uniform_dist)
resampled_speed = speed_interp(uniform_dist)
# ... etc.
```

**Output**: A `ResampledLap` object where every row is exactly 0.7m apart. A 3.2km lap = ~4,571 rows. Row N is always at `N * 0.7` meters from the start/finish line.

### 1.4 Track Auto-Detection & Lap Splitting

**Goal**: Automatically identify which track the data is from and split continuous GPS data into individual laps.

**Track Database Schema**:
```sql
CREATE TABLE tracks (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,               -- "Watkins Glen International"
    config TEXT,                       -- "Full Course" / "Short Course"
    country TEXT,
    state TEXT,
    start_finish_lat DOUBLE PRECISION,
    start_finish_lon DOUBLE PRECISION,
    start_finish_heading DOUBLE PRECISION, -- direction of crossing
    track_length_m DOUBLE PRECISION,
    corners JSONB,                     -- auto-detected or manually defined
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Auto-detection algorithm**:
1. Take the first GPS coordinate of the session
2. Query the track database for any track within 2km radius
3. If found, use that track's start/finish line
4. If not found, run the self-crossing algorithm:
   - Buffer the GPS path into a LineString
   - Find where the path crosses itself (this is the start/finish)
   - Store as a new track entry for future sessions

**Lap splitting**:
1. Define the start/finish line as a 20m-wide gate perpendicular to the heading
2. Walk through the GPS data, detect each crossing of the gate
3. Split the continuous data into individual laps
4. Discard incomplete laps (< 80% of median lap distance) — pit laps, in/out laps

### 1.5 Delta-T Calculation

**Goal**: For any two laps, compute the cumulative time delta at every distance point.

```python
def compute_delta_t(reference_lap: ResampledLap, comparison_lap: ResampledLap) -> np.ndarray:
    """
    Returns an array of time deltas (in seconds) at each 0.7m distance point.
    Negative = comparison lap is FASTER (gaining time).
    Positive = comparison lap is SLOWER (losing time).
    """
    # Both laps are already resampled to the same 0.7m grid
    # Trim to the shorter lap length
    min_len = min(len(reference_lap.time), len(comparison_lap.time))

    delta_t = comparison_lap.time[:min_len] - reference_lap.time[:min_len]
    return delta_t
```

The Delta-T derivative (slope) tells you WHERE time is being gained/lost:
- `d(delta_t)/d(distance) > 0` → losing time in this section
- `d(delta_t)/d(distance) < 0` → gaining time in this section

### 1.6 Corner Detection & KPI Extraction

**Goal**: Automatically identify corners and extract the 5 key performance indicators at each.

**Corner detection algorithm** (using heading rate of change):
```python
def detect_corners(heading: np.ndarray, distance: np.ndarray,
                   min_heading_rate=2.0, min_corner_length=20.0):
    """
    Detect corners by finding sustained heading changes.
    heading: degrees array (resampled at 0.7m intervals)
    min_heading_rate: degrees per meter threshold
    min_corner_length: minimum 20m to qualify as a corner (not noise)
    """
    # Calculate heading rate of change (deg/m)
    heading_rate = np.abs(np.gradient(unwrap_heading(heading), distance))

    # Smooth to avoid false positives
    heading_rate_smooth = savgol_filter(heading_rate, window_length=51, polyorder=3)

    # Find regions where heading rate exceeds threshold
    in_corner = heading_rate_smooth > min_heading_rate

    # Group consecutive True values into corner segments
    corners = find_segments(in_corner, distance, min_length=min_corner_length)
    return corners  # list of (start_m, end_m, direction) tuples
```

**KPI extraction for each corner**:

| KPI | How It's Found | What It Means |
|---|---|---|
| **Brake Point** | First distance where longitudinal G < -0.2g (within 50m before corner entry) | Where the driver starts braking |
| **Brake Pressure Peak** | Minimum longitudinal G value (most negative) | How hard the driver brakes |
| **Min Speed** | Lowest speed value within the corner segment | Apex/mid-corner speed |
| **Min Speed Location** | Distance at which min speed occurs | Early apex vs. late apex indicator |
| **Throttle Commit** | First distance where longitudinal G > +0.1g sustained for 20m+ after min speed | Where the driver gets back on power |

**Note on G-force**: If the CSV source doesn't include accelerometer G-force data (RaceBox without IMU), we derive it from the speed channel:
```python
longitudinal_g = np.gradient(speed_mps, time_s) / 9.81
lateral_g = (speed_mps ** 2) * np.gradient(heading_rad, distance_m) / 9.81
```

---

## Phase 2: AI Coaching Layer (Claude Integration)

### 2.1 Coaching Service Architecture

**Goal**: Trophi.ai-inspired AI coaching that provides corner-by-corner analysis, prioritized feedback, and conversational memory.

**Coaching analysis pipeline**:
```
ResampledLap(s) + Corner KPIs + Delta-T
            │
            ▼
   ┌─────────────────┐
   │  Data Summarizer │  ← Converts numpy arrays into structured text
   │  (Python)        │     that Claude can reason about
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │  Claude API      │  ← System prompt + structured data + conversation history
   │  (Anthropic SDK) │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │  Coach Response  │  ← Structured JSON: tips, scores, priorities
   │  Parser          │
   └─────────────────┘
```

### 2.2 Data Summarizer

Claude doesn't need 4,571 rows of raw data. The summarizer distills each lap into a structured analysis document:

```python
def summarize_for_coaching(session, reference_lap, comparison_lap, corners, delta_t):
    """
    Build a structured text summary for Claude.
    """
    summary = {
        "track": session.track.name,
        "session_date": session.date,
        "reference_lap": {
            "lap_number": reference_lap.number,
            "lap_time": reference_lap.total_time,
        },
        "comparison_lap": {
            "lap_number": comparison_lap.number,
            "lap_time": comparison_lap.total_time,
            "total_delta": comparison_lap.total_time - reference_lap.total_time,
        },
        "corners": []
    }

    for corner in corners:
        ref_kpis = extract_kpis(reference_lap, corner)
        cmp_kpis = extract_kpis(comparison_lap, corner)
        corner_delta = delta_t[corner.end_idx] - delta_t[corner.start_idx]

        summary["corners"].append({
            "name": corner.name,  # "Turn 1" or custom name
            "distance_range": f"{corner.start_m}m - {corner.end_m}m",
            "time_lost_gained": corner_delta,
            "brake_point_ref": ref_kpis.brake_point,
            "brake_point_cmp": cmp_kpis.brake_point,
            "brake_point_delta_m": cmp_kpis.brake_point - ref_kpis.brake_point,
            "min_speed_ref_mph": ref_kpis.min_speed_mph,
            "min_speed_cmp_mph": cmp_kpis.min_speed_mph,
            "min_speed_location_ref": ref_kpis.min_speed_location,
            "min_speed_location_cmp": cmp_kpis.min_speed_location,
            "throttle_commit_ref": ref_kpis.throttle_commit,
            "throttle_commit_cmp": cmp_kpis.throttle_commit,
            "peak_brake_g_ref": ref_kpis.peak_brake_g,
            "peak_brake_g_cmp": cmp_kpis.peak_brake_g,
        })

    return summary
```

### 2.3 Claude System Prompt Design

```
You are an expert motorsport driving coach analyzing telemetry data from
track day sessions. You communicate like a professional driving instructor —
direct, specific, and focused on actionable improvements.

RULES:
- Always reference specific corners by name and distance markers
- Quantify everything: "brake 5m later" not "brake later"
- Prioritize feedback by time cost: address the biggest time losses first
- For each corner, assess: brake point, trail braking, min speed,
  throttle commit, and line (via min speed location)
- Score each skill 1-10 relative to the reference lap
- Give exactly ONE concise coaching tip per corner (≤15 words)
- When the driver asks follow-up questions, reference the data specifically
- If you see a pattern across multiple corners (e.g., consistently
  early braking), call it out as a global tendency
- Reference past sessions when available to highlight improvement trends

DRIVER CONTEXT:
- Vehicle: Modified street car (~1.0-1.3g lateral capability)
- Experience level: HPDE / time attack
- Data source: RaceBox Mini 25Hz GPS

RESPONSE FORMAT:
Return a JSON object with this structure:
{
  "overall_summary": "string (2-3 sentences)",
  "total_time_delta": float,
  "top_priority_corners": ["Turn X", "Turn Y"],
  "global_tendencies": ["string"],
  "corners": [
    {
      "name": "Turn 1",
      "time_delta": float,
      "scores": {
        "braking": int,
        "trail_braking": int,
        "min_speed": int,
        "throttle_application": int,
        "consistency": int
      },
      "coaching_tip": "string (≤15 words)",
      "detailed_analysis": "string (2-3 sentences)"
    }
  ],
  "session_trend": "string (if past session data available)"
}
```

### 2.4 Conversation & Memory

**Database schema for coaching history**:
```sql
CREATE TABLE coaching_sessions (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    created_at TIMESTAMP,
    system_prompt TEXT,
    data_context TEXT  -- the summarized telemetry data
);

CREATE TABLE coaching_messages (
    id UUID PRIMARY KEY,
    coaching_session_id UUID REFERENCES coaching_sessions(id),
    role TEXT,          -- 'user' | 'assistant'
    content TEXT,
    created_at TIMESTAMP
);
```

**Conversation flow**:
1. User uploads CSV / selects session → system auto-generates the coach report
2. User can ask follow-up questions in natural language
3. Full conversation history is maintained in the Claude API context
4. Cross-session: When generating a new report, the system includes a "previous session summary" in the context from the last session at the same track

### 2.5 Technique Scoring (Trophi-Inspired)

Score each skill 1-10 per corner and aggregate to a per-lap "technique score":

| Skill | What's Measured | Scoring Basis |
|---|---|---|
| **Braking** | Brake point accuracy vs. reference | Distance delta from reference brake point |
| **Trail Braking** | Brake release profile into corner | Shape of decel curve from brake point to min speed |
| **Min Speed** | Corner speed vs. reference | Speed delta at apex |
| **Throttle Application** | Throttle commit timing & progression | Distance delta for throttle commit + accel profile |
| **Consistency** | Lap-to-lap variance for this corner | StdDev of KPIs across all session laps |

**Overall technique score** = weighted average of all corner scores, weighted by time cost (corners where you lose the most time weigh more heavily).

---

## Phase 3: Frontend (React + D3.js)

### 3.1 Pages & Views

| Page | Purpose | Key D3 Components |
|---|---|---|
| **Dashboard** | Session list, recent activity, quick stats | Lap time sparklines, session cards |
| **Session View** | Overview of one track day: all laps, best lap, consistency | Lap time bar chart, track map |
| **Lap Analysis** | Single lap deep dive: speed trace, G-G diagram, track map | Speed vs. distance, G-G scatter, colored track map |
| **Lap Compare** | Side-by-side or overlay of 2+ laps | Delta-T line, dual speed traces, corner KPI comparison table |
| **AI Coach** | Chat interface + auto-generated coach report | Corner score radar chart, technique score timeline |
| **Track Manager** | View/edit track definitions, corner boundaries | Interactive track map with draggable corner markers |

### 3.2 Core D3.js Visualizations

**Speed vs. Distance Trace**:
- X-axis: distance (meters), Y-axis: speed (mph)
- Overlay multiple laps with color coding
- Corner regions shaded in background
- Hover tooltip shows exact speed, G-force, time at any point

**Delta-T Line**:
- X-axis: distance, Y-axis: cumulative time delta (seconds)
- Green fill below zero (gaining), red fill above zero (losing)
- Corner boundaries marked with vertical dashed lines
- The slope of this line = instantaneous time gain/loss rate

**Track Map (GPS scatter with speed coloring)**:
- Plot lat/lon coordinates
- Color each point by speed (blue=slow, red=fast) or by delta-T (green=gaining, red=losing)
- Corner labels overlaid
- Click a corner to zoom into that section's telemetry

**G-G Diagram**:
- X-axis: lateral G, Y-axis: longitudinal G
- Plots the "traction circle" — how much of the tire's grip the driver is using
- Perfect driving fills the circle; gaps = unused grip
- Color points by distance to show progression through corners

**Corner Radar Chart** (per-corner technique scoring):
- 5 axes: Braking, Trail Braking, Min Speed, Throttle, Consistency
- Overlay reference lap (filled) vs. comparison lap (outline)
- Quick visual of which skills are strong/weak at each corner

### 3.3 API Contract (FastAPI ↔ Next.js)

```
POST   /api/sessions/upload          # Upload CSV file
GET    /api/sessions                  # List all sessions
GET    /api/sessions/{id}             # Session detail + laps
GET    /api/sessions/{id}/laps        # All laps for a session
GET    /api/laps/{id}                 # Full resampled lap data
GET    /api/laps/{id}/kpis            # Corner KPIs for a lap
GET    /api/laps/compare?ref={id}&cmp={id}  # Delta-T + comparison data
GET    /api/tracks                    # Track database
PUT    /api/tracks/{id}/corners       # Manual corner override
POST   /api/coaching/report           # Generate AI coach report
POST   /api/coaching/chat             # Conversational follow-up
GET    /api/coaching/history/{session_id}  # Past coaching messages
```

---

## Phase 4: Voice Coaching (Live Mode Foundation)

### 4.1 Voice I/O Architecture

For the "between sessions" use case (v1):
- **Speech-to-Text**: Web Speech API (browser-native) or Whisper API
- **Text-to-Speech**: Browser SpeechSynthesis API or ElevenLabs for natural voice
- User presses a mic button in the coach chat, speaks their question
- Transcribed text goes to Claude API as a regular message
- Claude's response is spoken back

For the "live on track" use case (v2, future):
- WebSocket connection from phone/tablet in the car to backend
- Backend receives live GPS stream from RaceBox via BT
- Real-time distance integration + delta-T computation
- After each lap crossing, auto-generate a 10-word coaching tip
- TTS plays the tip through the car's audio system

### 4.2 Live Predictive Delta (Future Architecture)

```
RaceBox Mini (BT) → Phone App → WebSocket → FastAPI Backend
                                                │
                                    ┌───────────┴───────────┐
                                    │ Real-time Distance     │
                                    │ Integration Engine     │
                                    │                        │
                                    │ Compare current GPS    │
                                    │ position to reference  │
                                    │ lap at same distance   │
                                    └───────────┬───────────┘
                                                │
                                    ┌───────────▼───────────┐
                                    │ Predictive Lap Time   │
                                    │ = ref_time + delta_t  │
                                    │   at current distance  │
                                    └───────────┬───────────┘
                                                │
                                    WebSocket → Phone Display + Audio
```

---

## Phase 5: Database Schema (Full)

```sql
-- Tracks
CREATE TABLE tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    config TEXT,
    country TEXT,
    state TEXT,
    start_finish_lat DOUBLE PRECISION NOT NULL,
    start_finish_lon DOUBLE PRECISION NOT NULL,
    start_finish_heading DOUBLE PRECISION NOT NULL,
    track_length_m DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Corner definitions (manual override or auto-detected)
CREATE TABLE corners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id UUID REFERENCES tracks(id) ON DELETE CASCADE,
    name TEXT NOT NULL,               -- "Turn 1", "The Esses", etc.
    number INTEGER NOT NULL,
    start_distance_m DOUBLE PRECISION NOT NULL,
    end_distance_m DOUBLE PRECISION NOT NULL,
    direction TEXT CHECK (direction IN ('left', 'right')),
    is_manual_override BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Sessions (one per track day / CSV upload)
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id UUID REFERENCES tracks(id),
    date DATE NOT NULL,
    source_format TEXT NOT NULL,       -- 'racebox' | 'racechrono'
    source_filename TEXT,
    notes TEXT,
    weather TEXT,
    vehicle_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Individual laps
CREATE TABLE laps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    lap_number INTEGER NOT NULL,
    lap_time_s DOUBLE PRECISION NOT NULL,
    total_distance_m DOUBLE PRECISION NOT NULL,
    is_reference BOOLEAN DEFAULT false,
    is_valid BOOLEAN DEFAULT true,     -- false for pit/incomplete laps
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Resampled telemetry data (the 0.7m arrays, stored efficiently)
CREATE TABLE lap_telemetry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lap_id UUID REFERENCES laps(id) ON DELETE CASCADE,
    -- Store as binary arrays for efficiency (numpy .tobytes())
    distance_array BYTEA NOT NULL,     -- float64 array
    time_array BYTEA NOT NULL,
    speed_array BYTEA NOT NULL,
    lat_array BYTEA NOT NULL,
    lon_array BYTEA NOT NULL,
    heading_array BYTEA NOT NULL,
    long_g_array BYTEA,               -- nullable (derived if not in source)
    lat_g_array BYTEA,
    num_points INTEGER NOT NULL,
    resample_step_m DOUBLE PRECISION NOT NULL DEFAULT 0.7
);

-- Corner KPIs per lap
CREATE TABLE corner_kpis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lap_id UUID REFERENCES laps(id) ON DELETE CASCADE,
    corner_id UUID REFERENCES corners(id) ON DELETE CASCADE,
    brake_point_m DOUBLE PRECISION,
    peak_brake_g DOUBLE PRECISION,
    min_speed_mps DOUBLE PRECISION,
    min_speed_distance_m DOUBLE PRECISION,
    throttle_commit_m DOUBLE PRECISION,
    time_through_corner_s DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- AI coaching
CREATE TABLE coaching_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id),
    reference_lap_id UUID REFERENCES laps(id),
    comparison_lap_id UUID REFERENCES laps(id),
    technique_score DOUBLE PRECISION,
    report_json JSONB,                 -- full structured report from Claude
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE coaching_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coaching_session_id UUID REFERENCES coaching_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## Implementation Order

### Sprint 1: Foundation
1. Project scaffolding (monorepo, Docker, CI)
2. PostgreSQL schema + Alembic migrations
3. CSV ingestion (both formats) with format auto-detection
4. Distance integration + 0.7m resampling
5. Unit tests with synthetic data + user's sample CSVs

### Sprint 2: Analysis Engine
6. Track auto-detection + lap splitting
7. Delta-T calculation
8. Corner auto-detection
9. KPI extraction (brake point, min speed, throttle commit)
10. Manual corner override API

### Sprint 3: AI Coaching
11. Claude API integration + data summarizer
12. System prompt design + structured output parsing
13. Coach report generation
14. Conversational follow-up (chat)
15. Session history + cross-session trend analysis

### Sprint 4: Frontend Core
16. Next.js scaffolding + layout
17. Session upload + dashboard
18. D3.js speed vs. distance trace
19. D3.js delta-T visualization
20. D3.js track map with speed coloring

### Sprint 5: Frontend Advanced
21. Lap comparison view (multi-lap overlay)
22. Corner KPI comparison table
23. G-G diagram
24. Corner radar chart (technique scoring)
25. AI coach chat interface

### Sprint 6: Voice & Polish
26. Voice input (Web Speech API / Whisper)
27. Voice output (TTS)
28. Track manager UI (corner editing)
29. Performance optimization (large sessions)
30. Error handling, edge cases, UX polish

### Future Sprints:
- Live BT streaming from RaceBox
- Real-time predictive delta
- Multi-user auth
- Cloud deployment
- Mobile-optimized UI for in-car use

---

## Key Dependencies

### Backend (Python)
```
fastapi
uvicorn
sqlalchemy[asyncio]
alembic
asyncpg              # PostgreSQL async driver
numpy
scipy
anthropic            # Claude API SDK
python-multipart     # File uploads
pydantic
```

### Frontend (TypeScript)
```
next
react
d3
@types/d3
tailwindcss          # Utility CSS
```

---

## Open Questions / Risks

1. **G-force accuracy from GPS-only**: Deriving longitudinal G from speed differentiation works but is noisier than a real accelerometer. The Savitzky-Golay filter helps, but for precision trail-braking analysis, an IMU would be better. Worth noting in the UI when data is "GPS-derived" vs. "accelerometer-measured."

2. **Track database seeding**: Need to decide on the initial set of tracks to seed. User to provide their home tracks.

3. **RaceBox CSV format verification**: Need user's actual sample CSVs to confirm exact column headers and data format before building the parser.

4. **Claude API cost**: Each coach report is ~2K input tokens (summarized data) + ~1K output tokens. At Sonnet pricing, ~$0.01 per report. Conversational follow-ups add more. Voice coaching at scale could get expensive.

5. **0.7m resampling validation**: Need to verify that 0.7m doesn't introduce artifacts at very high speeds where native resolution drops to ~1.8m. May need adaptive smoothing.

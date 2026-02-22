# Cataclysm MVP: Post-Session Analysis + AI Coaching

> Upload RaceChrono CSV v3 -> see your laps -> get AI coaching tips. Usable tomorrow at the track.

---

## What This MVP Does

1. Upload a RaceChrono CSV v3 export from your phone
2. Engine computes distance from GPS (our own math, not RaceChrono's)
3. Engine detects S/F line and splits laps (our own detection, not RaceChrono's)
4. 0.7m distance-domain resampling for lap alignment
5. Interactive charts: speed vs distance, delta-T, track map with speed coloring
6. Auto-detects corners from heading/yaw data
7. Extracts corner KPIs: brake point, min speed, throttle commit
8. Claude API generates prioritized coaching report with A-F technique grades
9. Chat with the AI coach about specific corners

**Stack**: Python + Streamlit + Plotly + Claude API. No Docker, no frontend framework, no database.

**Key principle**: The engine computes everything from raw GPS + IMU. RaceChrono is just the export tool. Same engine works with RaceBox direct CSV or BT stream later -- only the parser changes.

---

## Architecture

```
RaceChrono CSV v3 (or RaceBox CSV later)
       |
       v
+----------------+
|  CSV Parser     |  -> Positional parsing (handles duplicate columns)
|  (thin layer)   |  -> Normalizes to TelemetryFrame array
+-------+--------+
        |
        v
+-------------------------------+
|  Core Engine (device-agnostic) |
|                                |
|  1. Distance Integration       |  <- Haversine from GPS (ours, not RaceChrono's)
|  2. Lap Splitting              |  <- S/F gate crossing (ours, not RaceChrono's)
|  3. 0.7m Resampling            |  <- scipy interp1d
|  4. Corner Detection           |  <- Heading rate / yaw rate
|  5. KPI Extraction             |  <- Brake point, min speed, throttle commit
|  6. Delta-T Calculation        |  <- Distance-domain subtraction
+-------+-----------------------+
        |
        v
+-------------------------------+
|  Streamlit UI                  |
|                                |
|  - Session overview + lap times|
|  - Speed vs Distance (Plotly)  |  <- Multi-lap overlay
|  - Delta-T chart (Plotly)      |  <- Green/red fill
|  - Track map (Plotly)          |  <- GPS scatter, speed-colored
|  - Corner KPI table            |  <- Side-by-side comparison
|  - AI Coach (Claude API)       |  <- Report + follow-up chat
+-------------------------------+
```

---

## File Structure

```
cataclysm/
+-- app.py                    # Streamlit entry point
+-- cataclysm/
|   +-- __init__.py
|   +-- parser.py             # CSV format detection + parsing
|   +-- engine.py             # Distance, resampling, lap splitting
|   +-- corners.py            # Corner detection + KPI extraction
|   +-- delta.py              # Delta-T calculation
|   +-- coaching.py           # Claude API integration
|   +-- charts.py             # Plotly chart builders
+-- sample_data/
|   +-- racechrono_v3_barber.csv
+-- pyproject.toml
+-- PLAN.md                   # This file (MVP plan)
+-- PLAN_FULL.md              # Full platform plan (FastAPI + Next.js + D3.js)
```

---

## Module Details

### 1. parser.py -- CSV Ingestion

Parses RaceChrono CSV v3 by column POSITION (not name) due to duplicate headers.

Skips 8 metadata lines + 3 header rows. Extracts session metadata (track name, date).

Normalizes to TelemetryFrame:
- timestamp (unix epoch)
- elapsed_time (seconds from session start)
- lat, lon (decimal degrees)
- speed_mps (GPS speed, position 14)
- heading_deg (bearing, position 7)
- altitude_m, accuracy_m, satellites
- lat_g, lon_g (calculated G-forces, positions 17, 19)
- x_acc_g, y_acc_g, z_acc_g (raw IMU, positions 22-24)
- yaw_rate_dps (gyro Z, position 28)

Validation: drop frames where accuracy > 3.0m or satellites < 5.

### 2. engine.py -- Core Distance-Domain Engine

**Distance integration**: Always computed from GPS via flat-earth projection. Never uses RaceChrono's distance_traveled (we validate against it instead).

**Lap splitting**: Detect S/F gate by finding where GPS path crosses itself after >500m of travel. Split session at each gate crossing. Discard laps <80% of median distance.

**Resampling**: scipy interp1d at 0.7m steps. Every lap becomes a uniform array where index N = N * 0.7 meters from S/F.

### 3. corners.py -- Corner Detection + KPIs

**Detection**: Heading rate of change (deg/m) thresholded at ~1.5 deg/m, smoothed, with minimum corner length 15m.

**KPIs per corner**:
- Brake point: where lon_g < -0.2G (search 80m before corner entry)
- Peak brake G: most negative lon_g
- Min speed: lowest speed in corner segment
- Min speed location: early vs late apex indicator
- Throttle commit: where lon_g > +0.1G sustained 15m after min speed

### 4. delta.py -- Delta-T

Subtract time arrays of two resampled laps at each 0.7m point. Per-corner delta = delta at corner exit minus delta at corner entry.

### 5. coaching.py -- Claude API

Summarize corner KPIs + deltas into structured text. Claude returns JSON with:
- Priority corners ranked by time cost
- A-F grades per corner (braking, trail braking, min speed, throttle)
- One tip per corner (max 15 words)
- Global pattern identification
- Conversational follow-up supported

### 6. charts.py -- Plotly Charts

- Speed vs distance (multi-lap overlay, corner shading)
- Delta-T (green/red fill, corner boundary markers)
- Track map (lat/lon scatter, speed colorscale)
- Lap time bar chart (best lap highlighted)

---

## Validation Strategy

RaceChrono's pre-computed fields validate our engine:

| Our Calculation | Validated Against | Acceptable Error |
|---|---|---|
| Cumulative distance (Haversine) | RaceChrono distance_traveled | < 1% per lap |
| Lap boundaries (S/F gate) | RaceChrono lap_number transitions | Same count, < 5m offset |
| Lap times (our splits) | RaceChrono lap times | < 0.1s |

---

## Dependencies

```
streamlit>=1.30
plotly>=5.18
numpy>=1.26
scipy>=1.12
pandas>=2.1
anthropic>=0.40
```

---

## How To Run

```bash
pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

Open http://localhost:8501, upload CSV, analyze.

---

## Build Order

1. parser.py -- Parse Barber CSV, verify clean TelemetryFrames
2. engine.py -- Distance + lap splitting + resampling (validate against RaceChrono)
3. charts.py -- Speed trace + track map (visual verification)
4. corners.py -- Corner detection + KPIs
5. delta.py -- Delta-T between laps
6. coaching.py -- Claude API coaching report
7. app.py -- Wire everything in Streamlit

---

## Not In MVP (see PLAN_FULL.md)

- RaceBox direct CSV / BT streaming
- Track database with GPS proximity matching
- Manual corner editing UI
- PostgreSQL / persistent storage
- User accounts
- Voice input/output
- FastAPI + Next.js + D3.js
- Docker
- Cross-session trend analysis
- G-G diagram

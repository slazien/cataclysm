# Data Models

All core data structures are Python dataclasses. Backend API uses Pydantic schemas. Frontend uses TypeScript interfaces.

## Core Engine Dataclasses (`cataclysm/`)

### Session & Parsing

```python
@dataclass
class SessionMetadata:
    track_name: str
    session_date: str
    racechrono_version: str

@dataclass
class ParsedSession:
    metadata: SessionMetadata
    data: pd.DataFrame  # Quality-filtered telemetry
```

### Lap Processing

```python
@dataclass
class LapSummary:
    lap_number: int
    lap_time_s: float
    lap_distance_m: float
    max_speed_mps: float
    tags: set[str] = field(default_factory=set)

@dataclass
class ProcessedSession:
    lap_summaries: list[LapSummary]
    resampled_laps: dict[int, pd.DataFrame]  # lap_number → resampled DataFrame
    best_lap: int
```

### Corners

```python
@dataclass
class Corner:
    number: int
    entry_distance_m: float
    exit_distance_m: float
    apex_distance_m: float
    min_speed_mps: float
    brake_point_m: float | None
    peak_brake_g: float | None
    throttle_commit_m: float | None
    apex_type: str                          # "early" | "mid" | "late"
    # Optional enrichment from track database:
    brake_point_lat: float | None = None
    brake_point_lon: float | None = None
    apex_lat: float | None = None
    apex_lon: float | None = None
    peak_curvature: float | None = None
    mean_curvature: float | None = None
    direction: str | None = None            # "left" | "right"
    segment_type: str | None = None         # "corner" | "transition"
    parent_complex: int | None = None
    detection_method: str | None = None     # "heading_rate" | "spline" | "pelt" | "css" | "asc"
    character: str | None = None            # "flat" | "lift" | "brake"
    corner_type_hint: str | None = None     # "hairpin" | "sweeper"
    elevation_trend: str | None = None      # "uphill" | "downhill" | "flat" | "crest" | "compression"
    camber: str | None = None               # "positive" | "negative" | "off-camber"
    blind: bool = False
    coaching_notes: str | None = None
    elevation_change_m: float | None = None
    gradient_pct: float | None = None

# Type alias
AllLapCorners = dict[int, list[Corner]]     # lap_number → list of corners
CornerType = str                            # "slow" | "medium" | "fast"
```

### Delta (Lap Comparison)

```python
@dataclass
class CornerDelta:
    corner_number: int
    delta_s: float                          # positive = comparison slower

@dataclass
class DeltaResult:
    distance_m: np.ndarray
    delta_time_s: np.ndarray                # positive = comparison slower
    corner_deltas: list[CornerDelta] = field(default_factory=list)
    total_delta_s: float = 0.0
```

### Coaching

```python
@dataclass
class CornerGrade:
    corner: int
    braking: str
    trail_braking: str
    min_speed: str
    throttle: str
    notes: str

@dataclass
class CoachingReport:
    summary: str
    priority_corners: list[dict[str, object]]
    corner_grades: list[CornerGrade]
    patterns: list[str]
    drills: list[str] = field(default_factory=list)
    raw_response: str = ""
    validation_failed: bool = False
    validation_violations: list[str] = field(default_factory=list)

@dataclass
class CoachingContext:
    messages: list[dict[str, str]] = field(default_factory=list)

SkillLevel = str                            # "novice" | "intermediate" | "advanced"
```

### Gains (Time-Gain Estimation)

```python
@dataclass
class SegmentDefinition:
    name: str                               # "T5" or "S3-4"
    entry_distance_m: float
    exit_distance_m: float
    is_corner: bool

@dataclass
class SegmentGain:
    segment: SegmentDefinition
    best_time_s: float
    avg_time_s: float
    gain_s: float
    best_lap: int
    lap_times_s: dict[int, float] = field(default_factory=dict)

@dataclass
class ConsistencyGainResult:
    segment_gains: list[SegmentGain]
    total_gain_s: float
    avg_lap_time_s: float
    best_lap_time_s: float

@dataclass
class CompositeGainResult:
    segment_gains: list[SegmentGain]
    composite_time_s: float
    best_lap_time_s: float
    gain_s: float

@dataclass
class TheoreticalBestResult:
    sector_size_m: float
    n_sectors: int
    theoretical_time_s: float
    best_lap_time_s: float
    gain_s: float

@dataclass
class PhysicsGapResult:
    optimal_lap_time_s: float
    composite_time_s: float
    gap_s: float

@dataclass
class GainEstimate:
    consistency: ConsistencyGainResult
    composite: CompositeGainResult
    theoretical: TheoreticalBestResult
    clean_lap_numbers: list[int]
    best_lap_number: int
    physics_gap: PhysicsGapResult | None = None
```

### Consistency

```python
@dataclass
class LapConsistency:
    std_dev_s: float
    spread_s: float
    mean_abs_consecutive_delta_s: float
    max_consecutive_delta_s: float
    consistency_score: float                # 0-100
    choppiness_score: float                 # 0-100
    spread_score: float                     # 0-100
    jump_score: float                       # 0-100
    lap_numbers: list[int]
    lap_times_s: list[float]
    consecutive_deltas_s: list[float]

@dataclass
class CornerConsistencyEntry:
    corner_number: int
    min_speed_std_mph: float
    min_speed_range_mph: float
    brake_point_std_m: float | None
    throttle_commit_std_m: float | None
    consistency_score: float                # 0-100
    lap_numbers: list[int]
    min_speeds_mph: list[float]

@dataclass
class TrackPositionConsistency:
    distance_m: np.ndarray
    speed_std_mph: np.ndarray
    speed_mean_mph: np.ndarray
    speed_median_mph: np.ndarray
    n_laps: int
    lat: np.ndarray
    lon: np.ndarray

@dataclass
class SessionConsistency:
    lap_consistency: LapConsistency
    corner_consistency: list[CornerConsistencyEntry]
    track_position: TrackPositionConsistency
```

### Corner Analysis

```python
@dataclass
class CornerStats:
    best: float
    mean: float
    std: float
    value_range: float
    best_lap: int
    n_laps: int

@dataclass
class CornerCorrelation:
    kpi_x: str
    kpi_y: str
    r: float
    strength: str                           # "strong" | "moderate" | "weak"
    n_points: int

@dataclass
class CornerRecommendation:
    target_brake_m: float | None
    target_brake_landmark: LandmarkReference | None
    target_min_speed_mph: float
    gain_s: float
    corner_type: str                        # "slow" | "medium" | "fast"
    character: str | None = None
    corner_type_hint: str | None = None
    elevation_trend: str | None = None
    camber: str | None = None
    blind: bool = False
    coaching_notes: str | None = None
    elevation_change_m: float | None = None
    gradient_pct: float | None = None

@dataclass
class CornerAnalysis:
    corner_number: int
    n_laps: int
    stats_min_speed: CornerStats
    stats_brake_point: CornerStats | None
    stats_peak_brake_g: CornerStats | None
    stats_throttle_commit: CornerStats | None
    apex_distribution: dict[str, int]
    recommendation: CornerRecommendation
    time_value: TimeValue | None
    correlations: list[CornerCorrelation] = field(default_factory=list)

@dataclass
class SessionCornerAnalysis:
    corners: list[CornerAnalysis]           # sorted by gain opportunity
    best_lap: int
    total_consistency_gain_s: float
    n_laps_analyzed: int
```

### Physics & Velocity Profile

```python
@dataclass
class VehicleParams:
    mu: float                               # friction coefficient
    max_accel_g: float
    max_decel_g: float
    max_lateral_g: float
    friction_circle_exponent: float = 2.0   # 2.0=circle, >2=diamond
    aero_coefficient: float = 0.0
    drag_coefficient: float = 0.0
    top_speed_mps: float = 80.0

@dataclass
class OptimalProfile:
    distance_m: np.ndarray
    optimal_speed_mps: np.ndarray
    curvature: np.ndarray
    max_cornering_speed_mps: np.ndarray
    optimal_brake_points: list[float]
    optimal_throttle_points: list[float]
    lap_time_s: float
    vehicle_params: VehicleParams

@dataclass
class CurvatureResult:
    distance_m: np.ndarray
    curvature: np.ndarray                   # signed (positive=left)
    abs_curvature: np.ndarray
    heading_rad: np.ndarray
    x_smooth: np.ndarray
    y_smooth: np.ndarray
```

### Track Database

```python
@dataclass(frozen=True)
class OfficialCorner:
    number: int
    name: str
    fraction: float                         # Apex as fraction of lap distance (0.0-1.0)
    lat: float | None = None
    lon: float | None = None
    character: str | None = None            # "flat" | "lift" | "brake"
    direction: str | None = None            # "left" | "right"
    corner_type: str | None = None          # "hairpin" | "sweeper" | "chicane" | "kink"
    elevation_trend: str | None = None
    camber: str | None = None
    blind: bool = False
    coaching_notes: str | None = None

@dataclass(frozen=True)
class TrackLayout:
    name: str
    corners: list[OfficialCorner]
    landmarks: list[Landmark] = field(default_factory=list)
    center_lat: float | None = None
    center_lon: float | None = None
    country: str = ""
    length_m: float | None = None
    elevation_range_m: float | None = None

@dataclass
class TrackMatch:
    layout: TrackLayout
    distance_m: float
    confidence: float                       # 0.0-1.0
```

### Landmarks

```python
class LandmarkType(Enum):
    brake_board = "brake_board"
    structure = "structure"
    barrier = "barrier"
    road = "road"
    curbing = "curbing"
    natural = "natural"
    marshal = "marshal"
    sign = "sign"

@dataclass(frozen=True)
class Landmark:
    name: str
    distance_m: float
    landmark_type: LandmarkType
    lat: float | None = None
    lon: float | None = None
    description: str | None = None

@dataclass(frozen=True)
class LandmarkReference:
    landmark: Landmark
    offset_m: float                         # signed distance from query point

    def format_reference(self) -> str:
        """e.g., 'at the 200m board' or '15m before the access road'"""
```

### Equipment

```python
class TireCompoundCategory(StrEnum):
    STREET = "street"
    ENDURANCE_200TW = "endurance_200tw"
    SUPER_200TW = "super_200tw"
    TW_100 = "tw_100"
    R_COMPOUND = "r_compound"
    SLICK = "slick"

@dataclass
class TireSpec:
    model: str
    compound_category: TireCompoundCategory
    size: str
    treadwear_rating: int | None
    estimated_mu: float
    mu_source: MuSource
    mu_confidence: str
    pressure_psi: float | None = None
    brand: str | None = None
    age_sessions: int | None = None

@dataclass
class BrakeSpec:
    compound: str | None = None
    rotor_type: str | None = None
    pad_temp_range: str | None = None
    fluid_type: str | None = None

@dataclass
class SuspensionSpec:
    type: str | None = None
    front_spring_rate: str | None = None
    rear_spring_rate: str | None = None
    front_camber_deg: float | None = None
    rear_camber_deg: float | None = None
    # ... additional fields

@dataclass
class EquipmentProfile:
    id: str
    name: str
    tires: TireSpec
    brakes: BrakeSpec | None = None
    suspension: SuspensionSpec | None = None
    notes: str | None = None

@dataclass
class SessionEquipment:
    session_id: str
    profile_id: str
    overrides: dict[str, object] = field(default_factory=dict)
    conditions: SessionConditions | None = None
```

### Mini Sectors

```python
@dataclass
class MiniSector:
    index: int
    entry_distance_m: float
    exit_distance_m: float
    gps_points: list[tuple[float, float]]

@dataclass
class MiniSectorLapData:
    lap_number: int
    sector_times_s: list[float]
    deltas_s: list[float]
    classifications: list[str]              # "pb" | "faster" | "slower" | "neutral"

@dataclass
class MiniSectorAnalysis:
    sectors: list[MiniSector]
    best_sector_times_s: list[float]
    best_sector_laps: list[int]
    lap_data: dict[int, MiniSectorLapData]
    n_sectors: int
```

### Sectors

```python
@dataclass
class SectorSplit:
    sector_name: str
    time_s: float
    is_personal_best: bool = False

@dataclass
class LapSectorSplits:
    lap_number: int
    total_time_s: float
    splits: list[SectorSplit]

@dataclass
class SectorAnalysis:
    segments: list[SegmentDefinition]
    lap_splits: list[LapSectorSplits]
    best_sector_times: dict[str, float]
    best_sector_laps: dict[str, int]
    composite_time_s: float
```

---

## Backend Pydantic Schemas (`backend/api/schemas/`)

Backend schemas mirror core dataclasses but use Pydantic `BaseModel` for request/response validation. Key schemas:

### Session Schemas
- `SessionSummary` — Session metadata + derived scores
- `SessionList` — Paginated list wrapper
- `UploadResponse` — `{session_ids, message}`

### Analysis Schemas
- `CornerResponse` — Corners for one lap
- `AllLapsCornerResponse` — Corners for all laps
- `ConsistencyResponse`, `GainsResponse`, `GripResponse`
- `DeltaResponse` — Delta between two laps
- `LinkedChartResponse` — Multi-lap chart data
- `SectorResponse`, `DegradationResponse`
- `OptimalProfileResponse`, `IdealLapResponse`

### Coaching Schemas
- `CoachingReportResponse` — Report with status
- `ChatRequest` / `FollowUpMessage` — Chat interface

### Equipment Schemas
- `TireSpecSchema`, `BrakeSpecSchema`, `SuspensionSpecSchema`
- `EquipmentProfileResponse`, `SessionEquipmentResponse`
- `SessionConditionsSchema`

---

## Frontend TypeScript Types (`frontend/src/lib/types.ts`)

TypeScript interfaces mirror backend Pydantic schemas. Key types:

```typescript
interface SessionSummary {
  session_id: string
  track_name: string
  session_date: string
  n_laps: number
  best_lap_time_s: number
  consistency_score: number
  session_score?: number
  // ... weather, equipment, GPS quality fields
}

interface Corner {
  number: number
  entry_distance_m: number
  exit_distance_m: number
  apex_distance_m: number
  min_speed_mph: number
  brake_point_m?: number
  peak_brake_g?: number
  throttle_commit_m?: number
  apex_type: string
}

interface CoachingReport {
  session_id: string
  status: "ready" | "generating" | "error"
  summary?: string
  priority_corners: PriorityCorner[]
  corner_grades: CornerGrade[]
  patterns: string[]
  drills: string[]
}

interface LapData {
  lap_number: number
  distance_m: number[]
  speed_mph: number[]
  lat: number[]
  lon: number[]
  heading_deg: number[]
  lateral_g: number[]
  longitudinal_g: number[]
  lap_time_s: number[]
  altitude_m?: number[]
}

// Type alias
type AllLapCorners = Record<string, Corner[]>  // keyed by lap number string
```

## Units & Conversions

| Domain | Internal Unit | Display Unit |
|--------|--------------|-------------|
| Speed | m/s (mps) | mph or km/h (user preference) |
| Distance | meters | meters |
| Time | seconds | seconds (mm:ss.sss for lap times) |
| Acceleration | g | g |
| Temperature | Celsius | Celsius or Fahrenheit |
| Heading | degrees | degrees |
| Coordinates | decimal degrees | decimal degrees |

**Conversion constant**: `MPS_TO_MPH = 2.23694`

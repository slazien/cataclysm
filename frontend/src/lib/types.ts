export interface SessionSummary {
  session_id: string;
  track_name: string;
  session_date: string;
  n_laps: number | null;
  n_clean_laps: number | null;
  best_lap_time_s: number | null;
  top3_avg_time_s: number | null;
  avg_lap_time_s: number | null;
  consistency_score: number | null;
  session_score: number | null;
  tire_model?: string | null;
  compound_category?: string | null;
  equipment_profile_name?: string | null;
  gps_quality_score?: number | null;
  gps_quality_grade?: string | null;
  weather_temp_c?: number | null;
  weather_condition?: string | null;
  weather_humidity_pct?: number | null;
  weather_wind_kmh?: number | null;
  weather_precipitation_mm?: number | null;
}

export interface LapSummary {
  lap_number: number;
  lap_time_s: number;
  is_clean: boolean;
  lap_distance_m: number;
  max_speed_mps: number;
}

export interface LapData {
  lap_number: number;
  distance_m: number[];
  speed_mph: number[];
  lat: number[];
  lon: number[];
  heading_deg: number[];
  lateral_g: number[];
  longitudinal_g: number[];
  lap_time_s: number[];
  altitude_m?: number[] | null;
}

export interface Corner {
  number: number;
  entry_distance_m: number;
  exit_distance_m: number;
  apex_distance_m: number;
  min_speed_mph: number;
  brake_point_m: number | null;
  peak_brake_g: number | null;
  throttle_commit_m: number | null;
  apex_type: string;
}

export interface LapConsistency {
  std_dev_s: number;
  spread_s: number;
  mean_abs_consecutive_delta_s: number;
  max_consecutive_delta_s: number;
  consistency_score: number;
  choppiness_score?: number;
  spread_score?: number;
  jump_score?: number;
  lap_numbers: number[];
  lap_times_s: number[];
  consecutive_deltas_s: number[];
}

export interface TrackPositionConsistency {
  distance_m: number[];
  speed_std_mph: number[];
  speed_mean_mph: number[];
  speed_median_mph: number[];
  n_laps: number;
  lat: number[];
  lon: number[];
}

export interface CornerConsistencyEntry {
  corner_number: number;
  min_speed_std_mph: number;
  min_speed_range_mph: number;
  brake_point_std_m: number | null;
  throttle_commit_std_m: number | null;
  consistency_score: number;
  lap_numbers: number[];
  min_speeds_mph: number[];
}

export interface SessionConsistency {
  lap_consistency: LapConsistency;
  corner_consistency: CornerConsistencyEntry[];
  track_position: TrackPositionConsistency;
}

export interface CornerDelta {
  corner_number: number;
  delta_s: number;
  ref_min_speed_mph: number;
  comp_min_speed_mph: number;
}

export interface DeltaData {
  distance_m: number[];
  delta_s: number[];
  total_delta_s?: number;
  corner_deltas?: CornerDelta[];
}

export interface CornerKPI {
  number: number;
  apex_type: string;
  min_speed_mph: number;
  brake_point_m: number | null;
  peak_brake_g: number | null;
  throttle_commit_m: number | null;
  entry_distance_m: number;
  exit_distance_m: number;
  apex_distance_m: number;
}

export interface TrackFolder {
  folder: string;
  path: string;
  n_files: number;
}

// --- Coaching Types ---

export interface PriorityCorner {
  corner: number;
  time_cost_s: number;
  issue: string;
  tip: string;
}

export interface CornerGrade {
  corner: number;
  braking: string;
  trail_braking: string;
  min_speed: string;
  throttle: string;
  notes: string;
}

export interface CoachingReport {
  session_id: string;
  status: string; // "ready" | "generating" | "error"
  summary: string | null;
  priority_corners: PriorityCorner[];
  corner_grades: CornerGrade[];
  patterns: string[];
  drills: string[];
  validation_failed?: boolean;
  validation_violations?: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface IdealLapData {
  session_id: string;
  distance_m: number[];
  speed_mph: number[];
  segment_sources: [string, number, number][];
}

// --- Trends Types ---

export interface TrendSessionSummary {
  session_id: string;
  session_date: string;
  best_lap_time_s: number;
  top3_avg_time_s: number;
  avg_lap_time_s: number;
  consistency_score: number;
  n_laps: number;
  n_clean_laps: number;
  lap_times_s: number[];
}

export interface TrendAnalysisData {
  track_name: string;
  n_sessions: number;
  best_lap_trend: number[];
  top3_avg_trend: number[];
  consistency_trend: number[];
  theoretical_trend: number[];
  sessions: TrendSessionSummary[];
  corner_min_speed_trends: Record<string, (number | null)[]>;
  corner_brake_std_trends: Record<string, (number | null)[]>;
  corner_consistency_trends: Record<string, (number | null)[]>;
  milestones: Milestone[];
}

export interface TrendAnalysisResponse {
  track_name: string;
  data: TrendAnalysisData;
}

export interface Milestone {
  session_id: string;
  session_date: string;
  category: string;
  description: string;
  value: number;
}

export interface MilestoneResponse {
  track_name: string;
  milestones: Milestone[];
}

// --- Comparison Types ---

export interface ComparisonCornerDelta {
  corner_number: number;
  speed_diff_mph: number;
  a_min_speed_mph: number;
  b_min_speed_mph: number;
}

export interface ComparisonResult {
  session_a_id: string;
  session_b_id: string;
  session_a_track: string;
  session_b_track: string;
  session_a_best_lap: number | null;
  session_b_best_lap: number | null;
  delta_s: number;
  distance_m: number[];
  delta_time_s: number[];
  corner_deltas: ComparisonCornerDelta[];
  session_a_weather_condition?: string | null;
  session_a_weather_temp_c?: number | null;
  session_b_weather_condition?: string | null;
  session_b_weather_temp_c?: number | null;
}

// --- Equipment Types ---

export interface TireSpec {
  model: string;
  compound_category: string;
  size: string;
  treadwear_rating: number | null;
  estimated_mu: number;
  mu_source: string;
  mu_confidence: string;
  pressure_psi: number | null;
  brand: string | null;
  age_sessions: number | null;
}

export interface EquipmentProfile {
  id: string;
  name: string;
  tires: TireSpec;
  brakes?: {
    compound: string | null;
    rotor_type: string | null;
    pad_temp_range: string | null;
    fluid_type: string | null;
  } | null;
  suspension?: Record<string, unknown> | null;
  notes: string | null;
}

export interface EquipmentProfileCreate {
  name: string;
  tires: TireSpec;
  brakes?: {
    compound: string | null;
    rotor_type: string | null;
    pad_temp_range: string | null;
    fluid_type: string | null;
  } | null;
  suspension?: Record<string, unknown> | null;
  notes?: string | null;
}

export interface SessionEquipmentSet {
  profile_id: string;
  overrides?: Record<string, unknown>;
  conditions?: {
    track_condition?: string;
    ambient_temp_c?: number | null;
    track_temp_c?: number | null;
    humidity_pct?: number | null;
  } | null;
}

export interface BrakePadSearchResult {
  model: string;
  brand: string;
  category: string;
  temp_range: string;
  initial_bite: string;
  notes: string;
}

export interface SessionWeather {
  track_condition: string;
  ambient_temp_c: number | null;
  humidity_pct: number | null;
  wind_speed_kmh: number | null;
  wind_direction_deg: number | null;
  precipitation_mm: number | null;
  weather_source: string | null;
}

// --- GPS Quality Types ---

export interface GPSQualityMetric {
  score: number;
  [key: string]: unknown;
}

export interface GPSQualityReport {
  overall_score: number;
  grade: string;
  is_usable: boolean;
  accuracy: { p50: number; p90: number; score: number };
  satellites: { p10: number; p50: number; score: number };
  lap_distance_cv: { cv_percent: number; score: number; n_laps: number } | null;
  speed_spikes: {
    spikes_per_km: number;
    total_spikes: number;
    total_distance_km: number;
    score: number;
  };
  heading_jitter: {
    jitter_std: number;
    straight_fraction: number;
    score: number;
  } | null;
  lateral_scatter: { scatter_p90: number; score: number };
  metric_weights: Record<string, number>;
}

// --- Degradation Types ---

export interface DegradationEvent {
  corner_number: number;
  metric: string; // "brake_fade" | "tire_degradation"
  start_lap: number;
  end_lap: number;
  slope: number;
  r_squared: number;
  severity: string; // "mild" | "moderate" | "severe"
  description: string;
  values: number[];
  lap_numbers: number[];
}

export interface DegradationData {
  session_id: string;
  events: DegradationEvent[];
  has_brake_fade: boolean;
  has_tire_degradation: boolean;
}

// --- Mini-Sector Types ---

export interface MiniSector {
  index: number;
  entry_distance_m: number;
  exit_distance_m: number;
  gps_points: [number, number][]; // (lat, lon) pairs
}

export interface MiniSectorLapData {
  lap_number: number;
  sector_times_s: number[];
  deltas_s: number[];
  classifications: string[]; // "pb" | "faster" | "slower"
}

export interface MiniSectorData {
  session_id: string;
  n_sectors: number;
  sectors: MiniSector[];
  best_sector_times_s: number[];
  best_sector_laps: number[];
  lap_data: Record<string, MiniSectorLapData>;
}

export interface WrappedHighlight {
  label: string;
  value: string;
  category: string;
}

export interface WrappedData {
  year: number;
  total_sessions: number;
  total_laps: number;
  total_distance_km: number;
  tracks_visited: string[];
  total_track_time_hours: number;
  biggest_improvement_track: string | null;
  biggest_improvement_s: number | null;
  best_consistency_score: number;
  personality: string;
  personality_description: string;
  top_corner_grade: string | null;
  highlights: WrappedHighlight[];
}

// --- Achievement Types ---

export interface Achievement {
  id: string;
  name: string;
  description: string;
  criteria_type: string;
  criteria_value: number;
  tier: string;
  icon: string;
  unlocked: boolean;
  session_id: string | null;
  unlocked_at: string | null;
}

export interface AchievementListData {
  achievements: Achievement[];
}

export interface NewAchievementsData {
  newly_unlocked: Achievement[];
}

export interface SessionEquipmentResponse {
  session_id: string;
  profile_id: string;
  profile_name: string;
  overrides: Record<string, unknown>;
  tires: TireSpec;
  brakes?: {
    compound: string | null;
    rotor_type: string | null;
    pad_temp_range: string | null;
    fluid_type: string | null;
  } | null;
  suspension?: Record<string, unknown> | null;
  conditions?: Record<string, unknown> | null;
}

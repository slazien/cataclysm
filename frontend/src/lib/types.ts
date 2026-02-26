export interface SessionSummary {
  session_id: string;
  track_name: string;
  session_date: string;
  n_laps: number;
  n_clean_laps: number;
  best_lap_time_s: number;
  top3_avg_time_s: number;
  avg_lap_time_s: number;
  consistency_score: number;
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
}

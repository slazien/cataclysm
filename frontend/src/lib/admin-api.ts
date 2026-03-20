import { fetchApi } from "./api";

export interface TrackGeometry {
  x: number[];
  y: number[];
  curvature: number[];
  lats: number[];
  lons: number[];
}

export interface TrackCorner {
  number: number;
  name: string;
  fraction: number;
  direction: "left" | "right";
  corner_type: string;
  elevation_trend?: string;
  camber?: string;
  coaching_notes?: string;
  lat?: number;
  lon?: number;
  character?: string;
}

export interface TrackEditorData {
  track_slug: string;
  track_length_m: number;
  geometry: TrackGeometry;
  corners: TrackCorner[];
}

export interface LlmRoutingStatus {
  enabled: boolean;
  source: "db" | "env" | "default";
  updated_at: string | null;
  updated_by: string | null;
}

export interface LlmKpis {
  total_calls: number;
  total_errors: number;
  error_rate: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  cost_per_call: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_tokens: number;
  total_cache_creation_tokens: number;
  latency_p50: number;
  latency_p95: number;
  latency_p99: number;
  cache_hit_rate: number;
  cache_savings_usd: number;
  daily_avg_calls: number;
  delta_cost_pct: number | null;
}

export interface LlmCostTimeseriesRow {
  date: string;
  calls: number;
  cost_usd: number;
  cost_per_call: number;
}

export interface LlmCallsByModelRow {
  provider: string;
  model: string;
  calls: number;
  cost_usd: number;
}

export interface LlmCostByTaskRow {
  task: string;
  calls: number;
  errors: number;
  error_rate: number;
  cost_usd: number;
  avg_latency_ms: number;
  top_models: string;
}

export interface LlmTaskModelCostRow {
  task: string;
  provider: string;
  model: string;
  calls: number;
  cost_usd: number;
}

export interface LlmLatencyTimeseriesRow {
  date: string;
  p50: number;
  p95: number;
  count: number;
}

export interface LlmTokenTimeseriesRow {
  date: string;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  cache_creation_tokens: number;
}

export interface LlmErrorBreakdownRow {
  error: string;
  count: number;
  last_seen: string;
}

export interface LlmDashboardData {
  window_days: number;
  kpis: LlmKpis;
  cost_timeseries: LlmCostTimeseriesRow[];
  calls_by_model: LlmCallsByModelRow[];
  cost_by_task: LlmCostByTaskRow[];
  task_model_cost_matrix: LlmTaskModelCostRow[];
  latency_timeseries: LlmLatencyTimeseriesRow[];
  token_timeseries: LlmTokenTimeseriesRow[];
  error_breakdown: LlmErrorBreakdownRow[];
}

export async function getTrackList(): Promise<{ tracks: string[] }> {
  return fetchApi("/api/admin/tracks");
}

export async function getTrackEditorData(
  slug: string,
): Promise<TrackEditorData> {
  return fetchApi(`/api/admin/tracks/${slug}/editor`);
}

export async function saveTrackCorners(
  slug: string,
  corners: TrackCorner[],
): Promise<{ saved: boolean; corner_count: number }> {
  return fetchApi(`/api/admin/tracks/${slug}/corners`, {
    method: "PUT",
    body: JSON.stringify({ corners }),
  });
}

export async function getLlmRoutingStatus(): Promise<LlmRoutingStatus> {
  return fetchApi("/api/admin/llm-routing/status");
}

export async function setLlmRoutingStatus(enabled: boolean): Promise<LlmRoutingStatus> {
  return fetchApi("/api/admin/llm-routing/status", {
    method: "PUT",
    body: JSON.stringify({ enabled }),
  });
}

export async function getLlmDashboard(days: number): Promise<LlmDashboardData> {
  return fetchApi(`/api/admin/llm-usage/dashboard?days=${days}`);
}

export interface LlmRecentEvent {
  timestamp: string;
  task: string;
  provider: string;
  model: string;
  success: boolean;
  input_tokens: number;
  output_tokens: number;
  cached_input_tokens: number;
  cache_creation_input_tokens: number;
  latency_ms: number;
  cost_usd: number;
  error: string | null;
}

export async function getLlmRecentEvents(limit = 50): Promise<LlmRecentEvent[]> {
  return fetchApi(`/api/admin/llm-usage/events?limit=${limit}`);
}

// ── Per-task routing config types ────────────────────────────────────

export interface LlmModelInfo {
  provider: string;
  model: string;
  display: string;
  cost_in: number;
  cost_out: number;
}

export interface LlmRouteEntry {
  provider: string;
  model: string;
}

export interface LlmModelsResponse {
  models: LlmModelInfo[];
  tasks: string[];
  available_providers: string[];
}

export interface LlmTaskRoutesResponse {
  task_routes: Record<string, { chain: LlmRouteEntry[] }>;
  tasks: string[];
}

export async function getLlmModels(): Promise<LlmModelsResponse> {
  return fetchApi("/api/admin/llm-routing/models");
}

export async function getLlmTaskRoutes(): Promise<LlmTaskRoutesResponse> {
  return fetchApi("/api/admin/llm-routing/tasks");
}

export async function setLlmTaskRoute(
  task: string,
  chain: LlmRouteEntry[],
): Promise<{ task: string; config: { chain: LlmRouteEntry[] } }> {
  return fetchApi(`/api/admin/llm-routing/tasks/${task}`, {
    method: "PUT",
    body: JSON.stringify({ chain }),
  });
}

export async function deleteLlmTaskRoute(
  task: string,
): Promise<{ status: string; task: string }> {
  return fetchApi(`/api/admin/llm-routing/tasks/${task}`, {
    method: "DELETE",
  });
}

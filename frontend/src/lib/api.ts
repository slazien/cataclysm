import type {
  SessionSummary,
  LapSummary,
  LapData,
  Corner,
  DeltaData,
  SessionConsistency,
  TrackFolder,
  CoachingReport,
  IdealLapData,
} from "./types";

const API_BASE = "";

export async function fetchApi<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const headers: Record<string, string> = {
    ...((options?.headers as Record<string, string>) ?? {}),
  };
  if (!options?.body || !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function uploadSessions(
  files: File[],
): Promise<{ session_ids: string[] }> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  const res = await fetch(`${API_BASE}/api/sessions/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function listSessions() {
  return fetchApi<{ items: SessionSummary[]; total: number }>("/api/sessions");
}

export async function getSession(id: string) {
  return fetchApi<SessionSummary>(`/api/sessions/${id}`);
}

export async function getSessionLaps(id: string) {
  return fetchApi<LapSummary[]>(`/api/sessions/${id}/laps`);
}

export async function getLapData(id: string, lap: number) {
  return fetchApi<LapData>(`/api/sessions/${id}/laps/${lap}/data`);
}

export async function getCorners(id: string) {
  return fetchApi<Corner[]>(`/api/sessions/${id}/corners`);
}

export async function getAllLapCorners(id: string) {
  return fetchApi<Record<string, Corner[]>>(
    `/api/sessions/${id}/corners/all-laps`,
  );
}

export async function getDelta(id: string, ref: number, comp: number) {
  return fetchApi<DeltaData>(
    `/api/sessions/${id}/delta?ref=${ref}&comp=${comp}`,
  );
}

export async function getConsistency(id: string) {
  return fetchApi<SessionConsistency>(`/api/sessions/${id}/consistency`);
}

export async function getGains(id: string) {
  return fetchApi<Record<string, unknown>>(`/api/sessions/${id}/gains`);
}

export async function getGrip(id: string) {
  return fetchApi<Record<string, unknown>>(`/api/sessions/${id}/grip`);
}

export async function deleteSession(id: string) {
  return fetchApi<{ status: string }>(`/api/sessions/${id}`, {
    method: "DELETE",
  });
}

export async function deleteAllSessions() {
  return fetchApi<{ status: string }>("/api/sessions/all/clear", {
    method: "DELETE",
  });
}

export async function listTracks() {
  return fetchApi<TrackFolder[]>("/api/tracks");
}

export async function loadTrackFolder(folder: string) {
  return fetchApi<{ session_ids: string[] }>(
    `/api/tracks/${encodeURIComponent(folder)}/load`,
    { method: "POST" },
  );
}

// --- Coaching API ---

export async function generateCoachingReport(
  sessionId: string,
  skillLevel: string = "intermediate",
) {
  return fetchApi<CoachingReport>(`/api/coaching/${sessionId}/report`, {
    method: "POST",
    body: JSON.stringify({ skill_level: skillLevel }),
  });
}

export async function getCoachingReport(sessionId: string) {
  return fetchApi<CoachingReport>(`/api/coaching/${sessionId}/report`);
}

export async function getIdealLap(sessionId: string) {
  return fetchApi<IdealLapData>(`/api/sessions/${sessionId}/ideal-lap`);
}

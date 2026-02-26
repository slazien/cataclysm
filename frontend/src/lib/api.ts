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
  TrendAnalysisResponse,
  MilestoneResponse,
  ComparisonResult,
  GPSQualityReport,
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
  onUploadProgress?: (fraction: number) => void,
): Promise<{ session_ids: string[] }> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/sessions/upload`);
    xhr.withCredentials = true;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onUploadProgress) {
        onUploadProgress(e.loaded / e.total);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else if (xhr.status === 401) {
        reject(new Error("Please sign in to upload sessions."));
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`));
      }
    };

    xhr.onerror = () => reject(new Error("Upload network error"));
    xhr.send(formData);
  });
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

// Backend returns { session_id, lap_number, corners: [...] }
export async function getCorners(id: string) {
  const resp = await fetchApi<{ corners: Corner[] }>(
    `/api/sessions/${id}/corners`,
  );
  return resp.corners;
}

// Backend returns { session_id, laps: { "1": [...], "3": [...] } }
export async function getAllLapCorners(id: string) {
  const resp = await fetchApi<{ laps: Record<string, Corner[]> }>(
    `/api/sessions/${id}/corners/all-laps`,
  );
  return resp.laps;
}

export async function getDelta(id: string, ref: number, comp: number) {
  return fetchApi<DeltaData>(
    `/api/sessions/${id}/delta?ref=${ref}&comp=${comp}`,
  );
}

// Backend returns { session_id, data: { lap_consistency, corner_consistency, track_position } }
export async function getConsistency(id: string) {
  const resp = await fetchApi<{ data: SessionConsistency }>(
    `/api/sessions/${id}/consistency`,
  );
  return resp.data;
}

// Backend returns { session_id, data: {...} }
export async function getGains(id: string) {
  const resp = await fetchApi<{ data: Record<string, unknown> }>(
    `/api/sessions/${id}/gains`,
  );
  return resp.data;
}

// Backend returns { session_id, data: {...} }
export async function getGrip(id: string) {
  const resp = await fetchApi<{ data: Record<string, unknown> }>(
    `/api/sessions/${id}/grip`,
  );
  return resp.data;
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

export async function loadTrackFolder(folder: string, limit?: number) {
  const params = limit ? `?limit=${limit}` : "";
  return fetchApi<{ session_ids: string[] }>(
    `/api/tracks/${encodeURIComponent(folder)}/load${params}`,
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

export async function downloadPdfReport(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/coaching/${sessionId}/report/pdf`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to download PDF');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `coaching-report-${sessionId.slice(0, 8)}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function getIdealLap(sessionId: string) {
  return fetchApi<IdealLapData>(`/api/sessions/${sessionId}/ideal-lap`);
}

// --- GPS Quality API ---

export async function getGPSQuality(sessionId: string) {
  const resp = await fetchApi<{ data: GPSQualityReport }>(
    `/api/sessions/${sessionId}/gps-quality`,
  );
  return resp.data;
}

// --- Trends API ---

export async function getTrends(trackName: string) {
  return fetchApi<TrendAnalysisResponse>(
    `/api/trends/${encodeURIComponent(trackName)}`,
  );
}

export async function getMilestones(trackName: string) {
  return fetchApi<MilestoneResponse>(
    `/api/trends/${encodeURIComponent(trackName)}/milestones`,
  );
}

// --- Comparison API ---

export async function getComparison(sessionId: string, otherId: string) {
  return fetchApi<ComparisonResult>(
    `/api/sessions/${sessionId}/compare/${otherId}`,
  );
}

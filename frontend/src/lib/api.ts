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
  MiniSectorData,
  DegradationData,
  OptimalComparisonData,
  GGDiagramData,
  WrappedData,
  AchievementListData,
  NewAchievementsData,
  LeaderboardData,
  KingsData,
  ShareCreateResponse,
  ShareMetadata,
  ShareComparisonResult,
  PublicSessionView,
  StudentListData,
  InviteData,
  FlagListData,
  StudentSessionsData,
  StudentFlag,
  OrgSummary,
  OrgListData,
  OrgMemberListData,
  OrgEventListData,
  OrgEvent,
  ProgressLeaderboardResponse,
  LineAnalysisData,
  TrackGuideData,
  VehicleSearchResult,
  VehicleSpec,
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
  // Test user switching: send X-Test-User-Id header when set in localStorage
  if (typeof window !== "undefined") {
    const testUserId = localStorage.getItem("testUserId");
    if (testUserId) {
      headers["X-Test-User-Id"] = testUserId;
    }
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  // 204 No Content — nothing to parse (e.g., DELETE endpoints)
  if (res.status === 204) {
    return undefined as T;
  }
  // Guard against HTML redirect responses (e.g., middleware auth redirect)
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error(`API returned non-JSON response (${contentType})`);
  }
  return res.json();
}

export async function uploadSessions(
  files: File[],
  onUploadProgress?: (fraction: number) => void,
): Promise<{ session_ids: string[]; newly_unlocked?: string[] }> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/sessions/upload`);
    xhr.withCredentials = true;
    // Test user switching for upload path
    const testUserId = localStorage.getItem("testUserId");
    if (testUserId) {
      xhr.setRequestHeader("X-Test-User-Id", testUserId);
    }

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
      } else if (xhr.status === 429) {
        try {
          const resp = JSON.parse(xhr.responseText);
          reject(new Error(resp.detail || "Rate limit exceeded. Sign in for unlimited access."));
        } catch {
          reject(new Error("Rate limit exceeded. Sign in for unlimited access."));
        }
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

// --- User Profile API ---

export async function updateUserProfile(updates: { skill_level?: string }) {
  return fetchApi<{ id: string; skill_level: string }>("/api/auth/me", {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
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

export async function getCoachingReport(sessionId: string, skillLevel?: string) {
  const params = skillLevel ? `?skill_level=${encodeURIComponent(skillLevel)}` : '';
  return fetchApi<CoachingReport>(`/api/coaching/${sessionId}/report${params}`);
}

export async function clearAndRegenerateReport(sessionId: string, skillLevel: string) {
  return fetchApi<CoachingReport>(`/api/coaching/${sessionId}/report`, {
    method: "POST",
    body: JSON.stringify({ skill_level: skillLevel, force: true }),
  });
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

// --- Mini-Sectors API ---

export async function getMiniSectors(sessionId: string, nSectors: number = 20, lap?: number) {
  const params = new URLSearchParams({ n_sectors: nSectors.toString() });
  if (lap !== undefined) params.set('lap', lap.toString());
  return fetchApi<MiniSectorData>(
    `/api/sessions/${sessionId}/mini-sectors?${params}`,
  );
}

// --- Degradation API ---

export async function getDegradation(sessionId: string) {
  return fetchApi<DegradationData>(
    `/api/sessions/${sessionId}/degradation`,
  );
}

// --- Optimal Comparison API ---

export async function getOptimalComparison(sessionId: string, profileId?: string | null) {
  // profileId is appended as a query param so the browser HTTP cache
  // treats each equipment profile as a distinct URL.  Without this,
  // Cache-Control: max-age=60 causes the browser to serve the stale
  // response from the previous profile on equipment switch.
  const url = `/api/sessions/${sessionId}/optimal-comparison`;
  return fetchApi<OptimalComparisonData>(
    profileId ? `${url}?_eq=${profileId}` : url,
  );
}

// --- GPS Quality API ---

export async function getGPSQuality(sessionId: string) {
  const resp = await fetchApi<{ data: GPSQualityReport }>(
    `/api/sessions/${sessionId}/gps-quality`,
  );
  return resp.data;
}

// --- G-G Diagram API ---

export async function getGGDiagram(sessionId: string, corner?: number) {
  const params = corner !== undefined ? `?corner=${corner}` : "";
  return fetchApi<GGDiagramData>(
    `/api/sessions/${sessionId}/gg-diagram${params}`,
  );
}

export async function getLineAnalysis(sessionId: string, laps?: number[]) {
  const params = laps?.length
    ? `?${laps.map((l) => `laps=${l}`).join("&")}`
    : "";
  return fetchApi<LineAnalysisData>(
    `/api/sessions/${sessionId}/line-analysis${params}`,
  );
}

// --- Track Guide API ---

export async function getTrackGuide(sessionId: string) {
  return fetchApi<TrackGuideData>(`/api/sessions/${sessionId}/track-guide`);
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

// --- Wrapped API ---

export async function getWrapped(year: number) {
  return fetchApi<WrappedData>(`/api/wrapped/${year}`);
}

// --- Achievements API ---

export async function getAchievements() {
  return fetchApi<AchievementListData>("/api/achievements");
}

export async function getRecentAchievements() {
  return fetchApi<NewAchievementsData>("/api/achievements/recent");
}

// --- Leaderboard API ---

export async function getCornerLeaderboard(
  trackName: string,
  cornerNumber: number,
  limit: number = 10,
  category: string = 'sector_time',
) {
  const params = new URLSearchParams({
    corner: cornerNumber.toString(),
    limit: limit.toString(),
    category,
  });
  return fetchApi<LeaderboardData>(
    `/api/leaderboards/${encodeURIComponent(trackName)}/corners?${params}`,
  );
}

export async function getCornerKings(trackName: string) {
  return fetchApi<KingsData>(
    `/api/leaderboards/${encodeURIComponent(trackName)}/kings`,
  );
}

// --- Sharing API ---

export async function createShareLink(sessionId: string) {
  return fetchApi<ShareCreateResponse>("/api/sharing/create", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function getShareMetadata(token: string) {
  return fetchApi<ShareMetadata>(`/api/sharing/${token}`);
}

export async function uploadToShare(token: string, files: File[]) {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  return fetchApi<ShareComparisonResult>(`/api/sharing/${token}/upload`, {
    method: "POST",
    body: formData,
  });
}

export async function getShareComparison(token: string) {
  return fetchApi<ShareComparisonResult>(`/api/sharing/${token}/comparison`);
}

export async function getPublicSessionView(token: string) {
  return fetchApi<PublicSessionView>(`/api/sharing/${token}/view`);
}

// --- Instructor API ---

export async function getStudents() {
  return fetchApi<StudentListData>("/api/instructor/students");
}

export async function createInvite() {
  return fetchApi<InviteData>("/api/instructor/invite", { method: "POST" });
}

export async function acceptInvite(code: string) {
  return fetchApi<{ status: string }>(`/api/instructor/accept/${encodeURIComponent(code)}`, {
    method: "POST",
  });
}

export async function removeStudent(studentId: string) {
  return fetchApi<{ status: string }>(`/api/instructor/students/${studentId}`, {
    method: "DELETE",
  });
}

export async function getStudentSessions(studentId: string) {
  return fetchApi<StudentSessionsData>(
    `/api/instructor/students/${studentId}/sessions`,
  );
}

export async function getStudentFlags(studentId: string) {
  return fetchApi<FlagListData>(
    `/api/instructor/students/${studentId}/flags`,
  );
}

export async function createStudentFlag(
  studentId: string,
  flagType: string,
  description: string,
  sessionId?: string,
) {
  return fetchApi<StudentFlag>(`/api/instructor/students/${studentId}/flags`, {
    method: "POST",
    body: JSON.stringify({
      flag_type: flagType,
      description,
      session_id: sessionId ?? null,
    }),
  });
}

// --- Organization (HPDE Club) API ---

export async function getUserOrgs() {
  return fetchApi<OrgListData>("/api/orgs");
}

export async function getOrgBySlug(slug: string) {
  return fetchApi<OrgSummary>(`/api/orgs/${encodeURIComponent(slug)}`);
}

export async function createOrg(
  name: string,
  slug: string,
  logoUrl?: string,
  brandColor?: string,
) {
  return fetchApi<OrgSummary>("/api/orgs", {
    method: "POST",
    body: JSON.stringify({
      name,
      slug,
      logo_url: logoUrl ?? null,
      brand_color: brandColor ?? null,
    }),
  });
}

export async function getOrgMembers(slug: string) {
  return fetchApi<OrgMemberListData>(
    `/api/orgs/${encodeURIComponent(slug)}/members`,
  );
}

export async function addOrgMember(
  slug: string,
  userId: string,
  role: string,
  runGroup?: string,
) {
  return fetchApi<{ status: string }>(
    `/api/orgs/${encodeURIComponent(slug)}/members`,
    {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        role,
        run_group: runGroup ?? null,
      }),
    },
  );
}

export async function removeOrgMember(slug: string, userId: string) {
  return fetchApi<{ status: string }>(
    `/api/orgs/${encodeURIComponent(slug)}/members/${userId}`,
    { method: "DELETE" },
  );
}

export async function getOrgEvents(slug: string) {
  return fetchApi<OrgEventListData>(
    `/api/orgs/${encodeURIComponent(slug)}/events`,
  );
}

export async function createOrgEvent(
  slug: string,
  name: string,
  trackName: string,
  eventDate: string,
  runGroups?: string[],
) {
  return fetchApi<OrgEvent>(
    `/api/orgs/${encodeURIComponent(slug)}/events`,
    {
      method: "POST",
      body: JSON.stringify({
        name,
        track_name: trackName,
        event_date: eventDate,
        run_groups: runGroups ?? null,
      }),
    },
  );
}

export async function deleteOrgEvent(slug: string, eventId: string) {
  return fetchApi<{ status: string }>(
    `/api/orgs/${encodeURIComponent(slug)}/events/${eventId}`,
    { method: "DELETE" },
  );
}

// --- Progress Leaderboard API ---

export async function getProgressLeaderboard(trackName: string, days = 90) {
  return fetchApi<ProgressLeaderboardResponse>(
    `/api/progress/${encodeURIComponent(trackName)}/improvement?days=${days}`,
  );
}

// --- Vehicle Search API ---

export async function searchVehicles(query: string) {
  return fetchApi<VehicleSearchResult[]>(
    `/api/equipment/vehicles/search?q=${encodeURIComponent(query)}`,
  );
}

export async function getVehicleSpec(make: string, model: string, generation?: string) {
  const params = generation ? `?generation=${encodeURIComponent(generation)}` : '';
  return fetchApi<VehicleSpec>(
    `/api/equipment/vehicles/${encodeURIComponent(make)}/${encodeURIComponent(model)}${params}`,
  );
}

// --- Session Claiming API (anonymous -> authenticated migration) ---

export async function claimSession(sessionId: string) {
  return fetchApi<{ message: string }>("/api/sessions/claim", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

// --- Notes API ---

import type { Note, NoteCreate, NoteUpdate, NotesList } from "./types";

export async function listNotes(params?: {
  session_id?: string;
  global_only?: boolean;
  anchor_type?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params?.session_id) searchParams.set("session_id", params.session_id);
  if (params?.global_only) searchParams.set("global_only", "true");
  if (params?.anchor_type) searchParams.set("anchor_type", params.anchor_type);
  const qs = searchParams.toString();
  return fetchApi<NotesList>(`/api/notes${qs ? `?${qs}` : ""}`);
}

export async function createNote(body: NoteCreate) {
  return fetchApi<Note>("/api/notes", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateNote(noteId: string, body: NoteUpdate) {
  return fetchApi<Note>(`/api/notes/${noteId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteNote(noteId: string) {
  return fetchApi<void>(`/api/notes/${noteId}`, { method: "DELETE" });
}

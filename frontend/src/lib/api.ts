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
  WrappedData,
  AchievementListData,
  NewAchievementsData,
  LeaderboardData,
  KingsData,
  OptInResponse,
  ShareCreateResponse,
  ShareMetadata,
  ShareComparisonResult,
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
) {
  const params = new URLSearchParams({
    corner: cornerNumber.toString(),
    limit: limit.toString(),
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

export async function toggleLeaderboardOptIn(optIn: boolean) {
  return fetchApi<OptInResponse>("/api/leaderboards/opt-in", {
    method: "POST",
    body: JSON.stringify({ opt_in: optIn }),
  });
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

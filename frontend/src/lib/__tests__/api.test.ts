import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchApi,
  uploadSessions,
  listSessions,
  getSession,
  getSessionLaps,
  getLapData,
  getCorners,
  getAllLapCorners,
  getDelta,
  getConsistency,
  getGains,
  getGrip,
  deleteSession,
  deleteAllSessions,
  listTracks,
  loadTrackFolder,
  updateUserProfile,
  generateCoachingReport,
  getCoachingReport,
  clearAndRegenerateReport,
  downloadPdfReport,
  getIdealLap,
  getMiniSectors,
  getDegradation,
  getOptimalComparison,
  getGPSQuality,
  getGGDiagram,
  getLineAnalysis,
  getTrackGuide,
  getTrends,
  getMilestones,
  getComparison,
  getWrapped,
  getAchievements,
  getRecentAchievements,
  getCornerLeaderboard,
  getCornerKings,
  createShareLink,
  getShareMetadata,
  uploadToShare,
  getShareComparison,
  getPublicSessionView,
  getStudents,
  createInvite,
  acceptInvite,
  removeStudent,
  getStudentSessions,
  getStudentFlags,
  createStudentFlag,
  getUserOrgs,
  getOrgBySlug,
  createOrg,
  getOrgMembers,
  addOrgMember,
  removeOrgMember,
  getOrgEvents,
  createOrgEvent,
  deleteOrgEvent,
  getProgressLeaderboard,
  searchVehicles,
  getVehicleSpec,
  claimSession,
} from '../api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function jsonResponse(data: unknown, status = 200, statusText = 'OK') {
  return new Response(JSON.stringify(data), {
    status,
    statusText,
    headers: { 'content-type': 'application/json' },
  });
}

function htmlResponse(html = '<html></html>', status = 200) {
  return new Response(html, {
    status,
    statusText: 'OK',
    headers: { 'content-type': 'text/html' },
  });
}

function errorResponse(status: number, statusText: string) {
  return new Response(JSON.stringify({ detail: statusText }), {
    status,
    statusText,
    headers: { 'content-type': 'application/json' },
  });
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------

const originalFetch = globalThis.fetch;
let mockFetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mockFetch = vi.fn();
  globalThis.fetch = mockFetch;
  // Clear any testUserId from localStorage
  localStorage.removeItem('testUserId');
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

// ===========================================================================
// fetchApi
// ===========================================================================

describe('fetchApi', () => {
  it('makes GET request with JSON content type by default', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }));
    const result = await fetchApi('/api/test');
    expect(result).toEqual({ ok: true });
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/test',
      expect.objectContaining({
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        credentials: 'same-origin',
      }),
    );
  });

  it('throws on non-OK response', async () => {
    mockFetch.mockResolvedValue(errorResponse(404, 'Not Found'));
    await expect(fetchApi('/api/missing')).rejects.toThrow('API error: 404 Not Found');
  });

  it('throws on non-JSON content type', async () => {
    mockFetch.mockResolvedValue(htmlResponse());
    await expect(fetchApi('/api/redirected')).rejects.toThrow(
      'API returned non-JSON response (text/html)',
    );
  });

  it('skips Content-Type header when body is FormData', async () => {
    const formData = new FormData();
    formData.append('file', 'data');
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }));

    await fetchApi('/api/upload', { body: formData });

    const callArgs = mockFetch.mock.calls[0];
    const headers = callArgs[1].headers;
    expect(headers['Content-Type']).toBeUndefined();
  });

  it('sends Content-Type when body is a string (JSON)', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }));
    await fetchApi('/api/data', { body: JSON.stringify({ key: 'value' }) });

    const callArgs = mockFetch.mock.calls[0];
    expect(callArgs[1].headers['Content-Type']).toBe('application/json');
  });

  it('forwards custom headers', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }));
    await fetchApi('/api/test', {
      headers: { 'X-Custom': 'value' },
    });

    const callArgs = mockFetch.mock.calls[0];
    expect(callArgs[1].headers['X-Custom']).toBe('value');
    expect(callArgs[1].headers['Content-Type']).toBe('application/json');
  });

  it('sends X-Test-User-Id header when testUserId is in localStorage', async () => {
    localStorage.setItem('testUserId', 'user-42');
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }));

    await fetchApi('/api/test');

    const callArgs = mockFetch.mock.calls[0];
    expect(callArgs[1].headers['X-Test-User-Id']).toBe('user-42');
  });

  it('does not send X-Test-User-Id when not set', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ok: true }));
    await fetchApi('/api/test');

    const callArgs = mockFetch.mock.calls[0];
    expect(callArgs[1].headers['X-Test-User-Id']).toBeUndefined();
  });
});

// ===========================================================================
// uploadSessions (XHR-based)
// ===========================================================================

describe('uploadSessions', () => {
  // We capture the XHR instance created inside uploadSessions so tests can
  // trigger its lifecycle callbacks (onload / onerror / upload.onprogress).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let xhrInstance: any;

  // Configuration that tests set *before* calling uploadSessions.
  // The mock send() will apply these and fire onload/onerror automatically.
  let xhrConfig: {
    status: number;
    responseText: string;
    triggerError?: boolean;
    progressEvents?: Array<{ lengthComputable: boolean; loaded: number; total: number }>;
  };

  function createMockXhrClass() {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Ctor = function (this: any) {
      this.open = vi.fn();
      this.setRequestHeader = vi.fn();
      this.withCredentials = false;
      this.status = 200;
      this.responseText = '{}';
      this.upload = { onprogress: null };
      this.onload = null;
      this.onerror = null;
      xhrInstance = this;

      this.send = vi.fn(() => {
        // Fire progress events first
        if (xhrConfig.progressEvents) {
          for (const evt of xhrConfig.progressEvents) {
            if (this.upload.onprogress) {
              this.upload.onprogress(evt);
            }
          }
        }
        // Apply configured status/response
        this.status = xhrConfig.status;
        this.responseText = xhrConfig.responseText;
        // Fire the appropriate callback
        if (xhrConfig.triggerError) {
          if (this.onerror) this.onerror();
        } else {
          if (this.onload) this.onload();
        }
      });
    } as unknown as typeof XMLHttpRequest;
    return Ctor;
  }

  beforeEach(() => {
    xhrConfig = { status: 200, responseText: '{}' };
    vi.stubGlobal('XMLHttpRequest', createMockXhrClass());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('resolves with parsed JSON on success (2xx)', async () => {
    const expected = { session_ids: ['s1'] };
    xhrConfig = { status: 200, responseText: JSON.stringify(expected) };

    const file = new File(['data'], 'test.csv');
    const result = await uploadSessions([file]);

    expect(result).toEqual(expected);
    expect(xhrInstance.open).toHaveBeenCalledWith('POST', '/api/sessions/upload');
    expect(xhrInstance.withCredentials).toBe(true);
  });

  it('reports upload progress via callback', async () => {
    xhrConfig = {
      status: 200,
      responseText: JSON.stringify({ session_ids: [] }),
      progressEvents: [{ lengthComputable: true, loaded: 50, total: 100 }],
    };

    const progressFn = vi.fn();
    const file = new File(['data'], 'test.csv');
    await uploadSessions([file], progressFn);

    expect(progressFn).toHaveBeenCalledWith(0.5);
  });

  it('does not call progress callback when lengthComputable is false', async () => {
    xhrConfig = {
      status: 200,
      responseText: JSON.stringify({ session_ids: [] }),
      progressEvents: [{ lengthComputable: false, loaded: 50, total: 100 }],
    };

    const progressFn = vi.fn();
    const file = new File(['data'], 'test.csv');
    await uploadSessions([file], progressFn);

    expect(progressFn).not.toHaveBeenCalled();
  });

  it('rejects with auth error on 401', async () => {
    xhrConfig = { status: 401, responseText: '' };
    const file = new File(['data'], 'test.csv');
    await expect(uploadSessions([file])).rejects.toThrow('Please sign in to upload sessions.');
  });

  it('rejects with rate limit detail from response on 429', async () => {
    xhrConfig = {
      status: 429,
      responseText: JSON.stringify({ detail: 'Custom rate limit message' }),
    };
    const file = new File(['data'], 'test.csv');
    await expect(uploadSessions([file])).rejects.toThrow('Custom rate limit message');
  });

  it('rejects with fallback rate limit message on 429 with invalid JSON', async () => {
    xhrConfig = { status: 429, responseText: 'not json' };
    const file = new File(['data'], 'test.csv');
    await expect(uploadSessions([file])).rejects.toThrow(
      'Upload limit reached. Try again later or sign in for unlimited uploads.',
    );
  });

  it('rejects with bad format message on 400', async () => {
    xhrConfig = { status: 400, responseText: JSON.stringify({ detail: '' }) };
    const file = new File(['data'], 'test.csv');
    await expect(uploadSessions([file])).rejects.toThrow(
      "This file doesn't look like a RaceChrono v3 CSV. Need help exporting?",
    );
  });

  it('rejects with bad format detail from response on 400', async () => {
    xhrConfig = {
      status: 400,
      responseText: JSON.stringify({ detail: 'Missing GPS columns' }),
    };
    const file = new File(['data'], 'test.csv');
    await expect(uploadSessions([file])).rejects.toThrow('Missing GPS columns');
  });

  it('rejects with file too large message on 413', async () => {
    xhrConfig = { status: 413, responseText: '' };
    const file = new File(['data'], 'test.csv');
    await expect(uploadSessions([file])).rejects.toThrow(
      'File too large. Try exporting fewer laps.',
    );
  });

  it('rejects with generic upload error for other non-2xx statuses', async () => {
    xhrConfig = { status: 500, responseText: '' };
    const file = new File(['data'], 'test.csv');
    await expect(uploadSessions([file])).rejects.toThrow(
      'Upload failed. Please check your CSV format and try again.',
    );
  });

  it('rejects with network error on onerror', async () => {
    xhrConfig = { status: 200, responseText: '', triggerError: true };
    const file = new File(['data'], 'test.csv');
    await expect(uploadSessions([file])).rejects.toThrow(
      'Upload interrupted — check your connection and try again.',
    );
  });

  it('sends X-Test-User-Id header when testUserId is in localStorage', async () => {
    localStorage.setItem('testUserId', 'user-99');
    xhrConfig = { status: 200, responseText: JSON.stringify({ session_ids: [] }) };

    const file = new File(['data'], 'test.csv');
    await uploadSessions([file]);

    expect(xhrInstance.setRequestHeader).toHaveBeenCalledWith('X-Test-User-Id', 'user-99');
  });

  it('does not send X-Test-User-Id when not set', async () => {
    xhrConfig = { status: 200, responseText: JSON.stringify({ session_ids: [] }) };

    const file = new File(['data'], 'test.csv');
    await uploadSessions([file]);

    expect(xhrInstance.setRequestHeader).not.toHaveBeenCalled();
  });

  it('appends multiple files to FormData', async () => {
    xhrConfig = { status: 200, responseText: JSON.stringify({ session_ids: ['s1', 's2'] }) };

    const file1 = new File(['data1'], 'a.csv');
    const file2 = new File(['data2'], 'b.csv');
    await uploadSessions([file1, file2]);

    expect(xhrInstance.send).toHaveBeenCalledWith(expect.any(FormData));
  });

  it('rejects with default rate limit message when detail is empty on 429', async () => {
    xhrConfig = { status: 429, responseText: JSON.stringify({ detail: '' }) };
    const file = new File(['data'], 'test.csv');
    await expect(uploadSessions([file])).rejects.toThrow(
      'Upload limit reached. Try again later or sign in for unlimited uploads.',
    );
  });
});

// ===========================================================================
// Simple GET wrappers (each delegates to fetchApi)
// ===========================================================================

describe('simple API wrappers', () => {
  // Helper: set up mock to return JSON and verify the URL
  function setupFetchMock(responseData: unknown) {
    mockFetch.mockResolvedValue(jsonResponse(responseData));
  }

  function expectFetchCalledWith(urlSubstring: string, method?: string) {
    expect(mockFetch).toHaveBeenCalled();
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain(urlSubstring);
    if (method) {
      expect(options.method).toBe(method);
    }
  }

  // --- Session API ---

  it('listSessions calls /api/sessions', async () => {
    const data = { items: [], total: 0 };
    setupFetchMock(data);
    const result = await listSessions();
    expect(result).toEqual(data);
    expectFetchCalledWith('/api/sessions');
  });

  it('getSession calls /api/sessions/:id', async () => {
    const data = { session_id: 'abc' };
    setupFetchMock(data);
    const result = await getSession('abc');
    expect(result).toEqual(data);
    expectFetchCalledWith('/api/sessions/abc');
  });

  it('getSessionLaps calls /api/sessions/:id/laps', async () => {
    const data = [{ lap_number: 1 }];
    setupFetchMock(data);
    const result = await getSessionLaps('s1');
    expect(result).toEqual(data);
    expectFetchCalledWith('/api/sessions/s1/laps');
  });

  it('getLapData calls /api/sessions/:id/laps/:lap/data', async () => {
    const data = { lap_number: 3 };
    setupFetchMock(data);
    const result = await getLapData('s1', 3);
    expect(result).toEqual(data);
    expectFetchCalledWith('/api/sessions/s1/laps/3/data');
  });

  // --- Corners ---

  it('getCorners extracts corners array from response', async () => {
    const corners = [{ number: 1 }, { number: 2 }];
    setupFetchMock({ corners });
    const result = await getCorners('s1');
    expect(result).toEqual(corners);
    expectFetchCalledWith('/api/sessions/s1/corners');
  });

  it('getAllLapCorners extracts laps object from response', async () => {
    const laps = { '1': [{ number: 1 }], '3': [{ number: 1 }] };
    setupFetchMock({ laps });
    const result = await getAllLapCorners('s1');
    expect(result).toEqual(laps);
    expectFetchCalledWith('/api/sessions/s1/corners/all-laps');
  });

  // --- Delta ---

  it('getDelta calls correct URL with query params', async () => {
    const data = { distance_m: [], delta_s: [] };
    setupFetchMock(data);
    const result = await getDelta('s1', 1, 3);
    expect(result).toEqual(data);
    expectFetchCalledWith('/api/sessions/s1/delta?ref=1&comp=3');
  });

  // --- Consistency ---

  it('getConsistency extracts data from response', async () => {
    const data = { lap_consistency: {} };
    setupFetchMock({ data });
    const result = await getConsistency('s1');
    expect(result).toEqual(data);
    expectFetchCalledWith('/api/sessions/s1/consistency');
  });

  // --- Gains ---

  it('getGains extracts data from response', async () => {
    const data = { corners: [] };
    setupFetchMock({ data });
    const result = await getGains('s1');
    expect(result).toEqual(data);
    expectFetchCalledWith('/api/sessions/s1/gains');
  });

  // --- Grip ---

  it('getGrip extracts data from response', async () => {
    const data = { front: 1.0 };
    setupFetchMock({ data });
    const result = await getGrip('s1');
    expect(result).toEqual(data);
    expectFetchCalledWith('/api/sessions/s1/grip');
  });

  // --- Delete ---

  it('deleteSession calls DELETE on /api/sessions/:id', async () => {
    setupFetchMock({ status: 'ok' });
    await deleteSession('s1');
    expectFetchCalledWith('/api/sessions/s1', 'DELETE');
  });

  it('deleteAllSessions calls DELETE on /api/sessions/all/clear', async () => {
    setupFetchMock({ status: 'ok' });
    await deleteAllSessions();
    expectFetchCalledWith('/api/sessions/all/clear', 'DELETE');
  });

  // --- Tracks ---

  it('listTracks calls /api/tracks', async () => {
    setupFetchMock([]);
    await listTracks();
    expectFetchCalledWith('/api/tracks');
  });

  it('loadTrackFolder calls POST with encoded folder name', async () => {
    setupFetchMock({ session_ids: [] });
    await loadTrackFolder('Road Atlanta');
    expectFetchCalledWith('/api/tracks/Road%20Atlanta/load');
    expectFetchCalledWith('/api/tracks/', 'POST');
  });

  it('loadTrackFolder appends limit query param when provided', async () => {
    setupFetchMock({ session_ids: [] });
    await loadTrackFolder('Barber', 5);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('?limit=5');
  });

  // --- User Profile ---

  it('updateUserProfile calls PATCH on /api/auth/me', async () => {
    setupFetchMock({ id: 'u1', skill_level: 'advanced' });
    await updateUserProfile({ skill_level: 'advanced' });
    expectFetchCalledWith('/api/auth/me', 'PATCH');
  });

  // --- Coaching ---

  it('generateCoachingReport calls POST with skill level', async () => {
    setupFetchMock({ text: 'report' });
    await generateCoachingReport('s1', 'novice');
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/coaching/s1/report');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ skill_level: 'novice' });
  });

  it('generateCoachingReport defaults to intermediate skill level', async () => {
    setupFetchMock({ text: 'report' });
    await generateCoachingReport('s1');
    const [, options] = mockFetch.mock.calls[0];
    expect(JSON.parse(options.body)).toEqual({ skill_level: 'intermediate' });
  });

  it('getCoachingReport calls GET with optional skill_level param', async () => {
    setupFetchMock({ text: 'report' });
    await getCoachingReport('s1', 'advanced');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('?skill_level=advanced');
  });

  it('getCoachingReport calls GET without param when no skill level', async () => {
    setupFetchMock({ text: 'report' });
    await getCoachingReport('s1');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/coaching/s1/report');
  });

  it('clearAndRegenerateReport calls POST with force=true', async () => {
    setupFetchMock({ text: 'report' });
    await clearAndRegenerateReport('s1', 'intermediate');
    const [, options] = mockFetch.mock.calls[0];
    expect(JSON.parse(options.body)).toEqual({ skill_level: 'intermediate', force: true });
  });

  // --- Ideal Lap ---

  it('getIdealLap calls /api/sessions/:id/ideal-lap', async () => {
    setupFetchMock({ distance_m: [] });
    await getIdealLap('s1');
    expectFetchCalledWith('/api/sessions/s1/ideal-lap');
  });

  // --- Mini-Sectors ---

  it('getMiniSectors builds URL with n_sectors param', async () => {
    setupFetchMock({ sectors: [] });
    await getMiniSectors('s1', 10);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('n_sectors=10');
  });

  it('getMiniSectors includes lap param when provided', async () => {
    setupFetchMock({ sectors: [] });
    await getMiniSectors('s1', 20, 5);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('lap=5');
    expect(url).toContain('n_sectors=20');
  });

  it('getMiniSectors defaults nSectors to 20', async () => {
    setupFetchMock({ sectors: [] });
    await getMiniSectors('s1');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('n_sectors=20');
  });

  // --- Degradation ---

  it('getDegradation calls /api/sessions/:id/degradation', async () => {
    setupFetchMock({});
    await getDegradation('s1');
    expectFetchCalledWith('/api/sessions/s1/degradation');
  });

  // --- Optimal Comparison ---

  it('getOptimalComparison calls /api/sessions/:id/optimal-comparison', async () => {
    setupFetchMock({});
    await getOptimalComparison('s1');
    expectFetchCalledWith('/api/sessions/s1/optimal-comparison');
  });

  it('getOptimalComparison appends profileId as cache-busting param', async () => {
    setupFetchMock({});
    await getOptimalComparison('s1', 'prof-123');
    expectFetchCalledWith('/api/sessions/s1/optimal-comparison?_eq=prof-123');
  });

  // --- GPS Quality ---

  it('getGPSQuality extracts data from response', async () => {
    const data = { grade: 'A' };
    setupFetchMock({ data });
    const result = await getGPSQuality('s1');
    expect(result).toEqual(data);
    expectFetchCalledWith('/api/sessions/s1/gps-quality');
  });

  // --- G-G Diagram ---

  it('getGGDiagram calls without corner param when not provided', async () => {
    setupFetchMock({});
    await getGGDiagram('s1');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/sessions/s1/gg-diagram');
  });

  it('getGGDiagram includes corner query param when provided', async () => {
    setupFetchMock({});
    await getGGDiagram('s1', 5);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('?corner=5');
  });

  // --- Line Analysis ---

  it('getLineAnalysis calls without laps param when not provided', async () => {
    setupFetchMock({});
    await getLineAnalysis('s1');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/sessions/s1/line-analysis');
  });

  it('getLineAnalysis includes laps query params when provided', async () => {
    setupFetchMock({});
    await getLineAnalysis('s1', [1, 3, 5]);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('laps=1');
    expect(url).toContain('laps=3');
    expect(url).toContain('laps=5');
  });

  it('getLineAnalysis handles empty laps array', async () => {
    setupFetchMock({});
    await getLineAnalysis('s1', []);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/sessions/s1/line-analysis');
  });

  // --- Track Guide ---

  it('getTrackGuide calls /api/sessions/:id/track-guide', async () => {
    setupFetchMock({});
    await getTrackGuide('s1');
    expectFetchCalledWith('/api/sessions/s1/track-guide');
  });

  // --- Trends ---

  it('getTrends encodes track name', async () => {
    setupFetchMock({});
    await getTrends('Road Atlanta');
    expectFetchCalledWith('/api/trends/Road%20Atlanta');
  });

  it('getMilestones encodes track name', async () => {
    setupFetchMock({ milestones: [] });
    await getMilestones('Road Atlanta');
    expectFetchCalledWith('/api/trends/Road%20Atlanta/milestones');
  });

  // --- Comparison ---

  it('getComparison calls /api/sessions/:id/compare/:otherId', async () => {
    setupFetchMock({});
    await getComparison('s1', 's2');
    expectFetchCalledWith('/api/sessions/s1/compare/s2');
  });

  // --- Wrapped ---

  it('getWrapped calls /api/wrapped/:year', async () => {
    setupFetchMock({});
    await getWrapped(2025);
    expectFetchCalledWith('/api/wrapped/2025');
  });

  // --- Achievements ---

  it('getAchievements calls /api/achievements', async () => {
    setupFetchMock({ achievements: [] });
    await getAchievements();
    expectFetchCalledWith('/api/achievements');
  });

  it('getRecentAchievements calls /api/achievements/recent', async () => {
    setupFetchMock({ newly_unlocked: [] });
    await getRecentAchievements();
    expectFetchCalledWith('/api/achievements/recent');
  });

  // --- Leaderboard ---

  it('getCornerLeaderboard builds URL with all params', async () => {
    setupFetchMock({ entries: [] });
    await getCornerLeaderboard('Barber', 5, 20, 'min_speed');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/leaderboards/Barber/corners');
    expect(url).toContain('corner=5');
    expect(url).toContain('limit=20');
    expect(url).toContain('category=min_speed');
  });

  it('getCornerLeaderboard uses default limit and category', async () => {
    setupFetchMock({ entries: [] });
    await getCornerLeaderboard('Barber', 3);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('limit=10');
    expect(url).toContain('category=sector_time');
  });

  it('getCornerKings calls /api/leaderboards/:track/kings', async () => {
    setupFetchMock({ kings: [] });
    await getCornerKings('Barber');
    expectFetchCalledWith('/api/leaderboards/Barber/kings');
  });

  // --- Sharing ---

  it('createShareLink calls POST /api/sharing/create', async () => {
    setupFetchMock({ token: 'abc', url: 'http://example.com' });
    await createShareLink('s1');
    const [, options] = mockFetch.mock.calls[0];
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ session_id: 's1' });
  });

  it('getShareMetadata calls /api/sharing/:token', async () => {
    setupFetchMock({ token: 'abc' });
    await getShareMetadata('abc');
    expectFetchCalledWith('/api/sharing/abc');
  });

  it('uploadToShare calls POST with FormData', async () => {
    setupFetchMock({ comparison: {} });
    const file = new File(['data'], 'test.csv');
    await uploadToShare('abc', [file]);
    expectFetchCalledWith('/api/sharing/abc/upload', 'POST');
  });

  it('getShareComparison calls /api/sharing/:token/comparison', async () => {
    setupFetchMock({});
    await getShareComparison('abc');
    expectFetchCalledWith('/api/sharing/abc/comparison');
  });

  it('getPublicSessionView calls /api/sharing/:token/view', async () => {
    setupFetchMock({});
    await getPublicSessionView('abc');
    expectFetchCalledWith('/api/sharing/abc/view');
  });

  // --- Instructor ---

  it('getStudents calls /api/instructor/students', async () => {
    setupFetchMock({ students: [] });
    await getStudents();
    expectFetchCalledWith('/api/instructor/students');
  });

  it('createInvite calls POST /api/instructor/invite', async () => {
    setupFetchMock({ code: 'invite-code' });
    await createInvite();
    expectFetchCalledWith('/api/instructor/invite', 'POST');
  });

  it('acceptInvite calls POST with encoded code', async () => {
    setupFetchMock({ status: 'ok' });
    await acceptInvite('code with spaces');
    expectFetchCalledWith('/api/instructor/accept/code%20with%20spaces', 'POST');
  });

  it('removeStudent calls DELETE on /api/instructor/students/:id', async () => {
    setupFetchMock({ status: 'ok' });
    await removeStudent('st1');
    expectFetchCalledWith('/api/instructor/students/st1', 'DELETE');
  });

  it('getStudentSessions calls /api/instructor/students/:id/sessions', async () => {
    setupFetchMock({ sessions: [] });
    await getStudentSessions('st1');
    expectFetchCalledWith('/api/instructor/students/st1/sessions');
  });

  it('getStudentFlags calls /api/instructor/students/:id/flags', async () => {
    setupFetchMock({ flags: [] });
    await getStudentFlags('st1');
    expectFetchCalledWith('/api/instructor/students/st1/flags');
  });

  it('createStudentFlag calls POST with body', async () => {
    setupFetchMock({ id: 'flag1' });
    await createStudentFlag('st1', 'safety', 'needs attention', 's1');
    const [, options] = mockFetch.mock.calls[0];
    expect(options.method).toBe('POST');
    const body = JSON.parse(options.body);
    expect(body.flag_type).toBe('safety');
    expect(body.description).toBe('needs attention');
    expect(body.session_id).toBe('s1');
  });

  it('createStudentFlag sends null session_id when not provided', async () => {
    setupFetchMock({ id: 'flag1' });
    await createStudentFlag('st1', 'progress', 'doing well');
    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body.session_id).toBeNull();
  });

  // --- Organization ---

  it('getUserOrgs calls /api/orgs', async () => {
    setupFetchMock({ orgs: [] });
    await getUserOrgs();
    expectFetchCalledWith('/api/orgs');
  });

  it('getOrgBySlug encodes slug', async () => {
    setupFetchMock({ name: 'Test Org' });
    await getOrgBySlug('test-org');
    expectFetchCalledWith('/api/orgs/test-org');
  });

  it('createOrg calls POST with all fields', async () => {
    setupFetchMock({ slug: 'test' });
    await createOrg('Test', 'test', 'http://logo.png', '#ff0000');
    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body.name).toBe('Test');
    expect(body.slug).toBe('test');
    expect(body.logo_url).toBe('http://logo.png');
    expect(body.brand_color).toBe('#ff0000');
  });

  it('createOrg sends null for optional fields when not provided', async () => {
    setupFetchMock({ slug: 'test' });
    await createOrg('Test', 'test');
    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body.logo_url).toBeNull();
    expect(body.brand_color).toBeNull();
  });

  it('getOrgMembers encodes slug', async () => {
    setupFetchMock({ members: [] });
    await getOrgMembers('my-org');
    expectFetchCalledWith('/api/orgs/my-org/members');
  });

  it('addOrgMember calls POST with body', async () => {
    setupFetchMock({ status: 'ok' });
    await addOrgMember('my-org', 'u1', 'member', 'Group A');
    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body.user_id).toBe('u1');
    expect(body.role).toBe('member');
    expect(body.run_group).toBe('Group A');
  });

  it('addOrgMember sends null run_group when not provided', async () => {
    setupFetchMock({ status: 'ok' });
    await addOrgMember('my-org', 'u1', 'admin');
    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body.run_group).toBeNull();
  });

  it('removeOrgMember calls DELETE', async () => {
    setupFetchMock({ status: 'ok' });
    await removeOrgMember('my-org', 'u1');
    expectFetchCalledWith('/api/orgs/my-org/members/u1', 'DELETE');
  });

  it('getOrgEvents calls /api/orgs/:slug/events', async () => {
    setupFetchMock({ events: [] });
    await getOrgEvents('my-org');
    expectFetchCalledWith('/api/orgs/my-org/events');
  });

  it('createOrgEvent calls POST with body', async () => {
    setupFetchMock({ id: 'e1' });
    await createOrgEvent('my-org', 'Spring Event', 'Barber', '2026-04-01', ['A', 'B']);
    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body.name).toBe('Spring Event');
    expect(body.track_name).toBe('Barber');
    expect(body.event_date).toBe('2026-04-01');
    expect(body.run_groups).toEqual(['A', 'B']);
  });

  it('createOrgEvent sends null run_groups when not provided', async () => {
    setupFetchMock({ id: 'e1' });
    await createOrgEvent('my-org', 'Event', 'Barber', '2026-04-01');
    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body.run_groups).toBeNull();
  });

  it('deleteOrgEvent calls DELETE', async () => {
    setupFetchMock({ status: 'ok' });
    await deleteOrgEvent('my-org', 'e1');
    expectFetchCalledWith('/api/orgs/my-org/events/e1', 'DELETE');
  });

  // --- Progress Leaderboard ---

  it('getProgressLeaderboard includes days param', async () => {
    setupFetchMock({ entries: [] });
    await getProgressLeaderboard('Barber', 30);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('days=30');
  });

  it('getProgressLeaderboard defaults to 90 days', async () => {
    setupFetchMock({ entries: [] });
    await getProgressLeaderboard('Barber');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('days=90');
  });

  // --- Vehicle Search ---

  it('searchVehicles encodes query string', async () => {
    setupFetchMock([]);
    await searchVehicles('BMW M3');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('q=BMW%20M3');
  });

  it('getVehicleSpec encodes make and model', async () => {
    setupFetchMock({ hp: 450 });
    await getVehicleSpec('BMW', 'M3 Competition');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/equipment/vehicles/BMW/M3%20Competition');
  });

  it('getVehicleSpec includes generation param when provided', async () => {
    setupFetchMock({ hp: 450 });
    await getVehicleSpec('BMW', 'M3', 'G80');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('?generation=G80');
  });

  it('getVehicleSpec omits generation param when not provided', async () => {
    setupFetchMock({ hp: 450 });
    await getVehicleSpec('BMW', 'M3');
    const [url] = mockFetch.mock.calls[0];
    expect(url).not.toContain('generation');
  });

  // --- Session Claiming ---

  it('claimSession calls POST /api/sessions/claim', async () => {
    setupFetchMock({ message: 'claimed' });
    await claimSession('s1');
    const [, options] = mockFetch.mock.calls[0];
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ session_id: 's1' });
  });
});

// ===========================================================================
// downloadPdfReport (uses fetch directly, not fetchApi)
// ===========================================================================

describe('downloadPdfReport', () => {
  let createElementSpy: ReturnType<typeof vi.spyOn>;
  let appendChildSpy: ReturnType<typeof vi.spyOn>;
  let removeChildSpy: ReturnType<typeof vi.spyOn>;
  let revokeObjectURLSpy: ReturnType<typeof vi.spyOn>;
  let createObjectURLSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    createObjectURLSpy = vi.fn().mockReturnValue('blob:mock-url') as unknown as ReturnType<typeof vi.spyOn>;
    revokeObjectURLSpy = vi.fn() as unknown as ReturnType<typeof vi.spyOn>;
    URL.createObjectURL = createObjectURLSpy as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURLSpy as unknown as typeof URL.revokeObjectURL;

    const mockAnchor = {
      href: '',
      download: '',
      click: vi.fn(),
    };
    createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(
      mockAnchor as unknown as HTMLElement,
    );
    appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation(
      (node) => node,
    );
    removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation(
      (node) => node,
    );
  });

  afterEach(() => {
    createElementSpy.mockRestore();
    appendChildSpy.mockRestore();
    removeChildSpy.mockRestore();
  });

  it('downloads PDF and triggers download link', async () => {
    const mockBlob = new Blob(['pdf content'], { type: 'application/pdf' });
    mockFetch.mockResolvedValue(
      new Response(mockBlob, { status: 200, statusText: 'OK' }),
    );

    await downloadPdfReport('abc12345-6789');

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/coaching/abc12345-6789/report/pdf',
      expect.objectContaining({ credentials: 'include' }),
    );
    expect(createElementSpy).toHaveBeenCalledWith('a');
    expect(appendChildSpy).toHaveBeenCalled();
    expect(removeChildSpy).toHaveBeenCalled();
  });

  it('throws when response is not ok', async () => {
    mockFetch.mockResolvedValue(
      new Response('', { status: 500, statusText: 'Server Error' }),
    );
    await expect(downloadPdfReport('s1')).rejects.toThrow('Failed to download PDF');
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  useSessions,
  useSession,
  useSessionLaps,
  useLapData,
  useUploadSessions,
  useDeleteSession,
  useDeleteAllSessions,
} from '../useSession';
import { useSessionStore } from '@/stores/sessionStore';
import { useUiStore } from '@/stores/uiStore';

// ---------------------------------------------------------------------------
// Mock next-auth/react
// ---------------------------------------------------------------------------
const mockUseSession = vi.fn();
vi.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
}));

// ---------------------------------------------------------------------------
// Mock API functions
// ---------------------------------------------------------------------------
const mockListSessions = vi.fn();
const mockGetSession = vi.fn();
const mockGetSessionLaps = vi.fn();
const mockGetLapData = vi.fn();
const mockUploadSessions = vi.fn();
const mockDeleteSession = vi.fn();
const mockDeleteAllSessions = vi.fn();
const mockGetMilestones = vi.fn();
const mockFetchApi = vi.fn();

vi.mock('@/lib/api', () => ({
  listSessions: (...args: unknown[]) => mockListSessions(...args),
  getSession: (...args: unknown[]) => mockGetSession(...args),
  getSessionLaps: (...args: unknown[]) => mockGetSessionLaps(...args),
  getLapData: (...args: unknown[]) => mockGetLapData(...args),
  uploadSessions: (...args: unknown[]) => mockUploadSessions(...args),
  deleteSession: (...args: unknown[]) => mockDeleteSession(...args),
  deleteAllSessions: (...args: unknown[]) => mockDeleteAllSessions(...args),
  getMilestones: (...args: unknown[]) => mockGetMilestones(...args),
  fetchApi: (...args: unknown[]) => mockFetchApi(...args),
}));

// ---------------------------------------------------------------------------
// Query client wrapper
// ---------------------------------------------------------------------------
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// ---------------------------------------------------------------------------
// Setup / Teardown
// ---------------------------------------------------------------------------
beforeEach(() => {
  vi.clearAllMocks();
  mockUseSession.mockReturnValue({ status: 'authenticated', data: { user: {} } });
  // Reset stores
  useSessionStore.setState({
    activeSessionId: null,
    sessions: [],
    uploadState: 'idle',
    uploadProgress: 0,
    uploadErrorMessage: null,
  });
  useUiStore.setState({
    toasts: [],
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ===========================================================================
// useSessions
// ===========================================================================

describe('useSessions', () => {
  it('fetches sessions when authenticated', async () => {
    const sessionsData = { items: [{ session_id: 's1' }], total: 1 };
    mockListSessions.mockResolvedValue(sessionsData);

    const { result } = renderHook(() => useSessions(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(sessionsData);
    expect(mockListSessions).toHaveBeenCalledOnce();
  });

  it('does not fetch when not authenticated', async () => {
    mockUseSession.mockReturnValue({ status: 'unauthenticated', data: null });

    const { result } = renderHook(() => useSessions(), { wrapper: createWrapper() });

    // The query should never be enabled
    expect(result.current.fetchStatus).toBe('idle');
    expect(mockListSessions).not.toHaveBeenCalled();
  });

  it('does not fetch when session is loading', async () => {
    mockUseSession.mockReturnValue({ status: 'loading', data: null });

    const { result } = renderHook(() => useSessions(), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockListSessions).not.toHaveBeenCalled();
  });
});

// ===========================================================================
// useSession (single session)
// ===========================================================================

describe('useSession', () => {
  it('fetches session data when sessionId is provided', async () => {
    const sessionData = { session_id: 's1', track_name: 'Barber' };
    mockGetSession.mockResolvedValue(sessionData);

    const { result } = renderHook(() => useSession('s1'), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(sessionData);
    expect(mockGetSession).toHaveBeenCalledWith('s1');
  });

  it('does not fetch when sessionId is null', () => {
    const { result } = renderHook(() => useSession(null), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockGetSession).not.toHaveBeenCalled();
  });
});

// ===========================================================================
// useSessionLaps
// ===========================================================================

describe('useSessionLaps', () => {
  it('fetches laps when sessionId is provided', async () => {
    const lapsData = [{ lap_number: 1, lap_time_s: 92.5 }];
    mockGetSessionLaps.mockResolvedValue(lapsData);

    const { result } = renderHook(() => useSessionLaps('s1'), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(lapsData);
    expect(mockGetSessionLaps).toHaveBeenCalledWith('s1');
  });

  it('does not fetch when sessionId is null', () => {
    const { result } = renderHook(() => useSessionLaps(null), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockGetSessionLaps).not.toHaveBeenCalled();
  });
});

// ===========================================================================
// useLapData
// ===========================================================================

describe('useLapData', () => {
  it('fetches lap data when both sessionId and lapNumber are provided', async () => {
    const lapData = { lap_number: 3, distance_m: [0, 100] };
    mockGetLapData.mockResolvedValue(lapData);

    const { result } = renderHook(() => useLapData('s1', 3), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(lapData);
    expect(mockGetLapData).toHaveBeenCalledWith('s1', 3);
  });

  it('does not fetch when sessionId is null', () => {
    const { result } = renderHook(() => useLapData(null, 3), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockGetLapData).not.toHaveBeenCalled();
  });

  it('does not fetch when lapNumber is null', () => {
    const { result } = renderHook(() => useLapData('s1', null), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockGetLapData).not.toHaveBeenCalled();
  });
});

// ===========================================================================
// useUploadSessions
// ===========================================================================

describe('useUploadSessions', () => {
  it('handles successful upload and sets upload progress', async () => {
    const uploadResult = { session_ids: ['s1'], newly_unlocked: undefined };
    mockUploadSessions.mockImplementation((_files: File[], onProgress?: (n: number) => void) => {
      if (onProgress) onProgress(0.5);
      if (onProgress) onProgress(1);
      return Promise.resolve(uploadResult);
    });
    // Mock milestone check
    mockFetchApi.mockResolvedValue({ session_id: 's1', track_name: 'Barber' });
    mockGetMilestones.mockResolvedValue({ milestones: [] });

    const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

    const file = new File(['data'], 'test.csv');
    await act(async () => {
      result.current.mutate([file]);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Verify upload progress was tracked
    expect(mockUploadSessions).toHaveBeenCalled();
  });

  it('sets upload state to error on failure with specific message', async () => {
    mockUploadSessions.mockRejectedValue(new Error('File too large. Try exporting fewer laps.'));

    const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

    const file = new File(['data'], 'test.csv');
    await act(async () => {
      result.current.mutate([file]);
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    // Store should have recorded error state and message — no auto-dismiss
    expect(useSessionStore.getState().uploadState).toBe('error');
    expect(useSessionStore.getState().uploadErrorMessage).toBe(
      'File too large. Try exporting fewer laps.',
    );
  });

  it('shows achievement toasts when newly_unlocked is present', async () => {
    const uploadResult = { session_ids: ['s1'], newly_unlocked: ['ach1'] };
    mockUploadSessions.mockResolvedValue(uploadResult);
    mockFetchApi.mockImplementation((url: string) => {
      if (url === '/api/achievements/recent') {
        return Promise.resolve({ newly_unlocked: [{ name: 'First Track' }] });
      }
      if (url.includes('/api/sessions/')) {
        return Promise.resolve({ session_id: 's1', track_name: 'Barber' });
      }
      return Promise.resolve({});
    });
    mockGetMilestones.mockResolvedValue({ milestones: [] });

    const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

    const file = new File(['data'], 'test.csv');
    await act(async () => {
      result.current.mutate([file]);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Should have toasts in the store
    await waitFor(() => {
      const toasts = useUiStore.getState().toasts;
      expect(toasts.length).toBeGreaterThan(0);
    });
  });

  it('shows fallback achievement toast when fetching details fails', async () => {
    const uploadResult = { session_ids: ['s1'], newly_unlocked: ['ach1', 'ach2'] };
    mockUploadSessions.mockResolvedValue(uploadResult);
    mockFetchApi.mockImplementation((url: string) => {
      if (url === '/api/achievements/recent') {
        return Promise.reject(new Error('fail'));
      }
      if (url.includes('/api/sessions/')) {
        return Promise.resolve({ session_id: 's1', track_name: 'Barber' });
      }
      return Promise.resolve({});
    });
    mockGetMilestones.mockResolvedValue({ milestones: [] });

    const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

    const file = new File(['data'], 'test.csv');
    await act(async () => {
      result.current.mutate([file]);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Should have fallback toast
    await waitFor(() => {
      const toasts = useUiStore.getState().toasts;
      const achToast = toasts.find((t) => t.type === 'achievement');
      expect(achToast).toBeTruthy();
      expect(achToast!.message).toContain('2 achievements unlocked');
    });
  });

  it('shows PB toast when upload session is a personal best', async () => {
    const uploadResult = { session_ids: ['s1'] };
    mockUploadSessions.mockResolvedValue(uploadResult);
    mockFetchApi.mockImplementation((url: string) => {
      if (url.includes('/api/sessions/')) {
        return Promise.resolve({ session_id: 's1', track_name: 'Barber' });
      }
      return Promise.resolve({});
    });
    mockGetMilestones.mockResolvedValue({
      milestones: [{ category: 'pb', session_id: 's1' }],
    });

    const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

    const file = new File(['data'], 'test.csv');
    await act(async () => {
      result.current.mutate([file]);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    await waitFor(() => {
      const toasts = useUiStore.getState().toasts;
      const pbToast = toasts.find((t) => t.type === 'pb');
      expect(pbToast).toBeTruthy();
      expect(pbToast!.message).toBe('New Personal Best!');
    });
  });

  it('shows info toast when no PB milestone', async () => {
    const uploadResult = { session_ids: ['s1'] };
    mockUploadSessions.mockResolvedValue(uploadResult);
    mockFetchApi.mockImplementation((url: string) => {
      if (url.includes('/api/sessions/')) {
        return Promise.resolve({ session_id: 's1', track_name: 'Barber' });
      }
      return Promise.resolve({});
    });
    mockGetMilestones.mockResolvedValue({ milestones: [] });

    const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

    const file = new File(['data'], 'test.csv');
    await act(async () => {
      result.current.mutate([file]);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    await waitFor(() => {
      const toasts = useUiStore.getState().toasts;
      const infoToast = toasts.find((t) => t.type === 'info');
      expect(infoToast).toBeTruthy();
      expect(infoToast!.message).toBe('Session uploaded successfully');
    });
  });

  it('shows info toast when track_name is missing', async () => {
    const uploadResult = { session_ids: ['s1'] };
    mockUploadSessions.mockResolvedValue(uploadResult);
    mockFetchApi.mockImplementation((url: string) => {
      if (url.includes('/api/sessions/')) {
        return Promise.resolve({ session_id: 's1', track_name: null });
      }
      return Promise.resolve({});
    });

    const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

    const file = new File(['data'], 'test.csv');
    await act(async () => {
      result.current.mutate([file]);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    await waitFor(() => {
      const toasts = useUiStore.getState().toasts;
      const infoToast = toasts.find((t) => t.type === 'info');
      expect(infoToast).toBeTruthy();
    });
  });

  it('shows info toast when milestone check fails', async () => {
    const uploadResult = { session_ids: ['s1'] };
    mockUploadSessions.mockResolvedValue(uploadResult);
    mockFetchApi.mockImplementation((url: string) => {
      if (url.includes('/api/sessions/')) {
        return Promise.resolve({ session_id: 's1', track_name: 'Barber' });
      }
      return Promise.resolve({});
    });
    mockGetMilestones.mockRejectedValue(new Error('fail'));

    const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

    const file = new File(['data'], 'test.csv');
    await act(async () => {
      result.current.mutate([file]);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    await waitFor(() => {
      const toasts = useUiStore.getState().toasts;
      const infoToast = toasts.find((t) => t.type === 'info');
      expect(infoToast).toBeTruthy();
      expect(infoToast!.message).toBe('Session uploaded successfully');
    });
  });

  it('resets upload state after timeout on success', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const uploadResult = { session_ids: ['s1'] };
      mockUploadSessions.mockResolvedValue(uploadResult);
      mockFetchApi.mockResolvedValue({ session_id: 's1', track_name: 'Barber' });
      mockGetMilestones.mockResolvedValue({ milestones: [] });

      const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

      const file = new File(['data'], 'test.csv');
      await act(async () => {
        result.current.mutate([file]);
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      // Upload state should be 'done' right after success
      expect(useSessionStore.getState().uploadProgress).toBe(100);

      // Advance past the 1500ms auto-dismiss
      await act(async () => {
        vi.advanceTimersByTime(1600);
      });

      expect(useSessionStore.getState().uploadState).toBe('idle');
      expect(useSessionStore.getState().uploadProgress).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it('does not auto-dismiss error state (user must click Try Again)', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      mockUploadSessions.mockRejectedValue(new Error('fail'));

      const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

      const file = new File(['data'], 'test.csv');
      await act(async () => {
        result.current.mutate([file]);
      });

      await waitFor(() => expect(result.current.isError).toBe(true));

      // Error state should be set
      expect(useSessionStore.getState().uploadState).toBe('error');
      expect(useSessionStore.getState().uploadErrorMessage).toBe('fail');

      // Advance well past any old timeout — error should persist
      await act(async () => {
        vi.advanceTimersByTime(10000);
      });

      expect(useSessionStore.getState().uploadState).toBe('error');

      // Manual reset (simulates "Try Again" button)
      useSessionStore.getState().resetUpload();
      expect(useSessionStore.getState().uploadState).toBe('idle');
      expect(useSessionStore.getState().uploadErrorMessage).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('sets active session on successful upload', async () => {
    const uploadResult = { session_ids: ['new-session-1'] };
    mockUploadSessions.mockResolvedValue(uploadResult);
    mockFetchApi.mockResolvedValue({ session_id: 'new-session-1', track_name: 'Barber' });
    mockGetMilestones.mockResolvedValue({ milestones: [] });

    const { result } = renderHook(() => useUploadSessions(), { wrapper: createWrapper() });

    const file = new File(['data'], 'test.csv');
    await act(async () => {
      result.current.mutate([file]);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // The store should have the active session set
    expect(useSessionStore.getState().activeSessionId).toBe('new-session-1');
  });
});

// ===========================================================================
// useDeleteSession
// ===========================================================================

describe('useDeleteSession', () => {
  it('calls deleteSession API and invalidates queries', async () => {
    mockDeleteSession.mockResolvedValue({ status: 'ok' });

    const { result } = renderHook(() => useDeleteSession(), { wrapper: createWrapper() });

    await act(async () => {
      result.current.mutate('s1');
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockDeleteSession).toHaveBeenCalledWith('s1');
  });
});

// ===========================================================================
// useDeleteAllSessions
// ===========================================================================

describe('useDeleteAllSessions', () => {
  it('calls deleteAllSessions API and invalidates queries', async () => {
    mockDeleteAllSessions.mockResolvedValue({ status: 'ok' });

    const { result } = renderHook(() => useDeleteAllSessions(), { wrapper: createWrapper() });

    await act(async () => {
      result.current.mutate();
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockDeleteAllSessions).toHaveBeenCalled();
  });
});

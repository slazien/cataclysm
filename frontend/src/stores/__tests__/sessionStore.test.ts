import { describe, it, expect, beforeEach } from 'vitest';
import { useSessionStore } from '../sessionStore';
import type { SessionSummary } from '@/lib/types';

const SESSION_A: SessionSummary = {
  session_id: 'sess-aaa',
  track_name: 'Barber Motorsports Park',
  session_date: '2025-06-01',
  n_laps: 15,
  n_clean_laps: 12,
  best_lap_time_s: 98.4,
  top3_avg_time_s: 99.1,
  avg_lap_time_s: 101.2,
  consistency_score: 87,
  session_score: 82,
};

const SESSION_B: SessionSummary = {
  session_id: 'sess-bbb',
  track_name: 'Road America',
  session_date: '2025-07-15',
  n_laps: 20,
  n_clean_laps: 18,
  best_lap_time_s: 142.7,
  top3_avg_time_s: 143.5,
  avg_lap_time_s: 145.0,
  consistency_score: 91,
  session_score: 88,
};

describe('sessionStore', () => {
  beforeEach(() => {
    useSessionStore.setState({
      activeSessionId: null,
      sessions: [],
      uploadState: 'idle',
      uploadProgress: 0,
    });
  });

  // --- initial state ---

  it('has correct initial state', () => {
    const state = useSessionStore.getState();
    expect(state.activeSessionId).toBeNull();
    expect(state.sessions).toEqual([]);
    expect(state.uploadState).toBe('idle');
    expect(state.uploadProgress).toBe(0);
  });

  // --- setActiveSession ---

  describe('setActiveSession', () => {
    it('sets an active session id', () => {
      useSessionStore.getState().setActiveSession('sess-aaa');
      expect(useSessionStore.getState().activeSessionId).toBe('sess-aaa');
    });

    it('switches from one session to another', () => {
      useSessionStore.getState().setActiveSession('sess-aaa');
      useSessionStore.getState().setActiveSession('sess-bbb');
      expect(useSessionStore.getState().activeSessionId).toBe('sess-bbb');
    });

    it('clears the active session with null', () => {
      useSessionStore.getState().setActiveSession('sess-aaa');
      useSessionStore.getState().setActiveSession(null);
      expect(useSessionStore.getState().activeSessionId).toBeNull();
    });

    it('does not affect sessions list or upload state', () => {
      useSessionStore.setState({ sessions: [SESSION_A], uploadState: 'done', uploadProgress: 100 });
      useSessionStore.getState().setActiveSession('sess-aaa');
      const state = useSessionStore.getState();
      expect(state.sessions).toEqual([SESSION_A]);
      expect(state.uploadState).toBe('done');
      expect(state.uploadProgress).toBe(100);
    });
  });

  // --- setSessions ---

  describe('setSessions', () => {
    it('sets a list of sessions', () => {
      useSessionStore.getState().setSessions([SESSION_A, SESSION_B]);
      expect(useSessionStore.getState().sessions).toEqual([SESSION_A, SESSION_B]);
    });

    it('replaces an existing sessions list', () => {
      useSessionStore.getState().setSessions([SESSION_A]);
      useSessionStore.getState().setSessions([SESSION_B]);
      expect(useSessionStore.getState().sessions).toEqual([SESSION_B]);
    });

    it('sets an empty sessions list', () => {
      useSessionStore.getState().setSessions([SESSION_A, SESSION_B]);
      useSessionStore.getState().setSessions([]);
      expect(useSessionStore.getState().sessions).toEqual([]);
    });

    it('preserves session objects by reference', () => {
      useSessionStore.getState().setSessions([SESSION_A]);
      const stored = useSessionStore.getState().sessions[0];
      expect(stored).toBe(SESSION_A);
    });

    it('does not affect activeSessionId', () => {
      useSessionStore.getState().setActiveSession('sess-aaa');
      useSessionStore.getState().setSessions([SESSION_A, SESSION_B]);
      expect(useSessionStore.getState().activeSessionId).toBe('sess-aaa');
    });
  });

  // --- setUploadState ---

  describe('setUploadState', () => {
    it('transitions from idle to uploading', () => {
      useSessionStore.getState().setUploadState('uploading');
      expect(useSessionStore.getState().uploadState).toBe('uploading');
    });

    it('transitions from uploading to processing', () => {
      useSessionStore.getState().setUploadState('uploading');
      useSessionStore.getState().setUploadState('processing');
      expect(useSessionStore.getState().uploadState).toBe('processing');
    });

    it('transitions from processing to done', () => {
      useSessionStore.getState().setUploadState('processing');
      useSessionStore.getState().setUploadState('done');
      expect(useSessionStore.getState().uploadState).toBe('done');
    });

    it('transitions to error state', () => {
      useSessionStore.getState().setUploadState('uploading');
      useSessionStore.getState().setUploadState('error');
      expect(useSessionStore.getState().uploadState).toBe('error');
    });

    it('resets back to idle after error', () => {
      useSessionStore.getState().setUploadState('error');
      useSessionStore.getState().setUploadState('idle');
      expect(useSessionStore.getState().uploadState).toBe('idle');
    });

    it('does not affect sessions list or activeSessionId', () => {
      useSessionStore.setState({ sessions: [SESSION_A], activeSessionId: 'sess-aaa' });
      useSessionStore.getState().setUploadState('uploading');
      const state = useSessionStore.getState();
      expect(state.sessions).toEqual([SESSION_A]);
      expect(state.activeSessionId).toBe('sess-aaa');
    });
  });

  // --- setUploadProgress ---

  describe('setUploadProgress', () => {
    it('sets progress to 0 initially', () => {
      expect(useSessionStore.getState().uploadProgress).toBe(0);
    });

    it('sets progress to a mid-range upload value', () => {
      useSessionStore.getState().setUploadProgress(30);
      expect(useSessionStore.getState().uploadProgress).toBe(30);
    });

    it('sets progress to the upload/processing boundary value', () => {
      useSessionStore.getState().setUploadProgress(60);
      expect(useSessionStore.getState().uploadProgress).toBe(60);
    });

    it('sets progress to the processing ceiling value', () => {
      useSessionStore.getState().setUploadProgress(95);
      expect(useSessionStore.getState().uploadProgress).toBe(95);
    });

    it('sets progress to 100 when done', () => {
      useSessionStore.getState().setUploadProgress(100);
      expect(useSessionStore.getState().uploadProgress).toBe(100);
    });

    it('replaces previous progress value', () => {
      useSessionStore.getState().setUploadProgress(45);
      useSessionStore.getState().setUploadProgress(70);
      expect(useSessionStore.getState().uploadProgress).toBe(70);
    });

    it('does not affect uploadState', () => {
      useSessionStore.getState().setUploadState('uploading');
      useSessionStore.getState().setUploadProgress(50);
      expect(useSessionStore.getState().uploadState).toBe('uploading');
    });
  });

  // --- full upload lifecycle sequence ---

  describe('upload lifecycle', () => {
    it('progresses through the full upload lifecycle', () => {
      // Start idle
      expect(useSessionStore.getState().uploadState).toBe('idle');
      expect(useSessionStore.getState().uploadProgress).toBe(0);

      // Begin upload
      useSessionStore.getState().setUploadState('uploading');
      useSessionStore.getState().setUploadProgress(30);
      expect(useSessionStore.getState().uploadState).toBe('uploading');
      expect(useSessionStore.getState().uploadProgress).toBe(30);

      // Upload bytes complete, enter server processing phase
      useSessionStore.getState().setUploadProgress(60);
      useSessionStore.getState().setUploadState('processing');
      expect(useSessionStore.getState().uploadState).toBe('processing');
      expect(useSessionStore.getState().uploadProgress).toBe(60);

      // Processing finishes
      useSessionStore.getState().setUploadProgress(100);
      useSessionStore.getState().setUploadState('done');
      useSessionStore.getState().setSessions([SESSION_A]);
      useSessionStore.getState().setActiveSession(SESSION_A.session_id);

      const state = useSessionStore.getState();
      expect(state.uploadState).toBe('done');
      expect(state.uploadProgress).toBe(100);
      expect(state.sessions).toEqual([SESSION_A]);
      expect(state.activeSessionId).toBe('sess-aaa');
    });
  });

  // --- state independence ---

  describe('state independence', () => {
    it('independent fields do not bleed into each other', () => {
      useSessionStore.getState().setSessions([SESSION_A, SESSION_B]);
      useSessionStore.getState().setActiveSession('sess-bbb');
      useSessionStore.getState().setUploadProgress(75);

      const state = useSessionStore.getState();
      expect(state.sessions).toHaveLength(2);
      expect(state.activeSessionId).toBe('sess-bbb');
      expect(state.uploadProgress).toBe(75);
      expect(state.uploadState).toBe('idle');
    });
  });
});

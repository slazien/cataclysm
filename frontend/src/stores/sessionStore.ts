import { create } from 'zustand';
import type { SessionSummary } from '@/lib/types';

type UploadState = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

interface SessionState {
  activeSessionId: string | null;
  sessions: SessionSummary[];
  uploadState: UploadState;
  /** 0-100 real progress: 0-60 = upload bytes, 60-95 = server processing, 100 = done */
  uploadProgress: number;
  setActiveSession: (id: string | null) => void;
  setSessions: (sessions: SessionSummary[]) => void;
  setUploadState: (state: UploadState) => void;
  setUploadProgress: (pct: number) => void;
}

export const useSessionStore = create<SessionState>()((set) => ({
  activeSessionId: null,
  sessions: [],
  uploadState: 'idle',
  uploadProgress: 0,
  setActiveSession: (id) => set({ activeSessionId: id }),
  setSessions: (sessions) => set({ sessions }),
  setUploadState: (state) => set({ uploadState: state }),
  setUploadProgress: (pct) => set({ uploadProgress: pct }),
}));

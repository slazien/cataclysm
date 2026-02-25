import { create } from 'zustand';
import type { SessionSummary } from '@/lib/types';

type UploadState = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

interface SessionState {
  activeSessionId: string | null;
  sessions: SessionSummary[];
  uploadState: UploadState;
  setActiveSession: (id: string | null) => void;
  setSessions: (sessions: SessionSummary[]) => void;
  setUploadState: (state: UploadState) => void;
}

export const useSessionStore = create<SessionState>()((set) => ({
  activeSessionId: null,
  sessions: [],
  uploadState: 'idle',
  setActiveSession: (id) => set({ activeSessionId: id }),
  setSessions: (sessions) => set({ sessions }),
  setUploadState: (state) => set({ uploadState: state }),
}));

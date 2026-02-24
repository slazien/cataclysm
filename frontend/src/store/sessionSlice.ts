import { create } from "zustand";
import type { SessionSummary } from "@/lib/types";

interface SessionState {
  activeSessionId: string | null;
  sessions: SessionSummary[];
  setActiveSession: (id: string | null) => void;
  setSessions: (sessions: SessionSummary[]) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  activeSessionId: null,
  sessions: [],
  setActiveSession: (id) => set({ activeSessionId: id }),
  setSessions: (sessions) => set({ sessions }),
}));

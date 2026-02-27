import { create } from 'zustand';
import type { CoachingReport, ChatMessage } from '@/lib/types';

interface ContextChip {
  label: string;
  value: string;
}

interface CoachState {
  panelOpen: boolean;
  report: CoachingReport | null;
  chatHistory: ChatMessage[];
  contextChips: ContextChip[];
  pendingQuestion: string | null;
  isWaiting: boolean;
  togglePanel: () => void;
  setReport: (report: CoachingReport | null) => void;
  addMessage: (msg: ChatMessage) => void;
  clearChat: () => void;
  setContextChips: (chips: ContextChip[]) => void;
  setPendingQuestion: (q: string | null) => void;
  setIsWaiting: (v: boolean) => void;
}

export const useCoachStore = create<CoachState>()((set) => ({
  panelOpen: false,
  report: null,
  chatHistory: [],
  contextChips: [],
  pendingQuestion: null,
  isWaiting: false,
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  setReport: (report) => set({ report }),
  addMessage: (msg) => set((s) => ({ chatHistory: [...s.chatHistory, msg] })),
  clearChat: () => set({ chatHistory: [] }),
  setContextChips: (chips) => set({ contextChips: chips }),
  setPendingQuestion: (q) => set({ pendingQuestion: q }),
  setIsWaiting: (v) => set({ isWaiting: v }),
}));

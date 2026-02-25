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
  togglePanel: () => void;
  setReport: (report: CoachingReport | null) => void;
  addMessage: (msg: ChatMessage) => void;
  clearChat: () => void;
  setContextChips: (chips: ContextChip[]) => void;
}

export const useCoachStore = create<CoachState>()((set) => ({
  panelOpen: false,
  report: null,
  chatHistory: [],
  contextChips: [],
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  setReport: (report) => set({ report }),
  addMessage: (msg) => set((s) => ({ chatHistory: [...s.chatHistory, msg] })),
  clearChat: () => set({ chatHistory: [] }),
  setContextChips: (chips) => set({ contextChips: chips }),
}));

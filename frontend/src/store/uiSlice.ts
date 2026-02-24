import { create } from "zustand";

type Tab = "overview" | "speed-trace" | "corners" | "coaching" | "trends";

interface UiState {
  activeTab: Tab;
  sidebarOpen: boolean;
  selectedLaps: number[];
  skillLevel: string;
  setActiveTab: (tab: Tab) => void;
  toggleSidebar: () => void;
  setSelectedLaps: (laps: number[]) => void;
  setSkillLevel: (level: string) => void;
}

export const useUiStore = create<UiState>((set) => ({
  activeTab: "overview",
  sidebarOpen: true,
  selectedLaps: [],
  skillLevel: "intermediate",
  setActiveTab: (tab) => set({ activeTab: tab }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSelectedLaps: (laps) => set({ selectedLaps: laps }),
  setSkillLevel: (level) => set({ skillLevel: level }),
}));

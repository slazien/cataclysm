import { create } from 'zustand';

type SkillLevel = 'novice' | 'intermediate' | 'advanced';
type UnitPreference = 'imperial' | 'metric';
type ActiveView = 'dashboard' | 'deep-dive' | 'progress';

interface UiState {
  activeView: ActiveView;
  skillLevel: SkillLevel;
  sessionDrawerOpen: boolean;
  unitPreference: UnitPreference;
  setActiveView: (view: ActiveView) => void;
  setSkillLevel: (level: SkillLevel) => void;
  toggleSessionDrawer: () => void;
  setUnitPreference: (pref: UnitPreference) => void;
}

export const useUiStore = create<UiState>()((set) => ({
  activeView: 'dashboard',
  skillLevel: 'intermediate',
  sessionDrawerOpen: false,
  unitPreference: 'imperial',
  setActiveView: (view) => set({ activeView: view }),
  setSkillLevel: (level) => set({ skillLevel: level }),
  toggleSessionDrawer: () => set((s) => ({ sessionDrawerOpen: !s.sessionDrawerOpen })),
  setUnitPreference: (pref) => set({ unitPreference: pref }),
}));

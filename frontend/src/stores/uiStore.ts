import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type SkillLevel = 'novice' | 'intermediate' | 'advanced';
export type UnitPreference = 'imperial' | 'metric';
type ActiveView = 'session-report' | 'deep-dive' | 'progress' | 'debrief';

export interface Toast {
  id: string;
  message: string;
  type: 'pb' | 'milestone' | 'info';
  duration?: number;
}

interface UiState {
  activeView: ActiveView;
  skillLevel: SkillLevel;
  sessionDrawerOpen: boolean;
  settingsPanelOpen: boolean;
  unitPreference: UnitPreference;
  toasts: Toast[];
  setActiveView: (view: ActiveView) => void;
  setSkillLevel: (level: SkillLevel) => void;
  toggleSessionDrawer: () => void;
  toggleSettingsPanel: () => void;
  setUnitPreference: (pref: UnitPreference) => void;
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}

let toastCounter = 0;

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
  activeView: 'session-report',
  skillLevel: 'intermediate',
  sessionDrawerOpen: false,
  settingsPanelOpen: false,
  unitPreference: 'imperial',
  toasts: [],
  setActiveView: (view) => set({ activeView: view }),
  setSkillLevel: (level) => set({ skillLevel: level }),
  toggleSessionDrawer: () => set((s) => ({ sessionDrawerOpen: !s.sessionDrawerOpen })),
  toggleSettingsPanel: () => set((s) => ({ settingsPanelOpen: !s.settingsPanelOpen })),
  setUnitPreference: (pref) => set({ unitPreference: pref }),
  addToast: (toast) => {
    const id = `toast-${Date.now()}-${++toastCounter}`;
    set((s) => ({ toasts: [...s.toasts, { ...toast, id }] }));
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}),
    {
      name: 'cataclysm-prefs',
      partialize: (state) => ({
        skillLevel: state.skillLevel,
        unitPreference: state.unitPreference,
      }),
    },
  ),
);

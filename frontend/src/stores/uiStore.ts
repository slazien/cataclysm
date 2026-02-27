import { create } from 'zustand';

type SkillLevel = 'novice' | 'intermediate' | 'advanced';
type UnitPreference = 'imperial' | 'metric';
type ActiveView = 'dashboard' | 'deep-dive' | 'progress' | 'debrief';

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

export const useUiStore = create<UiState>()((set) => ({
  activeView: 'dashboard',
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
}));

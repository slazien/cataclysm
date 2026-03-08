import { create } from 'zustand';

type NotesTab = 'session' | 'global';

interface NotesState {
  panelOpen: boolean;
  activeTab: NotesTab;
  editingNoteId: string | null;
  togglePanel: () => void;
  setActiveTab: (tab: NotesTab) => void;
  setEditingNoteId: (id: string | null) => void;
}

export const useNotesStore = create<NotesState>()((set) => ({
  panelOpen: false,
  activeTab: 'session',
  editingNoteId: null,
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setEditingNoteId: (id) => set({ editingNoteId: id }),
}));

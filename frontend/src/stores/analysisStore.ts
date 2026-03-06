import { create } from 'zustand';

export type DeepDiveMode = 'speed' | 'corner' | 'sectors' | 'custom' | 'replay';

interface HoveredBrakeLap {
  lapNumber: number;
  brakePointM: number;
}

interface AnalysisState {
  cursorDistance: number | null;
  selectedLaps: number[];
  selectedCorner: string | null;
  deepDiveMode: DeepDiveMode;
  zoomRange: [number, number] | null;
  hoveredBrakeLap: HoveredBrakeLap | null;
  setCursorDistance: (d: number | null) => void;
  selectLaps: (laps: number[]) => void;
  selectCorner: (id: string | null) => void;
  setMode: (mode: DeepDiveMode) => void;
  setZoom: (range: [number, number] | null) => void;
  setHoveredBrakeLap: (v: HoveredBrakeLap | null) => void;
  reset: () => void;
}

const initialState = {
  cursorDistance: null,
  selectedLaps: [] as number[],
  selectedCorner: null,
  deepDiveMode: 'speed' as DeepDiveMode,
  zoomRange: null,
  hoveredBrakeLap: null as HoveredBrakeLap | null,
};

export const useAnalysisStore = create<AnalysisState>()((set) => ({
  ...initialState,
  setCursorDistance: (d) => set({ cursorDistance: d }),
  selectLaps: (laps) => set({ selectedLaps: laps }),
  selectCorner: (id) => set({ selectedCorner: id }),
  setMode: (mode) => set({ deepDiveMode: mode }),
  setZoom: (range) => set({ zoomRange: range }),
  setHoveredBrakeLap: (v) => set({ hoveredBrakeLap: v }),
  reset: () => set(initialState),
}));

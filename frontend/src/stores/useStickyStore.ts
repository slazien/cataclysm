import { create } from 'zustand';
import {
  avoidStickyObstacles,
  clampStickyPosition,
  getSpawnPosition,
  snapStickyToRail,
  type StickyObstacle,
  type StickyPosition,
  type StickyViewport,
} from '@/components/shared/stickies/stickyLayout';
import type { StickyData, StickyTone } from '@/lib/types';

export type { StickyTone } from '@/lib/types';

/** Runtime sticky with pixel positions for rendering. */
export interface Sticky {
  id: string;
  /** Pixel x for rendering (derived from normalized pos_x * viewport). */
  x: number;
  /** Pixel y for rendering (derived from normalized pos_y * viewport). */
  y: number;
  width: number;
  height: number;
  text: string;
  tone: StickyTone;
  collapsed: boolean;
  mobileMoveMode: boolean;
  zIndex: number;
  /** Normalized 0..1 from API. */
  posX: number;
  /** Normalized 0..1 from API. */
  posY: number;
  viewScope: string;
}

interface StickyState {
  stickies: Sticky[];
  maxZIndex: number;
  /** True after the first API hydration completes. */
  hydrated: boolean;

  hydrateFromApi: (
    apiStickies: StickyData[],
    viewport: StickyViewport,
    obstacles?: StickyObstacle[],
  ) => void;
  addSticky: (
    viewport: StickyViewport,
    obstacles?: StickyObstacle[],
  ) => Sticky;
  moveSticky: (
    id: string,
    position: StickyPosition,
    viewport: StickyViewport,
    options?: { snapToRail?: boolean; avoidObstacles?: StickyObstacle[] },
  ) => void;
  updateSticky: (id: string, updates: Partial<Sticky>) => void;
  setStickyText: (id: string, text: string) => void;
  setStickyTone: (id: string, tone: StickyTone) => void;
  toggleCollapsed: (
    id: string,
    viewport?: StickyViewport,
    obstacles?: StickyObstacle[],
  ) => void;
  setMobileMoveMode: (id: string, enabled: boolean) => void;
  removeSticky: (id: string) => void;
  bringToFront: (id: string) => void;
  /** Get normalized (0..1) position for API sync. */
  getNormalizedPos: (id: string, viewport: StickyViewport) => { pos_x: number; pos_y: number } | null;
}

export const DESKTOP_SIZE = { width: 292, height: 230 };
export const MOBILE_SIZE = { width: 272, height: 208 };
const TONES: StickyTone[] = ['amber', 'sky', 'mint', 'rose', 'violet', 'peach'];

export function getStickySize(viewport: StickyViewport) {
  return viewport.isMobile ? MOBILE_SIZE : DESKTOP_SIZE;
}

function makeStickyId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `sticky-${Math.random().toString(36).slice(2, 10)}`;
}

function apiToSticky(
  api: StickyData,
  viewport: StickyViewport,
  zIndex: number,
  obstacles: StickyObstacle[] = [],
): Sticky {
  const size = getStickySize(viewport);
  const rawPos = {
    x: api.pos_x * viewport.width,
    y: api.pos_y * viewport.height,
  };
  const clamped = clampStickyPosition(rawPos, size, viewport);
  const final = avoidStickyObstacles(clamped, size, viewport, obstacles);

  return {
    id: api.id,
    x: final.x,
    y: final.y,
    width: size.width,
    height: size.height,
    text: api.content,
    tone: api.tone as StickyTone,
    collapsed: api.collapsed,
    mobileMoveMode: false,
    zIndex,
    posX: api.pos_x,
    posY: api.pos_y,
    viewScope: api.view_scope,
  };
}

export const useStickyStore = create<StickyState>()((set, get) => ({
  stickies: [],
  maxZIndex: 100,
  hydrated: false,

  hydrateFromApi: (apiStickies, viewport, obstacles = []) => {
    let z = 100;
    const stickies = apiStickies.map((api) => {
      z += 1;
      return apiToSticky(api, viewport, z, obstacles);
    });
    set({ stickies, maxZIndex: z, hydrated: true });
  },

  addSticky: (viewport, obstacles = []) => {
    const { stickies, maxZIndex } = get();
    const size = getStickySize(viewport);
    const spawn = avoidStickyObstacles(
      getSpawnPosition(stickies.length, size, viewport),
      size,
      viewport,
      obstacles,
    );

    const newSticky: Sticky = {
      id: makeStickyId(),
      x: spawn.x,
      y: spawn.y,
      width: size.width,
      height: size.height,
      text: '',
      tone: TONES[Math.floor(Math.random() * TONES.length)],
      collapsed: true,
      mobileMoveMode: false,
      zIndex: maxZIndex + 1,
      posX: viewport.width > 0 ? spawn.x / viewport.width : 0.5,
      posY: viewport.height > 0 ? spawn.y / viewport.height : 0.1,
      viewScope: 'global',
    };

    set({
      stickies: [...stickies, newSticky],
      maxZIndex: maxZIndex + 1,
    });
    return newSticky;
  },

  moveSticky: (id, position, viewport, options) => {
    set((state) => ({
      stickies: state.stickies.map((sticky) => {
        if (sticky.id !== id) return sticky;
        const clamped = clampStickyPosition(position, sticky, viewport);
        const snapped = options?.snapToRail
          ? snapStickyToRail(clamped, sticky, viewport)
          : clamped;
        const next = avoidStickyObstacles(
          snapped,
          sticky,
          viewport,
          options?.avoidObstacles ?? [],
        );
        return {
          ...sticky,
          x: next.x,
          y: next.y,
          posX: viewport.width > 0 ? next.x / viewport.width : sticky.posX,
          posY: viewport.height > 0 ? next.y / viewport.height : sticky.posY,
        };
      }),
    }));
  },

  updateSticky: (id, updates) => {
    set((state) => ({
      stickies: state.stickies.map((sticky) =>
        sticky.id === id ? { ...sticky, ...updates } : sticky,
      ),
    }));
  },

  setStickyText: (id, text) => {
    get().updateSticky(id, { text });
  },

  setStickyTone: (id, tone) => {
    get().updateSticky(id, { tone });
  },

  toggleCollapsed: (id, viewport, obstacles = []) => {
    const sticky = get().stickies.find((item) => item.id === id);
    if (!sticky) return;
    const nextCollapsed = !sticky.collapsed;
    let updates: Partial<Sticky> = { collapsed: nextCollapsed };

    if (viewport) {
      const clamped = clampStickyPosition(
        { x: sticky.x, y: sticky.y },
        sticky,
        viewport,
      );
      const next = avoidStickyObstacles(clamped, sticky, viewport, obstacles);
      updates = { ...updates, x: next.x, y: next.y };
    }

    get().updateSticky(id, updates);
  },

  setMobileMoveMode: (id, enabled) => {
    get().updateSticky(id, { mobileMoveMode: enabled });
  },

  removeSticky: (id) => {
    set((state) => ({
      stickies: state.stickies.filter((sticky) => sticky.id !== id),
    }));
  },

  bringToFront: (id) => {
    const { stickies, maxZIndex } = get();
    const sticky = stickies.find((item) => item.id === id);
    if (sticky && sticky.zIndex <= maxZIndex) {
      set({
        stickies: stickies.map((item) =>
          item.id === id ? { ...item, zIndex: maxZIndex + 1 } : item,
        ),
        maxZIndex: maxZIndex + 1,
      });
    }
  },

  getNormalizedPos: (id, viewport) => {
    const sticky = get().stickies.find((item) => item.id === id);
    if (!sticky || viewport.width === 0 || viewport.height === 0) return null;
    return {
      pos_x: Math.max(0, Math.min(1, sticky.x / viewport.width)),
      pos_y: Math.max(0, Math.min(1, sticky.y / viewport.height)),
    };
  },
}));

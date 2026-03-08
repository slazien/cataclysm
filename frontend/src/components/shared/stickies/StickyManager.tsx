'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence } from 'motion/react';
import { useStickyStore, registerTriggerAdd, type StickyTone } from '@/stores/useStickyStore';
import { StickyNote } from '@/components/shared/stickies/StickyNote';
import { useIsMobile } from '@/hooks/useMediaQuery';
import { useStickies, useCreateSticky, useUpdateSticky, useDeleteSticky } from '@/hooks/useStickies';
import type {
  StickyObstacle,
  StickyViewport,
} from '@/components/shared/stickies/stickyLayout';

function getSafeAreaInsetBottom() {
  if (typeof window === 'undefined') return 0;
  const probe = document.createElement('div');
  probe.style.cssText =
    'position:fixed;bottom:0;left:0;visibility:hidden;padding-bottom:env(safe-area-inset-bottom);';
  document.body.appendChild(probe);
  const computed = Number.parseFloat(getComputedStyle(probe).paddingBottom) || 0;
  document.body.removeChild(probe);
  return computed;
}

function getSafeAreaInsetTop() {
  if (typeof window === 'undefined') return 0;
  const probe = document.createElement('div');
  probe.style.cssText =
    'position:fixed;top:0;left:0;visibility:hidden;padding-top:env(safe-area-inset-top);';
  document.body.appendChild(probe);
  const computed = Number.parseFloat(getComputedStyle(probe).paddingTop) || 0;
  document.body.removeChild(probe);
  return computed;
}

const OBSTACLE_SELECTOR =
  'main canvas, main svg, main table, main [data-sticky-obstacle="true"]';

function collectStickyObstacles(): StickyObstacle[] {
  if (typeof window === 'undefined') return [];

  const elements = Array.from(document.querySelectorAll<HTMLElement>(OBSTACLE_SELECTOR));
  const obstacles: StickyObstacle[] = [];

  for (const element of elements) {
    if (element.closest('[data-sticky-layer="true"]')) continue;
    const rect = element.getBoundingClientRect();
    if (rect.width < 220 || rect.height < 120) continue;
    obstacles.push({
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
    });
  }

  return obstacles;
}

export function StickyManager() {
  const { stickies, addSticky, hydrateFromApi, hydrated, getNormalizedPos } = useStickyStore();
  const isMobile = useIsMobile();
  const [viewportSize, setViewportSize] = useState({
    width: 0,
    height: 0,
    safeAreaTop: 0,
    safeAreaBottom: 0,
  });

  // API hooks
  const { data: apiData } = useStickies();
  const createMutation = useCreateSticky();
  const updateMutation = useUpdateSticky();
  const deleteMutation = useDeleteSticky();

  // Temp ID → API ID mapping for in-flight creates
  const tempIdMap = useRef<Map<string, string>>(new Map());
  const syncTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  /** Resolve a store ID to the real API ID (handles temp IDs). */
  const resolveApiId = useCallback((storeId: string): string | null => {
    return tempIdMap.current.get(storeId) ?? storeId;
  }, []);

  useEffect(() => {
    const syncViewport = () => {
      setViewportSize({
        width: window.innerWidth,
        height: window.innerHeight,
        safeAreaTop: getSafeAreaInsetTop(),
        safeAreaBottom: getSafeAreaInsetBottom(),
      });
    };

    syncViewport();
    window.addEventListener('resize', syncViewport);
    window.addEventListener('orientationchange', syncViewport);
    return () => {
      window.removeEventListener('resize', syncViewport);
      window.removeEventListener('orientationchange', syncViewport);
    };
  }, []);

  const viewport: StickyViewport = useMemo(
    () => ({
      width: viewportSize.width,
      height: viewportSize.height,
      safeAreaTop: viewportSize.safeAreaTop,
      safeAreaBottom: viewportSize.safeAreaBottom,
      isMobile,
    }),
    [isMobile, viewportSize],
  );

  // Hydrate store from API data once viewport is ready
  useEffect(() => {
    if (!apiData?.items || !viewport.width || !viewport.height) return;
    const obstacles = collectStickyObstacles();
    hydrateFromApi(apiData.items, viewport, obstacles);
  }, [apiData, viewport, hydrateFromApi]);

  // Re-clamp stickies on viewport resize (after initial hydration)
  useEffect(() => {
    if (!hydrated || !viewport.width || !viewport.height) return;
    const obstacles = collectStickyObstacles();
    for (const sticky of useStickyStore.getState().stickies) {
      useStickyStore.getState().moveSticky(
        sticky.id,
        { x: sticky.x, y: sticky.y },
        viewport,
        { avoidObstacles: obstacles },
      );
    }
  }, [hydrated, viewport]);

  const handleAdd = useCallback(() => {
    const obstacles = collectStickyObstacles();
    const newSticky = addSticky(viewport, obstacles);
    const tempId = newSticky.id;

    createMutation.mutate({
      pos_x: newSticky.posX,
      pos_y: newSticky.posY,
      content: '',
      tone: newSticky.tone,
      collapsed: true,
      view_scope: 'global',
    }, {
      onSuccess: (apiSticky) => {
        // Map temp → real, then replace ID in store
        tempIdMap.current.set(tempId, apiSticky.id);
        useStickyStore.setState((state) => ({
          stickies: state.stickies.map((s) =>
            s.id === tempId ? { ...s, id: apiSticky.id } : s,
          ),
        }));
        // Clean up after a brief delay (pending debounced syncs resolve)
        setTimeout(() => tempIdMap.current.delete(tempId), 3000);
      },
    });
  }, [viewport, addSticky, createMutation]);

  // Register handleAdd so FloatingToolsMenu can trigger it on mobile
  useEffect(() => {
    registerTriggerAdd(handleAdd);
    return () => registerTriggerAdd(null);
  }, [handleAdd]);

  // Debounced sync for position changes
  const syncPosition = useCallback(
    (stickyId: string) => {
      const existing = syncTimers.current.get(stickyId);
      if (existing) clearTimeout(existing);

      syncTimers.current.set(
        stickyId,
        setTimeout(() => {
          syncTimers.current.delete(stickyId);
          const apiId = resolveApiId(stickyId);
          if (!apiId) return;
          const pos = getNormalizedPos(stickyId, viewport);
          if (!pos) return;
          updateMutation.mutate({ stickyId: apiId, body: pos });
        }, 500),
      );
    },
    [viewport, getNormalizedPos, updateMutation, resolveApiId],
  );

  const syncContent = useCallback(
    (stickyId: string, content: string) => {
      const key = `content-${stickyId}`;
      const existing = syncTimers.current.get(key);
      if (existing) clearTimeout(existing);

      syncTimers.current.set(
        key,
        setTimeout(() => {
          syncTimers.current.delete(key);
          const apiId = resolveApiId(stickyId);
          if (!apiId) return;
          updateMutation.mutate({ stickyId: apiId, body: { content } });
        }, 1000),
      );
    },
    [updateMutation, resolveApiId],
  );

  const syncTone = useCallback(
    (stickyId: string, tone: StickyTone) => {
      const apiId = resolveApiId(stickyId);
      if (!apiId) return;
      updateMutation.mutate({ stickyId: apiId, body: { tone } });
    },
    [updateMutation, resolveApiId],
  );

  const syncCollapsed = useCallback(
    (stickyId: string, collapsed: boolean) => {
      const apiId = resolveApiId(stickyId);
      if (!apiId) return;
      updateMutation.mutate({ stickyId: apiId, body: { collapsed } });
    },
    [updateMutation, resolveApiId],
  );

  const handleDelete = useCallback(
    (stickyId: string) => {
      useStickyStore.getState().removeSticky(stickyId);
      const apiId = resolveApiId(stickyId);
      if (!apiId) return;
      deleteMutation.mutate(apiId);
    },
    [deleteMutation, resolveApiId],
  );

  // Clean up timers on unmount
  useEffect(() => {
    return () => {
      for (const timer of syncTimers.current.values()) {
        clearTimeout(timer);
      }
    };
  }, []);

  if (!viewport.width || !viewport.height) {
    return null;
  }

  return (
    <>
      <div data-sticky-layer="true" className="pointer-events-none fixed inset-0 z-40">
        <AnimatePresence>
          {stickies.map((sticky) => (
            <StickyNote
              key={sticky.id}
              sticky={sticky}
              viewport={viewport}
              isMobile={isMobile}
              resolveObstacles={collectStickyObstacles}
              onPositionChange={syncPosition}
              onContentChange={syncContent}
              onToneChange={syncTone}
              onCollapsedChange={syncCollapsed}
              onDelete={handleDelete}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* Add button removed — FloatingToolsMenu handles both platforms */}
    </>
  );
}

'use client';

import { useCallback, useEffect, useRef } from 'react';

/**
 * RAF-throttled callback hook. Calls the provided callback on each animation
 * frame while the component is mounted. Useful for rendering cursor overlays
 * and other high-frequency visual updates without causing layout thrash.
 */
export function useAnimationFrame(callback: (timestamp: number) => void, active = true) {
  const rafId = useRef<number>(0);
  const callbackRef = useRef(callback);

  // Keep the callback ref current without re-triggering the effect
  callbackRef.current = callback;

  const loop = useCallback((timestamp: number) => {
    callbackRef.current(timestamp);
    rafId.current = requestAnimationFrame(loop);
  }, []);

  useEffect(() => {
    if (!active) return;
    rafId.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafId.current);
  }, [active, loop]);
}

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { TourName } from '@/components/tour/tourSteps';
import { tourStorageKey } from '@/components/tour/tourSteps';

// ---------------------------------------------------------------------------
// useTour — triggers a Driver.js tour once per tourName, with dynamic import
// ---------------------------------------------------------------------------

interface UseTourReturn {
  startTour: () => void;
  hasSeen: boolean;
  markSeen: () => void;
}

/**
 * Manages a contextual Driver.js tour.
 *
 * @param tourName - Unique key for this tour (maps to localStorage).
 * @param enabled  - When this flips to `true` and the tour hasn't been seen,
 *                   the tour starts after an 800ms settle delay.
 * @param getSteps - Callback returning the DriveStep[] to display.
 */
export function useTour(
  tourName: TourName,
  enabled: boolean,
  getSteps: () => import('driver.js').DriveStep[],
): UseTourReturn {
  const storageKey = tourStorageKey(tourName);

  const [hasSeen, setHasSeen] = useState(() => {
    if (typeof window === 'undefined') return true;
    return localStorage.getItem(storageKey) === '1';
  });

  // Track whether we already started in this mount cycle
  const startedRef = useRef(false);
  // Keep driver instance ref for cleanup
  const driverRef = useRef<import('driver.js').Driver | null>(null);
  // Stable ref for getSteps — updated each render so startTour callback
  // can always see the latest steps without being a useCallback dependency.
  // This prevents the timer from being cancelled on every re-render.
  const getStepsRef = useRef(getSteps);
  getStepsRef.current = getSteps;

  const markSeen = useCallback(() => {
    try {
      localStorage.setItem(storageKey, '1');
    } catch {
      /* quota exceeded */
    }
    setHasSeen(true);
  }, [storageKey]);

  const startTour = useCallback(async () => {
    // Guard against concurrent/duplicate calls
    if (startedRef.current) {
      console.info('[tour] startTour: already started, skipping');
      return;
    }

    const steps = getStepsRef.current();

    // Verify all target elements exist in DOM before starting
    const missing: string[] = [];
    const allPresent = steps.every((step) => {
      if (!step.element) return true; // non-element steps always ok
      const found = document.querySelector(step.element as string) !== null;
      if (!found) missing.push(step.element as string);
      return found;
    });
    if (!allPresent) {
      console.info('[tour] startTour: DOM elements missing:', missing);
      return;
    }

    // Don't start while a modal overlay is blocking.
    if (!localStorage.getItem('cataclysm-disclaimer-accepted')) {
      console.info('[tour] startTour: disclaimer not accepted');
      return;
    }

    // All checks passed — prevent duplicate starts
    console.info('[tour] startTour: all checks passed, starting driver.js');
    startedRef.current = true;

    // Dynamic import — zero bundle cost for returning users
    // CSS is loaded globally via globals.css @import
    const { driver } = await import('driver.js');

    const driverInstance = driver({
      showProgress: true,
      popoverClass: 'cataclysm-tour-popover',
      nextBtnText: 'Next',
      prevBtnText: 'Back',
      doneBtnText: 'Got it',
      onDestroyStarted: () => {
        // Mark as seen whether they complete or dismiss
        markSeen();
        driverInstance.destroy();
      },
      steps,
    });

    driverRef.current = driverInstance;
    driverInstance.drive();
  }, [markSeen]);

  // Auto-trigger when enabled becomes true and tour not yet seen.
  // Uses interval-based retry: first attempt at 800ms (settle delay),
  // then every 500ms up to ~4s total. Handles transient DOM/overlay timing.
  useEffect(() => {
    console.info(`[tour] effect: enabled=${enabled} hasSeen=${hasSeen} started=${startedRef.current}`);
    if (!enabled || hasSeen || startedRef.current) return;

    console.info('[tour] effect: scheduling first attempt in 800ms');
    let attempts = 0;
    const maxAttempts = 8;

    const timer = setTimeout(() => {
      console.info(`[tour] attempt ${attempts + 1}/${maxAttempts}`);
      startTour();
      attempts++;
      if (startedRef.current || attempts >= maxAttempts) return;

      // First attempt failed — retry periodically
      intervalId = setInterval(() => {
        attempts++;
        if (startedRef.current || attempts >= maxAttempts) {
          clearInterval(intervalId!);
          return;
        }
        startTour();
      }, 500);
    }, 800);

    let intervalId: ReturnType<typeof setInterval> | undefined;

    return () => {
      clearTimeout(timer);
      if (intervalId) clearInterval(intervalId);
    };
  }, [enabled, hasSeen, startTour]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (driverRef.current) {
        try {
          driverRef.current.destroy();
        } catch {
          /* already destroyed */
        }
        driverRef.current = null;
      }
    };
  }, []);

  return { startTour, hasSeen, markSeen };
}

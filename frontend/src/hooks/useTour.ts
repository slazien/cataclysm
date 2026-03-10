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
      if (process.env.NODE_ENV !== 'production') console.debug(`[tour:${tourName}] skip: already started`);
      return;
    }

    const steps = getStepsRef.current();

    // Verify all target elements exist in DOM before starting
    const missing = steps
      .filter((step) => step.element && !document.querySelector(step.element as string))
      .map((step) => step.element);
    if (missing.length > 0) {
      // Always log missing elements — this is the most common failure cause
      console.warn(`[tour:${tourName}] skip: missing elements`, missing);
      return;
    }

    // Don't start while a modal overlay is blocking.
    if (!localStorage.getItem('cataclysm-disclaimer-accepted')) {
      console.warn(`[tour:${tourName}] skip: disclaimer not accepted`);
      return;
    }

    // All checks passed — prevent duplicate starts
    startedRef.current = true;

    try {
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
    } catch (err) {
      // Reset so retries can work — import or driver init failed
      startedRef.current = false;
      console.warn(`[tour:${tourName}] driver.js failed:`, err);
    }
  }, [markSeen]);

  // Auto-trigger when enabled becomes true and tour not yet seen.
  // Uses interval-based retry: first attempt at 800ms (settle delay),
  // then every 500ms up to ~4s total. Handles transient DOM/overlay timing.
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') {
      console.debug(`[tour:${tourName}] effect: enabled=${enabled} hasSeen=${hasSeen} started=${startedRef.current}`);
    }
    if (!enabled || hasSeen || startedRef.current) return;

    let attempts = 0;
    const maxAttempts = 8;

    const timer = setTimeout(() => {
      startTour();
      attempts++;
      if (startedRef.current || attempts >= maxAttempts) {
        if (!startedRef.current && attempts >= maxAttempts) {
          console.warn(`[tour:${tourName}] gave up after ${maxAttempts} attempts`);
        }
        return;
      }

      // First attempt failed — retry periodically
      intervalId = setInterval(() => {
        attempts++;
        if (startedRef.current || attempts >= maxAttempts) {
          if (!startedRef.current && attempts >= maxAttempts) {
            console.warn(`[tour:${tourName}] gave up after ${maxAttempts} attempts`);
          }
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

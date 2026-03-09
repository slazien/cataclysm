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
    const steps = getStepsRef.current();

    // Verify all target elements exist in DOM before starting
    const allPresent = steps.every((step) => {
      if (!step.element) return true; // non-element steps always ok
      return document.querySelector(step.element as string) !== null;
    });
    if (!allPresent) {
      // Targets not in DOM — skip gracefully
      return;
    }

    // Don't start while a modal overlay is blocking.
    // DisclaimerModal is in DOM only before user accepts (returns null after).
    // Check localStorage directly — more reliable than class selectors.
    if (!localStorage.getItem('cataclysm-disclaimer-accepted')) return;

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

  // Auto-trigger when enabled becomes true and tour not yet seen
  useEffect(() => {
    if (!enabled || hasSeen || startedRef.current) return;
    startedRef.current = true;

    const timer = setTimeout(() => {
      startTour();
    }, 800);

    return () => clearTimeout(timer);
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

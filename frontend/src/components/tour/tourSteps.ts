import type { DriveStep } from 'driver.js';
import type { SkillLevel } from '@/stores/uiStore';

// ---------------------------------------------------------------------------
// Tour step definitions
// ---------------------------------------------------------------------------

export type TourName = 'report' | 'deep-dive' | 'progress';

const STORAGE_PREFIX = 'cataclysm-tour-';

export function tourStorageKey(name: TourName): string {
  return `${STORAGE_PREFIX}${name}`;
}

/** Clear all tour "seen" flags so they replay on next visit. */
export function resetAllTours(): void {
  if (typeof window === 'undefined') return;
  const names: TourName[] = ['report', 'deep-dive', 'progress'];
  for (const name of names) {
    localStorage.removeItem(tourStorageKey(name));
  }
}

/**
 * Resolve the visible tab bar element selector.
 * Mobile (#tab-bar-mobile, visible < lg) and desktop (#tab-bar-desktop,
 * visible >= lg) share the same purpose but are separate DOM nodes.
 */
function getVisibleTabBarSelector(): string {
  const mobile = document.getElementById('tab-bar-mobile');
  if (mobile && mobile.offsetParent !== null) return '#tab-bar-mobile';
  return '#tab-bar-desktop';
}

// ---------------------------------------------------------------------------
// Report tour
// ---------------------------------------------------------------------------

export function getReportSteps(skillLevel: SkillLevel): DriveStep[] {
  const priorityDescription =
    skillLevel === 'novice'
      ? 'Your biggest opportunity this session. The coach explains what happened and how to improve.'
      : 'Your highest-leverage improvement. Data-backed coaching with specific action items.';

  return [
    {
      element: '#priority-improvements',
      popover: {
        title: 'Start Here',
        description: priorityDescription,
        side: 'bottom' as const,
      },
    },
    {
      element: '#corner-grades-table',
      popover: {
        title: 'Corner Grades',
        description:
          'Tap any corner to see your speed analysis and coaching for that turn.',
        side: 'top' as const,
      },
    },
    {
      element: getVisibleTabBarSelector(),
      popover: {
        title: 'Explore Your Data',
        description:
          'Deep Dive shows lap traces. Progress tracks improvement over time. Explore when you\'re ready.',
        side: 'top' as const,
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Deep Dive tour
// ---------------------------------------------------------------------------

export function getDeepDiveSteps(): DriveStep[] {
  return [
    {
      element: '#lap-picker',
      popover: {
        title: 'Select Laps',
        description:
          'Pick one or two laps to compare. Your fastest is pre-selected.',
        side: 'bottom' as const,
      },
    },
    {
      element: '#deep-dive-tabs',
      popover: {
        title: 'Analysis Views',
        description:
          'Lap Trace shows speed through the whole lap. Corner Focus zooms into one turn.',
        side: 'bottom' as const,
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Progress tour
// ---------------------------------------------------------------------------

export function getProgressSteps(): DriveStep[] {
  return [
    {
      element: '#progress-trend-chart',
      popover: {
        title: 'Your Improvement',
        description:
          'Each session you upload builds your timeline. More data = better insights.',
        side: 'bottom' as const,
      },
    },
  ];
}

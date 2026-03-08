# Trackday Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the app flawless for 5-10 HPDE friends testing at AMP in <7 days — bulletproof onboarding, credible coaching, zero dead ends.

**Architecture:** No new backend infrastructure. One new frontend component (SkillLevelPicker), one library integration (Driver.js for tours), coaching prompt audit for corner name specificity, and upload error hardening. All changes are frontend-heavy with one backend prompt tweak.

**Tech Stack:** Next.js 16 / React 19, Zustand, Driver.js, Tailwind, Claude Haiku coaching via existing backend.

**Design doc:** `docs/plans/2026-03-08-trackday-readiness-design.md`

---

## Task 1: Skill Level Picker Component

**Files:**
- Create: `frontend/src/components/shared/SkillLevelPicker.tsx`
- Modify: `frontend/src/components/shared/ProcessingOverlay.tsx`
- Modify: `frontend/src/stores/uiStore.ts` (if flag needed)
- Test: `frontend/src/components/shared/__tests__/SkillLevelPicker.test.tsx`

**Context:** After upload processing completes (state='done'), intercept with a skill level picker before the report renders. Shows once per user. Maps trackday count → skill level.

**Step 1: Create SkillLevelPicker component**

```tsx
// frontend/src/components/shared/SkillLevelPicker.tsx
'use client';

import { motion } from 'motion/react';
import { useUiStore, type SkillLevel } from '@/stores/uiStore';

const LEVELS = [
  { trackdays: 'Less than 5', level: 'novice' as SkillLevel, color: 'bg-emerald-500/20 border-emerald-500/40' },
  { trackdays: '5 – 20', level: 'intermediate' as SkillLevel, color: 'bg-amber-500/20 border-amber-500/40' },
  { trackdays: 'More than 20', level: 'advanced' as SkillLevel, color: 'bg-red-500/20 border-red-500/40' },
] as const;

const STORAGE_KEY = 'cataclysm-skill-level-set';

interface Props {
  onComplete: () => void;
}

export function SkillLevelPicker({ onComplete }: Props) {
  const setSkillLevel = useUiStore((s) => s.setSkillLevel);

  function handleSelect(level: SkillLevel) {
    setSkillLevel(level);
    localStorage.setItem(STORAGE_KEY, '1');
    // Also sync to backend if user is authenticated
    fetch('/api/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill_level: level }),
    }).catch(() => {}); // fire-and-forget
    onComplete();
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex min-h-screen flex-col items-center justify-center gap-8 p-6"
    >
      <div className="text-center">
        <h2 className="text-2xl font-bold text-[var(--text-primary)]">
          How many trackdays have you done?
        </h2>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          This adjusts your coaching and which features we show you.
        </p>
      </div>

      <div className="flex w-full max-w-sm flex-col gap-3">
        {LEVELS.map(({ trackdays, level, color }) => (
          <button
            key={level}
            onClick={() => handleSelect(level)}
            className={`min-h-[56px] rounded-xl border px-6 py-4 text-left text-lg font-medium
              text-[var(--text-primary)] transition-all active:scale-[0.98] ${color}
              hover:brightness-125`}
          >
            {trackdays}
          </button>
        ))}
      </div>
    </motion.div>
  );
}

export function shouldShowSkillPicker(): boolean {
  if (typeof window === 'undefined') return false;
  return !localStorage.getItem(STORAGE_KEY);
}
```

**Step 2: Write test for SkillLevelPicker**

```tsx
// frontend/src/components/shared/__tests__/SkillLevelPicker.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { SkillLevelPicker, shouldShowSkillPicker } from '../SkillLevelPicker';
import { useUiStore } from '@/stores/uiStore';
import { vi, describe, it, expect, beforeEach } from 'vitest';

describe('SkillLevelPicker', () => {
  const onComplete = vi.fn();

  beforeEach(() => {
    onComplete.mockReset();
    localStorage.clear();
  });

  it('renders three trackday range options', () => {
    render(<SkillLevelPicker onComplete={onComplete} />);
    expect(screen.getByText('Less than 5')).toBeInTheDocument();
    expect(screen.getByText('5 – 20')).toBeInTheDocument();
    expect(screen.getByText('More than 20')).toBeInTheDocument();
  });

  it('sets skill level and calls onComplete when option clicked', () => {
    render(<SkillLevelPicker onComplete={onComplete} />);
    fireEvent.click(screen.getByText('Less than 5'));
    expect(useUiStore.getState().skillLevel).toBe('novice');
    expect(onComplete).toHaveBeenCalledOnce();
  });

  it('persists flag so picker does not show again', () => {
    render(<SkillLevelPicker onComplete={onComplete} />);
    fireEvent.click(screen.getByText('5 – 20'));
    expect(shouldShowSkillPicker()).toBe(false);
  });

  it('shouldShowSkillPicker returns true when no flag set', () => {
    expect(shouldShowSkillPicker()).toBe(true);
  });
});
```

**Step 3: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/components/shared/__tests__/SkillLevelPicker.test.tsx
```

Expected: FAIL (component doesn't exist yet if writing test first, or PASS if created in step 1)

**Step 4: Integrate into ProcessingOverlay / page flow**

Modify the transition from upload-complete to report. In the component that calls `setActiveSession()` after upload (likely `WelcomeScreen.tsx` or `page.tsx`), add:

```tsx
import { SkillLevelPicker, shouldShowSkillPicker } from './SkillLevelPicker';

// In the upload success handler, before setActiveSession:
const [showSkillPicker, setShowSkillPicker] = useState(false);

// After ProcessingOverlay reaches 'done':
if (shouldShowSkillPicker()) {
  setShowSkillPicker(true);
  // Don't call setActiveSession yet
} else {
  setActiveSession(sessionId);
}

// In JSX:
{showSkillPicker && (
  <SkillLevelPicker onComplete={() => {
    setShowSkillPicker(false);
    setActiveSession(sessionId); // NOW show the report
  }} />
)}
```

The exact integration point depends on how `ProcessingOverlay` and `WelcomeScreen` interact — read both files before editing. The key contract: skill picker appears full-screen after processing, before report.

**Step 5: Run full test suite + TS check**

```bash
cd frontend && npx vitest run && npx tsc --noEmit
```

**Step 6: Commit**

```bash
git add frontend/src/components/shared/SkillLevelPicker.tsx frontend/src/components/shared/__tests__/SkillLevelPicker.test.tsx [modified files]
git commit -m "feat: skill level picker on first upload — maps trackday count to coaching level"
```

---

## Task 2: Upload Error Hardening

**Files:**
- Modify: `frontend/src/components/shared/ProcessingOverlay.tsx`
- Modify: `frontend/src/components/shared/WelcomeScreen.tsx` (upload handler)
- Test: Existing upload tests or new `__tests__/ProcessingOverlay.test.tsx`

**Context:** Currently shows generic "check your CSV format" on all errors. Need specific messages, client-side validation, and a retry button.

**Step 1: Add client-side CSV validation before upload**

In the upload handler (WelcomeScreen.tsx `handleFiles`), add pre-flight check:

```typescript
function validateCsvFiles(files: File[]): { valid: boolean; error?: string } {
  for (const file of files) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      return { valid: false, error: `"${file.name}" is not a CSV file. Please export from RaceChrono as CSV v3.` };
    }
  }
  return { valid: true };
}

// In handleFiles, before mutation:
const validation = validateCsvFiles(files);
if (!validation.valid) {
  setUploadError(validation.error!);
  return;
}
```

**Step 2: Map backend error responses to specific messages**

In the upload mutation `onError` handler:

```typescript
function getUploadErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    if (error.message.includes('timeout') || error.message.includes('network')) {
      return 'Upload interrupted — check your connection and try again.';
    }
  }
  // Check for API error response
  const status = (error as any)?.response?.status;
  if (status === 429) return 'Upload limit reached. Try again later or sign in for unlimited uploads.';
  if (status === 400) return 'This file doesn\'t look like a RaceChrono v3 CSV. Need help exporting?';
  if (status === 413) return 'File too large. Try exporting fewer laps.';
  return 'Upload failed. Please check your CSV format and try again.';
}
```

**Step 3: Add retry button to ProcessingOverlay error state**

In `ProcessingOverlay.tsx`, find the error state rendering. Add:

```tsx
{uploadState === 'error' && (
  <div className="flex flex-col items-center gap-4 text-center">
    <p className="text-sm text-red-400">{errorMessage}</p>
    <div className="flex gap-3">
      <Button variant="outline" onClick={onRetry}>
        Try Again
      </Button>
      <a
        href="#racechrono-export"
        className="text-sm text-[var(--cata-accent)] underline"
        onClick={onDismiss}
      >
        Export instructions
      </a>
    </div>
  </div>
)}
```

The `onRetry` prop resets the overlay to idle and scrolls back to the upload area. The export instructions link scrolls to the RaceChrono export section on WelcomeScreen.

**Step 4: Handle "no laps detected" as distinct from error**

Check the backend response — if upload succeeds but 0 laps are detected, the response `session_ids` will have entries but the session will have 0 laps. Show: "No laps detected — was the session shorter than 1 lap? Make sure RaceChrono was recording."

**Step 5: Test error states**

Manual test plan (no unit test needed for error messages):
- Upload a `.txt` file → client-side "not a CSV" error
- Upload a valid CSV → success path works
- Disconnect network during upload → timeout message
- Verify retry button resets state

**Step 6: Commit**

```bash
git add frontend/src/components/shared/ProcessingOverlay.tsx frontend/src/components/shared/WelcomeScreen.tsx
git commit -m "fix: specific upload error messages + retry button + client-side CSV validation"
```

---

## Task 3: Coaching Prompt — Corner Name Specificity

**Files:**
- Modify: `cataclysm/driving_physics.py` (corner summary table formatting)
- Test: `tests/test_driving_physics.py` (if exists) or manual review

**Context:** The main corner data table sent to Claude uses `T5` only. The full name ("Descent Right") is in the XML analysis section. This inconsistency causes Claude to sometimes reference corners by number only. Fix: add corner names to the summary table and add an explicit instruction.

**Step 1: Update `_format_all_laps_corners` to include corner names**

Find the function that formats the per-lap corner table. Currently outputs:
```
L1 | T5 | 45.2 | 3-board | 1.15 | 2-board | ...
```

Change to include corner name:
```
L1 | T5 Descent Right | 45.2 | 3-board | 1.15 | 2-board | ...
```

Or if the table header uses `Corner`, change to `Corner (Name)`.

The corner name comes from the `Corner` object's `.name` attribute (populated from track_db.py).

**Step 2: Add explicit instruction to coaching prompt**

In the system prompt section of `driving_physics.py`, add to the output requirements:

```python
# Add to COACHING_SYSTEM_PROMPT or the output format instructions:
"""
CORNER NAMING: Always reference corners by BOTH name and number, e.g. "Carousel (T4)",
"Countdown Hairpin (T6)". Never use just the number. The driver knows corners by name
at their home track.
"""
```

**Step 3: Verify with a manual coaching generation**

After deploying to staging, upload an AMP session and read the coaching report. Verify:
- Primary focus references corner by name + number
- Corner grade notes use name + number
- Priority corners section uses name + number

**Step 4: Commit**

```bash
git add cataclysm/driving_physics.py
git commit -m "fix: coaching prompt uses corner names + numbers — 'Carousel (T4)' not just 'T4'"
```

---

## Task 4: Driver.js App Tour

**Files:**
- Create: `frontend/src/components/tour/TourProvider.tsx`
- Create: `frontend/src/components/tour/tourSteps.ts`
- Create: `frontend/src/hooks/useTour.ts`
- Modify: `frontend/src/components/session-report/SessionReport.tsx` (add IDs)
- Modify: `frontend/src/components/session-report/PriorityCardsSection.tsx` (add ID)
- Modify: `frontend/src/components/session-report/CornerGradesSection.tsx` (add ID)
- Modify: `frontend/src/components/navigation/MobileBottomTabs.tsx` (add ID)
- Modify: `frontend/src/components/deep-dive/DeepDive.tsx` (add IDs)
- Modify: `frontend/src/components/progress/ProgressView.tsx` (add ID)
- Modify: `frontend/src/components/shared/SettingsPanel.tsx` (add "Replay tour" button)
- Modify: `frontend/package.json` (add driver.js)
- Modify: `frontend/src/app/globals.css` (tour styling overrides)
- Test: `frontend/src/hooks/__tests__/useTour.test.ts`

**Context:** Three contextual mini-tours triggered on first visit to each tab. Driver.js library, dynamic import, localStorage state, skill-aware text.

**Step 1: Install Driver.js**

```bash
cd frontend && npm install driver.js
```

**Step 2: Create tour step definitions**

```typescript
// frontend/src/components/tour/tourSteps.ts
import type { DriveStep } from 'driver.js';
import type { SkillLevel } from '@/stores/uiStore';

export function getReportTourSteps(skillLevel: SkillLevel): DriveStep[] {
  return [
    {
      element: '#priority-improvements',
      popover: {
        title: 'Start Here',
        description: skillLevel === 'novice'
          ? 'Your biggest opportunity this session. The coach explains what happened and how to improve.'
          : 'Your highest-leverage improvement. Data-backed coaching with specific action items.',
        side: 'bottom',
        align: 'center',
      },
    },
    {
      element: '#corner-grades-table',
      popover: {
        title: 'Corner Grades',
        description: 'Tap any corner to see your speed analysis and coaching for that turn.',
        side: 'top',
        align: 'center',
      },
    },
    {
      element: '#tab-bar',
      popover: {
        title: 'Explore Your Data',
        description: 'Deep Dive shows lap traces. Progress tracks improvement over time. Explore when you\'re ready.',
        side: 'top',
        align: 'center',
      },
    },
  ];
}

export function getDeepDiveTourSteps(): DriveStep[] {
  return [
    {
      element: '#lap-picker',
      popover: {
        title: 'Select Laps',
        description: 'Pick one or two laps to compare. Your fastest is pre-selected.',
        side: 'bottom',
        align: 'center',
      },
    },
    {
      element: '#deep-dive-tabs',
      popover: {
        title: 'Analysis Views',
        description: 'Lap Trace shows speed through the whole lap. Corner Focus zooms into one turn.',
        side: 'bottom',
        align: 'center',
      },
    },
  ];
}

export function getProgressTourSteps(): DriveStep[] {
  return [
    {
      element: '#progress-trend-chart',
      popover: {
        title: 'Your Improvement',
        description: 'Each session you upload builds your timeline. More data = better insights.',
        side: 'bottom',
        align: 'center',
      },
    },
  ];
}
```

**Step 3: Create tour hook**

```typescript
// frontend/src/hooks/useTour.ts
'use client';

import { useCallback, useEffect, useRef } from 'react';
import { useUiStore } from '@/stores/uiStore';

const TOUR_KEYS = {
  report: 'cataclysm-tour-report',
  deepDive: 'cataclysm-tour-deep-dive',
  progress: 'cataclysm-tour-progress',
} as const;

type TourName = keyof typeof TOUR_KEYS;

export function useTour(tourName: TourName, enabled: boolean) {
  const driverRef = useRef<any>(null);
  const skillLevel = useUiStore((s) => s.skillLevel);

  const hasSeen = useCallback(() => {
    if (typeof window === 'undefined') return true;
    return !!localStorage.getItem(TOUR_KEYS[tourName]);
  }, [tourName]);

  const markSeen = useCallback(() => {
    localStorage.setItem(TOUR_KEYS[tourName], '1');
  }, [tourName]);

  const startTour = useCallback(async () => {
    if (hasSeen()) return;

    const { driver } = await import('driver.js');
    const { getReportTourSteps, getDeepDiveTourSteps, getProgressTourSteps } =
      await import('@/components/tour/tourSteps');

    const stepsMap = {
      report: () => getReportTourSteps(skillLevel),
      deepDive: () => getDeepDiveTourSteps(),
      progress: () => getProgressTourSteps(),
    };

    const steps = stepsMap[tourName]();
    // Verify all target elements exist before starting
    const allTargetsExist = steps.every(
      (s) => !s.element || document.querySelector(s.element as string)
    );
    if (!allTargetsExist) return;

    driverRef.current = driver({
      showProgress: true,
      steps,
      onDestroyed: () => markSeen(),
      popoverClass: 'cataclysm-tour-popover',
      nextBtnText: 'Next',
      prevBtnText: 'Back',
      doneBtnText: 'Got it',
    });

    // Small delay for DOM to settle after render
    requestAnimationFrame(() => {
      driverRef.current?.drive();
    });
  }, [tourName, skillLevel, hasSeen, markSeen]);

  useEffect(() => {
    if (enabled && !hasSeen()) {
      // Delay to let the page render first
      const timer = setTimeout(() => startTour(), 800);
      return () => clearTimeout(timer);
    }
  }, [enabled, hasSeen, startTour]);

  return { startTour, hasSeen, markSeen };
}

export function resetAllTours() {
  Object.values(TOUR_KEYS).forEach((key) => localStorage.removeItem(key));
}
```

**Step 4: Add tour CSS overrides for dark theme**

```css
/* frontend/src/app/globals.css — add at end */
/* Driver.js tour dark theme overrides */
.cataclysm-tour-popover {
  background: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--cata-border) !important;
  border-radius: 0.75rem !important;
  max-width: min(320px, calc(100vw - 2rem)) !important;
}
.cataclysm-tour-popover .driver-popover-title {
  color: var(--text-primary) !important;
  font-size: 1rem !important;
  font-weight: 600 !important;
}
.cataclysm-tour-popover .driver-popover-description {
  color: var(--text-secondary) !important;
  font-size: 0.875rem !important;
  line-height: 1.5 !important;
}
.cataclysm-tour-popover .driver-popover-footer button {
  background: var(--cata-accent) !important;
  color: #000 !important;
  border: none !important;
  border-radius: 0.5rem !important;
  padding: 0.5rem 1rem !important;
  min-height: 44px !important;
  font-weight: 500 !important;
}
.cataclysm-tour-popover .driver-popover-close-btn {
  color: var(--text-secondary) !important;
  min-width: 44px !important;
  min-height: 44px !important;
}
.cataclysm-tour-popover .driver-popover-progress-text {
  color: var(--text-secondary) !important;
}
```

**Step 5: Add `id` attributes to tour target elements**

In each target component, add a stable `id`:

- `SessionReport.tsx` or `PriorityCardsSection.tsx`: `<div id="priority-improvements" ...>`
- `CornerGradesSection.tsx`: `<div id="corner-grades-table" ...>`
- `MobileBottomTabs.tsx`: `<div id="tab-bar" role="tablist" ...>`
- Desktop tab bar (if separate): same `id="tab-bar"`
- `DeepDive.tsx` lap picker area: `<div id="lap-picker" ...>`
- `DeepDive.tsx` sub-tabs: `<div id="deep-dive-tabs" ...>`
- `ProgressView.tsx` trend chart: `<div id="progress-trend-chart" ...>`

**Step 6: Integrate tour triggers**

In `SessionReport.tsx`:
```tsx
import { useTour } from '@/hooks/useTour';

// Inside the component, after data is loaded:
const { } = useTour('report', !!sessionData && !isPending);
```

In `DeepDive.tsx`:
```tsx
const { } = useTour('deepDive', !!sessionData && !isPending);
```

In `ProgressView.tsx`:
```tsx
// Only trigger if user has 2+ sessions
const { } = useTour('progress', sessions.length >= 2 && !isPending);
```

**Step 7: Add "Replay Tour" to Settings**

In `SettingsPanel.tsx`, add a button:
```tsx
import { resetAllTours } from '@/hooks/useTour';

<Button
  variant="ghost"
  size="sm"
  onClick={() => {
    resetAllTours();
    // Optionally close settings and trigger report tour
  }}
>
  Replay Tour
</Button>
```

**Step 8: Write test for tour hook**

```typescript
// frontend/src/hooks/__tests__/useTour.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { resetAllTours } from '../useTour';

describe('tour state', () => {
  beforeEach(() => localStorage.clear());

  it('resetAllTours clears all tour flags', () => {
    localStorage.setItem('cataclysm-tour-report', '1');
    localStorage.setItem('cataclysm-tour-deep-dive', '1');
    resetAllTours();
    expect(localStorage.getItem('cataclysm-tour-report')).toBeNull();
    expect(localStorage.getItem('cataclysm-tour-deep-dive')).toBeNull();
  });
});
```

**Step 9: Run tests + TS check**

```bash
cd frontend && npx vitest run && npx tsc --noEmit
```

**Step 10: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/tour/ frontend/src/hooks/useTour.ts frontend/src/hooks/__tests__/useTour.test.ts frontend/src/app/globals.css [all modified component files]
git commit -m "feat: Driver.js app tour — 3 contextual mini-tours for report, deep dive, progress"
```

---

## Task 5: Share Flow Verification

**Files:**
- Modify: `frontend/src/components/dashboard/ShareButton.tsx` (add `id` for tour, verify visibility)
- Possibly modify: `frontend/src/app/share/[token]/page.tsx` (CTA clarity)
- Test: Playwright E2E (manual, Task 7)

**Context:** Share exists and works. This task verifies discoverability and the conversion funnel on the share page.

**Step 1: Verify share button is visible on report (not buried)**

Read `SessionReportHeader.tsx` and confirm the ShareButton renders prominently. If it's behind a menu or dropdown, surface it. Add `id="share-button"` for tour targeting.

**Step 2: Verify anonymous sharing works**

Test manually: upload as anonymous → click share → copy link → open incognito → link works. If it doesn't, debug the token generation for anonymous users.

**Step 3: Check share page CTA**

Read `frontend/src/app/share/[token]/page.tsx`. The recipient should see:
- Session metadata (track, best lap, date)
- Clear CTA: "Upload your session to compare" or "Try it with your data"
- If CTA is weak or missing, add/improve it

**Step 4: Commit (if any changes)**

```bash
git add [modified files]
git commit -m "fix: share flow discoverability + clearer CTA on share page"
```

---

## Task 6: Onboarding Dead-End Sweep

**Files:**
- Modify: `frontend/src/components/progress/ProgressView.tsx` (empty state CTA)
- Modify: `frontend/src/components/shared/DisclaimerModal.tsx` (timing/length review)
- Possibly modify: Various components (empty states)

**Context:** Every screen needs a clear "what do I do next?" — no blank pages, no confusing dead ends.

**Step 1: Progress tab empty state (single session)**

Read `ProgressView.tsx`. If the empty state for single-session users says only "No trend data", improve to:
```tsx
<EmptyState
  icon={TrendingUp}
  title="Your improvement starts here"
  message="Upload more sessions to see lap time trends, consistency tracking, and corner-by-corner progress."
/>
```

**Step 2: Debrief tab — verify it works on first session**

Read the Debrief component. Confirm it renders something useful with a single session. If it requires multi-session data, add an appropriate message.

**Step 3: Disclaimer modal review**

Read `DisclaimerModal.tsx`. If the text is intimidatingly long:
- Shorten to essential legal content (2-3 short paragraphs)
- Keep the same legal coverage
- Consider showing AFTER WelcomeScreen hero renders (not blocking first visual)

**Step 4: Equipment button clarity**

In `SessionReportHeader.tsx`, if the equipment button text is unclear for new users, change empty-state label to "Add your car (optional)" or similar. Must be clear it's not required.

**Step 5: Commit**

```bash
git add [modified files]
git commit -m "fix: onboarding dead ends — better empty states, clearer CTAs, non-intimidating disclaimer"
```

---

## Task 7: Pre-Trackday Smoke Test (Playwright)

**Files:**
- Create: `frontend/e2e/trackday-readiness.spec.ts` (or run manually via Playwright MCP)

**Context:** Full E2E flow test at mobile viewports. This is verification, not new features. Run AFTER Tasks 1-6 are deployed to staging.

**Step 1: Wait for staging deploy**

After pushing all changes to staging, wait ~2-3 min for Railway to build both services. Verify with:
```bash
railway list-deployments --service frontend
railway list-deployments --service backend
```

Check build logs for any errors.

**Step 2: E2E flow at iPhone 14 (390×844)**

Using Playwright MCP or manual browser testing:

1. Navigate to `https://cataclysm-staging.up.railway.app`
2. Verify WelcomeScreen renders (hero, upload CTA, RaceChrono instructions)
3. Upload a real AMP session CSV
4. Verify ProcessingOverlay shows progress steps
5. Verify SkillLevelPicker appears after processing completes
6. Select a skill level
7. Verify SessionReport renders with:
   - Session score
   - Corner grades with AMP corner names
   - Priority Focus section
8. Verify tour triggers (3 steps on report)
9. Complete tour, verify it doesn't re-trigger on reload
10. Tap a corner grade → verify navigation to Corner Focus
11. Switch to Deep Dive → verify Lap Trace renders
12. Switch to Corner Focus → verify it renders
13. Verify Deep Dive tour triggers (2 steps)
14. Open share → copy link → open in new context → share page loads
15. Switch to Progress tab → verify empty state message
16. Switch to Debrief → verify it renders

**Step 3: Repeat at S24 (360×780)**

Same flow at narrowest viewport. Watch for:
- Text clipping
- Horizontal overflow
- Touch targets too small
- Tour tooltips overlapping target elements
- Tab bar fully visible

**Step 4: Error path tests**

1. Upload a `.txt` file → verify specific error message
2. Upload while offline (network disconnected) → verify timeout message + retry button

**Step 5: Coaching credibility check**

Read the generated coaching report for the AMP session:
- Does it reference corners by name + number? ("Carousel (T4)")
- Does the Primary Focus include specific data? (distances, speeds, time deltas)
- Does it include "why" explanations?
- Does the skill level affect tone appropriately?

**Step 6: Verify DEV_AUTH_BYPASS is NOT set**

```bash
railway variables list --service backend | grep AUTH
```

Must return nothing. If it returns `DEV_AUTH_BYPASS=true`, delete immediately.

**Step 7: Real phone test (your phone)**

Open staging URL on your actual phone. Tap through the full flow once. This catches viewport quirks that Playwright emulation misses.

---

## Execution Order & Dependencies

```
Task 1 (Skill Picker) ──┐
Task 2 (Upload Errors) ──┤
Task 3 (Coaching Prompt) ┤── All independent, can run in parallel
Task 5 (Share Verify) ───┤
Task 6 (Dead-End Sweep) ─┘
         │
         ▼
Task 4 (App Tour) ── depends on IDs from Tasks 1, 5, 6 being in place
         │
         ▼
Task 7 (Smoke Test) ── depends on ALL above deployed to staging
```

**Parallelizable**: Tasks 1, 2, 3, 5, 6 are fully independent.
**Sequential**: Task 4 needs IDs in DOM. Task 7 is the final gate.

**Estimated effort**: ~2-3 days for Tasks 1-6, ~1 day for Task 7 (including deploy wait + real-device testing).

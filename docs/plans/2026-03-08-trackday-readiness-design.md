# Trackday Readiness Design — AMP Beta Test

**Date**: 2026-03-08
**Goal**: Prepare app for 5-10 HPDE friends testing at Atlanta Motorsports Park in <7 days
**Approach**: Bulletproof First Impression — flawless onboarding, credible coaching, zero dead ends

## Context

- **Users**: 5-10 drivers, novice to advanced, mix of RaceChrono users and newcomers
- **GPS**: RaceBox-level (~0.5m) — no phone GPS concerns
- **Logistics**: Mix of hands-on help and self-service (link sent beforehand)
- **Wow moment**: Upload → instant coaching report that sounds like it watched them drive
- **Trust builder**: Specific, data-backed coaching with "why" explanations
- **AMP track**: Fully supported (16 turns, canonical reference, corrected 2026-03-08)

## 1. Skill Level Picker on First Upload

**Problem**: Defaults to "intermediate," buried in Settings. Novice gets advanced jargon; advanced gets patronizing advice.

**Solution**: Lightweight interstitial after ProcessingOverlay completes, before report renders:

- "How many trackdays have you done?" — 3 large tap targets:
  - "Less than 5" → novice
  - "5 – 20" → intermediate
  - "More than 20" → advanced
- One tap, persists to localStorage + backend (triggers coaching at correct skill level)
- Shows once (localStorage flag `cataclysm-skill-level-set`)
- Subtitle: "This adjusts your coaching and which features we show you."

## 2. Upload Flow Hardening

**Problem**: Generic "check your CSV format" errors, no retry button, no pre-upload validation.

**Changes**:
- **Client-side validation**: Check `.csv` extension + peek at first line for RaceChrono headers before upload
- **Specific error messages**:
  - Wrong format: "This doesn't look like a RaceChrono CSV" + link to export instructions
  - No laps: "No laps detected — was the session shorter than 1 lap?"
  - Network timeout: "Upload interrupted — check your connection and try again"
- **Retry button** in ProcessingOverlay error state (currently must dismiss and start over)
- **Not doing**: Real-time server progress streaming, non-RaceChrono format support

## 3. Coaching Language & Credibility

**Problem**: Coaching must sound like it watched them drive, not like a generic AI summary.

**Changes**:
- **Audit coaching prompt** for specificity — ensure it includes:
  - Concrete numbers from their data ("you braked 12m before the apex")
  - AMP corner names with turn numbers: "Carousel (T5)", not "corner 5"
  - "Why" explanations: "Braking earlier here costs 0.3s because you scrub speed through mid-corner"
- **Skill-level-appropriate language**:
  - Novice: "Try moving your braking point 2 car lengths closer each session"
  - Intermediate: "Your trail-braking release is abrupt — smoother transition carries 3 km/h more"
  - Advanced: "0.18s lost to early throttle application; lateral grip budget shows room for 2° more steering lock"
- **Priority Focus** leads with single biggest time gain, framed as actionable
- **Not doing**: Changing model (Haiku), adding coaching regen UI, video/animation

## 4. Mobile Polish & Full-Flow Verification

**Problem**: Individual screens QA'd, but no continuous end-to-end flow test on mobile.

**Changes**:
- Full-flow Playwright test at 390px (iPhone14) and 360px (S24):
  - Welcome → upload → skill picker → report → corner tap → Deep Dive → share → Settings
- Touch target audit (≥44px on all tappable elements)
- Loading state verification: no blank screens, no layout jumps, pulse animation on recomputing values
- **Not doing**: Layout redesigns, physical phone testing, offline support

## 5. Share Flow & Social Proof

**Problem**: Share exists but discoverability and share-page conversion need verification.

**Changes**:
- Verify share button is visible on report page (not buried in menu)
- Share works for anonymous users (no sign-in gate)
- Share page shows enough to impress + clear CTA: "Upload your session to compare"
- Test: tap share → "Link copied!" toast → open in incognito → page renders
- **Not doing**: Driver-to-driver overlay comparison, leaderboards, social auth pressure

## 6. Guided App Tour

**Research**: 3-step tours hit 72% completion (Chameleon 2025 Benchmark). Beyond 5 steps, most bail. Contextual > upfront. Always skippable, always re-triggerable.

**Library**: Driver.js — lightweight, MIT, framework-agnostic, best mobile positioning, actively maintained. Dynamic import (zero cost for returning users).

### Three Contextual Mini-Tours

**Tour 1: "Your Report"** (after first upload + skill picker, 3 steps):
1. Priority Focus card → "Start here — your biggest opportunity this session. The AI coach explains what happened and why."
2. Corner Grades → "Tap any corner to see your speed analysis and coaching for that turn."
3. Bottom tab bar → "Deep Dive shows lap traces. Progress tracks improvement. Explore when ready."

**Tour 2: "Deep Dive"** (first time opening tab, 2 steps):
1. Lap picker → "Select one or two laps to compare. Your fastest is pre-selected."
2. Sub-tabs → "Lap Trace = speed through the whole lap. Corner Focus = zoom into one turn."

**Tour 3: "Progress"** (first time, only if 2+ sessions, 1 step):
1. Lap time trend → "Each session builds your improvement timeline. More data = better insights."

### Implementation Details
- Target elements via `data-tour="step-id"` attributes (stable, not CSS selectors)
- State: Zustand store → localStorage: `{ reportTourSeen, deepDiveTourSeen, progressTourSeen }`
- Skip: every step has visible "Skip" button (≥44px touch target)
- Re-trigger: "Replay tour" button in Settings
- Mobile-first: content for 360px, positioned above/below (never overlapping target)
- Skill-aware: tour text references skill level (novice: "how you're doing"; advanced: "braking, trail-brake, apex speed, exit")
- **Not doing**: Blocking modals, interactive "click this" steps, tour on Welcome/Settings/Equipment

## 7. Pre-Trackday Smoke Test

### 7a. E2E Flow (Playwright, mobile viewports)
- Anonymous: welcome → upload real AMP CSV → skill picker → report → tour → corner tap → Deep Dive → share → Progress empty state → Debrief
- At 360px and 390px viewports

### 7b. Error Paths
- Non-CSV file → specific error + instructions link
- 0-lap CSV → appropriate message
- Network kill mid-upload → timeout + retry button

### 7c. Staging Deploy
- Push → Railway build passes → check logs for frontend + backend
- Verify `DEV_AUTH_BYPASS` not set
- Hit staging URL on real phone

### 7d. Real Data Validation
- 2+ real AMP sessions (different cars/drivers)
- Corner names match AMP 16-turn layout
- Coaching report reads as specific and credible

## Scope Summary

| Section | What | Effort |
|---------|------|--------|
| 1. Skill Level Picker | New component, 3 buttons, persist | Small |
| 2. Upload Hardening | Client validation, error messages, retry | Small |
| 3. Coaching Credibility | Prompt audit, specificity, corner names | Medium |
| 4. Mobile Polish | Full-flow Playwright verification | Medium |
| 5. Share Flow | Discoverability + share page CTA | Small |
| 6. App Tour | Driver.js, 3 contextual mini-tours | Medium |
| 7. Smoke Test | E2E verification | Medium |

No new backend infrastructure. No new pages. Polish + one component (skill picker) + one library (Driver.js) + coaching prompt audit.

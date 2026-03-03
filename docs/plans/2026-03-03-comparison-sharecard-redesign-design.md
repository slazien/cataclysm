# Comparison Results + Share Card Redesign

**Date**: 2026-03-03
**Status**: Approved

## Overview

Two related redesigns:
1. **Share Card (PNG export)** — Spotify Wrapped / identity-focused style replacing the current data-heavy layout
2. **Comparison Results** — Two-tier summary + deep dive replacing the overwhelming corner-by-corner table

## Identity Label System (shared)

Both features use personality-driven labels derived from skill dimensions (`skillDimensions.ts`).

| Highest Dimension | Labels (random from pool) |
|---|---|
| Braking | LATE BRAKER, BRAKE BOSS |
| Trail Braking | TRAIL WIZARD, SMOOTH OPERATOR |
| Throttle | THROTTLE KING, POWER PLAYER |
| Line | LINE MASTER, APEX HUNTER |
| Balanced (all within 10pts) | COMPLETE DRIVER, WELL ROUNDED |
| No data | TRACK WARRIOR |

New function: `getIdentityLabel(dimensions)` in `skillDimensions.ts`.

## Feature A: Share Card Redesign

### Layout (1080x1920, 9:16)

```
┌──────────────────────────┐
│                          │
│  Barber Motorsports Park │  ← track name, 28px
│  Mar 3, 2026             │  ← date
│                          │
│   [track outline glow]   │  ← track SVG path, blurred,
│                          │     low opacity decorative bg
│                          │
│   ══════════════════     │
│   SMOOTH OPERATOR        │  ← 96px bold, identity label
│   ══════════════════     │
│                          │
│       ┌─────────┐        │
│       │  8.4    │        │  ← score ring, r=100,
│       │  /10    │        │     thick stroke with glow
│       └─────────┘        │
│                          │
│   1:42.31  best lap      │  ← 48px, primary stat
│                          │
│  ┌──────┐ ┌──────┐      │
│  │ 12   │ │ 94%  │      │  ← stat pills (2-3)
│  │ laps │ │ cons │      │     rounded rect badges
│  └──────┘ └──────┘      │
│                          │
│  ─── cataclysm.app ───  │  ← footer CTA
└──────────────────────────┘
```

### Visual Style
- Dark gradient background (#0a0a1a → #1a1a2e)
- Track outline as decorative glow (stroke with gaussian blur, 15% opacity, accent color)
- Score ring: thick arc stroke (12px), accent color gradient, subtle outer glow
- Stat pills: rounded rect with frosted glass effect (semi-transparent bg + border)
- Subtle grain texture overlay (noise pattern at 3% opacity)
- No AI insight box (too text-heavy for a share image)

### Files Changed
- **Rewrite** `frontend/src/lib/shareCardRenderer.ts` — new identity-focused layout
- **Add** `getIdentityLabel()` to `frontend/src/lib/skillDimensions.ts`
- **Minor update** `frontend/src/hooks/useShareCard.ts` — pass identity label to renderer

## Feature B: Comparison Results Redesign

### Auth: Fully public (no auth required for share link recipient)

### Tier 1: Summary Card

Shown immediately after friend uploads CSV and comparison completes.

```
┌─────────────────────────────────────┐
│  🏆  Alex wins by 2.3s             │  ← winner banner
│  Barber Motorsports Park            │
├─────────────────────────────────────┤
│                                     │
│  [track map with delta-t color]     │  ← track outline colored
│                                     │     green/red by who's faster
├─────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌──────┐  │
│  │ -2.3s   │ │ 3 of 5  │ │ 8.4  │  │  ← stat pills:
│  │ gap     │ │corners  │ │vs 7.1│  │     gap, corners won,
│  │         │ │  won    │ │score │  │     score comparison
│  └─────────┘ └─────────┘ └──────┘  │
├─────────────────────────────────────┤
│  "Alex carries more speed through   │  ← 1-sentence AI verdict
│   mid-corner but Jordan brakes      │
│   later into T5"                    │
├─────────────────────────────────────┤
│       [ 🔍 Deep Dive ]              │  ← expand button
└─────────────────────────────────────┘
```

**Data sources (existing from `compare_sessions()`):**
- Winner + gap: `best_lap_time_s` comparison
- Corners won: count from `corner_deltas` where `delta_s < 0`
- Track map delta-t: `delta_time_s[]` mapped to GPS path
- Score: from coaching reports

**New:** `ai_verdict` — 1-sentence Claude Haiku summary added to comparison response.

### Tier 2: Deep Dive (inline expand)

Clicking "Deep Dive" expands inline (no page navigation):

1. **Delta-T Chart** — reuse existing `DeltaChart` from deep dive tab
   - X: distance, Y: cumulative time delta
   - Data: `delta_time_s[]` from `compare_sessions()`

2. **Speed Trace Overlay** — new D3 dual-line chart
   - Both drivers' speed vs distance on same axes
   - Color-coded (Driver A = accent, Driver B = secondary)
   - Data: new `speed_traces` field in comparison response

3. **Skill Radar Comparison** — two overlaid radar charts
   - Reuse `SkillRadar` component
   - 4 axes: Braking, Trail Braking, Throttle, Line
   - Data: new `skill_dimensions` field in comparison response

4. **AI Coach Narrative** — 3-4 paragraph comparison analysis
   - Structured: braking, corner entry, where each driver gains
   - Generated by Claude Haiku, cached with share token
   - New endpoint: `POST /api/sharing/{token}/ai-comparison`

5. **Corner Table** — existing corner-by-corner stats (moved here from current top-level)

## Backend Changes

### `backend/api/services/comparison.py`
- Add `speed_traces` to response: speed vs distance arrays for both sessions
- Add `skill_dimensions` for both drivers (compute from coaching report corner grades)
- Add `ai_verdict`: 1-sentence Haiku summary

### New endpoint: `POST /api/sharing/{token}/ai-comparison`
- Generates detailed 3-4 paragraph comparison narrative
- Uses Claude Haiku (same model as coaching reports)
- Cached in DB keyed by share token (immutable once generated)
- No auth required (public share link)

### `backend/api/routers/sharing.py`
- Extend comparison response Pydantic model with new fields

## Frontend Changes

| File | Change |
|---|---|
| `shareCardRenderer.ts` | Complete rewrite — identity-focused layout |
| `skillDimensions.ts` | Add `getIdentityLabel()` function |
| `ComparisonResults.tsx` | Replace with two-tier summary + deep dive |
| New: `ComparisonSummary.tsx` | Winner banner, stat pills, track delta map, AI verdict |
| New: `ComparisonDeepDive.tsx` | Delta chart, speed overlay, radar, AI narrative, corner table |
| New: `SpeedTraceOverlay.tsx` | D3 dual-line speed chart |
| `useShareCard.ts` | Minor: pass identity label to renderer |

## Out of Scope
- No separate page for deep dive (inline expand keeps context)
- No video/animation in share card (static PNG only)
- No comparison share card (only session share card redesigned)
- No social login for comparison (fully public)
- No leaderboard integration in comparison view

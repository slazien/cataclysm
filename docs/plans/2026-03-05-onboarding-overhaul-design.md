# Onboarding Overhaul Design

**Date:** 2026-03-05
**Status:** Approved
**Goal:** First session to "wow" in under 60 seconds. No sign-up required.

---

## Problem

The current onboarding flow has three friction points:

1. **Sign-in wall** — Google auth is required before seeing any value. Users who aren't sure about the product bounce before trying it.
2. **WelcomeScreen doesn't sell** — generic value prop cards and text. No visual demonstration of what the product actually does.
3. **Report is overwhelming** — after upload, the Report tab dumps 8+ sections at once: coaching summary, priority corners, corner grades, patterns, drills, lap times, raw data. First-time users don't know where to focus.

---

## Design

### 1. Anonymous Upload Flow

**Current:** Sign in required -> WelcomeScreen -> Upload -> Report

**New:** WelcomeScreen -> Upload (no auth) -> Report renders -> "Sign in to save" banner

**How it works:**
- Anonymous users get a temporary session stored in-memory on the backend (not persisted to Postgres).
- The session ID is stored in the browser's localStorage so they can navigate tabs.
- Coaching report generates normally (~$0.04 per report — acceptable conversion cost).
- Anonymous sessions expire after 24 hours server-side.
- When user signs in, the anonymous session is "claimed" — migrated to their account and persisted to Postgres.
- If they leave without signing in, the session is lost. This is the gate: "sign in to keep this."

**Rate limiting:**
- 3 anonymous sessions per IP per 24 hours. Matches the free trial limit and prevents abuse of Claude API budget.
- Global daily budget cap: 50 anonymous reports/day ($2/day max). Hard stop — returns a friendly "we're at capacity, sign in for guaranteed access" message. Prevents runaway costs from VPN/proxy abuse regardless of IP limits.

### 2. WelcomeScreen Redesign

**Goal:** Make a first-time visitor think "I want to try this right now" within 5 seconds.

**Layout (top to bottom):**

**Hero section:**
- Tagline: "Your fastest lap is next."
- Subtitle: "Upload your telemetry. Get AI coaching in seconds."
- Giant "Upload CSV" button (primary, amber) + drag-drop zone.
- Below the CTA: "No sign-up required. See your coaching report instantly."

**Sample report screenshot:**
- A real screenshot of a coaching report (Barber Motorsports Park) — score circle, #1 focus, corner grades, track map.
- Caption: "Here's what Cataclysm does with your data"

**Social proof strip:**
- Dynamic stats once we have users: "X sessions analyzed", "Drivers improve by 0.5s on average"
- Before real stats: 2-3 short testimonial-style quotes (from own testing initially, replaced with real ones later).

**How it works (3 steps):**
- Step 1: Upload your RaceChrono CSV
- Step 2: AI analyzes every corner
- Step 3: Get a personalized coaching report

**Supported formats:**
- Small logos/icons: "Works with RaceChrono" (and future formats as added).
- Collapsible export instructions (existing, moved lower).

**What's removed:**
- Value proposition cards (replaced by the screenshot which shows, not tells).
- Recent sessions list (moves to post-auth experience only).

### 3. Progressive Report

**Goal:** First-time user sees score + top priority immediately. Everything else available but not overwhelming.

**Always visible (the "answer" + trust evidence):**
1. **Session score** — big circle, color-coded, impossible to miss.
2. **#1 Focus area** — the single most important thing to work on, with data reference ("Brake 15m later at Turn 5 — you're leaving 0.4s on the table"). Includes a one-line methodology citation: "Based on Allen Berg corner prioritization."
3. **Track map** — best lap visualized, with the priority corner highlighted.
4. **Corner grades (compact)** — single horizontal row of letter grades (T1: B, T2: A, T3: C...). ~50px height. Serves as trust evidence — user sees the data backing the #1 Focus recommendation without needing to click.
5. **Lap times (compact)** — thin sparkline or mini bar chart showing lap time progression. ~40px height. Every driver's first instinct is "what were my lap times?" — meet that expectation.

**Collapsed sections (expand on click):**
6. Coaching summary (full text) — header shows lead sentence only. Requires reading time, better for later review.
7. Patterns & drills — header shows count: "2 patterns identified". Requires reflection, not paddock reading.
8. Raw data table — power user feature, always collapsed.

**Design principle:** Keep visible what's glanceable (grades, sparklines) or trust-building (evidence for the AI recommendation). Collapse what requires reading time or reflection (full coaching text, drills).

**First-time highlights:**
- Subtle pulsing glow on the session score circle (one-time, fades after 3 seconds).
- Small "NEW" dot on the #1 Focus card.
- Tracked via localStorage flag `cataclysm_first_report_seen`.
- No overlay, no tour, no blocking interaction.

**Returning users:**
- Same progressive layout, but sections remember their expand/collapse state per user (localStorage).
- Power users who always expand everything see everything expanded automatically.

### 4. Auth Prompts & Session Claiming

**Soft nudges at value moments (never blocking):**

| Trigger | Prompt style |
|---|---|
| Report loads (anonymous) | Top banner: "Sign in to save this session" |
| Click "Progress" tab | Tab shows: "Sign in to track progress across sessions" |
| Click "Share" | Modal: "Sign in to share your results" |
| Click coaching chat | Inline: "Sign in to chat with your AI coach" |
| Try to upload a 2nd session | Upload zone: "Sign in to analyze more sessions" |

**Session claiming flow:**
1. User clicks "Sign in" from any prompt -> Google OAuth flow.
2. On auth callback, frontend sends `POST /api/sessions/claim` with anonymous session ID from localStorage.
3. Backend migrates the session from in-memory to the user's account in Postgres.
4. Coaching report is preserved (no re-generation needed).
5. User lands back on their report, now with full account features unlocked.

**Edge cases:**
- Anonymous session expired before sign-in -> "Your session expired. Upload again to get started." (acceptable loss).
- User already has an account with sessions -> claimed session joins their existing history.
- Multiple anonymous sessions (shouldn't happen since 2nd upload requires auth) -> claim the one in localStorage.

---

## User Journey (New)

```
Land on WelcomeScreen
  -> "wow, I want that" (screenshot + social proof)
  -> Upload CSV (no sign-up required)
  -> ProcessingOverlay (progress bar + steps)
  -> Score + #1 Focus + Track Map + Corner Grades + Lap Times (instant value + trust evidence)
  -> "Sign in to save this" (soft banner)
  -> Google OAuth -> session claimed -> full experience unlocked
```

---

## What Changes

| Component | Change |
|---|---|
| `WelcomeScreen.tsx` | Full redesign: hero + screenshot + social proof + 3-step |
| `SessionReport.tsx` | Progressive disclosure: collapse sections, show score + focus first |
| `CoachingSummaryHero.tsx` | Extract #1 focus as standalone visible element |
| `ViewRouter.tsx` | Allow rendering without auth (anonymous session support) |
| `TopBar.tsx` | Show auth banner for anonymous users |
| `page.tsx` | Remove auth gate for initial upload flow |
| Backend: `main.py` | New route: `POST /api/sessions/claim` |
| Backend: `session_store.py` | Anonymous session storage (in-memory, 24hr TTL) |
| Backend: `dependencies.py` | `get_optional_user()` dependency for anonymous-allowed endpoints |
| Backend: upload route | Accept anonymous uploads, rate limit by IP |
| Middleware | Relax auth requirement for upload + analysis endpoints |

---

## Out of Scope

- Mobile-specific redesign (separate effort, priority #2)
- New data format support (priority #3)
- Share card redesign (priority #4)
- Monetization/paywall (after PMF validation)
- Onboarding email sequences or push notifications

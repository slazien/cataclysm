# Timezone-Aware Date Handling

**Status:** Approved  
**Date:** 2026-03-30

## Problem

Session dates are stored as UTC but displayed as-is, causing:
1. Times shown are UTC, not local track time (e.g., 12:31 instead of 8:31 AM EDT for Roebling)
2. `session_date` returned as DD/MM/YYYY string — JS `Date()` parses incorrectly (month/day swap, Invalid Date for days >12)
3. `session_date_local` field exists in schema but is never populated
4. `timezone_utils.py` has complete timezone resolution code but is unused in production

## Design

### Data Flow

```
CSV (UTC DD/MM/YYYY) → parser → pipeline (resolve timezone from GPS)
  → DB (DateTime UTC) + snapshot_json (timezone_name, session_date_local)
  → API (session_date=ISO, session_date_local="Mar 21, 2026 · 8:31 AM EDT")
  → Frontend (display session_date_local, parse session_date for grouping/sorting)
```

### Display Format

`Mar 21, 2026 · 8:31 AM EDT`

Used everywhere: session drawer, top bar breadcrumb, report header, share cards, progress charts, comparison selector.

### Section 1: Backend Serialization

Three serialization paths in `backend/api/routers/sessions.py` (lines 639, 694, 758):

**`session_date`** — always ISO 8601 UTC:
- In-memory path: parse `metadata.session_date` (DD/MM/YYYY HH:MM) via `_parse_session_date()` from `trends.py` → `.isoformat()`
- DB fallback path: `row.session_date.isoformat()`

**`session_date_local`** — human-readable local time:
- Resolve timezone from session GPS or track center coords
- Convert via updated `localize_session_date()` → `"Mar 21, 2026 · 8:31 AM EDT"` format
- Store in `snapshot_json` at upload time for restart survival
- DB fallback: lazy resolve from track coords if missing from snapshot

Also update in:
- `backend/api/routers/coaching.py` (lines 680, 722)
- `backend/api/routers/sharing.py` (lines 191-196, 252)

### Section 2: Timezone Resolution

**Where:** Pipeline, after parsing — GPS data is available.

**Resolution:**
1. First valid `(lat, lon)` from parsed telemetry DataFrame
2. `get_timezone_name(lat, lon)` → IANA name (e.g., `"America/New_York"`)
3. Store `timezone_name` in session snapshot (new key in `snapshot_json`)

**Fallback chain:**
1. GPS from telemetry (99% of cases)
2. Track center coords from `track_db.py` (if telemetry GPS missing)
3. Both fail → `session_date_local = None`, frontend shows ISO `session_date`

**Performance:** `timezonefinder` lookup ~1ms with in-memory mode (already configured as lazy singleton). No additional caching needed.

**No DB migration:** `timezone_name` stored in existing `snapshot_json` JSON blob.

### Section 3: Frontend Changes

**New `formatSessionDate()`** in `frontend/src/lib/formatters.ts`:
- Input: ISO string + optional timezone abbreviation
- Output: `"Mar 21, 2026 · 8:31 AM EDT"`
- Uses `Intl.DateTimeFormat` for locale-aware month names

**`getDateCategory()`** in `SessionDrawer.tsx`:
- Receives ISO strings → `new Date()` works natively
- Remove DD/MM/YYYY regex parsing (was a bandaid)

**`parseSessionDate()`** in `formatters.ts`:
- Update to parse ISO format instead of DD/MM/YYYY
- Keep DD/MM/YYYY fallback temporarily for cached responses

**Display surfaces** (all already use `session_date_local ?? session_date`):
- `SessionDrawer.tsx:247` — session list
- `TopBar.tsx:282` — breadcrumb
- `SessionReportHeader.tsx:146` — report header
- `TracksideCard.tsx:44,91` — share card
- `SessionSelector.tsx:104,151` — needs updating to prefer `session_date_local`

**Progress charts** (use `parseSessionDate()`):
- MilestoneTimeline, ProgressView, SessionBoxPlot, CornerHeatmap, SkillRadarEvolution
- Chart date labels → shorter format like `"Mar 21"`

**No timezone conversion in browser** — backend does all conversion.

### Section 4: Migration Safety

- **No DB migration**: `session_date` column unchanged (`DateTime(timezone=True)`). New data goes in `snapshot_json`.
- **Backwards compat**: Old sessions without `timezone_name` in snapshot → lazy resolve from track coords at response time (~1ms).
- **Frontend cache**: Old cached responses have DD/MM/YYYY `session_date` and `null` `session_date_local`. Fallback in `parseDateStr` handles DD/MM/YYYY for ~60s cache TTL. Display pattern `session_date_local ?? session_date` renders old responses fine.
- **Coaching/sharing routes**: Same pattern — ISO `session_date`, formatted `session_date_local`.

## Files Modified

### Backend
- `cataclysm/timezone_utils.py` — update `localize_session_date()` output format
- `backend/api/routers/sessions.py` — 3 serialization paths (lines 639, 694, 758)
- `backend/api/routers/coaching.py` — 2 paths (lines 680, 722) + `ReportContent` for PDF
- `backend/api/routers/sharing.py` — 2 paths (lines 191-196, 252)
- `backend/api/services/pipeline.py` — resolve timezone, store in snapshot
- `cataclysm/pdf_report.py` — `ReportContent.session_date` used in PDF header, should show local time

### Frontend
- `frontend/src/lib/formatters.ts` — new `formatSessionDate()`, update `parseSessionDate()`
- `frontend/src/components/navigation/SessionDrawer.tsx` — simplify `getDateCategory()`
- `frontend/src/components/comparison/SessionSelector.tsx` — use `session_date_local`

### Tests
- `tests/test_timezone_utils.py` — update for new output format
- `backend/tests/` — update session response assertions for ISO format
- `frontend/src/lib/formatters.test.ts` — tests for new formatting functions

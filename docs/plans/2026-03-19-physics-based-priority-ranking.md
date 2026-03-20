# Physics-Based Priority Corner Ranking

**Date**: 2026-03-19
**Status**: Approved

## Problem

Report and Debrief tabs show different "priority corners" despite both consuming `report.priority_corners` from the same coaching report. Root cause: the LLM re-estimates corner rankings and `time_cost_s` values that the physics engine already computed deterministically. The LLM receives physics data as input, then re-guesses — producing divergent rankings.

## Solution

Use physics `corner_opportunities` (from optimal comparison) as single source of truth for corner ranking and time costs. LLM provides coaching text only (issue, tip). Fallback to LLM-ranked data when physics unavailable.

## Design

### 1. Backend Prompt Change (`cataclysm/coaching.py`)

- Pre-select top N corners from `OptimalComparisonResult.corner_opportunities` (sorted by `time_cost_s` desc)
- N = `max_priorities` (novice:2, intermediate:3, advanced:4)
- Tell LLM explicitly which corners to write about with their physics data
- Remove: "estimate time_cost_s", "sort by time_cost_s", "identify corners with largest improvement"
- `time_cost_s` dropped from JSON schema request
- Fallback: when `OptimalComparisonResult` unavailable, use current prompt (LLM identifies and ranks)

### 2. Backend Router Change (`backend/api/routers/coaching.py`)

- Remove `_sanitize_priority_time_cost()` function (dead code)
- Remove `per_corner_caps` / `session_cap_s` computation block
- Remove re-sort of priority_corners (LLM told not to reorder)
- Keep `_parse_priority_corner_number()` (still needed)
- `PriorityCornerSchema.time_cost_s` stays (default 0.0) for backward compat

### 3. Frontend Hook (`hooks/useMergedPriorities.ts`)

```typescript
function useMergedPriorities(
  report: CoachingReport | undefined,
  optimalComparison: OptimalComparisonData | undefined,
  maxCorners: number,
): MergedPriority[]
```

Logic:
1. If `corner_opportunities` available: take top `maxCorners`, match to `priority_corners` by corner number for `issue`/`tip` text. Physics provides `time_cost_s`.
2. Else: fallback to `report.priority_corners.slice(0, maxCorners)` as-is.

```typescript
interface MergedPriority {
  corner: number;
  time_cost_s: number;
  issue: string | null;
  tip: string | null;
  source: 'physics' | 'llm';
  speed_gap_mph: number | null;
  brake_gap_m: number | null;
  exit_straight_time_cost_s: number | null;
}
```

### 4. Frontend Component Changes

- **`PriorityCardsSection`**: receives `MergedPriority[]`. Drops `liveTimeCost` overlay, `optimalComparison` prop, `isOptimalRefreshing` prop. Null `tip`/`issue` → show speed/brake gap data.
- **`TimeLossCorners`**: receives `MergedPriority[]`. Header → dynamic `Top {corners.length} Focus`.
- **`NextSessionFocus`**: receives `MergedPriority`.
- **`TracksideCard`**: receives `MergedPriority[]`.
- **`SessionReport`**: calls `useMergedPriorities(report, optimalComparison, 3)`.
- **`PitLaneDebrief`**: calls `useMergedPriorities(report, optimalComparison, maxCorners)`.

### 5. Edge Cases

- **Cached reports**: LLM `time_cost_s` still works via fallback (`source: 'llm'`). No migration.
- **Physics unavailable**: falls back to current behavior automatically.
- **Equipment switch**: both caches cleared → regen with fresh physics data.
- **Corner text mismatch**: prompt requests exact corners → rare. Null `issue`/`tip` handled in UI.
- **Fewer corners than maxCorners**: `.slice()` handles naturally.

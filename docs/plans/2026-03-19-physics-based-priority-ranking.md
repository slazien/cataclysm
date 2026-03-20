# Physics-Based Priority Corner Ranking — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace LLM-estimated corner priority ranking with physics-based ranking from `corner_opportunities`, using LLM for coaching text only.

**Architecture:** Backend prompt tells LLM which specific corners to write about (physics-ranked). Frontend `useMergedPriorities` hook merges physics ranking + LLM coaching text. Fallback to LLM-only when physics unavailable.

**Tech Stack:** Python (coaching.py prompt), FastAPI (coaching router), React/TypeScript (hook + 6 components)

---

### Task 1: Backend — Modify coaching prompt to use physics-ranked corners

**Files:**
- Modify: `cataclysm/coaching.py:1009-1011` (max_priorities map)
- Modify: `cataclysm/coaching.py:1067-1074` (priority_corners JSON schema in prompt)
- Modify: `cataclysm/coaching.py:1118-1122` (sort/identify instructions)
- Modify: `cataclysm/coaching.py:832-853` (`_build_coaching_prompt` signature — already has `optimal_comparison`)

**Step 1: Add helper to build physics-ranked corner instruction**

In `cataclysm/coaching.py`, add a function near `_format_optimal_comparison` (~line 462):

```python
def _build_priority_corner_instruction(
    optimal: OptimalComparisonResult,
    max_priorities: int,
) -> str:
    """Build explicit corner list for priority_corners based on physics ranking."""
    top = [
        opp for opp in optimal.corner_opportunities[:max_priorities]
        if opp.time_cost_s > 0
    ]
    if not top:
        return ""
    lines = [
        "Write coaching text for these specific priority corners "
        "(ranked by physics time loss — do NOT reorder, add, or remove corners):",
    ]
    for opp in top:
        brake_info = ""
        if opp.brake_gap_m is not None and abs(opp.brake_gap_m) > 0.5:
            direction = "early" if opp.brake_gap_m < 0 else "late"
            brake_info = f", brakes {abs(opp.brake_gap_m):.0f}m {direction}"
        lines.append(
            f"- T{opp.corner_number} ({opp.time_cost_s:.2f}s time cost, "
            f"{opp.speed_gap_mph:+.1f} mph gap{brake_info})"
        )
    return "\n".join(lines)
```

**Step 2: Modify `_build_coaching_prompt` to inject physics-ranked corners**

In `_build_coaching_prompt`, after line ~908 (optimal_instruction), add logic to build the priority corner instruction:

```python
    priority_corner_instruction = ""
    if optimal_comparison is not None:
        priority_corner_instruction = _build_priority_corner_instruction(
            optimal_comparison, max_priorities,
        )
```

**Step 3: Modify the JSON schema in the prompt**

Change lines 1067-1074 from:

```python
  "priority_corners": [
    {{
      "corner": <number>,
      "time_cost_s": <estimated avg time lost vs best lap at this corner>,
      "issue": "<what the data shows across all laps — include root cause chain>",
      "tip": "<MUST name the corner ...>"
    }}
  ],
```

To (conditionally, when physics is available):

```python
  "priority_corners": [
    {{
      "corner": <corner number from the list above>,
      "issue": "<what the data shows across all laps — include root cause chain>",
      "tip": "<MUST name the corner (T# or name+number) in the first sentence. \
Actionable advice with 'because' clause and what the driver will FEEL>"
    }}
  ],
```

When physics is NOT available (fallback), keep the current schema including `time_cost_s`.

**Step 4: Replace lines 1118-1122 with conditional instruction**

When physics available, replace with:
```
{priority_corner_instruction}

For each corner listed above, provide coaching text with ONE specific actionable change \
and a "because" clause explaining why. Use the exact corner numbers listed above — \
do NOT reorder, add, or remove corners.
```

When physics unavailable, keep existing text:
```
Sort priority_corners by time_cost_s descending (biggest avg time loss first).
Identify the {max_priorities} corners with the largest improvement opportunity. ...
```

**Step 5: Run tests**

Run: `pytest tests/test_coaching.py -v -x`
Expected: PASS (existing tests should still parse both old and new format)

**Step 6: Commit**

```bash
git add cataclysm/coaching.py
git commit -m "feat: use physics-ranked corners in coaching prompt"
```

---

### Task 2: Backend — Clean up coaching router (remove sanitize/re-sort)

**Files:**
- Modify: `backend/api/routers/coaching.py:161` (remove `_ABSOLUTE_PRIORITY_TIME_CAP_S`)
- Modify: `backend/api/routers/coaching.py:186-207` (remove `_sanitize_priority_time_cost`)
- Modify: `backend/api/routers/coaching.py:523-554` (simplify priority_corners assembly)

**Step 1: Simplify priority_corners assembly**

Replace lines 523-554:

```python
        # --- old code ---
        priority_corners = []
        per_corner_caps = (...)
        session_cap_s = (...)
        for pc in report.priority_corners:
            corner_num = _parse_priority_corner_number(pc.get("corner", 0))
            priority_corners.append(
                PriorityCornerSchema(
                    corner=corner_num,
                    time_cost_s=_sanitize_priority_time_cost(...),
                    issue=str(pc.get("issue", "")),
                    tip=str(pc.get("tip", "")),
                )
            )
        priority_corners.sort(key=lambda pc: (-pc.time_cost_s, pc.corner))
```

With:

```python
        # --- new code ---
        priority_corners = [
            PriorityCornerSchema(
                corner=_parse_priority_corner_number(pc.get("corner", 0)),
                time_cost_s=pc.get("time_cost_s", 0.0),
                issue=str(pc.get("issue", "")),
                tip=str(pc.get("tip", "")),
            )
            for pc in report.priority_corners
        ]
```

No re-sorting — order comes from the prompt (physics-ranked) or LLM (fallback).
`time_cost_s` passes through as-is via `PriorityCornerSchema` validator (clamps negatives to 0).

**Step 2: Remove dead code**

Delete `_ABSOLUTE_PRIORITY_TIME_CAP_S` (line 161) and `_sanitize_priority_time_cost` function (lines 186-207).

**Step 3: Run backend tests**

Run: `pytest backend/tests/test_coaching.py backend/tests/test_coaching_extended.py -v -x`
Expected: PASS

**Step 4: Run quality gates**

Run: `ruff check backend/ && dmypy run -- backend/`
Expected: Clean

**Step 5: Commit**

```bash
git add backend/api/routers/coaching.py
git commit -m "refactor: remove LLM time-cost sanitization, use physics ordering"
```

---

### Task 3: Frontend — Add `MergedPriority` type and `useMergedPriorities` hook

**Files:**
- Modify: `frontend/src/lib/types.ts:149-154` (add `MergedPriority` interface)
- Create: `frontend/src/hooks/useMergedPriorities.ts`

**Step 1: Add `MergedPriority` type**

In `frontend/src/lib/types.ts`, after the `PriorityCorner` interface (~line 154), add:

```typescript
export interface MergedPriority {
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

**Step 2: Create `useMergedPriorities` hook**

Create `frontend/src/hooks/useMergedPriorities.ts`:

```typescript
import { useMemo } from 'react';
import type { CoachingReport, OptimalComparisonData, MergedPriority } from '@/lib/types';

/**
 * Merge physics-ranked corner_opportunities with LLM coaching text.
 * Physics provides ranking + time costs; LLM provides issue/tip text.
 * Falls back to LLM-only priority_corners when physics unavailable.
 */
export function useMergedPriorities(
  report: CoachingReport | undefined,
  optimalComparison: OptimalComparisonData | undefined,
  maxCorners: number,
): MergedPriority[] {
  return useMemo(() => {
    if (!report) return [];

    const opportunities = optimalComparison?.corner_opportunities;
    const priorities = report.priority_corners;

    // Physics path: rank by corner_opportunities, attach LLM text
    if (opportunities && opportunities.length > 0) {
      const priorityMap = new Map(
        priorities?.map((p) => [p.corner, p]) ?? [],
      );
      return opportunities.slice(0, maxCorners).map((opp) => {
        const llm = priorityMap.get(opp.corner_number);
        return {
          corner: opp.corner_number,
          time_cost_s: opp.time_cost_s,
          issue: llm?.issue ?? null,
          tip: llm?.tip ?? null,
          source: 'physics' as const,
          speed_gap_mph: opp.speed_gap_mph,
          brake_gap_m: opp.brake_gap_m ?? null,
          exit_straight_time_cost_s: opp.exit_straight_time_cost_s,
        };
      });
    }

    // Fallback: LLM-only (no physics available)
    if (priorities && priorities.length > 0) {
      return priorities.slice(0, maxCorners).map((p) => ({
        corner: p.corner,
        time_cost_s: p.time_cost_s,
        issue: p.issue,
        tip: p.tip,
        source: 'llm' as const,
        speed_gap_mph: null,
        brake_gap_m: null,
        exit_straight_time_cost_s: null,
      }));
    }

    return [];
  }, [report, optimalComparison, maxCorners]);
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: Clean

**Step 4: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/hooks/useMergedPriorities.ts
git commit -m "feat: add useMergedPriorities hook for physics-based ranking"
```

---

### Task 4: Frontend — Wire `SessionReport` to use merged priorities

**Files:**
- Modify: `frontend/src/components/session-report/SessionReport.tsx:252-261`
- Modify: `frontend/src/components/session-report/PriorityCardsSection.tsx`

**Step 1: Update `SessionReport` to use `useMergedPriorities`**

In `SessionReport.tsx`, add import:
```typescript
import { useMergedPriorities } from '@/hooks/useMergedPriorities';
```

After line ~120 (where `optimalComparison` is destructured), add:
```typescript
const mergedPriorities = useMergedPriorities(report, optimalComparison, 3);
```

Replace lines 252-261:
```typescript
        {report?.priority_corners && report.priority_corners.length > 0 && (
          <PriorityCardsSection
            priorities={report.priority_corners}
            isNovice={isNovice}
            cornerGrades={report.corner_grades}
            optimalComparison={optimalComparison}
            isOptimalRefreshing={isOptimalStale}
            cornerDeltas={cornerDeltas}
          />
        )}
```

With:
```typescript
        {mergedPriorities.length > 0 && (
          <PriorityCardsSection
            priorities={mergedPriorities}
            isNovice={isNovice}
            cornerGrades={report?.corner_grades}
            cornerDeltas={cornerDeltas}
          />
        )}
```

**Step 2: Update `PriorityCardsSection` props and internals**

Change `PriorityCardsSectionProps`:
```typescript
import type { MergedPriority, CornerGrade } from '@/lib/types';
import type { CornerDelta } from '@/hooks/usePreviousSessionDelta';

interface PriorityCardsSectionProps {
  priorities: MergedPriority[];
  isNovice: boolean;
  cornerGrades?: CornerGrade[];
  cornerDeltas?: Map<number, CornerDelta> | null;
}
```

Remove `optimalComparison` and `isOptimalRefreshing` props entirely.

In the `.map()` at line 187, remove the `liveTimeCost` lookup block (lines 192-197). The time cost is already in `p.time_cost_s` from physics.

Update `PriorityCard` to use `p.time_cost_s` directly instead of `liveTimeCost || p.time_cost_s`. Remove the `isRefreshing` prop.

When `p.tip` is `null` (corner has physics data but no LLM text), show a compact fallback:
```typescript
const displayTip = p.tip ?? (
  p.speed_gap_mph != null
    ? `${Math.abs(p.speed_gap_mph).toFixed(1)} mph below optimal${p.brake_gap_m != null ? `, brakes ${Math.abs(p.brake_gap_m).toFixed(0)}m ${p.brake_gap_m < 0 ? 'early' : 'late'}` : ''}`
    : 'Review corner data in Deep Dive'
);
```

**Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: Clean

**Step 4: Commit**

```bash
git add frontend/src/components/session-report/SessionReport.tsx \
       frontend/src/components/session-report/PriorityCardsSection.tsx
git commit -m "feat: wire Report tab to physics-based priority ranking"
```

---

### Task 5: Frontend — Wire `PitLaneDebrief` and child components to use merged priorities

**Files:**
- Modify: `frontend/src/components/debrief/PitLaneDebrief.tsx:183,238-239,265,334-340`
- Modify: `frontend/src/components/debrief/TimeLossCorners.tsx:50-56`
- Modify: `frontend/src/components/debrief/NextSessionFocus.tsx:8-9,17`
- Modify: `frontend/src/components/debrief/TracksideCard.tsx:10-13`

**Step 1: Update `PitLaneDebrief` to use `useMergedPriorities`**

Add import:
```typescript
import { useMergedPriorities } from '@/hooks/useMergedPriorities';
```

After line ~189 (`maxCorners` definition), add:
```typescript
const mergedPriorities = useMergedPriorities(report, optimalComparison, maxCorners);
```

Replace `topPriority` (line 183):
```typescript
const topPriority = mergedPriorities[0] ?? null;
```

Replace all `report.priority_corners.slice(0, maxCorners)` with `mergedPriorities`:
- Line 239: `<TimeLossCorners corners={mergedPriorities} />`
- Line 265: `topCorners={mergedPriorities}`
- Lines 334-340: `mergedPriorities.map(...)` instead of `report.priority_corners.slice(0, maxCorners).map(...)`

**Step 2: Update `TimeLossCorners` props and header**

Change props from `PriorityCorner[]` to `MergedPriority[]`:
```typescript
import type { MergedPriority } from '@/lib/types';

interface TimeLossCornersProps {
  corners: MergedPriority[];
}
```

Change header from hardcoded "Top 3 Focus" to dynamic:
```typescript
<h3 className="...">
  Top {corners.length} Focus
</h3>
```

In `CornerRow`, handle `null` tip:
```typescript
function CornerRow({ pc }: { pc: MergedPriority }) {
  // ...
  const displayTip = pc.tip ?? 'Review corner data in Deep Dive';
  // use displayTip instead of pc.tip in MarkdownText
```

**Step 3: Update `NextSessionFocus` props**

Change from `PriorityCorner` to `MergedPriority`:
```typescript
import type { MergedPriority } from '@/lib/types';

interface NextSessionFocusProps {
  priority: MergedPriority;
}
```

Handle null `tip`:
```typescript
const tip = formatCoachingText(resolveSpeed(priority.tip ?? ''));
```

If tip is empty (null case), hide the component or show corner number with time cost.

**Step 4: Update `TracksideCard` props**

Change from `PriorityCorner[]` to `MergedPriority[]`:
```typescript
import type { MergedPriority } from '@/lib/types';

interface TracksideCardProps {
  session: SessionSummary;
  consistencyScore: number | null;
  topCorners: MergedPriority[];
  gapToOptimal: number | null;
  optimalLapTime: number | null;
}
```

Handle null `tip` in the focus display and corner list:
```typescript
<p>T{topCorners[0].corner}: {fmt(topCorners[0].tip ?? 'Focus on this corner')}</p>
```

**Step 5: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: Clean

**Step 6: Commit**

```bash
git add frontend/src/components/debrief/PitLaneDebrief.tsx \
       frontend/src/components/debrief/TimeLossCorners.tsx \
       frontend/src/components/debrief/NextSessionFocus.tsx \
       frontend/src/components/debrief/TracksideCard.tsx
git commit -m "feat: wire Debrief tab to physics-based priority ranking"
```

---

### Task 6: Quality gates and final verification

**Files:** None (verification only)

**Step 1: Run ruff format + check**

```bash
ruff format cataclysm/ tests/ backend/
ruff check cataclysm/ tests/ backend/
```
Expected: Clean

**Step 2: Run mypy**

```bash
dmypy run -- cataclysm/ backend/
```
Expected: Clean

**Step 3: Run Python tests**

```bash
pytest tests/ backend/tests/ -v -n auto
```
Expected: All PASS

**Step 4: Run frontend TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: Clean

**Step 5: Commit any fixes, push to staging**

```bash
git push origin HEAD:staging
```

**Step 6: Wait for Railway deploy (~2-3 min), then Playwright visual QA**

Verify on staging:
- Report tab: Priority Improvements show physics-ranked corners with time costs
- Debrief tab: Top N Focus shows same corners as Report (in same order)
- Both tabs match on corner numbers and time values
- Equipment switch → both tabs update to new physics ranking
- Load a session without equipment (no physics) → falls back to LLM-ranked corners

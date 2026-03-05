# Session Line Intelligence + Corner Priority + Track Introduction

**Date**: 2026-03-04
**Status**: Approved

## Problem Statement

The coaching system analyzes driving lines per-corner (`CornerLineProfile`) but lacks:
1. A **session-level line summary** — no aggregate view of line quality patterns across the whole session
2. **Corner priority highlighting** — Allen Berg A/B/C types are computed but buried in XML data; the AI doesn't weight its coaching emphasis by corner importance
3. A **novice track introduction** — new drivers get the same prompt structure as advanced drivers, missing the "track walk" briefing that every HPDE school provides before a first session

## Research Summary

Two-iteration deep research (8 topics, 150+ web searches) produced these key findings:

### On "Ideal Line" Comparison
- **No universal ideal line exists.** The optimal line varies by car (FWD/RWD/AWD), power-to-weight, tires, conditions, and driver style.
- Every professional coaching source (Ross Bentley, Allen Berg, Paradigm Shift Racing, Blayze) frames this as "reference line" not "ideal line."
- At RaceBox-level GPS accuracy (~0.5m), lateral offset analysis is meaningful for **consistency measurement** (comparing a driver to themselves across laps). This is exactly what `corner_line.py` already does.
- **Decision**: Do NOT compute or display a theoretical optimal line. Compare drivers to their own best lap. Our existing approach is well-aligned with industry practice.

### On Corner Prioritization
- **Allen Berg A/B/C types** are the universal framework: Type A (before straight) = highest priority, Type B (after straight) = entry speed matters, Type C (linking) = compromise.
- Exit speed advantage compounds across straight length. A 1 mph exit speed gain from a 40 mph hairpin before a 600m straight is worth far more than the same gain from a fast sweeper before a short link.
- Ross Bentley's rule: "Once you determine the fastest exit you can possibly get, focus on entry speed WITHIN the constraint of not hurting exit."
- The "sacrifice corner" concept: deliberately lose time in linking corners to maximize exit from the next Type A corner.

### On Track Introductions for Novices
- HPDE schools universally provide: track layout overview, corner classification, key landmarks, braking zones, corner priorities, safety info.
- RaceTrackDriving.com's 5-phase learning model: memorization (4-6 laps) → classification → rough line (6-12 laps) → refinement → optimization.
- Novice coaching should be limited to 1-2 priorities with sensory language and reference points.

### On Session-Level Metrics
- No industry-standard "track width utilization" metric exists. Consistency metrics (lap time SD, brake point SD, min speed SD, apex lateral SD) are the standard.
- Professional coaching debriefs distill to 2-3 actionable items, organized by corner phases (braking, entry, mid, exit).
- The most valuable session-level insight is identifying **dominant patterns** across corners (e.g., "early apex in 5 of 8 corners" or "inconsistent line only at Type A corners").

## Design

### Layer 1: Session-Level Line Summary

**New dataclass** `SessionLineProfile` in `corner_line.py`:

```python
@dataclass
class SessionLineProfile:
    """Aggregate line analysis across all corners in a session."""
    n_corners: int
    overall_consistency_tier: str          # median of per-corner consistency tiers
    dominant_error_pattern: str | None     # most common line error, or None if varied
    dominant_error_count: int              # how many corners share the dominant error
    worst_corners_by_line: list[int]       # corner numbers, most inconsistent first
    best_corners_by_line: list[int]        # corner numbers, most consistent first
    type_a_summary: str                    # "2 of 3 Type A corners are 'developing' consistency"
    mean_apex_sd_m: float                  # average apex lateral SD across all corners
```

**New function** `summarize_session_lines(profiles: list[CornerLineProfile]) -> SessionLineProfile`:
- Computes median consistency tier across all corners
- Finds dominant error pattern (most common non-"good_line" error if ≥ 40% of corners share it)
- Sorts corners by `d_apex_sd` for best/worst lists
- Generates Type A summary string highlighting whether high-priority corners have good or bad lines

**Prompt integration**: Formatted as `<session_line_summary>` XML block injected into the coaching prompt alongside the existing per-corner `<line_analysis>`.

### Layer 2: Corner Priority System

**Enhancements to `CornerLineProfile`**:
- Add `priority_rank: int` — 1 = most important corner on track
- Add `straight_after_m: float` — distance from this corner's exit to the next corner's entry

**Priority ranking algorithm**:
1. Compute `straight_after_m` for each corner from `corners[i].exit_distance_m` to `corners[i+1].entry_distance_m`
2. Sort corners: Type A first (sorted by `straight_after_m` descending), then Type B, then Type C
3. Assign ranks 1..N

**New prompt section** `<corner_priorities>`:
```xml
<corner_priorities>
  <corner number="5" type="A" rank="1" straight_after="580m">
    Exit speed carries for 580m. Highest priority corner on the track.
  </corner>
  <corner number="9" type="A" rank="2" straight_after="420m">
    Feeds the back straight. Second priority.
  </corner>
  ...
</corner_priorities>
```

**Updated coaching instruction**: "Weight coaching emphasis proportionally to corner priority rank. Type A corners should receive the most detailed advice. When a driver's line is inconsistent at a Type A corner, flag this as high-impact."

### Layer 3: Novice Track Introduction

**New function** `build_track_introduction(layout: TrackLayout, corners: list[Corner]) -> str`:

Only included in the coaching prompt when `effective_skill == "novice"`.

Content structure (mirrors real HPDE track walk briefings):

1. **Track Overview**
   - Name, length, number of corners, elevation range
   - General character derived from corner metadata ("technical circuit with significant elevation changes" vs "flat, flowing layout")

2. **Corner-by-Corner Guide**
   - For each `OfficialCorner`: number, name, direction, type, elevation trend
   - `coaching_notes` from track profile (the hand-written instructor tips)
   - Character (brake/lift/flat) where set

3. **Key Corners (Top 2-3 Type A)**
   - Which corners matter most and WHY
   - "T5 leads onto a 580m straight — your exit speed here has the biggest impact on lap time"
   - "T9 feeds the pit straight — get this right and it carries all the way to T1"

4. **Track Peculiarities**
   - Blind corners (`blind=True` from `OfficialCorner`)
   - Off-camber sections (`camber="off-camber"`)
   - Notable elevation changes (`elevation_trend != "flat"`)
   - Gathered from existing `OfficialCorner` metadata — no new data needed

5. **Landmark Reference Guide**
   - Key visual references grouped by track section
   - Brake boards, structures, gravel traps from existing `Landmark` data
   - "T5 braking zone: 3-board at 904m, 2-board at 957m, 1-board at 1000m"

**Prompt instruction for novices**: Updated to reference the track introduction:
"A track introduction is provided below. In your summary, help the driver understand the track layout and which corners to prioritize. Frame this as 'here's what matters most at this track' rather than an exhaustive tour of every corner."

### What Is NOT In Scope

| Excluded | Reason |
|----------|--------|
| "Ideal line" overlay/comparison | No universal ideal; varies by car/conditions; even 0.5m GPS can't reliably compare to a theoretical trajectory |
| Friction circle / grip utilization | Requires accelerometer data channels not reliably present in RaceChrono CSV v3. Separate feature. |
| Trail braking detection | Needs brake pressure or combined brake+steering data. Separate feature. |
| Frontend changes | This is purely backend prompt enrichment. No UI work needed. |
| API changes | No new endpoints. The coaching report JSON schema is unchanged — the AI simply produces better output from richer prompts. |

## Data Flow

```
TrackLayout (existing)
  ├── OfficialCorner metadata ──→ build_track_introduction() ──→ prompt (novice only)
  └── Landmark list ─────────────→ (already in prompt via existing landmark system)

CornerLineProfile[] (existing, enhanced)
  ├── Per-corner: already in prompt as <line_analysis>
  ├── NEW: priority_rank, straight_after_m ──→ <corner_priorities> in prompt
  └── NEW: aggregate into SessionLineProfile ──→ <session_line_summary> in prompt
```

## Files Changed

| File | Change |
|------|--------|
| `cataclysm/corner_line.py` | Add `SessionLineProfile` dataclass, `summarize_session_lines()`, `format_session_line_summary_for_prompt()`. Add `priority_rank` and `straight_after_m` fields to `CornerLineProfile`. Update `analyze_corner_lines()` to compute priority ranks. |
| `cataclysm/coaching.py` | Add `build_track_introduction()`, `_format_corner_priorities()`. Update `build_coaching_prompt()` to include session line summary, corner priorities, and track intro (novice only). Update novice prompt instructions. |
| `tests/test_corner_line.py` | Tests for `summarize_session_lines()`, priority ranking, `straight_after_m` computation |
| `tests/test_coaching.py` | Tests for `build_track_introduction()`, prompt integration, novice-only inclusion |

## Testing Strategy

- **Unit tests**: Synthetic corner data with known A/B/C types, verify priority ranking order, verify session summary aggregation
- **Integration test**: Build a full coaching prompt with all three layers, verify XML sections are present/absent based on skill level
- **Quality gates**: ruff, mypy, pytest — zero errors

## Research Sources

Full research transcripts saved at:
- Agent 1 (racing line theory, coaching, track intros): `tasks/a41717c95d7126b9e.output`
- Agent 2 (telemetry comparison, physics, metrics): `tasks/a52f14ce239a53ae1.output`

Key references:
- Allen Berg Racing Schools: A/B/C corner classification
- Ross Bentley (Speed Secrets): entry/exit speed balance, 2-point coaching
- Blayze coaching methodology: 6 fundamentals, sacrifice corners, 5 reference points
- Paradigm Shift Racing: Four Elements of a Perfect Corner hierarchy
- Driver61: corner prioritization by straight length
- RaceTrackDriving.com: 5-phase learning model for new tracks
- YourDataDriven: GPS accuracy limitations, speed trace as primary coaching tool
- HP Academy: friction circle, data analysis methodology
- Garmin Catalyst: "True Optimal Lap" compositing approach (informational)

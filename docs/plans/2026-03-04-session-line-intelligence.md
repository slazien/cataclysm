# Session Line Intelligence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add session-level line summary, corner priority ranking, and novice track introduction to the coaching prompt — enriching AI output without changing the JSON response schema or frontend.

**Architecture:** Three new prompt sections injected into `_build_coaching_prompt()`: `<session_line_summary>` (always, when line data exists), `<corner_priorities>` (always, when corners exist), and `<track_introduction>` (novice only, when `TrackLayout` is available). All computation happens in `corner_line.py`; prompt formatting in `coaching.py`. The call chain threads `TrackLayout` from the backend router through `generate_coaching_report` to the prompt builder.

**Tech Stack:** Python 3.11+, dataclasses, numpy. No new dependencies.

---

### Task 1: Add `straight_after_m` and `priority_rank` to `CornerLineProfile`

**Files:**
- Modify: `cataclysm/corner_line.py:24-46` (dataclass)
- Modify: `cataclysm/corner_line.py:118-141` (`_infer_allen_berg_type`)
- Modify: `cataclysm/corner_line.py:144-224` (`analyze_corner_lines`)
- Test: `tests/test_corner_line.py`

**Step 1: Write the failing tests**

Add to `tests/test_corner_line.py`:

```python
class TestCornerPriority:
    def test_straight_after_computed(self) -> None:
        """straight_after_m should be distance from exit to next corner entry."""
        corners = [
            _make_corner(1, entry=50, apex=100, exit=150),
            _make_corner(2, entry=700, apex=750, exit=800),  # 550m gap = Type A
            _make_corner(3, entry=850, apex=900, exit=950),  # 50m gap = Type C
        ]
        profiles = _analyze_with_corners(corners, n_laps=5)
        assert len(profiles) == 3
        assert profiles[0].straight_after_m == pytest.approx(550.0)
        assert profiles[1].straight_after_m == pytest.approx(50.0)
        assert profiles[2].straight_after_m == pytest.approx(0.0)  # last corner, wraps

    def test_priority_rank_type_a_first(self) -> None:
        """Type A corners (before long straights) should get lowest rank numbers."""
        corners = [
            _make_corner(1, entry=50, apex=100, exit=150),    # 550m gap -> Type A
            _make_corner(2, entry=700, apex=750, exit=800),   # 50m gap -> Type C
            _make_corner(3, entry=850, apex=900, exit=950),   # 50m gap -> Type C
        ]
        profiles = _analyze_with_corners(corners, n_laps=5)
        # Corner 1 is Type A -> rank 1; corners 2,3 are Type C -> ranks 2,3
        assert profiles[0].priority_rank == 1
        assert profiles[0].allen_berg_type == "A"

    def test_multiple_type_a_ranked_by_straight_length(self) -> None:
        """Among Type A corners, longer following straight = lower rank number."""
        corners = [
            _make_corner(1, entry=50, apex=100, exit=150),    # 350m gap
            _make_corner(2, entry=500, apex=550, exit=600),   # 600m gap (longer)
            _make_corner(3, entry=1200, apex=1250, exit=1300),
        ]
        profiles = _analyze_with_corners(corners, n_laps=5)
        type_a = [p for p in profiles if p.allen_berg_type == "A"]
        if len(type_a) >= 2:
            # The one with 600m straight should rank higher (lower number)
            ranks = {p.corner_number: p.priority_rank for p in profiles}
            assert ranks[2] < ranks[1]  # corner 2 has longer straight
```

Note: `_make_corner` and `_analyze_with_corners` are test helpers that need to be created. `_make_corner` builds a `Corner` with specified distances; `_analyze_with_corners` creates synthetic GPS traces + reference centerline and calls `analyze_corner_lines`.

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_corner_line.py::TestCornerPriority -v`
Expected: FAIL — `CornerLineProfile` has no `straight_after_m` or `priority_rank` field.

**Step 3: Add fields to `CornerLineProfile`**

In `cataclysm/corner_line.py`, add two fields to the dataclass (after `allen_berg_type`):

```python
@dataclass
class CornerLineProfile:
    """Line analysis for a single corner across all laps in a session."""

    corner_number: int
    n_laps: int

    # Session-median offsets at key points (meters from reference)
    d_entry_median: float
    d_apex_median: float
    d_exit_median: float

    # Apex timing
    apex_fraction_median: float  # 0.0=entry, 1.0=exit; ideal ~0.50-0.65 for Type A

    # Per-lap consistency
    d_apex_sd: float  # Lateral SD at apex across laps

    # Derived
    line_error_type: str  # "early_apex", "late_apex", "wide_entry", "pinched_exit", "good_line"
    severity: str  # "minor" <0.5m, "moderate" 0.5-1.5m, "major" >1.5m
    consistency_tier: str  # "expert" <0.3m, "consistent" <0.7m, "developing" <1.5m, "novice" >=1.5m
    allen_berg_type: str  # "A" (before straight), "B" (after straight), "C" (linking)

    # Corner priority (computed after all profiles are built)
    straight_after_m: float = 0.0  # Distance from exit to next corner entry
    priority_rank: int = 0  # 1 = most important corner on track
```

**Step 4: Update `_infer_allen_berg_type` to also return `straight_after_m`**

Rename to `_infer_berg_type_and_gap` and return a tuple:

```python
def _infer_berg_type_and_gap(
    corner: Corner, corners: list[Corner]
) -> tuple[str, float]:
    """Infer Allen Berg corner type and gap to next corner.

    Returns (berg_type, straight_after_m).
    """
    idx = corner.number - 1
    if idx < 0 or idx >= len(corners):
        return "C", 0.0

    # Gap to next corner
    gap_to_next = 0.0
    if idx + 1 < len(corners):
        gap_to_next = corners[idx + 1].entry_distance_m - corner.exit_distance_m

    # Gap from previous corner
    gap_from_prev = 0.0
    if idx > 0:
        gap_from_prev = corner.entry_distance_m - corners[idx - 1].exit_distance_m

    if gap_to_next > 150:
        return "A", gap_to_next
    if gap_from_prev > 150:
        return "B", gap_to_next
    return "C", gap_to_next
```

**Step 5: Update `analyze_corner_lines` to compute priority ranks**

After building all profiles, add a priority ranking step:

```python
    # --- existing loop builds profiles list ---

    # Assign priority ranks: Type A first (by straight_after_m desc), then B, then C
    _assign_priority_ranks(profiles)

    return profiles


def _assign_priority_ranks(profiles: list[CornerLineProfile]) -> None:
    """Assign priority_rank in-place. Rank 1 = most important corner."""
    type_order = {"A": 0, "B": 1, "C": 2}
    ranked = sorted(
        profiles,
        key=lambda p: (type_order.get(p.allen_berg_type, 2), -p.straight_after_m),
    )
    for rank, profile in enumerate(ranked, start=1):
        profile.priority_rank = rank
```

Update the profile construction inside the loop to use the new function:

```python
        berg_type, straight_gap = _infer_berg_type_and_gap(corner, corners)

        profiles.append(
            CornerLineProfile(
                ...,
                allen_berg_type=berg_type,
                straight_after_m=round(straight_gap, 1),
            )
        )
```

**Step 6: Create test helpers and run tests**

Add to the top of `tests/test_corner_line.py` (or update existing fixtures):

```python
def _make_corner(
    number: int,
    *,
    entry: float,
    apex: float,
    exit: float,
) -> Corner:
    """Build a minimal Corner for testing."""
    return Corner(
        number=number,
        entry_distance_m=entry,
        exit_distance_m=exit,
        apex_distance_m=apex,
        min_speed_mps=20.0,
        brake_point_m=entry - 50 if entry > 50 else 0.0,
        throttle_commit_m=apex + 10,
        peak_lateral_g=0.5,
    )
```

The `_analyze_with_corners` helper needs to create synthetic `GPSTrace` + `ReferenceCenterline` long enough to cover the corner distances. Check the existing `TestAnalyzeCornerLines` fixtures for the pattern — they create numpy arrays at 0.7m spacing.

Run: `pytest tests/test_corner_line.py::TestCornerPriority -v`
Expected: PASS

**Step 7: Commit**

```bash
git add cataclysm/corner_line.py tests/test_corner_line.py
git commit -m "feat: add straight_after_m and priority_rank to CornerLineProfile"
```

---

### Task 2: Add `SessionLineProfile` and `summarize_session_lines()`

**Files:**
- Modify: `cataclysm/corner_line.py` (add dataclass + function after `CornerLineProfile`)
- Test: `tests/test_corner_line.py`

**Step 1: Write the failing tests**

```python
from cataclysm.corner_line import SessionLineProfile, summarize_session_lines


class TestSessionLineSummary:
    def test_empty_profiles(self) -> None:
        result = summarize_session_lines([])
        assert result is None

    def test_overall_consistency_is_median(self) -> None:
        """Overall tier should be the median of per-corner tiers."""
        profiles = [
            _make_profile(1, d_apex_sd=0.2, error="good_line", berg="A"),  # expert
            _make_profile(2, d_apex_sd=0.5, error="good_line", berg="C"),  # consistent
            _make_profile(3, d_apex_sd=1.0, error="early_apex", berg="C"),  # developing
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        assert result.overall_consistency_tier == "consistent"  # median of [expert, consistent, developing]

    def test_dominant_error_detected(self) -> None:
        """If >=40% of corners share a non-good_line error, it's the dominant pattern."""
        profiles = [
            _make_profile(1, d_apex_sd=0.5, error="early_apex", berg="A"),
            _make_profile(2, d_apex_sd=0.5, error="early_apex", berg="C"),
            _make_profile(3, d_apex_sd=0.5, error="early_apex", berg="C"),
            _make_profile(4, d_apex_sd=0.5, error="good_line", berg="B"),
            _make_profile(5, d_apex_sd=0.5, error="wide_entry", berg="C"),
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        assert result.dominant_error_pattern == "early_apex"
        assert result.dominant_error_count == 3

    def test_no_dominant_error_when_varied(self) -> None:
        profiles = [
            _make_profile(1, d_apex_sd=0.5, error="early_apex", berg="A"),
            _make_profile(2, d_apex_sd=0.5, error="late_apex", berg="B"),
            _make_profile(3, d_apex_sd=0.5, error="wide_entry", berg="C"),
            _make_profile(4, d_apex_sd=0.5, error="pinched_exit", berg="C"),
            _make_profile(5, d_apex_sd=0.5, error="good_line", berg="C"),
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        assert result.dominant_error_pattern is None

    def test_worst_corners_sorted_by_sd(self) -> None:
        profiles = [
            _make_profile(1, d_apex_sd=0.2, error="good_line", berg="A"),
            _make_profile(2, d_apex_sd=1.8, error="early_apex", berg="C"),
            _make_profile(3, d_apex_sd=0.9, error="good_line", berg="C"),
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        assert result.worst_corners_by_line == [2, 3, 1]
        assert result.best_corners_by_line == [1, 3, 2]

    def test_type_a_summary_generated(self) -> None:
        profiles = [
            _make_profile(1, d_apex_sd=1.2, error="early_apex", berg="A"),  # developing
            _make_profile(2, d_apex_sd=0.5, error="good_line", berg="C"),
            _make_profile(3, d_apex_sd=0.4, error="good_line", berg="A"),  # consistent
        ]
        result = summarize_session_lines(profiles)
        assert result is not None
        assert "Type A" in result.type_a_summary
        assert "T1" in result.type_a_summary or "T3" in result.type_a_summary
```

Test helper:

```python
def _make_profile(
    corner_number: int,
    *,
    d_apex_sd: float,
    error: str,
    berg: str,
    straight_after: float = 100.0,
) -> CornerLineProfile:
    return CornerLineProfile(
        corner_number=corner_number,
        n_laps=10,
        d_entry_median=0.0,
        d_apex_median=0.0,
        d_exit_median=0.0,
        apex_fraction_median=0.55,
        d_apex_sd=d_apex_sd,
        line_error_type=error,
        severity="minor",
        consistency_tier=_consistency_tier(d_apex_sd),
        allen_berg_type=berg,
        straight_after_m=straight_after,
        priority_rank=corner_number,
    )
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_corner_line.py::TestSessionLineSummary -v`
Expected: FAIL — `SessionLineProfile` and `summarize_session_lines` don't exist.

**Step 3: Implement `SessionLineProfile` and `summarize_session_lines`**

Add to `cataclysm/corner_line.py` after `CornerLineProfile`:

```python
from collections import Counter


_TIER_ORDER = {"expert": 0, "consistent": 1, "developing": 2, "novice": 3}
_TIER_NAMES = {v: k for k, v in _TIER_ORDER.items()}


@dataclass
class SessionLineProfile:
    """Aggregate line analysis across all corners in a session."""

    n_corners: int
    overall_consistency_tier: str
    dominant_error_pattern: str | None
    dominant_error_count: int
    worst_corners_by_line: list[int]
    best_corners_by_line: list[int]
    type_a_summary: str
    mean_apex_sd_m: float


def summarize_session_lines(
    profiles: list[CornerLineProfile],
) -> SessionLineProfile | None:
    """Aggregate per-corner line profiles into a session-level summary."""
    if not profiles:
        return None

    # Overall consistency: median tier
    tier_values = sorted(_TIER_ORDER[p.consistency_tier] for p in profiles)
    median_tier_val = tier_values[len(tier_values) // 2]
    overall_tier = _TIER_NAMES[median_tier_val]

    # Dominant error pattern: most common non-good_line error if >= 40% of corners
    error_counts = Counter(
        p.line_error_type for p in profiles if p.line_error_type != "good_line"
    )
    dominant_error: str | None = None
    dominant_count = 0
    if error_counts:
        most_common, count = error_counts.most_common(1)[0]
        if count / len(profiles) >= 0.4:
            dominant_error = most_common
            dominant_count = count

    # Sort corners by apex SD
    by_sd = sorted(profiles, key=lambda p: p.d_apex_sd, reverse=True)
    worst = [p.corner_number for p in by_sd]
    best = list(reversed(worst))

    # Type A summary
    type_a = [p for p in profiles if p.allen_berg_type == "A"]
    if type_a:
        tier_counts = Counter(p.consistency_tier for p in type_a)
        parts = [f"{count} {tier}" for tier, count in tier_counts.most_common()]
        corner_list = ", ".join(f"T{p.corner_number}" for p in type_a)
        type_a_summary = (
            f"Type A corners ({corner_list}): {', '.join(parts)} consistency"
        )
    else:
        type_a_summary = "No Type A corners identified"

    mean_sd = float(np.mean([p.d_apex_sd for p in profiles]))

    return SessionLineProfile(
        n_corners=len(profiles),
        overall_consistency_tier=overall_tier,
        dominant_error_pattern=dominant_error,
        dominant_error_count=dominant_count,
        worst_corners_by_line=worst,
        best_corners_by_line=best,
        type_a_summary=type_a_summary,
        mean_apex_sd_m=round(mean_sd, 3),
    )
```

**Step 4: Run tests**

Run: `pytest tests/test_corner_line.py::TestSessionLineSummary -v`
Expected: PASS

**Step 5: Add prompt formatter**

Add `format_session_line_summary_for_prompt` to `corner_line.py`:

```python
def format_session_line_summary_for_prompt(
    summary: SessionLineProfile | None,
) -> str:
    """Format session-level line summary as XML for the coaching prompt."""
    if summary is None:
        return ""

    lines = ["<session_line_summary>"]
    lines.append(
        f"  <overall_consistency>{summary.overall_consistency_tier}"
        f" (mean apex SD: {summary.mean_apex_sd_m:.2f}m)</overall_consistency>"
    )
    if summary.dominant_error_pattern:
        lines.append(
            f"  <dominant_error>{summary.dominant_error_pattern}"
            f" in {summary.dominant_error_count}/{summary.n_corners}"
            f" corners</dominant_error>"
        )
    lines.append(
        f"  <worst_line_corners>"
        f"{', '.join(f'T{c}' for c in summary.worst_corners_by_line[:3])}"
        f"</worst_line_corners>"
    )
    lines.append(f"  <type_a_assessment>{summary.type_a_summary}</type_a_assessment>")
    lines.append("</session_line_summary>")
    return "\n".join(lines)
```

**Step 6: Test the formatter**

```python
class TestFormatSessionLineSummary:
    def test_none_returns_empty(self) -> None:
        assert format_session_line_summary_for_prompt(None) == ""

    def test_produces_xml(self) -> None:
        profiles = [
            _make_profile(1, d_apex_sd=0.5, error="early_apex", berg="A"),
            _make_profile(2, d_apex_sd=0.8, error="early_apex", berg="C"),
        ]
        summary = summarize_session_lines(profiles)
        xml = format_session_line_summary_for_prompt(summary)
        assert "<session_line_summary>" in xml
        assert "early_apex" in xml
        assert "Type A" in xml
```

Run: `pytest tests/test_corner_line.py::TestFormatSessionLineSummary -v`
Expected: PASS

**Step 7: Commit**

```bash
git add cataclysm/corner_line.py tests/test_corner_line.py
git commit -m "feat: add SessionLineProfile and session-level line summary"
```

---

### Task 3: Add corner priorities prompt section to `coaching.py`

**Files:**
- Modify: `cataclysm/coaching.py` (add `_format_corner_priorities`, update imports, update `_build_coaching_prompt`)
- Test: `tests/test_coaching.py`

**Step 1: Write the failing test**

```python
class TestFormatCornerPriorities:
    def test_empty_profiles(self) -> None:
        from cataclysm.coaching import _format_corner_priorities
        assert _format_corner_priorities([]) == ""

    def test_produces_xml_with_ranking(self) -> None:
        from cataclysm.coaching import _format_corner_priorities
        profiles = [
            _make_profile(5, d_apex_sd=0.5, error="good_line", berg="A",
                          straight_after=580.0),
            _make_profile(9, d_apex_sd=0.5, error="good_line", berg="A",
                          straight_after=420.0),
            _make_profile(3, d_apex_sd=0.5, error="good_line", berg="C",
                          straight_after=50.0),
        ]
        # Manually set priority ranks
        profiles[0].priority_rank = 1
        profiles[1].priority_rank = 2
        profiles[2].priority_rank = 3
        xml = _format_corner_priorities(profiles)
        assert "<corner_priorities>" in xml
        assert 'rank="1"' in xml
        assert "580" in xml
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_coaching.py::TestFormatCornerPriorities -v`
Expected: FAIL — function doesn't exist.

**Step 3: Implement `_format_corner_priorities`**

Add to `cataclysm/coaching.py`:

```python
def _format_corner_priorities(profiles: list[CornerLineProfile]) -> str:
    """Format corner priority ranking as XML for the coaching prompt."""
    if not profiles:
        return ""

    ranked = sorted(profiles, key=lambda p: p.priority_rank)
    lines = ["\n<corner_priorities>"]
    for p in ranked:
        desc = ""
        if p.allen_berg_type == "A":
            desc = (
                f"Exit speed carries for {p.straight_after_m:.0f}m. "
                f"{'Highest priority.' if p.priority_rank == 1 else 'High priority.'}"
            )
        elif p.allen_berg_type == "B":
            desc = "Entry speed corner — maximize speed at end of preceding straight."
        else:
            desc = "Linking corner — balance line to serve adjacent corners."
        lines.append(
            f'  <corner number="{p.corner_number}" type="{p.allen_berg_type}"'
            f' rank="{p.priority_rank}" straight_after="{p.straight_after_m:.0f}m">'
            f"{desc}</corner>"
        )
    lines.append("</corner_priorities>")
    return "\n".join(lines)
```

**Step 4: Run test**

Run: `pytest tests/test_coaching.py::TestFormatCornerPriorities -v`
Expected: PASS

**Step 5: Wire into `_build_coaching_prompt`**

Update imports at top of `coaching.py`:

```python
from cataclysm.corner_line import (
    CornerLineProfile,
    format_line_analysis_for_prompt,
    format_session_line_summary_for_prompt,
    summarize_session_lines,
)
```

In `_build_coaching_prompt()`, after the existing `line_analysis_section` computation (~line 678):

```python
    line_analysis_section = format_line_analysis_for_prompt(line_profiles or [])
    session_line_summary = format_session_line_summary_for_prompt(
        summarize_session_lines(line_profiles or [])
    )
    corner_priorities_section = _format_corner_priorities(line_profiles or [])
```

Insert these sections into the prompt template (in the `</session_data>` block, after `{line_analysis_section}`):

```python
{line_analysis_section}
{session_line_summary}
{corner_priorities_section}
</session_data>
```

Update `line_instruction` to include priority guidance:

```python
    line_instruction = ""
    if line_analysis_section:
        line_instruction = (
            "\nWhen LINE ANALYSIS data is present, integrate it with speed/brake analysis. "
            "A corner with good brake data but an early apex error costs time on the exit — "
            "report these together as one issue, not two separate observations.\n"
        )
    if corner_priorities_section:
        line_instruction += (
            "\nWeight coaching emphasis proportionally to corner priority rank. "
            "Type A corners (before long straights) should receive the most detailed advice. "
            "When a driver's line is inconsistent at a Type A corner, flag this as high-impact "
            "because exit speed compounds across the following straight.\n"
        )
```

**Step 6: Run full coaching prompt test**

Run: `pytest tests/test_coaching.py -v -k "prompt"`
Expected: PASS (existing tests should still pass; new sections are additive)

**Step 7: Commit**

```bash
git add cataclysm/coaching.py tests/test_coaching.py
git commit -m "feat: add corner priority ranking to coaching prompt"
```

---

### Task 4: Add `build_track_introduction()` for novice drivers

**Files:**
- Modify: `cataclysm/coaching.py` (add function, update `_build_coaching_prompt`)
- Test: `tests/test_coaching.py`

**Step 1: Write the failing tests**

```python
from cataclysm.coaching import build_track_introduction
from cataclysm.track_db import TrackLayout, OfficialCorner
from cataclysm.landmarks import Landmark, LandmarkType


class TestBuildTrackIntroduction:
    def test_none_layout_returns_empty(self) -> None:
        assert build_track_introduction(None) == ""

    def test_basic_structure(self) -> None:
        layout = TrackLayout(
            name="Test Raceway",
            corners=[
                OfficialCorner(1, "Hairpin", 0.15, direction="right",
                               corner_type="hairpin", elevation_trend="flat",
                               coaching_notes="Late apex onto back straight."),
                OfficialCorner(2, "Sweeper", 0.45, direction="left",
                               corner_type="sweeper", elevation_trend="uphill"),
                OfficialCorner(3, "Kink", 0.80, direction="right",
                               corner_type="kink", elevation_trend="downhill",
                               blind=True),
            ],
            length_m=2000.0,
            elevation_range_m=25.0,
        )
        result = build_track_introduction(layout)
        assert "<track_introduction>" in result
        assert "Test Raceway" in result
        assert "2000" in result or "2.0 km" in result
        assert "Hairpin" in result
        assert "Late apex" in result
        assert "blind" in result.lower()

    def test_landmarks_included(self) -> None:
        layout = TrackLayout(
            name="Test Circuit",
            corners=[OfficialCorner(1, "Turn 1", 0.10, direction="left")],
            landmarks=[
                Landmark("S/F gantry", 0.0, LandmarkType.structure),
                Landmark("T1 brake board", 150.0, LandmarkType.brake_board),
            ],
            length_m=1500.0,
        )
        result = build_track_introduction(layout)
        assert "S/F gantry" in result
        assert "brake board" in result

    def test_key_corners_highlighted(self) -> None:
        """Type A corners (before long straights) should be highlighted."""
        layout = TrackLayout(
            name="Test",
            corners=[
                OfficialCorner(1, "T1", 0.10, direction="right"),
                OfficialCorner(2, "T2", 0.30, direction="left"),
                OfficialCorner(3, "T3", 0.50, direction="right"),
            ],
            length_m=3000.0,
        )
        # With 3000m track: T1 at 300m, T2 at 900m, T3 at 1500m
        # Gaps: T1->T2 = 600m (Type A), T2->T3 = 600m (Type A)
        result = build_track_introduction(layout)
        assert "priority" in result.lower() or "important" in result.lower()
```

**Step 2: Run to verify failure**

Run: `pytest tests/test_coaching.py::TestBuildTrackIntroduction -v`
Expected: FAIL — `build_track_introduction` doesn't exist.

**Step 3: Implement `build_track_introduction`**

Add to `cataclysm/coaching.py`:

```python
from cataclysm.track_db import TrackLayout


def build_track_introduction(layout: TrackLayout | None) -> str:
    """Build a track briefing for novice drivers.

    Mirrors a real HPDE track walk: layout overview, corner guide,
    key corners, peculiarities, and landmark references.
    """
    if layout is None or not layout.corners:
        return ""

    lines = ["\n<track_introduction>"]

    # 1. Track overview
    length_str = f"{layout.length_m:.0f}m" if layout.length_m else "unknown length"
    n_corners = len(layout.corners)
    lines.append(f"<overview>")
    lines.append(f"  {layout.name} — {length_str}, {n_corners} corners.")
    if layout.elevation_range_m and layout.elevation_range_m > 10:
        lines.append(
            f"  Elevation range: ~{layout.elevation_range_m:.0f}m "
            f"(significant elevation changes affect braking and grip)."
        )
    lines.append("</overview>")

    # 2. Corner-by-corner guide
    lines.append("<corner_guide>")
    for c in layout.corners:
        parts = [f"T{c.number} {c.name}"]
        if c.direction:
            parts.append(c.direction.upper())
        if c.corner_type:
            parts.append(c.corner_type)
        if c.elevation_trend and c.elevation_trend != "flat":
            parts.append(c.elevation_trend)
        if c.character:
            parts.append(f"[{c.character}]")
        line = " | ".join(parts)
        if c.coaching_notes:
            line += f" — {c.coaching_notes}"
        lines.append(f"  {line}")
    lines.append("</corner_guide>")

    # 3. Key corners (Type A identification using 150m gap heuristic)
    key_corners: list[tuple[OfficialCorner, float]] = []
    for i, c in enumerate(layout.corners):
        if i + 1 < n_corners and layout.length_m:
            next_c = layout.corners[i + 1]
            gap = (next_c.fraction - c.fraction) * layout.length_m
            if gap > 150:
                key_corners.append((c, gap))
        elif i == n_corners - 1 and layout.length_m:
            # Last corner to S/F (wrap-around)
            gap = (1.0 - c.fraction + layout.corners[0].fraction) * layout.length_m
            if gap > 150:
                key_corners.append((c, gap))

    if key_corners:
        key_corners.sort(key=lambda x: -x[1])
        lines.append("<key_corners note='These matter most for lap time'>")
        for rank, (c, gap) in enumerate(key_corners[:3], start=1):
            lines.append(
                f"  #{rank}: T{c.number} ({c.name}) — exit speed carries for "
                f"{gap:.0f}m onto the following straight. "
                f"{'Highest priority corner.' if rank == 1 else 'High priority.'}"
            )
        lines.append("</key_corners>")

    # 4. Track peculiarities
    peculiarities: list[str] = []
    for c in layout.corners:
        if c.blind:
            peculiarities.append(f"T{c.number} ({c.name}): blind corner")
        if c.camber and c.camber in ("negative", "off-camber"):
            peculiarities.append(f"T{c.number} ({c.name}): {c.camber} — reduced grip")
        if c.elevation_trend == "crest":
            peculiarities.append(
                f"T{c.number} ({c.name}): crest — car goes light, smooth inputs"
            )
        if c.elevation_trend == "compression":
            peculiarities.append(
                f"T{c.number} ({c.name}): compression — extra grip available"
            )
    if peculiarities:
        lines.append("<peculiarities>")
        for p in peculiarities:
            lines.append(f"  {p}")
        lines.append("</peculiarities>")

    # 5. Landmark reference guide
    if layout.landmarks:
        lines.append("<landmark_guide>")
        for lm in layout.landmarks:
            desc = f"  {lm.name} ({lm.landmark_type.value}) at {lm.distance_m:.0f}m"
            if lm.description:
                desc += f" — {lm.description}"
            lines.append(desc)
        lines.append("</landmark_guide>")

    lines.append("</track_introduction>")
    return "\n".join(lines)
```

**Step 4: Run tests**

Run: `pytest tests/test_coaching.py::TestBuildTrackIntroduction -v`
Expected: PASS

**Step 5: Wire into `_build_coaching_prompt` — novice only**

Add `track_layout: TrackLayout | None = None` parameter to both `_build_coaching_prompt` and `generate_coaching_report`.

In `_build_coaching_prompt`, after the skill section:

```python
    track_intro_section = ""
    track_intro_instruction = ""
    if effective_skill == "novice" and track_layout is not None:
        track_intro_section = build_track_introduction(track_layout)
        track_intro_instruction = (
            "\nA TRACK INTRODUCTION is provided. In your summary, help the driver "
            "understand the track layout and which corners to prioritize. Frame this as "
            "'here\\'s what matters most at this track' rather than an exhaustive tour "
            "of every corner. Reference key corners by name.\n"
        )
```

Insert `{track_intro_section}` into the `</session_data>` block and `{track_intro_instruction}` into the `<instructions>` block.

**Step 6: Test novice-only inclusion**

```python
class TestTrackIntroNoviceOnly:
    def test_included_for_novice(self) -> None:
        """Track introduction should appear in prompt for novice skill level."""
        prompt = _build_coaching_prompt(
            ...,  # use existing test fixtures
            skill_level="novice",
            track_layout=_sample_layout(),
        )
        assert "<track_introduction>" in prompt

    def test_excluded_for_intermediate(self) -> None:
        prompt = _build_coaching_prompt(
            ...,
            skill_level="intermediate",
            track_layout=_sample_layout(),
        )
        assert "<track_introduction>" not in prompt
```

Run: `pytest tests/test_coaching.py -v -k "TrackIntro"`
Expected: PASS

**Step 7: Commit**

```bash
git add cataclysm/coaching.py tests/test_coaching.py
git commit -m "feat: add novice track introduction to coaching prompt"
```

---

### Task 5: Thread `TrackLayout` through the call chain

**Files:**
- Modify: `backend/api/routers/coaching.py:252-268` (pass `track_layout` to `generate_coaching_report`)
- Modify: `cataclysm/coaching.py` (`generate_coaching_report` signature + pass-through)
- Test: `backend/tests/test_auto_coaching.py` (if needed)

**Step 1: Update `generate_coaching_report` signature**

In `cataclysm/coaching.py`, add `track_layout` parameter to both functions:

```python
def _build_coaching_prompt(
    ...,
    line_profiles: list[CornerLineProfile] | None = None,
    track_layout: TrackLayout | None = None,  # NEW
) -> str:
```

```python
def generate_coaching_report(
    ...,
    line_profiles: list[CornerLineProfile] | None = None,
    track_layout: TrackLayout | None = None,  # NEW
) -> CoachingReport:
```

Pass through in `generate_coaching_report`:

```python
    prompt = _build_coaching_prompt(
        ...,
        line_profiles=line_profiles,
        track_layout=track_layout,
    )
```

**Step 2: Update call site in `backend/api/routers/coaching.py`**

At line ~252, add `track_layout=layout` to the `generate_coaching_report` call:

```python
                    report = await asyncio.to_thread(
                        generate_coaching_report,
                        coaching_summaries,
                        sd.all_lap_corners,
                        sd.parsed.metadata.track_name,
                        gains=sd.gains,
                        skill_level=skill_level,
                        landmarks=landmarks or None,
                        corner_analysis=corner_analysis,
                        causal_analysis=causal_analysis,
                        archetype=archetype,
                        skill_assessment=skill_assessment,
                        equipment_profile=equipment_profile,
                        conditions=conditions,
                        weather=weather,
                        corners_gained=corners_gained,
                        flow_laps=flow_laps,
                        track_layout=layout,  # NEW
                    )
```

`layout` is already computed at line 154: `layout = detect_track_or_lookup(...)`.

**Step 3: Verify existing tests still pass**

Run: `pytest tests/ backend/tests/ -v --timeout=60`
Expected: All PASS (the new parameter has a default of `None` so existing calls are unaffected).

**Step 4: Commit**

```bash
git add cataclysm/coaching.py backend/api/routers/coaching.py
git commit -m "feat: thread TrackLayout through coaching call chain"
```

---

### Task 6: Quality gates

**Step 1: Run ruff**

```bash
ruff check cataclysm/corner_line.py cataclysm/coaching.py tests/test_corner_line.py tests/test_coaching.py backend/api/routers/coaching.py
ruff format cataclysm/corner_line.py cataclysm/coaching.py tests/test_corner_line.py tests/test_coaching.py backend/api/routers/coaching.py
```

Expected: Zero errors after format.

**Step 2: Run mypy**

```bash
dmypy run -- cataclysm/ backend/
```

Expected: Zero type errors. Watch for:
- `SessionLineProfile` needs `from __future__ import annotations` (already present in `corner_line.py`)
- `TrackLayout | None` type annotation in `coaching.py` — ensure import is added
- `Counter` import from `collections`

**Step 3: Run full test suite**

```bash
pytest tests/ backend/tests/ -v
```

Expected: All PASS.

**Step 4: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve lint and type errors from session line intelligence"
```

---

### Task 7: Code review

**Step 1: Dispatch code review agent**

Use `superpowers:code-reviewer` agent to review all changed files:
- `cataclysm/corner_line.py`
- `cataclysm/coaching.py`
- `tests/test_corner_line.py`
- `tests/test_coaching.py`
- `backend/api/routers/coaching.py`

Focus areas:
- Are the new dataclass fields backward-compatible (default values)?
- Is `_assign_priority_ranks` mutation-safe (called after all profiles are built)?
- Does `build_track_introduction` handle edge cases (no landmarks, no coaching notes, missing length)?
- Does the novice-only gate work when `skill_assessment.final_level` overrides `skill_level`?

**Step 2: Address review findings and commit**

```bash
git add -u
git commit -m "fix: address code review findings"
```

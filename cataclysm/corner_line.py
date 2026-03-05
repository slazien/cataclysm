"""Corner-level driving line analysis on top of GPS trace primitives.

Detects apex location, classifies line errors (early/late apex, wide entry,
pinched exit), and rates consistency tier per corner.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from cataclysm.corners import Corner
from cataclysm.gps_line import GPSTrace, ReferenceCenterline, compute_lateral_offsets

LINE_ERROR_THRESHOLDS = {
    "early_apex_fraction": 0.40,  # Apex in first 40% of corner = early
    "late_apex_fraction": 0.65,  # Apex after 65% of corner = late
    "offset_threshold_m": 0.8,  # Meters deviation to flag an issue
    "consistency_threshold_m": 1.0,  # SD above this = inconsistent line
}


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
    straight_after_m: float = 0.0  # Distance from exit to next corner entry
    priority_rank: int = 0  # 1 = most important corner on track


@dataclass
class SessionLineProfile:
    """Session-wide summary of driving line patterns across all corners."""

    n_corners: int
    overall_consistency_tier: str  # median of per-corner tiers
    dominant_error_pattern: str | None  # most common non-good_line error if >= 40%
    dominant_error_count: int
    worst_corners_by_line: list[int]  # corner numbers, most inconsistent first
    best_corners_by_line: list[int]  # most consistent first
    type_a_summary: str  # e.g. "Type A corners (T5, T9): 1 developing, 1 consistent"
    mean_apex_sd_m: float


def detect_apex_fraction(
    offsets: np.ndarray,
    corner_start_idx: int,
    corner_end_idx: int,
) -> float:
    """Find the apex (minimum lateral offset = closest to inside) within a corner.

    Returns the apex position as a fraction (0.0 = entry, 1.0 = exit).
    """
    if corner_end_idx <= corner_start_idx:
        return 0.5
    corner_offsets = offsets[corner_start_idx:corner_end_idx]
    if len(corner_offsets) == 0:
        return 0.5
    # Apex = point closest to inside = minimum absolute offset (or most negative)
    apex_local = int(np.argmin(corner_offsets))
    return apex_local / max(len(corner_offsets) - 1, 1)


def classify_line_error(
    apex_fraction: float,
    d_entry: float,
    d_exit: float,
) -> tuple[str, str]:
    """Rule-based classification: (error_type, severity).

    Returns a tuple of (line_error_type, severity).
    """
    thresholds = LINE_ERROR_THRESHOLDS

    # Determine error type
    if apex_fraction < thresholds["early_apex_fraction"]:
        error_type = "early_apex"
    elif apex_fraction > thresholds["late_apex_fraction"]:
        error_type = "late_apex"
    elif abs(d_entry) > thresholds["offset_threshold_m"]:
        error_type = "wide_entry" if d_entry > 0 else "tight_entry"
    elif abs(d_exit) > thresholds["offset_threshold_m"]:
        error_type = "pinched_exit" if d_exit < 0 else "wide_exit"
    else:
        error_type = "good_line"

    # Determine severity from the most deviant metric
    max_dev = max(
        abs(apex_fraction - 0.55) * 4.0,  # Scale fraction to meters-like range
        abs(d_entry),
        abs(d_exit),
    )
    if max_dev < 0.5:
        severity = "minor"
    elif max_dev < 1.5:
        severity = "moderate"
    else:
        severity = "major"

    return error_type, severity


def _consistency_tier(sd: float) -> str:
    """Map lateral SD at apex to a consistency tier."""
    if sd < 0.3:
        return "expert"
    if sd < 0.7:
        return "consistent"
    if sd < 1.5:
        return "developing"
    return "novice"


def _infer_berg_type_and_gap(corner: Corner, corners: list[Corner]) -> tuple[str, float]:
    """Infer Allen Berg corner type and gap to next corner.

    A = corner before a significant straight (exit speed paramount)
    B = corner at end of a straight (entry speed matters)
    C = corner linking other corners (compromise)

    Returns (berg_type, gap_to_next_m) where gap_to_next_m is the distance
    from this corner's exit to the next corner's entry (0.0 for the last corner).

    Note: assumes corners are 1-indexed and contiguous (corner.number == index + 1),
    which is guaranteed by the standard corner detection pipeline in corners.py.
    """
    idx = corner.number - 1
    if idx < 0 or idx >= len(corners):
        return "C", 0.0

    # Compute gap to next corner
    gap_to_next = 0.0
    if idx + 1 < len(corners):
        gap_to_next = corners[idx + 1].entry_distance_m - corner.exit_distance_m

    # Check gap to next corner
    if gap_to_next > 150:  # Long straight follows
        return "A", gap_to_next

    # Check gap from previous corner
    if idx > 0:
        gap_from_prev = corner.entry_distance_m - corners[idx - 1].exit_distance_m
        if gap_from_prev > 150:  # Long straight precedes
            return "B", gap_to_next

    return "C", gap_to_next


def _assign_priority_ranks(profiles: list[CornerLineProfile]) -> None:
    """Assign priority_rank 1..N in-place.

    Sort order: Type A first (longest straight_after_m first), then B, then C.
    Within the same type, longer straight = lower rank number.
    """
    type_order = {"A": 0, "B": 1, "C": 2}
    ranked = sorted(
        range(len(profiles)),
        key=lambda i: (
            type_order.get(profiles[i].allen_berg_type, 2),
            -profiles[i].straight_after_m,
        ),
    )
    for rank, idx in enumerate(ranked, start=1):
        profiles[idx].priority_rank = rank


def analyze_corner_lines(
    traces: list[GPSTrace],
    ref: ReferenceCenterline,
    corners: list[Corner],
) -> list[CornerLineProfile]:
    """Analyze driving line for all corners across all laps.

    Uses lateral offsets relative to the reference centerline to determine
    apex timing, entry/exit offsets, line errors, and consistency.
    """
    if not traces or not corners:
        return []

    min_len = min(len(t.e) for t in traces)
    min_len = min(min_len, len(ref.e))

    # Compute lateral offsets for all laps
    all_offsets: list[np.ndarray] = []
    for trace in traces:
        offsets = compute_lateral_offsets(trace, ref)
        all_offsets.append(offsets[:min_len])

    # Map distance to index (assuming uniform 0.7m spacing)
    spacing = 0.7
    profiles: list[CornerLineProfile] = []

    for corner in corners:
        c_start = int(corner.entry_distance_m / spacing)
        c_end = int(corner.exit_distance_m / spacing)
        c_apex = int(corner.apex_distance_m / spacing)

        # Clamp to valid range
        c_start = max(0, min(c_start, min_len - 1))
        c_end = max(c_start + 1, min(c_end, min_len))
        c_apex = max(c_start, min(c_apex, c_end - 1))

        # Per-lap stats for this corner
        entry_offsets = []
        apex_offsets = []
        exit_offsets = []
        apex_fractions = []

        for offsets in all_offsets:
            if c_end > len(offsets):
                continue
            entry_offsets.append(offsets[c_start])
            apex_offsets.append(offsets[c_apex])
            exit_offsets.append(offsets[max(c_end - 1, 0)])
            frac = detect_apex_fraction(offsets, c_start, c_end)
            apex_fractions.append(frac)

        if not entry_offsets:
            continue

        d_entry_med = float(np.median(entry_offsets))
        d_apex_med = float(np.median(apex_offsets))
        d_exit_med = float(np.median(exit_offsets))
        apex_frac_med = float(np.median(apex_fractions))
        d_apex_sd = float(np.std(apex_offsets)) if len(apex_offsets) > 1 else 0.0

        error_type, severity = classify_line_error(apex_frac_med, d_entry_med, d_exit_med)
        tier = _consistency_tier(d_apex_sd)
        berg_type, gap_to_next = _infer_berg_type_and_gap(corner, corners)

        profiles.append(
            CornerLineProfile(
                corner_number=corner.number,
                n_laps=len(entry_offsets),
                d_entry_median=d_entry_med,
                d_apex_median=d_apex_med,
                d_exit_median=d_exit_med,
                apex_fraction_median=apex_frac_med,
                d_apex_sd=d_apex_sd,
                line_error_type=error_type,
                severity=severity,
                consistency_tier=tier,
                allen_berg_type=berg_type,
                straight_after_m=gap_to_next,
            )
        )

    _assign_priority_ranks(profiles)
    return profiles


def format_line_analysis_for_prompt(profiles: list[CornerLineProfile]) -> str:
    """Format line analysis results as XML for the coaching prompt."""
    if not profiles:
        return ""

    lines = ["<line_analysis>"]
    for p in profiles:
        lines.append(f'  <corner number="{p.corner_number}" type="{p.allen_berg_type}">')
        lines.append(f"    <entry_offset>{p.d_entry_median:+.1f}m from reference</entry_offset>")
        lines.append(
            f"    <apex_offset>{p.d_apex_median:+.1f}m | fraction {p.apex_fraction_median:.0%}"
            f" (ideal: 50-65% for Type A)</apex_offset>"
        )
        lines.append(f"    <exit_offset>{p.d_exit_median:+.1f}m from reference</exit_offset>")
        lines.append(f"    <error_type>{p.line_error_type} ({p.severity})</error_type>")
        lines.append(
            f"    <consistency>apex SD {p.d_apex_sd:.2f}m ({p.consistency_tier})</consistency>"
        )
        lines.append("  </corner>")
    lines.append("</line_analysis>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Session-level line summary
# ---------------------------------------------------------------------------

_TIER_TO_INT: dict[str, int] = {"expert": 0, "consistent": 1, "developing": 2, "novice": 3}
_INT_TO_TIER: dict[int, str] = {v: k for k, v in _TIER_TO_INT.items()}


def summarize_session_lines(
    profiles: list[CornerLineProfile],
) -> SessionLineProfile | None:
    """Summarize driving line patterns across all corners in a session.

    Returns None for empty input.
    """
    if not profiles:
        return None

    # Overall consistency: median tier
    tier_ints = [_TIER_TO_INT[p.consistency_tier] for p in profiles]
    # int() truncates toward 0 (= better tier), which is intentional —
    # gives drivers benefit-of-the-doubt in the overall assessment.
    median_tier_int = int(np.median(tier_ints))
    overall_tier = _INT_TO_TIER[median_tier_int]

    # Dominant error pattern: most common non-"good_line" error >= 40%
    error_counts: Counter[str] = Counter()
    for p in profiles:
        if p.line_error_type != "good_line":
            error_counts[p.line_error_type] += 1

    dominant_error: str | None = None
    dominant_count = 0
    if error_counts:
        most_common_error, count = error_counts.most_common(1)[0]
        if count / len(profiles) >= 0.40:
            dominant_error = most_common_error
            dominant_count = count

    # Sort corners by d_apex_sd
    sorted_by_sd = sorted(profiles, key=lambda p: p.d_apex_sd, reverse=True)
    worst_corners = [p.corner_number for p in sorted_by_sd]
    best_corners = list(reversed(worst_corners))

    # Type A summary
    type_a_profiles = [p for p in profiles if p.allen_berg_type == "A"]
    if type_a_profiles:
        corner_labels = ", ".join(f"T{p.corner_number}" for p in type_a_profiles)
        tier_counts: Counter[str] = Counter(p.consistency_tier for p in type_a_profiles)
        tier_parts = [f"{count} {tier}" for tier, count in tier_counts.most_common()]
        type_a_summary = f"Type A corners ({corner_labels}): {', '.join(tier_parts)}"
    else:
        type_a_summary = "No Type A corners detected"

    # Mean apex SD
    mean_sd = float(np.mean([p.d_apex_sd for p in profiles]))

    return SessionLineProfile(
        n_corners=len(profiles),
        overall_consistency_tier=overall_tier,
        dominant_error_pattern=dominant_error,
        dominant_error_count=dominant_count,
        worst_corners_by_line=worst_corners,
        best_corners_by_line=best_corners,
        type_a_summary=type_a_summary,
        mean_apex_sd_m=mean_sd,
    )


def format_session_line_summary_for_prompt(
    summary: SessionLineProfile | None,
) -> str:
    """Format session line summary as XML for the coaching prompt.

    Returns empty string for None.
    """
    if summary is None:
        return ""

    worst_str = ", ".join(f"T{n}" for n in summary.worst_corners_by_line[:3])
    lines = [
        "<session_line_summary>",
        f"  <overall_consistency>{summary.overall_consistency_tier}</overall_consistency>",
    ]
    if summary.dominant_error_pattern:
        lines.append(
            f"  <dominant_error>{summary.dominant_error_pattern}"
            f" ({summary.dominant_error_count}/{summary.n_corners}"
            f" corners)</dominant_error>"
        )
    lines.extend(
        [
            f"  <worst_corners>{worst_str}</worst_corners>",
            f"  <type_a_assessment>{summary.type_a_summary}</type_a_assessment>",
            f"  <mean_apex_sd>{summary.mean_apex_sd_m:.2f}m</mean_apex_sd>",
            "</session_line_summary>",
        ]
    )
    return "\n".join(lines)

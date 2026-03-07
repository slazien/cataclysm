"""Corner-level driving line analysis on top of GPS trace primitives.

Detects apex location, classifies line errors (early/late apex, wide entry,
pinched exit), and rates consistency tier per corner.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from cataclysm.corners import Corner
from cataclysm.gps_line import GPSTrace, ReferenceCenterline, compute_lateral_offsets

if TYPE_CHECKING:
    import pandas as pd

MIN_LAPS_FOR_BEST_CORNER = 3  # Need at least 3 laps for meaningful best-corner analysis
EXIT_SPEED_AVG_SAMPLES = 5  # Average this many samples around exit point (~200ms at 25Hz)


@dataclass
class PerLapCornerMetrics:
    """Performance metrics for a single corner on a single lap."""

    corner_number: int
    lap_number: int
    segment_time_s: float
    exit_speed_mps: float
    entry_speed_mps: float
    min_speed_mps: float


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

    # Best-corner fields (populated when resampled_laps are available)
    best_lap_number: int | None = None
    best_exit_speed_mps: float | None = None
    best_segment_time_s: float | None = None
    best_ranking_method: str | None = None  # "exit_speed" or "segment_time"
    best_d_entry: float | None = None
    best_d_apex: float | None = None
    best_d_exit: float | None = None
    median_segment_time_s: float | None = None
    median_exit_speed_mps: float | None = None


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


def compute_per_lap_corner_metrics(
    resampled_laps: dict[int, pd.DataFrame],
    corners: list[Corner],
    coaching_laps: list[int],
) -> dict[int, list[PerLapCornerMetrics]]:
    """Compute segment time, exit/entry/min speed for each corner on each lap.

    Returns dict keyed by corner number -> list of per-lap metrics.
    Uses 5-sample averaging at exit point to reduce GPS Doppler noise.
    """
    result: dict[int, list[PerLapCornerMetrics]] = {}
    half_win = EXIT_SPEED_AVG_SAMPLES // 2

    for corner in corners:
        metrics: list[PerLapCornerMetrics] = []
        for lap_num in coaching_laps:
            if lap_num not in resampled_laps:
                continue
            lap_df = resampled_laps[lap_num]
            dist = lap_df["lap_distance_m"].to_numpy()
            time = lap_df["lap_time_s"].to_numpy()
            speed = lap_df["speed_mps"].to_numpy()

            # Skip if corner exit exceeds lap distance range
            if corner.exit_distance_m > dist[-1] or corner.entry_distance_m < dist[0]:
                continue

            # Segment time via interpolation (same pattern as gains.py)
            entry_time = float(np.interp(corner.entry_distance_m, dist, time))
            exit_time = float(np.interp(corner.exit_distance_m, dist, time))
            seg_time = max(0.0, exit_time - entry_time)

            # Exit speed: average over a small window to reduce noise
            exit_idx = int(np.searchsorted(dist, corner.exit_distance_m))
            exit_idx = min(exit_idx, len(speed) - 1)
            lo = max(0, exit_idx - half_win)
            hi = min(len(speed), exit_idx + half_win + 1)
            exit_speed = float(np.mean(speed[lo:hi]))

            # Entry speed (single interp is fine — less critical)
            entry_speed = float(np.interp(corner.entry_distance_m, dist, speed))

            # Min speed through corner zone
            entry_idx = int(np.searchsorted(dist, corner.entry_distance_m))
            entry_idx = min(entry_idx, len(speed) - 1)
            zone = speed[entry_idx : exit_idx + 1]
            min_speed = float(np.min(zone)) if len(zone) > 0 else entry_speed

            metrics.append(
                PerLapCornerMetrics(
                    corner_number=corner.number,
                    lap_number=lap_num,
                    segment_time_s=round(seg_time, 4),
                    exit_speed_mps=round(exit_speed, 3),
                    entry_speed_mps=round(entry_speed, 3),
                    min_speed_mps=round(min_speed, 3),
                )
            )
        result[corner.number] = metrics

    return result


def identify_best_corner_laps(
    per_lap_metrics: dict[int, list[PerLapCornerMetrics]],
    profiles: list[CornerLineProfile],
    corners: list[Corner],
    lap_offsets: dict[int, np.ndarray],
) -> None:
    """Identify the best lap for each corner and update profiles in-place.

    Type A corners: rank by exit speed (descending).
    Type B/C corners: rank by segment time (ascending).
    """
    spacing = 0.7  # Same as used in analyze_corner_lines

    for profile in profiles:
        metrics = per_lap_metrics.get(profile.corner_number, [])
        if len(metrics) < MIN_LAPS_FOR_BEST_CORNER:
            continue

        corner = next((c for c in corners if c.number == profile.corner_number), None)
        if corner is None:
            continue

        # Choose ranking method based on Allen Berg type
        if profile.allen_berg_type == "A":
            best = max(metrics, key=lambda m: m.exit_speed_mps)
            method = "exit_speed"
        else:
            best = min(metrics, key=lambda m: m.segment_time_s)
            method = "segment_time"

        profile.best_lap_number = best.lap_number
        profile.best_exit_speed_mps = best.exit_speed_mps
        profile.best_segment_time_s = best.segment_time_s
        profile.best_ranking_method = method

        # Median values across all laps
        profile.median_segment_time_s = round(
            float(np.median([m.segment_time_s for m in metrics])), 4
        )
        profile.median_exit_speed_mps = round(
            float(np.median([m.exit_speed_mps for m in metrics])), 3
        )

        # Extract best lap's lateral offsets at entry/apex/exit
        best_offsets = lap_offsets.get(best.lap_number)
        if best_offsets is not None:
            c_start = int(corner.entry_distance_m / spacing)
            c_end = int(corner.exit_distance_m / spacing)
            c_apex = int(corner.apex_distance_m / spacing)
            max_idx = len(best_offsets) - 1
            c_start = max(0, min(c_start, max_idx))
            c_end = max(c_start, min(c_end, max_idx))
            c_apex = max(c_start, min(c_apex, c_end))
            profile.best_d_entry = round(float(best_offsets[c_start]), 2)
            profile.best_d_apex = round(float(best_offsets[c_apex]), 2)
            profile.best_d_exit = round(float(best_offsets[c_end]), 2)


def analyze_corner_lines(
    traces: list[GPSTrace],
    ref: ReferenceCenterline,
    corners: list[Corner],
    resampled_laps: dict[int, pd.DataFrame] | None = None,
    coaching_laps: list[int] | None = None,
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

    # Enrich with per-corner best lap data (reuses already-computed offsets)
    if resampled_laps is not None and coaching_laps is not None:
        per_lap = compute_per_lap_corner_metrics(resampled_laps, corners, coaching_laps)
        lap_offsets = {traces[i].lap_number: all_offsets[i] for i in range(len(traces))}
        identify_best_corner_laps(per_lap, profiles, corners, lap_offsets)

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


MPS_TO_MPH = 2.23694


def format_best_corner_for_prompt(profiles: list[CornerLineProfile]) -> str:
    """Format best-corner execution data as XML for the coaching prompt.

    Only includes corners that have best-corner data populated.
    Uses mph for consistency with the rest of the coaching prompt.
    """
    enriched = [p for p in profiles if p.best_lap_number is not None]
    if not enriched:
        return ""

    lines = ["<best_corner_execution>"]
    for p in enriched:
        assert p.best_exit_speed_mps is not None  # noqa: S101
        assert p.median_exit_speed_mps is not None  # noqa: S101
        assert p.best_segment_time_s is not None  # noqa: S101
        assert p.median_segment_time_s is not None  # noqa: S101

        best_exit_mph = p.best_exit_speed_mps * MPS_TO_MPH
        med_exit_mph = p.median_exit_speed_mps * MPS_TO_MPH
        delta_exit_mph = best_exit_mph - med_exit_mph
        delta_time = p.best_segment_time_s - p.median_segment_time_s

        lines.append(
            f'  <corner number="{p.corner_number}" type="{p.allen_berg_type}"'
            f' best_lap="{p.best_lap_number}" ranked_by="{p.best_ranking_method}">'
        )
        lines.append(
            f'    <exit_speed best="{best_exit_mph:.1f} mph"'
            f' median="{med_exit_mph:.1f} mph"'
            f' delta="{delta_exit_mph:+.1f} mph"/>'
        )
        lines.append(
            f'    <segment_time best="{p.best_segment_time_s:.2f}s"'
            f' median="{p.median_segment_time_s:.2f}s"'
            f' delta="{delta_time:+.2f}s"/>'
        )
        if p.best_d_entry is not None:
            lines.append(
                f'    <best_line d_entry="{p.best_d_entry:+.1f}m"'
                f' d_apex="{p.best_d_apex:+.1f}m"'
                f' d_exit="{p.best_d_exit:+.1f}m"/>'
            )
        lines.append("  </corner>")
    lines.append("</best_corner_execution>")
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

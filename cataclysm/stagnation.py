"""Stagnation detection: identify when a driver has plateaued at a track.

Compares best lap times and per-corner performance across recent sessions
to detect plateaus. Produces data-grounded coaching context that surfaces
telemetry patterns without prescribing technique changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

import numpy as np


class SessionSummaryInput(TypedDict, total=False):
    """Expected structure for session summary dicts passed to detect_stagnation."""

    best_lap_time_s: float  # required
    corner_times: dict[int, list[float]]  # optional


@dataclass
class StagnantCorner:
    """A corner where performance has not improved across sessions."""

    corner_number: int
    avg_time_s: float
    variance_s: float
    sessions_flat: int  # how many consecutive sessions with no improvement


@dataclass
class StagnationAnalysis:
    """Analysis of whether a driver has plateaued at a track."""

    is_stagnating: bool
    sessions_analyzed: int
    best_lap_times: list[float]  # best lap time per session (chronological)
    improvement_rate: float  # seconds improved per session (negative = getting faster)
    stagnant_corners: list[StagnantCorner] = field(default_factory=list)


def _compute_improvement_rate(best_times: list[float]) -> float:
    """Compute linear regression slope of best lap times vs session index.

    Returns seconds per session: negative means getting faster,
    positive means getting slower. Zero if fewer than 2 data points.
    """
    n = len(best_times)
    if n < 2:
        return 0.0

    x = np.arange(n, dtype=np.float64)
    y = np.array(best_times, dtype=np.float64)

    # Simple linear regression: slope = cov(x,y) / var(x)
    x_mean = x.mean()
    y_mean = y.mean()
    cov_xy = float(np.sum((x - x_mean) * (y - y_mean)))
    var_x = float(np.sum((x - x_mean) ** 2))

    if var_x < 1e-12:
        return 0.0

    return cov_xy / var_x


def _find_stagnant_corners(
    session_summaries: list[SessionSummaryInput],
    threshold_s: float,
) -> list[StagnantCorner]:
    """Identify corners where times have not improved across sessions.

    Expects each session summary dict to contain a ``corner_times`` key
    mapping corner numbers to lists of per-lap times for that session.
    Falls back to empty if the key is missing.
    """
    # Collect per-corner best times across sessions
    # corner_number -> list of (session_index, best_time) pairs
    corner_bests: dict[int, list[float]] = {}

    for summary in session_summaries:
        corner_times = summary.get("corner_times")
        if not isinstance(corner_times, dict):
            continue
        for corner_num_raw, times_raw in corner_times.items():
            corner_num = int(corner_num_raw)
            if not isinstance(times_raw, list) or not times_raw:
                continue
            # Filter to valid numeric times
            valid_times = [float(t) for t in times_raw if isinstance(t, (int, float)) and t > 0]
            if valid_times:
                corner_bests.setdefault(corner_num, []).append(min(valid_times))

    stagnant: list[StagnantCorner] = []

    for corner_num in sorted(corner_bests):
        bests = corner_bests[corner_num]
        if len(bests) < 2:
            continue

        # Count trailing sessions with no improvement beyond threshold
        best_so_far = bests[0]
        sessions_flat = 0
        for t in bests[1:]:
            if t < best_so_far - threshold_s:
                best_so_far = t
                sessions_flat = 0
            else:
                sessions_flat += 1

        if sessions_flat >= 2:
            avg_t = float(np.mean(bests))
            var_t = float(np.var(bests))
            stagnant.append(
                StagnantCorner(
                    corner_number=corner_num,
                    avg_time_s=round(avg_t, 4),
                    variance_s=round(var_t, 6),
                    sessions_flat=sessions_flat,
                )
            )

    return stagnant


def detect_stagnation(
    session_summaries: list[SessionSummaryInput],
    threshold_s: float = 0.3,
    min_sessions: int = 3,
) -> StagnationAnalysis:
    """Detect if a driver has plateaued based on lap time trends.

    Compares best lap times across the last ``min_sessions`` sessions at the
    same track. If improvement is less than ``threshold_s`` across those
    sessions, the driver is considered stagnating.

    Also identifies specific corners where times have NOT improved while
    others have (corner-level stagnation).

    Parameters
    ----------
    session_summaries
        List of session summary dicts, ordered chronologically (oldest first).
        Each dict should contain at minimum:
        - ``best_lap_time_s`` (float): best lap time for that session
        - ``corner_times`` (dict[int, list[float]]): optional per-corner times
    threshold_s
        Minimum improvement (seconds) to not be considered stagnating.
    min_sessions
        Minimum number of sessions required for stagnation detection.

    Returns
    -------
    StagnationAnalysis
        Analysis result including whether stagnation is detected, the
        improvement rate, and any stagnant corners.
    """
    if len(session_summaries) < min_sessions:
        return StagnationAnalysis(
            is_stagnating=False,
            sessions_analyzed=len(session_summaries),
            best_lap_times=[],
            improvement_rate=0.0,
        )

    # Extract best lap times
    best_times: list[float] = []
    for summary in session_summaries:
        raw = summary.get("best_lap_time_s")
        if isinstance(raw, (int, float)) and raw > 0:
            best_times.append(float(raw))

    if len(best_times) < min_sessions:
        return StagnationAnalysis(
            is_stagnating=False,
            sessions_analyzed=len(session_summaries),
            best_lap_times=best_times,
            improvement_rate=0.0,
        )

    improvement_rate = _compute_improvement_rate(best_times)

    # Check if improvement in the recent window is below threshold.
    # Compare best of last min_sessions to overall best before that window.
    recent = best_times[-min_sessions:]
    earlier = best_times[:-min_sessions] if len(best_times) > min_sessions else []

    if earlier:
        best_earlier = min(earlier)
        best_recent = min(recent)
        improvement = best_earlier - best_recent  # positive = got faster
    else:
        # Only have the window itself: compare first to best
        improvement = recent[0] - min(recent)

    is_stagnating = improvement < threshold_s

    # Corner-level analysis
    stagnant_corners = _find_stagnant_corners(session_summaries, threshold_s)

    return StagnationAnalysis(
        is_stagnating=is_stagnating,
        sessions_analyzed=len(session_summaries),
        best_lap_times=[round(t, 4) for t in best_times],
        improvement_rate=round(improvement_rate, 4),
        stagnant_corners=stagnant_corners,
    )


def build_stagnation_context(analysis: StagnationAnalysis) -> str:
    """Build coaching context for stagnation scenarios.

    Returns a prompt snippet that describes the data patterns WITHOUT
    prescribing physical technique changes.  The AI coach should surface
    data patterns and let the driver investigate.
    """
    if not analysis.is_stagnating:
        return ""

    best_time = min(analysis.best_lap_times) if analysis.best_lap_times else 0.0
    n = analysis.sessions_analyzed

    lines: list[str] = [
        f"The driver has plateaued at {best_time:.3f}s for {n} sessions.",
        f"Improvement rate: {analysis.improvement_rate:+.4f} s/session.",
        f"Best lap times per session: {analysis.best_lap_times}.",
    ]

    if analysis.stagnant_corners:
        corner_details: list[str] = []
        for sc in analysis.stagnant_corners:
            corner_details.append(
                f"  T{sc.corner_number}: avg={sc.avg_time_s:.3f}s, "
                f"variance={sc.variance_s:.4f}s, flat for {sc.sessions_flat} sessions"
            )
        lines.append("Stagnant corners:")
        lines.extend(corner_details)

    lines.append(
        "Identify corners where times have NOT improved while others have. "
        "For each stagnant corner, describe the measurable telemetry pattern "
        "(brake point, min speed, throttle application point) and how it "
        "differs from the driver's own best performance at that corner. "
        "Do NOT prescribe physical technique changes — only surface the data "
        "patterns the driver should investigate."
    )

    return "\n".join(lines)

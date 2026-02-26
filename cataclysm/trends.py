"""Cross-session trend analysis: snapshots, milestones, and trend computation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from cataclysm.consistency import CornerConsistencyEntry, LapConsistency
from cataclysm.corners import Corner
from cataclysm.engine import LapSummary
from cataclysm.gains import GainEstimate
from cataclysm.parser import SessionMetadata

MPS_TO_MPH = 2.23694


@dataclass
class CornerTrendEntry:
    """Aggregated corner metrics for one session (used in cross-session trending)."""

    corner_number: int
    min_speed_mean_mph: float
    min_speed_std_mph: float
    brake_point_mean_m: float | None
    brake_point_std_m: float | None
    peak_brake_g_mean: float | None
    throttle_commit_mean_m: float | None
    throttle_commit_std_m: float | None
    consistency_score: float


@dataclass
class SessionSnapshot:
    """Lightweight summary of a single session (~5KB) for cross-session trending.

    Stores only scalar metrics and small lists — never full DataFrames.
    """

    session_id: str
    metadata: SessionMetadata
    session_date_parsed: datetime
    n_laps: int
    n_clean_laps: int
    best_lap_time_s: float
    top3_avg_time_s: float
    avg_lap_time_s: float
    consistency_score: float
    std_dev_s: float
    theoretical_best_s: float
    composite_best_s: float
    lap_times_s: list[float]
    corner_metrics: list[CornerTrendEntry]
    lap_consistency: LapConsistency
    corner_consistency: list[CornerConsistencyEntry]
    gps_quality_score: float = 100.0
    gps_quality_grade: str = "A"

    @property
    def optimal_lap_time_s(self) -> float:
        """Best theoretical lap time (min of composite and theoretical)."""
        return min(self.theoretical_best_s, self.composite_best_s)


@dataclass
class Milestone:
    """A notable achievement detected across sessions."""

    session_id: str
    session_date: str
    category: str  # "pb", "consistency", "sub_threshold"
    description: str
    value: float


@dataclass
class TrendAnalysis:
    """Cross-session trend data for a single track."""

    track_name: str
    sessions: list[SessionSnapshot]  # sorted chronologically
    n_sessions: int
    best_lap_trend: list[float]
    top3_avg_trend: list[float]
    consistency_trend: list[float]
    theoretical_trend: list[float]
    corner_min_speed_trends: dict[int, list[float | None]]
    corner_brake_std_trends: dict[int, list[float | None]]
    corner_consistency_trends: dict[int, list[float | None]]
    milestones: list[Milestone] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%d/%m/%Y %H:%M",  # RaceChrono EU format
    "%d/%m/%Y,%H:%M",  # RaceChrono comma-separated
    "%m/%d/%Y %H:%M",  # US format
    "%Y-%m-%d %H:%M:%S",  # ISO
    "%Y-%m-%d %H:%M",  # ISO short
    "%Y-%m-%dT%H:%M:%S",  # ISO 8601
    "%Y-%m-%dT%H:%M",  # ISO 8601 short
    "%d/%m/%Y",  # Date only EU
    "%Y-%m-%d",  # Date only ISO
]


def _parse_session_date(date_str: str) -> datetime:
    """Parse a RaceChrono date string into a datetime.

    Tries multiple formats. Falls back to datetime.min if unparseable.
    """
    cleaned = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)  # noqa: DTZ007
        except ValueError:
            continue
    # Last resort: return epoch so sorting still works
    return datetime.min  # noqa: DTZ001


def _compute_session_id(file_key: str, track_name: str, date_str: str) -> str:
    """Generate a unique, deterministic session ID.

    Format: ``{track}_{YYYYMMDD}_{hash8}`` where hash8 is the first 8 hex
    chars of the SHA-256 of the full file key.
    """
    dt = _parse_session_date(date_str)
    date_part = dt.strftime("%Y%m%d") if dt != datetime.min else "unknown"  # noqa: DTZ001
    track_slug = track_name.lower().replace(" ", "_")[:20]
    hash8 = hashlib.sha256(file_key.encode()).hexdigest()[:8]
    return f"{track_slug}_{date_part}_{hash8}"


# ---------------------------------------------------------------------------
# Snapshot builder
# ---------------------------------------------------------------------------


def _build_corner_trend_entries(
    all_lap_corners: dict[int, list[Corner]],
    corner_consistency: list[CornerConsistencyEntry],
) -> list[CornerTrendEntry]:
    """Aggregate per-corner metrics across all laps into trend entries."""
    cc_map = {e.corner_number: e for e in corner_consistency}

    # Discover all corner numbers
    all_numbers: set[int] = set()
    for corners in all_lap_corners.values():
        for c in corners:
            all_numbers.add(c.number)

    entries: list[CornerTrendEntry] = []
    for cn in sorted(all_numbers):
        min_speeds: list[float] = []
        brake_points: list[float] = []
        peak_brakes: list[float] = []
        throttle_commits: list[float] = []

        for corners in all_lap_corners.values():
            for c in corners:
                if c.number != cn:
                    continue
                min_speeds.append(c.min_speed_mps * MPS_TO_MPH)
                if c.brake_point_m is not None:
                    brake_points.append(c.brake_point_m)
                if c.peak_brake_g is not None:
                    peak_brakes.append(c.peak_brake_g)
                if c.throttle_commit_m is not None:
                    throttle_commits.append(c.throttle_commit_m)

        if not min_speeds:
            continue

        speed_arr = np.array(min_speeds)
        cc = cc_map.get(cn)

        entries.append(
            CornerTrendEntry(
                corner_number=cn,
                min_speed_mean_mph=round(float(np.mean(speed_arr)), 2),
                min_speed_std_mph=round(float(np.std(speed_arr)), 2),
                brake_point_mean_m=(
                    round(float(np.mean(brake_points)), 1) if brake_points else None
                ),
                brake_point_std_m=(round(float(np.std(brake_points)), 1) if brake_points else None),
                peak_brake_g_mean=(round(float(np.mean(peak_brakes)), 3) if peak_brakes else None),
                throttle_commit_mean_m=(
                    round(float(np.mean(throttle_commits)), 1) if throttle_commits else None
                ),
                throttle_commit_std_m=(
                    round(float(np.std(throttle_commits)), 1) if throttle_commits else None
                ),
                consistency_score=cc.consistency_score if cc else 0.0,
            )
        )

    return entries


def build_session_snapshot(
    metadata: SessionMetadata,
    summaries: list[LapSummary],
    lap_consistency: LapConsistency,
    corner_consistency: list[CornerConsistencyEntry],
    gains: GainEstimate | None,
    all_lap_corners: dict[int, list[Corner]],
    anomalous_laps: set[int],
    file_key: str,
    *,
    gps_quality_score: float = 100.0,
    gps_quality_grade: str = "A",
) -> SessionSnapshot:
    """Extract a lightweight snapshot from single-session pipeline outputs.

    Takes exactly the objects ``app.py`` already computes per session.
    """
    clean_summaries = sorted(
        [s for s in summaries if s.lap_number not in anomalous_laps],
        key=lambda s: s.lap_time_s,
    )

    lap_times = [s.lap_time_s for s in clean_summaries]
    n_clean = len(clean_summaries)

    best_time = lap_times[0] if lap_times else 0.0
    avg_time = float(np.mean(lap_times)) if lap_times else 0.0

    # Top-3 average: use min(3, n_clean) fastest laps
    top3_count = min(3, n_clean)
    top3_avg = float(np.mean(lap_times[:top3_count])) if top3_count > 0 else 0.0

    theoretical_best = gains.theoretical.theoretical_time_s if gains else best_time
    composite_best = gains.composite.composite_time_s if gains else best_time

    corner_entries = _build_corner_trend_entries(all_lap_corners, corner_consistency)

    session_id = _compute_session_id(file_key, metadata.track_name, metadata.session_date)
    session_date = _parse_session_date(metadata.session_date)

    return SessionSnapshot(
        session_id=session_id,
        metadata=metadata,
        session_date_parsed=session_date,
        n_laps=len(summaries),
        n_clean_laps=n_clean,
        best_lap_time_s=round(best_time, 3),
        top3_avg_time_s=round(top3_avg, 3),
        avg_lap_time_s=round(avg_time, 3),
        consistency_score=lap_consistency.consistency_score,
        std_dev_s=lap_consistency.std_dev_s,
        theoretical_best_s=round(theoretical_best, 3),
        composite_best_s=round(composite_best, 3),
        lap_times_s=lap_times,
        corner_metrics=corner_entries,
        lap_consistency=lap_consistency,
        corner_consistency=corner_consistency,
        gps_quality_score=gps_quality_score,
        gps_quality_grade=gps_quality_grade,
    )


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


def _compute_milestones(sorted_snapshots: list[SessionSnapshot]) -> list[Milestone]:
    """Detect PBs, consistency breakthroughs, and sub-X thresholds.

    ``sorted_snapshots`` must be in chronological order.
    """
    milestones: list[Milestone] = []
    running_best = float("inf")
    prev_consistency: float | None = None

    # Time barriers to check (in seconds): every 5s from 1:00 to 3:00
    time_barriers = list(range(60, 181, 5))
    crossed_barriers: set[int] = set()

    for snap in sorted_snapshots:
        # PB detection
        if snap.best_lap_time_s < running_best:
            if running_best < float("inf"):
                improvement = running_best - snap.best_lap_time_s
                milestones.append(
                    Milestone(
                        session_id=snap.session_id,
                        session_date=snap.metadata.session_date,
                        category="pb",
                        description=f"New PB: {_fmt_time(snap.best_lap_time_s)} "
                        f"(-{improvement:.2f}s)",
                        value=snap.best_lap_time_s,
                    )
                )
            running_best = snap.best_lap_time_s
        else:
            # Still track barriers against running best
            pass

        # Consistency breakthrough (10+ point improvement)
        if prev_consistency is not None:
            delta = snap.consistency_score - prev_consistency
            if delta >= 10.0:
                milestones.append(
                    Milestone(
                        session_id=snap.session_id,
                        session_date=snap.metadata.session_date,
                        category="consistency",
                        description=f"Consistency breakthrough: "
                        f"{snap.consistency_score:.0f}/100 (+{delta:.0f})",
                        value=snap.consistency_score,
                    )
                )
        prev_consistency = snap.consistency_score

        # Sub-threshold detection
        for barrier in time_barriers:
            if barrier not in crossed_barriers and snap.best_lap_time_s < barrier:
                crossed_barriers.add(barrier)
                # Only report if the barrier is close to the actual time
                # (within 5s above) to avoid flooding milestones
                if snap.best_lap_time_s >= barrier - 5:
                    milestones.append(
                        Milestone(
                            session_id=snap.session_id,
                            session_date=snap.metadata.session_date,
                            category="sub_threshold",
                            description=f"Sub-{_fmt_time(float(barrier))} achieved: "
                            f"{_fmt_time(snap.best_lap_time_s)}",
                            value=snap.best_lap_time_s,
                        )
                    )

    return milestones


def _fmt_time(t: float) -> str:
    """Format seconds as m:ss.xx."""
    m = int(t // 60)
    s = t % 60
    return f"{m}:{s:05.2f}"


# ---------------------------------------------------------------------------
# Common corners
# ---------------------------------------------------------------------------


def _find_common_corners(snapshots: list[SessionSnapshot]) -> list[int]:
    """Find corner numbers present in ALL sessions (for stable trending)."""
    if not snapshots:
        return []

    sets = [{e.corner_number for e in snap.corner_metrics} for snap in snapshots]
    common = sets[0]
    for s in sets[1:]:
        common &= s

    return sorted(common)


# ---------------------------------------------------------------------------
# Trend computation
# ---------------------------------------------------------------------------


def compute_trend_analysis(snapshots: list[SessionSnapshot]) -> TrendAnalysis:
    """Compute cross-session trends from same-track snapshots.

    Parameters
    ----------
    snapshots:
        Two or more SessionSnapshot objects for the same track.

    Returns
    -------
    TrendAnalysis with trend arrays and milestones.

    Raises
    ------
    ValueError
        If fewer than 2 snapshots are provided.
    """
    if len(snapshots) < 2:
        msg = "At least 2 sessions required for trend analysis."
        raise ValueError(msg)

    # Sort chronologically
    sorted_snaps = sorted(snapshots, key=lambda s: s.session_date_parsed)
    track_name = sorted_snaps[0].metadata.track_name

    # Primary metric trends
    best_lap_trend = [s.best_lap_time_s for s in sorted_snaps]
    top3_avg_trend = [s.top3_avg_time_s for s in sorted_snaps]
    consistency_trend = [s.consistency_score for s in sorted_snaps]
    theoretical_trend = [s.theoretical_best_s for s in sorted_snaps]

    # Corner-level trends (only for corners present in all sessions)
    common_corners = _find_common_corners(sorted_snaps)

    corner_min_speed_trends: dict[int, list[float | None]] = {}
    corner_brake_std_trends: dict[int, list[float | None]] = {}
    corner_consistency_trends: dict[int, list[float | None]] = {}

    for cn in common_corners:
        speed_trend: list[float | None] = []
        brake_std_trend: list[float | None] = []
        consistency_trend_cn: list[float | None] = []

        for snap in sorted_snaps:
            entry = next(
                (e for e in snap.corner_metrics if e.corner_number == cn),
                None,
            )
            if entry is not None:
                speed_trend.append(entry.min_speed_mean_mph)
                brake_std_trend.append(entry.brake_point_std_m)
                consistency_trend_cn.append(entry.consistency_score)
            else:
                speed_trend.append(None)
                brake_std_trend.append(None)
                consistency_trend_cn.append(None)

        corner_min_speed_trends[cn] = speed_trend
        corner_brake_std_trends[cn] = brake_std_trend
        corner_consistency_trends[cn] = consistency_trend_cn

    milestones = _compute_milestones(sorted_snaps)

    return TrendAnalysis(
        track_name=track_name,
        sessions=sorted_snaps,
        n_sessions=len(sorted_snaps),
        best_lap_trend=best_lap_trend,
        top3_avg_trend=top3_avg_trend,
        consistency_trend=consistency_trend,
        theoretical_trend=theoretical_trend,
        corner_min_speed_trends=corner_min_speed_trends,
        corner_brake_std_trends=corner_brake_std_trends,
        corner_consistency_trends=corner_consistency_trends,
        milestones=milestones,
    )

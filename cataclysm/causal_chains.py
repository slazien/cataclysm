"""Inter-corner causal chain detection for coaching insights.

Detects how poor execution in one corner cascades to affect downstream
corners via the connecting straights. Uses per-lap corner data to find
statistical correlations between consecutive corner metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from cataclysm.constants import MPS_TO_MPH
from cataclysm.corners import Corner

logger = logging.getLogger(__name__)

# Minimum laps required for meaningful correlation.
_MIN_LAPS_FOR_CORRELATION = 5

# Correlation threshold for detecting a causal link.
_CAUSAL_R_THRESHOLD = 0.50

# Minimum number of causal links to form a chain.
_MIN_CHAIN_LENGTH = 2


@dataclass
class CornerLink:
    """A detected causal link between two consecutive corners."""

    upstream_corner: int
    downstream_corner: int
    metric_pair: str  # e.g. "min_speed → min_speed"
    pearson_r: float
    n_laps: int
    recovery_fraction: float  # 0.0 = no recovery, 1.0 = full recovery
    straight_distance_m: float


@dataclass
class CausalChain:
    """A chain of causally linked corners (A → B → C)."""

    links: list[CornerLink]
    root_corner: int
    total_cascade_cost_s: float  # estimated time cost from the cascade

    @property
    def chain_corners(self) -> list[int]:
        """All corners in the chain, in order."""
        corners = [self.links[0].upstream_corner]
        corners.extend(link.downstream_corner for link in self.links)
        return corners

    @property
    def length(self) -> int:
        return len(self.links)


@dataclass
class TimeKiller:
    """A corner whose poor execution causes the most cascading time loss."""

    corner: int
    direct_cost_s: float  # time lost at this corner itself
    cascade_cost_s: float  # time lost at downstream corners due to cascade
    total_cost_s: float  # direct + cascade
    affected_corners: list[int]


@dataclass
class SessionCausalAnalysis:
    """Complete causal chain analysis for a session."""

    links: list[CornerLink]
    chains: list[CausalChain]
    time_killer: TimeKiller | None
    n_laps_analyzed: int


def _extract_lap_metrics(
    all_lap_corners: dict[int, list[Corner]],
    corner_number: int,
    anomalous_laps: set[int] | None = None,
) -> dict[int, dict[str, float | None]]:
    """Extract per-lap metrics for a specific corner.

    Returns {lap_number: {metric_name: value}} for clean laps.
    """
    anomalous = anomalous_laps or set()
    result: dict[int, dict[str, float | None]] = {}
    for lap_num, corners in all_lap_corners.items():
        if lap_num in anomalous:
            continue
        for c in corners:
            if c.number == corner_number:
                result[lap_num] = {
                    "min_speed_mph": c.min_speed_mps * MPS_TO_MPH,
                    "brake_point_m": c.brake_point_m,
                    "throttle_commit_m": c.throttle_commit_m,
                    "peak_brake_g": c.peak_brake_g,
                }
                break
    return result


def compute_recovery_fraction(
    straight_distance_m: float,
    typical_accel_g: float = 0.4,
) -> float:
    """Estimate what fraction of an exit speed deficit is recovered on a straight.

    Uses v² = v₀² + 2ad physics. A shorter straight means less recovery.
    A typical track car accelerates at ~0.3-0.5g on a straight.

    Returns a value between 0.0 (no recovery) and 1.0 (full recovery).
    """
    if straight_distance_m <= 0:
        return 0.0

    # Reference: a 5 mph deficit at 60 mph with 0.4g accel
    # v² = v₀² + 2ad → need ~70m to recover 5 mph deficit
    # At 80 mph exit, need ~90m to recover 5 mph
    # Normalize: recovery_fraction = 1 - exp(-distance / characteristic_length)
    # Characteristic length ~100m for typical accel
    accel_mps2 = typical_accel_g * 9.81
    # Characteristic length = v_typical² / (2 * accel) where v_typical ~ 30 m/s (~67 mph)
    char_length = (30.0**2) / (2.0 * accel_mps2)
    fraction = 1.0 - np.exp(-straight_distance_m / char_length)
    return float(min(fraction, 1.0))


def _compute_link(
    all_lap_corners: dict[int, list[Corner]],
    upstream: int,
    downstream: int,
    anomalous_laps: set[int] | None = None,
) -> CornerLink | None:
    """Compute causal link between two consecutive corners.

    Tests multiple metric pairs and returns the strongest link found,
    or None if no significant correlation exists.
    """
    up_metrics = _extract_lap_metrics(all_lap_corners, upstream, anomalous_laps)
    down_metrics = _extract_lap_metrics(all_lap_corners, downstream, anomalous_laps)

    # Find laps present in both corners
    common_laps = sorted(set(up_metrics) & set(down_metrics))
    if len(common_laps) < _MIN_LAPS_FOR_CORRELATION:
        return None

    # Compute straight distance between the two corners
    # Use first lap's corner data for geometry
    first_lap = next(iter(all_lap_corners.values()))
    up_exit = None
    down_entry = None
    for c in first_lap:
        if c.number == upstream:
            up_exit = c.exit_distance_m
        if c.number == downstream:
            down_entry = c.entry_distance_m
    if up_exit is None or down_entry is None:
        return None

    straight_dist = down_entry - up_exit
    if straight_dist < 0:
        # Wrap-around (last corner to first) — skip for now
        return None

    recovery = compute_recovery_fraction(straight_dist)

    # Test metric pairs for correlation
    metric_pairs = [
        ("min_speed_mph", "min_speed_mph"),
        ("min_speed_mph", "brake_point_m"),
        ("throttle_commit_m", "brake_point_m"),
        ("throttle_commit_m", "min_speed_mph"),
    ]

    best_link: CornerLink | None = None
    best_abs_r = 0.0

    for up_metric, down_metric in metric_pairs:
        up_vals = []
        down_vals = []
        for lap in common_laps:
            uv = up_metrics[lap].get(up_metric)
            dv = down_metrics[lap].get(down_metric)
            if uv is not None and dv is not None:
                up_vals.append(uv)
                down_vals.append(dv)

        if len(up_vals) < _MIN_LAPS_FOR_CORRELATION:
            continue

        up_arr = np.array(up_vals)
        down_arr = np.array(down_vals)

        # Skip if either series has zero variance
        if np.std(up_arr) < 1e-9 or np.std(down_arr) < 1e-9:
            continue

        r = float(np.corrcoef(up_arr, down_arr)[0, 1])

        # For min_speed → min_speed, expect positive correlation (both drop together)
        # For min_speed → brake_point, expect negative (slower exit → later brake)
        # We care about absolute correlation strength
        if abs(r) > best_abs_r and abs(r) >= _CAUSAL_R_THRESHOLD:
            best_abs_r = abs(r)
            label = f"{up_metric.replace('_mph', '').replace('_m', '')} → "
            label += f"{down_metric.replace('_mph', '').replace('_m', '')}"
            best_link = CornerLink(
                upstream_corner=upstream,
                downstream_corner=downstream,
                metric_pair=label,
                pearson_r=r,
                n_laps=len(up_vals),
                recovery_fraction=recovery,
                straight_distance_m=straight_dist,
            )

    return best_link


def _build_chains(links: list[CornerLink]) -> list[CausalChain]:
    """Build chains from individual links by following connected corners.

    A chain is a sequence where upstream_corner of link N+1 equals
    downstream_corner of link N.
    """
    if not links:
        return []

    # Index links by upstream corner
    by_upstream: dict[int, CornerLink] = {}
    downstream_set: set[int] = set()
    for link in links:
        by_upstream[link.upstream_corner] = link
        downstream_set.add(link.downstream_corner)

    # Find chain roots: upstream corners that are not downstream of anything
    roots = [link.upstream_corner for link in links if link.upstream_corner not in downstream_set]

    # If no clear root, start from the link with highest absolute correlation
    if not roots:
        roots = [max(links, key=lambda lnk: abs(lnk.pearson_r)).upstream_corner]

    chains: list[CausalChain] = []
    visited: set[int] = set()

    for root in roots:
        if root in visited:
            continue
        chain_links: list[CornerLink] = []
        current = root
        while current in by_upstream and current not in visited:
            visited.add(current)
            link = by_upstream[current]
            chain_links.append(link)
            current = link.downstream_corner

        if len(chain_links) >= _MIN_CHAIN_LENGTH:
            # Estimate cascade cost: sum of (1 - recovery) * upstream correlation
            cascade_cost = sum(
                (1.0 - link.recovery_fraction) * abs(link.pearson_r) * 0.1 for link in chain_links
            )
            chains.append(
                CausalChain(
                    links=chain_links,
                    root_corner=root,
                    total_cascade_cost_s=round(cascade_cost, 3),
                )
            )

    return chains


def _find_time_killer(
    links: list[CornerLink],
    all_lap_corners: dict[int, list[Corner]],
    anomalous_laps: set[int] | None = None,
) -> TimeKiller | None:
    """Find the corner whose poor execution causes the most total time loss.

    Combines direct time cost (variance at the corner itself) with
    cascade cost (downstream impact weighted by correlation and recovery).
    """
    if not links:
        return None

    anomalous = anomalous_laps or set()

    # Compute direct cost per corner: std of min_speed * time_per_mph approximation
    # Rough estimate: 1 mph of min speed variance ≈ 0.05s at a typical corner
    corner_direct_cost: dict[int, float] = {}
    for lap_corners in all_lap_corners.values():
        for c in lap_corners:
            if c.number not in corner_direct_cost:
                corner_direct_cost[c.number] = 0.0

    for corner_num in corner_direct_cost:
        speeds = []
        for lap_num, corners in all_lap_corners.items():
            if lap_num in anomalous:
                continue
            for c in corners:
                if c.number == corner_num:
                    speeds.append(c.min_speed_mps * MPS_TO_MPH)
                    break
        if len(speeds) >= 2:
            corner_direct_cost[corner_num] = float(np.std(speeds)) * 0.05

    # Build downstream impact from links
    cascade_costs: dict[int, float] = {}
    affected: dict[int, list[int]] = {}
    for link in links:
        up = link.upstream_corner
        cascade_impact = (1.0 - link.recovery_fraction) * abs(link.pearson_r) * 0.1
        cascade_costs[up] = cascade_costs.get(up, 0.0) + cascade_impact
        if up not in affected:
            affected[up] = []
        affected[up].append(link.downstream_corner)

    # Find the corner with highest total cost
    best_corner = None
    best_total = 0.0
    for corner_num in corner_direct_cost:
        direct = corner_direct_cost[corner_num]
        cascade = cascade_costs.get(corner_num, 0.0)
        total = direct + cascade
        if total > best_total:
            best_total = total
            best_corner = corner_num

    if best_corner is None or best_total < 0.01:
        return None

    return TimeKiller(
        corner=best_corner,
        direct_cost_s=round(corner_direct_cost[best_corner], 3),
        cascade_cost_s=round(cascade_costs.get(best_corner, 0.0), 3),
        total_cost_s=round(best_total, 3),
        affected_corners=affected.get(best_corner, []),
    )


def compute_causal_analysis(
    all_lap_corners: dict[int, list[Corner]],
    anomalous_laps: set[int] | None = None,
) -> SessionCausalAnalysis:
    """Compute inter-corner causal chain analysis for a session.

    Analyzes correlations between consecutive corners to detect
    performance cascades. Returns chains and the "TimeKiller" corner.
    """
    if not all_lap_corners:
        return SessionCausalAnalysis(
            links=[],
            chains=[],
            time_killer=None,
            n_laps_analyzed=0,
        )

    anomalous = anomalous_laps or set()
    clean_laps = {lap for lap in all_lap_corners if lap not in anomalous}

    if len(clean_laps) < _MIN_LAPS_FOR_CORRELATION:
        return SessionCausalAnalysis(
            links=[],
            chains=[],
            time_killer=None,
            n_laps_analyzed=len(clean_laps),
        )

    # Get corner numbers from first lap (they should be consistent across laps)
    first_lap_corners = next(iter(all_lap_corners.values()))
    corner_numbers = sorted(c.number for c in first_lap_corners)

    if len(corner_numbers) < 2:
        return SessionCausalAnalysis(
            links=[],
            chains=[],
            time_killer=None,
            n_laps_analyzed=len(clean_laps),
        )

    # Compute links between all consecutive corner pairs
    links: list[CornerLink] = []
    for i in range(len(corner_numbers) - 1):
        link = _compute_link(
            all_lap_corners,
            corner_numbers[i],
            corner_numbers[i + 1],
            anomalous,
        )
        if link is not None:
            links.append(link)

    # Build chains from links
    chains = _build_chains(links)

    # Find the TimeKiller
    time_killer = _find_time_killer(links, all_lap_corners, anomalous)

    logger.info(
        "Causal analysis: %d links, %d chains, time_killer=T%s (%d clean laps)",
        len(links),
        len(chains),
        time_killer.corner if time_killer else "none",
        len(clean_laps),
    )

    return SessionCausalAnalysis(
        links=links,
        chains=chains,
        time_killer=time_killer,
        n_laps_analyzed=len(clean_laps),
    )


def format_causal_context_for_prompt(analysis: SessionCausalAnalysis) -> str:
    """Format causal chain analysis as text for the coaching prompt."""
    if not analysis.links:
        return ""

    lines = ["\n## Inter-Corner Causal Chains"]
    lines.append(
        "These correlations show how performance at one corner "
        "affects the next. Coach the ROOT corner, not the downstream symptom."
    )
    lines.append("")

    for link in analysis.links:
        recovery_pct = link.recovery_fraction * 100
        lines.append(
            f"- T{link.upstream_corner} → T{link.downstream_corner}: "
            f"r={link.pearson_r:.2f} ({link.metric_pair}), "
            f"straight={link.straight_distance_m:.0f}m, "
            f"recovery={recovery_pct:.0f}%"
        )

    if analysis.chains:
        lines.append("")
        lines.append("### Cascade Chains")
        for chain in analysis.chains:
            corners = " → ".join(f"T{c}" for c in chain.chain_corners)
            lines.append(f"- {corners} (cascade cost: ~{chain.total_cascade_cost_s:.3f}s)")

    if analysis.time_killer:
        tk = analysis.time_killer
        lines.append("")
        lines.append(f"### TimeKiller: T{tk.corner}")
        lines.append(
            f"Direct cost: ~{tk.direct_cost_s:.3f}s, "
            f"cascade cost: ~{tk.cascade_cost_s:.3f}s, "
            f"total: ~{tk.total_cost_s:.3f}s"
        )
        if tk.affected_corners:
            affected = ", ".join(f"T{c}" for c in tk.affected_corners)
            lines.append(f"Affects: {affected}")
        lines.append(
            "IMPORTANT: Improving this corner will have outsized impact "
            "because it cascades to downstream corners."
        )

    return "\n".join(lines)

"""Auto-classify corner types from curvature and geometry metrics.

Classification uses curvature magnitude, heading change, arc length, and speed loss
to assign one of: hairpin, sweeper, kink, chicane, esses, carousel, complex.
Sequence analysis detects multi-corner patterns (chicane, esses).

Reference thresholds from SAE / MoTeC / Driver61 motorsport engineering sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Single-corner curvature thresholds (1/m)
# ---------------------------------------------------------------------------
HAIRPIN_MIN_CURVATURE = 0.02
SWEEPER_MIN_CURVATURE = 0.005

# ---------------------------------------------------------------------------
# Heading change thresholds (degrees, absolute)
# ---------------------------------------------------------------------------
HAIRPIN_MIN_HEADING_DEG = 120.0
SWEEPER_MIN_HEADING_DEG = 30.0
KINK_MAX_HEADING_DEG = 25.0

# ---------------------------------------------------------------------------
# Arc length thresholds (metres)
# ---------------------------------------------------------------------------
HAIRPIN_MAX_ARC_M = 50.0
SWEEPER_MIN_ARC_M = 150.0
SWEEPER_MAX_ARC_M = 200.0
KINK_MAX_ARC_M = 30.0
KINK_MAX_SPEED_LOSS_PCT = 5.0

# ---------------------------------------------------------------------------
# Carousel thresholds
# ---------------------------------------------------------------------------
CAROUSEL_MIN_CURVATURE = 0.015
CAROUSEL_MIN_ARC_M = 100.0
CAROUSEL_MIN_HEADING_DEG = 180.0

# ---------------------------------------------------------------------------
# Sequence detection thresholds
# ---------------------------------------------------------------------------
SEQUENCE_MAX_GAP_M = 80.0  # max gap between exit and next entry
ESSES_MIN_COUNT = 3  # minimum alternating corners for esses


@dataclass
class CornerClassification:
    """Result of geometry-based corner type classification."""

    corner_type: str  # "hairpin"|"sweeper"|"kink"|"chicane"|"esses"|"carousel"|"complex"
    confidence: float  # 0.0 - 1.0
    reasoning: str


def _clamp_confidence(value: float) -> float:
    """Clamp confidence to [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def classify_corner(
    *,
    peak_curvature: float,
    heading_change_deg: float,
    arc_length_m: float,
    speed_loss_pct: float = 0.0,
    curvature_variation_index: float = 0.0,
) -> CornerClassification:
    """Classify a single corner from its geometry metrics.

    Args:
        peak_curvature: Maximum curvature in 1/m (always >= 0).
        heading_change_deg: Absolute heading change through the corner in degrees.
        arc_length_m: Length of the corner arc in metres.
        speed_loss_pct: Percent speed loss through the corner (0-100).
        curvature_variation_index: Curvature variation metric for future tuning.

    Returns:
        CornerClassification with type, confidence, and reasoning.
    """
    curv = abs(peak_curvature)
    heading = abs(heading_change_deg)
    arc = abs(arc_length_m)
    speed_loss = abs(speed_loss_pct)
    curvature_variation = abs(curvature_variation_index)

    # Guard: degenerate inputs
    if curv <= 0.0 and heading <= 0.0:
        if speed_loss < KINK_MAX_SPEED_LOSS_PCT:
            return CornerClassification(
                corner_type="kink",
                confidence=0.3,
                reasoning="Near-zero curvature and heading change; defaulting to kink",
            )
        return CornerClassification(
            corner_type="complex",
            confidence=0.4,
            reasoning=(
                "Near-zero curvature/heading but elevated speed loss "
                f"({speed_loss:.1f}%) suggests non-kink behavior"
            ),
        )

    # --- Carousel: long, high-curvature, large heading change ---
    if (
        curv >= CAROUSEL_MIN_CURVATURE
        and arc >= CAROUSEL_MIN_ARC_M
        and heading >= CAROUSEL_MIN_HEADING_DEG
    ):
        conf = _clamp_confidence(
            0.5
            + 0.2 * min((curv - CAROUSEL_MIN_CURVATURE) / 0.01, 1.0)
            + 0.15 * min((arc - CAROUSEL_MIN_ARC_M) / 100.0, 1.0)
            + 0.15 * min((heading - CAROUSEL_MIN_HEADING_DEG) / 60.0, 1.0)
        )
        return CornerClassification(
            corner_type="carousel",
            confidence=conf,
            reasoning=(
                f"High curvature ({curv:.4f} 1/m), long arc ({arc:.0f}m), "
                f"large heading change ({heading:.0f} deg)"
            ),
        )

    # --- Hairpin: tight corner by high curvature OR large heading on short arc ---
    if (
        curv >= HAIRPIN_MIN_CURVATURE or heading >= HAIRPIN_MIN_HEADING_DEG
    ) and arc <= HAIRPIN_MAX_ARC_M:
        # Confidence increases with curvature/heading evidence and decreases as
        # arc approaches/exceeds typical tight-corner length.
        arc_penalty = max(0.0, (arc - HAIRPIN_MAX_ARC_M) / HAIRPIN_MAX_ARC_M) * 0.2
        conf = _clamp_confidence(
            0.5
            + 0.2 * min((curv - HAIRPIN_MIN_CURVATURE) / 0.02, 1.0)
            + 0.2 * min((heading - HAIRPIN_MIN_HEADING_DEG) / 60.0, 1.0)
            - arc_penalty
        )
        return CornerClassification(
            corner_type="hairpin",
            confidence=conf,
            reasoning=(
                f"Tight geometry ({curv:.4f} 1/m, {heading:.0f} deg) on short arc {arc:.0f}m"
            ),
        )

    # --- Sweeper: moderate curvature, moderate heading, medium arc ---
    if (
        curv >= SWEEPER_MIN_CURVATURE
        and heading >= SWEEPER_MIN_HEADING_DEG
        and arc > SWEEPER_MIN_ARC_M
    ):
        # Confidence peaks when arc is in the sweet spot
        arc_fit = 1.0
        if arc <= SWEEPER_MIN_ARC_M:
            arc_fit = arc / SWEEPER_MIN_ARC_M
        elif arc > SWEEPER_MAX_ARC_M:
            arc_fit = max(0.3, 1.0 - (arc - SWEEPER_MAX_ARC_M) / SWEEPER_MAX_ARC_M)
        conf = _clamp_confidence(
            0.4
            + 0.2 * min((curv - SWEEPER_MIN_CURVATURE) / 0.015, 1.0)
            + 0.2 * min((heading - SWEEPER_MIN_HEADING_DEG) / 30.0, 1.0)
            + 0.2 * arc_fit
        )
        return CornerClassification(
            corner_type="sweeper",
            confidence=conf,
            reasoning=(
                f"Moderate curvature ({curv:.4f} 1/m), heading change "
                f"({heading:.0f} deg), arc {arc:.0f}m"
            ),
        )

    # --- Kink: low curvature, small heading change ---
    if (
        curv < SWEEPER_MIN_CURVATURE
        and heading <= KINK_MAX_HEADING_DEG
        and speed_loss < KINK_MAX_SPEED_LOSS_PCT
    ):
        conf = _clamp_confidence(
            0.45
            + 0.25 * (1.0 - min(curv / SWEEPER_MIN_CURVATURE, 1.0))
            + 0.2 * (1.0 - min(heading / KINK_MAX_HEADING_DEG, 1.0))
            + 0.1 * (1.0 - min(speed_loss / KINK_MAX_SPEED_LOSS_PCT, 1.0))
        )
        return CornerClassification(
            corner_type="kink",
            confidence=conf,
            reasoning=(
                f"Low curvature ({curv:.4f} 1/m), small heading change ({heading:.0f} deg), "
                f"and low speed loss ({speed_loss:.1f}%)"
            ),
        )

    # --- Complex: doesn't fit neatly into the above categories ---
    return CornerClassification(
        corner_type="complex",
        confidence=0.4,
        reasoning=(
            "Mixed geometry: "
            f"curvature {curv:.4f} 1/m, heading {heading:.0f} deg, arc {arc:.0f}m, "
            f"speed loss {speed_loss:.1f}%, CVI {curvature_variation:.2f}"
        ),
    )


def classify_sequence(
    corners: list[dict[str, Any]],
) -> list[CornerClassification]:
    """Classify a sequence of corners, detecting chicanes and esses.

    Each dict must have keys:
        peak_curvature (float), heading_change_deg (float), arc_length_m (float),
        direction (str: "left"|"right"), apex_distance_m (float),
        entry_distance_m (float), exit_distance_m (float).

    Returns one CornerClassification per input corner. Corners that form part
    of a chicane or esses pattern get their classification overridden.
    """
    if not corners:
        return []

    n = len(corners)

    # Step 1: classify each corner individually
    results: list[CornerClassification] = []
    for c in corners:
        results.append(
            classify_corner(
                peak_curvature=float(c.get("peak_curvature", 0.0) or 0.0),
                heading_change_deg=float(c.get("heading_change_deg", 0.0) or 0.0),
                arc_length_m=float(c.get("arc_length_m", 0.0) or 0.0),
            )
        )

    if n < 2:
        return results

    # Step 2: detect alternating-direction sequences
    # Build a list of gaps and direction alternation flags
    alternates: list[bool] = []
    close_enough: list[bool] = []
    for i in range(n - 1):
        dir_a = corners[i].get("direction")
        dir_b = corners[i + 1].get("direction")
        alternates.append(dir_a is not None and dir_b is not None and dir_a != dir_b)
        gap = _gap_between(corners[i], corners[i + 1])
        close_enough.append(gap <= SEQUENCE_MAX_GAP_M)

    # Step 3: find maximal alternating+close runs
    # A run starts where alternates[i] and close_enough[i] are both True
    used: list[bool] = [False] * n

    # Find esses first (3+ corners), then chicanes (exactly 2)
    i = 0
    while i < n - 1:
        if alternates[i] and close_enough[i] and not used[i]:
            # Start of a potential sequence
            run_start = i
            j = i
            while j < n - 1 and alternates[j] and close_enough[j] and not used[j + 1]:
                j += 1
            run_end = j  # inclusive corner index
            run_len = run_end - run_start + 1

            if run_len >= ESSES_MIN_COUNT:
                # Mark as esses
                for k in range(run_start, run_end + 1):
                    used[k] = True
                    results[k] = CornerClassification(
                        corner_type="esses",
                        confidence=_clamp_confidence(0.5 + 0.1 * min(run_len - 2, 5)),
                        reasoning=(
                            f"Part of {run_len}-corner alternating sequence "
                            f"(corners {run_start + 1}-{run_end + 1})"
                        ),
                    )
            elif run_len == 2:
                # Mark as chicane
                for k in range(run_start, run_end + 1):
                    used[k] = True
                    results[k] = CornerClassification(
                        corner_type="chicane",
                        confidence=_clamp_confidence(
                            0.6
                            + 0.2
                            * (
                                1.0
                                - _gap_between(corners[run_start], corners[run_end])
                                / SEQUENCE_MAX_GAP_M
                            )
                        ),
                        reasoning=(
                            f"Two opposite-direction corners "
                            f"(corners {run_start + 1}-{run_end + 1}) "
                            f"with {_gap_between(corners[run_start], corners[run_end]):.0f}m gap"
                        ),
                    )
            i = run_end + 1
        else:
            i += 1

    return results


def _gap_between(
    corner_a: dict[str, Any],
    corner_b: dict[str, Any],
) -> float:
    """Compute gap between exit of corner_a and entry of corner_b."""
    exit_a = float(corner_a.get("exit_distance_m", 0.0) or 0.0)
    entry_b = float(corner_b.get("entry_distance_m", 0.0) or 0.0)
    return abs(entry_b - exit_a)

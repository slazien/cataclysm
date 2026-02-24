"""Track segmentation into straights and corners via changepoint detection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import ruptures
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from cataclysm.curvature import CurvatureResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_CORNER_CURVATURE = 0.003  # 1/m — below this is "straight"
MIN_SEGMENT_LENGTH_M = 15.0
MERGE_GAP_M = 30.0

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TrackSegment:
    """A single segment of track (straight, corner, or transition)."""

    segment_type: str  # "straight" | "corner" | "transition"
    entry_distance_m: float
    exit_distance_m: float
    peak_curvature: float  # max |kappa| in segment
    mean_curvature: float  # mean |kappa| in segment
    direction: str  # "left" | "right" | "straight"
    scale: float  # characteristic scale from CSS (0.0 for others)
    parent_complex: int | None  # hierarchical grouping ID


@dataclass
class SegmentationResult:
    """Output of any segmentation method."""

    segments: list[TrackSegment]
    method: str  # "pelt" | "css" | "asc"
    changepoints_m: list[float]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_step_m(distance_m: np.ndarray) -> float:
    """Infer the distance step from the distance array."""
    if len(distance_m) > 1:
        return float(distance_m[1] - distance_m[0])
    return 0.7


def _classify_segments(
    changepoints_m: list[float],
    curvature_result: CurvatureResult,
    method: str,
) -> SegmentationResult:
    """Build a SegmentationResult from changepoint distances and curvature data.

    Between each pair of consecutive changepoints, compute mean |kappa| and peak
    |kappa| to decide straight vs corner, then merge, filter, and assign
    hierarchical complex IDs.
    """
    distance = curvature_result.distance_m
    abs_curv = curvature_result.abs_curvature
    signed_curv = curvature_result.curvature

    if len(distance) == 0:
        return SegmentationResult(segments=[], method=method, changepoints_m=[])

    d_min = float(distance[0])
    d_max = float(distance[-1])

    # Ensure changepoints span the full track and are sorted/unique
    all_boundaries = sorted({d_min, d_max, *changepoints_m})
    # Clamp boundaries to [d_min, d_max]
    all_boundaries = [b for b in all_boundaries if d_min <= b <= d_max]

    if len(all_boundaries) < 2:
        all_boundaries = [d_min, d_max]

    # Build raw segments between consecutive boundaries
    raw_segments: list[TrackSegment] = []
    for i in range(len(all_boundaries) - 1):
        entry_d = all_boundaries[i]
        exit_d = all_boundaries[i + 1]

        mask = (distance >= entry_d) & (distance <= exit_d)
        if not mask.any():
            continue

        seg_abs = abs_curv[mask]
        seg_signed = signed_curv[mask]

        mean_abs = float(np.mean(seg_abs))
        peak_abs = float(np.max(seg_abs))
        mean_signed = float(np.mean(seg_signed))

        if mean_abs > MIN_CORNER_CURVATURE:
            seg_type = "corner"
            direction = "left" if mean_signed > 0 else "right"
        else:
            seg_type = "straight"
            direction = "straight"

        raw_segments.append(
            TrackSegment(
                segment_type=seg_type,
                entry_distance_m=entry_d,
                exit_distance_m=exit_d,
                peak_curvature=peak_abs,
                mean_curvature=mean_abs,
                direction=direction,
                scale=0.0,
                parent_complex=None,
            )
        )

    # Merge adjacent segments of the same type within MERGE_GAP_M
    merged = _merge_adjacent_segments(raw_segments)

    # Filter out segments shorter than MIN_SEGMENT_LENGTH_M
    filtered = [
        s for s in merged if (s.exit_distance_m - s.entry_distance_m) >= MIN_SEGMENT_LENGTH_M
    ]

    # Assign parent_complex IDs to consecutive corner groups with same direction
    _assign_complex_ids(filtered)

    entry_cps = {s.entry_distance_m for s in filtered}
    exit_cps = {s.exit_distance_m for s in filtered}
    final_cps = sorted(entry_cps | exit_cps)
    # Remove the track start/end from reported changepoints
    final_cps = [cp for cp in final_cps if cp != d_min and cp != d_max]

    return SegmentationResult(
        segments=filtered,
        method=method,
        changepoints_m=final_cps,
    )


def _merge_adjacent_segments(segments: list[TrackSegment]) -> list[TrackSegment]:
    """Merge consecutive segments of the same type that are within MERGE_GAP_M."""
    if len(segments) <= 1:
        return list(segments)

    merged: list[TrackSegment] = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        gap = seg.entry_distance_m - prev.exit_distance_m
        same_type = prev.segment_type == seg.segment_type
        if same_type and gap <= MERGE_GAP_M:
            # Merge: extend previous segment to cover both
            merged[-1] = TrackSegment(
                segment_type=prev.segment_type,
                entry_distance_m=prev.entry_distance_m,
                exit_distance_m=seg.exit_distance_m,
                peak_curvature=max(prev.peak_curvature, seg.peak_curvature),
                mean_curvature=(prev.mean_curvature + seg.mean_curvature) / 2.0,
                direction=prev.direction if prev.direction == seg.direction else prev.direction,
                scale=max(prev.scale, seg.scale),
                parent_complex=None,
            )
        else:
            merged.append(seg)
    return merged


def _assign_complex_ids(segments: list[TrackSegment]) -> None:
    """Group consecutive corner segments with the same direction into numbered complexes."""
    complex_id = 0
    i = 0
    while i < len(segments):
        seg = segments[i]
        if seg.segment_type == "corner":
            complex_id += 1
            seg.parent_complex = complex_id
            # Group consecutive corners with the same direction
            j = i + 1
            while j < len(segments):
                nxt = segments[j]
                if nxt.segment_type == "corner" and nxt.direction == seg.direction:
                    nxt.parent_complex = complex_id
                    j += 1
                else:
                    break
            i = j
        else:
            i += 1


# ---------------------------------------------------------------------------
# Method A — PELT changepoint detection
# ---------------------------------------------------------------------------


def segment_pelt(
    curvature_result: CurvatureResult,
    penalty: float | None = None,
) -> SegmentationResult:
    """Segment the track using PELT (Pruned Exact Linear Time) changepoint detection.

    Parameters
    ----------
    curvature_result:
        Curvature profile from :func:`cataclysm.curvature.compute_curvature`.
    penalty:
        Penalty value for PELT.  If *None*, uses a BIC-like default of
        ``2 * log(n)``.

    Returns
    -------
    SegmentationResult
        Segments with method="pelt".
    """
    distance = curvature_result.distance_m
    abs_curv = curvature_result.abs_curvature
    step_m = _infer_step_m(distance)

    signal = abs_curv.reshape(-1, 1)
    n = len(signal)

    pen = 2.0 * np.log(max(n, 2)) if penalty is None else penalty

    min_size = max(2, int(MIN_SEGMENT_LENGTH_M / step_m))

    algo = ruptures.Pelt(model="rbf", min_size=min_size).fit(signal)
    bkpts = algo.predict(pen=pen)

    # ruptures returns sample indices (1-based end points); convert to distances
    # The last breakpoint is always len(signal), which we ignore (it's track end)
    cp_distances = [float(distance[idx - 1]) for idx in bkpts if idx < n]

    return _classify_segments(cp_distances, curvature_result, method="pelt")


# ---------------------------------------------------------------------------
# Method B — Curvature Scale Space (CSS)
# ---------------------------------------------------------------------------


def segment_css(
    curvature_result: CurvatureResult,
    scales: list[float] | None = None,
) -> SegmentationResult:
    """Segment the track using Curvature Scale Space analysis.

    Gaussian-smooths the absolute curvature at multiple spatial scales, finds
    zero-crossings and peaks at each scale, then keeps changepoints that persist
    across at least 2 scales.

    Parameters
    ----------
    curvature_result:
        Curvature profile.
    scales:
        Gaussian sigma values in **metres**.  Defaults to [5, 10, 20, 50, 100].

    Returns
    -------
    SegmentationResult
        Segments with method="css".
    """
    distance = curvature_result.distance_m
    curvature = curvature_result.curvature
    abs_curv = curvature_result.abs_curvature
    step_m = _infer_step_m(distance)

    if scales is None:
        scales = [5.0, 10.0, 20.0, 50.0, 100.0]

    # Collect changepoint distances per scale, tracking which scale found them
    cp_counts: dict[int, int] = {}  # distance index -> count of scales

    for sigma_m in scales:
        sigma_pts = max(1.0, sigma_m / step_m)

        # Smooth the signed curvature and find zero-crossings
        smoothed_signed = gaussian_filter1d(curvature, sigma=sigma_pts)
        sign_arr = np.sign(smoothed_signed)
        # Zero-crossings: where sign changes
        sign_changes = np.where(np.diff(sign_arr) != 0)[0]
        for idx in sign_changes:
            cp_counts[int(idx)] = cp_counts.get(int(idx), 0) + 1

        # Smooth absolute curvature and find peaks
        smoothed_abs = gaussian_filter1d(abs_curv, sigma=sigma_pts)
        peak_indices, _ = find_peaks(smoothed_abs, height=MIN_CORNER_CURVATURE)
        for idx in peak_indices:
            cp_counts[int(idx)] = cp_counts.get(int(idx), 0) + 1

    # Keep changepoints that appear at >= 2 scales
    persistent_indices = sorted(idx for idx, count in cp_counts.items() if count >= 2)

    cp_distances = [float(distance[idx]) for idx in persistent_indices if idx < len(distance)]

    return _classify_segments(cp_distances, curvature_result, method="css")


# ---------------------------------------------------------------------------
# Method C — Adaptive Segmentation by Curvature peaks (ASC)
# ---------------------------------------------------------------------------


def segment_asc(
    curvature_result: CurvatureResult,
    min_peak_curvature: float = 0.005,
) -> SegmentationResult:
    """Segment the track by finding curvature peaks and expanding corner zones.

    1. Find peaks in |curvature| above *min_peak_curvature*.
    2. Expand each peak outward until |curvature| drops below MIN_CORNER_CURVATURE.
    3. Merge overlapping corner zones.
    4. Split zones at curvature sign changes (S-turns).
    5. Fill gaps as straights.

    Parameters
    ----------
    curvature_result:
        Curvature profile.
    min_peak_curvature:
        Minimum |curvature| to qualify as a corner peak.

    Returns
    -------
    SegmentationResult
        Segments with method="asc".
    """
    distance = curvature_result.distance_m
    abs_curv = curvature_result.abs_curvature
    signed_curv = curvature_result.curvature
    step_m = _infer_step_m(distance)
    n = len(distance)

    if n == 0:
        return SegmentationResult(segments=[], method="asc", changepoints_m=[])

    min_dist_pts = max(2, int(MIN_SEGMENT_LENGTH_M / step_m))

    # Step 1: Find peaks in abs_curvature
    peak_indices, _ = find_peaks(
        abs_curv,
        height=min_peak_curvature,
        distance=min_dist_pts,
    )

    if len(peak_indices) == 0:
        # No corners found — entire track is a straight
        return _classify_segments([], curvature_result, method="asc")

    # Step 2: Expand each peak outward until abs_curvature < MIN_CORNER_CURVATURE
    corner_zones: list[tuple[int, int]] = []
    for peak_idx in peak_indices:
        left = int(peak_idx)
        while left > 0 and abs_curv[left - 1] >= MIN_CORNER_CURVATURE:
            left -= 1
        right = int(peak_idx)
        while right < n - 1 and abs_curv[right + 1] >= MIN_CORNER_CURVATURE:
            right += 1
        corner_zones.append((left, right))

    # Step 3: Merge overlapping or adjacent zones
    corner_zones.sort()
    merged_zones: list[tuple[int, int]] = [corner_zones[0]]
    for left, right in corner_zones[1:]:
        prev_left, prev_right = merged_zones[-1]
        if left <= prev_right + 1:
            merged_zones[-1] = (prev_left, max(prev_right, right))
        else:
            merged_zones.append((left, right))

    # Step 4: Split zones at curvature sign changes (S-turns)
    split_zones: list[tuple[int, int]] = []
    for left, right in merged_zones:
        zone_signed = signed_curv[left : right + 1]
        zone_sign = np.sign(zone_signed)
        sign_changes = np.where(np.diff(zone_sign) != 0)[0]

        if len(sign_changes) == 0:
            split_zones.append((left, right))
        else:
            # Split at each sign change
            prev = left
            for sc in sign_changes:
                split_point = left + int(sc)
                if split_point > prev:
                    split_zones.append((prev, split_point))
                prev = split_point + 1
            if prev <= right:
                split_zones.append((prev, right))

    # Collect all changepoint distances from zone boundaries
    changepoints: set[float] = set()
    for left, right in split_zones:
        if left > 0:
            changepoints.add(float(distance[left]))
        if right < n - 1:
            changepoints.add(float(distance[right]))

    cp_list = sorted(changepoints)

    return _classify_segments(cp_list, curvature_result, method="asc")


# ---------------------------------------------------------------------------
# Convenience dispatcher
# ---------------------------------------------------------------------------

_METHODS: dict[str, Callable[..., SegmentationResult]] = {
    "pelt": segment_pelt,
    "css": segment_css,
    "asc": segment_asc,
}


def segment_track(
    curvature_result: CurvatureResult,
    method: str = "pelt",
) -> SegmentationResult:
    """Segment a track using the specified method.

    Parameters
    ----------
    curvature_result:
        Curvature profile from :func:`cataclysm.curvature.compute_curvature`.
    method:
        One of ``"pelt"``, ``"css"``, or ``"asc"``.

    Returns
    -------
    SegmentationResult

    Raises
    ------
    ValueError
        If *method* is not recognised.
    """
    func = _METHODS.get(method)
    if func is None:
        valid = ", ".join(sorted(_METHODS))
        msg = f"Unknown segmentation method {method!r}. Valid methods: {valid}"
        raise ValueError(msg)
    return func(curvature_result)

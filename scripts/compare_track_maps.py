"""Compare generated track-map screenshots against a reference image.

This script supports either full-page screenshots (auto-crops the map card) or
pre-cropped map-card images.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class CropBounds:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class ComparisonMetrics:
    chamfer_ref_to_candidate: float
    chamfer_candidate_to_ref: float
    chamfer_mean: float
    iou: float
    reference_coverage: float
    candidate_coverage: float
    reference_point_count: int
    candidate_point_count: int
    quality_score: float
    quality_label: str


@dataclass(frozen=True)
class CandidateReport:
    candidate_path: str
    candidate_label: str
    reference_crop: CropBounds
    candidate_crop: CropBounds
    metrics: ComparisonMetrics
    overlay_path: str


def _parse_crop(value: str) -> CropBounds:
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("Crop must be x,y,w,h")
    try:
        x, y, w, h = (int(p) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Crop must contain integers") from exc
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("Crop width and height must be > 0")
    return CropBounds(x=x, y=y, w=w, h=h)


def _load_image(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def _crop_image(image: np.ndarray, bounds: CropBounds) -> np.ndarray:
    h, w = image.shape[:2]
    x0 = max(0, bounds.x)
    y0 = max(0, bounds.y)
    x1 = min(w, x0 + bounds.w)
    y1 = min(h, y0 + bounds.h)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Invalid crop bounds after clipping")
    return image[y0:y1, x0:x1]


def _longest_run(mask: np.ndarray) -> tuple[int, int, int]:
    best_len = 0
    best_start = 0
    best_end = -1
    n = mask.size
    i = 0
    while i < n:
        if not mask[i]:
            i += 1
            continue
        start = i
        while i < n and mask[i]:
            i += 1
        end = i - 1
        run_len = end - start + 1
        if run_len > best_len:
            best_len = run_len
            best_start = start
            best_end = end
    return best_len, best_start, best_end


def _auto_detect_map_card(image: np.ndarray) -> CropBounds | None:
    """Detect map-card bounds in a full screenshot.

    Heuristic tuned for Cataclysm screenshots: find a long horizontal top border,
    then locate a matching long horizontal bottom border.
    """

    height, width = image.shape[:2]

    # If it's likely already a map-card crop, avoid further cropping.
    if width <= 1400 and height <= 900:
        return CropBounds(0, 0, width, height)

    gray = np.dot(image[..., :3].astype(np.float32), np.array([0.299, 0.587, 0.114]))
    vgrad = np.abs(np.diff(gray, axis=0))

    threshold = np.percentile(vgrad, 98.8)
    edges = vgrad > threshold

    min_run = int(width * 0.25)
    max_run = int(width * 0.82)
    start_y = int(height * 0.15)
    end_y = int(height * 0.95)

    top_candidates: list[tuple[int, int, int, int]] = []
    for y in range(start_y, end_y):
        run_len, x0, x1 = _longest_run(edges[y])
        if run_len < min_run or run_len > max_run:
            continue
        if x0 < int(width * 0.08):
            continue
        if x1 > int(width * 0.98):
            continue
        top_candidates.append((y, x0, x1, run_len))

    if not top_candidates:
        return None

    best_score = -1.0
    best_pair: tuple[int, int, int, int] | None = None

    for top_y, x0, x1, run_len in top_candidates:
        min_h = int(height * 0.20)
        max_h = int(height * 0.85)
        for bottom_y in range(top_y + min_h, min(height - 1, top_y + max_h)):
            run2_len, x20, x21 = _longest_run(edges[bottom_y])
            if abs(run2_len - run_len) > 40:
                continue
            if abs(x20 - x0) > 30 or abs(x21 - x1) > 30:
                continue
            card_h = bottom_y - top_y
            if card_h < 250:
                continue
            score = float(run_len * card_h)
            if score > best_score:
                best_score = score
                best_pair = (top_y, bottom_y, x0, x1)

    if best_pair is None:
        return None

    top_y, bottom_y, x0, x1 = best_pair

    # Inset by 1 px to avoid border noise in color extraction.
    x = x0 + 1
    y = top_y + 1
    w = max(1, (x1 - x0 + 1) - 2)
    h = max(1, (bottom_y - top_y + 1) - 2)
    return CropBounds(x=x, y=y, w=w, h=h)


def _rgb_to_hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arr = rgb.astype(np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    mx = np.max(arr, axis=-1)
    mn = np.min(arr, axis=-1)
    diff = mx - mn

    h = np.zeros_like(mx)
    s = np.where(mx == 0, 0.0, diff / mx)
    v = mx

    nz = diff != 0

    idx = (mx == r) & nz
    h[idx] = ((g[idx] - b[idx]) / diff[idx]) % 6

    idx = (mx == g) & nz
    h[idx] = ((b[idx] - r[idx]) / diff[idx]) + 2

    idx = (mx == b) & nz
    h[idx] = ((r[idx] - g[idx]) / diff[idx]) + 4

    h /= 6.0
    return h, s, v


def _extract_track_mask_colored(image: np.ndarray, min_component_area: int) -> np.ndarray:
    h, s, v = _rgb_to_hsv(image)

    # Capture yellow/orange/red + green segments used for track quality coloring.
    warm_or_green = ((h < 0.20) | ((h > 0.23) & (h < 0.42))) & (s > 0.30) & (v > 0.35)

    mask = ndimage.binary_opening(warm_or_green, structure=np.ones((2, 2), dtype=bool))
    mask = ndimage.binary_dilation(mask, structure=np.ones((3, 3), dtype=bool), iterations=1)

    labeled, count = ndimage.label(mask)
    filtered = np.zeros_like(mask)

    for idx in range(1, count + 1):
        comp = labeled == idx
        if int(comp.sum()) >= min_component_area:
            filtered |= comp

    return filtered


def _extract_track_mask_geometry(image: np.ndarray, min_component_area: int) -> np.ndarray:
    """Extract full track geometry (gray base line + colored segments).

    Strategy:
    - Threshold luminance to get visible track strokes on dark background.
    - Keep only large connected components.
    - Prefer the largest non-border component as the track shape.
    """

    arr = image.astype(np.float32)
    lum = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]

    # Dark UI background is ~10-25; track strokes and borders are brighter.
    mask = lum > 38.0
    mask = ndimage.binary_opening(mask, structure=np.ones((2, 2), dtype=bool))

    labeled, count = ndimage.label(mask)
    if count == 0:
        return np.zeros_like(mask)

    height, width = mask.shape
    best_component: np.ndarray | None = None
    best_area = 0

    for idx in range(1, count + 1):
        comp = labeled == idx
        area = int(comp.sum())
        if area < min_component_area:
            continue

        ys, xs = np.where(comp)
        if xs.size == 0:
            continue

        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        w = x1 - x0 + 1
        h = y1 - y0 + 1

        # Ignore tiny components and likely card borders.
        if w < 100 or h < 80:
            continue
        touches_left = x0 <= 1
        touches_right = x1 >= width - 2
        touches_top = y0 <= 1
        touches_bottom = y1 >= height - 2
        if (touches_left or touches_right) and h > int(height * 0.7):
            continue
        if (touches_top or touches_bottom) and w > int(width * 0.7):
            continue

        if area > best_area:
            best_area = area
            best_component = comp

    if best_component is None:
        return np.zeros_like(mask)
    return best_component


def _extract_track_mask(image: np.ndarray, min_component_area: int, mode: str) -> np.ndarray:
    if mode == "colored-segments":
        return _extract_track_mask_colored(image, min_component_area=min_component_area)
    return _extract_track_mask_geometry(image, min_component_area=min_component_area)


def _normalize_points(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.where(mask)
    if xs.size == 0:
        return np.empty((0, 2), dtype=np.float32)

    pts = np.column_stack((xs, ys)).astype(np.float32)
    mn = pts.min(axis=0)
    mx = pts.max(axis=0)
    rng = np.maximum(mx - mn, 1e-6)
    return (pts - mn) / rng


def _sample_points(points: np.ndarray, max_points: int, seed: int) -> np.ndarray:
    if points.shape[0] <= max_points:
        return points
    rng = np.random.default_rng(seed)
    idx = rng.choice(points.shape[0], size=max_points, replace=False)
    return points[idx]


def _chamfer(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    tree_a = cKDTree(a)
    tree_b = cKDTree(b)

    a_to_b = tree_b.query(a, k=1)[0]
    b_to_a = tree_a.query(b, k=1)[0]

    mean_a = float(a_to_b.mean())
    mean_b = float(b_to_a.mean())
    return mean_a, mean_b, float((mean_a + mean_b) / 2.0)


def _rasterize(points: np.ndarray, size: int, stroke: int) -> np.ndarray:
    canvas = np.zeros((size, size), dtype=bool)
    if points.size == 0:
        return canvas

    px = np.clip(np.rint(points[:, 0] * (size - 1)).astype(int), 0, size - 1)
    py = np.clip(np.rint(points[:, 1] * (size - 1)).astype(int), 0, size - 1)
    canvas[py, px] = True

    if stroke > 1:
        kernel = np.ones((stroke, stroke), dtype=bool)
        canvas = ndimage.binary_dilation(canvas, structure=kernel)

    return canvas


def _iou(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    inter = a & b
    union = a | b

    inter_count = int(inter.sum())
    union_count = int(union.sum())
    a_count = int(a.sum())
    b_count = int(b.sum())

    iou = 0.0 if union_count == 0 else inter_count / union_count
    a_cov = 0.0 if a_count == 0 else inter_count / a_count
    b_cov = 0.0 if b_count == 0 else inter_count / b_count
    return iou, a_cov, b_cov


def _quality_label(chamfer_mean: float, iou: float) -> tuple[float, str]:
    # Score in [0, 100], weighting shape distance more heavily than overlap.
    distance_term = max(0.0, 1.0 - (chamfer_mean / 0.12))
    score = 100.0 * (0.65 * distance_term + 0.35 * iou)

    if score >= 85:
        label = "excellent"
    elif score >= 70:
        label = "good"
    elif score >= 55:
        label = "moderate"
    else:
        label = "poor"

    return score, label


def _write_overlay(
    ref_raster: np.ndarray,
    cand_raster: np.ndarray,
    output_path: Path,
) -> None:
    h, w = ref_raster.shape
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # Ref-only cyan, candidate-only orange, overlap green.
    ref_only = ref_raster & ~cand_raster
    cand_only = cand_raster & ~ref_raster
    both = ref_raster & cand_raster

    img[ref_only] = np.array([60, 170, 255], dtype=np.uint8)
    img[cand_only] = np.array([255, 170, 60], dtype=np.uint8)
    img[both] = np.array([110, 255, 130], dtype=np.uint8)

    Image.fromarray(img, mode="RGB").save(output_path)


def _compare_one(
    reference_crop: np.ndarray,
    candidate_crop: np.ndarray,
    max_points: int,
    min_component_area: int,
    render_size: int,
    overlay_stroke: int,
    mode: str,
) -> ComparisonMetrics:
    ref_mask = _extract_track_mask(
        reference_crop,
        min_component_area=min_component_area,
        mode=mode,
    )
    cand_mask = _extract_track_mask(
        candidate_crop,
        min_component_area=min_component_area,
        mode=mode,
    )

    ref_pts = _normalize_points(ref_mask)
    cand_pts = _normalize_points(cand_mask)

    if ref_pts.shape[0] == 0:
        raise ValueError("No track-like colored pixels found in reference image")
    if cand_pts.shape[0] == 0:
        raise ValueError("No track-like colored pixels found in candidate image")

    ref_pts_s = _sample_points(ref_pts, max_points=max_points, seed=0)
    cand_pts_s = _sample_points(cand_pts, max_points=max_points, seed=1)

    c_ref, c_cand, c_mean = _chamfer(ref_pts_s, cand_pts_s)

    ref_raster = _rasterize(ref_pts, size=render_size, stroke=overlay_stroke)
    cand_raster = _rasterize(cand_pts, size=render_size, stroke=overlay_stroke)

    iou, ref_cov, cand_cov = _iou(ref_raster, cand_raster)
    score, label = _quality_label(c_mean, iou)

    return ComparisonMetrics(
        chamfer_ref_to_candidate=c_ref,
        chamfer_candidate_to_ref=c_cand,
        chamfer_mean=c_mean,
        iou=iou,
        reference_coverage=ref_cov,
        candidate_coverage=cand_cov,
        reference_point_count=int(ref_pts.shape[0]),
        candidate_point_count=int(cand_pts.shape[0]),
        quality_score=score,
        quality_label=label,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True, help="Path to reference image")
    parser.add_argument(
        "--candidate",
        type=Path,
        action="append",
        required=True,
        help="Path to candidate image; can be repeated",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/track_map_compare"),
        help="Directory for overlays, crops, and JSON report",
    )
    parser.add_argument(
        "--reference-crop",
        type=_parse_crop,
        default=None,
        help="Optional manual crop for reference as x,y,w,h",
    )
    parser.add_argument(
        "--candidate-crop",
        type=_parse_crop,
        default=None,
        help="Optional manual crop for all candidates as x,y,w,h",
    )
    parser.add_argument(
        "--no-auto-crop",
        action="store_true",
        help="Disable auto-detection of map-card bounds for full screenshots",
    )
    parser.add_argument(
        "--min-component-area",
        type=int,
        default=120,
        help="Minimum connected-component area retained in extracted track mask",
    )
    parser.add_argument(
        "--mode",
        choices=["geometry", "colored-segments"],
        default="geometry",
        help="Comparison mode: full track geometry or only colored corner segments",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=8000,
        help="Max points sampled per image for Chamfer distance",
    )
    parser.add_argument(
        "--render-size",
        type=int,
        default=800,
        help="Raster size for overlap metrics/overlay rendering",
    )
    parser.add_argument(
        "--overlay-stroke",
        type=int,
        default=3,
        help="Dilation stroke width for overlap rasterization",
    )
    parser.add_argument(
        "--save-crops",
        action="store_true",
        help="Save cropped map-card images in output directory",
    )
    parser.add_argument(
        "--json-name",
        default="report.json",
        help="Output JSON filename",
    )

    args = parser.parse_args()

    if args.min_component_area <= 0:
        raise ValueError("--min-component-area must be > 0")
    if args.max_points <= 10:
        raise ValueError("--max-points must be > 10")
    if args.render_size < 100:
        raise ValueError("--render-size must be >= 100")
    if args.overlay_stroke < 1:
        raise ValueError("--overlay-stroke must be >= 1")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    reference_image = _load_image(args.reference)
    if args.reference_crop is not None:
        ref_bounds = args.reference_crop
    elif args.no_auto_crop:
        ref_bounds = CropBounds(0, 0, reference_image.shape[1], reference_image.shape[0])
    else:
        ref_bounds = _auto_detect_map_card(reference_image) or CropBounds(
            0, 0, reference_image.shape[1], reference_image.shape[0]
        )

    reference_crop = _crop_image(reference_image, ref_bounds)

    if args.save_crops:
        Image.fromarray(reference_crop).save(args.output_dir / "reference_crop.png")

    reports: list[CandidateReport] = []

    for candidate_path in args.candidate:
        candidate_image = _load_image(candidate_path)
        if args.candidate_crop is not None:
            cand_bounds = args.candidate_crop
        elif args.no_auto_crop:
            cand_bounds = CropBounds(0, 0, candidate_image.shape[1], candidate_image.shape[0])
        else:
            cand_bounds = _auto_detect_map_card(candidate_image) or CropBounds(
                0, 0, candidate_image.shape[1], candidate_image.shape[0]
            )

        candidate_crop = _crop_image(candidate_image, cand_bounds)
        candidate_label = candidate_path.stem

        metrics = _compare_one(
            reference_crop=reference_crop,
            candidate_crop=candidate_crop,
            max_points=args.max_points,
            min_component_area=args.min_component_area,
            render_size=args.render_size,
            overlay_stroke=args.overlay_stroke,
            mode=args.mode,
        )

        ref_mask = _extract_track_mask(
            reference_crop,
            min_component_area=args.min_component_area,
            mode=args.mode,
        )
        cand_mask = _extract_track_mask(
            candidate_crop,
            min_component_area=args.min_component_area,
            mode=args.mode,
        )
        ref_pts = _normalize_points(ref_mask)
        cand_pts = _normalize_points(cand_mask)

        ref_raster = _rasterize(ref_pts, size=args.render_size, stroke=args.overlay_stroke)
        cand_raster = _rasterize(cand_pts, size=args.render_size, stroke=args.overlay_stroke)

        overlay_path = args.output_dir / f"{candidate_label}_overlay.png"
        _write_overlay(ref_raster=ref_raster, cand_raster=cand_raster, output_path=overlay_path)

        if args.save_crops:
            Image.fromarray(candidate_crop).save(args.output_dir / f"{candidate_label}_crop.png")

        reports.append(
            CandidateReport(
                candidate_path=str(candidate_path),
                candidate_label=candidate_label,
                reference_crop=ref_bounds,
                candidate_crop=cand_bounds,
                metrics=metrics,
                overlay_path=str(overlay_path),
            )
        )

    json_path = args.output_dir / args.json_name
    payload = {
        "reference_path": str(args.reference),
        "reference_crop": asdict(ref_bounds),
        "mode": args.mode,
        "candidates": [
            {
                "candidate_path": r.candidate_path,
                "candidate_label": r.candidate_label,
                "candidate_crop": asdict(r.candidate_crop),
                "metrics": asdict(r.metrics),
                "overlay_path": r.overlay_path,
            }
            for r in reports
        ],
    }

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Saved report: {json_path}")
    for report in reports:
        m = report.metrics
        print(
            f"{report.candidate_label}: "
            f"chamfer={m.chamfer_mean:.4f}, iou={m.iou:.4f}, "
            f"score={m.quality_score:.1f}, label={m.quality_label}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Track Map Visual Comparison

This documents how to compare a generated track map against a known-good reference screenshot.

## What is compared

We compare **track geometry shape**, not exact pixels:

1. Auto-crop each image to the map card (or use manual crop).
2. Extract track geometry:
- default (`--mode geometry`): full line shape (gray base + colored overlays)
- optional (`--mode colored-segments`): only yellow/orange/red/green segments
3. Normalize both shapes into `[0,1] x [0,1]` (translation/scale invariant).
4. Compute:
- `chamfer_mean`: average nearest-neighbor shape distance (lower is better).
- `iou`: overlap between normalized rasterized shapes (higher is better).
- `quality_score` and `quality_label` derived from those metrics.
5. Save overlay image:
- cyan: reference-only
- orange: candidate-only
- green: overlap

This is robust to different screenshot sizes and map-card dimensions.
Use `geometry` when you care about map shape regardless of color.
Use `colored-segments` when you specifically want corner-color/segmentation parity.

## Reusable script

Script: [`scripts/compare_track_maps.py`](/mnt/d/OneDrive/Dokumenty/vscode/cataclysm/scripts/compare_track_maps.py)

### Basic usage

```bash
python3 scripts/compare_track_maps.py \
  --reference /mnt/d/Downloads/barber_ref.png \
  --candidate /tmp/amp_map_card_clean_barber_motorsports_p_20260222_b101ba9c.png \
  --output-dir /tmp/trackmap_compare_barber \
  --mode geometry \
  --save-crops
```

### Compare multiple candidates to one reference

```bash
python3 scripts/compare_track_maps.py \
  --reference /mnt/d/Downloads/roebling_ref.png \
  --candidate /tmp/amp_map_card_clean_roebling_road_20260111_3fe04ad5.png \
  --candidate /tmp/amp_map_card_clean_roebling_nometa_20260111_306e54a8.png \
  --output-dir /tmp/trackmap_compare_roebling \
  --mode geometry \
  --save-crops
```

### If auto-crop fails (manual crop)

```bash
python3 scripts/compare_track_maps.py \
  --reference /mnt/d/Downloads/barber_ref.png \
  --reference-crop 548,342,1464,1056 \
  --candidate /tmp/full_screenshot.png \
  --candidate-crop 790,835,976,739 \
  --output-dir /tmp/trackmap_compare_manual
```

## Reading results

Output JSON: `/tmp/.../report.json`

Useful thresholds in practice:
- `chamfer_mean <= 0.03` and `iou >= 0.55`: very close
- `chamfer_mean 0.03-0.06`: moderate mismatch
- `chamfer_mean >= 0.06`: significant shape mismatch

Use the overlay PNG as the primary visual confirmation.

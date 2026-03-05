# Deep Dive Track Map Redesign

## Date: 2026-03-04

## Summary

Redesign the deep dive track map from a 3-way mode toggle (2D | SAT | 3D) to a 2D/3D view toggle with an independent SAT overlay toggle. This creates 4 view combinations and adds 3D satellite terrain support using Mapbox GL's native terrain API.

## UX Structure

### Controls Layout

```
[2D] [3D]   [SAT]   [Exaggeration slider*]   [Fullscreen]
```

*Exaggeration slider only visible when 3D + SAT is active.

### View Matrix

| | SAT OFF | SAT ON |
|---|---|---|
| **2D** | SVG track map (`TrackMapInteractive`) | Mapbox GL flat satellite (pitch=0) |
| **3D** | Three.js/R3F (`TrackMap3D`) | Mapbox GL 3D terrain (pitch=45, auto-bearing) |

## Implementation Details

### 3D + SAT (New)

- **Renderer**: Mapbox GL via `react-map-gl` (already a dependency)
- **DEM source**: `mapbox://mapbox.mapbox-terrain-dem-v1` (512px tiles, maxzoom 14)
- **Terrain**: `map.setTerrain({ source: 'mapbox-dem', exaggeration: 2.0 })`
- **Exaggeration slider**: Range 1.0-4.0, step 0.5, default 2.0
- **Initial camera**: `pitch: 45`, bearing auto-oriented to S/F straight direction
- **Track line**: Existing GeoJSON colored segments (speed/delta) - drapes over terrain automatically
- **Markers**: Reuse corner labels, S/F marker, cursor dot from `TrackMapSatellite`

### 2D + SAT (Modified)

- Change initial pitch from 45 to 0 (truly flat top-down)
- Otherwise identical to current `TrackMapSatellite`

### Auto-bearing Computation

Compute initial bearing from first ~20 GPS points (S/F straight direction):
```
dx = lon[20] - lon[0]
dy = lat[20] - lat[0]
bearing = atan2(dx, dy) * 180 / PI
```
Fallback: bearing=0 if insufficient data.

## Component Changes

### `TrackMapContainer.tsx`

- Replace `MapMode = '2d' | 'sat' | '3d'` with:
  - `viewMode: '2d' | '3d'`
  - `satEnabled: boolean`
- Update controls: 2D/3D toggle group + SAT toggle button
- Show exaggeration slider when `viewMode === '3d' && satEnabled`
- Render logic selects from 4 combinations

### `TrackMapSatellite.tsx`

- Accept new `terrain` prop (boolean, default false)
- Accept `exaggeration` prop (number, default 2.0)
- When `terrain=true`: add DEM source, enable terrain, use `pitch: 45` + auto-bearing
- When `terrain=false`: use `pitch: 0`, bearing=0 (flat top-down)

### No New Components

`TrackMapSatellite` handles both 2D and 3D satellite modes via props. `TrackMapInteractive` and `TrackMap3D` remain unchanged.

## Technical Notes

- Mapbox GL v3 terrain is GPU-accelerated and mobile-optimized
- GeoJSON lines automatically drape over terrain surface
- `map.queryTerrainElevation(lnglat)` available for future features
- Corner markers (Mapbox `<Marker>`) are positioned in screen space above terrain

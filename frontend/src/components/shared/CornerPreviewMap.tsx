'use client';

import { useMemo, useState, useCallback, useRef } from 'react';
import MapGL, { Source, Layer, Marker, type MapRef } from 'react-map-gl/mapbox';
import * as d3 from 'd3';
import type { LngLatBoundsLike } from 'mapbox-gl';
import { useSessionStore } from '@/stores';
import { useCorners, useMultiLapData } from '@/hooks/useAnalysis';
import { useAnalysisStore } from '@/stores';
import { colors } from '@/lib/design-tokens';
import type { LapData } from '@/lib/types';

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? '';

/** Padding in degrees around corner bounds (~30m). */
const BOUNDS_PAD = 0.0003;
/** Extra track distance (meters) before entry and after exit to show context. */
const CONTEXT_M = 80;

interface CornerPreviewMapProps {
  cornerNum: number;
  width?: number;
  height?: number;
}

/** Interpolate [lon, lat] at a given distance along the lap. */
function interpolatePosition(
  targetDist: number,
  lapData: LapData,
): [number, number] | null {
  const { distance_m, lat, lon } = lapData;
  if (distance_m.length === 0) return null;
  const idx = d3.bisectLeft(distance_m, targetDist);
  if (idx <= 0) return [lon[0], lat[0]];
  if (idx >= distance_m.length) return [lon[lon.length - 1], lat[lat.length - 1]];
  const d0 = distance_m[idx - 1];
  const d1 = distance_m[idx];
  const t = d1 !== d0 ? (targetDist - d0) / (d1 - d0) : 0;
  return [
    lon[idx - 1] + t * (lon[idx] - lon[idx - 1]),
    lat[idx - 1] + t * (lat[idx] - lat[idx - 1]),
  ];
}

export function CornerPreviewMap({ cornerNum, width = 320, height = 220 }: CornerPreviewMapProps) {
  const sessionId = useSessionStore((s) => s.activeSessionId);
  const { data: corners } = useCorners(sessionId);
  const mapRef = useRef<MapRef>(null);

  // Use first selected lap, or fall back to lap 1
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const lapNum = selectedLaps[0] ?? 1;
  const lapNums = useMemo(() => [lapNum], [lapNum]);
  const { data: multiLap } = useMultiLapData(sessionId, lapNums);

  // Fade in only after map has finished rendering tiles + layers
  const [ready, setReady] = useState(false);
  const onIdle = useCallback(() => setReady(true), []);

  const corner = useMemo(
    () => corners?.find((c) => c.number === cornerNum) ?? null,
    [corners, cornerNum],
  );

  const lapData = multiLap?.[0] ?? null;

  // Compute bounds and speed-colored GeoJSON segments for the corner region
  const { bounds, geojson, apexPos } = useMemo(() => {
    if (!corner || !lapData) return { bounds: null, geojson: null, apexPos: null };

    const { distance_m, speed_mph, lat, lon } = lapData;

    // Range: entry - context to exit + context
    const startDist = Math.max(0, corner.entry_distance_m - CONTEXT_M);
    const endDist = corner.exit_distance_m + CONTEXT_M;

    // Find indices within range
    let startIdx = 0;
    let endIdx = distance_m.length - 1;
    for (let i = 0; i < distance_m.length; i++) {
      if (distance_m[i] >= startDist) { startIdx = i; break; }
    }
    for (let i = distance_m.length - 1; i >= 0; i--) {
      if (distance_m[i] <= endDist) { endIdx = i; break; }
    }
    if (endIdx <= startIdx + 1) return { bounds: null, geojson: null, apexPos: null };

    // Speed range within this corner region
    const regionSpeeds = speed_mph.slice(startIdx, endIdx + 1);
    const minSpd = d3.min(regionSpeeds) ?? 0;
    const maxSpd = d3.max(regionSpeeds) ?? 1;
    const speedScale = d3
      .scaleLinear<string>()
      .domain([minSpd, (minSpd + maxSpd) / 2, maxSpd])
      .range([colors.motorsport.brake, colors.motorsport.neutral, colors.motorsport.throttle]);

    // Build colored line segments (one per GPS pair for smooth coloring)
    const features: GeoJSON.Feature[] = [];
    const allLons: number[] = [];
    const allLats: number[] = [];

    for (let i = startIdx; i < endIdx; i++) {
      const lon1 = lon[i], lat1 = lat[i];
      const lon2 = lon[i + 1], lat2 = lat[i + 1];
      if (lon1 == null || lat1 == null || lon2 == null || lat2 == null) continue;

      allLons.push(lon1, lon2);
      allLats.push(lat1, lat2);

      features.push({
        type: 'Feature',
        properties: { color: speedScale(speed_mph[i]) as string },
        geometry: { type: 'LineString', coordinates: [[lon1, lat1], [lon2, lat2]] },
      });
    }

    if (allLons.length === 0) return { bounds: null, geojson: null, apexPos: null };

    // Also include brake point in bounds if available
    if (corner.brake_point_m != null) {
      const brakePos = interpolatePosition(corner.brake_point_m, lapData);
      if (brakePos) { allLons.push(brakePos[0]); allLats.push(brakePos[1]); }
    }

    const minLon = Math.min(...allLons) - BOUNDS_PAD;
    const maxLon = Math.max(...allLons) + BOUNDS_PAD;
    const minLat = Math.min(...allLats) - BOUNDS_PAD;
    const maxLat = Math.max(...allLats) + BOUNDS_PAD;

    const computedBounds: LngLatBoundsLike = [[minLon, minLat], [maxLon, maxLat]];
    const apex = interpolatePosition(corner.apex_distance_m, lapData);
    const fc: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features };
    return { bounds: computedBounds, geojson: fc, apexPos: apex };
  }, [corner, lapData]);

  if (!MAPBOX_TOKEN || !bounds || !geojson) {
    return (
      <div
        className="flex items-center justify-center rounded-t-lg bg-[var(--bg-base)] text-xs text-[var(--text-secondary)]"
        style={{ width, height }}
      >
        {!MAPBOX_TOKEN ? 'Map unavailable' : 'Loading...'}
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-t-lg" style={{ width, height }}>
      {/* Skeleton shown until map is fully rendered (tiles + layers) */}
      {!ready && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-[var(--bg-base)] text-xs text-[var(--text-secondary)]">
          Loading map...
        </div>
      )}

      <div
        className="h-full w-full"
        style={{ opacity: ready ? 1 : 0, transition: 'opacity 200ms ease-in' }}
      >
        <MapGL
          ref={mapRef}
          mapboxAccessToken={MAPBOX_TOKEN}
          initialViewState={{ bounds, fitBoundsOptions: { padding: 30 } }}
          style={{ width: '100%', height: '100%' }}
          mapStyle="mapbox://styles/mapbox/satellite-v9"
          interactive={false}
          attributionControl={false}
          logoPosition="bottom-right"
          onIdle={onIdle}
        >
          {/* No mapLoaded gate — react-map-gl v8 queues source/layer ops until ready */}
          <Source id="corner-preview-line" type="geojson" data={geojson}>
            <Layer
              id="corner-preview-line-layer"
              type="line"
              paint={{
                'line-color': ['get', 'color'],
                'line-width': 3.5,
                'line-opacity': 0.9,
              }}
            />
          </Source>

          {apexPos && (
            <Marker longitude={apexPos[0]} latitude={apexPos[1]} anchor="center">
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--cata-accent)] text-[10px] font-bold text-black shadow">
                {cornerNum}
              </div>
            </Marker>
          )}
        </MapGL>
      </div>
    </div>
  );
}

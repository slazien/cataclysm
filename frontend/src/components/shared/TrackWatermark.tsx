'use client';

import { useMemo } from 'react';
import { useSessionStore } from '@/stores';
import { useSessionLaps, useLapData } from '@/hooks/useSession';

const WM_SIZE = 280;
const WM_PADDING = 16;

/**
 * Projects GPS lat/lon arrays into SVG coordinate space.
 * Simplified version of the projection in TrackMapInteractive.
 */
function projectToSvg(
  lat: number[],
  lon: number[],
  size: number,
  padding: number,
): { x: number[]; y: number[] } {
  if (lat.length === 0) return { x: [], y: [] };

  let minLat = lat[0], maxLat = lat[0];
  let minLon = lon[0], maxLon = lon[0];
  for (let i = 1; i < lat.length; i++) {
    if (lat[i] < minLat) minLat = lat[i];
    if (lat[i] > maxLat) maxLat = lat[i];
    if (lon[i] < minLon) minLon = lon[i];
    if (lon[i] > maxLon) maxLon = lon[i];
  }

  const latRange = maxLat - minLat || 1e-6;
  const lonRange = maxLon - minLon || 1e-6;
  const midLat = (minLat + maxLat) / 2;
  const lonScale = Math.cos((midLat * Math.PI) / 180);

  const dataW = lonRange * lonScale;
  const dataH = latRange;
  const avail = size - 2 * padding;
  const scale = Math.min(avail / dataW, avail / dataH);

  const scaledW = dataW * scale;
  const scaledH = dataH * scale;
  const offsetX = padding + (avail - scaledW) / 2;
  const offsetY = padding + (avail - scaledH) / 2;

  const x = lon.map((lo) => offsetX + (lo - minLon) * lonScale * scale);
  const y = lat.map((la) => offsetY + scaledH - (la - minLat) * scale);

  return { x, y };
}

/**
 * Renders a faint track silhouette as a background watermark.
 * Uses the best lap's GPS data projected into a simplified SVG outline.
 * Positioned absolutely in the top-right corner of its parent container.
 */
export function TrackWatermark() {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: laps } = useSessionLaps(activeSessionId);

  const bestLapNumber = useMemo(() => {
    if (!laps || laps.length === 0) return null;
    let best = laps[0];
    for (const lap of laps) {
      if (lap.lap_time_s < best.lap_time_s) best = lap;
    }
    return best.lap_number;
  }, [laps]);

  const { data: lapData } = useLapData(activeSessionId, bestLapNumber);

  const pathD = useMemo(() => {
    if (!lapData || lapData.lat.length < 2) return null;

    const { x, y } = projectToSvg(lapData.lat, lapData.lon, WM_SIZE, WM_PADDING);
    if (x.length < 2) return null;

    // Downsample to ~200 points for a smooth but lightweight path
    const step = Math.max(1, Math.floor(x.length / 200));
    const parts: string[] = [`M${x[0].toFixed(1)},${y[0].toFixed(1)}`];
    for (let i = step; i < x.length; i += step) {
      parts.push(`L${x[i].toFixed(1)},${y[i].toFixed(1)}`);
    }
    // Close back to start for a complete loop
    parts.push('Z');

    return parts.join('');
  }, [lapData]);

  if (!pathD) return null;

  return (
    <div
      className="pointer-events-none absolute right-0 top-0 z-0"
      style={{ width: WM_SIZE, height: WM_SIZE }}
      aria-hidden="true"
    >
      <svg
        viewBox={`0 0 ${WM_SIZE} ${WM_SIZE}`}
        width={WM_SIZE}
        height={WM_SIZE}
        className="h-full w-full"
      >
        <path
          d={pathD}
          fill="none"
          stroke="var(--cata-accent, #f59e0b)"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.07}
        />
      </svg>
    </div>
  );
}

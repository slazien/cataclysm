'use client';

import { useRef, useEffect, useCallback } from 'react';
import * as d3 from 'd3';
import type { LapData, IdealLapData, Corner } from '@/lib/types';
import { distanceToGpsIndex } from '@/hooks/useOptimalReplay';
import { useUnits } from '@/hooks/useUnits';

const PADDING = 30;

interface OptimalReplayMapProps {
  lapData: LapData;
  idealLap: IdealLapData;
  corners: Corner[];
  /** Index into lapData arrays for the actual lap position */
  actualIndex: number;
  /** Distance (metres) for the ideal lap position */
  idealDistance: number;
  /** Index into idealLap arrays (for speed lookup) */
  idealIndex: number;
}

/** Speed → color: green (fast) → yellow → red (slow/braking) */
function speedColor(speed: number, minSpeed: number, maxSpeed: number): string {
  const range = maxSpeed - minSpeed || 1;
  const t = Math.max(0, Math.min(1, (speed - minSpeed) / range));
  return `hsl(${(1 - t) * 120}, 90%, 50%)`;
}

/**
 * Canvas-based track map showing actual vs ideal lap as two animated
 * trails with racing dots. The actual lap is white, the ideal/ghost
 * is amber/gold.
 */
export function OptimalReplayMap({
  lapData,
  idealLap,
  corners,
  actualIndex,
  idealDistance,
  idealIndex,
}: OptimalReplayMapProps) {
  const { formatDistance } = useUnits();
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const projRef = useRef<{
    x: Float64Array;
    y: Float64Array;
    w: number;
    h: number;
  } | null>(null);
  const minSpeedRef = useRef(0);
  const maxSpeedRef = useRef(1);

  // Project GPS coords to canvas coords
  const project = useCallback(
    (width: number, height: number) => {
      const { lat, lon } = lapData;
      if (lat.length === 0) return null;

      const minLat = d3.min(lat) ?? 0;
      const maxLat = d3.max(lat) ?? 0;
      const minLon = d3.min(lon) ?? 0;
      const maxLon = d3.max(lon) ?? 0;

      const latRange = maxLat - minLat || 1e-6;
      const lonRange = maxLon - minLon || 1e-6;

      const midLat = (minLat + maxLat) / 2;
      const lonScale = Math.cos((midLat * Math.PI) / 180);

      const dataWidth = lonRange * lonScale;
      const dataHeight = latRange;

      const availW = width - 2 * PADDING;
      const availH = height - 2 * PADDING;
      const scale = Math.min(availW / dataWidth, availH / dataHeight);

      const scaledW = dataWidth * scale;
      const scaledH = dataHeight * scale;
      const offsetX = PADDING + (availW - scaledW) / 2;
      const offsetY = PADDING + (availH - scaledH) / 2;

      const xArr = new Float64Array(lon.length);
      const yArr = new Float64Array(lat.length);
      for (let i = 0; i < lon.length; i++) {
        xArr[i] = offsetX + (lon[i] - minLon) * lonScale * scale;
        yArr[i] = offsetY + scaledH - (lat[i] - minLat) * scale;
      }

      return { x: xArr, y: yArr, w: width, h: height };
    },
    [lapData],
  );

  // Set up canvas sizing via ResizeObserver
  useEffect(() => {
    const el = containerRef.current;
    const canvas = canvasRef.current;
    if (!el || !canvas) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      const ctx = canvas.getContext('2d');
      if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      projRef.current = project(width, height);
    });
    observer.observe(el);

    // Compute combined speed bounds
    const allSpeeds = [...lapData.speed_mph, ...idealLap.speed_mph];
    minSpeedRef.current = d3.min(allSpeeds) ?? 0;
    maxSpeedRef.current = d3.max(allSpeeds) ?? 1;

    return () => observer.disconnect();
  }, [lapData, idealLap, project]);

  // Draw on every frame
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const proj = projRef.current;
    if (!proj) return;

    const { x, y, w, h } = proj;
    const n = x.length;
    if (n < 2) return;

    const minSpd = minSpeedRef.current;
    const maxSpd = maxSpeedRef.current;
    const step = n > 4000 ? 2 : 1;

    ctx.clearRect(0, 0, w, h);

    // 1. Full track outline (muted)
    ctx.beginPath();
    ctx.moveTo(x[0], y[0]);
    for (let i = 1; i < n; i++) {
      ctx.lineTo(x[i], y[i]);
    }
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // 2. Ideal lap trail (amber/gold, slightly transparent)
    const idealGpsIdx = distanceToGpsIndex(idealDistance, lapData.distance_m);
    const idealEnd = Math.min(idealGpsIdx, n - 1);

    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.globalAlpha = 0.5;
    for (let i = 0; i < idealEnd; i += step) {
      const j = Math.min(i + step, idealEnd);
      // Map this GPS index back to ideal speed
      const idealSpd = getIdealSpeedAtGpsIndex(
        i,
        lapData.distance_m,
        idealLap.distance_m,
        idealLap.speed_mph,
      );
      ctx.beginPath();
      ctx.moveTo(x[i], y[i]);
      ctx.lineTo(x[j], y[j]);
      ctx.strokeStyle = speedColor(idealSpd, minSpd, maxSpd);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // 3. Actual lap trail (full opacity, thicker)
    const actualEnd = Math.min(actualIndex, n - 1);
    ctx.lineWidth = 3.5;
    for (let i = 0; i < actualEnd; i += step) {
      const j = Math.min(i + step, actualEnd);
      ctx.beginPath();
      ctx.moveTo(x[i], y[i]);
      ctx.lineTo(x[j], y[j]);
      ctx.strokeStyle = speedColor(lapData.speed_mph[j], minSpd, maxSpd);
      ctx.stroke();
    }

    // 4. Corner annotations — show when actual dot has passed
    for (const corner of corners) {
      if (!corner.apex_lat || !corner.apex_lon) continue;
      // Find closest GPS index to apex
      const apexIdx = findClosestGpsIndex(corner.apex_lat, corner.apex_lon, lapData);
      if (apexIdx > actualEnd + 50) continue; // Not yet reached

      const cx = x[apexIdx];
      const cy = y[apexIdx];

      // Small corner label
      ctx.font = '600 10px system-ui, sans-serif';
      ctx.fillStyle =
        apexIdx <= actualEnd ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.3)';
      ctx.textAlign = 'center';
      ctx.fillText(`T${corner.number}`, cx, cy - 10);

      // Tiny circle at apex
      ctx.beginPath();
      ctx.arc(cx, cy, 3, 0, Math.PI * 2);
      ctx.fillStyle =
        apexIdx <= actualEnd ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.2)';
      ctx.fill();
    }

    // 5. Ideal dot (amber/gold ghost)
    if (idealEnd >= 0 && idealEnd < n) {
      const ix = x[idealEnd];
      const iy = y[idealEnd];

      // Glow
      const grad = ctx.createRadialGradient(ix, iy, 0, ix, iy, 12);
      grad.addColorStop(0, 'rgba(251, 191, 36, 0.5)');
      grad.addColorStop(1, 'rgba(251, 191, 36, 0)');
      ctx.beginPath();
      ctx.arc(ix, iy, 12, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      // Dot
      ctx.beginPath();
      ctx.arc(ix, iy, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = '#fbbf24'; // amber-400
      ctx.strokeStyle = 'rgba(0,0,0,0.4)';
      ctx.lineWidth = 1.5;
      ctx.fill();
      ctx.stroke();
    }

    // 6. Actual dot (white with speed-colored border)
    if (actualEnd >= 0 && actualEnd < n) {
      const ax = x[actualEnd];
      const ay = y[actualEnd];

      // Glow
      const grad = ctx.createRadialGradient(ax, ay, 0, ax, ay, 14);
      grad.addColorStop(0, 'rgba(255, 255, 255, 0.6)');
      grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
      ctx.beginPath();
      ctx.arc(ax, ay, 14, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      // Dot
      ctx.beginPath();
      ctx.arc(ax, ay, 5, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = speedColor(lapData.speed_mph[actualEnd], minSpd, maxSpd);
      ctx.lineWidth = 2;
      ctx.fill();
      ctx.stroke();
    }

    // 7. Delta indicator (distance gap between dots)
    if (actualEnd > 0 && idealEnd > 0) {
      const gapM = lapData.distance_m[idealEnd] - lapData.distance_m[actualEnd];
      const gapText =
        gapM >= 0
          ? `Ideal +${formatDistance(gapM)} ahead`
          : `You +${formatDistance(Math.abs(gapM))} ahead`;
      const gapColor = gapM >= 0 ? '#fbbf24' : '#4ade80';

      ctx.font = '600 11px system-ui, sans-serif';
      ctx.fillStyle = gapColor;
      ctx.textAlign = 'right';
      ctx.fillText(gapText, w - 12, h - 12);
    }
  }, [actualIndex, idealDistance, idealIndex, lapData, idealLap, corners, formatDistance]);

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      {/* Legend */}
      <div className="absolute left-3 top-3 flex flex-col gap-1">
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-white" />
          <span className="text-[10px] font-medium text-white/70">Your Best Lap</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-400" />
          <span className="text-[10px] font-medium text-amber-400/70">Ideal Lap</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Get ideal speed at a given GPS index by mapping through distance.
 * GPS index i → distance in lapData → find matching distance in idealLap → speed.
 */
function getIdealSpeedAtGpsIndex(
  gpsIndex: number,
  lapDistances: number[],
  idealDistances: number[],
  idealSpeeds: number[],
): number {
  const dist = lapDistances[gpsIndex];
  // Binary search in ideal distances
  let lo = 0;
  let hi = idealDistances.length - 1;
  if (dist <= idealDistances[0]) return idealSpeeds[0];
  if (dist >= idealDistances[hi]) return idealSpeeds[hi];
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    if (idealDistances[mid] <= dist) lo = mid;
    else hi = mid;
  }
  // Linear interpolation between lo and hi
  const dRange = idealDistances[hi] - idealDistances[lo];
  if (dRange <= 0) return idealSpeeds[lo];
  const frac = (dist - idealDistances[lo]) / dRange;
  return idealSpeeds[lo] + frac * (idealSpeeds[hi] - idealSpeeds[lo]);
}

/**
 * Find the closest GPS index to a given lat/lon in the lap data.
 */
function findClosestGpsIndex(
  targetLat: number,
  targetLon: number,
  lapData: LapData,
): number {
  let bestIdx = 0;
  let bestDist = Infinity;
  // Sample every 5th point for performance (track has ~3000-5000 points)
  for (let i = 0; i < lapData.lat.length; i += 5) {
    const dlat = lapData.lat[i] - targetLat;
    const dlon = lapData.lon[i] - targetLon;
    const d = dlat * dlat + dlon * dlon;
    if (d < bestDist) {
      bestDist = d;
      bestIdx = i;
    }
  }
  // Refine within ±5 of best sample
  const start = Math.max(0, bestIdx - 5);
  const end = Math.min(lapData.lat.length - 1, bestIdx + 5);
  for (let i = start; i <= end; i++) {
    const dlat = lapData.lat[i] - targetLat;
    const dlon = lapData.lon[i] - targetLon;
    const d = dlat * dlat + dlon * dlon;
    if (d < bestDist) {
      bestDist = d;
      bestIdx = i;
    }
  }
  return bestIdx;
}

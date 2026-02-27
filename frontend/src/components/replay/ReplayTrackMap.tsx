'use client';

import { useCallback, useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { colors } from '@/lib/design-tokens';
import type { LapData } from '@/lib/types';

interface ReplayTrackMapProps {
  lapData: LapData;
  currentIndex: number;
}

const PADDING = 20;

/** Map speed (mph) to a colour along green -> yellow -> red. */
function speedColor(speed: number, minSpeed: number, maxSpeed: number): string {
  const range = maxSpeed - minSpeed || 1;
  const t = Math.max(0, Math.min(1, (speed - minSpeed) / range));
  // green(120) -> yellow(60) -> red(0)
  return `hsl(${(1 - t) * 120}, 90%, 50%)`;
}

/**
 * Canvas-based track map with animated replay dot and growing coloured trail.
 *
 * - Full track outline drawn once in muted grey.
 * - A coloured trail grows behind the moving dot, with colour based on speed.
 * - The current position is a glowing dot.
 */
export function ReplayTrackMap({ lapData, currentIndex }: ReplayTrackMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const projRef = useRef<{ x: Float64Array; y: Float64Array; w: number; h: number } | null>(null);
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

    // Compute speed bounds once
    minSpeedRef.current = d3.min(lapData.speed_mph) ?? 0;
    maxSpeedRef.current = d3.max(lapData.speed_mph) ?? 1;

    return () => observer.disconnect();
  }, [lapData, project]);

  // Re-draw on every index change
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

    ctx.clearRect(0, 0, w, h);

    // 1. Full track outline (muted)
    ctx.beginPath();
    ctx.moveTo(x[0], y[0]);
    for (let i = 1; i < n; i++) {
      ctx.lineTo(x[i], y[i]);
    }
    ctx.strokeStyle = colors.text.muted;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.3;
    ctx.stroke();
    ctx.globalAlpha = 1;

    // 2. Coloured trail up to currentIndex (draw in segments for per-point colour)
    const minSpd = minSpeedRef.current;
    const maxSpd = maxSpeedRef.current;
    const end = Math.min(currentIndex, n - 1);

    // Use thicker segments for the trail, skip points for perf if > 4000 pts
    const step = n > 4000 ? 2 : 1;
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';

    for (let i = 0; i < end; i += step) {
      const j = Math.min(i + step, end);
      ctx.beginPath();
      ctx.moveTo(x[i], y[i]);
      ctx.lineTo(x[j], y[j]);
      ctx.strokeStyle = speedColor(lapData.speed_mph[j], minSpd, maxSpd);
      ctx.stroke();
    }

    // 3. Current position dot with glow
    if (end >= 0 && end < n) {
      const cx = x[end];
      const cy = y[end];

      // Glow
      const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, 14);
      gradient.addColorStop(0, 'rgba(255, 255, 255, 0.6)');
      gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
      ctx.beginPath();
      ctx.arc(cx, cy, 14, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.fill();

      // Dot
      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.strokeStyle = speedColor(lapData.speed_mph[end], minSpd, maxSpd);
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }, [currentIndex, lapData]);

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
    </div>
  );
}

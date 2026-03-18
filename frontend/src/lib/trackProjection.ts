/**
 * Shared lat/lon → SVG projection utilities used by both the full TrackMapInteractive
 * and the lightweight MiniTrackMap overlay.
 */
import * as d3 from 'd3';
import type { LapData } from '@/lib/types';

export interface ProjectionParams {
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
  lonScale: number;
  scale: number;
  offsetX: number;
  offsetY: number;
  scaledH: number;
}

export function computeProjection(
  allLats: number[][],
  allLons: number[][],
  width: number,
  height: number,
  padding: number,
): ProjectionParams | null {
  const flatLat = allLats.flat();
  const flatLon = allLons.flat();
  if (flatLat.length === 0) return null;

  const minLat = d3.min(flatLat) ?? 0;
  const maxLat = d3.max(flatLat) ?? 0;
  const minLon = d3.min(flatLon) ?? 0;
  const maxLon = d3.max(flatLon) ?? 0;

  const latRange = maxLat - minLat || 1e-6;
  const lonRange = maxLon - minLon || 1e-6;

  const midLat = (minLat + maxLat) / 2;
  const lonScaleF = Math.cos((midLat * Math.PI) / 180);

  const dataWidth = lonRange * lonScaleF;
  const dataHeight = latRange;

  const availW = width - 2 * padding;
  const availH = height - 2 * padding;
  const scale = Math.min(availW / dataWidth, availH / dataHeight);

  const scaledW = dataWidth * scale;
  const scaledH = dataHeight * scale;
  const offsetX = padding + (availW - scaledW) / 2;
  const offsetY = padding + (availH - scaledH) / 2;

  return { minLat, maxLat, minLon, maxLon, lonScale: lonScaleF, scale, offsetX, offsetY, scaledH };
}

export function applyProjection(
  lat: number[],
  lon: number[],
  p: ProjectionParams,
): { x: number[]; y: number[] } {
  const x = lon.map((lo) => p.offsetX + (lo - p.minLon) * p.lonScale * p.scale);
  const y = lat.map((la) => p.offsetY + p.scaledH - (la - p.minLat) * p.scale);
  return { x, y };
}

/**
 * Given the cursor distance on the reference lap, compute the distance
 * the comparison lap has covered at the same elapsed time.
 *
 * This powers the "ghost dot": if the comp lap is slower, ghostDistance < cursorDistance
 * (the ghost trails behind). If faster, ghostDistance > cursorDistance (ghost leads).
 *
 * Both lap_time_s arrays are monotonically increasing, so inverse lookup is a bisection.
 */
export function computeGhostDistance(
  cursorDistance: number,
  refLap: LapData,
  compLap: LapData,
): number | null {
  if (
    refLap.lap_time_s.length < 2 ||
    compLap.lap_time_s.length < 2 ||
    refLap.distance_m.length < 2 ||
    compLap.distance_m.length < 2
  ) {
    return null;
  }

  // Defensive: clamp indices against the shorter of distance_m / lap_time_s
  const refN = Math.min(refLap.distance_m.length, refLap.lap_time_s.length);
  const compN = Math.min(compLap.distance_m.length, compLap.lap_time_s.length);

  // 1. Find elapsed time on ref lap at cursorDistance
  const refIdx = Math.min(d3.bisectLeft(refLap.distance_m, cursorDistance), refN - 1);
  let refTime: number;
  if (refIdx <= 0) {
    refTime = refLap.lap_time_s[0];
  } else {
    const d0 = refLap.distance_m[refIdx - 1];
    const d1 = refLap.distance_m[refIdx];
    const t = d1 !== d0 ? (cursorDistance - d0) / (d1 - d0) : 0;
    refTime =
      refLap.lap_time_s[refIdx - 1] +
      t * (refLap.lap_time_s[refIdx] - refLap.lap_time_s[refIdx - 1]);
  }

  // 2. Find distance on comp lap at refTime (inverse lookup on lap_time_s → distance_m)
  const rawCompIdx = d3.bisectLeft(compLap.lap_time_s, refTime);
  if (rawCompIdx <= 0) return compLap.distance_m[0];
  if (rawCompIdx >= compN) return compLap.distance_m[compN - 1];
  const compTimeIdx = rawCompIdx;

  const t0 = compLap.lap_time_s[compTimeIdx - 1];
  const t1 = compLap.lap_time_s[compTimeIdx];
  const frac = t1 !== t0 ? (refTime - t0) / (t1 - t0) : 0;
  return (
    compLap.distance_m[compTimeIdx - 1] +
    frac * (compLap.distance_m[compTimeIdx] - compLap.distance_m[compTimeIdx - 1])
  );
}

export function interpolateCursorPosition(
  cursorDistance: number,
  lapData: LapData,
  projected: { x: number[]; y: number[] },
): { cx: number; cy: number } | null {
  const idx = d3.bisectLeft(lapData.distance_m, cursorDistance);
  if (idx <= 0) return { cx: projected.x[0], cy: projected.y[0] };
  if (idx >= lapData.distance_m.length)
    return {
      cx: projected.x[projected.x.length - 1],
      cy: projected.y[projected.y.length - 1],
    };

  const d0 = lapData.distance_m[idx - 1];
  const d1 = lapData.distance_m[idx];
  const t = d1 !== d0 ? (cursorDistance - d0) / (d1 - d0) : 0;

  return {
    cx: projected.x[idx - 1] + t * (projected.x[idx] - projected.x[idx - 1]),
    cy: projected.y[idx - 1] + t * (projected.y[idx] - projected.y[idx - 1]),
  };
}

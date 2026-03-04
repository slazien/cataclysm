'use client';

import { useMemo } from 'react';
import * as d3 from 'd3';
import { colors } from '@/lib/design-tokens';
import type { ComparisonTrackCoords, ComparisonCornerDelta } from '@/lib/types';

const SVG_SIZE = 400;
const PADDING = 12;
const CHUNK_COUNT = 100;

interface ComparisonTrackMapProps {
  trackCoords: ComparisonTrackCoords;
  distanceM: number[];
  deltaTimeS: number[];
  cornerDeltas: ComparisonCornerDelta[];
}

function projectCoords(
  lat: number[],
  lon: number[],
): { x: number[]; y: number[] } {
  if (lat.length === 0) return { x: [], y: [] };

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

  const availW = SVG_SIZE - 2 * PADDING;
  const availH = SVG_SIZE - 2 * PADDING;
  const scale = Math.min(availW / dataWidth, availH / dataHeight);

  const scaledW = dataWidth * scale;
  const scaledH = dataHeight * scale;
  const offsetX = PADDING + (availW - scaledW) / 2;
  const offsetY = PADDING + (availH - scaledH) / 2;

  const x = lon.map((lo) => offsetX + (lo - minLon) * lonScale * scale);
  const y = lat.map((la) => offsetY + scaledH - (la - minLat) * scale);

  return { x, y };
}

interface Segment {
  d: string;
  color: string;
}

function buildDeltaSegments(
  projected: { x: number[]; y: number[] },
  trackDistanceM: number[],
  deltaDistanceM: number[],
  deltaTimeS: number[],
): Segment[] {
  const segments: Segment[] = [];
  const n = projected.x.length;
  if (n < 2 || deltaDistanceM.length === 0) return segments;

  const minDelta = d3.min(deltaTimeS) ?? -1;
  const maxDelta = d3.max(deltaTimeS) ?? 1;

  const deltaScale = d3
    .scaleLinear()
    .domain([minDelta, 0, maxDelta])
    .range([0, 0.5, 1])
    .clamp(true);

  const colorScale = d3
    .scaleLinear<string>()
    .domain([0, 0.5, 1])
    .range([colors.motorsport.throttle, colors.text.muted, colors.motorsport.brake]);

  const chunkSize = Math.max(1, Math.floor(n / CHUNK_COUNT));
  for (let i = 0; i < n - 1; i += chunkSize) {
    const end = Math.min(i + chunkSize + 1, n);
    const points: string[] = [];
    for (let j = i; j < end; j++) {
      points.push(`${projected.x[j]},${projected.y[j]}`);
    }

    const midDist = trackDistanceM[Math.min(i + Math.floor(chunkSize / 2), n - 1)];
    const dIdx = d3.bisectLeft(deltaDistanceM, midDist);
    const clampedIdx = Math.min(dIdx, deltaTimeS.length - 1);
    const dVal = deltaTimeS[clampedIdx];
    const t = deltaScale(dVal) as number;

    segments.push({
      d: 'M' + points.join('L'),
      color: colorScale(t) as string,
    });
  }

  return segments;
}

interface CornerLabel {
  x: number;
  y: number;
  number: number;
}

function buildCornerLabels(
  cornerDeltas: ComparisonCornerDelta[],
  trackDistanceM: number[],
  projected: { x: number[]; y: number[] },
): CornerLabel[] {
  return cornerDeltas.map((cd) => {
    const apexDist = (cd.entry_distance_m + cd.exit_distance_m) / 2;
    const idx = d3.bisectLeft(trackDistanceM, apexDist);
    const clampedIdx = Math.min(idx, projected.x.length - 1);
    return {
      x: projected.x[clampedIdx] ?? 0,
      y: projected.y[clampedIdx] ?? 0,
      number: cd.corner_number,
    };
  });
}

const SF_LEN = 18;
const SF_THICK = 6;
const SF_COLS = 6;
const SF_ROWS = 2;

function CheckeredSFLine({ x, y, angle }: { x: number; y: number; angle: number }) {
  const sqW = SF_LEN / SF_COLS;
  const sqH = SF_THICK / SF_ROWS;
  return (
    <g transform={`translate(${x}, ${y}) rotate(${angle})`}>
      {Array.from({ length: SF_COLS * SF_ROWS }, (_, i) => {
        const col = i % SF_COLS;
        const row = Math.floor(i / SF_COLS);
        return (
          <rect
            key={i}
            x={col * sqW - SF_LEN / 2}
            y={row * sqH - SF_THICK / 2}
            width={sqW + 0.3}
            height={sqH + 0.3}
            fill={(row + col) % 2 === 0 ? '#ffffff' : '#1a1a1a'}
          />
        );
      })}
    </g>
  );
}

export function ComparisonTrackMap({
  trackCoords,
  distanceM,
  deltaTimeS,
  cornerDeltas,
}: ComparisonTrackMapProps) {
  const { projected, segments, cornerLabels, sfLine } = useMemo(() => {
    const proj = projectCoords(trackCoords.lat, trackCoords.lon);
    const segs = buildDeltaSegments(proj, trackCoords.distance_m, distanceM, deltaTimeS);
    const labels = buildCornerLabels(cornerDeltas, trackCoords.distance_m, proj);

    const sfLine = (() => {
      if (proj.x.length < 2) return null;
      const look = Math.min(10, proj.x.length - 1);
      const dx = proj.x[look] - proj.x[0];
      const dy = proj.y[look] - proj.y[0];
      return {
        x: proj.x[0],
        y: proj.y[0],
        angle: Math.atan2(dy, dx) * (180 / Math.PI) + 90,
      };
    })();

    return { projected: proj, segments: segs, cornerLabels: labels, sfLine };
  }, [trackCoords, distanceM, deltaTimeS, cornerDeltas]);

  if (projected.x.length === 0) return null;

  return (
    <svg
      viewBox={`0 0 ${SVG_SIZE} ${SVG_SIZE}`}
      className="h-full max-h-full w-full"
      preserveAspectRatio="xMidYMid meet"
    >
      {/* Track path segments colored by delta */}
      {segments.map((seg, i) => (
        <path
          key={i}
          d={seg.d}
          fill="none"
          stroke={seg.color}
          strokeWidth={3}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}

      {/* Start/Finish checkered line */}
      {sfLine && <CheckeredSFLine x={sfLine.x} y={sfLine.y} angle={sfLine.angle} />}

      {/* Corner number labels */}
      {cornerLabels.map((label) => (
        <g key={label.number}>
          <circle
            cx={label.x}
            cy={label.y}
            r={10}
            fill={colors.bg.elevated}
            stroke={colors.text.muted}
            strokeWidth={1}
          />
          <text
            x={label.x}
            y={label.y}
            textAnchor="middle"
            dominantBaseline="central"
            fill={colors.text.primary}
            fontSize={8}
            fontWeight="bold"
            fontFamily="Inter, system-ui, sans-serif"
          >
            {label.number}
          </text>
        </g>
      ))}
    </svg>
  );
}

'use client';

import { useMemo } from 'react';
import * as d3 from 'd3';
import { useLapData } from '@/hooks/useSession';
import { useCorners } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useUiStore, useAnalysisStore } from '@/stores';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { colors } from '@/lib/design-tokens';
import type { Corner, CornerGrade, LapData } from '@/lib/types';

interface HeroTrackMapProps {
  sessionId: string;
  bestLapNumber: number;
}

const PADDING = 20;
const SVG_WIDTH = 500;
const SVG_HEIGHT = 360;

function projectCoords(
  lat: number[],
  lon: number[],
  width: number,
  height: number,
  padding: number,
): { x: number[]; y: number[] } {
  if (lat.length === 0) return { x: [], y: [] };

  // Use d3.min/max to avoid stack overflow with large arrays
  const minLat = d3.min(lat) ?? 0;
  const maxLat = d3.max(lat) ?? 0;
  const minLon = d3.min(lon) ?? 0;
  const maxLon = d3.max(lon) ?? 0;

  const latRange = maxLat - minLat || 1e-6;
  const lonRange = maxLon - minLon || 1e-6;

  // Correct for latitude distortion
  const midLat = (minLat + maxLat) / 2;
  const lonScale = Math.cos((midLat * Math.PI) / 180);

  const dataWidth = lonRange * lonScale;
  const dataHeight = latRange;

  const availW = width - 2 * padding;
  const availH = height - 2 * padding;
  const scale = Math.min(availW / dataWidth, availH / dataHeight);

  const scaledW = dataWidth * scale;
  const scaledH = dataHeight * scale;
  const offsetX = padding + (availW - scaledW) / 2;
  const offsetY = padding + (availH - scaledH) / 2;

  const x = lon.map((lo) => offsetX + (lo - minLon) * lonScale * scale);
  // Flip Y so north is up
  const y = lat.map((la) => offsetY + scaledH - (la - minLat) * scale);

  return { x, y };
}

function gradeToColor(grade: string): string {
  return (colors.grade as Record<string, string>)[grade.toLowerCase()] ?? colors.text.muted;
}

function speedToColor(speed: number, minSpeed: number, maxSpeed: number): string {
  const range = maxSpeed - minSpeed || 1;
  const t = (speed - minSpeed) / range;
  // Interpolate red -> amber -> green
  if (t < 0.5) {
    return colors.grade.f; // red for slow
  } else if (t < 0.75) {
    return colors.grade.c; // amber for medium
  }
  return colors.grade.a; // green for fast
}

function findSegmentIndex(distance_m: number[], targetDist: number): number {
  const i = d3.bisectLeft(distance_m, targetDist);
  return Math.min(i, distance_m.length - 1);
}

interface TrackSegment {
  startIdx: number;
  endIdx: number;
  color: string;
  cornerNumber?: number;
}

function computeSegments(
  lapData: LapData,
  corners: Corner[],
  cornerGrades: CornerGrade[] | null,
): TrackSegment[] {
  const { distance_m, speed_mph } = lapData;
  if (distance_m.length === 0) return [];

  const segments: TrackSegment[] = [];
  const sortedCorners = [...corners].sort(
    (a, b) => a.entry_distance_m - b.entry_distance_m,
  );

  // Build a grade lookup
  const gradeMap = new Map<number, CornerGrade>();
  if (cornerGrades) {
    cornerGrades.forEach((cg) => gradeMap.set(cg.corner, cg));
  }

  // Precompute speed range once (constant for a given lap)
  const minSpd = d3.min(speed_mph) ?? 0;
  const maxSpd = d3.max(speed_mph) ?? 1;

  let currentIdx = 0;

  for (const corner of sortedCorners) {
    const entryIdx = findSegmentIndex(distance_m, corner.entry_distance_m);
    const exitIdx = findSegmentIndex(distance_m, corner.exit_distance_m);

    // Straight section before this corner
    if (entryIdx > currentIdx) {
      segments.push({
        startIdx: currentIdx,
        endIdx: entryIdx,
        color: colors.text.muted,
      });
    }

    // Corner section
    const grade = gradeMap.get(corner.number);
    let cornerColor: string;
    if (grade) {
      // Average the grade letters to a single color
      const gradeLetters = [grade.braking, grade.min_speed, grade.throttle].filter(Boolean);
      if (gradeLetters.length > 0) {
        // Use the worst grade to color
        const gradeOrder = ['F', 'D', 'C', 'B', 'A'];
        const worstIdx = Math.min(
          ...gradeLetters.map((g) => {
            const idx = gradeOrder.indexOf(g.toUpperCase());
            return idx >= 0 ? idx : 2; // default to C
          }),
        );
        cornerColor = gradeToColor(gradeOrder[worstIdx]);
      } else {
        cornerColor = colors.text.muted;
      }
    } else {
      // No grades — color by speed
      cornerColor = speedToColor(corner.min_speed_mph, minSpd, maxSpd);
    }

    segments.push({
      startIdx: entryIdx,
      endIdx: exitIdx,
      color: cornerColor,
      cornerNumber: corner.number,
    });

    currentIdx = exitIdx;
  }

  // Trailing straight
  if (currentIdx < distance_m.length - 1) {
    segments.push({
      startIdx: currentIdx,
      endIdx: distance_m.length - 1,
      color: colors.text.muted,
    });
  }

  return segments;
}

interface CornerLabel {
  x: number;
  y: number;
  number: number;
}

export function HeroTrackMap({ sessionId, bestLapNumber }: HeroTrackMapProps) {
  const { data: lapData, isLoading: lapLoading } = useLapData(sessionId, bestLapNumber);
  const { data: corners, isLoading: cornersLoading } = useCorners(sessionId);
  const { data: report } = useCoachingReport(sessionId);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);

  const { segments, labels, projected, sfLine } = useMemo(() => {
    if (!lapData || !corners) {
      return { segments: [], labels: [], projected: null, sfLine: null };
    }

    const proj = projectCoords(lapData.lat, lapData.lon, SVG_WIDTH, SVG_HEIGHT, PADDING);
    const segs = computeSegments(
      lapData,
      corners,
      report?.corner_grades ?? null,
    );

    // Compute corner label positions at apex
    const labs: CornerLabel[] = corners.map((c) => {
      const apexIdx = findSegmentIndex(lapData.distance_m, c.apex_distance_m);
      return {
        x: proj.x[apexIdx] ?? 0,
        y: proj.y[apexIdx] ?? 0,
        number: c.number,
      };
    });

    // Compute S/F line angle (perpendicular to track at start)
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

    return { segments: segs, labels: labs, projected: proj, sfLine };
  }, [lapData, corners, report]);

  const handleCornerClick = (cornerNumber: number) => {
    selectCorner(`T${cornerNumber}`);
    setActiveView('deep-dive');
  };

  if (lapLoading || cornersLoading) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Track Map
        </h2>
        <div className="flex items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-8">
          <CircularProgress size={24} />
        </div>
      </div>
    );
  }

  if (!projected || projected.x.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Track Map
        </h2>
        <div className="flex items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-8">
          <p className="text-sm text-[var(--text-secondary)]">No GPS data available</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
        Track Map
      </h2>
      <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-2">
        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          className="h-auto w-full"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Draw track segments */}
          {segments.map((seg, i) => {
            const points: string[] = [];
            for (let j = seg.startIdx; j <= seg.endIdx && j < projected.x.length; j++) {
              points.push(`${projected.x[j]},${projected.y[j]}`);
            }
            if (points.length < 2) return null;
            return (
              <polyline
                key={i}
                points={points.join(' ')}
                fill="none"
                stroke={seg.color}
                strokeWidth={3.5}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={seg.cornerNumber !== undefined ? 1 : 0.4}
              />
            );
          })}

          {/* Corner labels */}
          {labels.map((label) => (
            <g
              key={label.number}
              onClick={() => handleCornerClick(label.number)}
              className="cursor-pointer"
            >
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

          {/* Start/Finish checkered line */}
          {sfLine && <CheckeredSFLine x={sfLine.x} y={sfLine.y} angle={sfLine.angle} />}
        </svg>
      </div>
    </div>
  );
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

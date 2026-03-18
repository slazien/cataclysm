'use client';

import { useMemo } from 'react';
import * as d3 from 'd3';
import { useMultiLapData, useCorners, useDelta } from '@/hooks/useAnalysis';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useCornerKings } from '@/hooks/useLeaderboard';
import { useSession } from '@/hooks/useSession';
import { useAnalysisStore, useSessionStore } from '@/stores';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { colors } from '@/lib/design-tokens';
import { worstGrade } from '@/lib/gradeUtils';
import {
  computeProjection,
  applyProjection,
  interpolateCursorPosition,
  computeGhostDistance,
} from '@/lib/trackProjection';
// GradeChip cannot be used inside SVG <foreignObject> reliably, so grade badges are rendered inline
import type { Corner, LapData, DeltaData, CornerGrade } from '@/lib/types';

interface TrackMapInteractiveProps {
  sessionId: string;
}

const SVG_WIDTH = 400;
const SVG_HEIGHT = 400;
const PADDING = 12;

interface TrackSegment {
  d: string;
  color: string;
}

function buildSegments(
  lapData: LapData,
  projected: { x: number[]; y: number[] },
  delta: DeltaData | null | undefined,
): TrackSegment[] {
  const segments: TrackSegment[] = [];
  const n = projected.x.length;
  if (n < 2) return segments;

  // If we have delta data, color by delta; otherwise color by speed
  if (delta && delta.distance_m.length > 0) {
    // Build a delta lookup: for each track point, find closest delta value
    const deltaScale = d3
      .scaleLinear()
      .domain([
        d3.min(delta.delta_s) ?? -1,
        0,
        d3.max(delta.delta_s) ?? 1,
      ])
      .range([0, 0.5, 1])
      .clamp(true);

    const colorScale = d3
      .scaleLinear<string>()
      .domain([0, 0.5, 1])
      .range([colors.motorsport.throttle, colors.text.muted, colors.motorsport.brake]);

    // Draw in small chunks
    const chunkSize = Math.max(1, Math.floor(n / 100));
    for (let i = 0; i < n - 1; i += chunkSize) {
      const end = Math.min(i + chunkSize + 1, n);
      const points: string[] = [];
      for (let j = i; j < end; j++) {
        points.push(`${projected.x[j]},${projected.y[j]}`);
      }
      // Find average delta in this segment
      const midDist = lapData.distance_m[Math.min(i + Math.floor(chunkSize / 2), n - 1)];
      const dIdx = d3.bisectLeft(delta.distance_m, midDist);
      const clampedDIdx = Math.min(dIdx, delta.delta_s.length - 1);
      const dVal = delta.delta_s[clampedDIdx];
      const t = deltaScale(dVal) as number;

      segments.push({
        d: 'M' + points.join('L'),
        color: colorScale(t) as string,
      });
    }
  } else {
    // Color by speed
    const minSpeed = d3.min(lapData.speed_mph) ?? 0;
    const maxSpeed = d3.max(lapData.speed_mph) ?? 1;
    const speedScale = d3
      .scaleLinear<string>()
      .domain([minSpeed, (minSpeed + maxSpeed) / 2, maxSpeed])
      .range([colors.motorsport.brake, colors.motorsport.neutral, colors.motorsport.throttle]);

    const chunkSize = Math.max(1, Math.floor(n / 100));
    for (let i = 0; i < n - 1; i += chunkSize) {
      const end = Math.min(i + chunkSize + 1, n);
      const points: string[] = [];
      for (let j = i; j < end; j++) {
        points.push(`${projected.x[j]},${projected.y[j]}`);
      }
      const midIdx = Math.min(i + Math.floor(chunkSize / 2), n - 1);
      const speed = lapData.speed_mph[midIdx];

      segments.push({
        d: 'M' + points.join('L'),
        color: speedScale(speed) as string,
      });
    }
  }

  return segments;
}

interface CornerLabel {
  x: number;
  y: number;
  number: number;
  grade: string | null;
}

function buildCornerLabels(
  corners: Corner[],
  lapData: LapData,
  projected: { x: number[]; y: number[] },
  cornerGrades: CornerGrade[] | null,
): CornerLabel[] {
  const gradeMap = new Map<number, string>();
  if (cornerGrades) {
    for (const cg of cornerGrades) {
      const gradeLetters = [cg.braking, cg.trail_braking, cg.min_speed, cg.throttle].filter(
        Boolean,
      );
      if (gradeLetters.length > 0) {
        gradeMap.set(cg.corner, worstGrade(gradeLetters));
      }
    }
  }

  return corners.map((c) => {
    const apexIdx = d3.bisectLeft(lapData.distance_m, c.nominal_distance_m ?? c.apex_distance_m);
    const clampedIdx = Math.min(apexIdx, projected.x.length - 1);
    return {
      x: projected.x[clampedIdx] ?? 0,
      y: projected.y[clampedIdx] ?? 0,
      number: c.number,
      grade: gradeMap.get(c.number) ?? null,
    };
  });
}

export function TrackMapInteractive({ sessionId }: TrackMapInteractiveProps) {
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const cursorDistance = useAnalysisStore((s) => s.cursorDistance);
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const { data: sessionData } = useSession(activeSessionId);
  const trackName = sessionData?.track_name ?? undefined;
  const { data: kingsData } = useCornerKings(trackName);

  // Build a set of corner numbers the user is king of
  const kingCorners = useMemo(() => {
    const set = new Set<number>();
    if (kingsData?.kings) {
      for (const k of kingsData.kings) {
        set.add(k.corner_number);
      }
    }
    return set;
  }, [kingsData]);

  const refLap = selectedLaps.length >= 2 ? selectedLaps[0] : null;
  const compLap = selectedLaps.length >= 2 ? selectedLaps[1] : null;

  const { data: lapDataArr, isLoading: lapsLoading } = useMultiLapData(
    sessionId,
    selectedLaps,
  );
  const { data: corners } = useCorners(sessionId);
  const { data: delta } = useDelta(sessionId, refLap, compLap);
  const { data: report } = useCoachingReport(sessionId);

  const lapData = lapDataArr[0] ?? null;
  const compLapData = lapDataArr.length >= 2 ? lapDataArr[1] : null;

  const { projected, segments, cornerLabels, sfLine, compPolyline, compProjected } = useMemo(() => {
    if (!lapData || !corners) {
      return {
        projected: null, segments: [], cornerLabels: [],
        sfLine: null, compPolyline: null, compProjected: null,
      };
    }

    // Compute shared projection bounds when comparing 2 laps
    const allLats = compLapData ? [lapData.lat, compLapData.lat] : [lapData.lat];
    const allLons = compLapData ? [lapData.lon, compLapData.lon] : [lapData.lon];
    const projParams = computeProjection(
      allLats, allLons, SVG_WIDTH, SVG_HEIGHT, PADDING,
    );
    if (!projParams) {
      return {
        projected: null, segments: [], cornerLabels: [],
        sfLine: null, compPolyline: null, compProjected: null,
      };
    }

    const proj = applyProjection(lapData.lat, lapData.lon, projParams);
    const segs = buildSegments(lapData, proj, delta);
    const labels = buildCornerLabels(
      corners,
      lapData,
      proj,
      report?.corner_grades ?? null,
    );

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

    // Project comparison lap using same coordinate frame
    let compPolyline: string | null = null;
    const compProj = compLapData
      ? applyProjection(compLapData.lat, compLapData.lon, projParams)
      : null;
    if (compProj && compProj.x.length >= 2) {
      const { x: cx, y: cy } = compProj;
      const pts = cx.map((xv, i) => `${xv},${cy[i]}`);
      compPolyline = 'M' + pts.join('L');
    }

    return {
      projected: proj, segments: segs, cornerLabels: labels,
      sfLine, compPolyline, compProjected: compProj,
    };
  }, [lapData, compLapData, corners, delta, report]);

  const cursorPos = useMemo(() => {
    if (cursorDistance === null || !lapData || !projected) return null;
    return interpolateCursorPosition(cursorDistance, lapData, projected);
  }, [cursorDistance, lapData, projected]);

  // Ghost dot: where the comparison lap would be at the same elapsed time
  const ghostPos = useMemo(() => {
    if (cursorDistance === null || !lapData || !compLapData || !compProjected) return null;
    const ghostDist = computeGhostDistance(cursorDistance, lapData, compLapData);
    if (ghostDist === null) return null;
    return interpolateCursorPosition(ghostDist, compLapData, compProjected);
  }, [cursorDistance, lapData, compLapData, compProjected]);

  const isComparing = compLapData !== null;

  const handleCornerClick = (cornerNumber: number) => {
    const cornerId = `T${cornerNumber}`;
    selectCorner(selectedCorner === cornerId ? null : cornerId);
  };

  if (lapsLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <CircularProgress size={20} />
      </div>
    );
  }

  if (!projected || projected.x.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">
          {selectedLaps.length === 0 ? 'Select laps to view track map' : 'No GPS data available'}
        </p>
      </div>
    );
  }

  return (
    <div className="h-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-1">
      <svg
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        className="h-full max-h-full w-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Comparison lap trace (underneath, thinner) */}
        {compPolyline && (
          <path
            d={compPolyline}
            fill="none"
            stroke={colors.comparison.compare}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.7}
          />
        )}

        {/* Track path segments */}
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

        {/* Corner labels with grade chips */}
        {cornerLabels.map((label) => {
          const isSelected = selectedCorner === `T${label.number}`;
          return (
            <g
              key={label.number}
              onClick={() => handleCornerClick(label.number)}
              className="cursor-pointer"
            >
              {/* Selected corner pulsing ring */}
              {isSelected && (
                <circle
                  cx={label.x}
                  cy={label.y}
                  r={16}
                  fill="none"
                  stroke={colors.motorsport.optimal}
                  strokeWidth={2}
                  opacity={0.6}
                >
                  <animate
                    attributeName="r"
                    values="14;18;14"
                    dur="1.5s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.6;0.2;0.6"
                    dur="1.5s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}
              <circle
                cx={label.x}
                cy={label.y}
                r={10}
                fill={colors.bg.elevated}
                stroke={isSelected ? colors.motorsport.optimal : colors.text.muted}
                strokeWidth={isSelected ? 2 : 1}
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
              {/* Crown for Corner King */}
              {kingCorners.has(label.number) && (
                <text
                  x={label.x - 10}
                  y={label.y - 10}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={8}
                >
                  {'\u{1F451}'}
                </text>
              )}
              {/* Grade badge offset */}
              {label.grade && (
                <g transform={`translate(${label.x + 10}, ${label.y - 10})`}>
                  <foreignObject x={-8} y={-6} width={20} height={14}>
                    <div
                      style={{
                        fontSize: '7px',
                        fontWeight: 'bold',
                        textAlign: 'center',
                        lineHeight: '14px',
                        borderRadius: '3px',
                        color:
                          (colors.grade as Record<string, string>)[label.grade.toLowerCase()] ??
                          colors.text.muted,
                        backgroundColor: `${(colors.grade as Record<string, string>)[label.grade.toLowerCase()] ?? colors.text.muted}22`,
                      }}
                    >
                      {label.grade}
                    </div>
                  </foreignObject>
                </g>
              )}
            </g>
          );
        })}

        {/* Ghost dot (comparison lap position at same elapsed time) */}
        {ghostPos && (
          <circle
            cx={ghostPos.cx}
            cy={ghostPos.cy}
            r={4}
            fill={colors.comparison.compare}
            stroke="#fff"
            strokeWidth={1.5}
            opacity={0.7}
          >
            <animate
              attributeName="r"
              values="3;5;3"
              dur="1s"
              repeatCount="indefinite"
            />
          </circle>
        )}

        {/* Animated cursor dot — blue when comparing, green when single lap */}
        {cursorPos && (
          <circle
            cx={cursorPos.cx}
            cy={cursorPos.cy}
            r={5}
            fill={isComparing ? colors.comparison.reference : colors.motorsport.optimal}
            stroke="#fff"
            strokeWidth={1.5}
          >
            <animate
              attributeName="r"
              values="4;6;4"
              dur="1s"
              repeatCount="indefinite"
            />
          </circle>
        )}
      </svg>
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

'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAnimationFrame } from '@/hooks/useAnimationFrame';
import { useLineAnalysis, useCorners } from '@/hooks/useAnalysis';
import { useUnits } from '@/hooks/useUnits';
import { useAnalysisStore } from '@/stores';
import { colors, fonts } from '@/lib/design-tokens';
import type { Corner, LapSpatialTrace, CornerLineProfile } from '@/lib/types';

const MPS_TO_MPH = 2.23694;
const SPACING_M = 0.7; // distance-domain resampling spacing
const TRACK_HALF_WIDTH_M = 5.5; // estimated half-width for boundary drawing

const EXAG_MIN = 1;
const EXAG_MAX = 8;
const EXAG_STEP = 0.5;

const MARGINS = { top: 8, right: 8, bottom: 8, left: 8 };

// Time-interval dots: one dot every N seconds
const TIME_DOT_INTERVAL_S = 0.25;

interface CornerZone {
  startIdx: number;
  endIdx: number;
  apexIdx: number;
}

function getCornerZone(corner: Corner, padBefore: number, padAfter: number, maxIdx: number): CornerZone {
  const startDist = Math.max(0, corner.entry_distance_m - padBefore);
  const endDist = corner.exit_distance_m + padAfter;
  return {
    startIdx: Math.max(0, Math.min(Math.round(startDist / SPACING_M), maxIdx)),
    endIdx: Math.max(0, Math.min(Math.round(endDist / SPACING_M), maxIdx)),
    apexIdx: Math.max(0, Math.min(Math.round(corner.apex_distance_m / SPACING_M), maxIdx)),
  };
}

/**
 * Compute the unit-length normal (perpendicular) to the reference line at each point.
 * Normal points "left" of the travel direction (consistent sign convention).
 */
function computeReferenceNormals(
  refE: number[],
  refN: number[],
  startIdx: number,
  endIdx: number,
): { ne: number[]; nn: number[] } {
  const ne: number[] = new Array(refE.length).fill(0);
  const nn: number[] = new Array(refN.length).fill(0);

  for (let i = startIdx; i <= endIdx && i < refE.length; i++) {
    let de: number, dn: number;
    if (i === 0 || i === startIdx) {
      de = refE[Math.min(i + 1, refE.length - 1)] - refE[i];
      dn = refN[Math.min(i + 1, refN.length - 1)] - refN[i];
    } else if (i >= refE.length - 1 || i >= endIdx) {
      de = refE[i] - refE[i - 1];
      dn = refN[i] - refN[i - 1];
    } else {
      de = refE[i + 1] - refE[i - 1];
      dn = refN[i + 1] - refN[i - 1];
    }
    const len = Math.sqrt(de * de + dn * dn) || 1;
    ne[i] = -dn / len;
    nn[i] = de / len;
  }
  return { ne, nn };
}

function computeLateralOffset(
  traceE: number, traceN: number,
  refE: number, refN: number,
  normalE: number, normalN: number,
): number {
  const de = traceE - refE;
  const dn = traceN - refN;
  return de * normalE + dn * normalN;
}

function exaggeratePoint(
  traceE: number, traceN: number,
  refE: number, refN: number,
  normalE: number, normalN: number,
  exag: number,
): { e: number; n: number } {
  if (exag === 1) return { e: traceE, n: traceN };
  const offset = computeLateralOffset(traceE, traceN, refE, refN, normalE, normalN);
  const extra = offset * (exag - 1);
  return {
    e: traceE + extra * normalE,
    n: traceN + extra * normalN,
  };
}

/**
 * Rotate coordinates so entry-to-exit direction points upward (north).
 */
function rotateCornerAligned(
  eArr: number[], nArr: number[],
  entryE: number, entryN: number,
  exitE: number, exitN: number,
): { e: number[]; n: number[] } {
  const travelAngle = Math.atan2(exitN - entryN, exitE - entryE);
  const rotation = Math.PI / 2 - travelAngle;
  const cosR = Math.cos(rotation);
  const sinR = Math.sin(rotation);
  const cx = (entryE + exitE) / 2;
  const cy = (entryN + exitN) / 2;

  const re: number[] = new Array(eArr.length);
  const rn: number[] = new Array(nArr.length);
  for (let i = 0; i < eArr.length; i++) {
    const de = eArr[i] - cx;
    const dn = nArr[i] - cy;
    re[i] = cosR * de - sinR * dn + cx;
    rn[i] = sinR * de + cosR * dn + cy;
  }
  return { e: re, n: rn };
}

/**
 * Compute cumulative time from speed (speed_mps) and spacing, returning
 * indices where equal-time markers should be placed.
 */
function computeTimeDotIndices(speedMps: number[], startIdx: number, endIdx: number): number[] {
  const indices: number[] = [];
  let cumulativeTime = 0;
  let nextDotTime = TIME_DOT_INTERVAL_S;

  for (let i = startIdx + 1; i <= endIdx && i < speedMps.length; i++) {
    const avgSpeed = (speedMps[i] + speedMps[i - 1]) / 2;
    if (avgSpeed > 0.1) {
      cumulativeTime += SPACING_M / avgSpeed;
    }
    if (cumulativeTime >= nextDotTime) {
      indices.push(i - startIdx);
      nextDotTime += TIME_DOT_INTERVAL_S;
    }
  }
  return indices;
}

function drawSpeedColoredLine(
  ctx: CanvasRenderingContext2D,
  eCoords: number[],
  nCoords: number[],
  speed: number[],
  startIdx: number,
  endIdx: number,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  colorScale: d3.ScaleSequential<string>,
  lineWidth: number,
) {
  for (let i = startIdx + 1; i <= endIdx && i < eCoords.length; i++) {
    if (i >= speed.length) break;
    ctx.strokeStyle = colorScale(speed[i]);
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    ctx.moveTo(xScale(eCoords[i - 1]), yScale(nCoords[i - 1]));
    ctx.lineTo(xScale(eCoords[i]), yScale(nCoords[i]));
    ctx.stroke();
  }
}

function drawMarker(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  label: string,
  fillColor: string,
  shape: 'circle' | 'diamond' | 'triangle',
) {
  const r = 4;
  ctx.fillStyle = fillColor;
  ctx.beginPath();
  if (shape === 'circle') {
    ctx.arc(x, y, r, 0, Math.PI * 2);
  } else if (shape === 'diamond') {
    ctx.moveTo(x, y - r);
    ctx.lineTo(x + r, y);
    ctx.lineTo(x, y + r);
    ctx.lineTo(x - r, y);
    ctx.closePath();
  } else {
    ctx.moveTo(x, y - r);
    ctx.lineTo(x + r * 0.87, y + r * 0.5);
    ctx.lineTo(x - r * 0.87, y + r * 0.5);
    ctx.closePath();
  }
  ctx.fill();

  ctx.fillStyle = colors.text.secondary;
  ctx.font = `9px ${fonts.mono}`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'bottom';
  ctx.fillText(label, x, y - 6);
}

interface CornerLineMapProps {
  sessionId: string;
  cornerNumber: number;
}

export function CornerLineMap({ sessionId, cornerNumber }: CornerLineMapProps) {
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const { data: lineData } = useLineAnalysis(sessionId);
  const { data: corners } = useCorners(sessionId);
  const { convertSpeed, speedUnit } = useUnits();
  const [exaggeration, setExaggeration] = useState(4);
  const [rotateAligned, setRotateAligned] = useState(false);
  const [showTimeDots, setShowTimeDots] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const animationRef = useRef<{ startTime: number; duration: number } | null>(null);
  const animationProgressRef = useRef(0);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx, makeTouchProps } =
    useCanvasChart(MARGINS);

  // Refs for RAF-based overlay (avoid stale closures)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const renderDataRef = useRef<any>(null);
  const xScaleRef = useRef(null as d3.ScaleLinear<number, number> | null);
  const yScaleRef = useRef(null as d3.ScaleLinear<number, number> | null);
  const dimsRef = useRef(dimensions);
  dimsRef.current = dimensions;

  const corner = useMemo(() => corners?.find((c) => c.number === cornerNumber), [corners, cornerNumber]);

  const profile: CornerLineProfile | undefined = useMemo(
    () => lineData?.corner_profiles.find((p) => p.corner_number === cornerNumber),
    [lineData, cornerNumber],
  );

  // Compute render data with optional rotation
  const renderData = useMemo(() => {
    if (!lineData?.available || !corner || !lineData.lap_traces.length) return null;

    const maxIdx = lineData.distance_m.length - 1;
    const zone = getCornerZone(corner, 15, 25, maxIdx);
    if (zone.endIdx <= zone.startIdx) return null;

    const normals = computeReferenceNormals(
      lineData.reference_e, lineData.reference_n, zone.startIdx, zone.endIdx,
    );

    const bestLapNum = profile?.best_lap_number ?? null;
    const tracesToRender: { trace: LapSpatialTrace; isBest: boolean; isSelected: boolean }[] = [];

    if (bestLapNum !== null) {
      const bestTrace = lineData.lap_traces.find((t) => t.lap_number === bestLapNum);
      if (bestTrace) {
        tracesToRender.push({ trace: bestTrace, isBest: true, isSelected: selectedLaps.includes(bestLapNum) });
      }
    }

    for (const lapNum of selectedLaps) {
      if (lapNum === bestLapNum) continue;
      const trace = lineData.lap_traces.find((t) => t.lap_number === lapNum);
      if (trace) {
        tracesToRender.push({ trace, isBest: false, isSelected: true });
      }
    }

    if (tracesToRender.length === 0) return null;

    // Rotation reference points (from reference line at entry/exit)
    const entryRefE = lineData.reference_e[zone.startIdx];
    const entryRefN = lineData.reference_n[zone.startIdx];
    const exitRefE = lineData.reference_e[zone.endIdx];
    const exitRefN = lineData.reference_n[zone.endIdx];

    // Pre-compute exaggerated (and optionally rotated) coordinates
    const exaggeratedTraces = tracesToRender.map(({ trace, isBest, isSelected }) => {
      const rawE: number[] = [];
      const rawN: number[] = [];
      for (let i = zone.startIdx; i <= zone.endIdx && i < trace.e.length; i++) {
        if (i < lineData.reference_e.length) {
          const p = exaggeratePoint(
            trace.e[i], trace.n[i],
            lineData.reference_e[i], lineData.reference_n[i],
            normals.ne[i], normals.nn[i],
            exaggeration,
          );
          rawE.push(p.e);
          rawN.push(p.n);
        }
      }

      let exE = rawE;
      let exN = rawN;
      if (rotateAligned) {
        const rotated = rotateCornerAligned(rawE, rawN, entryRefE, entryRefN, exitRefE, exitRefN);
        exE = rotated.e;
        exN = rotated.n;
      }

      // Compute time-dot indices
      const timeDotIndices = computeTimeDotIndices(trace.speed_mps, zone.startIdx, zone.endIdx);

      return { trace, isBest, isSelected, exE, exN, timeDotIndices };
    });

    // Track edges
    const leftEdgeRawE: number[] = [];
    const leftEdgeRawN: number[] = [];
    const rightEdgeRawE: number[] = [];
    const rightEdgeRawN: number[] = [];
    for (let i = zone.startIdx; i <= zone.endIdx && i < lineData.reference_e.length; i++) {
      const hw = TRACK_HALF_WIDTH_M * exaggeration;
      leftEdgeRawE.push(lineData.reference_e[i] + normals.ne[i] * hw);
      leftEdgeRawN.push(lineData.reference_n[i] + normals.nn[i] * hw);
      rightEdgeRawE.push(lineData.reference_e[i] - normals.ne[i] * hw);
      rightEdgeRawN.push(lineData.reference_n[i] - normals.nn[i] * hw);
    }

    let leftEdge = { e: leftEdgeRawE, n: leftEdgeRawN };
    let rightEdge = { e: rightEdgeRawE, n: rightEdgeRawN };
    if (rotateAligned) {
      const lRot = rotateCornerAligned(leftEdgeRawE, leftEdgeRawN, entryRefE, entryRefN, exitRefE, exitRefN);
      leftEdge = { e: lRot.e, n: lRot.n };
      const rRot = rotateCornerAligned(rightEdgeRawE, rightEdgeRawN, entryRefE, entryRefN, exitRefE, exitRefN);
      rightEdge = { e: rRot.e, n: rRot.n };
    }

    // Bounds
    let minE = Infinity, maxE = -Infinity, minN = Infinity, maxN = -Infinity;
    let minSpeed = Infinity, maxSpeed = -Infinity;

    for (const { exE, exN, trace } of exaggeratedTraces) {
      for (let j = 0; j < exE.length; j++) {
        minE = Math.min(minE, exE[j]);
        maxE = Math.max(maxE, exE[j]);
        minN = Math.min(minN, exN[j]);
        maxN = Math.max(maxN, exN[j]);
        const si = zone.startIdx + j;
        if (si < trace.speed_mps.length) {
          minSpeed = Math.min(minSpeed, trace.speed_mps[si]);
          maxSpeed = Math.max(maxSpeed, trace.speed_mps[si]);
        }
      }
    }

    for (let j = 0; j < leftEdge.e.length; j++) {
      minE = Math.min(minE, leftEdge.e[j], rightEdge.e[j]);
      maxE = Math.max(maxE, leftEdge.e[j], rightEdge.e[j]);
      minN = Math.min(minN, leftEdge.n[j], rightEdge.n[j]);
      maxN = Math.max(maxN, leftEdge.n[j], rightEdge.n[j]);
    }

    if (!isFinite(minE) || !isFinite(minSpeed)) return null;

    const rangeE = maxE - minE || 10;
    const rangeN = maxN - minN || 10;
    const padE = Math.max(rangeE * 0.15, 3);
    const padN = Math.max(rangeN * 0.15, 3);

    return {
      zone,
      normals,
      exaggeratedTraces,
      leftEdge,
      rightEdge,
      bounds: { minE: minE - padE, maxE: maxE + padE, minN: minN - padN, maxN: maxN + padN },
      speedRange: { min: minSpeed, max: maxSpeed },
    };
  }, [lineData, corner, profile, selectedLaps, exaggeration, rotateAligned]);

  // Keep refs current
  renderDataRef.current = renderData;

  // Build D3 scales maintaining 1:1 aspect ratio
  const { xScale, yScale } = useMemo(() => {
    if (!renderData || dimensions.innerWidth <= 0 || dimensions.innerHeight <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.top + 1, MARGINS.top]),
      };
    }

    const { bounds } = renderData;
    const dataW = bounds.maxE - bounds.minE;
    const dataH = bounds.maxN - bounds.minN;
    const { innerWidth, innerHeight } = dimensions;

    const scaleX = innerWidth / dataW;
    const scaleY = innerHeight / dataH;
    const scale = Math.min(scaleX, scaleY);

    const usedW = dataW * scale;
    const usedH = dataH * scale;
    const offsetX = (innerWidth - usedW) / 2;
    const offsetY = (innerHeight - usedH) / 2;

    return {
      xScale: d3.scaleLinear()
        .domain([bounds.minE, bounds.maxE])
        .range([MARGINS.left + offsetX, MARGINS.left + offsetX + usedW]),
      yScale: d3.scaleLinear()
        .domain([bounds.minN, bounds.maxN])
        .range([MARGINS.top + offsetY + usedH, MARGINS.top + offsetY]),
    };
  }, [renderData, dimensions.innerWidth, dimensions.innerHeight]);

  xScaleRef.current = xScale;
  yScaleRef.current = yScale;

  // Main data canvas draw
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || !renderData || dimensions.innerWidth <= 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    const { zone, exaggeratedTraces, leftEdge, rightEdge, speedRange } = renderData;

    const localColorScale = d3.scaleSequential(d3.interpolatePlasma)
      .domain([speedRange.min, speedRange.max]);

    // Track surface fill
    ctx.fillStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.beginPath();
    for (let j = 0; j < leftEdge.e.length; j++) {
      const x = xScale(leftEdge.e[j]);
      const y = yScale(leftEdge.n[j]);
      if (j === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    for (let j = rightEdge.e.length - 1; j >= 0; j--) {
      ctx.lineTo(xScale(rightEdge.e[j]), yScale(rightEdge.n[j]));
    }
    ctx.closePath();
    ctx.fill();

    // Track edges
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([]);
    for (const edge of [leftEdge, rightEdge]) {
      ctx.beginPath();
      for (let j = 0; j < edge.e.length; j++) {
        const x = xScale(edge.e[j]);
        const y = yScale(edge.n[j]);
        if (j === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Reference centerline (dashed)
    if (lineData?.reference_e && lineData.reference_n) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);

      // Need to apply same rotation to reference if rotateAligned
      let refE = lineData.reference_e;
      let refN = lineData.reference_n;
      if (rotateAligned) {
        const entryRefE = lineData.reference_e[zone.startIdx];
        const entryRefN = lineData.reference_n[zone.startIdx];
        const exitRefE = lineData.reference_e[zone.endIdx];
        const exitRefN = lineData.reference_n[zone.endIdx];
        const sliceE: number[] = [];
        const sliceN: number[] = [];
        for (let i = zone.startIdx; i <= zone.endIdx && i < lineData.reference_e.length; i++) {
          sliceE.push(lineData.reference_e[i]);
          sliceN.push(lineData.reference_n[i]);
        }
        const rot = rotateCornerAligned(sliceE, sliceN, entryRefE, entryRefN, exitRefE, exitRefN);
        ctx.beginPath();
        for (let j = 0; j < rot.e.length; j++) {
          const x = xScale(rot.e[j]);
          const y = yScale(rot.n[j]);
          if (j === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      } else {
        ctx.beginPath();
        for (let i = zone.startIdx; i <= zone.endIdx && i < refE.length; i++) {
          const x = xScale(refE[i]);
          const y = yScale(refN[i]);
          if (i === zone.startIdx) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      ctx.setLineDash([]);
    }

    // Draw lap traces: best first (behind), then selected (on top)
    const sorted = [...exaggeratedTraces].sort((a, b) => {
      if (a.isBest && !b.isBest) return -1;
      if (!a.isBest && b.isBest) return 1;
      return 0;
    });

    for (const { trace, isBest, exE, exN } of sorted) {
      const speedSlice: number[] = [];
      for (let i = zone.startIdx; i <= zone.endIdx && i < trace.speed_mps.length; i++) {
        speedSlice.push(trace.speed_mps[i]);
      }
      drawSpeedColoredLine(
        ctx, exE, exN, speedSlice,
        0, exE.length - 1,
        xScale, yScale, localColorScale,
        isBest && !sorted.every((s) => s.isBest) ? 2 : 3,
      );
    }

    // Time-interval dots
    if (showTimeDots) {
      for (const { exE, exN, timeDotIndices, isBest } of sorted) {
        const dotColor = isBest ? colors.comparison.reference : colors.comparison.compare;
        ctx.fillStyle = dotColor;
        for (const idx of timeDotIndices) {
          if (idx < exE.length) {
            ctx.beginPath();
            ctx.arc(xScale(exE[idx]), yScale(exN[idx]), 2.5, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
    }

    // Entry/apex/exit markers
    const primaryTrace = sorted.find((s) => s.isSelected && !s.isBest) ?? sorted[0];
    if (primaryTrace) {
      const entryDistIdx = Math.max(zone.startIdx, Math.round(corner!.entry_distance_m / SPACING_M));
      const apexDistIdx = zone.apexIdx;
      const exitDistIdx = Math.min(zone.endIdx, Math.round(corner!.exit_distance_m / SPACING_M));

      const entryLocal = entryDistIdx - zone.startIdx;
      const apexLocal = apexDistIdx - zone.startIdx;
      const exitLocal = exitDistIdx - zone.startIdx;

      if (entryLocal >= 0 && entryLocal < primaryTrace.exE.length) {
        drawMarker(ctx, xScale(primaryTrace.exE[entryLocal]), yScale(primaryTrace.exN[entryLocal]), 'Entry', colors.text.secondary, 'triangle');
      }
      if (apexLocal >= 0 && apexLocal < primaryTrace.exE.length) {
        drawMarker(ctx, xScale(primaryTrace.exE[apexLocal]), yScale(primaryTrace.exN[apexLocal]), 'Apex', colors.motorsport.brake, 'diamond');
      }
      if (exitLocal >= 0 && exitLocal < primaryTrace.exE.length) {
        drawMarker(ctx, xScale(primaryTrace.exE[exitLocal]), yScale(primaryTrace.exN[exitLocal]), 'Exit', colors.motorsport.throttle, 'circle');
      }
    }

    // Speed delta annotation at apex
    const bestEntry = sorted.find((s) => s.isBest);
    const selEntry = sorted.find((s) => s.isSelected && !s.isBest);
    if (bestEntry && selEntry && corner) {
      const apexLocal = zone.apexIdx - zone.startIdx;
      const bestSpeedIdx = Math.min(zone.apexIdx, bestEntry.trace.speed_mps.length - 1);
      const selSpeedIdx = Math.min(zone.apexIdx, selEntry.trace.speed_mps.length - 1);
      if (bestSpeedIdx >= 0 && selSpeedIdx >= 0) {
        const bestSpd = bestEntry.trace.speed_mps[bestSpeedIdx];
        const selSpd = selEntry.trace.speed_mps[selSpeedIdx];
        const deltaMps = bestSpd - selSpd;
        const deltaDisplay = convertSpeed(deltaMps * MPS_TO_MPH);

        if (Math.abs(deltaDisplay) > 0.1 && apexLocal >= 0 && apexLocal < bestEntry.exE.length) {
          const apexX = xScale(bestEntry.exE[apexLocal]);
          const apexY = yScale(bestEntry.exN[apexLocal]);

          const label = `Best: ${deltaDisplay > 0 ? '+' : ''}${deltaDisplay.toFixed(1)} ${speedUnit}`;
          ctx.font = `bold 10px ${fonts.mono}`;
          const tw = ctx.measureText(label).width;
          const px = Math.min(apexX + 12, MARGINS.left + dimensions.innerWidth - tw - 12);
          const py = Math.max(apexY - 16, MARGINS.top + 14);

          ctx.fillStyle = 'rgba(10, 12, 16, 0.85)';
          const rx = px - 4, ry = py - 10, rw = tw + 8, rh = 16, rr = 3;
          ctx.beginPath();
          ctx.moveTo(rx + rr, ry);
          ctx.lineTo(rx + rw - rr, ry);
          ctx.quadraticCurveTo(rx + rw, ry, rx + rw, ry + rr);
          ctx.lineTo(rx + rw, ry + rh - rr);
          ctx.quadraticCurveTo(rx + rw, ry + rh, rx + rw - rr, ry + rh);
          ctx.lineTo(rx + rr, ry + rh);
          ctx.quadraticCurveTo(rx, ry + rh, rx, ry + rh - rr);
          ctx.lineTo(rx, ry + rr);
          ctx.quadraticCurveTo(rx, ry, rx + rr, ry);
          ctx.closePath();
          ctx.fill();

          ctx.fillStyle = deltaMps > 0 ? colors.motorsport.throttle : colors.motorsport.brake;
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          ctx.fillText(label, px, py - 2);
        }
      }
    }

    // Color scale legend (bottom-right)
    const legendW = 8;
    const legendH = Math.min(60, dimensions.innerHeight * 0.4);
    const legendX = dimensions.width - MARGINS.right - legendW - 4;
    const legendY = dimensions.height - MARGINS.bottom - legendH - 4;

    for (let i = 0; i < legendH; i++) {
      const t = 1 - i / legendH;
      const speed = speedRange.min + t * (speedRange.max - speedRange.min);
      ctx.fillStyle = localColorScale(speed);
      ctx.fillRect(legendX, legendY + i, legendW, 1);
    }

    ctx.fillStyle = colors.text.secondary;
    ctx.font = `9px ${fonts.mono}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    const maxLabel = `${convertSpeed(speedRange.max * MPS_TO_MPH).toFixed(0)}`;
    const minLabel = `${convertSpeed(speedRange.min * MPS_TO_MPH).toFixed(0)}`;
    ctx.fillText(maxLabel, legendX - ctx.measureText(maxLabel).width - 2, legendY - 1);
    ctx.fillText(minLabel, legendX - ctx.measureText(minLabel).width - 2, legendY + legendH - 8);

    // Lap legend (top-left)
    ctx.font = `10px ${fonts.sans}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    let ly = MARGINS.top + 2;
    for (const { trace, isBest } of sorted) {
      const lapLabel = isBest
        ? `L${trace.lap_number} (Best)`
        : `L${trace.lap_number}`;
      ctx.fillStyle = isBest ? colors.comparison.reference : colors.comparison.compare;
      ctx.fillRect(MARGINS.left + 4, ly + 2, 10, 2);
      ctx.fillStyle = colors.text.secondary;
      ctx.fillText(lapLabel, MARGINS.left + 18, ly - 1);
      ly += 14;
    }
  }, [renderData, lineData, xScale, yScale, dimensions, corner, convertSpeed, speedUnit, exaggeration, showTimeDots, rotateAligned]);

  // --- Overlay: cursor sync + hover tooltip + animated replay ---

  // Convert mouse position to nearest distance index on the primary trace
  const findNearestPoint = useCallback(
    (clientX: number, clientY: number): { distanceIdx: number; traceIdx: number; localIdx: number } | null => {
      const rd = renderDataRef.current;
      const xs = xScaleRef.current;
      const ys = yScaleRef.current;
      if (!rd || !xs || !ys) return null;

      const canvas = overlayCanvasRef.current;
      if (!canvas) return null;
      const rect = canvas.getBoundingClientRect();
      const mx = clientX - rect.left;
      const my = clientY - rect.top;

      // Scale for HiDPI
      const dpr = window.devicePixelRatio || 1;
      const canvasX = mx * dpr;
      const canvasY = my * dpr;

      let bestDist = Infinity;
      let bestResult: { distanceIdx: number; traceIdx: number; localIdx: number } | null = null;

      for (let ti = 0; ti < rd.exaggeratedTraces.length; ti++) {
        const { exE, exN } = rd.exaggeratedTraces[ti];
        for (let j = 0; j < exE.length; j++) {
          const px = xs(exE[j]) * dpr;
          const py = ys(exN[j]) * dpr;
          const d = (canvasX - px) ** 2 + (canvasY - py) ** 2;
          if (d < bestDist) {
            bestDist = d;
            bestResult = { distanceIdx: rd.zone.startIdx + j, traceIdx: ti, localIdx: j };
          }
        }
      }

      // Only match if within 20px (canvas coords)
      if (bestDist > (20 * dpr) ** 2) return null;
      return bestResult;
    },
    [],
  );

  const handleOverlayMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const result = findNearestPoint(e.clientX, e.clientY);
      if (result) {
        // Write cursor distance to store for sync with other charts
        const distance = result.distanceIdx * SPACING_M;
        useAnalysisStore.getState().setCursorDistance(distance);
      }
    },
    [findNearestPoint],
  );

  const handleOverlayMouseLeave = useCallback(() => {
    useAnalysisStore.getState().setCursorDistance(null);
  }, []);

  // Overlay RAF loop: draw cursor position dot + hover tooltip
  useAnimationFrame(() => {
    const ctx = getOverlayCtx();
    if (!ctx) return;
    const dims = dimsRef.current;
    ctx.clearRect(0, 0, dims.width, dims.height);

    const rd = renderDataRef.current;
    const xs = xScaleRef.current;
    const ys = yScaleRef.current;
    if (!rd || !xs || !ys) return;

    // Animated replay
    if (isAnimating && animationRef.current) {
      const elapsed = (performance.now() - animationRef.current.startTime) / 1000;
      const progress = Math.min(elapsed / animationRef.current.duration, 1);
      animationProgressRef.current = progress;

      for (const { exE, exN, isBest } of rd.exaggeratedTraces) {
        const idx = Math.floor(progress * (exE.length - 1));
        if (idx >= 0 && idx < exE.length) {
          const x = xs(exE[idx]);
          const y = ys(exN[idx]);

          // Glow effect
          ctx.beginPath();
          ctx.arc(x, y, 8, 0, Math.PI * 2);
          ctx.fillStyle = isBest
            ? 'rgba(59, 130, 246, 0.3)' // blue glow
            : 'rgba(249, 115, 22, 0.3)'; // orange glow
          ctx.fill();

          // Solid dot
          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          ctx.fillStyle = isBest ? colors.comparison.reference : colors.comparison.compare;
          ctx.fill();
        }
      }

      if (progress >= 1) {
        setIsAnimating(false);
        animationRef.current = null;
      }
      return;
    }

    // Cursor sync from store
    const cursorDist = useAnalysisStore.getState().cursorDistance;
    if (cursorDist === null) return;

    const cursorIdx = Math.round(cursorDist / SPACING_M);
    if (cursorIdx < rd.zone.startIdx || cursorIdx > rd.zone.endIdx) return;

    const localIdx = cursorIdx - rd.zone.startIdx;

    for (const { trace, exE, exN, isBest } of rd.exaggeratedTraces) {
      if (localIdx >= 0 && localIdx < exE.length) {
        const x = xs(exE[localIdx]);
        const y = ys(exN[localIdx]);

        // Cursor dot
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fillStyle = isBest ? colors.comparison.reference : colors.comparison.compare;
        ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.7)';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Speed tooltip
        const speedIdx = Math.min(cursorIdx, trace.speed_mps.length - 1);
        if (speedIdx >= 0) {
          const speedMph = trace.speed_mps[speedIdx] * MPS_TO_MPH;
          const displaySpeed = convertSpeed(speedMph);
          const tooltipLabel = `${displaySpeed.toFixed(1)} ${speedUnit}`;

          ctx.font = `bold 9px ${fonts.mono}`;
          const tw = ctx.measureText(tooltipLabel).width;
          const tx = Math.min(x + 10, dims.width - tw - 12);
          const ty = Math.max(y - 20, 12);

          ctx.fillStyle = 'rgba(10, 12, 16, 0.9)';
          const pad = 3;
          ctx.fillRect(tx - pad, ty - 8, tw + pad * 2, 14);
          ctx.fillStyle = isBest ? colors.comparison.reference : colors.comparison.compare;
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          ctx.fillText(tooltipLabel, tx, ty - 1);
        }
      }
    }
  });

  // Start animated replay
  const startReplay = useCallback(() => {
    if (!renderData) return;
    // Estimate duration from corner length and average speed
    const zone = renderData.zone;
    const numPoints = zone.endIdx - zone.startIdx;
    const distanceM = numPoints * SPACING_M;
    // ~3 seconds for a typical corner
    const duration = Math.max(2, Math.min(5, distanceM / 30));
    animationRef.current = { startTime: performance.now(), duration };
    animationProgressRef.current = 0;
    setIsAnimating(true);
  }, [renderData]);

  // Fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    const el = wrapperRef.current;
    if (!el) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      el.requestFullscreen().catch(() => {});
    }
  }, []);

  // Export as image
  const exportImage = useCallback(() => {
    const canvas = dataCanvasRef.current;
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `corner-${cornerNumber}-line-map.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  }, [cornerNumber]);

  // Don't render if no line data available
  if (!lineData?.available || !corner || !lineData.lap_traces?.length) return null;
  if (!renderData) return null;

  const touchProps = makeTouchProps(handleOverlayMouseMove, handleOverlayMouseLeave);

  return (
    <div ref={wrapperRef} className="flex flex-col">
      <div ref={containerRef} className="relative h-[200px] w-full">
        <canvas
          ref={dataCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', zIndex: 1 }}
        />
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', zIndex: 2, cursor: 'crosshair' }}
          onMouseMove={handleOverlayMouseMove}
          onMouseLeave={handleOverlayMouseLeave}
          {...touchProps}
        />
      </div>
      {/* Controls row */}
      <div className="flex items-center justify-between gap-1.5 px-2 py-1">
        {/* Left: feature toggles */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setRotateAligned((v) => !v)}
            className={`rounded px-1.5 py-0.5 text-[10px] transition-colors ${
              rotateAligned
                ? 'bg-[var(--bg-elevated)] text-[var(--text-primary)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
            title="Rotate corner so travel direction points upward"
          >
            <svg className="inline-block h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0l-4 4m4-4l4 4" />
            </svg>
          </button>
          <button
            onClick={() => setShowTimeDots((v) => !v)}
            className={`rounded px-1.5 py-0.5 text-[10px] transition-colors ${
              showTimeDots
                ? 'bg-[var(--bg-elevated)] text-[var(--text-primary)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
            title="Show equal-time interval dots (0.25s)"
          >
            <svg className="inline-block h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="6" cy="12" r="2" />
              <circle cx="12" cy="12" r="2" />
              <circle cx="18" cy="12" r="2" />
            </svg>
          </button>
          <button
            onClick={startReplay}
            disabled={isAnimating}
            className={`rounded px-1.5 py-0.5 text-[10px] transition-colors ${
              isAnimating
                ? 'text-[var(--text-muted)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
            title="Animate replay through corner"
          >
            <svg className="inline-block h-3 w-3" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
          </button>
          <button
            onClick={toggleFullscreen}
            className="rounded px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            title="Toggle fullscreen"
          >
            <svg className="inline-block h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" />
            </svg>
          </button>
          <button
            onClick={exportImage}
            className="rounded px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            title="Export as PNG"
          >
            <svg className="inline-block h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
        </div>
        {/* Right: exaggeration slider */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-[var(--text-secondary)]">
            {exaggeration.toFixed(1)}×
          </span>
          <input
            type="range"
            min={EXAG_MIN}
            max={EXAG_MAX}
            step={EXAG_STEP}
            value={exaggeration}
            onChange={(e) => setExaggeration(Number(e.target.value))}
            className="h-1 w-16 cursor-pointer accent-[var(--color-optimal)]"
            aria-label={`Lateral exaggeration: ${exaggeration.toFixed(1)}×`}
          />
          <span className="text-[10px] text-[var(--text-secondary)]">exag</span>
        </div>
      </div>
    </div>
  );
}

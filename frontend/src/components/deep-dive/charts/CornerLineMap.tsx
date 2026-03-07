'use client';

import { useEffect, useMemo, useState } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
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
    // Forward difference tangent (use central difference when possible)
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
    // Normal = rotate tangent 90° CCW: (-dn, de) / len
    ne[i] = -dn / len;
    nn[i] = de / len;
  }
  return { ne, nn };
}

/**
 * Compute signed lateral offset of a trace point from the reference line.
 * Positive = left of reference (in normal direction), negative = right.
 */
function computeLateralOffset(
  traceE: number, traceN: number,
  refE: number, refN: number,
  normalE: number, normalN: number,
): number {
  const de = traceE - refE;
  const dn = traceN - refN;
  return de * normalE + dn * normalN; // dot product with normal
}

/**
 * Apply lateral exaggeration: project point along the reference normal
 * by (exag - 1) × original_offset.
 */
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

  // Label
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
  const [exaggeration, setExaggeration] = useState(1);

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx } =
    useCanvasChart(MARGINS);

  // Find the corner object
  const corner = useMemo(() => corners?.find((c) => c.number === cornerNumber), [corners, cornerNumber]);

  // Find corner line profile (has best lap info)
  const profile: CornerLineProfile | undefined = useMemo(
    () => lineData?.corner_profiles.find((p) => p.corner_number === cornerNumber),
    [lineData, cornerNumber],
  );

  // Compute corner zone, reference normals, exaggerated traces, and bounds
  const renderData = useMemo(() => {
    if (!lineData?.available || !corner || !lineData.lap_traces.length) return null;

    const maxIdx = lineData.distance_m.length - 1;
    const zone = getCornerZone(corner, 15, 25, maxIdx);
    if (zone.endIdx <= zone.startIdx) return null;

    // Compute reference normals for exaggeration
    const normals = computeReferenceNormals(
      lineData.reference_e, lineData.reference_n, zone.startIdx, zone.endIdx,
    );

    // Collect all traces to render (selected laps + best lap)
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

    // Pre-compute exaggerated coordinates for each trace
    const exaggeratedTraces = tracesToRender.map(({ trace, isBest, isSelected }) => {
      const exE: number[] = [];
      const exN: number[] = [];
      for (let i = zone.startIdx; i <= zone.endIdx && i < trace.e.length; i++) {
        if (i < lineData.reference_e.length) {
          const p = exaggeratePoint(
            trace.e[i], trace.n[i],
            lineData.reference_e[i], lineData.reference_n[i],
            normals.ne[i], normals.nn[i],
            exaggeration,
          );
          exE.push(p.e);
          exN.push(p.n);
        }
      }
      return { trace, isBest, isSelected, exE, exN };
    });

    // Track edge coordinates (reference ± half-width, also exaggerated)
    const leftEdgeE: number[] = [];
    const leftEdgeN: number[] = [];
    const rightEdgeE: number[] = [];
    const rightEdgeN: number[] = [];
    for (let i = zone.startIdx; i <= zone.endIdx && i < lineData.reference_e.length; i++) {
      const hw = TRACK_HALF_WIDTH_M * exaggeration;
      leftEdgeE.push(lineData.reference_e[i] + normals.ne[i] * hw);
      leftEdgeN.push(lineData.reference_n[i] + normals.nn[i] * hw);
      rightEdgeE.push(lineData.reference_e[i] - normals.ne[i] * hw);
      rightEdgeN.push(lineData.reference_n[i] - normals.nn[i] * hw);
    }

    // Compute bounds from all exaggerated traces + track edges
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

    // Include track edges in bounds
    for (let j = 0; j < leftEdgeE.length; j++) {
      minE = Math.min(minE, leftEdgeE[j], rightEdgeE[j]);
      maxE = Math.max(maxE, leftEdgeE[j], rightEdgeE[j]);
      minN = Math.min(minN, leftEdgeN[j], rightEdgeN[j]);
      maxN = Math.max(maxN, leftEdgeN[j], rightEdgeN[j]);
    }

    if (!isFinite(minE) || !isFinite(minSpeed)) return null;

    // Add padding (15% of range or minimum 3m)
    const rangeE = maxE - minE || 10;
    const rangeN = maxN - minN || 10;
    const padE = Math.max(rangeE * 0.15, 3);
    const padN = Math.max(rangeN * 0.15, 3);

    return {
      zone,
      normals,
      exaggeratedTraces,
      leftEdge: { e: leftEdgeE, n: leftEdgeN },
      rightEdge: { e: rightEdgeE, n: rightEdgeN },
      bounds: { minE: minE - padE, maxE: maxE + padE, minN: minN - padN, maxN: maxN + padN },
      speedRange: { min: minSpeed, max: maxSpeed },
    };
  }, [lineData, corner, profile, selectedLaps, exaggeration]);

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

  // Draw
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || !renderData || dimensions.innerWidth <= 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    const { zone, exaggeratedTraces, leftEdge, rightEdge, speedRange } = renderData;

    const localColorScale = d3.scaleSequential(d3.interpolatePlasma)
      .domain([speedRange.min, speedRange.max]);

    // Draw track surface (filled polygon: left edge forward, right edge backward)
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

    // Draw track edges
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

    // Draw reference centerline (dashed)
    if (lineData?.reference_e && lineData.reference_n) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      for (let i = zone.startIdx; i <= zone.endIdx && i < lineData.reference_e.length; i++) {
        const x = xScale(lineData.reference_e[i]);
        const y = yScale(lineData.reference_n[i]);
        if (i === zone.startIdx) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw lap traces: best first (behind), then selected (on top)
    const sorted = [...exaggeratedTraces].sort((a, b) => {
      if (a.isBest && !b.isBest) return -1;
      if (!a.isBest && b.isBest) return 1;
      return 0;
    });

    for (const { trace, isBest, exE, exN } of sorted) {
      // Speed array needs to be sliced to match the zone
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

    // Draw entry/apex/exit markers on the primary trace
    const primaryTrace = sorted.find((s) => s.isSelected && !s.isBest) ?? sorted[0];
    if (primaryTrace) {
      const entryDistIdx = Math.max(zone.startIdx, Math.round(corner!.entry_distance_m / SPACING_M));
      const apexDistIdx = zone.apexIdx;
      const exitDistIdx = Math.min(zone.endIdx, Math.round(corner!.exit_distance_m / SPACING_M));

      // Convert distance-domain indices to local array indices
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
  }, [renderData, lineData, xScale, yScale, dimensions, corner, convertSpeed, speedUnit, exaggeration]);

  // Don't render if no line data available
  if (!lineData?.available || !corner || !lineData.lap_traces?.length) return null;
  if (!renderData) return null;

  return (
    <div className="flex flex-col">
      <div ref={containerRef} className="relative h-[200px] w-full">
        <canvas
          ref={dataCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', zIndex: 1 }}
        />
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', zIndex: 2 }}
        />
      </div>
      {/* Lateral exaggeration slider */}
      <div className="flex items-center justify-end gap-1.5 px-2 py-1">
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
          title={`Lateral exaggeration: ${exaggeration.toFixed(1)}×`}
        />
        <span className="text-[10px] text-[var(--text-secondary)]">exag</span>
      </div>
    </div>
  );
}

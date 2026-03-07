'use client';

import { useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useLineAnalysis, useCorners } from '@/hooks/useAnalysis';
import { useUnits } from '@/hooks/useUnits';
import { useAnalysisStore } from '@/stores';
import { colors, fonts } from '@/lib/design-tokens';
import type { Corner, LapSpatialTrace, CornerLineProfile } from '@/lib/types';

const MPS_TO_MPH = 2.23694;
const SPACING_M = 0.7; // distance-domain resampling spacing

const MARGINS = { top: 8, right: 8, bottom: 8, left: 8 };

/** Plasma-inspired colorblind-safe speed scale (purple -> pink -> orange -> yellow) */
const speedColorScale = d3.scaleSequential(d3.interpolatePlasma);

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

function drawSpeedColoredLine(
  ctx: CanvasRenderingContext2D,
  e: number[],
  n: number[],
  speed: number[],
  zone: CornerZone,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  colorScale: d3.ScaleSequential<string>,
  lineWidth: number,
) {
  const { startIdx, endIdx } = zone;
  for (let i = startIdx + 1; i <= endIdx && i < e.length; i++) {
    if (i >= speed.length) break;
    ctx.strokeStyle = colorScale(speed[i]);
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    ctx.moveTo(xScale(e[i - 1]), yScale(n[i - 1]));
    ctx.lineTo(xScale(e[i]), yScale(n[i]));
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

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx } =
    useCanvasChart(MARGINS);

  // Find the corner object
  const corner = useMemo(() => corners?.find((c) => c.number === cornerNumber), [corners, cornerNumber]);

  // Find corner line profile (has best lap info)
  const profile: CornerLineProfile | undefined = useMemo(
    () => lineData?.corner_profiles.find((p) => p.corner_number === cornerNumber),
    [lineData, cornerNumber],
  );

  // Compute corner zone, scales, and data slices
  const renderData = useMemo(() => {
    if (!lineData?.available || !corner || !lineData.lap_traces.length) return null;

    const maxIdx = lineData.distance_m.length - 1;
    const zone = getCornerZone(corner, 30, 50, maxIdx);
    if (zone.endIdx <= zone.startIdx) return null;

    // Collect all traces to render (selected laps + best lap)
    const bestLapNum = profile?.best_lap_number ?? null;
    const tracesToRender: { trace: LapSpatialTrace; isBest: boolean; isSelected: boolean }[] = [];

    // Best lap trace (if available and not already in selected)
    if (bestLapNum !== null) {
      const bestTrace = lineData.lap_traces.find((t) => t.lap_number === bestLapNum);
      if (bestTrace) {
        tracesToRender.push({ trace: bestTrace, isBest: true, isSelected: selectedLaps.includes(bestLapNum) });
      }
    }

    // Selected lap traces
    for (const lapNum of selectedLaps) {
      if (lapNum === bestLapNum) continue; // Already added as best
      const trace = lineData.lap_traces.find((t) => t.lap_number === lapNum);
      if (trace) {
        tracesToRender.push({ trace, isBest: false, isSelected: true });
      }
    }

    if (tracesToRender.length === 0) return null;

    // Compute bounds from all traces in the zone
    let minE = Infinity, maxE = -Infinity, minN = Infinity, maxN = -Infinity;
    let minSpeed = Infinity, maxSpeed = -Infinity;

    for (const { trace } of tracesToRender) {
      for (let i = zone.startIdx; i <= zone.endIdx && i < trace.e.length; i++) {
        minE = Math.min(minE, trace.e[i]);
        maxE = Math.max(maxE, trace.e[i]);
        minN = Math.min(minN, trace.n[i]);
        maxN = Math.max(maxN, trace.n[i]);
        if (i < trace.speed_mps.length) {
          minSpeed = Math.min(minSpeed, trace.speed_mps[i]);
          maxSpeed = Math.max(maxSpeed, trace.speed_mps[i]);
        }
      }
    }

    // Also include reference line in bounds
    for (let i = zone.startIdx; i <= zone.endIdx && i < lineData.reference_e.length; i++) {
      minE = Math.min(minE, lineData.reference_e[i]);
      maxE = Math.max(maxE, lineData.reference_e[i]);
      minN = Math.min(minN, lineData.reference_n[i]);
      maxN = Math.max(maxN, lineData.reference_n[i]);
    }

    if (!isFinite(minE) || !isFinite(minSpeed)) return null;

    // Add padding (20% of range or minimum 5m)
    const rangeE = maxE - minE || 10;
    const rangeN = maxN - minN || 10;
    const padE = Math.max(rangeE * 0.2, 5);
    const padN = Math.max(rangeN * 0.2, 5);

    return {
      zone,
      tracesToRender,
      bounds: { minE: minE - padE, maxE: maxE + padE, minN: minN - padN, maxN: maxN + padN },
      speedRange: { min: minSpeed, max: maxSpeed },
    };
  }, [lineData, corner, profile, selectedLaps]);

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

    // Maintain 1:1 aspect ratio (ENU meters)
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
        .range([MARGINS.top + offsetY + usedH, MARGINS.top + offsetY]), // Y inverted: north = up
    };
  }, [renderData, dimensions.innerWidth, dimensions.innerHeight]);

  // Draw
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || !renderData || dimensions.innerWidth <= 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    const { zone, tracesToRender, speedRange } = renderData;

    // Configure speed color scale
    const localColorScale = d3.scaleSequential(d3.interpolatePlasma)
      .domain([speedRange.min, speedRange.max]);

    // Draw reference centerline (dashed gray)
    if (lineData?.reference_e && lineData.reference_n) {
      ctx.strokeStyle = colors.text.muted;
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
    const sorted = [...tracesToRender].sort((a, b) => {
      if (a.isBest && !b.isBest) return -1; // best drawn first (behind)
      if (!a.isBest && b.isBest) return 1;
      return 0;
    });

    for (const { trace, isBest } of sorted) {
      drawSpeedColoredLine(
        ctx, trace.e, trace.n, trace.speed_mps,
        zone, xScale, yScale, localColorScale,
        isBest && !sorted.every((s) => s.isBest) ? 2 : 3,
      );
    }

    // Draw entry/apex/exit markers on the first selected (or best) trace
    const primaryTrace = sorted.find((s) => s.isSelected && !s.isBest) ?? sorted[0];
    if (primaryTrace) {
      const { trace } = primaryTrace;
      const entryIdx = Math.max(zone.startIdx, Math.round(corner!.entry_distance_m / SPACING_M));
      const apexIdx = zone.apexIdx;
      const exitIdx = Math.min(zone.endIdx, Math.round(corner!.exit_distance_m / SPACING_M));

      if (entryIdx < trace.e.length) {
        drawMarker(ctx, xScale(trace.e[entryIdx]), yScale(trace.n[entryIdx]), 'Entry', colors.text.secondary, 'triangle');
      }
      if (apexIdx < trace.e.length) {
        drawMarker(ctx, xScale(trace.e[apexIdx]), yScale(trace.n[apexIdx]), 'Apex', colors.motorsport.brake, 'diamond');
      }
      if (exitIdx < trace.e.length) {
        drawMarker(ctx, xScale(trace.e[exitIdx]), yScale(trace.n[exitIdx]), 'Exit', colors.motorsport.throttle, 'circle');
      }
    }

    // Speed delta annotations at apex (if we have both best and selected)
    const bestEntry = sorted.find((s) => s.isBest);
    const selEntry = sorted.find((s) => s.isSelected && !s.isBest);
    if (bestEntry && selEntry && corner) {
      const ai = Math.min(zone.apexIdx, bestEntry.trace.speed_mps.length - 1, selEntry.trace.speed_mps.length - 1);
      if (ai >= 0) {
        const bestSpd = bestEntry.trace.speed_mps[ai];
        const selSpd = selEntry.trace.speed_mps[ai];
        const deltaMps = bestSpd - selSpd;
        const deltaDisplay = convertSpeed(deltaMps * MPS_TO_MPH);

        if (Math.abs(deltaDisplay) > 0.1) {
          const apexX = xScale(bestEntry.trace.e[ai]);
          const apexY = yScale(bestEntry.trace.n[ai]);

          // Background pill
          const label = `Best: ${deltaDisplay > 0 ? '+' : ''}${deltaDisplay.toFixed(1)} ${speedUnit}`;
          ctx.font = `bold 10px ${fonts.mono}`;
          const tw = ctx.measureText(label).width;
          const px = Math.min(apexX + 12, MARGINS.left + dimensions.innerWidth - tw - 12);
          const py = Math.max(apexY - 16, MARGINS.top + 14);

          ctx.fillStyle = 'rgba(10, 12, 16, 0.85)';
          ctx.beginPath();
          ctx.roundRect(px - 4, py - 10, tw + 8, 16, 3);
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
      const t = 1 - i / legendH; // top = fast, bottom = slow
      const speed = speedRange.min + t * (speedRange.max - speedRange.min);
      ctx.fillStyle = localColorScale(speed);
      ctx.fillRect(legendX, legendY + i, legendW, 1);
    }

    // Legend labels
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
    for (const { trace, isBest, isSelected } of sorted) {
      const label = isBest
        ? `L${trace.lap_number} (Best)`
        : `L${trace.lap_number}`;
      ctx.fillStyle = isBest ? colors.comparison.reference : colors.comparison.compare;
      ctx.fillRect(MARGINS.left + 4, ly + 2, 10, 2);
      ctx.fillStyle = colors.text.secondary;
      ctx.fillText(label, MARGINS.left + 18, ly - 1);
      ly += 14;
    }
  }, [renderData, lineData, xScale, yScale, dimensions, corner, convertSpeed, speedUnit]);

  // Don't render if no line data available
  if (!lineData?.available || !corner || !lineData.lap_traces?.length) return null;
  if (!renderData) return null;

  return (
    <div ref={containerRef} className="relative h-[180px] w-full">
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
  );
}

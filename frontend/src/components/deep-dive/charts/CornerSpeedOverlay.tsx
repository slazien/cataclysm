'use client';

import { useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAllLapCorners, useMultiLapData, useCorners } from '@/hooks/useAnalysis';
import { useSessionLaps } from '@/hooks/useSession';
import { useAnalysisStore } from '@/stores';
import { colors, fonts } from '@/lib/design-tokens';
import { parseCornerNumber } from '@/lib/cornerUtils';
import { CHART_MARGINS as MARGINS } from './chartHelpers';
import type { Corner } from '@/lib/types';

interface CornerSpeedOverlayProps {
  sessionId: string;
}

/** Draw only grid lines (behind data). */
function drawGrid(
  ctx: CanvasRenderingContext2D,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerWidth: number,
  innerHeight: number,
  margins: typeof MARGINS,
) {
  const yTicks = yScale.ticks(5);
  ctx.strokeStyle = colors.grid;
  ctx.lineWidth = 1;
  for (const tick of yTicks) {
    const y = yScale(tick);
    ctx.beginPath();
    ctx.moveTo(margins.left, y);
    ctx.lineTo(margins.left + innerWidth, y);
    ctx.stroke();
  }
}

/** Draw axis tick labels, axis labels (on top of data). */
function drawLabels(
  ctx: CanvasRenderingContext2D,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerWidth: number,
  innerHeight: number,
  margins: typeof MARGINS,
) {
  ctx.font = `10px ${fonts.mono}`;

  // Y-axis tick labels
  const yTicks = yScale.ticks(5);
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (const tick of yTicks) {
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${tick}`, margins.left - 6, yScale(tick));
  }

  // X-axis tick labels
  const xTicks = xScale.ticks(6);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (const tick of xTicks) {
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${tick}`, xScale(tick), margins.top + innerHeight + 6);
  }

  // Axis labels
  ctx.fillStyle = colors.text.secondary;
  ctx.font = `11px ${fonts.sans}`;
  ctx.textAlign = 'center';
  ctx.fillText('Distance (m)', margins.left + innerWidth / 2, margins.top + innerHeight + 24);

  ctx.save();
  ctx.translate(14, margins.top + innerHeight / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText('Speed (mph)', 0, 0);
  ctx.restore();
}

/** Height fraction for the brake/throttle mini-trace strip. */
const G_STRIP_RATIO = 0.25;

export function CornerSpeedOverlay({ sessionId }: CornerSpeedOverlayProps) {
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);

  const { data: corners } = useCorners(sessionId);
  const { data: laps } = useSessionLaps(sessionId);
  const { data: allLapCorners } = useAllLapCorners(sessionId);

  // Get all clean lap numbers
  const cleanLapNumbers = useMemo(() => {
    if (!laps) return [];
    return laps.filter((l) => l.is_clean).map((l) => l.lap_number);
  }, [laps]);

  const { data: lapDataArr, isLoading } = useMultiLapData(sessionId, cleanLapNumbers);

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx } =
    useCanvasChart(MARGINS);

  // Resolve corner data
  const cornerNumber = selectedCorner ? parseCornerNumber(selectedCorner) : null;
  const corner: Corner | undefined = useMemo(() => {
    if (cornerNumber === null || !corners) return undefined;
    return corners.find((c) => c.number === cornerNumber);
  }, [corners, cornerNumber]);

  // Find the best lap (fastest min speed at this corner)
  const bestLapNumber = useMemo(() => {
    if (!allLapCorners || cornerNumber === null) return null;
    let bestSpeed = -Infinity;
    let bestLap: number | null = null;
    for (const [lapNum, lapCorners] of Object.entries(allLapCorners)) {
      const c = lapCorners.find((lc) => lc.number === cornerNumber);
      if (c && c.min_speed_mph > bestSpeed) {
        bestSpeed = c.min_speed_mph;
        bestLap = parseInt(lapNum, 10);
      }
    }
    return bestLap;
  }, [allLapCorners, cornerNumber]);

  // Comparison lap: the second selected lap if any
  const compLap = selectedLaps.length >= 2 ? selectedLaps[1] : null;

  // Build scales scoped to the corner zone
  // Speed chart gets top ~75%, g-strip gets bottom ~25%
  const { xScale, yScale, gScale, speedAreaHeight, gStripTop, gStripHeight } = useMemo(() => {
    const totalHeight = dimensions.innerHeight;
    const gH = Math.round(totalHeight * G_STRIP_RATIO);
    const speedH = totalHeight - gH;
    const gTop = MARGINS.top + speedH;

    if (!corner || lapDataArr.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.top + 1, MARGINS.top]),
        gScale: d3.scaleLinear().domain([-1, 1]).range([gTop + gH, gTop]),
        speedAreaHeight: speedH,
        gStripTop: gTop,
        gStripHeight: gH,
      };
    }

    const entryDist = corner.entry_distance_m;
    const exitDist = corner.exit_distance_m;
    // Add a 10% margin outside the corner zone
    const span = exitDist - entryDist;
    const xMin = Math.max(0, entryDist - span * 0.1);
    const xMax = exitDist + span * 0.1;

    // Find min/max speed within this range across all laps
    let minSpeed = Infinity;
    let maxSpeed = -Infinity;
    let maxAbsG = 0;
    for (const lap of lapDataArr) {
      for (let i = 0; i < lap.distance_m.length; i++) {
        if (lap.distance_m[i] >= xMin && lap.distance_m[i] <= xMax) {
          if (lap.speed_mph[i] < minSpeed) minSpeed = lap.speed_mph[i];
          if (lap.speed_mph[i] > maxSpeed) maxSpeed = lap.speed_mph[i];
          const absG = Math.abs(lap.longitudinal_g[i]);
          if (absG > maxAbsG) maxAbsG = absG;
        }
      }
    }

    if (!isFinite(minSpeed)) minSpeed = 0;
    if (!isFinite(maxSpeed)) maxSpeed = 100;
    if (maxAbsG === 0) maxAbsG = 0.5;

    const speedPad = (maxSpeed - minSpeed) * 0.08;
    const gBound = maxAbsG * 1.15;

    return {
      xScale: d3
        .scaleLinear()
        .domain([xMin, xMax])
        .range([MARGINS.left, MARGINS.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([Math.max(0, minSpeed - speedPad), maxSpeed + speedPad])
        .range([MARGINS.top + speedH, MARGINS.top]),
      gScale: d3
        .scaleLinear()
        .domain([-gBound, gBound])
        .range([gTop + gH, gTop]),
      speedAreaHeight: speedH,
      gStripTop: gTop,
      gStripHeight: gH,
    };
  }, [corner, lapDataArr, dimensions.innerWidth, dimensions.innerHeight]);

  // Draw
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0 || !corner || lapDataArr.length === 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    // --- 1. Grid lines (behind data) ---
    drawGrid(ctx, xScale, yScale, dimensions.innerWidth, speedAreaHeight, MARGINS);

    // Corner zone shading
    const entryX = xScale(corner.entry_distance_m);
    const apexX = xScale(corner.apex_distance_m);
    const exitX = xScale(corner.exit_distance_m);

    ctx.fillStyle = 'rgba(255, 255, 255, 0.03)';
    ctx.fillRect(entryX, MARGINS.top, exitX - entryX, dimensions.innerHeight);

    // Vertical markers: entry, apex, exit
    const markers = [
      { x: entryX, label: 'Entry', style: 'rgba(255,255,255,0.2)' },
      { x: apexX, label: 'Apex', style: colors.motorsport.optimal },
      { x: exitX, label: 'Exit', style: 'rgba(255,255,255,0.2)' },
    ];
    for (const m of markers) {
      ctx.strokeStyle = m.style;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(m.x, MARGINS.top);
      ctx.lineTo(m.x, MARGINS.top + dimensions.innerHeight);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // --- 2. Data: speed traces ---
    // All clean laps — thin, semi-transparent
    for (let li = 0; li < lapDataArr.length; li++) {
      const lap = lapDataArr[li];
      const isBest = lap.lap_number === bestLapNumber;
      const isComp = lap.lap_number === compLap;

      // Skip best/comp — draw them separately on top
      if (isBest || isComp) continue;

      ctx.strokeStyle = `${colors.lap[li % colors.lap.length]}40`; // ~25% opacity
      ctx.lineWidth = 1;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < lap.distance_m.length; i++) {
        const x = xScale(lap.distance_m[i]);
        const y = yScale(lap.speed_mph[i]);
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }

    // Comparison lap — dashed
    if (compLap !== null) {
      const compData = lapDataArr.find((l) => l.lap_number === compLap);
      if (compData) {
        ctx.strokeStyle = colors.lap[1 % colors.lap.length];
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < compData.distance_m.length; i++) {
          const x = xScale(compData.distance_m[i]);
          const y = yScale(compData.speed_mph[i]);
          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }

    // Best lap — thick, solid, purple
    const bestData = bestLapNumber !== null
      ? lapDataArr.find((l) => l.lap_number === bestLapNumber)
      : undefined;

    if (bestData) {
      ctx.strokeStyle = colors.motorsport.pb;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < bestData.distance_m.length; i++) {
        const x = xScale(bestData.distance_m[i]);
        const y = yScale(bestData.speed_mph[i]);
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }

    // --- 3. Brake/throttle mini-trace strip (best lap only) ---
    // Separator line between speed chart and g-strip
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(MARGINS.left, gStripTop);
    ctx.lineTo(MARGINS.left + dimensions.innerWidth, gStripTop);
    ctx.stroke();

    // Draw brake/throttle fill for the best lap (or first available)
    const gLap = bestData ?? lapDataArr[0];
    if (gLap && gStripHeight > 0) {
      const zeroY = gScale(0);

      // Clip to the strip area
      ctx.save();
      ctx.beginPath();
      ctx.rect(MARGINS.left, gStripTop, dimensions.innerWidth, gStripHeight);
      ctx.clip();

      // Fill segments colored by sign of longitudinal_g
      for (let i = 1; i < gLap.distance_m.length; i++) {
        const x0 = xScale(gLap.distance_m[i - 1]);
        const x1 = xScale(gLap.distance_m[i]);
        const y0 = gScale(gLap.longitudinal_g[i - 1]);
        const y1 = gScale(gLap.longitudinal_g[i]);
        const avgG = (gLap.longitudinal_g[i - 1] + gLap.longitudinal_g[i]) / 2;

        ctx.fillStyle = avgG < 0
          ? 'rgba(239, 68, 68, 0.35)' // braking — red
          : 'rgba(34, 197, 94, 0.35)'; // throttle — green

        ctx.beginPath();
        ctx.moveTo(x0, zeroY);
        ctx.lineTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.lineTo(x1, zeroY);
        ctx.closePath();
        ctx.fill();
      }

      // Zero line in the g-strip
      ctx.strokeStyle = colors.axis;
      ctx.lineWidth = 0.5;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(MARGINS.left, zeroY);
      ctx.lineTo(MARGINS.left + dimensions.innerWidth, zeroY);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.restore();

      // Label for g-strip
      ctx.fillStyle = colors.text.muted;
      ctx.font = `9px ${fonts.sans}`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText('Long. G', MARGINS.left + 4, gStripTop + 3);
    }

    // --- 4. Axis tick labels and axis labels (on top) ---
    drawLabels(ctx, xScale, yScale, dimensions.innerWidth, speedAreaHeight, MARGINS);

    // Entry/apex/exit marker labels
    for (const m of markers) {
      ctx.fillStyle = m.style;
      ctx.font = `9px ${fonts.sans}`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.fillText(m.label, m.x, MARGINS.top - 2);
    }

    // --- 5. Legend ---
    const legendY = MARGINS.top + 8;
    const legendX = MARGINS.left + 8;
    ctx.font = `10px ${fonts.sans}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    // Best lap label
    ctx.fillStyle = colors.motorsport.pb;
    ctx.fillRect(legendX, legendY, 14, 2);
    ctx.fillText(
      bestLapNumber !== null ? `Best (L${bestLapNumber})` : 'Best',
      legendX + 18,
      legendY - 4,
    );

    // Comp lap label
    if (compLap !== null) {
      ctx.fillStyle = colors.lap[1 % colors.lap.length];
      ctx.setLineDash([4, 3]);
      ctx.strokeStyle = colors.lap[1 % colors.lap.length];
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(legendX, legendY + 16);
      ctx.lineTo(legendX + 14, legendY + 16);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillText(`Comp (L${compLap})`, legendX + 18, legendY + 12);
    }
  }, [
    lapDataArr,
    corner,
    bestLapNumber,
    compLap,
    xScale,
    yScale,
    gScale,
    speedAreaHeight,
    gStripTop,
    gStripHeight,
    dimensions,
    getDataCtx,
  ]);

  if (!selectedCorner || cornerNumber === null) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">Select a corner to view speed overlay</p>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
      <h3 className="absolute left-3 top-2 z-10 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
        Corner Speed Overlay — Turn {cornerNumber}
      </h3>
      <div ref={containerRef} className="h-full w-full">
        <canvas
          ref={dataCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%' }}
        />
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%' }}
        />
      </div>
      {isLoading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-[var(--bg-surface)]/80">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--cata-accent)] border-t-transparent" />
        </div>
      )}
    </div>
  );
}

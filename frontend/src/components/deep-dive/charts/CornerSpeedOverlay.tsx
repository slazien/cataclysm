'use client';

import { useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAllLapCorners, useMultiLapData, useCorners } from '@/hooks/useAnalysis';
import { useSessionLaps } from '@/hooks/useSession';
import { useAnalysisStore } from '@/stores';
import { colors, fonts } from '@/lib/design-tokens';
import { CHART_MARGINS as MARGINS } from './chartHelpers';
import type { Corner } from '@/lib/types';

interface CornerSpeedOverlayProps {
  sessionId: string;
}

function parseCornerNumber(cornerId: string): number | null {
  const match = cornerId.match(/T(\d+)/i);
  return match ? parseInt(match[1], 10) : null;
}

function drawAxes(
  ctx: CanvasRenderingContext2D,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerWidth: number,
  innerHeight: number,
  margins: typeof MARGINS,
) {
  ctx.strokeStyle = colors.axis;
  ctx.lineWidth = 1;
  ctx.fillStyle = colors.axis;
  ctx.font = `10px ${fonts.mono}`;

  // Y-axis ticks
  const yTicks = yScale.ticks(5);
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (const tick of yTicks) {
    const y = yScale(tick);
    ctx.strokeStyle = colors.grid;
    ctx.beginPath();
    ctx.moveTo(margins.left, y);
    ctx.lineTo(margins.left + innerWidth, y);
    ctx.stroke();
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${tick}`, margins.left - 6, y);
  }

  // X-axis ticks
  const xTicks = xScale.ticks(6);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (const tick of xTicks) {
    const x = xScale(tick);
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${tick}`, x, margins.top + innerHeight + 6);
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
  const { xScale, yScale } = useMemo(() => {
    if (!corner || lapDataArr.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.top + 1, MARGINS.top]),
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
    for (const lap of lapDataArr) {
      for (let i = 0; i < lap.distance_m.length; i++) {
        if (lap.distance_m[i] >= xMin && lap.distance_m[i] <= xMax) {
          if (lap.speed_mph[i] < minSpeed) minSpeed = lap.speed_mph[i];
          if (lap.speed_mph[i] > maxSpeed) maxSpeed = lap.speed_mph[i];
        }
      }
    }

    if (!isFinite(minSpeed)) minSpeed = 0;
    if (!isFinite(maxSpeed)) maxSpeed = 100;

    const speedPad = (maxSpeed - minSpeed) * 0.08;

    return {
      xScale: d3
        .scaleLinear()
        .domain([xMin, xMax])
        .range([MARGINS.left, MARGINS.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([Math.max(0, minSpeed - speedPad), maxSpeed + speedPad])
        .range([MARGINS.top + dimensions.innerHeight, MARGINS.top]),
    };
  }, [corner, lapDataArr, dimensions.innerWidth, dimensions.innerHeight]);

  // Draw
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0 || !corner || lapDataArr.length === 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    const entryX = xScale(corner.entry_distance_m);
    const apexX = xScale(corner.apex_distance_m);
    const exitX = xScale(corner.exit_distance_m);

    // Corner zone shading
    ctx.fillStyle = 'rgba(255, 255, 255, 0.03)';
    ctx.fillRect(
      entryX,
      MARGINS.top,
      exitX - entryX,
      dimensions.innerHeight,
    );

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

      // Label
      ctx.fillStyle = m.style;
      ctx.font = `9px ${fonts.sans}`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.fillText(m.label, m.x, MARGINS.top - 2);
    }

    // Draw all clean laps — thin, semi-transparent
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

    // Draw comparison lap — dashed
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

    // Draw best lap — thick, solid, purple
    if (bestLapNumber !== null) {
      const bestData = lapDataArr.find((l) => l.lap_number === bestLapNumber);
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
    }

    // Axes
    drawAxes(ctx, xScale, yScale, dimensions.innerWidth, dimensions.innerHeight, MARGINS);

    // Legend
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

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--cata-accent)] border-t-transparent" />
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
    </div>
  );
}

'use client';

import { useCallback, useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAllLapCorners } from '@/hooks/useAnalysis';
import { useUnits } from '@/hooks/useUnits';
import { useAnalysisStore } from '@/stores';
import { colors, fonts } from '@/lib/design-tokens';
import { parseCornerNumber } from '@/lib/cornerUtils';
import { InfoTooltip } from '@/components/shared/InfoTooltip';
import { getChartMargins } from './chartHelpers';
import type { ChartMargins } from '@/hooks/useCanvasChart';

interface PedalConsistencyProps {
  sessionId: string;
}

interface BrakePoint {
  lapNumber: number;
  brakePointM: number;
}

/** Draw only grid lines (behind data). */
function drawGrid(
  ctx: CanvasRenderingContext2D,
  yScale: d3.ScaleLinear<number, number>,
  innerWidth: number,
  margins: ChartMargins,
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

/** Draw axis tick labels and axis labels (on top of data). */
function drawLabels(
  ctx: CanvasRenderingContext2D,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerWidth: number,
  innerHeight: number,
  margins: ChartMargins,
  convertDist: (m: number) => number,
  distUnit: string,
) {
  ctx.font = `10px ${fonts.mono}`;

  // Y-axis tick labels
  const yTicks = yScale.ticks(5);
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (const tick of yTicks) {
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${convertDist(tick).toFixed(0)}`, margins.left - 6, yScale(tick));
  }

  // X-axis tick labels
  const xTicks = xScale.ticks(Math.min(10, xScale.domain()[1] - xScale.domain()[0]));
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (const tick of xTicks) {
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${Math.round(tick)}`, xScale(tick), margins.top + innerHeight + 6);
  }

  // Axis labels
  ctx.fillStyle = colors.text.secondary;
  ctx.font = `11px ${fonts.sans}`;
  ctx.textAlign = 'center';
  ctx.fillText('Lap Number', margins.left + innerWidth / 2, margins.top + innerHeight + 24);

  ctx.save();
  ctx.translate(14, margins.top + innerHeight / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText(`Brake Point (${distUnit})`, 0, 0);
  ctx.restore();
}

export function PedalConsistency({ sessionId }: PedalConsistencyProps) {
  const selectedCorner = useAnalysisStore((s) => s.selectedCorner);
  const hoveredPedalPoint = useAnalysisStore((s) => s.hoveredPedalPoint);
  const setHoveredPedalPoint = useAnalysisStore((s) => s.setHoveredPedalPoint);
  const { data: allLapCorners } = useAllLapCorners(sessionId);
  const { convertDistance, distanceUnit } = useUnits();

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx, makeTouchProps } =
    useCanvasChart(getChartMargins);

  const cornerNumber = selectedCorner ? parseCornerNumber(selectedCorner) : null;

  // Extract brake points for the selected corner across all laps
  const brakePoints: BrakePoint[] = useMemo(() => {
    if (cornerNumber === null || !allLapCorners) return [];
    const points: BrakePoint[] = [];
    for (const [lapNum, lapCorners] of Object.entries(allLapCorners)) {
      const c = lapCorners.find((lc) => lc.number === cornerNumber);
      if (c && c.brake_point_m !== null) {
        points.push({
          lapNumber: parseInt(lapNum, 10),
          brakePointM: c.brake_point_m,
        });
      }
    }
    points.sort((a, b) => a.lapNumber - b.lapNumber);
    return points;
  }, [allLapCorners, cornerNumber]);

  // Stats
  const { mean, stdDev } = useMemo(() => {
    if (brakePoints.length === 0) return { mean: 0, stdDev: 0 };
    const values = brakePoints.map((p) => p.brakePointM);
    const m = d3.mean(values) ?? 0;
    const sd = d3.deviation(values) ?? 0;
    return { mean: m, stdDev: sd };
  }, [brakePoints]);

  // Build scales
  const { xScale, yScale } = useMemo(() => {
    if (brakePoints.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([dimensions.margins.left, dimensions.margins.left + 1]),
        yScale: d3.scaleLinear().domain([0, 1]).range([dimensions.margins.top + 1, dimensions.margins.top]),
      };
    }

    const lapNums = brakePoints.map((p) => p.lapNumber);
    const bpValues = brakePoints.map((p) => p.brakePointM);
    const minLap = d3.min(lapNums) ?? 0;
    const maxLap = d3.max(lapNums) ?? 1;
    const minBp = d3.min(bpValues) ?? 0;
    const maxBp = d3.max(bpValues) ?? 1;
    const bpPad = (maxBp - minBp) * 0.15 || 5;

    return {
      xScale: d3
        .scaleLinear()
        .domain([minLap - 0.5, maxLap + 0.5])
        .range([dimensions.margins.left, dimensions.margins.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([minBp - bpPad, maxBp + bpPad])
        .range([dimensions.margins.top + dimensions.innerHeight, dimensions.margins.top]),
    };
  }, [brakePoints, dimensions.innerWidth, dimensions.innerHeight, dimensions.margins]);

  // Draw
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0 || brakePoints.length === 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    // --- 1. Grid lines (behind data) ---
    drawGrid(ctx, yScale, dimensions.innerWidth, dimensions.margins);

    // --- 2. Data ---
    // Standard deviation band
    if (stdDev > 0) {
      const bandTop = yScale(mean + stdDev);
      const bandBottom = yScale(mean - stdDev);
      ctx.fillStyle = 'rgba(168, 85, 247, 0.08)'; // purple-ish to match PB color
      ctx.fillRect(
        dimensions.margins.left,
        bandTop,
        dimensions.innerWidth,
        bandBottom - bandTop,
      );
    }

    // Mean reference line (dashed)
    const meanY = yScale(mean);
    ctx.strokeStyle = colors.motorsport.pb;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(dimensions.margins.left, meanY);
    ctx.lineTo(dimensions.margins.left + dimensions.innerWidth, meanY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Mean label
    ctx.fillStyle = colors.motorsport.pb;
    ctx.font = `10px ${fonts.mono}`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'bottom';
    ctx.fillText(`avg: ${convertDistance(mean).toFixed(0)}${distanceUnit}`, dimensions.margins.left + dimensions.innerWidth - 4, meanY - 3);

    // Dots
    for (let i = 0; i < brakePoints.length; i++) {
      const bp = brakePoints[i];
      const x = xScale(bp.lapNumber);
      const y = yScale(bp.brakePointM);
      const color = colors.lap[i % colors.lap.length];

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, 2 * Math.PI);
      ctx.fill();

      // Subtle border
      ctx.strokeStyle = 'rgba(255,255,255,0.15)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Lap number label below dot
      ctx.fillStyle = colors.text.muted;
      ctx.font = `9px ${fonts.mono}`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(`L${bp.lapNumber}`, x, y + 8);
    }

    // --- 3. Axis labels (on top of data) ---
    drawLabels(ctx, xScale, yScale, dimensions.innerWidth, dimensions.innerHeight, dimensions.margins, convertDistance, distanceUnit);

    // Std dev annotation
    if (stdDev > 0) {
      ctx.fillStyle = colors.text.muted;
      ctx.font = `9px ${fonts.sans}`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText(
        `std dev: ${convertDistance(stdDev).toFixed(1)}${distanceUnit}`,
        dimensions.margins.left + 4,
        dimensions.margins.top + 4,
      );
    }
  }, [brakePoints, mean, stdDev, xScale, yScale, dimensions, getDataCtx, convertDistance, distanceUnit]);

  // --- Hover handler: find nearest dot, highlight, set cross-chart state ---
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = overlayCanvasRef.current;
      if (!canvas || brakePoints.length === 0) return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      // Find nearest brake point within 15px threshold
      let nearest: BrakePoint | null = null;
      let nearestDist = Infinity;
      for (const bp of brakePoints) {
        const px = xScale(bp.lapNumber);
        const py = yScale(bp.brakePointM);
        const d = Math.hypot(mx - px, my - py);
        if (d < nearestDist) {
          nearestDist = d;
          nearest = bp;
        }
      }

      const ctx = getOverlayCtx();
      if (!ctx) return;
      ctx.clearRect(0, 0, dimensions.width, dimensions.height);

      if (nearest && nearestDist < 15) {
        // Draw highlight ring
        const hx = xScale(nearest.lapNumber);
        const hy = yScale(nearest.brakePointM);
        ctx.strokeStyle = colors.text.primary;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(hx, hy, 8, 0, 2 * Math.PI);
        ctx.stroke();

        // Tooltip
        ctx.fillStyle = 'rgba(0,0,0,0.85)';
        const label = `L${nearest.lapNumber}: ${convertDistance(nearest.brakePointM).toFixed(0)}${distanceUnit}`;
        ctx.font = `11px ${fonts.mono}`;
        const tw = ctx.measureText(label).width;
        const tx = Math.min(hx + 12, dimensions.width - tw - 8);
        const ty = Math.max(hy - 24, dimensions.margins.top);
        ctx.fillRect(tx - 4, ty - 2, tw + 8, 18);
        ctx.fillStyle = colors.text.primary;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText(label, tx, ty);

        setHoveredPedalPoint({ lapNumber: nearest.lapNumber, distanceM: nearest.brakePointM, type: 'brake' });
      } else {
        setHoveredPedalPoint(null);
      }
    },
    [brakePoints, xScale, yScale, dimensions, getOverlayCtx, setHoveredPedalPoint, convertDistance, distanceUnit, overlayCanvasRef],
  );

  const handleMouseLeave = useCallback(() => {
    const ctx = getOverlayCtx();
    if (ctx) ctx.clearRect(0, 0, dimensions.width, dimensions.height);
    setHoveredPedalPoint(null);
  }, [getOverlayCtx, dimensions, setHoveredPedalPoint]);

  // External hover sync: highlight dot when hoveredPedalPoint is set from another chart (e.g. satellite map)
  useEffect(() => {
    const ctx = getOverlayCtx();
    if (!ctx || dimensions.innerWidth <= 0) return;

    // Only draw if there's a hovered lap and the overlay isn't already drawn by mouse
    if (!hoveredPedalPoint || hoveredPedalPoint.type !== 'brake') return;

    const bp = brakePoints.find((p) => p.lapNumber === hoveredPedalPoint.lapNumber);
    if (!bp) return;

    const hx = xScale(bp.lapNumber);
    const hy = yScale(bp.brakePointM);

    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    // Highlight ring
    ctx.strokeStyle = colors.text.primary;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(hx, hy, 8, 0, 2 * Math.PI);
    ctx.stroke();

    // Tooltip
    ctx.fillStyle = 'rgba(0,0,0,0.85)';
    const label = `L${bp.lapNumber}: ${convertDistance(bp.brakePointM).toFixed(0)}${distanceUnit}`;
    ctx.font = `11px ${fonts.mono}`;
    const tw = ctx.measureText(label).width;
    const tx = Math.min(hx + 12, dimensions.width - tw - 8);
    const ty = Math.max(hy - 24, dimensions.margins.top);
    ctx.fillRect(tx - 4, ty - 2, tw + 8, 18);
    ctx.fillStyle = colors.text.primary;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(label, tx, ty);
  }, [hoveredPedalPoint, brakePoints, xScale, yScale, dimensions, getOverlayCtx, convertDistance, distanceUnit]);

  if (!selectedCorner || cornerNumber === null) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">
          Select a corner to view brake consistency
        </p>
      </div>
    );
  }

  if (brakePoints.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-secondary)]">
          No brake point data for Turn {cornerNumber}
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
      <div className="pointer-events-none absolute left-3 top-1 z-10 flex items-center gap-1.5">
        <h3 className="rounded bg-[var(--bg-surface)]/80 px-1 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Turn {cornerNumber} Braking
        </h3>
        <InfoTooltip helpKey="chart.brake-consistency" className="pointer-events-auto" />
      </div>
      <div ref={containerRef} className="h-full w-full">
        <canvas
          ref={dataCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', zIndex: 1 }}
        />
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', cursor: 'crosshair', zIndex: 2, pointerEvents: 'auto' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          {...makeTouchProps(handleMouseMove, handleMouseLeave)}
        />
      </div>
    </div>
  );
}

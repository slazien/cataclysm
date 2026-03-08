'use client';

import { useCallback, useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { motion } from 'motion/react';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useAnimationFrame } from '@/hooks/useAnimationFrame';
import { useLineAnalysis, useCorners } from '@/hooks/useAnalysis';
import { useUnits } from '@/hooks/useUnits';
import { useAnalysisStore } from '@/stores';
import { CircularProgress } from '@/components/shared/CircularProgress';
import { colors, fonts } from '@/lib/design-tokens';
import { getChartMargins, drawCornerZones } from './chartHelpers';
import type { ChartMargins } from '@/hooks/useCanvasChart';

interface LateralOffsetChartProps {
  sessionId: string;
}

function drawAxes(
  ctx: CanvasRenderingContext2D,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  innerWidth: number,
  innerHeight: number,
  margins: ChartMargins,
  distLabel: string,
  convertDist: (m: number) => number,
  distUnit: string,
) {
  ctx.strokeStyle = colors.axis;
  ctx.lineWidth = 1;
  ctx.fillStyle = colors.axis;
  ctx.font = `10px ${fonts.mono}`;

  // Y-axis ticks
  const yTicks = yScale.ticks(6);
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
    ctx.fillText(`${convertDist(tick).toFixed(1)}`, margins.left - 6, y);
  }

  // X-axis ticks
  const xTicks = xScale.ticks(8);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (const tick of xTicks) {
    const x = xScale(tick);
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${Math.round(convertDist(tick))}`, x, margins.top + innerHeight + 6);
  }

  // Axis labels
  ctx.fillStyle = colors.text.secondary;
  ctx.font = `11px ${fonts.sans}`;
  ctx.textAlign = 'center';
  ctx.fillText(distLabel, margins.left + innerWidth / 2, margins.top + innerHeight + 24);

  ctx.save();
  ctx.translate(14, margins.top + innerHeight / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText(`Lateral Offset (${distUnit})`, 0, 0);
  ctx.restore();
}

export function LateralOffsetChart({ sessionId }: LateralOffsetChartProps) {
  const selectedLaps = useAnalysisStore((s) => s.selectedLaps);
  const { data: lineData, isLoading } = useLineAnalysis(sessionId, selectedLaps);
  const { data: corners } = useCorners(sessionId);
  const { convertDistance, distanceUnit } = useUnits();

  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx, makeTouchProps } =
    useCanvasChart(getChartMargins);

  // Build scales
  const { xScale, yScale } = useMemo(() => {
    if (!lineData?.available || lineData.traces.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([dimensions.margins.left, dimensions.margins.left + 1]),
        yScale: d3.scaleLinear().domain([-1, 1]).range([dimensions.margins.top + 1, dimensions.margins.top]),
      };
    }

    const maxDist = d3.max(lineData.distance_m) ?? 1;

    // Compute y-domain from all offset traces, symmetric around 0
    let maxAbs = 1;
    for (const trace of lineData.traces) {
      const traceMax = d3.max(trace.offsets_m, (d) => Math.abs(d));
      if (traceMax !== undefined && traceMax > maxAbs) maxAbs = traceMax;
    }
    const yPad = Math.ceil(maxAbs * 1.15 * 2) / 2; // Round up to nearest 0.5m

    return {
      xScale: d3
        .scaleLinear()
        .domain([0, maxDist])
        .range([dimensions.margins.left, dimensions.margins.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([-yPad, yPad])
        .range([dimensions.margins.top + dimensions.innerHeight, dimensions.margins.top]),
    };
  }, [lineData, dimensions.innerWidth, dimensions.innerHeight, dimensions.margins]);

  // Stable refs for RAF
  const xScaleRef = useRef(xScale);
  xScaleRef.current = xScale;
  const dimsRef = useRef(dimensions);
  dimsRef.current = dimensions;

  // Draw data layer
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0 || !lineData?.available) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    // Corner zones
    if (corners) {
      drawCornerZones(ctx, corners, xScale, dimensions.margins.top, dimensions.innerHeight);
    }

    // Zero-line (reference = driving on the reference line)
    const zeroY = yScale(0);
    ctx.strokeStyle = colors.text.muted;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(dimensions.margins.left, zeroY);
    ctx.lineTo(dimensions.margins.left + dimensions.innerWidth, zeroY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Lateral offset traces per lap
    const traces = lineData.traces;
    for (let li = 0; li < traces.length; li++) {
      const trace = traces[li];
      const color =
        traces.length === 2
          ? li === 0
            ? colors.comparison.reference
            : colors.comparison.compare
          : colors.lap[li % colors.lap.length];
      ctx.strokeStyle = color;
      ctx.lineWidth = traces.length === 2 ? (li === 0 ? 2 : 1.5) : 1.5;
      ctx.beginPath();
      const len = Math.min(trace.offsets_m.length, lineData.distance_m.length);
      for (let i = 0; i < len; i++) {
        const x = xScale(lineData.distance_m[i]);
        const y = yScale(trace.offsets_m[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Axes
    drawAxes(ctx, xScale, yScale, dimensions.innerWidth, dimensions.innerHeight, dimensions.margins, `Distance (${distanceUnit})`, convertDistance, distanceUnit);
  }, [lineData, corners, xScale, yScale, dimensions, distanceUnit, convertDistance]);

  // Mouse handlers
  const handleOverlayMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const scale = xScaleRef.current;
    const [xMin, xMax] = scale.range();
    if (x >= xMin && x <= xMax) {
      useAnalysisStore.getState().setCursorDistance(scale.invert(x));
    }
  }, []);

  const handleOverlayMouseLeave = useCallback(() => {
    useAnalysisStore.getState().setCursorDistance(null);
  }, []);

  // Cursor overlay via RAF
  useAnimationFrame(() => {
    const ctx = getOverlayCtx();
    if (!ctx || !lineData?.available) return;
    const dims = dimsRef.current;
    ctx.clearRect(0, 0, dims.width, dims.height);

    const cursorDist = useAnalysisStore.getState().cursorDistance;
    if (cursorDist === null) return;

    const x = xScaleRef.current(cursorDist);
    const dm = dims.margins;
    if (x < dm.left || x > dm.left + dims.innerWidth) return;

    // Vertical cursor line
    ctx.strokeStyle = colors.cursor;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x, dm.top);
    ctx.lineTo(x, dm.top + dims.innerHeight);
    ctx.stroke();

    // Tooltip: show offset values at cursor
    const traces = lineData.traces;
    if (traces.length > 0) {
      const tooltipY = dm.top + 8;
      ctx.font = `11px ${fonts.mono}`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';

      for (let li = 0; li < traces.length; li++) {
        const trace = traces[li];
        const idx = d3.bisectLeft(lineData.distance_m, cursorDist);
        const clampedIdx = Math.min(idx, trace.offsets_m.length - 1);
        const offset = trace.offsets_m[clampedIdx];
        const color =
          traces.length === 2
            ? li === 0
              ? colors.comparison.reference
              : colors.comparison.compare
            : colors.lap[li % colors.lap.length];
        const sign = offset >= 0 ? '+' : '';
        const label = `L${trace.lap_number}: ${sign}${convertDistance(offset).toFixed(2)}${distanceUnit}`;

        const textWidth = ctx.measureText(label).width;
        const rightEdge = dm.left + dims.innerWidth;
        const tooltipX = x + textWidth + 20 > rightEdge ? x - textWidth - 16 : x + 10;

        ctx.fillStyle = 'rgba(10, 12, 16, 0.85)';
        ctx.fillRect(tooltipX - 2, tooltipY + li * 18 - 2, textWidth + 8, 16);
        ctx.fillStyle = color;
        ctx.fillText(label, tooltipX + 2, tooltipY + li * 18);
      }
    }
  });

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <CircularProgress size={20} />
      </div>
    );
  }

  if (!lineData?.available) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">
          Line analysis requires GPS grade A/B and 3+ laps
        </p>
      </div>
    );
  }

  if (selectedLaps.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[var(--text-secondary)]">Select laps to view driving line</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <motion.div
        initial={{ clipPath: 'inset(0 100% 0 0)' }}
        animate={{ clipPath: 'inset(0 0% 0 0)' }}
        transition={{ duration: 0.5, ease: 'easeOut', delay: 0.2 }}
        className="absolute inset-0"
      >
        <canvas
          ref={dataCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', zIndex: 1 }}
        />
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0"
          onMouseMove={handleOverlayMouseMove}
          onMouseLeave={handleOverlayMouseLeave}
          {...makeTouchProps(handleOverlayMouseMove, handleOverlayMouseLeave)}
          style={{ width: '100%', height: '100%', cursor: 'crosshair', zIndex: 2, pointerEvents: 'auto' }}
        />
      </motion.div>
    </div>
  );
}

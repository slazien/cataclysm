'use client';

import { useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useUnits } from '@/hooks/useUnits';
import { colors, fonts } from '@/lib/design-tokens';

const MARGINS = { top: 16, right: 16, bottom: 36, left: 56 };
const MARGINS_MOBILE = { top: 12, right: 8, bottom: 28, left: 40 };
const getCompMargins = (isMobile: boolean) => (isMobile ? MARGINS_MOBILE : MARGINS);

interface SpeedTraceOverlayProps {
  traceA: { distance_m: number[]; speed_mph: number[] };
  traceB: { distance_m: number[]; speed_mph: number[] };
  labelA: string;
  labelB: string;
  height?: number;
}

export function SpeedTraceOverlay({
  traceA,
  traceB,
  labelA,
  labelB,
  height = 256,
}: SpeedTraceOverlayProps) {
  const { convertSpeed, convertDistance, speedUnit, distanceUnit } = useUnits();
  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx } =
    useCanvasChart(getCompMargins);

  const { xScale, yScale } = useMemo(() => {
    if (dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([dimensions.margins.left, dimensions.margins.left + 1]),
        yScale: d3.scaleLinear().domain([0, 1]).range([dimensions.margins.top + 1, dimensions.margins.top]),
      };
    }

    const maxDist = Math.max(
      d3.max(traceA.distance_m) ?? 1,
      d3.max(traceB.distance_m) ?? 1,
    );
    const maxSpeed = Math.max(
      d3.max(traceA.speed_mph) ?? 100,
      d3.max(traceB.speed_mph) ?? 100,
    );

    return {
      xScale: d3
        .scaleLinear()
        .domain([0, maxDist])
        .range([dimensions.margins.left, dimensions.margins.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([0, maxSpeed * 1.1])
        .range([dimensions.margins.top + dimensions.innerHeight, dimensions.margins.top]),
    };
  }, [traceA, traceB, dimensions.innerWidth, dimensions.innerHeight]);

  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0) return;

    const { width, height: h } = dimensions;
    ctx.clearRect(0, 0, width, h);

    // Draw trace helper
    function drawTrace(
      context: CanvasRenderingContext2D,
      distArr: number[],
      speedArr: number[],
      color: string,
    ) {
      context.strokeStyle = color;
      context.lineWidth = 1.5;
      context.beginPath();
      for (let i = 0; i < distArr.length; i++) {
        const x = xScale(distArr[i]);
        const y = yScale(speedArr[i]);
        if (i === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      }
      context.stroke();
    }

    // Y-axis gridlines + tick labels (drawn BEFORE traces so lines appear behind)
    const yTicks = yScale.ticks(6);
    ctx.font = `10px ${fonts.mono}`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (const tick of yTicks) {
      const y = yScale(tick);
      ctx.strokeStyle = colors.grid;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(dimensions.margins.left, y);
      ctx.lineTo(dimensions.margins.left + dimensions.innerWidth, y);
      ctx.stroke();
      ctx.fillStyle = colors.axis;
      ctx.fillText(`${Math.round(convertSpeed(tick))}`, dimensions.margins.left - 6, y);
    }

    // Draw reference trace (A) — on top of gridlines
    drawTrace(ctx, traceA.distance_m, traceA.speed_mph, colors.comparison.reference);
    // Draw compare trace (B)
    drawTrace(ctx, traceB.distance_m, traceB.speed_mph, colors.comparison.compare);

    // X-axis ticks
    const xTicks = xScale.ticks(8);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (const tick of xTicks) {
      ctx.fillStyle = colors.axis;
      ctx.fillText(`${Math.round(convertDistance(tick))}`, xScale(tick), dimensions.margins.top + dimensions.innerHeight + 6);
    }

    // Axis labels
    ctx.fillStyle = colors.text.secondary;
    ctx.font = `11px ${fonts.sans}`;
    ctx.textAlign = 'center';
    ctx.fillText(
      `Distance (${distanceUnit})`,
      dimensions.margins.left + dimensions.innerWidth / 2,
      dimensions.margins.top + dimensions.innerHeight + 24,
    );

    ctx.save();
    ctx.translate(14, dimensions.margins.top + dimensions.innerHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText(`Speed (${speedUnit})`, 0, 0);
    ctx.restore();
  }, [traceA, traceB, xScale, yScale, dimensions, getDataCtx, convertSpeed, convertDistance, speedUnit, distanceUnit]);

  return (
    <div className="flex flex-col gap-2">
      <div ref={containerRef} className="relative w-full" style={{ height }}>
        <canvas
          ref={dataCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', zIndex: 1 }}
        />
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0"
          style={{ width: '100%', height: '100%', cursor: 'crosshair', zIndex: 2, pointerEvents: 'auto' }}
        />
      </div>
      {/* Legend */}
      <div className="flex items-center justify-center gap-6 text-xs text-[var(--text-secondary)]">
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-0.5 w-4 rounded"
            style={{ backgroundColor: colors.comparison.reference }}
          />
          <span>{labelA}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-0.5 w-4 rounded"
            style={{ backgroundColor: colors.comparison.compare }}
          />
          <span>{labelB}</span>
        </div>
      </div>
    </div>
  );
}

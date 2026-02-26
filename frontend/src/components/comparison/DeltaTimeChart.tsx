'use client';

import { useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { colors, fonts } from '@/lib/design-tokens';

const MARGINS = { top: 16, right: 16, bottom: 36, left: 56 };

interface DeltaTimeChartProps {
  distance_m: number[];
  delta_time_s: number[];
  totalDelta: number;
}

export function DeltaTimeChart({ distance_m, delta_time_s, totalDelta }: DeltaTimeChartProps) {
  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx } =
    useCanvasChart(MARGINS);

  const { xScale, yScale } = useMemo(() => {
    if (distance_m.length === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([-1, 1]).range([MARGINS.top + 1, MARGINS.top]),
      };
    }

    const maxDist = d3.max(distance_m) ?? 1;
    const maxAbs = d3.max(delta_time_s.map((v) => Math.abs(v))) ?? 1;
    const bound = Math.max(maxAbs * 1.2, 0.1);

    return {
      xScale: d3
        .scaleLinear()
        .domain([0, maxDist])
        .range([MARGINS.left, MARGINS.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([-bound, bound])
        .range([MARGINS.top + dimensions.innerHeight, MARGINS.top]),
    };
  }, [distance_m, delta_time_s, dimensions.innerWidth, dimensions.innerHeight]);

  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || distance_m.length === 0 || dimensions.innerWidth <= 0) return;

    const { width, height } = dimensions;
    ctx.clearRect(0, 0, width, height);

    const zeroY = yScale(0);

    // Draw filled areas
    for (let i = 1; i < distance_m.length; i++) {
      const x0 = xScale(distance_m[i - 1]);
      const x1 = xScale(distance_m[i]);
      const y0 = yScale(delta_time_s[i - 1]);
      const y1 = yScale(delta_time_s[i]);

      const deltaVal = (delta_time_s[i - 1] + delta_time_s[i]) / 2;

      ctx.fillStyle =
        deltaVal > 0
          ? 'rgba(239, 68, 68, 0.35)' // red -- session A slower
          : 'rgba(34, 197, 94, 0.35)'; // green -- session A faster

      ctx.beginPath();
      ctx.moveTo(x0, zeroY);
      ctx.lineTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.lineTo(x1, zeroY);
      ctx.closePath();
      ctx.fill();
    }

    // Delta line
    ctx.strokeStyle = colors.text.primary;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < distance_m.length; i++) {
      const x = xScale(distance_m[i]);
      const y = yScale(delta_time_s[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Zero line
    ctx.strokeStyle = colors.axis;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(MARGINS.left, zeroY);
    ctx.lineTo(MARGINS.left + dimensions.innerWidth, zeroY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Y-axis ticks
    const yTicks = yScale.ticks(5);
    ctx.font = `10px ${fonts.mono}`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (const tick of yTicks) {
      const y = yScale(tick);
      ctx.strokeStyle = colors.grid;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(MARGINS.left, y);
      ctx.lineTo(MARGINS.left + dimensions.innerWidth, y);
      ctx.stroke();
      ctx.fillStyle = colors.axis;
      ctx.fillText(tick.toFixed(2), MARGINS.left - 6, y);
    }

    // X-axis ticks
    const xTicks = xScale.ticks(8);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (const tick of xTicks) {
      ctx.fillStyle = colors.axis;
      ctx.fillText(`${tick}`, xScale(tick), MARGINS.top + dimensions.innerHeight + 6);
    }

    // Axis labels
    ctx.fillStyle = colors.text.secondary;
    ctx.font = `11px ${fonts.sans}`;
    ctx.textAlign = 'center';
    ctx.fillText(
      'Distance (m)',
      MARGINS.left + dimensions.innerWidth / 2,
      MARGINS.top + dimensions.innerHeight + 24,
    );

    ctx.save();
    ctx.translate(14, MARGINS.top + dimensions.innerHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText('Delta (s)', 0, 0);
    ctx.restore();

    // Total delta in top-right
    const totalStr = `${totalDelta >= 0 ? '+' : ''}${totalDelta.toFixed(3)}s`;
    ctx.font = `bold 12px ${fonts.mono}`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'top';
    ctx.fillStyle =
      totalDelta > 0 ? colors.motorsport.brake : colors.motorsport.throttle;
    ctx.fillText(totalStr, MARGINS.left + dimensions.innerWidth - 4, MARGINS.top + 4);
  }, [distance_m, delta_time_s, totalDelta, xScale, yScale, dimensions, getDataCtx]);

  return (
    <div ref={containerRef} className="relative h-full w-full">
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
  );
}

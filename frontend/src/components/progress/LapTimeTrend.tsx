'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { colors, fonts } from '@/lib/design-tokens';
import { formatTimeShort } from '@/lib/formatters';
import type { TrendSessionSummary } from '@/lib/types';
import { drawTrendAxes } from './progressChartHelpers';

interface LapTimeTrendProps {
  sessions: TrendSessionSummary[];
  bestLapTrend: number[];
  top3AvgTrend: number[];
  theoreticalTrend: number[];
  className?: string;
}

const MARGINS = { top: 20, right: 20, bottom: 44, left: 64 };

function drawLine(
  ctx: CanvasRenderingContext2D,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  data: number[],
  color: string,
  lineWidth: number,
  dashed = false,
) {
  if (data.length === 0) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  if (dashed) ctx.setLineDash([6, 4]);
  else ctx.setLineDash([]);

  ctx.beginPath();
  let started = false;
  for (let i = 0; i < data.length; i++) {
    if (data[i] == null || data[i] <= 0) continue;
    const x = xScale(i);
    const y = yScale(data[i]);
    if (!started) {
      ctx.moveTo(x, y);
      started = true;
    } else {
      ctx.lineTo(x, y);
    }
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // Dots
  ctx.fillStyle = color;
  for (let i = 0; i < data.length; i++) {
    if (data[i] == null || data[i] <= 0) continue;
    ctx.beginPath();
    ctx.arc(xScale(i), yScale(data[i]), 3, 0, Math.PI * 2);
    ctx.fill();
  }
}

export function LapTimeTrend({
  sessions,
  bestLapTrend,
  top3AvgTrend,
  theoreticalTrend,
  className,
}: LapTimeTrendProps) {
  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx } =
    useCanvasChart(MARGINS);

  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const { xScale, yScale } = useMemo(() => {
    const n = sessions.length;
    if (n === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.top + 1, MARGINS.top]),
      };
    }

    const allValues = [...bestLapTrend, ...top3AvgTrend, ...theoreticalTrend].filter(
      (v) => v != null && v > 0,
    );
    const minVal = d3.min(allValues) ?? 0;
    const maxVal = d3.max(allValues) ?? 1;
    const padding = (maxVal - minVal) * 0.1 || 1;

    return {
      xScale: d3
        .scaleLinear()
        .domain([0, n - 1])
        .range([MARGINS.left, MARGINS.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([maxVal + padding, minVal - padding])
        .range([MARGINS.top, MARGINS.top + dimensions.innerHeight]),
    };
  }, [sessions.length, bestLapTrend, top3AvgTrend, theoreticalTrend, dimensions.innerWidth, dimensions.innerHeight]);

  const xScaleRef = useRef(xScale);
  xScaleRef.current = xScale;

  // Draw data layer
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0 || sessions.length === 0) return;

    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    drawTrendAxes({
      ctx,
      xScale,
      yScale,
      sessions,
      innerWidth: dimensions.innerWidth,
      innerHeight: dimensions.innerHeight,
      margins: MARGINS,
      yLabel: 'Lap Time',
      formatYTick: formatTimeShort,
      yTickCount: 6,
    });
    drawLine(ctx, xScale, yScale, theoreticalTrend, colors.motorsport.pb, 1.5, true);
    drawLine(ctx, xScale, yScale, top3AvgTrend, colors.motorsport.neutral, 2);
    drawLine(ctx, xScale, yScale, bestLapTrend, colors.motorsport.optimal, 2);

    // Legend
    const legendX = MARGINS.left + 8;
    const legendY = MARGINS.top + 8;
    ctx.font = `10px ${fonts.sans}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';

    const items = [
      { label: 'Best Lap', color: colors.motorsport.optimal, dashed: false },
      { label: 'Top 3 Avg', color: colors.motorsport.neutral, dashed: false },
      { label: 'Theoretical', color: colors.motorsport.pb, dashed: true },
    ];

    for (let i = 0; i < items.length; i++) {
      const y = legendY + i * 16;
      ctx.strokeStyle = items[i].color;
      ctx.lineWidth = 2;
      if (items[i].dashed) ctx.setLineDash([4, 3]);
      else ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(legendX, y);
      ctx.lineTo(legendX + 20, y);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = colors.text.secondary;
      ctx.fillText(items[i].label, legendX + 26, y);
    }
  }, [sessions, bestLapTrend, top3AvgTrend, theoreticalTrend, xScale, yScale, dimensions, getDataCtx]);

  // Hover overlay
  useEffect(() => {
    const overlay = overlayCanvasRef.current;
    if (!overlay) return;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = overlay.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      if (mouseX < MARGINS.left || mouseX > MARGINS.left + dimensions.innerWidth) {
        setHoveredIdx(null);
        return;
      }
      const scale = xScaleRef.current;
      const idx = Math.round(scale.invert(mouseX));
      if (idx >= 0 && idx < sessions.length) {
        setHoveredIdx(idx);
      } else {
        setHoveredIdx(null);
      }
    };

    const handleMouseLeave = () => setHoveredIdx(null);

    overlay.addEventListener('mousemove', handleMouseMove);
    overlay.addEventListener('mouseleave', handleMouseLeave);
    return () => {
      overlay.removeEventListener('mousemove', handleMouseMove);
      overlay.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [sessions.length, dimensions.innerWidth]);

  // Draw hover overlay
  useEffect(() => {
    const ctx = getOverlayCtx();
    if (!ctx) return;
    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    if (hoveredIdx === null || hoveredIdx < 0 || hoveredIdx >= sessions.length) return;

    const x = xScale(hoveredIdx);

    // Vertical line
    ctx.strokeStyle = colors.cursor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, MARGINS.top);
    ctx.lineTo(x, MARGINS.top + dimensions.innerHeight);
    ctx.stroke();

    // Tooltip
    const lines = [
      `Best: ${formatTimeShort(bestLapTrend[hoveredIdx])}`,
      `Top 3: ${formatTimeShort(top3AvgTrend[hoveredIdx])}`,
      theoreticalTrend[hoveredIdx] > 0 ? `Optimal: ${formatTimeShort(theoreticalTrend[hoveredIdx])}` : '',
    ].filter(Boolean);

    ctx.font = `11px ${fonts.mono}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    const lineHeight = 16;
    const tooltipWidth = 140;
    const tooltipHeight = lines.length * lineHeight + 8;
    const tooltipX = x + tooltipWidth + 16 > MARGINS.left + dimensions.innerWidth ? x - tooltipWidth - 8 : x + 8;
    const tooltipY = MARGINS.top + 4;

    ctx.fillStyle = 'rgba(10, 12, 16, 0.9)';
    ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);

    const tooltipColors = [colors.motorsport.optimal, colors.motorsport.neutral, colors.motorsport.pb];
    for (let i = 0; i < lines.length; i++) {
      ctx.fillStyle = tooltipColors[i] ?? colors.text.primary;
      ctx.fillText(lines[i], tooltipX + 6, tooltipY + 4 + i * lineHeight);
    }
  }, [hoveredIdx, sessions, bestLapTrend, top3AvgTrend, theoreticalTrend, xScale, dimensions, getOverlayCtx]);

  if (sessions.length === 0) {
    return (
      <div className={`flex h-full items-center justify-center ${className ?? ''}`}>
        <p className="text-sm text-[var(--text-muted)]">No trend data available</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`relative h-full w-full ${className ?? ''}`}>
      <canvas
        ref={dataCanvasRef}
        className="absolute inset-0"
        style={{ width: '100%', height: '100%' }}
      />
      <canvas
        ref={overlayCanvasRef}
        className="absolute inset-0"
        style={{ width: '100%', height: '100%', cursor: 'crosshair' }}
      />
    </div>
  );
}

'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { colors, fonts } from '@/lib/design-tokens';
import type { TrendSessionSummary } from '@/lib/types';

interface ConsistencyTrendProps {
  sessions: TrendSessionSummary[];
  consistencyTrend: number[];
  className?: string;
}

const MARGINS = { top: 20, right: 20, bottom: 44, left: 64 };

function drawAxes(
  ctx: CanvasRenderingContext2D,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  sessions: TrendSessionSummary[],
  innerWidth: number,
  innerHeight: number,
) {
  ctx.strokeStyle = colors.axis;
  ctx.fillStyle = colors.axis;
  ctx.font = `10px ${fonts.mono}`;

  // Y-axis ticks
  const yTicks = yScale.ticks(5);
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (const tick of yTicks) {
    const y = yScale(tick);
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(MARGINS.left, y);
    ctx.lineTo(MARGINS.left + innerWidth, y);
    ctx.stroke();
    ctx.fillStyle = colors.axis;
    ctx.fillText(`${tick}`, MARGINS.left - 6, y);
  }

  // X-axis labels
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (let i = 0; i < sessions.length; i++) {
    const x = xScale(i);
    ctx.fillStyle = colors.axis;
    const dateLabel = new Date(sessions[i].session_date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
    ctx.fillText(dateLabel, x, MARGINS.top + innerHeight + 6);
  }

  // Axis labels
  ctx.fillStyle = colors.text.secondary;
  ctx.font = `11px ${fonts.sans}`;
  ctx.textAlign = 'center';
  ctx.fillText('Session', MARGINS.left + innerWidth / 2, MARGINS.top + innerHeight + 28);

  ctx.save();
  ctx.translate(14, MARGINS.top + innerHeight / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText('Consistency (0-100)', 0, 0);
  ctx.restore();
}

export function ConsistencyTrend({ sessions, consistencyTrend, className }: ConsistencyTrendProps) {
  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx } =
    useCanvasChart(MARGINS);

  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const { xScale, yScale } = useMemo(() => {
    const n = sessions.length;
    if (n === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([0, 100]).range([MARGINS.top + 1, MARGINS.top]),
      };
    }

    return {
      xScale: d3
        .scaleLinear()
        .domain([0, n - 1])
        .range([MARGINS.left, MARGINS.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([0, 100])
        .range([MARGINS.top + dimensions.innerHeight, MARGINS.top]),
    };
  }, [sessions.length, dimensions.innerWidth, dimensions.innerHeight]);

  const xScaleRef = useRef(xScale);
  xScaleRef.current = xScale;

  // Draw data
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0 || sessions.length === 0) return;

    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    drawAxes(ctx, xScale, yScale, sessions, dimensions.innerWidth, dimensions.innerHeight);

    // Fill area under line
    if (consistencyTrend.length > 1) {
      ctx.fillStyle = `${colors.motorsport.optimal}15`;
      ctx.beginPath();
      ctx.moveTo(xScale(0), yScale(0));
      for (let i = 0; i < consistencyTrend.length; i++) {
        ctx.lineTo(xScale(i), yScale(consistencyTrend[i] ?? 0));
      }
      ctx.lineTo(xScale(consistencyTrend.length - 1), yScale(0));
      ctx.closePath();
      ctx.fill();
    }

    // Line
    ctx.strokeStyle = colors.motorsport.optimal;
    ctx.lineWidth = 2;
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < consistencyTrend.length; i++) {
      const val = consistencyTrend[i];
      if (val == null) continue;
      const x = xScale(i);
      const y = yScale(val);
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    // Dots
    ctx.fillStyle = colors.motorsport.optimal;
    for (let i = 0; i < consistencyTrend.length; i++) {
      if (consistencyTrend[i] == null) continue;
      ctx.beginPath();
      ctx.arc(xScale(i), yScale(consistencyTrend[i]), 3.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [sessions, consistencyTrend, xScale, yScale, dimensions, getDataCtx]);

  // Mouse events
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
      const idx = Math.round(xScaleRef.current.invert(mouseX));
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

  // Hover overlay
  useEffect(() => {
    const ctx = getOverlayCtx();
    if (!ctx) return;
    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    if (hoveredIdx === null || hoveredIdx < 0 || hoveredIdx >= sessions.length) return;

    const x = xScale(hoveredIdx);

    ctx.strokeStyle = colors.cursor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, MARGINS.top);
    ctx.lineTo(x, MARGINS.top + dimensions.innerHeight);
    ctx.stroke();

    // Tooltip
    const val = consistencyTrend[hoveredIdx];
    if (val == null) return;

    ctx.font = `11px ${fonts.mono}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    const label = `Score: ${val.toFixed(1)}`;
    const textWidth = ctx.measureText(label).width;
    const tooltipX = x + textWidth + 20 > MARGINS.left + dimensions.innerWidth ? x - textWidth - 16 : x + 8;
    const tooltipY = MARGINS.top + 4;

    ctx.fillStyle = 'rgba(10, 12, 16, 0.9)';
    ctx.fillRect(tooltipX, tooltipY, textWidth + 12, 22);

    ctx.fillStyle = colors.motorsport.optimal;
    ctx.fillText(label, tooltipX + 6, tooltipY + 5);
  }, [hoveredIdx, consistencyTrend, sessions, xScale, dimensions, getOverlayCtx]);

  if (sessions.length === 0) {
    return (
      <div className={`flex h-full items-center justify-center ${className ?? ''}`}>
        <p className="text-sm text-[var(--text-muted)]">No consistency data available</p>
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

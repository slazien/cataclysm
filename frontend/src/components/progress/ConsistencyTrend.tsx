'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { motion } from 'motion/react';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { colors, fonts } from '@/lib/design-tokens';
import type { TrendSessionSummary } from '@/lib/types';
import { drawTrendAxes } from './progressChartHelpers';

/** Draw a small diamond + label at (x, y). */
function drawPbLegendEntry(ctx: CanvasRenderingContext2D, x: number, y: number) {
  ctx.save();
  ctx.translate(x + 10, y);
  ctx.rotate(Math.PI / 4);
  ctx.fillStyle = colors.accent.primary;
  ctx.fillRect(-3, -3, 6, 6);
  ctx.strokeStyle = colors.accent.primaryHover;
  ctx.lineWidth = 1;
  ctx.strokeRect(-3, -3, 6, 6);
  ctx.restore();

  ctx.fillStyle = colors.text.secondary;
  ctx.font = `10px ${fonts.sans}`;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText('PB Session', x + 26, y);
}

interface ConsistencyTrendProps {
  sessions: TrendSessionSummary[];
  consistencyTrend: number[];
  pbIndices?: Set<number>;
  className?: string;
}

const MARGINS = { top: 20, right: 20, bottom: 44, left: 64 };

export function ConsistencyTrend({ sessions, consistencyTrend, pbIndices, className }: ConsistencyTrendProps) {
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

    drawTrendAxes({
      ctx,
      xScale,
      yScale,
      sessions,
      innerWidth: dimensions.innerWidth,
      innerHeight: dimensions.innerHeight,
      margins: MARGINS,
      yLabel: 'Consistency (0-100)',
    });

    // Fill area under line with gradient
    if (consistencyTrend.length > 1) {
      const chartBottom = MARGINS.top + dimensions.innerHeight;
      const gradient = ctx.createLinearGradient(0, MARGINS.top, 0, chartBottom);
      gradient.addColorStop(0, 'rgba(59, 130, 246, 0.15)');
      gradient.addColorStop(1, 'rgba(59, 130, 246, 0)');
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.moveTo(xScale(0), chartBottom);
      for (let i = 0; i < consistencyTrend.length; i++) {
        ctx.lineTo(xScale(i), yScale(consistencyTrend[i] ?? 0));
      }
      ctx.lineTo(xScale(consistencyTrend.length - 1), chartBottom);
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
      const dotVal = consistencyTrend[i];
      if (dotVal == null) continue;
      ctx.beginPath();
      ctx.arc(xScale(i), yScale(dotVal), 3.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // PB diamonds on the consistency line
    if (pbIndices && pbIndices.size > 0) {
      for (const i of pbIndices) {
        if (i >= consistencyTrend.length || consistencyTrend[i] == null) continue;
        const px = xScale(i);
        const py = yScale(consistencyTrend[i]);
        ctx.save();
        ctx.translate(px, py);
        ctx.rotate(Math.PI / 4);
        ctx.fillStyle = colors.accent.primary;
        ctx.fillRect(-4, -4, 8, 8);
        ctx.strokeStyle = colors.accent.primaryHover;
        ctx.lineWidth = 1;
        ctx.strokeRect(-4, -4, 8, 8);
        ctx.restore();
      }
      // Legend entry
      drawPbLegendEntry(ctx, MARGINS.left + 8, MARGINS.top + 8);
    }
  }, [sessions, consistencyTrend, pbIndices, xScale, yScale, dimensions, getDataCtx]);

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

    const isPb = pbIndices?.has(hoveredIdx) ?? false;
    const label = isPb ? `Score: ${val.toFixed(1)}  ◆ PB` : `Score: ${val.toFixed(1)}`;
    const textWidth = ctx.measureText(label).width;
    const tooltipX = x + textWidth + 20 > MARGINS.left + dimensions.innerWidth ? x - textWidth - 16 : x + 8;
    const tooltipY = MARGINS.top + 4;

    // Tooltip card with rounded corners and subtle border
    const tw = textWidth + 12;
    const th = 22;
    ctx.fillStyle = 'rgba(10, 12, 16, 0.92)';
    ctx.beginPath();
    ctx.roundRect(tooltipX, tooltipY, tw, th, 6);
    ctx.fill();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.roundRect(tooltipX, tooltipY, tw, th, 6);
    ctx.stroke();

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
          style={{ width: '100%', height: '100%', cursor: 'crosshair', zIndex: 2, pointerEvents: 'auto' }}
        />
      </motion.div>
    </div>
  );
}

'use client';

import { useEffect, useMemo, useState, useRef } from 'react';
import * as d3 from 'd3';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { colors, fonts } from '@/lib/design-tokens';
import type { TrendSessionSummary } from '@/lib/types';

interface SessionBoxPlotProps {
  sessions: TrendSessionSummary[];
  className?: string;
}

const MARGINS = { top: 20, right: 20, bottom: 44, left: 64 };

interface BoxStats {
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
}

function computeBoxStats(values: number[]): BoxStats | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return {
    min: sorted[0],
    q1: d3.quantile(sorted, 0.25) ?? sorted[0],
    median: d3.quantile(sorted, 0.5) ?? sorted[0],
    q3: d3.quantile(sorted, 0.75) ?? sorted[0],
    max: sorted[sorted.length - 1],
  };
}

function formatTime(seconds: number): string {
  const min = Math.floor(seconds / 60);
  const sec = seconds % 60;
  return min > 0 ? `${min}:${sec.toFixed(1).padStart(4, '0')}` : `${sec.toFixed(2)}s`;
}

export function SessionBoxPlot({ sessions, className }: SessionBoxPlotProps) {
  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx } =
    useCanvasChart(MARGINS);

  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  // Compute box stats for each session
  const boxData = useMemo(
    () => sessions.map((s) => computeBoxStats(s.lap_times_s)),
    [sessions],
  );

  const n = sessions.length;

  // Scales
  const { xScale, yScale, boxWidth } = useMemo(() => {
    if (n === 0 || dimensions.innerWidth <= 0) {
      return {
        xScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.left, MARGINS.left + 1]),
        yScale: d3.scaleLinear().domain([0, 1]).range([MARGINS.top + 1, MARGINS.top]),
        boxWidth: 0,
      };
    }

    const allValues: number[] = [];
    for (const stats of boxData) {
      if (stats) {
        allValues.push(stats.min, stats.max);
      }
    }
    const minVal = d3.min(allValues) ?? 0;
    const maxVal = d3.max(allValues) ?? 1;
    const padding = (maxVal - minVal) * 0.1 || 1;

    const bw = Math.min(40, (dimensions.innerWidth / n) * 0.6);

    return {
      xScale: d3
        .scaleLinear()
        .domain([-0.5, n - 0.5])
        .range([MARGINS.left, MARGINS.left + dimensions.innerWidth]),
      yScale: d3
        .scaleLinear()
        .domain([maxVal + padding, minVal - padding])
        .range([MARGINS.top, MARGINS.top + dimensions.innerHeight]),
      boxWidth: bw,
    };
  }, [n, boxData, dimensions.innerWidth, dimensions.innerHeight]);

  const xScaleRef = useRef(xScale);
  xScaleRef.current = xScale;

  // Draw
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || dimensions.innerWidth <= 0 || n === 0) return;

    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    // Grid lines
    const yTicks = yScale.ticks(6);
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
      ctx.font = `10px ${fonts.mono}`;
      ctx.fillText(formatTime(tick), MARGINS.left - 6, y);
    }

    // X-axis labels
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (let i = 0; i < n; i++) {
      const x = xScale(i);
      ctx.fillStyle = colors.axis;
      ctx.font = `10px ${fonts.mono}`;
      const dateLabel = new Date(sessions[i].session_date).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
      ctx.fillText(dateLabel, x, MARGINS.top + dimensions.innerHeight + 6);
    }

    // Axis labels
    ctx.fillStyle = colors.text.secondary;
    ctx.font = `11px ${fonts.sans}`;
    ctx.textAlign = 'center';
    ctx.fillText(
      'Session',
      MARGINS.left + dimensions.innerWidth / 2,
      MARGINS.top + dimensions.innerHeight + 28,
    );

    ctx.save();
    ctx.translate(14, MARGINS.top + dimensions.innerHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = 'center';
    ctx.fillText('Lap Time', 0, 0);
    ctx.restore();

    // Draw boxes
    for (let i = 0; i < n; i++) {
      const stats = boxData[i];
      if (!stats) continue;

      const cx = xScale(i);
      const halfBox = boxWidth / 2;

      const yMin = yScale(stats.min);
      const yQ1 = yScale(stats.q1);
      const yMedian = yScale(stats.median);
      const yQ3 = yScale(stats.q3);
      const yMax = yScale(stats.max);

      // Whisker: min to Q1
      ctx.strokeStyle = colors.text.muted;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx, yMin);
      ctx.lineTo(cx, yQ1);
      ctx.stroke();

      // Whisker: Q3 to max
      ctx.beginPath();
      ctx.moveTo(cx, yQ3);
      ctx.lineTo(cx, yMax);
      ctx.stroke();

      // Whisker caps
      ctx.beginPath();
      ctx.moveTo(cx - halfBox * 0.4, yMin);
      ctx.lineTo(cx + halfBox * 0.4, yMin);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(cx - halfBox * 0.4, yMax);
      ctx.lineTo(cx + halfBox * 0.4, yMax);
      ctx.stroke();

      // Box
      ctx.fillStyle = `${colors.motorsport.optimal}30`;
      ctx.fillRect(cx - halfBox, yQ3, boxWidth, yQ1 - yQ3);
      ctx.strokeStyle = colors.motorsport.optimal;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(cx - halfBox, yQ3, boxWidth, yQ1 - yQ3);

      // Median line
      ctx.strokeStyle = colors.text.primary;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(cx - halfBox, yMedian);
      ctx.lineTo(cx + halfBox, yMedian);
      ctx.stroke();
    }
  }, [sessions, boxData, xScale, yScale, boxWidth, n, dimensions, getDataCtx]);

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
      if (idx >= 0 && idx < n) {
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
  }, [n, dimensions.innerWidth]);

  // Hover overlay
  useEffect(() => {
    const ctx = getOverlayCtx();
    if (!ctx) return;
    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    if (hoveredIdx === null || hoveredIdx < 0 || hoveredIdx >= n) return;

    const stats = boxData[hoveredIdx];
    if (!stats) return;

    const x = xScale(hoveredIdx);

    // Highlight line
    ctx.strokeStyle = colors.cursor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, MARGINS.top);
    ctx.lineTo(x, MARGINS.top + dimensions.innerHeight);
    ctx.stroke();

    // Tooltip
    const lines = [
      `Max: ${formatTime(stats.max)}`,
      `Q3:  ${formatTime(stats.q3)}`,
      `Med: ${formatTime(stats.median)}`,
      `Q1:  ${formatTime(stats.q1)}`,
      `Min: ${formatTime(stats.min)}`,
    ];

    ctx.font = `11px ${fonts.mono}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    const lineHeight = 16;
    const tooltipWidth = 130;
    const tooltipHeight = lines.length * lineHeight + 8;
    const tooltipX =
      x + tooltipWidth + 16 > MARGINS.left + dimensions.innerWidth
        ? x - tooltipWidth - 8
        : x + 8;
    const tooltipY = MARGINS.top + 4;

    ctx.fillStyle = 'rgba(10, 12, 16, 0.9)';
    ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);

    for (let i = 0; i < lines.length; i++) {
      ctx.fillStyle = colors.text.secondary;
      ctx.fillText(lines[i], tooltipX + 6, tooltipY + 4 + i * lineHeight);
    }
  }, [hoveredIdx, boxData, xScale, n, dimensions, getOverlayCtx]);

  if (n === 0) {
    return (
      <div className={`flex h-full items-center justify-center ${className ?? ''}`}>
        <p className="text-sm text-[var(--text-muted)]">No session data available</p>
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

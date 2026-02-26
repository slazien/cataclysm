'use client';

import { useEffect, useCallback, useState } from 'react';
import { useSessionLaps } from '@/hooks/useSession';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { formatLapTime } from '@/lib/formatters';
import { colors, fonts } from '@/lib/design-tokens';
import type { LapSummary } from '@/lib/types';

interface LapTimesBarProps {
  sessionId: string;
}

const MARGINS = { top: 32, right: 16, bottom: 36, left: 56 };
const CHART_HEIGHT = 220;
const BAR_PADDING = 0.25;

function getBarColor(lap: LapSummary, bestTime: number): string {
  if (lap.lap_time_s === bestTime) return colors.motorsport.pb;
  if (lap.is_clean) return colors.motorsport.optimal;
  return colors.text.muted;
}

export function LapTimesBar({ sessionId }: LapTimesBarProps) {
  const { containerRef, dataCanvasRef, overlayCanvasRef, dimensions, getDataCtx, getOverlayCtx } =
    useCanvasChart(MARGINS);
  const { data: laps, isLoading } = useSessionLaps(sessionId);
  const { data: report } = useCoachingReport(sessionId);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const renderChart = useCallback(() => {
    const ctx = getDataCtx();
    if (!ctx || !laps || laps.length === 0) return;

    const { width, innerWidth, innerHeight, margins } = dimensions;
    if (innerWidth <= 0 || innerHeight <= 0) return;

    // Clear entire canvas
    ctx.clearRect(0, 0, width, dimensions.height);

    const sortedLaps = [...laps].sort((a, b) => a.lap_number - b.lap_number);
    const lapTimes = sortedLaps.map((l) => l.lap_time_s);
    const bestTime = Math.min(...lapTimes);
    const avgTime = lapTimes.reduce((a, b) => a + b, 0) / lapTimes.length;

    const yMin = Math.min(...lapTimes) - 2;
    const yMax = Math.max(...lapTimes) + 1;

    // Scale functions
    const barTotalWidth = innerWidth / sortedLaps.length;
    const barWidth = barTotalWidth * (1 - BAR_PADDING);
    const barGap = barTotalWidth * BAR_PADDING;

    const xScale = (index: number) => margins.left + index * barTotalWidth + barGap / 2;
    const yScale = (value: number) =>
      margins.top + ((yMax - value) / (yMax - yMin)) * innerHeight;

    // AI annotation text above chart
    if (report?.summary) {
      ctx.save();
      ctx.font = `11px ${fonts.sans}`;
      ctx.fillStyle = colors.ai.icon;
      ctx.globalAlpha = 0.8;
      const maxWidth = innerWidth;
      const truncated =
        report.summary.length > 120
          ? report.summary.slice(0, 117) + '...'
          : report.summary;
      ctx.fillText(truncated, margins.left, margins.top - 10, maxWidth);
      ctx.restore();
    }

    // Grid lines
    const yTickCount = 5;
    const yStep = (yMax - yMin) / yTickCount;
    ctx.save();
    ctx.strokeStyle = colors.grid;
    ctx.setLineDash([2, 4]);
    ctx.lineWidth = 1;
    for (let i = 0; i <= yTickCount; i++) {
      const val = yMin + i * yStep;
      const y = yScale(val);
      ctx.beginPath();
      ctx.moveTo(margins.left, y);
      ctx.lineTo(margins.left + innerWidth, y);
      ctx.stroke();
    }
    ctx.restore();

    // Bars
    ctx.save();
    ctx.globalAlpha = 0.85;
    for (let i = 0; i < sortedLaps.length; i++) {
      const lap = sortedLaps[i];
      const x = xScale(i);
      const y = yScale(lap.lap_time_s);
      const h = yScale(yMin) - y;

      ctx.fillStyle = getBarColor(lap, bestTime);

      // Draw rounded-top bar
      const r = Math.min(2, barWidth / 2);
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + barWidth, y, x + barWidth, y + h, r);
      ctx.lineTo(x + barWidth, y + h);
      ctx.lineTo(x, y + h);
      ctx.arcTo(x, y, x + r, y, r);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();

    // Best lap reference line
    ctx.save();
    ctx.strokeStyle = colors.motorsport.pb;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 4]);
    const bestY = yScale(bestTime);
    ctx.beginPath();
    ctx.moveTo(margins.left, bestY);
    ctx.lineTo(margins.left + innerWidth, bestY);
    ctx.stroke();
    ctx.restore();

    // Best lap label
    ctx.save();
    ctx.font = `10px ${fonts.sans}`;
    ctx.fillStyle = colors.motorsport.pb;
    ctx.textAlign = 'right';
    ctx.fillText(`PB ${formatLapTime(bestTime)}`, margins.left + innerWidth - 4, bestY - 4);
    ctx.restore();

    // Average line
    ctx.save();
    ctx.strokeStyle = colors.text.muted;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    const avgY = yScale(avgTime);
    ctx.beginPath();
    ctx.moveTo(margins.left, avgY);
    ctx.lineTo(margins.left + innerWidth, avgY);
    ctx.stroke();
    ctx.restore();

    // Average label
    ctx.save();
    ctx.font = `10px ${fonts.sans}`;
    ctx.fillStyle = colors.text.muted;
    ctx.textAlign = 'right';
    ctx.fillText('avg', margins.left + innerWidth - 4, avgY - 4);
    ctx.restore();

    // X-axis
    ctx.save();
    ctx.strokeStyle = colors.axis;
    ctx.lineWidth = 1;
    const xAxisY = margins.top + innerHeight;
    ctx.beginPath();
    ctx.moveTo(margins.left, xAxisY);
    ctx.lineTo(margins.left + innerWidth, xAxisY);
    ctx.stroke();

    ctx.font = `10px ${fonts.sans}`;
    ctx.fillStyle = colors.text.secondary;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (let i = 0; i < sortedLaps.length; i++) {
      const x = xScale(i) + barWidth / 2;
      ctx.fillText(`L${sortedLaps[i].lap_number}`, x, xAxisY + 6);
      // Tick mark
      ctx.beginPath();
      ctx.moveTo(x, xAxisY);
      ctx.lineTo(x, xAxisY + 4);
      ctx.stroke();
    }
    ctx.restore();

    // Y-axis
    ctx.save();
    ctx.strokeStyle = colors.axis;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margins.left, margins.top);
    ctx.lineTo(margins.left, margins.top + innerHeight);
    ctx.stroke();

    ctx.font = `10px ${fonts.mono}`;
    ctx.fillStyle = colors.text.secondary;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= yTickCount; i++) {
      const val = yMin + i * yStep;
      const y = yScale(val);
      ctx.fillText(formatLapTime(val), margins.left - 6, y);
      // Tick mark
      ctx.beginPath();
      ctx.moveTo(margins.left - 4, y);
      ctx.lineTo(margins.left, y);
      ctx.stroke();
    }
    ctx.restore();
  }, [laps, dimensions, getDataCtx, report]);

  useEffect(() => {
    renderChart();
  }, [renderChart]);

  // Mouse events for hover tooltip
  useEffect(() => {
    const overlay = overlayCanvasRef.current;
    if (!overlay || !laps || laps.length === 0) return;

    const sortedLaps = [...laps].sort((a, b) => a.lap_number - b.lap_number);
    const barTotalWidth = dimensions.innerWidth / sortedLaps.length;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = overlay.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      if (mouseX < MARGINS.left || mouseX > MARGINS.left + dimensions.innerWidth) {
        setHoveredIdx(null);
        return;
      }
      const idx = Math.floor((mouseX - MARGINS.left) / barTotalWidth);
      if (idx >= 0 && idx < sortedLaps.length) {
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
  }, [laps, dimensions.innerWidth, overlayCanvasRef]);

  // Hover overlay rendering
  useEffect(() => {
    const ctx = getOverlayCtx();
    if (!ctx) return;
    ctx.clearRect(0, 0, dimensions.width, dimensions.height);

    if (hoveredIdx === null || !laps || laps.length === 0) return;

    const sortedLaps = [...laps].sort((a, b) => a.lap_number - b.lap_number);
    if (hoveredIdx < 0 || hoveredIdx >= sortedLaps.length) return;

    const lap = sortedLaps[hoveredIdx];
    const bestTime = Math.min(...sortedLaps.map((l) => l.lap_time_s));
    const barTotalWidth = dimensions.innerWidth / sortedLaps.length;
    const barWidth = barTotalWidth * (1 - BAR_PADDING);
    const barGap = barTotalWidth * BAR_PADDING;
    const barX = MARGINS.left + hoveredIdx * barTotalWidth + barGap / 2;
    const barCenterX = barX + barWidth / 2;

    // Highlight bar outline
    const yMin = Math.min(...sortedLaps.map((l) => l.lap_time_s)) - 2;
    const yMax = Math.max(...sortedLaps.map((l) => l.lap_time_s)) + 1;
    const yScale = (value: number) =>
      MARGINS.top + ((yMax - value) / (yMax - yMin)) * dimensions.innerHeight;

    const barY = yScale(lap.lap_time_s);
    const barH = yScale(yMin) - barY;

    ctx.strokeStyle = colors.text.primary;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(barX - 0.5, barY - 0.5, barWidth + 1, barH + 1);

    // Tooltip
    const delta = lap.lap_time_s - bestTime;
    const lines = [
      `L${lap.lap_number}: ${formatLapTime(lap.lap_time_s)}`,
      delta > 0 ? `+${formatLapTime(delta)} vs PB` : 'Personal Best',
    ];

    ctx.font = `11px ${fonts.mono}`;
    const lineHeight = 16;
    const maxTextWidth = Math.max(...lines.map((l) => ctx.measureText(l).width));
    const tooltipWidth = maxTextWidth + 16;
    const tooltipHeight = lines.length * lineHeight + 8;
    const tooltipX =
      barCenterX + tooltipWidth + 8 > MARGINS.left + dimensions.innerWidth
        ? barCenterX - tooltipWidth - 8
        : barCenterX + 8;
    const tooltipY = MARGINS.top + 4;

    // Tooltip background
    ctx.fillStyle = 'rgba(10, 12, 16, 0.92)';
    const r = 4;
    ctx.beginPath();
    ctx.moveTo(tooltipX + r, tooltipY);
    ctx.arcTo(tooltipX + tooltipWidth, tooltipY, tooltipX + tooltipWidth, tooltipY + tooltipHeight, r);
    ctx.arcTo(tooltipX + tooltipWidth, tooltipY + tooltipHeight, tooltipX, tooltipY + tooltipHeight, r);
    ctx.arcTo(tooltipX, tooltipY + tooltipHeight, tooltipX, tooltipY, r);
    ctx.arcTo(tooltipX, tooltipY, tooltipX + tooltipWidth, tooltipY, r);
    ctx.closePath();
    ctx.fill();

    // Tooltip text
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    for (let i = 0; i < lines.length; i++) {
      ctx.fillStyle = i === 0 ? colors.text.primary : colors.text.secondary;
      ctx.fillText(lines[i], tooltipX + 8, tooltipY + 4 + i * lineHeight);
    }
  }, [hoveredIdx, laps, dimensions, getOverlayCtx]);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Lap Times
        </h2>
        <div className="h-[220px] animate-pulse rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]" />
      </div>
    );
  }

  if (!laps || laps.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Lap Times
        </h2>
        <div className="flex h-[220px] items-center justify-center rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
          <p className="text-sm text-[var(--text-secondary)]">No lap data</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-4">
        <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Lap Times
        </h2>
        <div className="flex items-center gap-3 text-xs text-[var(--text-secondary)]">
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: colors.motorsport.pb }}
            />
            PB
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: colors.motorsport.optimal }}
            />
            Clean
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: colors.text.muted }}
            />
            Unclean
          </span>
        </div>
      </div>
      <div
        ref={containerRef}
        className="relative rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-2"
        style={{ height: CHART_HEIGHT }}
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
      </div>
    </div>
  );
}

'use client';

import { useMemo, useEffect } from 'react';
import { useGains } from '@/hooks/useAnalysis';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { SkeletonCard } from '@/components/shared/SkeletonCard';

interface CornerGain {
  name: string;
  gain_s: number;
  best_time_s: number;
  avg_time_s: number;
  best_lap: number;
  pct_of_total: number;
}

const MARGINS = { top: 4, right: 16, bottom: 4, left: 50 };

interface TimeGainedChartProps {
  sessionId: string;
}

export function TimeGainedChart({ sessionId }: TimeGainedChartProps) {
  const { data: gainsData, isLoading } = useGains(sessionId);

  const cornerGains = useMemo(() => {
    if (!gainsData) return [];

    // Navigate the gains data structure: gainsData.consistency.segment_gains
    const consistency = (gainsData as Record<string, unknown>)?.consistency as
      | Record<string, unknown>
      | undefined;
    if (!consistency) return [];

    const segmentGains = consistency.segment_gains as
      | Array<{
          segment: { name: string; is_corner: boolean };
          gain_s: number;
          best_time_s: number;
          avg_time_s: number;
          best_lap: number;
        }>
      | undefined;
    if (!segmentGains) return [];

    const corners = segmentGains
      .filter((sg) => sg.segment.is_corner && sg.gain_s > 0.01)
      .sort((a, b) => b.gain_s - a.gain_s);

    const totalGain = corners.reduce((sum, c) => sum + c.gain_s, 0);

    return corners.map(
      (sg): CornerGain => ({
        name: sg.segment.name,
        gain_s: sg.gain_s,
        best_time_s: sg.best_time_s,
        avg_time_s: sg.avg_time_s,
        best_lap: sg.best_lap,
        pct_of_total: totalGain > 0 ? (sg.gain_s / totalGain) * 100 : 0,
      }),
    );
  }, [gainsData]);

  const { containerRef, dataCanvasRef, dimensions } = useCanvasChart(MARGINS);

  // Draw bars
  useEffect(() => {
    const canvas = dataCanvasRef.current;
    if (!canvas || cornerGains.length === 0 || dimensions.width === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width, height, margins } = dimensions;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.setTransform(dimensions.dpr, 0, 0, dimensions.dpr, 0, 0);

    const chartW = width - margins.left - margins.right;
    const chartH = height - margins.top - margins.bottom;
    const barHeight = Math.min(22, chartH / cornerGains.length - 4);
    const barSpacing =
      cornerGains.length > 1
        ? (chartH - barHeight * cornerGains.length) / (cornerGains.length - 1)
        : 0;
    const maxGain = Math.max(...cornerGains.map((c) => c.gain_s));

    cornerGains.forEach((corner, i) => {
      const y = margins.top + i * (barHeight + barSpacing);
      const barW = maxGain > 0 ? (corner.gain_s / maxGain) * chartW : 0;

      // Color intensity based on severity
      const intensity = maxGain > 0 ? corner.gain_s / maxGain : 0;
      const r = Math.round(239 * (0.3 + 0.7 * intensity));
      const g = Math.round(68 * (1 - intensity * 0.5));
      const b = Math.round(68 * (1 - intensity * 0.5));

      // Bar
      ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.85)`;
      ctx.beginPath();
      ctx.roundRect(margins.left, y, barW, barHeight, 3);
      ctx.fill();

      // Corner name label
      ctx.fillStyle = 'rgba(200, 200, 210, 0.8)';
      ctx.font = '11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(corner.name, margins.left - 6, y + barHeight / 2);

      // Value label
      const label = `${corner.gain_s.toFixed(2)}s (${Math.round(corner.pct_of_total)}%)`;
      if (barW > 80) {
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 10px Inter, system-ui, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(label, margins.left + 6, y + barHeight / 2);
      } else {
        ctx.fillStyle = 'rgba(200, 200, 210, 0.6)';
        ctx.font = '10px Inter, system-ui, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(label, margins.left + barW + 4, y + barHeight / 2);
      }
    });

    ctx.restore();
  }, [cornerGains, dimensions, dataCanvasRef]);

  if (isLoading) {
    return <SkeletonCard height="h-40" />;
  }

  if (cornerGains.length === 0) {
    return null;
  }

  const chartHeight = Math.max(120, cornerGains.length * 28 + 16);

  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      <h3 className="mb-1 text-sm font-semibold text-[var(--text-primary)]">
        Time Left on Table by Corner
      </h3>
      <p className="mb-3 text-[10px] text-[var(--text-tertiary)]">
        Average vs. personal best per corner — where to focus practice
      </p>
      <div ref={containerRef} style={{ height: chartHeight }} className="relative">
        <canvas ref={dataCanvasRef} className="absolute inset-0" />
      </div>
    </div>
  );
}

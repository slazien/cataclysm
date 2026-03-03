'use client';

import { useMemo, useEffect } from 'react';
import { motion } from 'motion/react';
import { useOptimalComparison } from '@/hooks/useAnalysis';
import { useCanvasChart } from '@/hooks/useCanvasChart';
import { useUnits } from '@/hooks/useUnits';
import { SkeletonCard } from '@/components/shared/SkeletonCard';
import type { CornerOpportunity } from '@/lib/types';

const MARGINS = { top: 4, right: 16, bottom: 4, left: 50 };

/** Minimum speed gap (in mph) to display a corner row. */
const MIN_GAP_MPH = 0.5;

/** Interpolate between two hex colors (6-char, no '#'). */
function lerpColor(a: string, b: string, t: number): string {
  const clamp = Math.max(0, Math.min(1, t));
  const ar = parseInt(a.slice(0, 2), 16);
  const ag = parseInt(a.slice(2, 4), 16);
  const ab = parseInt(a.slice(4, 6), 16);
  const br = parseInt(b.slice(0, 2), 16);
  const bg = parseInt(b.slice(2, 4), 16);
  const bb = parseInt(b.slice(4, 6), 16);

  const r = Math.round(ar + (br - ar) * clamp);
  const g = Math.round(ag + (bg - ag) * clamp);
  const bl = Math.round(ab + (bb - ab) * clamp);
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${bl.toString(16).padStart(2, '0')}`;
}

// Green (small gap) -> Amber -> Red (large gap)
const COLOR_GREEN = '22c55e';
const COLOR_RED = 'ef4444';

interface OptimalGapChartProps {
  sessionId: string;
}

export function OptimalGapChart({ sessionId }: OptimalGapChartProps) {
  const { data: comparison, isLoading } = useOptimalComparison(sessionId);
  const { convertSpeed, speedUnit } = useUnits();

  // Filter to non-trivial gaps, already sorted by time_cost_s desc from backend
  const opportunities = useMemo(() => {
    if (!comparison?.corner_opportunities) return [];
    return comparison.corner_opportunities.filter(
      (opp) => opp.speed_gap_mph > MIN_GAP_MPH && opp.time_cost_s > 0,
    );
  }, [comparison]);

  const totalGapS = comparison?.total_gap_s ?? 0;

  const { containerRef, dataCanvasRef, dimensions } = useCanvasChart(MARGINS);

  // Draw bars
  useEffect(() => {
    const canvas = dataCanvasRef.current;
    if (!canvas || opportunities.length === 0 || dimensions.width === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width, height, margins } = dimensions;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.setTransform(dimensions.dpr, 0, 0, dimensions.dpr, 0, 0);

    const chartW = width - margins.left - margins.right;
    const chartH = height - margins.top - margins.bottom;
    const barHeight = Math.min(22, chartH / opportunities.length - 4);
    const barSpacing =
      opportunities.length > 1
        ? (chartH - barHeight * opportunities.length) / (opportunities.length - 1)
        : 0;
    const maxTimeCost = Math.max(...opportunities.map((o) => o.time_cost_s));

    opportunities.forEach((opp: CornerOpportunity, i: number) => {
      const y = margins.top + i * (barHeight + barSpacing);
      const barW = maxTimeCost > 0 ? (opp.time_cost_s / maxTimeCost) * chartW : 0;

      // Color gradient: green for small relative cost, red for large
      const intensity = maxTimeCost > 0 ? opp.time_cost_s / maxTimeCost : 0;
      const barColor = lerpColor(COLOR_GREEN, COLOR_RED, intensity);

      // Bar
      ctx.fillStyle = barColor + 'd9'; // ~85% opacity
      ctx.beginPath();
      ctx.roundRect(margins.left, y, barW, barHeight, 3);
      ctx.fill();

      // Corner name label (left of bar)
      ctx.fillStyle = 'rgba(200, 200, 210, 0.8)';
      ctx.font = '11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(`T${opp.corner_number}`, margins.left - 6, y + barHeight / 2);

      // Value label: "+X.X mph potential  ~0.Xs"
      const gapDisplay = convertSpeed(opp.speed_gap_mph).toFixed(1);
      const label = `+${gapDisplay} ${speedUnit}  ~${opp.time_cost_s.toFixed(1)}s`;
      if (barW > 140) {
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
  }, [opportunities, dimensions, dataCanvasRef, convertSpeed, speedUnit]);

  if (isLoading) {
    return <SkeletonCard height="h-40" />;
  }

  if (opportunities.length === 0) {
    return null;
  }

  const chartHeight = Math.max(120, opportunities.length * 28 + 16);

  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Speed vs Optimal
          </h3>
          <p className="text-[10px] text-[var(--text-tertiary)]">
            Per-corner speed gap vs physics-optimal profile — biggest opportunities first
          </p>
        </div>
        {totalGapS > 0 && (
          <span className="whitespace-nowrap rounded-full bg-[var(--color-throttle)]/10 px-2.5 py-0.5 text-xs font-semibold tabular-nums text-[var(--color-throttle)]">
            {totalGapS.toFixed(1)}s potential
          </span>
        )}
      </div>
      <div ref={containerRef} style={{ height: chartHeight }} className="relative">
        <motion.div
          initial={{ clipPath: 'inset(0 100% 0 0)' }}
          animate={{ clipPath: 'inset(0 0% 0 0)' }}
          transition={{ duration: 0.5, ease: 'easeOut', delay: 0.2 }}
          className="absolute inset-0"
        >
          <canvas ref={dataCanvasRef} className="absolute inset-0" />
        </motion.div>
      </div>
    </div>
  );
}

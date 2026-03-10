'use client';

import React, { useMemo, useEffect, useRef } from 'react';
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

interface BarRegion {
  cornerNumber: number;
  y: number;
  height: number;
}

interface OptimalGapChartProps {
  sessionId: string;
  onCornerClick?: (cornerNumber: number) => void;
}

function totalImpactS(opp: CornerOpportunity): number {
  return opp.time_cost_s + (opp.exit_straight_time_cost_s ?? 0);
}

export function OptimalGapChart({ sessionId, onCornerClick }: OptimalGapChartProps) {
  const { data: comparison, isLoading } = useOptimalComparison(sessionId);
  const { convertSpeed, speedUnit } = useUnits();
  const barRegionsRef = useRef<BarRegion[]>([]);
  const isInvalidComparison =
    comparison != null && (!comparison.is_valid || comparison.total_gap_s <= 0);
  const invalidReason = 'The physics-optimal reference was invalid for this session. Speed gap data is unavailable.';

  // Filter to non-trivial gaps, already sorted by time_cost_s desc from backend
  const opportunities = useMemo(() => {
    if (!comparison?.corner_opportunities) return [];
    return comparison.corner_opportunities
      .filter((opp) => opp.speed_gap_mph > MIN_GAP_MPH && totalImpactS(opp) > 0)
      .sort((a, b) => totalImpactS(b) - totalImpactS(a));
  }, [comparison]);

  const totalGapS = comparison?.total_gap_s ?? null;

  const straightsGapS = useMemo(() => {
    if (!comparison?.corner_opportunities || !comparison?.total_gap_s || comparison.total_gap_s <= 0) return 0;
    if (!comparison.is_valid) return 0;
    const allCornerCost = comparison.corner_opportunities.reduce((s, o) => s + totalImpactS(o), 0);
    const residual = comparison.total_gap_s - allCornerCost;
    return residual > 0.1 ? residual : 0;
  }, [comparison]);

  const { containerRef, dataCanvasRef, dimensions, getDataCtx } = useCanvasChart(MARGINS);

  // Draw bars
  useEffect(() => {
    const ctx = getDataCtx();
    if (!ctx || opportunities.length === 0 || dimensions.width === 0) return;

    const { width, height, margins } = dimensions;
    ctx.clearRect(0, 0, width, height);

    const chartW = width - margins.left - margins.right;
    const chartH = height - margins.top - margins.bottom;
    const displayCount = opportunities.length + (straightsGapS > 0 ? 1 : 0);
    const barHeight = Math.min(22, chartH / displayCount - 4);
    const barSpacing =
      displayCount > 1
        ? (chartH - barHeight * displayCount) / (displayCount - 1)
        : 0;
    const maxTimeCost = Math.max(...opportunities.map((o) => totalImpactS(o)), straightsGapS);

    // Build hit regions for click detection
    barRegionsRef.current = opportunities.map((opp, i) => ({
      cornerNumber: opp.corner_number,
      y: margins.top + i * (barHeight + barSpacing),
      height: barHeight,
    }));

    opportunities.forEach((opp: CornerOpportunity, i: number) => {
      const y = margins.top + i * (barHeight + barSpacing);
      const totalImpact = totalImpactS(opp);
      const exitCost = opp.exit_straight_time_cost_s ?? 0;
      const barW = maxTimeCost > 0 ? (totalImpact / maxTimeCost) * chartW : 0;

      // Color gradient: green for small relative cost, red for large
      const intensity = maxTimeCost > 0 ? totalImpact / maxTimeCost : 0;
      const barColor = lerpColor(COLOR_GREEN, COLOR_RED, intensity);

      // Bar
      ctx.fillStyle = barColor + 'd9'; // ~85% opacity
      ctx.beginPath();
      if (ctx.roundRect) {
        ctx.roundRect(margins.left, y, barW, barHeight, 3);
      } else {
        ctx.rect(margins.left, y, barW, barHeight);
      }
      ctx.fill();

      // Corner name label (left of bar)
      ctx.fillStyle = 'rgba(200, 200, 210, 0.8)';
      ctx.font = '11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(`T${opp.corner_number}`, margins.left - 6, y + barHeight / 2);

      // Value label: "+X.X mph potential  ~0.Xs"
      const gapDisplay = convertSpeed(opp.speed_gap_mph).toFixed(1);
      const label =
        exitCost > 0
          ? `~${opp.time_cost_s.toFixed(1)}s corner + ${exitCost.toFixed(1)}s exit = ${totalImpact.toFixed(1)}s`
          : `+${gapDisplay} ${speedUnit}  ~${opp.time_cost_s.toFixed(1)}s`;
      if (barW > 140) {
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 10px Inter, system-ui, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(label, margins.left + 6, y + barHeight / 2);
      } else {
        ctx.font = '10px Inter, system-ui, sans-serif';
        const labelX = margins.left + barW + 4;
        const textW = ctx.measureText(label).width;
        const rightBound = width - margins.right;
        if (labelX + textW > rightBound && barW >= 50) {
          // Not enough space outside — draw inside bar, right-aligned
          ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
          ctx.textAlign = 'right';
          ctx.fillText(label, margins.left + barW - 4, y + barHeight / 2);
        } else {
          ctx.fillStyle = 'rgba(200, 200, 210, 0.6)';
          ctx.textAlign = 'left';
          // Clip to right bound to avoid any overflow
          ctx.save();
          ctx.beginPath();
          ctx.rect(labelX, y, rightBound - labelX, barHeight + 2);
          ctx.clip();
          ctx.fillText(label, labelX, y + barHeight / 2);
          ctx.restore();
        }
      }
    });

    // --- Straights residual bar ---
    if (straightsGapS > 0) {
      const sIdx = opportunities.length;
      const sY = margins.top + sIdx * (barHeight + barSpacing);
      const sBarW = maxTimeCost > 0 ? (straightsGapS / maxTimeCost) * chartW : 0;

      // Muted blue-gray color for non-corner time
      ctx.fillStyle = 'rgba(148, 163, 184, 0.45)'; // slate-400 at 45%
      ctx.beginPath();
      if (ctx.roundRect) {
        ctx.roundRect(margins.left, sY, sBarW, barHeight, 3);
      } else {
        ctx.rect(margins.left, sY, sBarW, barHeight);
      }
      ctx.fill();

      // Label: "Str."
      ctx.fillStyle = 'rgba(148, 163, 184, 0.7)';
      ctx.font = '11px Inter, system-ui, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText('Str.', margins.left - 6, sY + barHeight / 2);

      // Value label: "~X.Xs straights" — clip to canvas right bound
      const sLabel = `~${straightsGapS.toFixed(1)}s straights`;
      const sLabelX = margins.left + sBarW + 4;
      const rightBound = width - margins.right;
      ctx.fillStyle = 'rgba(148, 163, 184, 0.6)';
      ctx.font = '10px Inter, system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.save();
      ctx.beginPath();
      ctx.rect(sLabelX, sY, rightBound - sLabelX, barHeight + 2);
      ctx.clip();
      ctx.fillText(sLabel, sLabelX, sY + barHeight / 2);
      ctx.restore();
    }

  }, [opportunities, dimensions, getDataCtx, convertSpeed, speedUnit, straightsGapS]);

  // Hit-test helper — reads bar regions at call time (ref is always current)
  const getHitCorner = (e: React.MouseEvent<HTMLCanvasElement>): BarRegion | undefined => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mouseY = e.clientY - rect.top;
    return barRegionsRef.current.find((r) => mouseY >= r.y && mouseY <= r.y + r.height);
  };

  if (isLoading) {
    return <SkeletonCard height="h-40" />;
  }

  if (opportunities.length === 0 && isInvalidComparison) {
    return (
      <div className="rounded-xl border border-[var(--color-brake)]/30 bg-[var(--color-brake)]/5 p-4">
        <div className="mb-1 flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Speed vs Optimal</h3>
          <span className="rounded-full bg-[var(--color-brake)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--color-brake)]">
            Optimal reference unavailable
          </span>
        </div>
        <p className="text-[11px] text-[var(--text-secondary)]">
          {invalidReason}
        </p>
      </div>
    );
  }

  if (opportunities.length === 0) {
    return (
      <p className="py-2 text-center text-xs text-[var(--text-secondary)]">
        No significant speed gaps found — you&apos;re close to the physics-optimal profile.
      </p>
    );
  }

  const displayCount = opportunities.length + (straightsGapS > 0 ? 1 : 0);
  const chartHeight = Math.max(120, displayCount * 28 + 16);

  return (
    <div className="rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Speed vs Optimal
          </h3>
          <p className="text-[11px] text-[var(--text-secondary)]">
            Time gap vs physics-optimal profile — biggest opportunities first
          </p>
        </div>
        {totalGapS !== null && totalGapS > 0 && (
          <span className="whitespace-nowrap rounded-full bg-[var(--color-throttle)]/10 px-2.5 py-0.5 text-xs font-semibold tabular-nums text-[var(--color-throttle)]">
            {isInvalidComparison ? '~' : ''}{totalGapS.toFixed(1)}s potential
          </span>
        )}
      </div>
      {isInvalidComparison && opportunities.length > 0 && (
        <div className="mb-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-1.5">
          <p className="text-[11px] text-amber-400">
            {comparison && comparison.total_gap_s <= 0
              ? 'Physics model estimates are approximate — overall gap is negative, individual corners may still be directionally useful'
              : 'Some per-corner estimates are approximate — the model is slower than your actual speed at a few corners'}
          </p>
        </div>
      )}
      <div ref={containerRef} style={{ height: chartHeight }} className="relative">
        <motion.div
          initial={{ clipPath: 'inset(0 100% 0 0)' }}
          animate={{ clipPath: 'inset(0 0% 0 0)' }}
          transition={{ duration: 0.5, ease: 'easeOut', delay: 0.2 }}
          className="absolute inset-0"
        >
          <canvas
            ref={dataCanvasRef}
            className="absolute inset-0"
            onClick={onCornerClick ? (e) => { const hit = getHitCorner(e); if (hit) onCornerClick(hit.cornerNumber); } : undefined}
            onMouseMove={onCornerClick ? (e) => { e.currentTarget.style.cursor = getHitCorner(e) ? 'pointer' : 'default'; } : undefined}
            onMouseLeave={onCornerClick ? (e) => { e.currentTarget.style.cursor = 'default'; } : undefined}
          />
        </motion.div>
      </div>
      {onCornerClick && (
        <p className="mt-2 text-[10px] text-[var(--text-secondary)] opacity-60">
          Click any bar to explore in Deep Dive →
        </p>
      )}
    </div>
  );
}

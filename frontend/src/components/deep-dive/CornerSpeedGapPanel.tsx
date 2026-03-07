'use client';

import { useMemo, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useOptimalComparison } from '@/hooks/useAnalysis';
import { useAnalysisStore } from '@/stores';
import { useUnits } from '@/hooks/useUnits';
import { parseCornerNumber } from '@/lib/cornerUtils';
import { SkeletonCard } from '@/components/shared/SkeletonCard';
import { InfoTooltip } from '@/components/shared/InfoTooltip';
import { cn } from '@/lib/utils';
import type { CornerOpportunity } from '@/lib/types';

/** Minimum speed gap (in mph) to show a corner row. */
const MIN_GAP_MPH = 0.3;

/** Interpolate between two hex colors (6-char, no '#'). */
function lerpColor(a: string, b: string, t: number): string {
  const clamp = Math.max(0, Math.min(1, t));
  const parse = (hex: string, offset: number) => parseInt(hex.slice(offset, offset + 2), 16);
  const mix = (ac: number, bc: number) => Math.round(ac + (bc - ac) * clamp);

  const r = mix(parse(a, 0), parse(b, 0));
  const g = mix(parse(a, 2), parse(b, 2));
  const bl = mix(parse(a, 4), parse(b, 4));
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${bl.toString(16).padStart(2, '0')}`;
}

const COLOR_GREEN = '22c55e';
const COLOR_AMBER = 'f59e0b';
const COLOR_RED = 'ef4444';

function gapColor(ratio: number): string {
  // 0..0.5 => green->amber, 0.5..1 => amber->red
  if (ratio <= 0.5) return lerpColor(COLOR_GREEN, COLOR_AMBER, ratio * 2);
  return lerpColor(COLOR_AMBER, COLOR_RED, (ratio - 0.5) * 2);
}

interface CornerSpeedGapPanelProps {
  sessionId: string;
  selectedCorner: number | null;
}

/** Row in the overview bar chart. */
function GapBar({
  opp,
  maxTimeCost,
  isSelected,
  isHovered,
  onHover,
  onClick,
  convertSpeed,
  speedUnit,
}: {
  opp: CornerOpportunity;
  maxTimeCost: number;
  isSelected: boolean;
  isHovered: boolean;
  onHover: (corner: number | null) => void;
  onClick: (corner: number) => void;
  convertSpeed: (mph: number) => number;
  speedUnit: string;
}) {
  const widthPct = maxTimeCost > 0 ? (opp.time_cost_s / maxTimeCost) * 100 : 0;
  const intensity = maxTimeCost > 0 ? opp.time_cost_s / maxTimeCost : 0;
  const barColor = gapColor(intensity);
  const gapDisplay = convertSpeed(opp.speed_gap_mph).toFixed(1);

  return (
    <motion.button
      className={cn(
        'group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors',
        isSelected
          ? 'bg-[var(--bg-elevated)] ring-1 ring-[var(--cata-accent)]'
          : isHovered
            ? 'bg-[var(--bg-elevated)]/60'
            : 'hover:bg-[var(--bg-elevated)]/40',
      )}
      onMouseEnter={() => onHover(opp.corner_number)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onClick(opp.corner_number)}
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
    >
      {/* Corner label */}
      <span className="w-7 shrink-0 text-right text-xs font-medium tabular-nums text-[var(--text-secondary)]">
        T{opp.corner_number}
      </span>

      {/* Bar container */}
      <div className="relative flex h-5 flex-1 items-center">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-sm"
          style={{ backgroundColor: barColor, opacity: isHovered || isSelected ? 0.95 : 0.75 }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(widthPct, 2)}%` }}
          transition={{ duration: 0.4, ease: 'easeOut', delay: 0.05 }}
        />
        {/* Label inside or outside bar */}
        <span
          className={cn(
            'relative z-10 whitespace-nowrap text-[11px] font-medium tabular-nums',
            widthPct > 45 ? 'pl-1.5 text-white' : 'text-[var(--text-secondary)]',
          )}
          style={widthPct <= 45 ? { paddingLeft: `calc(${Math.max(widthPct, 2)}% + 6px)` } : undefined}
        >
          +{gapDisplay} {speedUnit} / ~{opp.time_cost_s.toFixed(2)}s
        </span>
      </div>
    </motion.button>
  );
}

/** Focused detail view for a single corner. */
function CornerFocusView({
  opp,
  convertSpeed,
  speedUnit,
}: {
  opp: CornerOpportunity;
  convertSpeed: (mph: number) => number;
  speedUnit: string;
}) {
  const yourSpeed = convertSpeed(opp.actual_min_speed_mph);
  const optimalSpeed = convertSpeed(opp.optimal_min_speed_mph);
  const maxSpeed = Math.max(yourSpeed, optimalSpeed);
  const yourPct = maxSpeed > 0 ? (yourSpeed / maxSpeed) * 100 : 0;
  const optimalPct = maxSpeed > 0 ? (optimalSpeed / maxSpeed) * 100 : 0;
  const absGap = Math.abs(convertSpeed(opp.speed_gap_mph));
  const gapDisplay = absGap.toFixed(1);
  const hasTimeCost = opp.time_cost_s > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
      className="space-y-3"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-[var(--text-primary)] font-[family-name:var(--font-display)]">
          Turn {opp.corner_number} Breakdown
        </h4>
        <span
          className={cn(
            'rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums',
            hasTimeCost
              ? 'bg-[var(--color-brake)]/10 text-[var(--color-brake)]'
              : 'bg-[var(--text-muted)]/10 text-[var(--text-secondary)]',
          )}
        >
          {hasTimeCost
            ? `~${opp.time_cost_s.toFixed(2)}s cost`
            : 'No measurable gap'}
        </span>
      </div>

      {/* Side-by-side speed comparison */}
      <div className="space-y-2">
        {/* Your speed bar */}
        <div className="space-y-1">
          <div className="flex items-baseline justify-between">
            <span className="text-[11px] text-[var(--text-secondary)]">Your Min Speed</span>
            <span className="text-sm font-medium tabular-nums text-[var(--text-primary)]">
              {yourSpeed.toFixed(1)} {speedUnit}
            </span>
          </div>
          <div className="h-3 w-full overflow-hidden rounded-full bg-[var(--bg-elevated)]">
            <motion.div
              className="h-full rounded-full bg-[var(--cata-accent)]"
              initial={{ width: 0 }}
              animate={{ width: `${yourPct}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>
        </div>

        {/* Optimal speed bar */}
        <div className="space-y-1">
          <div className="flex items-baseline justify-between">
            <span className="text-[11px] text-[var(--text-secondary)]">Optimal Min Speed</span>
            <span className="text-sm font-medium tabular-nums text-[var(--color-throttle)]">
              {optimalSpeed.toFixed(1)} {speedUnit}
            </span>
          </div>
          <div className="h-3 w-full overflow-hidden rounded-full bg-[var(--bg-elevated)]">
            <motion.div
              className="h-full rounded-full bg-[var(--color-throttle)]"
              initial={{ width: 0 }}
              animate={{ width: `${optimalPct}%` }}
              transition={{ duration: 0.5, ease: 'easeOut', delay: 0.1 }}
            />
          </div>
        </div>
      </div>

      {/* Insight text */}
      <div className="rounded-lg bg-[var(--bg-elevated)] px-3 py-2">
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
          {hasTimeCost ? (
            <>
              {'You\'re losing '}
              <span className="font-semibold tabular-nums text-[var(--color-brake)]">
                ~{opp.time_cost_s.toFixed(2)}s
              </span>
              {' at Turn '}
              <span className="font-semibold text-[var(--text-primary)]">{opp.corner_number}</span>
              {' — closing the '}
              <span className="font-semibold tabular-nums text-[var(--cata-accent)]">
                {gapDisplay} {speedUnit}
              </span>
              {' speed gap would save '}
              <span className="font-semibold tabular-nums text-[var(--color-throttle)]">
                ~{opp.time_cost_s.toFixed(2)}s
              </span>
              {' per lap.'}
            </>
          ) : (
            <>
              {'Your speed at Turn '}
              <span className="font-semibold text-[var(--text-primary)]">{opp.corner_number}</span>
              {' is close to the model\'s prediction — no significant gap detected.'}
            </>
          )}
        </p>
      </div>
    </motion.div>
  );
}

export function CornerSpeedGapPanel({ sessionId, selectedCorner }: CornerSpeedGapPanelProps) {
  const { data: comparison, isLoading } = useOptimalComparison(sessionId);
  const { convertSpeed, speedUnit } = useUnits();
  const selectCorner = useAnalysisStore((s) => s.selectCorner);
  const [hoveredCorner, setHoveredCorner] = useState<number | null>(null);

  const isInvalidComparison =
    comparison != null && (!comparison.is_valid || comparison.total_gap_s <= 0);

  // Filter and sort opportunities by time cost (biggest first)
  const opportunities = useMemo(() => {
    if (!comparison?.corner_opportunities) return [];
    return comparison.corner_opportunities
      .filter((opp) => opp.speed_gap_mph > MIN_GAP_MPH && opp.time_cost_s > 0)
      .sort((a, b) => b.time_cost_s - a.time_cost_s);
  }, [comparison]);

  const maxTimeCost = useMemo(
    () => Math.max(...opportunities.map((o) => o.time_cost_s), 0),
    [opportunities],
  );

  const totalGapS = Math.max(comparison?.total_gap_s ?? 0, 0);

  // Find the focused opportunity for selectedCorner — search ALL corner data,
  // not just the filtered opportunities list, so corners where the driver is
  // faster than optimal still show the breakdown view.
  const focusedOpp = useMemo(
    () =>
      selectedCorner !== null
        ? comparison?.corner_opportunities?.find((o) => o.corner_number === selectedCorner) ?? null
        : null,
    [comparison, selectedCorner],
  );

  const handleCornerClick = useCallback(
    (corner: number) => {
      selectCorner(`T${corner}`);
    },
    [selectCorner],
  );

  if (isLoading) {
    return <SkeletonCard height="h-40" />;
  }

  if (opportunities.length === 0 && !focusedOpp && isInvalidComparison) {
    return (
      <div className="rounded-xl border border-[var(--color-brake)]/30 bg-[var(--color-brake)]/5 p-4">
        <h3 className="mb-1 text-sm font-semibold text-[var(--text-primary)] font-[family-name:var(--font-display)]">
          Speed Gap vs Optimal
        </h3>
        <p className="text-xs text-[var(--text-secondary)]">
          The physics-optimal reference was invalid for this session. Speed gap data is unavailable.
        </p>
      </div>
    );
  }

  if (opportunities.length === 0 && !focusedOpp) {
    return null;
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-3">
      {/* Header */}
      <div className="mb-2 flex items-baseline justify-between">
        <div>
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-[var(--text-primary)] font-[family-name:var(--font-display)]">
            Speed Gap vs Optimal
            <InfoTooltip helpKey="chart.speed-gap" />
          </h3>
          <p className="text-[11px] text-[var(--text-secondary)]">
            Per-corner time cost from speed deficit
          </p>
        </div>
        {!isInvalidComparison && totalGapS > 0 && (
          <span className="whitespace-nowrap rounded-full bg-[var(--color-brake)]/10 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-[var(--color-brake)]">
            {totalGapS.toFixed(1)}s total
          </span>
        )}
      </div>

      {isInvalidComparison && opportunities.length > 0 && (
        <div className="mb-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-1.5">
          <p className="text-[11px] text-amber-400">
            Estimates are approximate — overall gap is negative, individual corners may still be useful
          </p>
        </div>
      )}

      {/* Content area */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <AnimatePresence mode="wait">
          {focusedOpp ? (
            <CornerFocusView
              key={`focus-${focusedOpp.corner_number}`}
              opp={focusedOpp}
              convertSpeed={convertSpeed}
              speedUnit={speedUnit}
            />
          ) : (
            <motion.div
              key="overview"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="space-y-0.5"
            >
              {opportunities.map((opp) => (
                <GapBar
                  key={opp.corner_number}
                  opp={opp}
                  maxTimeCost={maxTimeCost}
                  isSelected={opp.corner_number === selectedCorner}
                  isHovered={opp.corner_number === hoveredCorner}
                  onHover={setHoveredCorner}
                  onClick={handleCornerClick}
                  convertSpeed={convertSpeed}
                  speedUnit={speedUnit}
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

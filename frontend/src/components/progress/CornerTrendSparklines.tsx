'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { useUnits } from '@/hooks/useUnits';
import { InfoTooltip } from '@/components/shared/InfoTooltip';

interface CornerTrendSparklinesProps {
  cornerMinSpeedTrends: Record<string, (number | null)[]>;
  className?: string;
}

interface SparklineData {
  cornerKey: string;
  values: (number | null)[];
  latestValue: number | null;
  trend: 'improving' | 'regressing' | 'flat';
}

const TREND_COLORS = {
  improving: { stroke: '#22c55e', bg: 'rgba(34, 197, 94, 0.08)', text: 'text-green-400' },
  regressing: { stroke: '#ef4444', bg: 'rgba(239, 68, 68, 0.08)', text: 'text-red-400' },
  flat: { stroke: '#f59e0b', bg: 'rgba(245, 158, 11, 0.08)', text: 'text-amber-400' },
} as const;

/** Determine trend direction from a series of values */
function detectTrend(values: (number | null)[]): 'improving' | 'regressing' | 'flat' {
  const valid = values.filter((v): v is number => v != null);
  if (valid.length < 2) return 'flat';

  // Compare average of first half vs second half
  const mid = Math.floor(valid.length / 2);
  const firstHalf = valid.slice(0, mid);
  const secondHalf = valid.slice(mid);

  const firstAvg = firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length;
  const secondAvg = secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length;

  const delta = secondAvg - firstAvg;
  // Threshold: 1 mph change is meaningful for corner min speed
  if (delta > 1) return 'improving';
  if (delta < -1) return 'regressing';
  return 'flat';
}

function Sparkline({ data, width, height }: { data: SparklineData; width: number; height: number }) {
  const valid = data.values
    .map((v, i) => (v != null ? { x: i, y: v } : null))
    .filter((p): p is { x: number; y: number } => p != null);

  if (valid.length < 2) {
    return (
      <svg width={width} height={height} className="opacity-30">
        <text
          x={width / 2}
          y={height / 2}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="currentColor"
          fontSize={9}
          className="text-[var(--text-secondary)]"
        >
          --
        </text>
      </svg>
    );
  }

  const colors = TREND_COLORS[data.trend];

  // Compute scales
  const minY = Math.min(...valid.map((p) => p.y));
  const maxY = Math.max(...valid.map((p) => p.y));
  const yRange = maxY - minY || 1;
  const padding = 2;

  const xScale = (x: number) =>
    padding + ((x - valid[0].x) / (valid[valid.length - 1].x - valid[0].x || 1)) * (width - padding * 2);
  const yScale = (y: number) =>
    height - padding - ((y - minY) / yRange) * (height - padding * 2);

  const points = valid.map((p) => `${xScale(p.x).toFixed(1)},${yScale(p.y).toFixed(1)}`).join(' ');

  // Area fill path
  const areaPath = [
    `M ${xScale(valid[0].x).toFixed(1)},${height}`,
    ...valid.map((p) => `L ${xScale(p.x).toFixed(1)},${yScale(p.y).toFixed(1)}`),
    `L ${xScale(valid[valid.length - 1].x).toFixed(1)},${height}`,
    'Z',
  ].join(' ');

  return (
    <svg width={width} height={height}>
      <path d={areaPath} fill={colors.bg} />
      <polyline
        points={points}
        fill="none"
        stroke={colors.stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* Latest point dot */}
      <circle
        cx={xScale(valid[valid.length - 1].x)}
        cy={yScale(valid[valid.length - 1].y)}
        r={2.5}
        fill={colors.stroke}
      />
    </svg>
  );
}

export function CornerTrendSparklines({
  cornerMinSpeedTrends,
  className,
}: CornerTrendSparklinesProps) {
  const { convertSpeed, speedUnit } = useUnits();
  const sparklines: SparklineData[] = useMemo(() => {
    const keys = Object.keys(cornerMinSpeedTrends).sort(
      (a, b) => parseInt(a) - parseInt(b),
    );
    return keys.map((key) => {
      const values = cornerMinSpeedTrends[key];
      const validValues = values.filter((v): v is number => v != null);
      const latestValue = validValues.length > 0 ? validValues[validValues.length - 1] : null;
      return {
        cornerKey: key,
        values,
        latestValue,
        trend: detectTrend(values),
      };
    });
  }, [cornerMinSpeedTrends]);

  if (sparklines.length === 0) return null;

  return (
    <div
      className={cn(
        'rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4',
        className,
      )}
    >
      <h3 className="mb-3 flex items-center gap-1.5 font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">
        Corner Speed Trends
        <InfoTooltip helpKey="chart.corner-sparklines" />
      </h3>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {sparklines.map((data) => {
          const colors = TREND_COLORS[data.trend];
          return (
            <div
              key={data.cornerKey}
              className="flex items-center gap-2 rounded-md border border-[var(--cata-border)] bg-[var(--bg-elevated)] px-2.5 py-2"
            >
              <div className="min-w-0 shrink-0">
                <p className="text-[11px] font-medium text-[var(--text-secondary)]">
                  T{data.cornerKey}
                </p>
                <p className={cn('text-sm font-semibold tabular-nums', colors.text)}>
                  {data.latestValue != null ? `${convertSpeed(data.latestValue).toFixed(0)}` : '--'}
                </p>
                <p className="text-[10px] text-[var(--text-secondary)]">{speedUnit}</p>
              </div>
              <div className="min-w-0 flex-1">
                <Sparkline data={data} width={72} height={28} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

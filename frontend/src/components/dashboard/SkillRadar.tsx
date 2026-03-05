'use client';

import { useMemo, useState } from 'react';
import { History } from 'lucide-react';
import { useCoachingReport } from '@/hooks/useCoaching';
import { useSkillHistory } from '@/hooks/useSkillHistory';
import { RadarChart } from '@/components/shared/RadarChart';
import {
  computeSkillDimensions,
  dimensionsToArray,
  SKILL_AXES,
} from '@/lib/skillDimensions';
import { InfoTooltip } from '@/components/shared/InfoTooltip';
interface SkillRadarProps {
  sessionId: string;
}

/**
 * Formats a session_date string (e.g. "2025-06-14") into a compact label.
 * Falls back to the raw string if parsing fails.
 */
function formatShortDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

/**
 * Compute opacity for a historical entry.
 * Most recent historical session = 0.20, oldest = 0.08.
 * `index` is 0-based from oldest, `total` is the number of historical entries.
 */
function historyOpacity(index: number, total: number): number {
  if (total <= 1) return 0.15;
  // Linear interpolation: oldest (index 0) = 0.08, newest (index total-1) = 0.20
  return 0.08 + (index / (total - 1)) * 0.12;
}

/**
 * Build a hex color with an alpha channel suffix for SVG fill.
 * E.g. "#6366f1" + opacity 0.15 -> "rgba(99,102,241,0.15)".
 */
function colorWithOpacity(hex: string, opacity: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${opacity})`;
}

const INDIGO = '#6366f1';

export function SkillRadar({ sessionId }: SkillRadarProps) {
  const { data: report } = useCoachingReport(sessionId);
  const { history } = useSkillHistory(sessionId);
  const [showHistory, setShowHistory] = useState(true);

  const dimensions = useMemo(() => {
    if (!report?.corner_grades || report.corner_grades.length === 0) return null;
    return computeSkillDimensions(report.corner_grades);
  }, [report]);

  if (!dimensions) return null;

  const values = dimensionsToArray(dimensions);
  const avgScore = Math.round(values.reduce((a, b) => a + b, 0) / values.length);

  // Build datasets: historical entries first (rendered behind), current on top
  const datasets = useMemo(() => {
    const ds: Array<{
      label: string;
      values: number[];
      color: string;
      fillOpacity?: number;
      strokeOpacity?: number;
      showDots?: boolean;
    }> = [];

    if (showHistory && history.length > 0) {
      for (let i = 0; i < history.length; i++) {
        const entry = history[i];
        const opacity = historyOpacity(i, history.length);
        ds.push({
          label: formatShortDate(entry.date),
          values: entry.values,
          color: INDIGO,
          fillOpacity: opacity,
          strokeOpacity: opacity + 0.1,
          showDots: false,
        });
      }
    }

    // Current session — always last (rendered on top)
    ds.push({
      label: 'Current',
      values,
      color: INDIGO,
    });

    return ds;
  }, [showHistory, history, values]);

  const hasHistory = history.length > 0;

  return (
    <div className="self-start rounded-xl border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      {/* Header */}
      <div className="mb-2 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-[var(--text-primary)]">
          Skill Profile
          <InfoTooltip helpKey="chart.skill-radar" />
        </h3>
        <div className="flex items-center gap-2">
          {hasHistory && (
            <button
              type="button"
              onClick={() => setShowHistory((v) => !v)}
              className={`flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                showHistory
                  ? 'bg-indigo-500/20 text-indigo-400'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
              }`}
              title={showHistory ? 'Hide session history' : 'Show session history'}
            >
              <History className="h-3 w-3" />
              History
            </button>
          )}
          <span className="text-xs text-[var(--text-tertiary)]">Avg: {avgScore}/100</span>
        </div>
      </div>

      {/* Radar chart */}
      <RadarChart
        axes={SKILL_AXES}
        datasets={datasets}
        size={200}
      />

      {/* Legend (only when history is shown and there are entries) */}
      {showHistory && hasHistory && (
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 px-1">
          {history.map((entry, i) => (
            <div key={entry.sessionId} className="flex items-center gap-1">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{
                  backgroundColor: colorWithOpacity(INDIGO, historyOpacity(i, history.length) + 0.2),
                }}
              />
              <span className="text-[10px] text-[var(--text-muted)]">
                {formatShortDate(entry.date)}
              </span>
            </div>
          ))}
          <div className="flex items-center gap-1">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: INDIGO }}
            />
            <span className="text-[10px] font-medium text-[var(--text-secondary)]">Current</span>
          </div>
        </div>
      )}
    </div>
  );
}

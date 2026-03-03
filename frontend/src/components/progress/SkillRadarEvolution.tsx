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
import { ChartErrorBoundary } from '@/components/shared/ChartErrorBoundary';
import { cn } from '@/lib/utils';

interface SkillRadarEvolutionProps {
  /** The most recent session ID at the current track. */
  sessionId: string;
  /** Track name displayed in the card header. */
  trackName: string;
}

/** Palette for historical layers (oldest to newest). */
const HISTORY_COLORS = ['#8b5cf6', '#a78bfa', '#6366f1'] as const;
const CURRENT_COLOR = '#6366f1';

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
 * Most recent historical session = 0.22, oldest = 0.10.
 */
function historyOpacity(index: number, total: number): number {
  if (total <= 1) return 0.18;
  return 0.10 + (index / (total - 1)) * 0.12;
}

/**
 * Self-contained card component showing skill radar evolution over sessions.
 * Renders the latest session's radar in full color with historical session
 * overlays showing progression over time.
 */
export function SkillRadarEvolution({ sessionId, trackName }: SkillRadarEvolutionProps) {
  const { data: report } = useCoachingReport(sessionId);
  const { history, isLoading } = useSkillHistory(sessionId);
  const [showHistory, setShowHistory] = useState(true);

  const dimensions = useMemo(() => {
    if (!report?.corner_grades || report.corner_grades.length === 0) return null;
    return computeSkillDimensions(report.corner_grades);
  }, [report]);

  // Build datasets: historical entries first (rendered behind), current on top
  const datasets = useMemo(() => {
    if (!dimensions) return [];
    const values = dimensionsToArray(dimensions);

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
        const color = HISTORY_COLORS[i % HISTORY_COLORS.length];
        ds.push({
          label: formatShortDate(entry.date),
          values: entry.values,
          color,
          fillOpacity: opacity,
          strokeOpacity: opacity + 0.15,
          showDots: false,
        });
      }
    }

    // Current session - always last (rendered on top)
    ds.push({
      label: 'Latest',
      values,
      color: CURRENT_COLOR,
    });

    return ds;
  }, [showHistory, history, dimensions]);

  const avgScore = useMemo(() => {
    if (!dimensions) return 0;
    const values = dimensionsToArray(dimensions);
    return Math.round(values.reduce((a, b) => a + b, 0) / values.length);
  }, [dimensions]);

  // Don't render if no coaching data available
  if (!dimensions || isLoading) return null;

  const hasHistory = history.length > 0;

  return (
    <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="font-[family-name:var(--font-display)] text-sm font-medium text-[var(--text-secondary)]">
            Skill Evolution
          </h3>
          <p className="text-xs text-[var(--text-muted)]">{trackName}</p>
        </div>
        <div className="flex items-center gap-2">
          {hasHistory && (
            <button
              type="button"
              onClick={() => setShowHistory((v) => !v)}
              className={cn(
                'flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors',
                showHistory
                  ? 'bg-indigo-500/20 text-indigo-400'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]',
              )}
              title={showHistory ? 'Hide session history' : 'Show session history'}
            >
              <History className="h-3 w-3" />
              {showHistory ? 'History On' : 'History Off'}
            </button>
          )}
          <span className="text-xs text-[var(--text-tertiary)]">Avg: {avgScore}/100</span>
        </div>
      </div>

      {/* Radar chart */}
      <ChartErrorBoundary name="Skill Radar Evolution">
        <div className="mx-auto w-fit">
          <RadarChart axes={SKILL_AXES} datasets={datasets} size={220} />
        </div>
      </ChartErrorBoundary>

      {/* Session legend */}
      {showHistory && hasHistory && (
        <div className="mt-3 space-y-1 border-t border-[var(--cata-border)] pt-3">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            Sessions
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
            {history.map((entry, i) => {
              const color = HISTORY_COLORS[i % HISTORY_COLORS.length];
              const opacity = historyOpacity(i, history.length);
              return (
                <div key={entry.sessionId} className="flex items-center gap-1.5">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-sm"
                    style={{
                      backgroundColor: color,
                      opacity: opacity + 0.25,
                    }}
                  />
                  <span className="text-[11px] text-[var(--text-muted)]">
                    {formatShortDate(entry.date)}
                  </span>
                </div>
              );
            })}
            <div className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ backgroundColor: CURRENT_COLOR }}
              />
              <span className="text-[11px] font-medium text-[var(--text-secondary)]">
                Latest
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

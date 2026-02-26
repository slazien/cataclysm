'use client';

import { useMemo } from 'react';
import type { Milestone, TrendSessionSummary } from '@/lib/types';
import { parseSessionDate } from '@/lib/formatters';

interface MilestoneTimelineProps {
  sessions: TrendSessionSummary[];
  milestones: Milestone[];
  className?: string;
}

const CATEGORY_CONFIG: Record<string, { color: string; label: string }> = {
  pb: { color: '#a855f7', label: 'PB' },
  consistency: { color: '#3b82f6', label: 'Consistency' },
  corner_improvement: { color: '#22c55e', label: 'Corner' },
  general: { color: '#f59e0b', label: 'General' },
};

function getCategoryConfig(category: string) {
  return CATEGORY_CONFIG[category] ?? { color: '#f59e0b', label: category };
}

function formatDate(dateStr: string): string {
  const d = parseSessionDate(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatShortDate(dateStr: string): string {
  const d = parseSessionDate(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function MilestoneTimeline({ sessions, milestones, className }: MilestoneTimelineProps) {
  // Sort milestones newest-first
  const sortedMilestones = useMemo(() => {
    return [...milestones].sort((a, b) => {
      const da = parseSessionDate(a.session_date).getTime();
      const db = parseSessionDate(b.session_date).getTime();
      return db - da;
    });
  }, [milestones]);

  // Session count for the summary line
  const sessionCount = sessions.length;
  const dateRange = useMemo(() => {
    if (sessions.length === 0) return '';
    const first = formatShortDate(sessions[0].session_date);
    const last = formatShortDate(sessions[sessions.length - 1].session_date);
    return first === last ? first : `${first} – ${last}`;
  }, [sessions]);

  if (milestones.length === 0) {
    return (
      <div className={className}>
        <p className="py-6 text-center text-sm text-[var(--text-muted)]">
          No milestones yet — keep driving!
        </p>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Summary bar */}
      <div className="mb-3 flex items-center gap-3 text-xs text-[var(--text-muted)]">
        <span>{sortedMilestones.length} milestones across {sessionCount} sessions</span>
        <span className="text-[var(--text-muted)]/50">•</span>
        <span>{dateRange}</span>
      </div>

      {/* Scrollable vertical timeline */}
      <div className="max-h-[240px] overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
        <div className="relative pl-6">
          {/* Vertical line */}
          <div
            className="absolute left-[9px] top-1 bottom-1 w-px"
            style={{ backgroundColor: 'var(--cata-border, #1c1f27)' }}
          />

          {sortedMilestones.map((m, i) => {
            const { color, label } = getCategoryConfig(m.category);
            return (
              <div key={`${m.session_date}-${m.category}-${i}`} className="relative pb-4 last:pb-0">
                {/* Dot on the timeline */}
                <div
                  className="absolute left-[-18px] top-[5px] h-[10px] w-[10px] rounded-full ring-2 ring-[var(--bg-surface)]"
                  style={{ backgroundColor: color }}
                />

                {/* Content */}
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm leading-snug text-[var(--text-primary)]">
                      {m.description}
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      <span
                        className="inline-block rounded px-1.5 py-0.5 text-[10px] font-medium leading-none"
                        style={{ backgroundColor: `${color}20`, color }}
                      >
                        {label}
                      </span>
                      <span className="text-[11px] text-[var(--text-muted)]">
                        {formatDate(m.session_date)}
                      </span>
                    </div>
                  </div>

                  {/* Value badge (e.g., lap time) */}
                  {m.value > 0 && (
                    <span className="shrink-0 font-mono text-xs text-[var(--text-secondary)]">
                      {m.category === 'pb'
                        ? `${Math.floor(m.value / 60)}:${(m.value % 60).toFixed(2).padStart(5, '0')}`
                        : m.value.toFixed(1)}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

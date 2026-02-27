'use client';

import type { SessionSummary } from '@/lib/types';
import type { GPSQualityReport } from '@/lib/types';

interface SessionReportHeaderProps {
  session: SessionSummary | null;
  gpsQuality: GPSQualityReport | null;
}

export function SessionReportHeader({ session, gpsQuality }: SessionReportHeaderProps) {
  const score = session?.session_score;
  const scoreColor = score != null
    ? score >= 80 ? 'text-green-400' : score >= 60 ? 'text-yellow-400' : 'text-red-400'
    : 'text-[var(--text-muted)]';

  return (
    <div className="flex items-center gap-5">
      {/* Score circle */}
      <div className="relative flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4 border-[var(--cata-border)] bg-[var(--bg-elevated)]">
        <span className={`text-2xl font-bold ${scoreColor}`}>
          {score != null ? Math.round(score) : '\u2014'}
        </span>
        <span className="absolute -bottom-1 rounded-full bg-[var(--bg-surface)] px-1.5 text-[10px] font-medium text-[var(--text-muted)]">
          SCORE
        </span>
      </div>

      {/* Track info */}
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-xl font-semibold text-[var(--text-primary)]">
          {session?.track_name ?? 'Loading...'}
        </h1>
        <p className="text-sm text-[var(--text-muted)]">{session?.session_date ?? ''}</p>
      </div>

      {/* Badges */}
      <div className="flex shrink-0 items-center gap-2">
        {gpsQuality && (
          <span className="rounded-full bg-[var(--bg-elevated)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
            GPS {gpsQuality.grade}
          </span>
        )}
        {session?.weather_condition && (
          <span className="rounded-full bg-[var(--bg-elevated)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
            {session.weather_temp_c != null ? `${Math.round(session.weather_temp_c)}\u00B0C` : ''} {session.weather_condition}
          </span>
        )}
      </div>
    </div>
  );
}
